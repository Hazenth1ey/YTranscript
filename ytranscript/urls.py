"""Turn a pasted link into a YouTube video ID.

YouTube links come in many shapes, but they all contain the same thing: an
11-character *video ID* such as ``dQw4w9WgXcQ``. Examples::

    https://www.youtube.com/watch?v=dQw4w9WgXcQ
    https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s&list=PL123
    https://youtu.be/dQw4w9WgXcQ?si=abc
    https://www.youtube.com/shorts/dQw4w9WgXcQ
    https://www.youtube.com/embed/dQw4w9WgXcQ
    https://www.youtube.com/live/dQw4w9WgXcQ
    https://m.youtube.com/watch?v=dQw4w9WgXcQ
    https://music.youtube.com/watch?v=dQw4w9WgXcQ
    youtube.com/watch?v=dQw4w9WgXcQ          (no "https://")
    dQw4w9WgXcQ                               (just the ID)

The caption library only wants the ID, so this file extracts it.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse, parse_qs

from .errors import InvalidLinkError

# A YouTube video ID is exactly 11 characters from this alphabet.
# ``re`` is Python's "regular expression" module - a mini-language for
# describing text patterns. ``^...$`` means "the whole string must match".
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

# Host names that we treat as "this is YouTube".
_YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
    "youtu.be",
}

# Path prefixes where the ID is the next path segment,
# e.g. /shorts/<ID>, /embed/<ID>, /live/<ID>, /v/<ID>.
_PATH_PREFIXES = ("shorts", "embed", "live", "v", "e")


def is_video_id(text: str) -> bool:
    """True if ``text`` is a bare 11-character YouTube video ID."""
    return bool(_VIDEO_ID_RE.match(text.strip()))


def _normalise(url: str) -> str:
    """Add ``https://`` if the user pasted a link without it.

    ``urlparse`` (used below) only recognises the host name when the link
    starts with a scheme like ``https://``. Without this step,
    ``youtube.com/watch?v=...`` would be read as a *path*, not a host.
    """
    url = url.strip()
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url):
        url = "https://" + url
    return url


def is_youtube_url(url: str) -> bool:
    """True if the link points at YouTube (or is a bare video ID)."""
    if is_video_id(url):
        return True
    try:
        host = (urlparse(_normalise(url)).hostname or "").lower()
    except ValueError:
        return False
    return host in _YOUTUBE_HOSTS


def extract_video_id(url: str) -> str:
    """Return the 11-character video ID hidden inside ``url``.

    Raises ``InvalidLinkError`` with a helpful message if we can't find one.
    """
    if not url or not url.strip():
        raise InvalidLinkError("Please paste a video link.")

    raw = url.strip()

    # Case 1: the user pasted just the ID.
    if is_video_id(raw):
        return raw

    parsed = urlparse(_normalise(raw))
    host = (parsed.hostname or "").lower()

    if host not in _YOUTUBE_HOSTS:
        raise InvalidLinkError(
            f"'{raw}' is not a YouTube link. "
            "Supported shapes: youtube.com/watch?v=..., youtu.be/..., "
            "youtube.com/shorts/..., or a bare 11-character video ID."
        )

    # Split the path "/shorts/abc123" into ["shorts", "abc123"].
    # ``filter(None, ...)`` drops the empty strings produced by leading/trailing "/".
    parts = [p for p in parsed.path.split("/") if p]

    candidate: str | None = None

    if host == "youtu.be":
        # Short links: https://youtu.be/<ID>
        candidate = parts[0] if parts else None
    elif parts and parts[0] in _PATH_PREFIXES and len(parts) >= 2:
        # https://www.youtube.com/shorts/<ID>, /embed/<ID>, /live/<ID>, ...
        candidate = parts[1]
    else:
        # The classic form: https://www.youtube.com/watch?v=<ID>&t=...
        # ``parse_qs`` turns "v=abc&t=42" into {"v": ["abc"], "t": ["42"]}.
        query = parse_qs(parsed.query)
        values = query.get("v")
        candidate = values[0] if values else None

    if candidate and is_video_id(candidate):
        return candidate

    raise InvalidLinkError(
        f"Could not find a video ID in '{raw}'. "
        "Make sure the link points at a single video (not a channel or playlist)."
    )


def canonical_url(video_id: str) -> str:
    """The standard 'watch' link for a video ID (handy for output files)."""
    return f"https://www.youtube.com/watch?v={video_id}"
