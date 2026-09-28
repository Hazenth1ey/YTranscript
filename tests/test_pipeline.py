"""Tests for the decision logic in pipeline.py.

We use ``monkeypatch`` (a pytest tool) to swap the real fetch/transcribe
functions for tiny fakes, then check that ``get_transcript`` calls the right
one under each set of options.
"""

import pytest

from ytranscript import pipeline
from ytranscript.errors import InvalidLinkError, NoCaptionsError
from ytranscript.models import Segment, Transcript

YT = "https://youtu.be/dQw4w9WgXcQ"
VIMEO = "https://vimeo.com/123456"


def _transcript(source: str) -> Transcript:
    return Transcript("id", "url", "English", "en", True, source, [Segment("hi", 0, 1)])


@pytest.fixture
def fakes(monkeypatch):
    """Replace the real fetchers with recorders. Returns the call log."""
    calls = []

    def fake_fetch(url, languages, translate_to):
        calls.append(("captions", url, list(languages), translate_to))
        if "nocaptions" in url:
            raise NoCaptionsError("none")
        return _transcript("youtube-captions")

    def fake_whisper(url, model_size, language, progress):
        calls.append(("whisper", url, model_size, language))
        return _transcript(f"whisper-{model_size}")

    monkeypatch.setattr(pipeline, "fetch_youtube_transcript", fake_fetch)
    # transcribe_with_whisper is imported *inside* the function, so patch the module it comes from.
    import ytranscript.transcribe as transcribe_module
    monkeypatch.setattr(transcribe_module, "transcribe_with_whisper", fake_whisper)
    return calls


def test_youtube_uses_captions_by_default(fakes):
    t = pipeline.get_transcript(YT, languages=["en", "fr"], translate_to="de")
    assert t.source == "youtube-captions"
    assert fakes == [("captions", YT, ["en", "fr"], "de")]


def test_youtube_no_captions_without_fallback_raises(fakes):
    with pytest.raises(NoCaptionsError):
        pipeline.get_transcript("https://www.youtube.com/watch?v=nocaptions1")


def test_youtube_no_captions_with_fallback_uses_whisper(fakes):
    url = "https://www.youtube.com/watch?v=nocaptions1"
    t = pipeline.get_transcript(url, whisper_fallback=True, whisper_model="small")
    assert t.source == "whisper-small"
    assert [c[0] for c in fakes] == ["captions", "whisper"]


def test_use_whisper_skips_captions(fakes):
    t = pipeline.get_transcript(YT, use_whisper=True, whisper_language="en")
    assert t.source == "whisper-base"
    assert fakes == [("whisper", YT, "base", "en")]


def test_non_youtube_requires_whisper(fakes):
    with pytest.raises(InvalidLinkError, match="not a YouTube link"):
        pipeline.get_transcript(VIMEO)
    assert fakes == []


def test_non_youtube_with_whisper(fakes):
    t = pipeline.get_transcript(VIMEO, use_whisper=True)
    assert t.source == "whisper-base"


def test_non_youtube_with_fallback_flag_also_works(fakes):
    t = pipeline.get_transcript(VIMEO, whisper_fallback=True)
    assert t.source == "whisper-base"
    assert fakes[0][0] == "whisper"


def test_empty_url(fakes):
    with pytest.raises(InvalidLinkError):
        pipeline.get_transcript("   ")


def test_progress_messages(fakes):
    messages = []
    pipeline.get_transcript("https://www.youtube.com/watch?v=nocaptions1", whisper_fallback=True, progress=messages.append)
    assert messages[0] == "Fetching YouTube captions..."
    assert "falling back to Whisper" in messages[1]
