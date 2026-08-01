"""
Unit tests for main CLI entrypoint branching and Transcribe-Only mode.
"""
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from main import main, parse_args


def test_parse_args_defaults():
    args = parse_args(["--transcribe-audio", "test.mp3"])
    assert args.transcribe_audio == "test.mp3"
    assert args.images_dir is None
    assert args.transcript is None
    assert args.whisper_model == "small"


def test_transcribe_only_mode_bypasses_pipeline(tmp_path):
    audio_dir = tmp_path / "audio_folder"
    audio_dir.mkdir()
    audio_file = audio_dir / "voiceover.mp3"
    audio_file.write_text("dummy audio")

    mock_transcribe_res = {
        "segments": [{"start": 0.0, "end": 3.0, "text": "Hello world"}],
        "words": [{"word": "Hello", "start": 0.0, "end": 1.0}],
        "text": "Hello world"
    }

    with patch("main.check_whisper_installed"), \
         patch("main.check_ffprobe_installed", return_value="/usr/bin/ffprobe"), \
         patch("main.probe_file_duration", return_value=3.0), \
         patch("main.transcribe_audio", return_value=mock_transcribe_res) as mock_transcribe, \
         patch("main.SlideshowPipeline") as mock_pipeline_cls:

        mock_pipeline_instance = MagicMock()
        mock_pipeline_cls.return_value = mock_pipeline_instance

        exit_code = main(["--transcribe-audio", str(audio_file)])

        # Assert exit code 0
        assert exit_code == 0

        # Assert transcribe_audio was called
        mock_transcribe.assert_called_once_with(audio_file.resolve(), model_size="small")

        # Assert SlideshowPipeline was NEVER instantiated or run
        mock_pipeline_cls.assert_not_called()
        mock_pipeline_instance.run.assert_not_called()

        # Assert default files created in audio file's directory
        expected_transcript = audio_dir / "output_transcript.txt"
        expected_words = audio_dir / "output_words.json"

        assert expected_transcript.exists()
        assert expected_words.exists()

        assert "[00:00] Hello world" in expected_transcript.read_text(encoding='utf-8')
