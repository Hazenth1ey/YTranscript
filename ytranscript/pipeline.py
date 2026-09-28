"""The decision-maker: given a link, which method produces the transcript?

Rules, in order:

1. YouTube link and the caller didn't force Whisper -> fetch YouTube captions.
2. That failed because there are no captions, and the fallback is allowed
   -> transcribe the audio with Whisper.
3. Not a YouTube link -> Whisper is the only option.

Everything else (bad link, blocked, video private) is raised as a
``TranscriptError`` for the caller to display.
"""

from __future__ import annotations

from typing import Callable, Iterable

from .errors import NoCaptionsError, InvalidLinkError
from .fetch import DEFAULT_LANGUAGES, fetch_youtube_transcript
from .models import Transcript
from .urls import is_youtube_url


def get_transcript(
    url: str,
    languages: Iterable[str] = DEFAULT_LANGUAGES,
    translate_to: str | None = None,
    use_whisper: bool = False,
    whisper_fallback: bool = False,
    whisper_model: str = "base",
    whisper_language: str | None = None,
    progress: Callable[[str], None] | None = None,
) -> Transcript:
    """Return a ``Transcript`` for ``url`` using the best available method.

    ``use_whisper=True`` skips captions entirely and always transcribes the
    audio. ``whisper_fallback=True`` tries captions first and only runs
    Whisper if the video has none. ``whisper_language`` forces Whisper to a
    language (``None`` = auto-detect, which is usually best). ``progress`` is
    an optional function that receives short status messages (the CLI prints
    them to the terminal).
    """
    log = progress or (lambda _msg: None)

    if not url or not url.strip():
        raise InvalidLinkError("Please paste a video link.")

    youtube = is_youtube_url(url)

    if youtube and not use_whisper:
        log("Fetching YouTube captions...")
        try:
            return fetch_youtube_transcript(url, languages=languages, translate_to=translate_to)
        except NoCaptionsError:
            if not whisper_fallback:
                raise
            log("No captions found; falling back to Whisper speech-to-text.")

    elif not youtube and not (use_whisper or whisper_fallback):
        raise InvalidLinkError(
            f"'{url}' is not a YouTube link. Non-YouTube videos need Whisper speech-to-text: "
            "turn on the Whisper option (--whisper on the command line) and make sure the "
            "optional dependencies are installed."
        )

    # Import lazily so the core package works even without the optional deps.
    from .transcribe import transcribe_with_whisper

    return transcribe_with_whisper(
        url,
        model_size=whisper_model,
        language=whisper_language,
        progress=log,
    )
