"""
Unit tests for FastAPI REST API (api.py).
Mocks Whisper transcription and FFmpeg SlideshowPipeline.run execution to ensure fast unit tests without live heavy media processing.
"""
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from api import app, job_store


def test_health_endpoint():
    with patch("api.check_ffmpeg_installed"), \
         patch("api.check_ffprobe_installed"), \
         patch("api.check_whisper_installed"), \
         TestClient(app) as client:

        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["ffmpeg"] is True
        assert data["ffprobe"] is True
        assert data["whisper"] is True


def test_transcribe_endpoint_success(tmp_path):
    with patch("fastapi.BackgroundTasks.add_task"), \
         TestClient(app) as client:
        response = client.post(
            "/transcribe",
            files={"audio_file": ("test.mp3", b"fake audio", "audio/mpeg")},
            data={"whisper_model": "tiny"}
        )

        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        job_id = data["job_id"]

        status_res = client.get(f"/transcribe/{job_id}")
        assert status_res.status_code == 200
        job_data = status_res.json()
        assert job_data["status"] in ["queued", "processing", "completed"]


def test_generate_video_validation_missing_input():
    with TestClient(app) as client:
        response = client.post(
            "/generate-video",
            data={"images_mode": "files"},
            files=[("images", ("1.png", b"fake image", "image/png"))]
        )
        assert response.status_code == 400
        assert "Missing transcript input" in response.json()["detail"]


def test_generate_video_endpoint_success():
    with patch("fastapi.BackgroundTasks.add_task"), \
         TestClient(app) as client:
        response = client.post(
            "/generate-video",
            data={
                "images_mode": "files",
                "resolution": "1920x1080",
                "fps": 30
            },
            files=[
                ("images", ("1.png", b"fake image 1", "image/png")),
                ("transcript_file", ("transcript.txt", b"[00:00] Slide 1", "text/plain"))
            ]
        )

        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        job_id = data["job_id"]

        status_res = client.get(f"/generate-video/{job_id}")
        assert status_res.status_code == 200
        assert status_res.json()["job_type"] == "generate-video"


def test_job_store_disk_fallback():
    job_id = "test-disk-fallback-123"
    try:
        job = job_store.create_job(job_id, job_type="transcribe")
        job_store.update_job(job_id, status="completed")

        job_store._jobs.clear()
        assert job_id not in job_store._jobs

        recovered_job = job_store.get_job(job_id)
        assert recovered_job is not None
        assert recovered_job.job_id == job_id
        assert recovered_job.status == "completed"
    finally:
        from api import STORAGE_DIR
        import shutil
        job_dir = STORAGE_DIR / job_id
        if job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)
        job_store._jobs.pop(job_id, None)
