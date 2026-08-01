# Modular Slideshow Video Generator

A flexible, reusable Python CLI tool that converts a folder of numerically-ordered images and a timestamped transcript file (or automatically transcribed audio via OpenAI Whisper) into a synchronized video slideshow using FFmpeg.

## Features
- **Dynamic Image Sorting**: Works with any count and extension (`.jpg`, `.jpeg`, `.png`), automatically sorted numerically by numbers embedded in filenames (`1.jpg`, `2.png`, `10.jpeg`).
- **Flexible Transcript Regex Parsing**: Supports bracketed timestamps like `[m:ss]`, `[mm:ss]`, `[hh:mm:ss]`, and fractional seconds `[m:ss.ms]`.
- **Automatic Speech-to-Text Transcription**: Powered by OpenAI Whisper (`--transcribe-audio`). Automatically extracts `[mm:ss]` sentence segments and word-level JSON timestamps for future highlighted subtitles.
- **FFmpeg Concat Demuxer Engine**: High performance, pillarbox/letterbox resolution scaling (`scale` + `pad`), even dimension enforcement for `libx264`, and pixel aspect ratio normalization (`setsar=1`).
- **Audio Multiplexing & Video Freeze Frame**: Merges an audio track (`--audio`) using video stream copying (`-c:v copy`). If audio is longer than raw video, automatically freezes the final video frame (`tpad`) to match audio length.
- **Mismatch Handling**: Configurable interactive terminal prompt or CLI flags (`--on-mismatch=ask|truncate|error`) when image count $M \neq N$ timestamp count.

---

## Prerequisites
1. **Python 3.8+**
2. **FFmpeg** & **ffprobe** installed and accessible in system PATH.
   - macOS: `brew install ffmpeg`
   - Ubuntu/Debian: `sudo apt update && sudo apt install ffmpeg`
3. *(Optional)* **OpenAI Whisper** for automatic transcription:
   ```bash
   pip install openai-whisper
   ```

---

## Installation

1. Clone or download the repository.
2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

---

## Usage

### 1. Fully Automated (Images + Audio -> Video)
No manual transcript typing required! Whisper transcribes the audio and builds the video in one command:

```bash
python main.py --images-dir ./v/ --transcribe-audio ./v/voiceover01.mp3 --audio ./v/voiceover01.mp3 --output final.mp4
```

> **Model Precision Note**: The default Whisper model size is `--whisper-model small`. Using `small` or `medium` provides superior word-level timestamp accuracy (`output_words.json`), which is recommended for word-highlighted subtitle generators.

### 2. Manual Transcript Mode
Provide your own timestamped text file:

```bash
python main.py --images-dir ./images --transcript ./transcript.txt --audio ./voiceover.mp3 --output output.mp4
```

### 3. Audio Offset (Delay or Advance)

```bash
# Delay audio start by 2.5 seconds relative to video
python main.py -i ./images -t ./transcript.txt -a ./voiceover.mp3 --audio-offset 2.5 -o output.mp4

# Advance/Trim audio start by 1.5 seconds
python main.py -i ./images -t ./transcript.txt -a ./voiceover.mp3 --audio-offset -1.5 -o output.mp4
```

---

## CLI Arguments Reference

| Argument | Short | Description | Default |
| :--- | :--- | :--- | :--- |
| `--images-dir` | `-i` | **Required**. Path to folder containing images. | - |
| `--transcript` | `-t` | Path to manual transcript file (mutually exclusive with `--transcribe-audio`). | `None` |
| `--transcribe-audio` | - | Path to audio file to transcribe automatically via Whisper. | `None` |
| `--whisper-model` | - | Whisper model size (`tiny`, `base`, `small`, `medium`, `large`). | `small` |
| `--save-transcript` | - | Path to save generated text transcript file. | `output_transcript.txt` |
| `--save-word-timestamps` | - | Path to save word-level timestamps JSON file. | `output_words.json` |
| `--audio` | `-a` | Optional path to audio file to multiplex into final video. | `None` (Silent) |
| `--audio-offset` | - | Audio start delay ($>0$) or trim ($<0$) in seconds. | `0.0` |
| `--keep-temp` | - | Keep intermediate silent video file when `--audio` is set. | `False` |
| `--output` | `-o` | Output video filepath. | `output.mp4` |
| `--total-duration`| `-d` | Optional total video duration in seconds (for last slide). | Calculated |
| `--resolution` | `-r` | Output video resolution `WxH` (must be even numbers). | `1920x1080` |
| `--fps` | - | Output video framerate. | `30` |
| `--on-mismatch` | - | Handling mode when timestamp count $\neq$ image count (`ask`, `truncate`, `error`). | `ask` |

---

## Example Manual Transcript File (`transcript.txt`)

```text
[0:00] Welcome to this automated video presentation.
[0:04.5] In this section, we discuss the core architecture and modules.
[0:12.0] Next, we explore the FFmpeg concat demuxer rendering pipeline.
[01:05.5] Finally, here are the conclusions and future extension hooks.
```

---

## Project Structure & Architecture

```
.
├── main.py                       # CLI entry point (argparse & rich UI/logging)
├── modules/
│   ├── __init__.py
│   ├── transcript_parser.py      # Extract timestamps from text files
│   ├── timing_calculator.py      # Map timestamps to images & compute durations
│   ├── ffmpeg_engine.py          # FFmpeg check & video rendering via concat demuxer
│   ├── audio_muxer.py            # Audio probing, duration check & stream-copy muxing
│   ├── transcriber.py            # Whisper speech-to-text & word-level JSON extraction
│   └── pipeline.py               # Pipeline orchestrator with extensibility hooks
├── tests/
│   ├── __init__.py
│   ├── test_transcript_parser.py
│   ├── test_timing_calculator.py
│   ├── test_ffmpeg_engine.py
│   ├── test_audio_muxer.py
│   └── test_transcriber.py
├── docs/
│   └── superpowers/specs/        # Design specification documentation
├── requirements.txt              # Dependencies
└── README.md                     # Documentation
```

---

## Running Tests

Execute all unit tests with `pytest`:

```bash
pytest
```
