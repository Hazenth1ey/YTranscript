"""Shared test helpers.

``pytest`` automatically loads this file. Anything decorated with
``@pytest.fixture`` can be requested by a test simply by naming it as a
parameter, e.g. ``def test_something(sample_transcript): ...``.

The real ``youtube-transcript-api`` needs the internet, which tests must
never rely on. So we build a *fake* that behaves like the real library's
objects (same method names, same attributes) but returns canned data.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from youtube_transcript_api._errors import NoTranscriptFound

from ytranscript.models import Segment, Transcript


# ---------------------------------------------------------------------------
# A sample transcript used by the format and CLI tests
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_transcript() -> Transcript:
    return Transcript(
        video_id="dQw4w9WgXcQ",
        source_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        language="English",
        language_code="en",
        is_generated=False,
        source="youtube-captions",
        segments=[
            Segment("We're no strangers to love", 0.0, 2.5),
            Segment("You know the rules\nand so do I", 2.5, 3.0),
            Segment("A full commitment's what I'm thinking of", 10.0, 3.2),
        ],
    )


# ---------------------------------------------------------------------------
# A fake youtube-transcript-api
# ---------------------------------------------------------------------------

@dataclass
class FakeSnippet:
    text: str
    start: float
    duration: float


@dataclass
class FakeFetched:
    """Mimics ``FetchedTranscript``: iterable of snippets + metadata."""

    snippets: list[FakeSnippet]
    language: str
    language_code: str
    is_generated: bool

    def __iter__(self):
        return iter(self.snippets)


@dataclass
class FakeTrack:
    """Mimics one ``Transcript`` entry inside a ``TranscriptList``."""

    language: str
    language_code: str
    is_generated: bool
    is_translatable: bool = True
    snippets: list[FakeSnippet] = field(default_factory=list)
    translated_to: list[str] = field(default_factory=list)

    def fetch(self) -> FakeFetched:
        return FakeFetched(self.snippets, self.language, self.language_code, self.is_generated)

    def translate(self, code: str) -> "FakeTrack":
        self.translated_to.append(code)
        return FakeTrack(
            language=f"Translated({code})",
            language_code=code,
            is_generated=self.is_generated,
            snippets=[FakeSnippet(f"[{code}] {s.text}", s.start, s.duration) for s in self.snippets],
        )


class FakeTranscriptList:
    """Mimics ``TranscriptList``: iterable + ``find_transcript``."""

    def __init__(self, video_id: str, tracks: list[FakeTrack]):
        self.video_id = video_id
        self.tracks = tracks

    def __iter__(self):
        return iter(self.tracks)

    def find_transcript(self, language_codes):
        # Same rule as the real library: manual tracks first, then generated.
        for generated in (False, True):
            for code in language_codes:
                for t in self.tracks:
                    if t.language_code == code and t.is_generated == generated:
                        return t
        raise NoTranscriptFound(self.video_id, list(language_codes), self)


class FakeApi:
    """Mimics ``YouTubeTranscriptApi``. ``tracks`` maps video_id -> tracks,
    ``errors`` maps video_id -> exception to raise instead."""

    def __init__(self, tracks: dict[str, list[FakeTrack]] | None = None, errors: dict | None = None):
        self.tracks = tracks or {}
        self.errors = errors or {}
        self.calls: list[str] = []

    def list(self, video_id: str) -> FakeTranscriptList:
        self.calls.append(video_id)
        if video_id in self.errors:
            raise self.errors[video_id]
        return FakeTranscriptList(video_id, self.tracks.get(video_id, []))


@pytest.fixture
def english_snippets() -> list[FakeSnippet]:
    return [
        FakeSnippet("hello world", 0.0, 1.0),
        FakeSnippet("second line", 1.0, 1.5),
    ]


@pytest.fixture
def fake_api(english_snippets) -> FakeApi:
    """A fake YouTube with one video that has manual English + auto Spanish."""
    return FakeApi(
        tracks={
            "dQw4w9WgXcQ": [
                FakeTrack("Spanish (auto)", "es", is_generated=True,
                          snippets=[FakeSnippet("hola mundo", 0.0, 1.0)]),
                FakeTrack("English", "en", is_generated=False, snippets=english_snippets),
            ],
            "onlyDeutsch": [
                FakeTrack("German", "de", is_generated=False,
                          snippets=[FakeSnippet("hallo welt", 0.0, 1.0)]),
            ],
            "nothingHere": [],
        }
    )
