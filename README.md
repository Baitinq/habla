<p align="center">
  <img src="logo.svg" alt="habla logo" width="120" height="120">
</p>

<h1 align="center">habla</h1>

<p align="center">
  <strong>Fast, private, cross-platform voice-to-text</strong>
</p>

**habla** is a local voice-to-text daemon powered by NVIDIA Parakeet TDT 0.6B v2, sherpa-onnx, and Silero VAD. It
runs the same English INT8 ONNX model on macOS and Linux, segments speech at natural pauses, and writes finalized
transcriptions to stdout for hotkeys and scripts.

## Features

- Fully local after the first model download
- English-only Parakeet TDT 0.6B v2
- Punctuation and capitalization
- The same ONNX implementation on macOS and Linux
- Silero voice activity detection with its standard endpointing defaults
- Lazy model loading and automatic unload after five idle minutes
- Background daemon controlled through a Unix socket

## Requirements

- macOS or Linux on ARM64 or x86-64
- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- A microphone and PortAudio

Install PortAudio if it is not already available:

```bash
brew install portaudio                # macOS
sudo apt install libportaudio2        # Debian/Ubuntu
```

## Installation

```bash
git clone https://github.com/baitinq/habla
cd habla
./scripts/install
```

The English Parakeet INT8 model (~634 MB) and Silero VAD model download on first start and are cached under
`~/.cache/habla`.

## Usage

Start the daemon:

```bash
habla
```

From another terminal:

```bash
habla --toggle    # Start recording; run again to stop
habla --status    # Print recording or idle
```

The first `habla --toggle` process stays open. Each finalized utterance is printed after Silero detects its standard
500 ms silence endpoint. Stopping
recording finalizes the current utterance immediately and closes the process.

### Stream to the clipboard

```bash
habla --toggle | pbcopy
# Speak, then run `habla --toggle` again.
```

### Type into the active application on macOS

```bash
habla --toggle | while IFS= read -r line; do
    osascript -e "tell application \"System Events\" to keystroke \"$line \""
done
```

## Start automatically on macOS

Create `~/Library/LaunchAgents/com.habla.daemon.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.habla.daemon</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/YOUR_USERNAME/.local/bin/habla</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardErrorPath</key>
    <string>/tmp/habla.log</string>
</dict>
</plist>
```

Then load it:

```bash
launchctl load ~/Library/LaunchAgents/com.habla.daemon.plist
```

## Start automatically on Linux

Create `~/.config/systemd/user/habla.service`:

```ini
[Unit]
Description=Habla voice-to-text daemon

[Service]
ExecStart=%h/.local/bin/habla
Restart=always

[Install]
WantedBy=default.target
```

Enable it:

```bash
systemctl --user daemon-reload
systemctl --user enable --now habla
```

## Configuration

| Environment variable | Default | Description |
|---|---|---|
| `HABLA_MODEL_DIR` | `~/.cache/habla` | Model cache directory |
| `HABLA_ONNX_PROVIDER` | automatic | `cuda` on Linux x86-64 with NVIDIA; `cpu` otherwise |
| `HABLA_ONNX_THREADS` | `4` | ONNX inference threads |
| `HABLA_UNLOAD_AFTER` | `300` | Idle seconds before unloading the model; `0` disables unloading |

On Linux x86-64, installation uses sherpa-onnx's CUDA 12.8 + cuDNN 9 wheel. Habla selects its CUDA provider when
`nvidia-smi` is available and otherwise uses the bundled CPU provider. macOS and Linux ARM64 use the CPU wheel.

## Architecture

The daemon captures 16 kHz Float32 microphone audio and feeds it through Silero VAD in 32 ms windows. After Silero's
default 500 ms silence endpoint, the completed speech segment is decoded once with the English Parakeet INT8 model and
written to the active `habla --toggle` client. Stopping capture flushes the current speech segment. The microphone starts
before a cold model load, so audio spoken during loading is retained. After five idle minutes, the model is released and
loaded again on the next recording.

Finalized utterances are used instead of unstable partial hypotheses because keyboard injection cannot safely revise text
that has already been typed into another application.

## Development

```bash
uv sync
uv run habla
```
