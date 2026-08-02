"""
Unit tests for FastAPI REST API (api.py).
Mocks Whisper transcription and FFmpeg SlideshowPipeline.run execution to ensure fast unit tests without live heavy media processing.
"""
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from api import app, job_store


client = TestClient(app)


def test_health_endpoint():
    with patch("api.check_ffmpeg_installed"), \
         patch("api.check_ffprobe_installed"), \
         patch("api.check_whisper_installed"):

        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["ffmpeg"] is True
        assert data["ffprobe"] is True
        assert data["whisper"] is True


def test_transcribe_endpoint_success(tmp_path):
    mock_res = {
        "segments": [{"start": 0.0, "end": 2.0, "text": "Hello world"}],
        "words": [{"word": "Hello", "start": 0.0, "end": 1.0}],
        "text": "Hello world"
    }

    with patch("api.transcribe_audio", return_value=mock_res) as mock_transcribe:
        # 1. Post job
        audio_content = b"fake audio data"
        response = client.post(
            "/transcribe",
            files={"audio_file": ("test.mp3", audio_content, "audio/mpeg")},
            data={"whisper_model": "tiny"}
        )

        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        job_id = data["job_id"]

        # 2. Get status
        status_res = client.get(f"/transcribe/{job_id}")
        assert status_res.status_code == 200
        job_data = status_res.json()
        assert job_data["status"] in ["completed", "processing", "queued"]

        # If job completed in background, verify result URLs
        if job_data["status"] == "completed":
            assert "transcript" in job_data["result_urls"]
            assert "words" in job_data["result_urls"]


def test_generate_video_validation_missing_input():
    # Attempting to generate video without transcript_file AND without audio_file
    response = client.post(
        "/generate-video",
        data={"images_mode": "files"},
        files=[("images", ("1.png", b"fake image", "image/png"))]
    )
    assert response.status_code == 400
    assert "Missing transcript input" in response.json()["detail"]


def test_generate_video_endpoint_success():
    with patch("api.SlideshowPipeline") as mock_pipeline_cls:
        mock_instance = MagicMock()
        mock_pipeline_cls.return_value = mock_instance

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
