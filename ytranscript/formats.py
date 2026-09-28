"""Convert a ``Transcript`` into different file formats.

Supported formats:

* ``txt``  - plain readable text, grouped into paragraphs.
* ``srt``  - the classic subtitle format (VLC, YouTube upload, video editors).
* ``vtt``  - WebVTT, the subtitle format web browsers use.
* ``json`` - machine-readable, keeps every timestamp.
* ``md``   - Markdown with a small header and timestamped lines.

Each format is a small function that takes a ``Transcript`` and returns a
string. ``format_transcript`` picks the right one by name.
"""

from __future__ import annotations

import json
from typing import Callable

from .models import Transcript


# ---------------------------------------------------------------------------
# Timestamp helpers
# ---------------------------------------------------------------------------

def _split_seconds(seconds: float) -> tuple[int, int, int, int]:
    """Break 3723.456 seconds into (1 hour, 2 minutes, 3 seconds, 456 ms)."""
    if seconds < 0:
        seconds = 0.0
    total_ms = int(round(seconds * 1000))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return hours, minutes, secs, ms


def timestamp_srt(seconds: float) -> str:
    """SRT style: ``00:01:02,345`` (comma before milliseconds)."""
    h, m, s, ms = _split_seconds(seconds)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def timestamp_vtt(seconds: float) -> str:
    """WebVTT style: ``00:01:02.345`` (dot before milliseconds)."""
    h, m, s, ms = _split_seconds(seconds)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def timestamp_short(seconds: float) -> str:
    """Human style: ``1:02`` or ``1:02:03`` when the video is over an hour."""
    h, m, s, _ = _split_seconds(seconds)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


# ---------------------------------------------------------------------------
# Formats
# ---------------------------------------------------------------------------

def _clean(text: str) -> str:
    """Collapse newlines inside a caption into single spaces."""
    return " ".join(text.split())


def to_text(
    transcript: Transcript,
    timestamps: bool = False,
    paragraph_gap: float = 2.0,
    paragraph_chars: int = 600,
) -> str:
    """Plain text.

    With ``timestamps=True`` every caption gets its own line prefixed by
    ``[m:ss]``. Without, the captions are joined into paragraphs: a new
    paragraph starts when there is a pause longer than ``paragraph_gap``
    seconds, or the current paragraph grows past ``paragraph_chars``.
    """
    if timestamps:
        lines = [
            f"[{timestamp_short(seg.start)}] {_clean(seg.text)}"
            for seg in transcript.segments
            if _clean(seg.text)
        ]
        return "\n".join(lines) + ("\n" if lines else "")

    paragraphs: list[str] = []
    current: list[str] = []
    current_len = 0
    last_end: float | None = None

    for seg in transcript.segments:
        text = _clean(seg.text)
        if not text:
            continue
        gap = (seg.start - last_end) if last_end is not None else 0.0
        if current and (gap > paragraph_gap or current_len > paragraph_chars):
            paragraphs.append(" ".join(current))
            current, current_len = [], 0
        current.append(text)
        current_len += len(text) + 1
        last_end = seg.end

    if current:
        paragraphs.append(" ".join(current))

    return "\n\n".join(paragraphs) + ("\n" if paragraphs else "")


def to_srt(transcript: Transcript) -> str:
    """SubRip (.srt). Each block is: number, time range, text, blank line."""
    blocks = []
    for i, seg in enumerate(transcript.segments, start=1):
        blocks.append(
            f"{i}\n{timestamp_srt(seg.start)} --> {timestamp_srt(seg.end)}\n{_clean(seg.text)}\n"
        )
    return "\n".join(blocks)


def to_vtt(transcript: Transcript) -> str:
    """WebVTT (.vtt). Like SRT but starts with a ``WEBVTT`` header."""
    blocks = ["WEBVTT\n"]
    for seg in transcript.segments:
        blocks.append(
            f"{timestamp_vtt(seg.start)} --> {timestamp_vtt(seg.end)}\n{_clean(seg.text)}\n"
        )
    return "\n".join(blocks)


def to_json(transcript: Transcript) -> str:
    """JSON with all metadata and every segment. ``indent=2`` makes it readable."""
    return json.dumps(transcript.to_dict(), indent=2, ensure_ascii=False) + "\n"


def to_markdown(transcript: Transcript) -> str:
    """Markdown: a heading, a few facts, then timestamped lines."""
    title = transcript.title or f"Transcript of {transcript.video_id}"
    kind = "auto-generated" if transcript.is_generated else "human-made"
    header = [
        f"# {title}",
        "",
        f"- **Source:** {transcript.source_url}",
        f"- **Language:** {transcript.language} (`{transcript.language_code}`, {kind})",
        f"- **Duration:** {timestamp_short(transcript.total_duration)}",
        "",
    ]
    body = [
        f"**[{timestamp_short(seg.start)}]** {_clean(seg.text)}  "
        for seg in transcript.segments
        if _clean(seg.text)
    ]
    return "\n".join(header + body) + "\n"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

# Maps a format name to (function, file extension, description).
# The command-line tool and web page both read this so adding a format is
# a one-line change here and nothing else.
FORMATS: dict[str, tuple[Callable[[Transcript], str], str, str]] = {
    "txt": (to_text, ".txt", "Plain text, in paragraphs"),
    "srt": (to_srt, ".srt", "SubRip subtitles"),
    "vtt": (to_vtt, ".vtt", "WebVTT subtitles"),
    "json": (to_json, ".json", "JSON with timestamps"),
    "md": (to_markdown, ".md", "Markdown with timestamps"),
}


def format_transcript(transcript: Transcript, fmt: str = "txt", **options) -> str:
    """Render ``transcript`` as the format called ``fmt``.

    Extra keyword options (like ``timestamps=True``) are passed through to
    the text formatter; other formats ignore them.
    """
    fmt = fmt.lower().lstrip(".")
    if fmt not in FORMATS:
        raise ValueError(f"Unknown format '{fmt}'. Choose one of: {', '.join(FORMATS)}")
    func, _, _ = FORMATS[fmt]
    if fmt == "txt":
        return func(transcript, **options)
    return func(transcript)


def extension_for(fmt: str) -> str:
    """The file extension for a format name, e.g. ``"srt"`` -> ``".srt"``."""
    return FORMATS[fmt.lower().lstrip(".")][1]
