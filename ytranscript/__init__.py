"""ytranscript - turn a video link into a transcript.

This is the "front door" of the package. When another file (or the
command-line tool) writes ``from ytranscript import get_transcript``, Python
runs this file first and finds the names exported below.

The important pieces live in their own files:

* ``models.py``     - the data shapes (``Transcript`` and ``Segment``).
* ``urls.py``       - turning a pasted link into a YouTube video ID.
* ``fetch.py``      - asking YouTube for its captions.
* ``transcribe.py`` - optional fallback: download the audio and run
                      speech-to-text (Whisper) when no captions exist.
* ``formats.py``    - converting a transcript to text / SRT / VTT / JSON / MD.
* ``cli.py``        - the ``ytranscript`` terminal command.
* ``web.py``        - the small web page you can paste links into.
"""

from .models import Segment, Transcript
from .errors import TranscriptError, InvalidLinkError, NoCaptionsError
from .pipeline import get_transcript
from .formats import format_transcript, FORMATS

__all__ = [
    "Segment",
    "Transcript",
    "TranscriptError",
    "InvalidLinkError",
    "NoCaptionsError",
    "get_transcript",
    "format_transcript",
    "FORMATS",
]

__version__ = "0.1.0"
