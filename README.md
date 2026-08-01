# Modular Slideshow Video Generator

A flexible, reusable Python CLI tool that converts a folder of numerically-ordered images and a timestamped transcript file into a synchronized video slideshow using FFmpeg, with optional background audio multiplexing.

## Features
- **Dynamic Image Sorting**: Works with any count and extension (`.jpg`, `.jpeg`, `.png`), automatically sorted numerically by numbers embedded in filenames (`1.jpg`, `2.png`, `10.jpeg`).
- **Flexible Transcript Regex Parsing**: Supports bracketed timestamps like `[m:ss]`, `[mm:ss]`, `[hh:mm:ss]`, and fractional seconds `[m:ss.ms]`.
- **FFmpeg Concat Demuxer Engine**: High performance, pillarbox/letterbox resolution scaling (`scale` + `pad`), even dimension enforcement for `libx264`, and pixel aspect ratio normalization (`setsar=1`).
- **Audio Multiplexing (Muxer)**: Seamlessly merges an audio track (`--audio`) using video stream copying (`-c:v copy`), audio delay/trimming offsets (`--audio-offset`), duration mismatch reports, and `-shortest` stream sync.
- **Mismatch Handling**: Configurable interactive terminal prompt or CLI flags (`--on-mismatch=ask|truncate|error`) when image count $M \neq N$ timestamp count.
- **Pipeline & Hook Architecture**: Easily extensible for image filters/transforms, custom FFmpeg render filters, and audio track attachment.

---

## Prerequisites
1. **Python 3.8+**
2. **FFmpeg** & **ffprobe** installed and accessible in system PATH.
   - macOS: `brew install ffmpeg`
   - Ubuntu/Debian: `sudo apt update && sudo apt install ffmpeg`

---

## Installation

1. Clone or download the repository.
2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

---

## Usage

### Basic Silent Slideshow

```bash
python main.py --images-dir /path/to/images --transcript /path/to/transcript.txt --output output.mp4
```

### Slideshow with Background Audio Track

```bash
python main.py --images-dir /path/to/images --transcript /path/to/transcript.txt --audio /path/to/audio.mp3 --output output.mp4
```

### Slideshow with Audio Offset (Delay or Trim)

```bash
# Delay audio start by 2.5 seconds relative to video
python main.py -i ./images -t ./transcript.txt -a ./voiceover.mp3 --audio-offset 2.5 -o output.mp4

# Trim audio start by 1.5 seconds (advance audio)
python main.py -i ./images -t ./transcript.txt -a ./voiceover.mp3 --audio-offset -1.5 -o output.mp4
```

### CLI Arguments Reference

| Argument | Short | Description | Default |
| :--- | :--- | :--- | :--- |
| `--images-dir` | `-i` | **Required**. Path to folder containing images. | - |
| `--transcript` | `-t` | **Required**. Path to transcript text file. | - |
| `--audio` | `-a` | Optional path to audio file (`.mp3`, `.wav`, `.m4a`, etc.). | `None` (Silent) |
| `--audio-offset` | - | Audio start delay ($>0$) or trim ($<0$) in seconds. | `0.0` |
| `--keep-temp` | - | Keep intermediate silent video file when `--audio` is set. | `False` |
| `--output` | `-o` | Output video filepath. | `output.mp4` |
| `--total-duration`| `-d` | Optional total video duration in seconds (for last slide). | Calculated |
| `--resolution` | `-r` | Output video resolution `WxH` (must be even numbers). | `1920x1080` |
| `--fps` | - | Output video framerate. | `30` |
| `--on-mismatch` | - | Handling mode when timestamp count $\neq$ image count (`ask`, `truncate`, `error`). | `ask` |

---

## Example Transcript File (`transcript.txt`)

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
│   └── pipeline.py               # Pipeline orchestrator with extensibility hooks
├── tests/
│   ├── __init__.py
│   ├── test_transcript_parser.py
│   ├── test_timing_calculator.py
│   ├── test_ffmpeg_engine.py
│   └── test_audio_muxer.py
├── docs/
│   └── superpowers/specs/        # Design specification documentation
├── requirements.txt              # Dependencies (rich, pytest)
└── README.md                     # Documentation
```

---

## Running Tests

Execute all unit tests with `pytest`:

```bash
pytest
```
