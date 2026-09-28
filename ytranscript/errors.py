"""The errors this project can raise.

In Python, an *exception* is how a function says "I could not do what you
asked". We define our own exception types so the command-line tool and the
web page can catch them and show a friendly message instead of a scary
stack trace.

All of our errors inherit from ``TranscriptError``, so code that wants to
catch "anything that went wrong while making a transcript" only needs
``except TranscriptError:``.
"""


class TranscriptError(Exception):
    """Base class: something went wrong while producing a transcript."""


class InvalidLinkError(TranscriptError):
    """The text you gave us does not look like a video link we understand."""


class NoCaptionsError(TranscriptError):
    """The video exists, but YouTube has no captions for it (in any language,
    or in the languages you asked for)."""


class VideoUnavailableError(TranscriptError):
    """The video is private, deleted, region-locked, age-restricted, ..."""


class BlockedError(TranscriptError):
    """YouTube refused to talk to us (rate-limited or IP blocked)."""


class WhisperNotInstalledError(TranscriptError):
    """The optional speech-to-text dependencies are not installed."""
