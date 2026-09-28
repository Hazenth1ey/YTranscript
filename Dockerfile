# A Dockerfile is a recipe for building a "container image": a self-contained
# copy of the app plus everything it needs to run. Almost every hosting
# platform (Render, Railway, Fly.io, Google Cloud Run, a plain VPS...) can
# run one of these.

# Start from an official small Linux image that already has Python 3.12.
FROM python:3.12-slim

# Don't buffer output, so log lines show up in the hosting dashboard immediately.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # Whisper needs more CPU/RAM than typical hosting tiers provide, and its
    # libraries would triple the image size, so the hosted version is captions-only.
    YTRANSCRIPT_ENABLE_WHISPER=0

WORKDIR /app

# Copy only the files needed to install dependencies first. Docker caches each
# step, so if only the code changes later, this slow step is skipped.
COPY pyproject.toml README.md ./
COPY ytranscript ./ytranscript
RUN pip install --no-cache-dir .

# Hosting platforms tell us which port to listen on via $PORT (default 8000).
EXPOSE 8000

# gunicorn is a production-grade web server. "ytranscript.web:app" points it
# at the Flask app object. Two worker processes handle requests in parallel;
# the 120 s timeout leaves room for slow caption fetches.
CMD ["sh", "-c", "gunicorn ytranscript.web:app --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 120"]
