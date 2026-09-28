"""The data shapes used everywhere else in the project.

A *dataclass* is a small Python feature that lets you describe "a thing with
these named fields" without writing lots of boilerplate. Think of it like a
row in a spreadsheet: ``Segment`` is one row, ``Transcript`` is the whole
sheet plus a few bits of information about the video.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Segment:
    """One line of subtitles.

    ``start`` and ``duration`` are in seconds. So a segment with
    ``start=61.5, duration=2.0`` was spoken from 1:01.5 to 1:03.5.
    """

    text: str
    start: float
    duration: float

    @property
    def end(self) -> float:
        """The moment this line stops being shown, in seconds."""
        return self.start + self.duration


@dataclass
class Transcript:
    """A whole transcript plus some facts about where it came from."""

    video_id: str
    source_url: str
    language: str  # human-readable, e.g. "English"
    language_code: str  # machine code, e.g. "en"
    is_generated: bool  # True = YouTube's automatic captions, False = human-made
    source: str  # "youtube-captions" or "whisper"
    segments: list[Segment] = field(default_factory=list)
    title: str | None = None

    @property
    def text(self) -> str:
        """All the spoken words joined with spaces, no timestamps."""
        return " ".join(seg.text.strip() for seg in self.segments if seg.text.strip())

    @property
    def total_duration(self) -> float:
        """How long the transcript runs, in seconds (0 if empty)."""
        if not self.segments:
            return 0.0
        return max(seg.end for seg in self.segments)

    def to_dict(self) -> dict[str, Any]:
        """Turn this object into plain dictionaries/lists (needed for JSON)."""
        return asdict(self)
