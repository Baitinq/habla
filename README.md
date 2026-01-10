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
- **Real-time Transcription** — Record and transcribe speech on demand
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
habla --start     # Begin recording
habla --stop      # Stop and transcribe
habla --toggle    # Toggle recording on/off
habla --status    # Check if recording or idle
```

### Example: Pipe to clipboard

```bash
# macOS
habla --toggle && sleep 3 && habla --toggle | pbcopy

# Linux (X11)
habla --toggle && sleep 3 && habla --toggle | xclip -selection clipboard
```

### Example: Bind to a hotkey

Bind `habla --toggle` to a key combination in your window manager or keyboard settings. Each press starts or stops recording, with the transcription printed when you stop.

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
# Toggle recording and paste transcription
alt - space : habla --toggle | pbcopy && osascript -e 'tell application "System Events" to keystroke "v" using command down'
```

This binds `Alt+Space` to toggle recording. When you stop, the transcription is copied to clipboard and pasted at your cursor.

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `MODEL` | `large-v3-turbo-q8_0` | Whisper model to use |

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
         │ start/stop/toggle/status
         │
┌────────┴────────┐
│  habla --start  │
│  habla --stop   │
│  habla --toggle │
└─────────────────┘
```

1. The daemon starts and loads the Whisper model
2. It listens for commands on a Unix socket
3. On `start`, it begins recording audio from your microphone
4. On `stop`, it resamples the audio to 16kHz and transcribes it
5. The transcription is printed to stdout

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
