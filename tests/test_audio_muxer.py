"""
Unit tests for audio_muxer module.
Tests probe_file_duration and mux_audio logic across:
- Video longer than audio (stream copy -c:v copy -shortest)
- Audio longer than video (video frame freeze via tpad filter and -c:v libx264)
- Positive and negative audio offsets
- Equal durations
"""
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from modules.audio_muxer import probe_file_duration, mux_audio


def test_probe_file_duration_success(tmp_path):
    dummy_media = tmp_path / "media.mp3"
    dummy_media.write_text("dummy content")

    mock_res = MagicMock()
    mock_res.stdout = "45.123\n"
    mock_res.returncode = 0

    with patch("shutil.which", return_value="/usr/bin/ffprobe"):
        with patch("subprocess.run", return_value=mock_res) as mock_run:
            duration = probe_file_duration(dummy_media)
            assert duration == 45.123
            mock_run.assert_called_once()


def test_probe_file_duration_invalid(tmp_path):
    dummy_media = tmp_path / "corrupt.mp3"
    dummy_media.write_text("corrupt content")

    mock_res = MagicMock()
    mock_res.stdout = ""
    mock_res.returncode = 1

    with patch("shutil.which", return_value="/usr/bin/ffprobe"):
        with patch("subprocess.run", return_value=mock_res):
            with pytest.raises(ValueError, match="Invalid media file"):
                probe_file_duration(dummy_media)


def test_mux_audio_video_longer(tmp_path):
    video = tmp_path / "video.mp4"
    audio = tmp_path / "audio.mp3"
    output = tmp_path / "out.mp4"
    video.write_text("video")
    audio.write_text("audio")

    # Video: 12.0s, Audio: 8.0s -> Video is longer
    with patch("modules.audio_muxer.probe_file_duration", side_effect=[12.0, 8.0]):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            res_path, v_dur, a_dur, diff, extended, extend_by = mux_audio(video, audio, output, offset=0.0)

            assert res_path == output.resolve()
            assert v_dur == 12.0
            assert a_dur == 8.0
            assert diff == 4.0
            assert not extended
            assert extend_by == 0.0

            cmd = mock_run.call_args[0][0]
            assert "-c:v" in cmd
            idx_cv = cmd.index("-c:v")
            assert cmd[idx_cv + 1] == "copy"
            assert "-shortest" in cmd


def test_mux_audio_audio_longer_tpad(tmp_path):
    video = tmp_path / "video.mp4"
    audio = tmp_path / "audio.mp3"
    output = tmp_path / "out.mp4"
    video.write_text("video")
    audio.write_text("audio")

    # Video: 10.0s, Audio: 15.0s -> Audio is longer by 5.0s
    with patch("modules.audio_muxer.probe_file_duration", side_effect=[10.0, 15.0]):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            res_path, v_dur, a_dur, diff, extended, extend_by = mux_audio(video, audio, output, offset=0.0)

            assert v_dur == 10.0
            assert a_dur == 15.0
            assert diff == 5.0
            assert extended
            assert extend_by == 5.0

            cmd = mock_run.call_args[0][0]
            assert "-filter_complex" in cmd
            idx_fc = cmd.index("-filter_complex")
            assert "tpad=stop_mode=clone:stop_duration=5.0000" in cmd[idx_fc + 1]
            assert "-c:v" in cmd
            idx_cv = cmd.index("-c:v")
            assert cmd[idx_cv + 1] == "libx264"
            assert "-shortest" not in cmd


def test_mux_audio_tpad_with_positive_offset(tmp_path):
    video = tmp_path / "video.mp4"
    audio = tmp_path / "audio.mp3"
    output = tmp_path / "out.mp4"
    video.write_text("video")
    audio.write_text("audio")

    # Video: 10.0s, Audio: 12.0s, Offset: +2.0s -> Effective audio = 14.0s -> Extend by 4.0s
    with patch("modules.audio_muxer.probe_file_duration", side_effect=[10.0, 12.0]):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            res_path, v_dur, a_dur, diff, extended, extend_by = mux_audio(video, audio, output, offset=2.0)

            assert extended
            assert extend_by == 4.0

            cmd = mock_run.call_args[0][0]
            assert "-itsoffset" in cmd
            idx_off = cmd.index("-itsoffset")
            assert cmd[idx_off + 1] == "2.0000"
            # Ensure offset is before audio input
            assert cmd[idx_off + 2] == "-i"
            assert cmd[idx_off + 3] == str(audio.resolve())
            assert "tpad=stop_mode=clone:stop_duration=4.0000" in cmd[cmd.index("-filter_complex") + 1]


def test_mux_audio_tpad_with_negative_offset(tmp_path):
    video = tmp_path / "video.mp4"
    audio = tmp_path / "audio.mp3"
    output = tmp_path / "out.mp4"
    video.write_text("video")
    audio.write_text("audio")

    # Video: 5.0s, Audio: 10.0s, Offset: -2.0s -> Effective audio = 8.0s -> Extend by 3.0s
    with patch("modules.audio_muxer.probe_file_duration", side_effect=[5.0, 10.0]):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            res_path, v_dur, a_dur, diff, extended, extend_by = mux_audio(video, audio, output, offset=-2.0)

            assert extended
            assert extend_by == 3.0

            cmd = mock_run.call_args[0][0]
            assert "-ss" in cmd
            idx_ss = cmd.index("-ss")
            assert cmd[idx_ss + 1] == "2.0000"
            assert cmd[idx_ss + 2] == "-i"
            assert cmd[idx_ss + 3] == str(audio.resolve())
            assert "tpad=stop_mode=clone:stop_duration=3.0000" in cmd[cmd.index("-filter_complex") + 1]


def test_mux_audio_equal_durations(tmp_path):
    video = tmp_path / "video.mp4"
    audio = tmp_path / "audio.mp3"
    output = tmp_path / "out.mp4"
    video.write_text("video")
    audio.write_text("audio")

    # Video: 10.0s, Audio: 10.0s -> Equal
    with patch("modules.audio_muxer.probe_file_duration", side_effect=[10.0, 10.0]):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            res_path, v_dur, a_dur, diff, extended, extend_by = mux_audio(video, audio, output, offset=0.0)

            assert not extended
            assert extend_by == 0.0
            cmd = mock_run.call_args[0][0]
            assert "-c:v" in cmd
            assert cmd[cmd.index("-c:v") + 1] == "copy"
