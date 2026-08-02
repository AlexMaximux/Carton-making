# Design Specification: OpenAI Whisper Automatic Transcription

## Overview
Adds automatic speech-to-text transcription capability using OpenAI Whisper (`openai-whisper`). Users can specify `--transcribe-audio` to automatically transcribe speech from an audio file, format it into a bracketed `[mm:ss]` transcript file, and extract word-level timestamps (`JSON`) for future word-highlighted subtitles.

## Key Rules & Architectural Principles
1. **Fully Additive**: Zero modification to `transcript_parser.py`, `timing_calculator.py`, `ffmpeg_engine.py`, or `audio_muxer.py`.
2. **Mutual Exclusion**: `--transcribe-audio` and `--transcript` are mutually exclusive. Specifying both raises a clear CLI error.
3. **Format Compatibility**: Output of `format_segments_as_transcript(segments)` generates bracketed timestamp text `[mm:ss] Text` matching `transcript_parser.py` requirements.
4. **Default Model (`small`) & Word-Level Accuracy**: Default model size set to `small` for superior word-level timestamp accuracy compared to `tiny`/`base`.
5. **CPU / Processing Time Status**: Displays clear status notification prior to transcription ("Transcribing audio using Whisper model 'small' (CPU mode, this may take a few moments)...").

---

## Architecture & Module Specification

```
modules/
├── transcriber.py        # [NEW] Whisper loading, audio transcription & transcript formatting
├── pipeline.py           # Updated CLI orchestrator integration
├── audio_muxer.py        # Untouched
├── ffmpeg_engine.py      # Untouched
├── timing_calculator.py  # Untouched
└── transcript_parser.py  # Untouched
```

### `modules/transcriber.py`
- `check_whisper_installed() -> None`: Checks if `whisper` module is importable. If missing, raises `ImportError("openai-whisper is not installed. Please install it using: pip install openai-whisper")`.
- `format_timestamp(seconds: float) -> str`: Formats floating point seconds into `[mm:ss]` bracket string (e.g., `5.2` -> `[00:05]`).
- `format_segments_as_transcript(segments: list) -> str`: Iterates over Whisper segment dictionaries `{"start": float, "text": str}` and builds the line-by-line formatted transcript string.
- `transcribe_audio(audio_path: Union[str, Path], model_size: str = "small") -> dict`:
  - Calls `whisper.load_model(model_size)`.
  - Executes `model.transcribe(str(audio_path), word_timestamps=True)`.
  - Extracts `segments` (`[{"start": float, "end": float, "text": str}, ...]`) and `words` (`[{"word": str, "start": float, "end": float}, ...]`).
  - Returns `{"segments": segments, "words": words, "text": full_text}`.

### `main.py` CLI Updates
- New CLI parameters:
  - `--transcribe-audio` (type: `str`, optional): Audio file to transcribe automatically.
  - `--whisper-model` (type: `str`, default: `"small"`): Model size (`tiny`, `base`, `small`, `medium`, `large`).
  - `--save-transcript` (type: `str`, optional): Target path for formatted text transcript (default: `output_transcript.txt`).
  - `--save-word-timestamps` (type: `str`, optional): Target path for word timestamps JSON file.
- Mutually Exclusive Validation: If both `--transcript` and `--transcribe-audio` are specified, raises `ValueError("Cannot specify both --transcript and --transcribe-audio. Please select one.")`.

---

## Verification Plan

### Unit Tests (`tests/test_transcriber.py`)
1. `test_format_timestamp`: Test formatting seconds to `[mm:ss]` (e.g. `0.0` -> `[00:00]`, `65.5` -> `[01:05]`).
2. `test_format_segments_as_transcript`: Test converting Whisper segments list into valid transcript text compatible with `transcript_parser`.
3. `test_word_timestamps_extraction`: Test extracting word list from mock Whisper segment structure.

### Manual Verification
1. Run CLI command:
   `python main.py --images-dir ./v/ --transcribe-audio ./v/voiceover01.mp3 --audio ./v/voiceover01.mp3 --output final.mp4`
2. Verify generated transcript text file (`output_transcript.txt`) and word timestamps JSON.
