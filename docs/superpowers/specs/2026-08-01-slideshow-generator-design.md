# Design Specification: Modular Slideshow Video Generator

## Overview
A reusable Python CLI application that reads a folder of numerically-ordered images (e.g. `1.jpg`, `2.png`, ...) and a timestamped transcript file (`[m:ss]`, `[mm:ss]`, `[hh:mm:ss]`), calculates the timing for each image based on timestamp intervals, and renders a slideshow video using FFmpeg.

## Core Features & Requirements
1. **Dynamic Image Handling**: Sorts images by numerical value in filename regardless of prefix/padding or extension (`jpg`, `jpeg`, `png`).
2. **Flexible Transcript Parser**: Uses regular expressions to parse various timestamp formats (`[m:ss]`, `[mm:ss]`, `[hh:mm:ss]`, `[mm:ss.ms]`).
3. **Pure Timing Calculator**: Independent, unit-tested module that maps $N$ timestamps to $M$ images and computes exact segment durations.
4. **Mismatch Handling ($N \neq M$)**: Console warnings and configurable actions (`ask`, `truncate`, `error`).
5. **FFmpeg Engine**: Concat demuxer strategy with resolution scaling/padding (pillarboxing/letterboxing), even dimension enforcement, SAR setting (`setsar=1`), and standard MP4 (H.264/AAC ready) export.
6. **Pipeline & Hook Architecture**: Extensible hooks for pre-processing images, custom render filters, and future audio multiplexing.

---

## Architecture & File Structure

```
.
├── main.py                       # CLI entry point (argparse & rich UI/logging)
├── modules/
│   ├── __init__.py
│   ├── transcript_parser.py      # Extract timestamps from text files
│   ├── timing_calculator.py      # Map timestamps to images & compute durations
│   ├── ffmpeg_engine.py          # FFmpeg check & video rendering via concat demuxer
│   └── pipeline.py               # Pipeline orchestrator with extensibility hooks
├── tests/
│   ├── __init__.py
│   ├── test_transcript_parser.py
│   └── test_timing_calculator.py
├── requirements.txt              # Dependencies (rich, pytest)
└── README.md                     # Usage guide and CLI documentation
```

---

## Detailed Component Specifications

### 1. `transcript_parser.py`
- **Function**: `parse_transcript(file_path_or_content: str) -> list[float]`
- **Regex Pattern**: `r'\[(?:(\d{1,2}):)?(\d{1,2}):(\d{2})(?:\.(\d+))?\]|\[(\d{1,2}):(\d{2})(?:\.(\d+))?\]'`
- **Behavior**:
  - Scans line by line or full text for all bracketed timestamps.
  - Converts matched time components (hours, minutes, seconds, milliseconds) into floating point total seconds.
  - Returns a sorted list of timestamps in seconds.
  - Raises `ValueError` with clear error message if no timestamps are matched.

### 2. `timing_calculator.py`
- **Data Class**: `ImageSegment(image_path: str, start_time: float, duration: float)`
- **Function**: `calculate_timings(timestamps: list[float], image_paths: list[str], total_duration: float = None, fallback_duration: float = None) -> list[ImageSegment]`
- **Image Sorting**: Extracts leading or embedded digits using `re.search(r'\d+', filename)` to sort numerically (e.g. `1.jpg` < `2.png` < `10.jpg`).
- **Mismatch Resolution**:
  - Calculates $N = len(timestamps)$ and $M = len(image_paths)$.
  - If $N \neq M$, raises `MismatchWarning` exception or handles array truncation based on parameter `on_mismatch` (`ask`, `truncate`, `error`).
- **Segment Durations**:
  - Segment $i$ duration ($0 \le i < K-1$ where $K = min(N, M)$): $timestamp_{i+1} - timestamp_i$.
  - Segment $K-1$ (last image):
    - If `total_duration` is provided and $> timestamp_{K-1}$: $duration = total\_duration - timestamp_{K-1}$.
    - Else if `fallback_duration` is provided: $duration = fallback\_duration$.
    - Else: $duration = \text{previous segment duration}$ (or 3.0s if only 1 segment).

### 3. `ffmpeg_engine.py`
- **FFmpeg Check**: `check_ffmpeg_installed()` executes `ffmpeg -version`. If missing, raises an `EnvironmentError` with installation instructions for macOS (`brew install ffmpeg`) and Ubuntu/Debian (`sudo apt-get install ffmpeg`).
- **Resolution & H.264 Validation**: Ensures width and height are even integers (divisible by 2) to prevent `libx264` encoder failures. Raises `ValueError` if odd resolution is passed.
- **Concat Spec Generation**: Writes temporary text file:
  ```txt
  file '/absolute/path/to/1.jpg'
  duration 4.5
  file '/absolute/path/to/2.jpg'
  duration 3.2
  file '/absolute/path/to/2.jpg'
  ```
  *(Note: Concat demuxer requires repeating the last file entry without duration).*
- **Rendering Command**:
  ```bash
  ffmpeg -y -f concat -safe 0 -i concat_list.txt \
    -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps=30,format=yuv420p" \
    -c:v libx264 -preset medium -crf 23 output.mp4
  ```

### 4. `pipeline.py` & Extensibility Hooks
- `SlideshowPipeline`:
  - `add_pre_process_hook(callable)`: Modifies or applies filters to image paths before rendering.
  - `add_render_filter_hook(callable)`: Allows injecting FFmpeg video filters into the `-vf` chain.
  - `add_audio_hook(callable)`: Post-processing step to attach audio file to the final output video.
  - `execute(...)`: Executes the full workflow sequentially.

### 5. `main.py` CLI & User Experience
- **Arguments**:
  - `--images-dir` / `-i` (required): Folder containing images.
  - `--transcript` / `-t` (required): Path to text transcript file.
  - `--output` / `-o` (default: `output.mp4`): Output video filepath.
  - `--total-duration` / `-d` (optional): Total duration for video.
  - `--resolution` / `-r` (default: `1920x1080`): Output resolution widthxheight (must be even dimensions).
  - `--fps` (default: `30`): Output framerate.
  - `--on-mismatch` (choices: `ask`, `truncate`, `error`, default: `ask`): How to handle $N \neq M$.
- **Rich Output**:
  - Formatted table logging each image index, path, start time, end time, and duration.
  - Progress bar or status spinner during FFmpeg execution.

---

## Verification Plan

### Automated Tests (`pytest`)
1. **Unit tests for `transcript_parser`**: Test various bracket formats (`[0:05]`, `[01:23]`, `[01:02:03]`, `[0:15.5]`, mixed content text lines).
2. **Unit tests for `timing_calculator`**:
   - Sorting image filenames (`1.jpg`, `02.png`, `10.jpeg`).
   - Computing duration intervals correctly.
   - Fallback duration calculations for last image.
   - Array truncation when $N \neq M$.

### Manual & Automated Integration Verification
1. Run CLI with sample images and transcript file.
2. Automated duration check with `ffprobe`:
   ```bash
   ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 output.mp4
   ```
   Compare `ffprobe` output duration against expected total duration from `timing_calculator` (tolerance $\pm 0.2\text{s}$).
