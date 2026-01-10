#!/usr/bin/env python3
import sys
import os
import argparse
import socket
import numpy as np
import scipy.signal
import sounddevice as sd
from pywhispercpp.model import Model

WHISPER_SAMPLERATE = 16000
MODEL = os.getenv("MODEL", "large-v3-turbo-q8_0")
SOCKET_PATH = os.path.expanduser("~/.habla.sock")


class Recorder:
    def __init__(self):
        self.recording = False
        self.audio_data = []
        self.stream = None

        print(f"Loading model: {MODEL}", file=sys.stderr)
        self.model = Model(MODEL, language="en")

        self.samplerate = int(sd.query_devices(kind="input")["default_samplerate"])
        sd.default.samplerate = self.samplerate
        sd.default.channels = 1

    def _callback(self, indata, frames, time, status):
        if self.recording:
            self.audio_data.append(indata.copy())

    def start(self):
        if self.recording:
            return
        self.recording = True
        self.audio_data = []
        print("Recording...", file=sys.stderr)
        self.stream = sd.InputStream(callback=self._callback)
        self.stream.start()

    def stop(self):
        if not self.recording:
            return ""
        self.recording = False

        if self.stream:
            self.stream.stop()
            self.stream.close()

        if not self.audio_data:
            return ""

        audio = np.concatenate(self.audio_data, axis=0)

        if self.samplerate != WHISPER_SAMPLERATE:
            num_samples = int(len(audio) * WHISPER_SAMPLERATE / self.samplerate)
            audio = scipy.signal.resample(audio, num_samples)

        print("Transcribing...", file=sys.stderr)
        segments = self.model.transcribe(audio)
        text = " ".join(s.text for s in segments).strip()

        return text


def send_command(cmd):
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(SOCKET_PATH)
        sock.sendall(cmd.encode())
        chunks = []
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
        sock.close()
        return b"".join(chunks).decode()
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
            try:
                cmd = conn.recv(1024).decode().strip()
                if cmd == "start":
                    recorder.start()
                    conn.sendall(b"")
                elif cmd == "stop":
                    text = recorder.stop()
                    conn.sendall(text.encode())
                elif cmd == "toggle":
                    if recorder.recording:
                        text = recorder.stop()
                        conn.sendall(text.encode())
                    else:
                        recorder.start()
                        conn.sendall(b"")
                elif cmd == "status":
                    conn.sendall(b"recording" if recorder.recording else b"idle")
                else:
                    conn.sendall(b"unknown")
            finally:
                conn.close()
    except KeyboardInterrupt:
        if recorder.recording:
            text = recorder.stop()
            if text:
                print(text, end="", flush=True)
    finally:
        server.close()
        if os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)


def main():
    parser = argparse.ArgumentParser(description="Voice-to-text daemon")
    parser.add_argument("--start", action="store_true", help="Start recording")
    parser.add_argument("--stop", action="store_true", help="Stop recording")
    parser.add_argument("--toggle", action="store_true", help="Toggle recording")
    parser.add_argument("--status", action="store_true", help="Get status")
    args = parser.parse_args()

    if args.start:
        send_command("start")
    elif args.stop:
        text = send_command("stop")
        if text:
            print(text, end="", flush=True)
    elif args.toggle:
        text = send_command("toggle")
        if text:
            print(text, end="", flush=True)
    elif args.status:
        print(send_command("status"))
    else:
        daemon()


if __name__ == "__main__":
    main()
