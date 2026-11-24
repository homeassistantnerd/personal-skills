#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OBS Recording Audio Extractor & Vietnamese Transcriber for NotebookLM.
Extracts clean, normalized speech audio (<200MB) using FFmpeg and transcribes
via Groq Cloud API (whisper-large-v3) with automatic chunking and timestamp alignment.
"""

import os
import sys
import argparse
import subprocess
import tempfile
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Ensure UTF-8 output on Windows terminals
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass


def check_prerequisites(api_key_required=True):
    """Verify ffmpeg is installed and API key is present if required."""
    # Check FFmpeg
    try:
        result = subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            raise FileNotFoundError()
    except FileNotFoundError:
        print("[ERROR] FFmpeg is not installed or not found in system PATH.", file=sys.stderr)
        print("Please install FFmpeg on Windows using one of the following:", file=sys.stderr)
        print("  - Winget: winget install Gyan.FFmpeg", file=sys.stderr)
        print("  - Chocolatey: choco install ffmpeg", file=sys.stderr)
        print("  - Or download from https://www.gyan.dev/ffmpeg/builds/ and add to PATH.", file=sys.stderr)
        sys.exit(1)

    # Check Groq SDK
    if api_key_required:
        try:
            import groq  # noqa: F401
        except ImportError:
            print("[ERROR] 'groq' package is not installed.", file=sys.stderr)
            print("Please run: pip install -r requirements.txt", file=sys.stderr)
            sys.exit(1)


def get_media_duration(file_path):
    """Retrieve media duration in seconds using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(file_path)
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return float(res.stdout.strip())
    except Exception:
        return 0.0


def format_timestamp(seconds):
    """Format seconds into HH:MM:SS string."""
    seconds = max(0, int(seconds))
    hrs = seconds // 3600
    mins = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hrs:02d}:{mins:02d}:{secs:02d}"


def extract_clean_audio(video_path, output_audio_path, bitrate="64k"):
    """
    Extract speech-optimized mono MP3 using FFmpeg filters:
    - Downmix to mono (-ac 1)
    - 80Hz highpass filter to eliminate desk bumps & rumble
    - 8000Hz lowpass filter to remove high-frequency hiss
    - dynaudnorm to dynamically balance instructor & student speech volumes
    - 16kHz sample rate optimal for speech recognition & NotebookLM
    - 64kbps MP3 guarantees 3 hours stays ~82MB (well under 200MB limit)
    """
    video_path = Path(video_path)
    output_audio_path = Path(output_audio_path)
    output_audio_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"\n[1/4] Extracting & cleaning audio from: {video_path.name}")
    print(f"      Target: {output_audio_path.name} (Mono @ {bitrate}, 16kHz, dynaudnorm)")

    start_time = time.time()

    # Audio filter chain for speech enhancement
    audio_filter = "highpass=f=80,lowpass=f=8000,dynaudnorm=p=0.9:m=100.0:s=12:b=1"

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vn",
        "-af", audio_filter,
        "-ar", "16000",
        "-ac", "1",
        "-c:a", "libmp3lame",
        "-b:a", str(bitrate),
        str(output_audio_path)
    ]

    process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if process.returncode != 0:
        print(f"[ERROR] FFmpeg audio extraction failed:\n{process.stderr}", file=sys.stderr)
        sys.exit(1)

    elapsed = time.time() - start_time
    file_size_mb = output_audio_path.stat().st_size / (1024 * 1024)
    duration_sec = get_media_duration(output_audio_path)

    print(f"      [DONE] Extracted in {elapsed:.1f}s")
    print(f"      Duration : {format_timestamp(duration_sec)} ({duration_sec:.1f}s)")
    print(f"      File size: {file_size_mb:.2f} MB (NotebookLM limit: 200 MB)")

    if file_size_mb > 200.0:
        print(f"[WARNING] File size ({file_size_mb:.2f} MB) exceeds NotebookLM 200 MB limit!", file=sys.stderr)
    else:
        print(f"      [OK] Strictly within 200MB limit ({(file_size_mb/200)*100:.1f}% of quota)")

    return output_audio_path, duration_sec, file_size_mb


def chunk_audio(audio_path, temp_dir, chunk_duration_sec=900):
    """
    Split audio into segments <= 20MB for Groq API upload (Groq limit is 25MB).
    Uses lossless stream-copy for near-instant splitting.
    Returns list of tuples: (chunk_file_path, start_offset_seconds, chunk_duration)
    """
    audio_path = Path(audio_path)
    file_size_mb = audio_path.stat().st_size / (1024 * 1024)

    # If already <= 20 MB, transcribe directly without chunking
    if file_size_mb <= 20.0:
        duration = get_media_duration(audio_path)
        return [(audio_path, 0.0, duration)]

    print(f"\n[2/4] Audio is {file_size_mb:.2f} MB (> 20 MB Groq payload limit).")
    print(f"      Splitting into ~{chunk_duration_sec//60}-minute chunks via FFmpeg stream-copy...")

    chunk_pattern = os.path.join(temp_dir, "chunk_%03d.mp3")
    cmd = [
        "ffmpeg", "-y",
        "-i", str(audio_path),
        "-f", "segment",
        "-segment_time", str(chunk_duration_sec),
        "-c", "copy",
        chunk_pattern
    ]

    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        print(f"[ERROR] Failed to chunk audio:\n{res.stderr}", file=sys.stderr)
        sys.exit(1)

    chunk_files = sorted(Path(temp_dir).glob("chunk_*.mp3"))
    if not chunk_files:
        print("[ERROR] No chunks were produced.", file=sys.stderr)
        sys.exit(1)

    chunks_with_offsets = []
    current_offset = 0.0
    for idx, cf in enumerate(chunk_files):
        dur = get_media_duration(cf)
        chunks_with_offsets.append((cf, current_offset, dur))
        print(f"      Chunk {idx+1:02d}/{len(chunk_files):02d}: {cf.name} | Offset: {format_timestamp(current_offset)} | Length: {dur:.1f}s | {cf.stat().st_size/(1024*1024):.2f} MB")
        current_offset += dur

    return chunks_with_offsets


def transcribe_single_chunk(groq_client, chunk_info, max_retries=3):
    """Transcribe a single audio chunk with Groq whisper-large-v3."""
    chunk_path, offset_sec, chunk_dur = chunk_info

    for attempt in range(1, max_retries + 1):
        try:
            with open(chunk_path, "rb") as audio_file:
                transcription = groq_client.audio.transcriptions.create(
                    file=(chunk_path.name, audio_file.read()),
                    model="whisper-large-v3",
                    language="vi",
                    response_format="verbose_json",
                    temperature=0.0
                )

            # transcription is a VerboseTranscription object or dict with 'segments'
            segments = []
            raw_segments = getattr(transcription, "segments", None)
            if raw_segments is None and isinstance(transcription, dict):
                raw_segments = transcription.get("segments", [])

            if raw_segments:
                for seg in raw_segments:
                    # seg can be dict or object
                    s_start = getattr(seg, "start", None) if hasattr(seg, "start") else seg.get("start", 0.0)
                    s_end = getattr(seg, "end", None) if hasattr(seg, "end") else seg.get("end", 0.0)
                    s_text = getattr(seg, "text", "") if hasattr(seg, "text") else seg.get("text", "")

                    segments.append({
                        "start": offset_sec + float(s_start),
                        "end": offset_sec + float(s_end),
                        "text": str(s_text).strip()
                    })
            else:
                # Fallback to plain text if segments weren't returned
                full_text = getattr(transcription, "text", "") if hasattr(transcription, "text") else transcription.get("text", "")
                if full_text:
                    segments.append({
                        "start": offset_sec,
                        "end": offset_sec + chunk_dur,
                        "text": full_text.strip()
                    })

            return segments

        except Exception as e:
            if attempt < max_retries:
                wait_sec = attempt * 3
                print(f"      [RETRY] Error on {chunk_path.name} ({e}). Retrying in {wait_sec}s...")
                time.sleep(wait_sec)
            else:
                print(f"[ERROR] Failed transcribing {chunk_path.name} after {max_retries} attempts: {e}", file=sys.stderr)
                raise


def transcribe_audio_groq(chunks_info, api_key):
    """Concurrently transcribe chunks via Groq Whisper API and assemble unified timeline."""
    from groq import Groq
    client = Groq(api_key=api_key)

    total_chunks = len(chunks_info)
    print(f"\n[3/4] Transcribing {total_chunks} chunk(s) with Groq Whisper Large v3 (Vietnamese)...")
    start_time = time.time()

    all_segments = []
    # Concurrency capped at 3 workers to respect Groq free-tier rate limits comfortably
    max_workers = min(3, total_chunks)

    indexed_chunks = list(enumerate(chunks_info))
    results = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {
            executor.submit(transcribe_single_chunk, client, chunk_info): idx
            for idx, chunk_info in indexed_chunks
        }

        completed_count = 0
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            chunk_file = chunks_info[idx][0].name
            try:
                chunk_segments = future.result()
                results[idx] = chunk_segments
                completed_count += 1
                print(f"      Progress: {completed_count}/{total_chunks} chunks completed ({chunk_file})")
            except Exception as e:
                print(f"[ERROR] Chunk {chunk_file} failed: {e}", file=sys.stderr)
                raise

    # Stitch segments in chronological chunk order
    for idx in range(total_chunks):
        if idx in results:
            all_segments.extend(results[idx])

    elapsed = time.time() - start_time
    total_words = sum(len(seg["text"].split()) for seg in all_segments)
    print(f"      [DONE] Transcription completed in {elapsed:.1f}s")
    print(f"      Generated {len(all_segments)} dialogue segments ({total_words:,} Vietnamese words)")

    return all_segments


def format_notebooklm_markdown(segments, metadata, output_md_path, output_txt_path):
    """
    Format transcript for Google NotebookLM:
    - Group segments into clean, readable paragraphs with timestamp headers.
    - Output both a structured Markdown (.md) and plain text (.txt).
    """
    output_md_path = Path(output_md_path)
    output_txt_path = Path(output_txt_path)

    print(f"\n[4/4] Generating NotebookLM formatted documents...")

    # Group segments into blocks of ~2.5 minutes or on long pauses (> 3.0s)
    blocks = []
    current_block_segments = []
    current_block_start = 0.0

    for seg in segments:
        text = seg["text"].strip()
        if not text:
            continue

        if not current_block_segments:
            current_block_start = seg["start"]
            current_block_segments.append(seg)
        else:
            prev_end = current_block_segments[-1]["end"]
            duration_so_far = seg["end"] - current_block_start
            pause = seg["start"] - prev_end

            # Break block if block is > 150 seconds or pause > 3.0s
            if duration_so_far >= 150.0 or pause >= 3.5:
                blocks.append((current_block_start, prev_end, current_block_segments))
                current_block_start = seg["start"]
                current_block_segments = [seg]
            else:
                current_block_segments.append(seg)

    if current_block_segments:
        blocks.append((current_block_start, current_block_segments[-1]["end"], current_block_segments))

    # Calculate statistics
    total_words = sum(len(seg["text"].split()) for seg in segments)

    # 1. Build Markdown (.md)
    md_lines = [
        f"# Bản Ghi Bài Giảng: {metadata.get('title', 'Online Class')}",
        "",
        "## Thông Tin Tổng Quan",
        f"- **Tệp gốc:** `{metadata.get('source_file', 'unknown')}`",
        f"- **Thời lượng:** `{format_timestamp(metadata.get('duration_sec', 0))}`",
        f"- **Kích thước âm thanh:** `{metadata.get('file_size_mb', 0):.2f} MB` (Hợp lệ tải lên NotebookLM: < 200 MB)",
        f"- **Tổng số từ:** `{total_words:,} từ`",
        f"- **Mô hình nhận diện:** `Groq Whisper Large v3` (Ngôn ngữ: Tiếng Việt)",
        f"- **Ngày xử lý:** `{time.strftime('%Y-%m-%d %H:%M:%S')}`",
        "",
        "---",
        "",
        "## Nội Dung Bài Giảng (Theo Dòng Thời Gian)",
        ""
    ]

    txt_lines = [
        f"BẢN GHI BÀI GIẢNG: {metadata.get('title', 'Online Class')}",
        f"Thời lượng: {format_timestamp(metadata.get('duration_sec', 0))}",
        f"Ngày xử lý: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 60,
        ""
    ]

    for start_t, end_t, seg_list in blocks:
        time_header = f"[{format_timestamp(start_t)} - {format_timestamp(end_t)}]"
        block_text = " ".join(s["text"] for s in seg_list).strip()

        # Markdown block
        md_lines.append(f"### {time_header}")
        md_lines.append(f"{block_text}")
        md_lines.append("")

        # TXT block
        txt_lines.append(f"{time_header} {block_text}")

    # Write files
    output_md_path.write_text("\n".join(md_lines), encoding="utf-8")
    output_txt_path.write_text("\n".join(txt_lines), encoding="utf-8")

    print(f"      [OK] Saved Markdown transcript: {output_md_path}")
    print(f"      [OK] Saved Plain Text transcript: {output_txt_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Extract speech audio (<200MB) from OBS recordings and transcribe in Vietnamese for NotebookLM."
    )
    parser.add_argument("-i", "--input", required=True, help="Path to OBS video recording file (.mkv, .mp4, etc.)")
    parser.add_argument("-o", "--output-dir", default=None, help="Output directory (defaults to recording directory)")
    parser.add_argument("-k", "--api-key", default=None, help="Groq API key (or set GROQ_API_KEY environment variable)")
    parser.add_argument("-b", "--bitrate", default="64k", help="Audio bitrate for MP3 compression (default: 64k)")
    parser.add_argument("--chunk-minutes", type=int, default=15, help="Minutes per chunk for Groq API limit (default: 15)")
    parser.add_argument("--audio-only", action="store_true", help="Only extract and clean audio, skip transcription")
    parser.add_argument("--transcribe-only", action="store_true", help="Input is already an audio file, skip extraction")

    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    if not input_path.exists():
        print(f"[ERROR] Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    # Resolve output directory
    output_dir = Path(args.output_dir).resolve() if args.output_dir else input_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    base_name = input_path.stem

    # Resolve API Key
    api_key = args.api_key or os.environ.get("GROQ_API_KEY")
    if not api_key and not args.audio_only:
        # Check if .env exists in current directory or skill root directory
        try:
            from dotenv import load_dotenv
            # First check current working directory
            load_dotenv()
            # Also check skill directory ~/.claude/skills/obs-transcribe/.env
            skill_env = Path(__file__).resolve().parent.parent / ".env"
            if skill_env.exists():
                load_dotenv(skill_env)
            api_key = os.environ.get("GROQ_API_KEY")
        except Exception:
            pass

    if not args.audio_only and not api_key:
        print("[ERROR] Groq API Key is required for Vietnamese transcription.", file=sys.stderr)
        print("Please provide it via one of the following methods:", file=sys.stderr)
        print("  1. Set environment variable: set GROQ_API_KEY=gsk_...", file=sys.stderr)
        print("  2. Add GROQ_API_KEY=gsk_... to a .env file", file=sys.stderr)
        print("  3. Pass as argument: --api-key gsk_...", file=sys.stderr)
        print("\nYou can get a free Groq API key instantly at: https://console.groq.com/keys", file=sys.stderr)
        sys.exit(1)

    check_prerequisites(api_key_required=not args.audio_only)

    print("=" * 70)
    print(" OBS RECORDING PROCESSOR FOR NOTEBOOKLM (VIETNAMESE TRANSCRIPTION)")
    print("=" * 70)
    print(f" Input File : {input_path}")
    print(f" Output Dir : {output_dir}")

    clean_audio_path = output_dir / f"{base_name}_clean.mp3"
    output_md_path = output_dir / f"{base_name}_transcript.md"
    output_txt_path = output_dir / f"{base_name}_transcript.txt"

    # Step 1: Audio Extraction
    if args.transcribe_only:
        clean_audio_path = input_path
        duration_sec = get_media_duration(clean_audio_path)
        file_size_mb = clean_audio_path.stat().st_size / (1024 * 1024)
        print(f"\n[INFO] Skipping extraction (--transcribe-only). Using: {clean_audio_path.name}")
    else:
        clean_audio_path, duration_sec, file_size_mb = extract_clean_audio(
            input_path, clean_audio_path, bitrate=args.bitrate
        )

    if args.audio_only:
        print("\n[COMPLETE] Audio extraction finished (--audio-only specified).")
        print(f"Clean audio ready for NotebookLM upload: {clean_audio_path}")
        return

    # Step 2 & 3: Chunking & Transcription
    with tempfile.TemporaryDirectory() as temp_dir:
        chunks_info = chunk_audio(
            clean_audio_path,
            temp_dir,
            chunk_duration_sec=args.chunk_minutes * 60
        )

        segments = transcribe_audio_groq(chunks_info, api_key)

    # Step 4: Formatting
    metadata = {
        "title": base_name,
        "source_file": input_path.name,
        "duration_sec": duration_sec,
        "file_size_mb": file_size_mb
    }

    format_notebooklm_markdown(segments, metadata, output_md_path, output_txt_path)

    print("\n" + "=" * 70)
    print(" ALL TASKS COMPLETED SUCCESSFULLY!")
    print("=" * 70)
    print("Deliverables ready for Google NotebookLM:")
    print(f"  1. Audio file       : {clean_audio_path} ({file_size_mb:.2f} MB)")
    print(f"  2. Markdown document: {output_md_path}")
    print(f"  3. Plain text       : {output_txt_path}")
    print("\nTip for NotebookLM:")
    print("  - Drag and drop either the .mp3 (Audio Source) or .md (Document Source)")
    print("    directly into https://notebooklm.google.com/ to start generating summaries,")
    print("    study guides, and asking questions!")
    print("=" * 70)


if __name__ == "__main__":
    main()
