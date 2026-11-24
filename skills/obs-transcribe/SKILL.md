---
name: obs-transcribe
description: Extract speech audio (<200MB) from large OBS online class recordings and transcribe in Vietnamese using Groq Whisper Large v3 for NotebookLM.
argument-hint: "<path-to-video-file> [--output-dir <path>] [--audio-only]"
user-invocable: true
---

# OBS Recording Transcriber & Audio Optimizer for NotebookLM

Extract audio from large OBS recordings (5GB+, 2–3 hours), filter and compress it to strictly under 200MB for Google NotebookLM, and produce an accurate Vietnamese transcription using Groq Cloud (`whisper-large-v3`).

## When to Use This Skill
- The user asks to process, extract audio, compress, or transcribe an OBS class recording, lecture, or meeting video.
- The user has large video files (5GB+, MKV, MP4, MOV) that exceed the NotebookLM 200MB file limit.
- The user wants a clean Vietnamese transcript with timestamps formatted for NotebookLM summarization and study guides.

## Script Location
Relative to this skill's directory:
- Core extraction and transcription engine: [`scripts/process_recording.py`](./scripts/process_recording.py)
- Dependencies: [`requirements.txt`](./requirements.txt)

## Execution Steps

When the user invokes `/obs-transcribe <arguments>` or provides a recording file:

### 1. Parse Arguments & Identify Input File
- Identify the video file path from `$ARGUMENTS` (or the user's message).
- If the path contains spaces, ensure it is properly quoted.
- If no file path is given, ask the user to provide the path to their OBS recording.

### 2. Check Prerequisites
- Ensure `ffmpeg` is available on the system PATH.
- Check if `groq` Python package is installed:
  ```bash
  python -c "import groq"
  ```
  If not installed, prompt or install using the `requirements.txt` in this skill's directory:
  ```bash
  pip install -r "<SKILL_DIR>/requirements.txt"
  ```
- Check for `GROQ_API_KEY`:
  - Check if `GROQ_API_KEY` is set in the environment or `.env`.
  - If missing, ask the user to provide their Groq API key (free from https://console.groq.com/keys).

### 3. Run the Processing Pipeline
Execute the Python script from this skill's directory:
```bash
python "<SKILL_DIR>/scripts/process_recording.py" -i "<PATH_TO_RECORDING>"
```

Optional flags:
- `-o "<OUTPUT_DIR>"`: Custom output folder (defaults to the video's directory).
- `-b "64k"`: Custom audio bitrate (64k mono guarantees a 3-hour class stays ~82MB, well under 200MB).
- `--audio-only`: Only extract the speech-optimized audio without running transcription.
- `--transcribe-only`: Skip extraction if the user already has a clean audio file.

### 4. Report Results to User
Present the generated files clearly:
1. **Clean Speech Audio (`<name>_clean.mp3`)**:
   - Volume-normalized with `dynaudnorm` to balance quiet questions and loud lecture audio.
   - Highpass (80Hz) and lowpass (8000Hz) filtered to eliminate AC drone, desk rumbles, and mic hiss.
   - Strictly < 200 MB (ready for NotebookLM audio upload).
2. **NotebookLM Markdown Transcript (`<name>_transcript.md`)**:
   - Organized into 2–3 minute timestamped sections (e.g., `### [00:15:00 - 00:18:30]`).
   - Clean Vietnamese text with proper accents and punctuation.
   - Metadata header with duration, file size, and word count.
3. **Plain Text Transcript (`<name>_transcript.txt`)**:
   - Unformatted backup for quick search and copy-pasting.

### 5. Guide User on Uploading to NotebookLM
Remind the user:
- Go to [Google NotebookLM](https://notebooklm.google.com/).
- Create or open a notebook for this class.
- Click **Add Source**:
  - **Option A (Fastest for Notes & Q&A)**: Upload `<name>_transcript.md` as a Markdown / Document source. NotebookLM can instantly summarize the entire class, create study guides, and generate FAQs.
  - **Option B (Audio Overview)**: Upload `<name>_clean.mp3` as an Audio source (now well within the 200MB limit).
