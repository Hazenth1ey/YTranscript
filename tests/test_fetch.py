"""Tests for fetching captions, using the fake YouTube from conftest.py."""

import pytest
import requests
from youtube_transcript_api._errors import (
    AgeRestricted,
    IpBlocked,
    TranscriptsDisabled,
    VideoUnavailable,
)

from ytranscript.errors import (
    BlockedError,
    InvalidLinkError,
    NoCaptionsError,
    TranscriptError,
    VideoUnavailableError,
)
from ytranscript.fetch import fetch_youtube_transcript, list_available_languages

URL = "https://youtu.be/dQw4w9WgXcQ"


def test_fetch_prefers_manual_english(fake_api):
    t = fetch_youtube_transcript(URL, api=fake_api)
    assert t.video_id == "dQw4w9WgXcQ"
    assert t.source_url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert t.language_code == "en"
    assert t.is_generated is False
    assert t.source == "youtube-captions"
    assert [s.text for s in t.segments] == ["hello world", "second line"]
    assert t.segments[1].start == 1.0 and t.segments[1].duration == 1.5


def test_fetch_requested_language(fake_api):
    t = fetch_youtube_transcript(URL, languages=["es"], api=fake_api)
    assert t.language_code == "es"
    assert t.is_generated is True
    assert t.segments[0].text == "hola mundo"


def test_fetch_falls_back_to_whatever_exists(fake_api):
    # We ask for English but the video only has German -> we get German
    # rather than an error.
    t = fetch_youtube_transcript("onlyDeutsch", languages=["en"], api=fake_api)
    assert t.language_code == "de"
    assert t.segments[0].text == "hallo welt"


def test_fetch_translates_when_asked(fake_api):
    t = fetch_youtube_transcript("onlyDeutsch", translate_to="en", api=fake_api)
    assert t.language_code == "en"
    assert t.segments[0].text == "[en] hallo welt"


def test_fetch_does_not_translate_if_already_that_language(fake_api):
    t = fetch_youtube_transcript(URL, translate_to="en", api=fake_api)
    assert t.segments[0].text == "hello world"  # untouched


def test_fetch_video_without_any_captions(fake_api):
    with pytest.raises(NoCaptionsError):
        fetch_youtube_transcript("nothingHere", api=fake_api)


def test_fetch_rejects_bad_link(fake_api):
    with pytest.raises(InvalidLinkError):
        fetch_youtube_transcript("https://vimeo.com/1", api=fake_api)
    assert fake_api.calls == []  # never even asked YouTube


@pytest.mark.parametrize(
    "library_error, our_error, phrase",
    [
        (TranscriptsDisabled("dQw4w9WgXcQ"), NoCaptionsError, "turned off"),
        (VideoUnavailable("dQw4w9WgXcQ"), VideoUnavailableError, "unavailable"),
        (AgeRestricted("dQw4w9WgXcQ"), VideoUnavailableError, "age-restricted"),
        (IpBlocked("dQw4w9WgXcQ"), BlockedError, "blocked"),
        (requests.exceptions.ConnectionError("no route"), TranscriptError, "Could not reach YouTube"),
        (RuntimeError("boom"), Exception, "Unexpected error"),
    ],
)
def test_library_errors_become_friendly_errors(fake_api, library_error, our_error, phrase):
    fake_api.errors["dQw4w9WgXcQ"] = library_error
    with pytest.raises(our_error) as excinfo:
        fetch_youtube_transcript(URL, api=fake_api)
    assert phrase in str(excinfo.value)


def test_list_available_languages(fake_api):
    tracks = list_available_languages(URL, api=fake_api)
    assert tracks == [
        {"language": "Spanish (auto)", "language_code": "es", "is_generated": True, "is_translatable": True},
        {"language": "English", "language_code": "en", "is_generated": False, "is_translatable": True},
    ]


def test_list_available_languages_error(fake_api):
    fake_api.errors["dQw4w9WgXcQ"] = TranscriptsDisabled("dQw4w9WgXcQ")
    with pytest.raises(NoCaptionsError):
        list_available_languages(URL, api=fake_api)
