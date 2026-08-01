"""
Unit tests for transcriber module.
Tests formatting functions, segment conversion, and word timestamp extraction.
"""
import json
import pytest
from modules.transcriber import (
    format_timestamp,
    format_segments_as_transcript,
    extract_word_timestamps,
    save_word_timestamps_json
)


def test_format_timestamp():
    assert format_timestamp(0.0) == "[00:00]"
    assert format_timestamp(5.2) == "[00:05]"
    assert format_timestamp(65.4) == "[01:05]"
    assert format_timestamp(3605.0) == "[60:05]"


def test_format_segments_as_transcript():
    segments = [
        {"start": 0.0, "end": 4.5, "text": " Welcome to the video presentation. "},
        {"start": 4.5, "end": 12.0, "text": " In this section we explain the architecture. "},
    ]

    formatted = format_segments_as_transcript(segments)
    expected = (
        "[00:00] Welcome to the video presentation.\n"
        "[00:04] In this section we explain the architecture.\n"
    )
    assert formatted == expected


def test_extract_word_timestamps():
    segments = [
        {
            "start": 0.0,
            "end": 2.0,
            "text": "Hello world",
            "words": [
                {"word": " Hello", "start": 0.1, "end": 0.5},
                {"word": " world", "start": 0.6, "end": 1.2}
            ]
        }
    ]

    words = extract_word_timestamps(segments)
    assert len(words) == 2
    assert words[0] == {"word": "Hello", "start": 0.1, "end": 0.5}
    assert words[1] == {"word": "world", "start": 0.6, "end": 1.2}


def test_save_word_timestamps_json(tmp_path):
    words = [{"word": "Hello", "start": 0.1, "end": 0.5}]
    out_json = tmp_path / "words.json"

    saved_path = save_word_timestamps_json(words, out_json)
    assert saved_path == out_json.resolve()

    data = json.loads(out_json.read_text(encoding='utf-8'))
    assert data == words
