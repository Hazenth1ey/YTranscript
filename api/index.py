"""Entry point for Vercel.

Vercel runs Python as "serverless functions": every file inside the ``api/``
folder becomes one, started on demand when a request comes in. For a web
framework like Flask, Vercel looks for a variable called ``app`` in the file
and hands each request to it. ``vercel.json`` routes *all* addresses to this
file, so the whole site (the form, /download, /health, /api/transcript) is
served by the one Flask app.

Whisper is switched off here: a serverless function has a short time limit
and no room for a speech-recognition model, so the hosted version serves
YouTube captions only.
"""

import os

# ``setdefault`` only sets the value if it isn't already set, so a value
# entered in the Vercel dashboard still wins.
os.environ.setdefault("YTRANSCRIPT_ENABLE_WHISPER", "0")

from ytranscript.web import app  # noqa: E402  (import after the setting on purpose)

__all__ = ["app"]
