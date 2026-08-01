"""
Unit tests for transcript_parser module.
"""
import pytest
from modules.transcript_parser import parse_timestamp_str, parse_transcript


def test_parse_timestamp_str():
    assert parse_timestamp_str("0:05") == 5.0
    assert parse_timestamp_str("01:30") == 90.0
    assert parse_timestamp_str("01:02:03") == 3723.0
    assert parse_timestamp_str("0:15.5") == 15.5
    assert parse_timestamp_str("01:02.345") == 62.345


def test_parse_transcript_content():
    content = """
    Intro line [0:00]
    First slide narrative [0:04.5]
    Second slide details [0:12]
    Final slide conclusion [01:05]
    """
    timestamps = parse_transcript(content)
    assert timestamps == [0.0, 4.5, 12.0, 65.0]


def test_parse_transcript_file(tmp_path):
    transcript_file = tmp_path / "transcript.txt"
    transcript_file.write_text(
        "[0:02] Welcome\n[0:08] Section 1\n[01:15] Section 2",
        encoding='utf-8'
    )
    timestamps = parse_transcript(transcript_file)
    assert timestamps == [2.0, 8.0, 75.0]


def test_parse_transcript_no_timestamps():
    with pytest.raises(ValueError, match="No valid timestamps found"):
        parse_transcript("This text contains no timestamp brackets.")
