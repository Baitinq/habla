<p align="center">
  <img src="logo.svg" alt="habla logo" width="120" height="120">
</p>

<h1 align="center">habla</h1>

<p align="center">
  <strong>Voice-to-text daemon powered by Whisper</strong>
</p>

<p align="center">
  <a href="#installation">Installation</a> •
  <a href="#usage">Usage</a> •
  <a href="#vibe-coding-setup-macos">Vibe Coding Setup</a> •
  <a href="#configuration">Configuration</a> •
  <a href="#how-it-works">How It Works</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12+-3776ab?logo=python&logoColor=white" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/whisper-large--v3--turbo-6366f1" alt="Whisper">
</p>

---

**habla** (Spanish for *"speak"*) is a lightweight voice-to-text daemon that transcribes speech in real-time using OpenAI's Whisper model via [whisper.cpp](https://github.com/ggerganov/whisper.cpp). It runs as a background service and outputs transcriptions to stdout, making it easy to pipe into other tools and workflows.

## Features

- **Daemon Architecture** — Runs in the background, controlled via simple commands
- **Streaming Transcription** — Text streams to stdout as you speak
- **Whisper-powered** — Uses state-of-the-art speech recognition
- **Unix-friendly** — Outputs to stdout for easy piping and scripting
- **Toggle Support** — Perfect for binding to a hotkey
- **CUDA Acceleration** — Optional GPU support for faster transcription

## Installation

### Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) package manager
- Python 3.12+
- A microphone

**Linux users:** Add yourself to the `input` group for microphone access:
```bash
sudo usermod -aG input $USER
```

### Install with CUDA (NVIDIA GPUs)

```bash
uv tool install --reinstall -Caccel=cuda git+https://github.com/baitinq/habla
```

### Install CPU-only

```bash
uv tool install --reinstall git+https://github.com/baitinq/habla
```

## Usage

### Start the daemon

```bash
habla
```

The daemon loads the Whisper model and listens for commands on `~/.habla.sock`.

### Control recording

From another terminal (or via hotkey):

```bash
habla --toggle    # Toggle recording on/off
habla --status    # Check if recording or idle
```

### Example: Stream to clipboard

```bash
# macOS - collects all chunks, then paste
habla --toggle | pbcopy
# (press toggle again to stop, then Cmd+V to paste)

# Linux (X11)
habla --toggle | xclip -selection clipboard
```

### Example: Real-time typing

```bash
# Type directly into active window as you speak
habla --toggle | while IFS= read -r line; do
    osascript -e "tell application \"System Events\" to keystroke \"$line \""
done
```

### Vibe Coding Setup (macOS)

For a seamless voice-to-text workflow while coding, you can set up habla to start automatically and bind it to a hotkey that pastes transcriptions directly.

#### 1. Auto-start the daemon with launchd

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

#### 2. Hotkey with skhd

Install [skhd](https://github.com/koekeishiya/skhd) and add to `~/.skhdrc`:

```bash
# Toggle recording and type transcription in real-time
alt - space : habla --toggle | while IFS= read -r line; do osascript -e "tell application \"System Events\" to keystroke \"$line \""; done
```

This binds `Alt+Space` to toggle recording. Text is typed directly into your active window as you speak. Press `Alt+Space` again to stop.

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `MODEL` | `large-v3-turbo-q8_0` | Whisper model to use |
| `CHUNK_INTERVAL` | `3` | Seconds between streaming transcriptions (use large value for batch mode) |
| `SILENCE_THRESHOLD` | `0.01` | Audio RMS threshold for voice detection (set to `0` to disable) |

### Available models

```bash
MODEL=tiny.en habla      # Fastest, English-only
MODEL=base.en habla      # Fast, English-only
MODEL=small habla        # Balanced
MODEL=large-v3-turbo-q8_0 habla  # Best quality (default)
```

Models are automatically downloaded on first use.

## How It Works

```
┌─────────────────────────────────────────────────────────┐
│                      habla daemon                       │
│                                                         │
│  ┌─────────────┐    ┌─────────────┐    ┌────────────┐  │
│  │  Microphone │───▶│   Recorder  │───▶│   Whisper  │  │
│  └─────────────┘    └─────────────┘    └────────────┘  │
│                            │                  │         │
│                            ▼                  ▼         │
│                     Unix Socket          stdout        │
│                    (~/.habla.sock)     (transcription)  │
└─────────────────────────────────────────────────────────┘
         ▲
         │ toggle/status
         │
┌────────┴────────┐
│  habla --toggle │
│  habla --status │
└─────────────────┘
```

1. The daemon starts and loads the Whisper model
2. It listens for commands on a Unix socket
3. On `toggle`, it begins recording and transcribing in chunks (~3 seconds)
4. Each chunk is streamed to stdout as it's ready
5. On the next `toggle`, it transcribes any remaining audio and stops

## Development

```bash
# Clone the repo
git clone https://github.com/baitinq/habla
cd habla

# Using Nix (recommended)
nix develop
uv sync

# Or manually with uv
uv sync
```

## Dependencies

- [numpy](https://numpy.org/) — Audio data handling
- [scipy](https://scipy.org/) — Audio resampling
- [sounddevice](https://python-sounddevice.readthedocs.io/) — Microphone access
- [pywhispercpp](https://github.com/absadiki/pywhispercpp) — Whisper.cpp Python bindings
