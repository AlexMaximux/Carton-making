# Design Specification: FastAPI REST API Layer

## Overview
Adds a standalone, asynchronous REST API layer (`api.py`) powered by FastAPI and Uvicorn. Exposes speech-to-text transcription, image sequence sorting, timing calculation, and FFmpeg video generation via polling-based Background Job endpoints without modifying any code in `modules/` or `main.py`.

## Core Features & Architecture

```
.
├── api.py                        # [NEW] FastAPI application, endpoints & JobStore
├── modules/                      # Existing business logic (UNTOUCHED)
│   ├── transcript_parser.py
│   ├── timing_calculator.py
│   ├── ffmpeg_engine.py
│   ├── audio_muxer.py
│   ├── transcriber.py
│   └── pipeline.py
├── storage/                      # [NEW] Auto-created temporary job artifacts directory
│   └── {job_id}/
│       ├── audio.mp3
│       ├── images/
│       ├── output_transcript.txt
│       ├── output_words.json
│       └── output.mp4
└── tests/
    └── test_api.py               # [NEW] API unit tests using FastAPI TestClient
```

---

## Endpoint Specifications

### 1. `GET /health`
- **Response**:
  ```json
  {
    "status": "ok",
    "ffmpeg": true,
    "ffprobe": true,
    "whisper": true
  }
  ```

### 2. `POST /transcribe`
- **Content-Type**: `multipart/form-data`
- **Parameters**:
  - `audio_file`: `UploadFile` (Required)
  - `whisper_model`: `str` (Default: `"small"`)
- **Initial Response (202 Accepted)**:
  ```json
  {
    "job_id": "3b29c991-76a1-4328-86d1-cfdb9e7b2ff9",
    "status": "queued"
  }
  ```

### 3. `GET /transcribe/{job_id}`
- **Response**:
  ```json
  {
    "job_id": "3b29c991-76a1-4328-86d1-cfdb9e7b2ff9",
    "status": "completed",
    "created_at": "2026-08-02T02:25:00Z",
    "result_urls": {
      "transcript": "/download/3b29c991-76a1-4328-86d1-cfdb9e7b2ff9/transcript",
      "words": "/download/3b29c991-76a1-4328-86d1-cfdb9e7b2ff9/words"
    },
    "error_message": null
  }
  ```

### 4. `POST /generate-video`
- **Content-Type**: `multipart/form-data`
- **Parameters**:
  - `images_mode`: `"files"` or `"zip"` (Default: `"files"`)
  - `images`: `List[UploadFile]` (Optional if `images_mode == "files"`)
  - `zip_file`: `UploadFile` (Optional if `images_mode == "zip"`)
  - `transcript_file`: `UploadFile` (Optional)
  - `audio_file`: `UploadFile` (Optional)
  - `whisper_model`: `str` (Default: `"small"`)
  - `resolution`: `str` (Default: `"1920x1080"`)
  - `fps`: `int` (Default: `30`)
  - `audio_offset`: `float` (Default: `0.0`)
  - `total_duration`: `float` (Optional)
  - `on_mismatch`: `"truncate"`, `"error"` (Default: `"truncate"`)
- **Validation**: Requires at least `transcript_file` OR `audio_file`. Returns HTTP 400 if neither is provided.

### 5. `GET /generate-video/{job_id}`
- **Response**:
  ```json
  {
    "job_id": "3b29c991-76a1-4328-86d1-cfdb9e7b2ff9",
    "status": "completed",
    "created_at": "2026-08-02T02:25:00Z",
    "result_urls": {
      "video": "/download/3b29c991-76a1-4328-86d1-cfdb9e7b2ff9/video"
    },
    "error_message": null
  }
  ```

### 6. `GET /download/{job_id}/{file_type}`
- **Parameters**: `file_type` in `["transcript", "words", "video"]`.
- **Response**: `FileResponse` returning file data.

---

## Verification Plan

### Automated Tests (`tests/test_api.py`)
1. Test `/health` endpoint.
2. Test `/transcribe` endpoint with mocked Whisper worker.
3. Test `/generate-video` endpoint validation (HTTP 400 when missing both transcript and audio).
4. Test `/download/{job_id}/{file_type}` returns FileResponse.

### Manual Verification
1. Start API server using `uvicorn api:app --port 8000`.
2. Inspect OpenAPI Swagger docs at `http://localhost:8000/docs`.
3. Run test `curl` requests for `/health`, `/transcribe`, and `/generate-video`.
