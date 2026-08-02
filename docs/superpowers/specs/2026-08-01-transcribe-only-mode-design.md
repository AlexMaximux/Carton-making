# Design Specification: Standalone Transcribe-Only Mode

## Overview
Adds a standalone "Transcribe-Only" execution mode to `main.py`. Allows users to transcribe any audio file and extract sentence/word timestamps without specifying an image directory (`--images-dir`), output video (`--output`), or rendering any video files.

## CLI Modes & Branching Rules

| Mode | Command Example | Actions Taken |
| :--- | :--- | :--- |
| **1. Standalone Transcribe-Only** | `python main.py --transcribe-audio ./v/audio.mp3` | Runs Whisper transcription $\rightarrow$ Saves transcript & word JSON in audio file's folder $\rightarrow$ Prints report $\rightarrow$ Exits (0) **without** video rendering or pipeline invocation. |
| **2. Full Auto (Transcribe + Video)** | `python main.py -i ./v -a ./v/audio.mp3 --transcribe-audio ./v/audio.mp3` | Runs Whisper transcription $\rightarrow$ Saves files $\rightarrow$ Runs `SlideshowPipeline.run()` $\rightarrow$ Renders video with audio. |
| **3. Manual Transcript Video** | `python main.py -i ./v -t ./transcript.txt -a ./audio.mp3` | Uses manual transcript file $\rightarrow$ Runs `SlideshowPipeline.run()` $\rightarrow$ Renders video with audio. |

---

## Technical Specifications & Default Paths

### 1. `main.py` CLI Argument Changes
- `--images-dir` (`-i`): Set `required=False` (default `None`).
- `--transcript` (`-t`): Set `required=False` (default `None`).
- `--transcribe-audio`: Set `required=False` (default `None`).

### 2. Default Output Paths for Transcription
When `--transcribe-audio` is supplied:
- Audio Directory: `audio_dir = Path(args.transcribe_audio).resolve().parent`
- Default Transcript Path (if `--save-transcript` not set): `audio_dir / "output_transcript.txt"`
- Default Word Timestamps JSON Path (if `--save-word-timestamps` not set): `audio_dir / "output_words.json"`

### 3. Branching Validation Rules in `main.py`
```python
if args.transcribe_audio and args.transcript:
    # Error: Mutually exclusive
elif args.transcribe_audio and not args.images_dir:
    # Mode 1: Transcribe-Only Mode (Execute transcription, save outputs, exit 0)
elif args.transcribe_audio and args.images_dir:
    # Mode 2: Full Auto Transcribe + Video Generation
elif not args.transcribe_audio and args.images_dir:
    if not args.transcript:
        # Error: Missing --transcript
    # Mode 3: Manual Transcript Video Generation
else:
    # Error: Neither --transcribe-audio nor --images-dir provided
```

---

## Verification Plan

### Unit Tests (`tests/test_main.py`)
- Mock `transcribe_audio`, `format_segments_as_transcript`, `save_word_timestamps_json`, and `SlideshowPipeline.run`.
- Execute `main.py` with only `--transcribe-audio`.
- Assert `SlideshowPipeline.run()` is **never** called.
- Assert default saved files are placed in the audio file's directory.

### Manual Verification
1. Run `python main.py --transcribe-audio ./v/voiceover01.mp3`.
2. Verify `v/output_transcript.txt` and `v/output_words.json` are created.
3. Verify no `.mp4` file is generated and process exits cleanly.
