#!/usr/bin/env python3
import argparse
import os
from pathlib import Path
import platform
import shutil
import socket
import sys
import tarfile
import threading
import urllib.request

import numpy as np
import sherpa_onnx
import sounddevice as sd

ASR_SAMPLERATE = 16000
SOCKET_PATH = os.path.expanduser("~/.habla.sock")
STREAM_INTERVAL = 0.1
MODEL_NAME = "sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8"
MODEL_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
    f"{MODEL_NAME}.tar.bz2"
)
VAD_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
    "silero_vad.onnx"
)


def download_models():
    cache_dir = Path(os.getenv("HABLA_MODEL_DIR", Path.home() / ".cache" / "habla"))
    model_dir = cache_dir / MODEL_NAME
    vad_path = cache_dir / "silero_vad.onnx"

    cache_dir.mkdir(parents=True, exist_ok=True)
    model_files = (
        "encoder.int8.onnx",
        "decoder.int8.onnx",
        "joiner.int8.onnx",
        "tokens.txt",
    )
    if not all((model_dir / name).exists() for name in model_files):
        archive = cache_dir / f"{MODEL_NAME}.tar.bz2"
        print("Downloading English Parakeet v2 INT8 model…", file=sys.stderr)
        urllib.request.urlretrieve(MODEL_URL, archive)
        with tarfile.open(archive) as tar:
            tar.extractall(cache_dir, filter="data")
        archive.unlink()

    if not vad_path.exists():
        print("Downloading Silero VAD model…", file=sys.stderr)
        urllib.request.urlretrieve(VAD_URL, vad_path)

    return model_dir, vad_path


class Parakeet:
    def __init__(self):
        model_dir, vad_path = download_models()
        default_provider = (
            "cuda"
            if platform.system() == "Linux"
            and platform.machine() == "x86_64"
            and shutil.which("nvidia-smi")
            else "cpu"
        )
        provider = os.getenv("HABLA_ONNX_PROVIDER", default_provider)
        threads = int(os.getenv("HABLA_ONNX_THREADS", min(4, os.cpu_count())))

        print(f"Loading English Parakeet v2 INT8 ({provider})…", file=sys.stderr)
        self.recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(model_dir / "encoder.int8.onnx"),
            decoder=str(model_dir / "decoder.int8.onnx"),
            joiner=str(model_dir / "joiner.int8.onnx"),
            tokens=str(model_dir / "tokens.txt"),
            num_threads=threads,
            sample_rate=ASR_SAMPLERATE,
            feature_dim=128,
            provider=provider,
            model_type="nemo_transducer",
        )

        self.vad_config = sherpa_onnx.VadModelConfig()
        self.vad_config.silero_vad.model = str(vad_path)
        self.vad_config.silero_vad.min_silence_duration = 0.5
        self.vad_config.silero_vad.min_speech_duration = 0.15
        self.vad_config.silero_vad.max_speech_duration = 15
        self.vad_config.sample_rate = ASR_SAMPLERATE
        self.vad = self._new_vad()
        self.pending_audio = np.empty(0, dtype=np.float32)

    def _new_vad(self):
        return sherpa_onnx.VoiceActivityDetector(
            self.vad_config,
            buffer_size_in_seconds=30,
        )

    def start(self):
        self.vad.reset()
        self.pending_audio = np.empty(0, dtype=np.float32)

    def accept_audio(self, audio):
        self.pending_audio = np.concatenate((self.pending_audio, audio))
        window_size = self.vad_config.silero_vad.window_size
        complete_samples = len(self.pending_audio) // window_size * window_size

        for offset in range(0, complete_samples, window_size):
            self.vad.accept_waveform(self.pending_audio[offset : offset + window_size])
        self.pending_audio = self.pending_audio[complete_samples:]

    def transcribe(self, audio):
        if len(audio) < ASR_SAMPLERATE:
            audio = np.pad(audio, (0, ASR_SAMPLERATE - len(audio)))
        stream = self.recognizer.create_stream()
        stream.accept_waveform(ASR_SAMPLERATE, audio)
        self.recognizer.decode_stream(stream)
        return stream.result.text.strip()

    def finalized_segments(self):
        while not self.vad.empty():
            yield self.transcribe(np.asarray(self.vad.front.samples, dtype=np.float32))
            self.vad.pop()

    def finish(self):
        if len(self.pending_audio):
            window_size = self.vad_config.silero_vad.window_size
            audio = np.pad(
                self.pending_audio,
                (0, window_size - len(self.pending_audio)),
            )
            self.vad.accept_waveform(audio)
            self.pending_audio = np.empty(0, dtype=np.float32)
        self.vad.flush()
        return list(self.finalized_segments())


class Recorder:
    def __init__(self):
        self.recording = False
        self.audio_data = []
        self.audio_lock = threading.Lock()
        self.stream = None
        self.streaming_conn = None
        self.transcribe_thread = None
        self.stop_event = threading.Event()
        self.asr = Parakeet()

        sd.check_input_settings(
            device=sd.default.device[0],
            channels=1,
            dtype="float32",
            samplerate=ASR_SAMPLERATE,
        )

    def _callback(self, indata, frames, time_info, status):
        if self.recording:
            with self.audio_lock:
                self.audio_data.append(indata.copy())

    def _take_audio(self):
        with self.audio_lock:
            chunks = self.audio_data
            self.audio_data = []
        if not chunks:
            return None
        return np.concatenate(chunks, axis=0).flatten()

    def _send_text(self, text):
        if not text or not self.streaming_conn:
            return
        try:
            self.streaming_conn.sendall((text + "\n").encode())
        except (BrokenPipeError, OSError):
            pass

    def _transcription_loop(self):
        while not self.stop_event.wait(timeout=STREAM_INTERVAL):
            audio = self._take_audio()
            if audio is not None:
                self.asr.accept_audio(audio)
            for transcript in self.asr.finalized_segments():
                self._send_text(transcript)

        audio = self._take_audio()
        if audio is not None:
            self.asr.accept_audio(audio)
        for transcript in self.asr.finish():
            self._send_text(transcript)

    def start(self, streaming_conn=None):
        if self.recording:
            return
        self.asr.start()
        self.recording = True
        with self.audio_lock:
            self.audio_data = []
        self.streaming_conn = streaming_conn
        self.stop_event.clear()

        print("Recording...", file=sys.stderr)
        self.stream = sd.InputStream(
            samplerate=ASR_SAMPLERATE,
            channels=1,
            dtype="float32",
            callback=self._callback,
        )
        self.stream.start()

        if streaming_conn:
            self.transcribe_thread = threading.Thread(target=self._transcription_loop, daemon=True)
            self.transcribe_thread.start()

    def stop(self):
        if not self.recording:
            return
        self.recording = False

        self.stream.stop()
        self.stream.close()
        self.stream = None

        self.stop_event.set()
        if self.transcribe_thread:
            self.transcribe_thread.join()
            self.transcribe_thread = None

        if self.streaming_conn:
            self.streaming_conn.close()
            self.streaming_conn = None

    def close(self):
        if self.recording:
            self.stop()


def send_command(cmd):
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(SOCKET_PATH)
        sock.sendall(cmd.encode())

        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            print(chunk.decode(), end="", flush=True)

        sock.close()
    except (FileNotFoundError, ConnectionRefusedError):
        print("Daemon not running. Start with: habla", file=sys.stderr)
        sys.exit(1)


def daemon():
    recorder = Recorder()

    if os.path.exists(SOCKET_PATH):
        os.remove(SOCKET_PATH)

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(SOCKET_PATH)
    server.listen(1)

    print(f"Listening on {SOCKET_PATH}", file=sys.stderr)

    try:
        while True:
            conn, _ = server.accept()
            cmd = conn.recv(1024).decode().strip()

            if cmd == "toggle":
                if recorder.recording:
                    recorder.stop()
                    conn.close()
                else:
                    recorder.start(streaming_conn=conn)
            elif cmd == "status":
                status = "recording" if recorder.recording else "idle"
                conn.sendall((status + "\n").encode())
                conn.close()
            else:
                conn.sendall(b"unknown\n")
                conn.close()
    except KeyboardInterrupt:
        pass
    finally:
        recorder.close()
        server.close()
        if os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)


def main():
    parser = argparse.ArgumentParser(description="Voice-to-text daemon")
    parser.add_argument("--toggle", action="store_true", help="Toggle recording")
    parser.add_argument("--status", action="store_true", help="Get status")
    args = parser.parse_args()

    if args.toggle:
        send_command("toggle")
    elif args.status:
        send_command("status")
    else:
        daemon()


if __name__ == "__main__":
    main()
