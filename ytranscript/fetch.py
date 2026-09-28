"""Ask YouTube for a video's captions.

YouTube stores captions ("subtitles") for most videos. Some are written by
the uploader (accurate), others are made automatically by YouTube's speech
recognition (usually fine, occasionally funny). This file downloads them
using the ``youtube-transcript-api`` library and converts the result into
our own ``Transcript`` object so the rest of the program does not need to
know anything about that library.

Why the indirection? If that library changes (or we swap it for another),
only this file needs updating.
"""

from __future__ import annotations

from typing import Iterable, Any

import requests
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    AgeRestricted,
    CouldNotRetrieveTranscript,
    InvalidVideoId,
    IpBlocked,
    NoTranscriptFound,
    NotTranslatable,
    RequestBlocked,
    TranscriptsDisabled,
    TranslationLanguageNotAvailable,
    VideoUnavailable,
    VideoUnplayable,
)

from . import config
from .errors import (
    BlockedError,
    NoCaptionsError,
    TranscriptError,
    VideoUnavailableError,
)
from .models import Segment, Transcript
from .urls import canonical_url, extract_video_id

# The language we try when the caller doesn't say. A *tuple* of language
# codes, tried in order; "en" first, then anything else available.
DEFAULT_LANGUAGES: tuple[str, ...] = ("en",)


def default_api() -> YouTubeTranscriptApi:
    """Build the YouTube client, routed through a proxy if one is configured."""
    return YouTubeTranscriptApi(proxy_config=config.build_proxy_config())


def _friendly_error(video_id: str, exc: Exception) -> TranscriptError:
    """Translate the library's exceptions into our own, with plain messages.

    We don't want a beginner (or a web page) to see raw library errors, so
    each known failure gets a sentence a human can act on.
    """
    if isinstance(exc, TranscriptsDisabled):
        return NoCaptionsError(
            f"Captions are turned off for video {video_id}. "
            "Try the Whisper fallback (--whisper) to transcribe the audio instead."
        )
    if isinstance(exc, NoTranscriptFound):
        return NoCaptionsError(
            f"Video {video_id} has captions, but none in the language(s) you asked for. "
            "Run with --list-languages to see what is available, or use --translate-to."
        )
    if isinstance(exc, AgeRestricted):
        return VideoUnavailableError(
            f"Video {video_id} is age-restricted, so captions can't be fetched without logging in."
        )
    if isinstance(exc, (VideoUnavailable, VideoUnplayable, InvalidVideoId)):
        return VideoUnavailableError(
            f"Video {video_id} is unavailable (private, deleted, region-locked, or the ID is wrong)."
        )
    if isinstance(exc, (IpBlocked, RequestBlocked)):
        return BlockedError(
            "YouTube blocked the request. This usually happens on cloud servers or after "
            "many requests in a row. Try again later, from a normal home connection, or "
            "configure a proxy."
        )
    if isinstance(exc, (NotTranslatable, TranslationLanguageNotAvailable)):
        return NoCaptionsError(
            f"Video {video_id}'s captions cannot be translated to the language you asked for."
        )
    if isinstance(exc, CouldNotRetrieveTranscript):
        return TranscriptError(f"Could not fetch captions for video {video_id}: {exc}")
    if isinstance(exc, requests.exceptions.RequestException):
        return TranscriptError(
            "Could not reach YouTube. Check your internet connection, VPN, proxy or firewall "
            f"and try again. (Details: {exc.__class__.__name__})"
        )
    return TranscriptError(f"Unexpected error while fetching video {video_id}: {exc}")


def list_available_languages(url: str, api: YouTubeTranscriptApi | None = None) -> list[dict[str, Any]]:
    """Return every caption track YouTube offers for the video.

    Each entry looks like::

        {"language": "English", "language_code": "en",
         "is_generated": False, "is_translatable": True}
    """
    video_id = extract_video_id(url)
    api = api or default_api()
    try:
        transcript_list = api.list(video_id)
    except Exception as exc:  # noqa: BLE001 - we convert *everything* to our errors
        raise _friendly_error(video_id, exc) from exc

    return [
        {
            "language": t.language,
            "language_code": t.language_code,
            "is_generated": t.is_generated,
            "is_translatable": t.is_translatable,
        }
        for t in transcript_list
    ]


def fetch_youtube_transcript(
    url: str,
    languages: Iterable[str] = DEFAULT_LANGUAGES,
    translate_to: str | None = None,
    api: YouTubeTranscriptApi | None = None,
) -> Transcript:
    """Download the captions for ``url`` and return a ``Transcript``.

    Parameters
    ----------
    url:
        Any YouTube link shape, or a bare video ID.
    languages:
        Language codes to try, in order of preference (e.g. ``["en", "es"]``).
        Human-made captions are preferred over auto-generated ones.
        If none of these exist, we fall back to *whatever* the video has,
        so you still get something rather than an error.
    translate_to:
        If given (e.g. ``"en"``), ask YouTube to machine-translate the captions
        into that language.
    api:
        Only used by the tests, so they can hand in a fake YouTube.
    """
    video_id = extract_video_id(url)
    languages = list(languages) or list(DEFAULT_LANGUAGES)
    api = api or default_api()

    try:
        transcript_list = api.list(video_id)

        try:
            # ``find_transcript`` looks for a human-made track first, then an
            # automatic one, in the order of ``languages``.
            chosen = transcript_list.find_transcript(languages)
        except NoTranscriptFound:
            # Nothing in the requested languages. Rather than fail, take the
            # first track the video has at all (again preferring human-made).
            all_tracks = list(transcript_list)
            if not all_tracks:
                raise
            manual = [t for t in all_tracks if not t.is_generated]
            chosen = manual[0] if manual else all_tracks[0]

        if translate_to and chosen.language_code != translate_to:
            chosen = chosen.translate(translate_to)

        fetched = chosen.fetch()
    except TranscriptError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _friendly_error(video_id, exc) from exc

    segments = [
        Segment(text=snippet.text, start=float(snippet.start), duration=float(snippet.duration))
        for snippet in fetched
    ]

    return Transcript(
        video_id=video_id,
        source_url=canonical_url(video_id),
        language=fetched.language,
        language_code=fetched.language_code,
        is_generated=fetched.is_generated,
        source="youtube-captions",
        segments=segments,
    )
