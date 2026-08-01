"""
Unit tests for timing_calculator module.
"""
import pytest
from pathlib import Path
from modules.timing_calculator import (
    extract_numerical_key,
    get_sorted_images,
    calculate_timings,
    MismatchWarning
)


def test_extract_numerical_key():
    assert extract_numerical_key("1.jpg") == (1, "1")
    assert extract_numerical_key("img_02.png") == (2, "img_02")
    assert extract_numerical_key("10_photo.jpeg") == (10, "10_photo")
    assert extract_numerical_key("abc.png") == (99999999, "abc")


def test_get_sorted_images(tmp_path):
    # Create test images in non-sorted order
    (tmp_path / "10.jpg").write_text("dummy")
    (tmp_path / "2.png").write_text("dummy")
    (tmp_path / "1.jpeg").write_text("dummy")

    sorted_files = get_sorted_images(tmp_path)
    names = [f.name for f in sorted_files]
    assert names == ["1.jpeg", "2.png", "10.jpg"]


def test_calculate_timings_normal(tmp_path):
    img1 = tmp_path / "1.jpg"
    img2 = tmp_path / "2.jpg"
    img3 = tmp_path / "3.jpg"
    for f in (img1, img2, img3):
        f.write_text("dummy")

    timestamps = [0.0, 5.0, 12.0]
    image_paths = [img1, img2, img3]

    # Without total_duration (last segment duration uses previous segment duration: 12-5 = 7.0)
    segments = calculate_timings(timestamps, image_paths, on_mismatch="error")
    assert len(segments) == 3
    assert segments[0].duration == 5.0
    assert segments[1].duration == 7.0
    assert segments[2].duration == 7.0

    # With total_duration = 20.0
    segments2 = calculate_timings(timestamps, image_paths, total_duration=20.0, on_mismatch="error")
    assert segments2[2].duration == 8.0  # 20.0 - 12.0


def test_calculate_timings_mismatch_truncate(tmp_path):
    img1 = tmp_path / "1.jpg"
    img2 = tmp_path / "2.jpg"
    img3 = tmp_path / "3.jpg"

    timestamps = [0.0, 5.0]
    image_paths = [img1, img2, img3]

    # Should truncate to min(2, 3) = 2
    segments = calculate_timings(timestamps, image_paths, on_mismatch="truncate")
    assert len(segments) == 2


def test_calculate_timings_mismatch_raise():
    timestamps = [0.0, 5.0]
    image_paths = ["1.jpg", "2.jpg", "3.jpg"]

    with pytest.raises(MismatchWarning):
        calculate_timings(timestamps, image_paths, on_mismatch="ask")

    with pytest.raises(ValueError, match="Timestamp count"):
        calculate_timings(timestamps, image_paths, on_mismatch="error")
