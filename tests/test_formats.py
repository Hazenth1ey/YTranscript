"""Tests for the output formats. We compare against exact expected strings so
any accidental change in spacing or timestamp style shows up immediately."""

import json

import pytest

from ytranscript.formats import (
    FORMATS,
    extension_for,
    format_transcript,
    timestamp_short,
    timestamp_srt,
    timestamp_vtt,
    to_markdown,
    to_srt,
    to_text,
    to_vtt,
)
from ytranscript.models import Segment, Transcript


@pytest.mark.parametrize(
    "seconds, srt, vtt, short",
    [
        (0, "00:00:00,000", "00:00:00.000", "0:00"),
        (1.5, "00:00:01,500", "00:00:01.500", "0:01"),
        (62.345, "00:01:02,345", "00:01:02.345", "1:02"),
        (3723.456, "01:02:03,456", "01:02:03.456", "1:02:03"),
        (-5, "00:00:00,000", "00:00:00.000", "0:00"),  # never negative
    ],
)
def test_timestamps(seconds, srt, vtt, short):
    assert timestamp_srt(seconds) == srt
    assert timestamp_vtt(seconds) == vtt
    assert timestamp_short(seconds) == short


def test_to_text_joins_into_paragraphs(sample_transcript):
    # Segments 1 and 2 are back-to-back; segment 3 starts after a 4.5 s pause,
    # so it becomes a new paragraph. The "\n" inside segment 2 is flattened.
    expected = (
        "We're no strangers to love You know the rules and so do I\n"
        "\n"
        "A full commitment's what I'm thinking of\n"
    )
    assert to_text(sample_transcript) == expected


def test_to_text_with_timestamps(sample_transcript):
    expected = (
        "[0:00] We're no strangers to love\n"
        "[0:02] You know the rules and so do I\n"
        "[0:10] A full commitment's what I'm thinking of\n"
    )
    assert to_text(sample_transcript, timestamps=True) == expected


def test_to_text_breaks_long_paragraphs():
    # 20 segments of ~50 chars back-to-back = ~1000 chars -> must split at 600.
    segs = [Segment("word " * 10, i * 1.0, 1.0) for i in range(20)]
    t = Transcript("id", "url", "English", "en", True, "test", segs)
    paragraphs = to_text(t).strip().split("\n\n")
    assert len(paragraphs) == 2
    assert all(len(p) <= 700 for p in paragraphs)


def test_to_text_empty():
    t = Transcript("id", "url", "English", "en", True, "test", [])
    assert to_text(t) == ""
    assert to_text(t, timestamps=True) == ""


def test_to_srt(sample_transcript):
    expected = (
        "1\n00:00:00,000 --> 00:00:02,500\nWe're no strangers to love\n"
        "\n"
        "2\n00:00:02,500 --> 00:00:05,500\nYou know the rules and so do I\n"
        "\n"
        "3\n00:00:10,000 --> 00:00:13,200\nA full commitment's what I'm thinking of\n"
    )
    assert to_srt(sample_transcript) == expected


def test_to_vtt(sample_transcript):
    out = to_vtt(sample_transcript)
    assert out.startswith("WEBVTT\n\n")
    assert "00:00:02.500 --> 00:00:05.500\nYou know the rules and so do I\n" in out
    assert "," not in out.split("\n")[2]  # VTT uses dots, never commas


def test_to_json_round_trips(sample_transcript):
    data = json.loads(format_transcript(sample_transcript, "json"))
    assert data["video_id"] == "dQw4w9WgXcQ"
    assert data["language_code"] == "en"
    assert data["is_generated"] is False
    assert len(data["segments"]) == 3
    assert data["segments"][1] == {"text": "You know the rules\nand so do I", "start": 2.5, "duration": 3.0}


def test_to_markdown(sample_transcript):
    out = to_markdown(sample_transcript)
    assert out.startswith("# Transcript of dQw4w9WgXcQ\n")
    assert "- **Language:** English (`en`, human-made)" in out
    assert "- **Duration:** 0:13" in out
    assert "**[0:02]** You know the rules and so do I  " in out


def test_to_markdown_uses_title_when_known(sample_transcript):
    sample_transcript.title = "Never Gonna Give You Up"
    assert to_markdown(sample_transcript).startswith("# Never Gonna Give You Up\n")


def test_format_registry_and_extensions():
    assert set(FORMATS) == {"txt", "srt", "vtt", "json", "md"}
    assert extension_for("srt") == ".srt"
    assert extension_for(".MD") == ".md"


def test_format_transcript_rejects_unknown(sample_transcript):
    with pytest.raises(ValueError, match="Unknown format"):
        format_transcript(sample_transcript, "docx")


def test_transcript_helpers(sample_transcript):
    assert sample_transcript.total_duration == 13.2
    assert sample_transcript.text.startswith("We're no strangers to love You know")
    assert sample_transcript.segments[1].end == 5.5
