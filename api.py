"""
REST API Layer for Modular Slideshow Video Generator & Whisper Transcriber
Powered by FastAPI & Uvicorn.
"""
import shutil
import threading
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Union

from fastapi import FastAPI, BackgroundTasks, File, Form, HTTPException, UploadFile, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from modules.ffmpeg_engine import check_ffmpeg_installed
from modules.audio_muxer import check_ffprobe_installed, probe_file_duration
from modules.transcriber import (
    check_whisper_installed,
    transcribe_audio,
    format_segments_as_transcript,
    save_word_timestamps_json
)
from modules.pipeline import SlideshowPipeline

# Initialize FastAPI App
app = FastAPI(
    title="Slideshow Video Generator & Whisper Transcriber API",
    description="REST API for speech-to-text audio transcription and slideshow video generation using FFmpeg and OpenAI Whisper.",
    version="1.0.0"
)

# 1. Enable CORS Middleware
# Note: For production deployments, restrict allow_origins to trusted domains.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Base Storage Directory for temporary job artifacts
STORAGE_DIR = Path("./storage").resolve()
STORAGE_DIR.mkdir(exist_ok=True)


import json


# 2. Thread-Safe Job Store Model & Manager
class JobModel(BaseModel):
    job_id: str
    job_type: str  # "transcribe" or "generate-video"
    status: str  # "queued", "processing", "completed", "failed"
    created_at: str
    error_message: Optional[str] = None
    result_paths: Dict[str, str] = Field(default_factory=dict)
    result_urls: Dict[str, str] = Field(default_factory=dict)


class JobStore:
    """Thread-safe in-memory job status store backed by disk persistence for multi-worker process safety and server restarts."""
    def __init__(self):
        self._jobs: Dict[str, JobModel] = {}
        self._lock = threading.Lock()

    def _save_job_to_disk(self, job: JobModel):
        try:
            job_dir = STORAGE_DIR / job.job_id
            job_dir.mkdir(parents=True, exist_ok=True)
            meta_file = job_dir / "job.json"
            meta_file.write_text(job.model_dump_json(indent=2), encoding="utf-8")
        except Exception:
            pass

    def create_job(self, job_id: str, job_type: str) -> JobModel:
        with self._lock:
            now_iso = datetime.now(timezone.utc).isoformat()
            job = JobModel(
                job_id=job_id,
                job_type=job_type,
                status="queued",
                created_at=now_iso
            )
            self._jobs[job_id] = job
            self._save_job_to_disk(job)
            return job

    def get_job(self, job_id: str) -> Optional[JobModel]:
        with self._lock:
            if job_id in self._jobs:
                return self._jobs[job_id]

            # Disk fallback for multi-worker process setup or server restarts
            meta_file = STORAGE_DIR / job_id / "job.json"
            if meta_file.is_file():
                try:
                    data = json.loads(meta_file.read_text(encoding="utf-8"))
                    job = JobModel(**data)
                    self._jobs[job_id] = job
                    return job
                except Exception:
                    pass
            return None

    def update_job(
        self,
        job_id: str,
        status: Optional[str] = None,
        error_message: Optional[str] = None,
        result_paths: Optional[Dict[str, str]] = None,
        result_urls: Optional[Dict[str, str]] = None
    ) -> Optional[JobModel]:
        with self._lock:
            job = self.get_job(job_id)
            if not job:
                return None
            if status:
                job.status = status
            if error_message:
                job.error_message = error_message
            if result_paths:
                job.result_paths.update(result_paths)
            if result_urls:
                job.result_urls.update(result_urls)
            self._jobs[job_id] = job
            self._save_job_to_disk(job)
            return job


job_store = JobStore()


# 3. Health Check Endpoint
@app.get("/health", summary="Health Check", description="Checks server status and availability of system dependencies (FFmpeg, ffprobe, Whisper).")
def health_check():
    ffmpeg_ok = False
    ffprobe_ok = False
    whisper_ok = False

    try:
        check_ffmpeg_installed()
        ffmpeg_ok = True
    except Exception:
        pass

    try:
        check_ffprobe_installed()
        ffprobe_ok = True
    except Exception:
        pass

    try:
        check_whisper_installed()
        whisper_ok = True
    except Exception:
        pass

    return {
        "status": "ok",
        "ffmpeg": ffmpeg_ok,
        "ffprobe": ffprobe_ok,
        "whisper": whisper_ok
    }


# 4. Background Workers
def run_transcribe_job(job_id: str, audio_file_path: Path, whisper_model: str):
    job_dir = STORAGE_DIR / job_id
    try:
        job_store.update_job(job_id, status="processing")

        res = transcribe_audio(audio_file_path, model_size=whisper_model)

        transcript_path = job_dir / "transcript.txt"
        words_path = job_dir / "words.json"

        formatted_txt = format_segments_as_transcript(res["segments"])
        transcript_path.write_text(formatted_txt, encoding='utf-8')

        save_word_timestamps_json(res["words"], words_path)

        result_paths = {
            "transcript": str(transcript_path),
            "words": str(words_path)
        }
        result_urls = {
            "transcript": f"/download/{job_id}/transcript",
            "words": f"/download/{job_id}/words"
        }

        job_store.update_job(
            job_id,
            status="completed",
            result_paths=result_paths,
            result_urls=result_urls
        )
    except Exception as err:
        job_store.update_job(job_id, status="failed", error_message=str(err))


def run_generate_video_job(
    job_id: str,
    images_dir: Path,
    transcript_file_path: Optional[Path],
    audio_file_path: Optional[Path],
    whisper_model: str,
    resolution: str,
    fps: int,
    audio_offset: float,
    total_duration: Optional[float],
    on_mismatch: str
):
    job_dir = STORAGE_DIR / job_id
    try:
        job_store.update_job(job_id, status="processing")

        # If audio provided without transcript, transcribe audio first
        if audio_file_path and not transcript_file_path:
            res = transcribe_audio(audio_file_path, model_size=whisper_model)
            t_path = job_dir / "transcript.txt"
            t_path.write_text(format_segments_as_transcript(res["segments"]), encoding='utf-8')
            w_path = job_dir / "words.json"
            save_word_timestamps_json(res["words"], w_path)
            transcript_file_path = t_path
            job_store.update_job(job_id, result_urls={
                "transcript": f"/download/{job_id}/transcript",
                "words": f"/download/{job_id}/words"
            })

        output_video_path = job_dir / "output.mp4"

        pipeline = SlideshowPipeline()
        pipeline.run(
            images_dir=images_dir,
            transcript_path=transcript_file_path,
            output_path=output_video_path,
            audio_path=audio_file_path,
            audio_offset=audio_offset,
            resolution=resolution,
            fps=fps,
            total_duration=total_duration,
            on_mismatch=on_mismatch
        )

        result_paths = {"video": str(output_video_path)}
        result_urls = {"video": f"/download/{job_id}/video"}

        job_store.update_job(
            job_id,
            status="completed",
            result_paths=result_paths,
            result_urls=result_urls
        )
    except Exception as err:
        job_store.update_job(job_id, status="failed", error_message=str(err))


# 5. REST Endpoints

@app.post("/transcribe", summary="Create Audio Transcription Job", status_code=202)

async def create_transcribe_job(
    background_tasks: BackgroundTasks,
    audio_file: UploadFile = File(..., description="Audio file to transcribe (mp3, wav, m4a, etc.)"),
    whisper_model: str = Form("small", description="Whisper model size: tiny, base, small, medium, large")
):
    job_id = str(uuid.uuid4())
    job_dir = STORAGE_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    audio_ext = Path(audio_file.filename).suffix or ".mp3"
    audio_saved_path = job_dir / f"audio{audio_ext}"

    with open(audio_saved_path, "wb") as buffer:
        shutil.copyfileobj(audio_file.file, buffer)

    job_store.create_job(job_id, job_type="transcribe")
    background_tasks.add_task(run_transcribe_job, job_id, audio_saved_path, whisper_model)

    return {"job_id": job_id, "status": "queued"}


@app.get("/transcribe/{job_id}", summary="Get Transcription Job Status")
def get_transcribe_status(job_id: str):
    job = job_store.get_job(job_id)
    if not job or job.job_type != "transcribe":
        raise HTTPException(status_code=404, detail=f"Transcribe job '{job_id}' not found.")
    return job


@app.post("/generate-video", summary="Create Slideshow Video Generation Job", status_code=202)
async def create_generate_video_job(
    background_tasks: BackgroundTasks,
    images_mode: str = Form("files", description="Image upload mode: 'files' or 'zip'"),
    images: Optional[List[UploadFile]] = File(None, description="List of image files when images_mode='files'"),
    zip_file: Optional[UploadFile] = File(None, description="ZIP archive containing images when images_mode='zip'"),
    transcript_file: Optional[UploadFile] = File(None, description="Optional manual transcript file [mm:ss] text"),
    audio_file: Optional[UploadFile] = File(None, description="Optional audio file for background sound or auto-transcription"),
    whisper_model: str = Form("small", description="Whisper model size if auto-transcribing"),
    resolution: str = Form("1920x1080", description="Video resolution WxH (even dimensions required)"),
    fps: int = Form(30, description="Video framerate"),
    audio_offset: float = Form(0.0, description="Audio offset in seconds (+ delay, - trim)"),
    total_duration: Optional[float] = Form(None, description="Optional total video duration in seconds"),
    on_mismatch: str = Form("truncate", description="Mismatch resolution mode: 'truncate' or 'error'")
):
    # Validation: Must provide either transcript_file or audio_file for automatic transcription
    if not transcript_file and not audio_file:
        raise HTTPException(
            status_code=400,
            detail="Missing transcript input! Must provide either 'transcript_file' OR 'audio_file' for auto-transcription."
        )

    job_id = str(uuid.uuid4())
    job_dir = STORAGE_DIR / job_id
    images_dir = job_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    # Save images
    if images_mode == "zip":
        if not zip_file:
            raise HTTPException(status_code=400, detail="Missing 'zip_file' parameter when images_mode='zip'.")
        zip_path = job_dir / "images.zip"
        with open(zip_path, "wb") as buffer:
            shutil.copyfileobj(zip_file.file, buffer)
        try:
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(images_dir)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid or corrupted ZIP archive: {e}")
    else:
        if not images:
            raise HTTPException(status_code=400, detail="Missing 'images' files when images_mode='files'.")
        for img in images:
            img_target = images_dir / Path(img.filename).name
            with open(img_target, "wb") as buffer:
                shutil.copyfileobj(img.file, buffer)

    # Save optional transcript file
    saved_transcript_path = None
    if transcript_file:
        saved_transcript_path = job_dir / "manual_transcript.txt"
        with open(saved_transcript_path, "wb") as buffer:
            shutil.copyfileobj(transcript_file.file, buffer)

    # Save optional audio file
    saved_audio_path = None
    if audio_file:
        a_ext = Path(audio_file.filename).suffix or ".mp3"
        saved_audio_path = job_dir / f"audio{a_ext}"
        with open(saved_audio_path, "wb") as buffer:
            shutil.copyfileobj(audio_file.file, buffer)

    job_store.create_job(job_id, job_type="generate-video")

    background_tasks.add_task(
        run_generate_video_job,
        job_id=job_id,
        images_dir=images_dir,
        transcript_file_path=saved_transcript_path,
        audio_file_path=saved_audio_path,
        whisper_model=whisper_model,
        resolution=resolution,
        fps=fps,
        audio_offset=audio_offset,
        total_duration=total_duration,
        on_mismatch=on_mismatch
    )

    return {"job_id": job_id, "status": "queued"}


@app.get("/generate-video/{job_id}", summary="Get Video Generation Job Status")
def get_generate_video_status(job_id: str):
    job = job_store.get_job(job_id)
    if not job or job.job_type != "generate-video":
        raise HTTPException(status_code=404, detail=f"Generate video job '{job_id}' not found.")
    return job


@app.get("/download/{job_id}/{file_type}", summary="Download Job Output File")
def download_file(job_id: str, file_type: str):
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    if job.status != "completed":
        raise HTTPException(status_code=400, detail=f"Job '{job_id}' is not completed yet (current status: '{job.status}').")

    file_path_str = job.result_paths.get(file_type)
    if not file_path_str:
        raise HTTPException(status_code=404, detail=f"File type '{file_type}' not found for job '{job_id}'.")

    file_path = Path(file_path_str)
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"File '{file_path.name}' is missing on server.")

    media_types = {
        "transcript": "text/plain; charset=utf-8",
        "words": "application/json",
        "video": "video/mp4"
    }
    media_type = media_types.get(file_type, "application/octet-stream")

    return FileResponse(path=file_path, filename=file_path.name, media_type=media_type)


# TODO: Implement a periodic background cleanup task (e.g. using APScheduler or asyncio loop)
# to automatically purge storage directories (./storage/{job_id}) older than 1 hour.
