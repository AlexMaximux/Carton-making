# Modular Slideshow Video Generator & Whisper Transcriber

A flexible, reusable Python CLI & REST API application that converts a folder of numerically-ordered images and a timestamped transcript file (or automatically transcribed audio via OpenAI Whisper) into a synchronized video slideshow using FFmpeg.

## Features
- **FastAPI Asynchronous REST API**: Polling-based background job architecture (`api.py`) exposing speech-to-text transcription, video generation, and file downloads.
- **Standalone Transcribe-Only Mode**: Run speech-to-text on any audio file via CLI or HTTP API without requiring images or video rendering.
- **Dynamic Image Sorting**: Works with any count and extension (`.jpg`, `.jpeg`, `.png`), automatically sorted numerically by numbers embedded in filenames (`1.jpg`, `2.png`, `10.jpeg`).
- **Flexible Transcript Regex Parsing**: Supports bracketed timestamps like `[m:ss]`, `[mm:ss]`, `[hh:mm:ss]`, and fractional seconds `[m:ss.ms]`.
- **Automatic Speech-to-Text Transcription**: Powered by OpenAI Whisper (`--transcribe-audio`). Automatically extracts `[mm:ss]` sentence segments and word-level JSON timestamps for future highlighted subtitles.
- **FFmpeg Concat Demuxer Engine**: High performance, pillarbox/letterbox resolution scaling (`scale` + `pad`), even dimension enforcement for `libx264`, and pixel aspect ratio normalization (`setsar=1`).
- **Audio Multiplexing & Video Freeze Frame**: Merges an audio track (`--audio`) using video stream copying (`-c:v copy`). If audio is longer than raw video, automatically freezes the final video frame (`tpad`) to match audio length.

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

## REST API Usage (FastAPI)

### Start the Server

Run Uvicorn server on port 8000:

```bash
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

Interactive Swagger UI documentation is automatically available at:
`http://localhost:8000/docs`

---

### API Endpoints & `curl` Examples

#### 1. Health Check (`GET /health`)

```bash
curl http://localhost:8000/health
```

#### 2. Submit Audio Transcription Job (`POST /transcribe`)

```bash
curl -X POST "http://localhost:8000/transcribe" \
  -F "audio_file=@/path/to/voiceover.mp3" \
  -F "whisper_model=small"
```
*Response*: `{"job_id": "3b29c991-...", "status": "queued"}`

#### 3. Poll Transcription Job Status (`GET /transcribe/{job_id}`)

```bash
curl http://localhost:8000/transcribe/3b29c991-...
```
*Response when completed*:
```json
{
  "job_id": "3b29c991-...",
  "status": "completed",
  "result_urls": {
    "transcript": "/download/3b29c991-.../transcript",
    "words": "/download/3b29c991-.../words"
  }
}
```

#### 4. Submit Video Generation Job (`POST /generate-video`)

**Using individual image files:**

```bash
curl -X POST "http://localhost:8000/generate-video" \
  -F "images_mode=files" \
  -F "images=@/path/to/1.jpg" \
  -F "images=@/path/to/2.jpg" \
  -F "audio_file=@/path/to/voiceover.mp3" \
  -F "whisper_model=small" \
  -F "resolution=1920x1080" \
  -F "fps=30"
```

**Using ZIP archive of images:**

```bash
curl -X POST "http://localhost:8000/generate-video" \
  -F "images_mode=zip" \
  -F "zip_file=@/path/to/images.zip" \
  -F "transcript_file=@/path/to/transcript.txt" \
  -F "audio_file=@/path/to/voiceover.mp3"
```
*Response*: `{"job_id": "8f3ccb55-...", "status": "queued"}`

#### 5. Poll Video Generation Job Status (`GET /generate-video/{job_id}`)

```bash
curl http://localhost:8000/generate-video/8f3ccb55-...
```

#### 6. Download Output File (`GET /download/{job_id}/{file_type}`)

```bash
# Download transcript
curl -O http://localhost:8000/download/3b29c991-.../transcript

# Download video MP4
curl -o final.mp4 http://localhost:8000/download/8f3ccb55-.../video
```

---

## CLI Usage Examples

### Standalone Transcribe-Only Mode

```bash
python main.py --transcribe-audio ./v/voiceover01.mp3
```

### Fully Automated Mode (Images + Audio -> Video)

```bash
python main.py --images-dir ./v/ --transcribe-audio ./v/voiceover01.mp3 --audio ./v/voiceover01.mp3 --output final.mp4
```

### Manual Transcript Mode

```bash
python main.py --images-dir ./images --transcript ./transcript.txt --audio ./voiceover.mp3 --output output.mp4
```

---

## Project Structure & Architecture

```
.
├── main.py                       # CLI entry point & branching orchestrator
├── api.py                        # FastAPI REST API layer & Background Job Manager
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
│   ├── test_api.py
│   ├── test_transcript_parser.py
│   ├── test_timing_calculator.py
│   ├── test_ffmpeg_engine.py
│   ├── test_audio_muxer.py
│   ├── test_transcriber.py
│   └── test_main.py
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
