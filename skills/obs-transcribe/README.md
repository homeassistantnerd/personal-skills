# OBS to Transcript Skill for Google NotebookLM

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![FFmpeg](https://img.shields.io/badge/ffmpeg-required-green.svg)](https://ffmpeg.org/)
[![Groq Whisper](https://img.shields.io/badge/Groq-Whisper%20Large%20v3-orange.svg)](https://groq.com/)
[![NotebookLM Ready](https://img.shields.io/badge/NotebookLM-compatible-blueviolet.svg)](https://notebooklm.google.com/)

A specialized Claude Code skill and CLI tool to convert large (5GB+, 2–3+ hours) OBS online class recordings into clean, speech-optimized audio files strictly under Google NotebookLM's **200 MB** limit, paired with highly accurate **Vietnamese/multilingual transcriptions** generated in seconds via Groq Whisper Large v3.

---

## The Problem It Solves

- **5GB+ Video Files**: OBS recordings of online classes and lectures are too large to upload directly to NotebookLM (limit: **200 MB** for audio/video).
- **Fluctuating Classroom Audio**: Lecturer microphones often distort or spike while student questions are too quiet to hear.
- **Slow Transcription**: Local Whisper models can take 30–60 minutes for a 2-hour lecture on consumer hardware.

## How It Works

```
Large OBS Recording (5GB+, 2-3h)
             │
             ▼
┌────────────────────────────────────────────────────────┐
│ 1. FFmpeg Audio Extraction & Speech Filtering          │
│    - Downmix to Mono (-ac 1)                           │
│    - Speech bandpass: highpass=80Hz, lowpass=8000Hz    │
│    - Dynamic audio leveling via dynaudnorm             │
│    - Codec: MP3 64kbps, 16kHz                          │
│    - Result: 3h lecture = ~82 MB (strictly < 200 MB)   │
└──────────────────────────┬─────────────────────────────┘
                           │ Outputs <name>_clean.mp3 (<200MB)
                           ▼
┌────────────────────────────────────────────────────────┐
│ 2. Groq Chunking & Transcription Engine                │
│    - Auto-splits audio > 20MB into 15-min chunks       │
│      using lossless FFmpeg stream-copy (-c copy)       │
│    - Concurrently transcribes chunks via Groq API      │
│      (whisper-large-v3, Vietnamese language)          │
│    - Reassembles unified timeline with exact offsets   │
│    - Fast: ~15-30s for an entire 2-3h recording        │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│ 3. NotebookLM Output Formatting                        │
│    - <name>_clean.mp3 (Speech audio < 200MB)           │
│    - <name>_transcript.md (Markdown with time blocks)  │
│    - <name>_transcript.txt (Plain text backup)        │
└────────────────────────────────────────────────────────┘
```

---

## Outputs Generated

| File | Description | Recommended NotebookLM Use |
|---|---|---|
| `<name>_clean.mp3` | Mono 64kbps volume-leveled speech audio (< 200 MB) | Audio Source (for NotebookLM Audio Overview) |
| `<name>_transcript.md` | Structured Markdown with metadata and ~2.5-min timestamped sections | **Document Source** (best for instant summaries, study guides, Q&A) |
| `<name>_transcript.txt` | Clean timestamped text file | Quick search, note archiving, or copy-pasting |

---

## Prerequisites

1. **Python 3.9+**
2. **FFmpeg** installed and accessible on your system PATH:
   - **Windows:** `winget install Gyan.FFmpeg` or `choco install ffmpeg`
   - **macOS:** `brew install ffmpeg`
   - **Linux:** `sudo apt install ffmpeg`
3. **Groq API Key**:
   - Free account with generous rate limits at [console.groq.com/keys](https://console.groq.com/keys).

---

## Installation

### Method A: Install as a Global Claude Code Skill (Recommended)

Clone directly into your Claude skills directory:

**Windows (PowerShell):**
```powershell
git clone https://github.com/homeassistantnerd/obs-to-transcript-skill.git "$HOME\.claude\skills\obs-transcribe"
pip install -r "$HOME\.claude\skills\obs-transcribe\requirements.txt"
```

**macOS / Linux:**
```bash
git clone https://github.com/homeassistantnerd/obs-to-transcript-skill.git ~/.claude/skills/obs-transcribe
pip install -r ~/.claude/skills/obs-transcribe/requirements.txt
```

### Method B: Standalone CLI Tool

Clone to any directory on your computer:
```bash
git clone https://github.com/homeassistantnerd/obs-to-transcript-skill.git
cd obs-to-transcript-skill
pip install -r requirements.txt
```

---

## Configuration

Set your Groq API key using any of the following methods:

1. **In a `.env` file** (copy from `.env.example`):
   ```bash
   cp .env.example .env
   ```
   Edit `.env`:
   ```env
   GROQ_API_KEY=gsk_your_actual_key_here
   ```
2. **Or as an environment variable**:
   - **Windows (CMD):** `set GROQ_API_KEY=gsk_...`
   - **Windows (PowerShell):** `$env:GROQ_API_KEY="gsk_..."`
   - **macOS / Linux:** `export GROQ_API_KEY="gsk_..."`
3. **Or pass it directly via CLI:** `--api-key "gsk_..."`

---

## Usage

### 1. In Claude Code
Whenever you are working in Claude Code, simply run:
```bash
/obs-transcribe "C:\path\to\recording.mkv"
```
Or specify an output folder:
```bash
/obs-transcribe "C:\path\to\recording.mp4" -o "C:\path\to\output"
```

### 2. Standalone Terminal / CLI
```bash
python scripts/process_recording.py -i "path/to/recording.mkv"
```

#### CLI Options
```text
usage: process_recording.py [-h] -i INPUT [-o OUTPUT_DIR] [-k API_KEY]
                            [-b BITRATE] [--chunk-minutes CHUNK_MINUTES]
                            [--audio-only] [--transcribe-only]

options:
  -i, --input INPUT               Path to OBS recording file (.mkv, .mp4, .mov, etc.)
  -o, --output-dir OUTPUT_DIR     Output folder (defaults to recording's folder)
  -k, --api-key API_KEY           Groq API key (or set via GROQ_API_KEY)
  -b, --bitrate BITRATE           Audio compression bitrate (default: 64k)
  --chunk-minutes CHUNK_MINUTES   Minutes per chunk for Groq limit (default: 15)
  --audio-only                    Only extract and clean audio, skip transcription
  --transcribe-only               Input is already an audio file, skip extraction
```

---

## Google NotebookLM Workflow

1. Navigate to [Google NotebookLM](https://notebooklm.google.com/).
2. Create a new notebook for your class or subject.
3. Click **Add Source**:
   - **Fastest (Recommended):** Drag and drop `<name>_transcript.md`. NotebookLM parses the timestamped lecture structure and can immediately generate study guides, lesson summaries, and answer questions grounded in the lecture.
   - **Audio Overview:** Drag and drop `<name>_clean.mp3` to generate an AI podcast / conversational overview of the class.

---

## License

MIT License. See [LICENSE](LICENSE) for details.
