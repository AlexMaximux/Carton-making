"""
Unit tests for ffmpeg_engine module.
"""
import pytest
from modules.ffmpeg_engine import (
    parse_and_validate_resolution,
    build_concat_file_content
)
from modules.timing_calculator import ImageSegment


def test_parse_and_validate_resolution_valid():
    assert parse_and_validate_resolution("1920x1080") == (1920, 1080)
    assert parse_and_validate_resolution("1280x720") == (1280, 720)
    assert parse_and_validate_resolution(" 3840X2160 ") == (3840, 2160)


def test_parse_and_validate_resolution_odd_dimensions():
    with pytest.raises(ValueError, match="odd dimensions"):
        parse_and_validate_resolution("1921x1080")

    with pytest.raises(ValueError, match="odd dimensions"):
        parse_and_validate_resolution("1920x1081")


def test_parse_and_validate_resolution_invalid_string():
    with pytest.raises(ValueError, match="Invalid resolution format"):
        parse_and_validate_resolution("1920-1080")


def test_build_concat_file_content():
    segments = [
        ImageSegment(image_path="/path/to/1.jpg", start_time=0.0, duration=4.5),
        ImageSegment(image_path="/path/to/2.png", start_time=4.5, duration=3.0),
    ]
    content = build_concat_file_content(segments)
    expected = (
        "file '/path/to/1.jpg'\n"
        "duration 4.5000\n"
        "file '/path/to/2.png'\n"
        "duration 3.0000\n"
        "file '/path/to/2.png'\n"
    )
    assert content == expected
