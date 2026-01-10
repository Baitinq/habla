#!/usr/bin/env python3
import sys
import os
import argparse
import socket
import threading
import numpy as np
import scipy.signal
import sounddevice as sd
from pywhispercpp.model import Model

WHISPER_SAMPLERATE = 16000
MODEL = os.getenv("MODEL", "large-v3-turbo-q8_0")
SOCKET_PATH = os.path.expanduser("~/.habla.sock")
CHUNK_INTERVAL = int(os.getenv("CHUNK_INTERVAL", "3"))


class Recorder:
    def __init__(self):
        self.recording = False
        self.audio_data = []
        self.stream = None
        self.streaming_conn = None
        self.transcribe_thread = None
        self.stop_event = threading.Event()

        print(f"Loading model: {MODEL}", file=sys.stderr)
        self.model = Model(MODEL, language="en")

        self.samplerate = int(sd.query_devices(kind="input")["default_samplerate"])
        sd.default.samplerate = self.samplerate
        sd.default.channels = 1

    def _callback(self, indata, frames, time_info, status):
        if self.recording:
            self.audio_data.append(indata.copy())

    def _transcribe_audio(self, audio):
        """Transcribe audio array, handling resampling."""
        if len(audio) == 0:
            return ""

        audio = audio.flatten()
        if self.samplerate != WHISPER_SAMPLERATE:
            num_samples = int(len(audio) * WHISPER_SAMPLERATE / self.samplerate)
            audio = scipy.signal.resample(audio, num_samples)

        segments = self.model.transcribe(audio)
        return " ".join(s.text for s in segments).strip()

    def _streaming_loop(self):
        """Background thread that transcribes chunks and streams them."""
        processed_chunks = 0

        while self.recording:
            if self.stop_event.wait(timeout=CHUNK_INTERVAL):
                break  # Stop was signaled

            current_chunks = len(self.audio_data)
            if current_chunks > processed_chunks:
                new_audio = self.audio_data[processed_chunks:current_chunks]
                processed_chunks = current_chunks

                audio = np.concatenate(new_audio, axis=0)
                text = self._transcribe_audio(audio)

                if text and self.streaming_conn:
                    try:
                        self.streaming_conn.sendall((text + "\n").encode())
                    except (BrokenPipeError, OSError):
                        break

        # Transcribe any remaining audio
        if len(self.audio_data) > processed_chunks:
            remaining_audio = self.audio_data[processed_chunks:]
            audio = np.concatenate(remaining_audio, axis=0)
            text = self._transcribe_audio(audio)

            if text and self.streaming_conn:
                try:
                    self.streaming_conn.sendall((text + "\n").encode())
                except (BrokenPipeError, OSError):
                    pass

    def start(self, streaming_conn=None):
        if self.recording:
            return
        self.recording = True
        self.audio_data = []
        self.streaming_conn = streaming_conn
        self.stop_event.clear()

        print("Recording...", file=sys.stderr)
        self.stream = sd.InputStream(callback=self._callback)
        self.stream.start()

        if streaming_conn:
            self.transcribe_thread = threading.Thread(target=self._streaming_loop, daemon=True)
            self.transcribe_thread.start()

    def stop(self):
        if not self.recording:
            return
        self.recording = False
        self.stop_event.set()  # Wake up streaming thread immediately

        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        # Wait for streaming thread to finish
        if self.transcribe_thread:
            self.transcribe_thread.join(timeout=30)
            self.transcribe_thread = None

        # Close streaming connection
        if self.streaming_conn:
            try:
                self.streaming_conn.close()
            except:
                pass
            self.streaming_conn = None


def send_command(cmd):
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(SOCKET_PATH)
        sock.sendall(cmd.encode())

        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            text = chunk.decode()
            if text:
                print(text, end="", flush=True)

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
                    conn.sendall(b"")
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
        if recorder.recording:
            recorder.stop()
    finally:
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
