"""
Unit tests for modules/caption_generator.py
"""

import json
import pytest
from pathlib import Path

from modules.caption_generator import (
    hex_to_ass_color,
    format_ass_time,
    load_words_json,
    group_words_into_lines,
    build_ass_subtitle
)


def test_hex_to_ass_color():
    """Verifies hex to ASS color conversion (#RRGGBB -> &HBBGGRR&)."""
    assert hex_to_ass_color("#FFD60A") == "&H0AD6FF&"
    assert hex_to_ass_color("#FFFFFF") == "&HFFFFFF&"
    assert hex_to_ass_color("#000000") == "&H000000&"
    assert hex_to_ass_color("FF0000") == "&H0000FF&"

    # Test alpha inclusion
    assert hex_to_ass_color("#FFD60A", include_alpha=True) == "&H000AD6FF&"
    assert hex_to_ass_color("#000000", include_alpha=True) == "&H00000000&"

    # Test invalid hex
    with pytest.raises(ValueError):
        hex_to_ass_color("invalid")


def test_format_ass_time():
    """Verifies float seconds formatting to ASS H:MM:SS.cs timestamp string."""
    assert format_ass_time(0.0) == "0:00:00.00"
    assert format_ass_time(1.23) == "0:00:01.23"
    assert format_ass_time(65.4) == "0:01:05.40"
    assert format_ass_time(3661.05) == "1:01:01.05"


def test_group_words_into_lines_basic():
    """Verifies word grouping with word count limits and silence gaps."""
    sample_words = [
        {"word": "Hello", "start": 0.0, "end": 0.5},
        {"word": "world", "start": 0.5, "end": 1.0},
        {"word": "this", "start": 1.0, "end": 1.4},
        {"word": "is", "start": 1.4, "end": 1.6},
        {"word": "a", "start": 1.6, "end": 1.7},
        {"word": "test", "start": 1.7, "end": 2.2},
    ]

    groups = group_words_into_lines(sample_words, max_words_per_line=3, max_lines_per_group=2)
    assert len(groups) >= 1
    assert groups[0]["start_time"] == 0.0
    assert groups[0]["end_time"] >= 1.0


def test_group_words_into_lines_silence_split():
    """Verifies grouping splits when silence threshold (1.0s) is exceeded."""
    sample_words = [
        {"word": "First", "start": 0.0, "end": 0.5},
        {"word": "part", "start": 0.5, "end": 1.0},
        # 2-second pause here
        {"word": "Second", "start": 3.0, "end": 3.5},
        {"word": "part", "start": 3.5, "end": 4.0},
    ]

    groups = group_words_into_lines(sample_words, silence_threshold=1.0)
    assert len(groups) == 2
    assert groups[0]["start_time"] == 0.0
    assert groups[0]["end_time"] == 1.0
    assert groups[1]["start_time"] == 3.0
    assert groups[1]["end_time"] == 4.0


def test_build_ass_subtitle_alignment_and_scaling():
    """Verifies ASS subtitle generation includes correct Alignment=2 for bottom position and dynamic font sizing."""
    sample_words = [
        {"word": "Test", "start": 0.0, "end": 1.0},
        {"word": "Subtitle", "start": 1.0, "end": 2.0},
    ]
    groups = group_words_into_lines(sample_words)

    # 1080p video test
    ass_1080p = build_ass_subtitle(
        word_groups=groups,
        style_config={"position": "bottom", "highlight_color": "#FFD60A"},
        video_width=1920,
        video_height=1080
    )

    assert "[Script Info]" in ass_1080p
    assert "[V4+ Styles]" in ass_1080p
    assert "[Events]" in ass_1080p
    assert "PlayResX: 1920" in ass_1080p
    assert "PlayResY: 1080" in ass_1080p

    # Alignment=2 is bottom-center in ASS numpad
    assert ",2,20,20," in ass_1080p  # Alignment=2 in Style line
    # Font size 5% of 1080 = 54
    assert ",54," in ass_1080p

    # Highlight color tag &H0AD6FF& (from #FFD60A)
    assert r"{\c&H0AD6FF&}Test" in ass_1080p
    assert r"{\c&H0AD6FF&}Subtitle" in ass_1080p

    # 720p video test to verify dynamic font scaling
    ass_720p = build_ass_subtitle(
        word_groups=groups,
        style_config={"position": "bottom"},
        video_width=1280,
        video_height=720
    )
    # Font size 5% of 720 = 36
    assert ",36," in ass_720p


def test_load_words_json(tmp_path):
    """Verifies loading valid and invalid words JSON files."""
    valid_data = [
        {"word": "hello", "start": 0.0, "end": 0.5},
        {"word": "world", "start": 0.5, "end": 1.0}
    ]
    json_file = tmp_path / "test_words.json"
    json_file.write_text(json.dumps(valid_data), encoding="utf-8")

    loaded = load_words_json(json_file)
    assert len(loaded) == 2
    assert loaded[0]["word"] == "hello"
    assert loaded[1]["end"] == 1.0
