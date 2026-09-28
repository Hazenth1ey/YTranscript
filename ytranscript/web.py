"""A tiny web page for people who prefer clicking to typing commands.

Run it with::

    ytranscript-web            (after ``pip install -e .``)
    python -m ytranscript.web  (works without installing the command)

then open http://127.0.0.1:5000 in your browser, paste a link, press
"Get transcript". You can read the result on the page or download it.

How it works: Flask is a small library that listens for browser requests.
Each ``@app.route(...)`` line below says "when the browser asks for this
address, run this function". ``GET /`` shows the form, ``POST /`` (what
the form sends when you click the button) fetches the transcript, and
``/download`` sends the same thing back as a file.

The page is deliberately plain HTML + a little CSS, no JavaScript framework,
so you can read the whole thing in one sitting.
"""

from __future__ import annotations

from flask import Flask, Response, jsonify, render_template_string, request

from . import __version__, config
from .errors import TranscriptError
from .formats import FORMATS, extension_for, format_transcript
from .pipeline import get_transcript
from .transcribe import DEFAULT_WHISPER_MODEL, WHISPER_MODELS

app = Flask(__name__)

# Jinja2 template: the {{ ... }} and {% ... %} bits are filled in by Python.
PAGE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>YTranscript</title>
<style>
  :root { --bg:#f7f7f8; --card:#fff; --ink:#1c1c1e; --muted:#6b6b70; --accent:#c4302b; --line:#e4e4e7; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#141416; --card:#1e1e21; --ink:#f2f2f2; --muted:#a0a0a6; --line:#2c2c30; }
  }
  * { box-sizing: border-box; }
  body { margin:0; padding:24px 16px; background:var(--bg); color:var(--ink);
         font: 16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
  main { max-width: 820px; margin: 0 auto; }
  h1 { font-size: 1.6rem; margin: 0 0 4px; }
  .sub { color: var(--muted); margin: 0 0 20px; }
  form, .result { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 20px; }
  label { display:block; font-weight:600; margin: 12px 0 4px; }
  input[type=text], select { width:100%; padding:10px 12px; font-size:1rem; border:1px solid var(--line);
         border-radius:8px; background:var(--bg); color:var(--ink); }
  .row { display:grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  @media (max-width: 560px) { .row { grid-template-columns: 1fr; } }
  .check { display:flex; align-items:center; gap:8px; margin-top:14px; font-weight:400; }
  button, a.btn { display:inline-block; margin-top:18px; padding:10px 18px; font-size:1rem; border:0;
         border-radius:8px; background:var(--accent); color:#fff; cursor:pointer; text-decoration:none; }
  .error { margin: 18px 0 0; padding: 12px 14px; border-radius: 8px; background: #fde8e7; color: #7a1f1a; }
  @media (prefers-color-scheme: dark) { .error { background:#3a1d1b; color:#ffb4ae; } }
  .result { margin-top: 20px; }
  .meta { color: var(--muted); font-size: .9rem; margin: 0 0 12px; }
  pre { white-space: pre-wrap; word-wrap: break-word; margin:0; max-height: 60vh; overflow:auto;
        padding: 12px; background: var(--bg); border-radius: 8px; font-size: .92rem; }
  .small { color: var(--muted); font-size: .85rem; }
</style>
</head>
<body>
<main>
  <h1>YTranscript</h1>
  <p class="sub">Paste a video link, get the transcript.</p>

  <form method="post" action="/">
    <label for="url">Video link</label>
    <input type="text" id="url" name="url" placeholder="https://www.youtube.com/watch?v=..." value="{{ url }}" required autofocus>

    <div class="row">
      <div>
        <label for="format">Format</label>
        <select id="format" name="format">
          {% for name, (_, _, desc) in formats.items() %}
            <option value="{{ name }}" {% if name == fmt %}selected{% endif %}>{{ name }} &middot; {{ desc }}</option>
          {% endfor %}
        </select>
      </div>
      <div>
        <label for="languages">Preferred languages <span class="small">(codes, comma-separated)</span></label>
        <input type="text" id="languages" name="languages" value="{{ languages }}" placeholder="en">
      </div>
    </div>

    <div class="row">
      <div>
        <label for="translate_to">Translate to <span class="small">(optional, e.g. en)</span></label>
        <input type="text" id="translate_to" name="translate_to" value="{{ translate_to }}" placeholder="leave empty to keep original">
      </div>
      {% if whisper_enabled %}
      <div>
        <label for="whisper_model">Whisper model <span class="small">(only if used)</span></label>
        <select id="whisper_model" name="whisper_model">
          {% for m in whisper_models %}
            <option value="{{ m }}" {% if m == whisper_model %}selected{% endif %}>{{ m }}</option>
          {% endfor %}
        </select>
      </div>
      {% endif %}
    </div>

    <label class="check"><input type="checkbox" name="timestamps" {% if timestamps %}checked{% endif %}> Add timestamps to plain text</label>
    {% if whisper_enabled %}
    <label class="check"><input type="checkbox" name="whisper_fallback" {% if whisper_fallback %}checked{% endif %}> If there are no captions, transcribe the audio with Whisper (slow)</label>
    <label class="check"><input type="checkbox" name="whisper" {% if whisper %}checked{% endif %}> Always use Whisper (needed for non-YouTube links)</label>
    {% else %}
    <p class="small">This hosted version fetches YouTube captions only. Speech-to-text for videos without captions is available when running the tool on your own computer.</p>
    {% endif %}

    <button type="submit">Get transcript</button>
  </form>

  {% if error %}
    <div class="error">{{ error }}</div>
  {% endif %}

  {% if rendered is not none %}
    <section class="result">
      <p class="meta">
        {{ transcript.language }} ({{ transcript.language_code }}),
        {{ "auto-generated" if transcript.is_generated else "human-made" }},
        {{ transcript.segments | length }} lines, source: {{ transcript.source }}
        &middot; <a href="{{ transcript.source_url }}" target="_blank" rel="noopener">open video</a>
      </p>
      <pre>{{ rendered }}</pre>
      <a class="btn" href="/download?{{ query }}">Download .{{ fmt }}</a>
    </section>
  {% endif %}
</main>
</body>
</html>
"""


def _form_values(source) -> dict:
    """Read the form fields (or query-string) into a plain dictionary."""
    languages = source.get("languages", "en") or "en"
    # When Whisper is switched off for this deployment, ignore any request
    # for it, even a hand-crafted one, so the server never tries to run it.
    whisper_ok = config.whisper_enabled()
    return {
        "url": (source.get("url") or "").strip(),
        "fmt": source.get("format", "txt") if source.get("format") in FORMATS else "txt",
        "languages": languages,
        "translate_to": (source.get("translate_to") or "").strip() or None,
        "timestamps": bool(source.get("timestamps")),
        "whisper": whisper_ok and bool(source.get("whisper")),
        "whisper_fallback": whisper_ok and bool(source.get("whisper_fallback")),
        "whisper_model": source.get("whisper_model") if source.get("whisper_model") in WHISPER_MODELS else DEFAULT_WHISPER_MODEL,
    }


def _run(values: dict):
    """Fetch and render according to the form values. Returns (transcript, rendered_text)."""
    language_list = [c.strip() for c in values["languages"].split(",") if c.strip()]
    transcript = get_transcript(
        values["url"],
        languages=language_list,
        translate_to=values["translate_to"],
        use_whisper=values["whisper"],
        whisper_fallback=values["whisper_fallback"],
        whisper_model=values["whisper_model"],
    )
    rendered = format_transcript(transcript, values["fmt"], timestamps=values["timestamps"])
    return transcript, rendered


def _render(values: dict, error: str | None = None, transcript=None, rendered: str | None = None):
    from urllib.parse import urlencode

    query = urlencode({
        "url": values["url"],
        "format": values["fmt"],
        "languages": values["languages"],
        "translate_to": values["translate_to"] or "",
        "timestamps": "1" if values["timestamps"] else "",
        "whisper": "1" if values["whisper"] else "",
        "whisper_fallback": "1" if values["whisper_fallback"] else "",
        "whisper_model": values["whisper_model"],
    })
    return render_template_string(
        PAGE,
        formats=FORMATS,
        whisper_models=WHISPER_MODELS,
        whisper_enabled=config.whisper_enabled(),
        error=error,
        transcript=transcript,
        rendered=rendered,
        query=query,
        **values,
    )


@app.route("/", methods=["GET", "POST"])
def index():
    """Show the form; on POST also fetch and display the transcript."""
    if request.method == "GET":
        return _render(_form_values(request.args))

    values = _form_values(request.form)
    try:
        transcript, rendered = _run(values)
    except TranscriptError as exc:
        return _render(values, error=str(exc)), 400
    return _render(values, transcript=transcript, rendered=rendered)


@app.route("/download")
def download():
    """Same as POST /, but returns the transcript as a downloadable file."""
    values = _form_values(request.args)
    try:
        transcript, rendered = _run(values)
    except TranscriptError as exc:
        return Response(f"Error: {exc}\n", status=400, mimetype="text/plain")

    # Keep only letters, digits, "-" and "_" so the file name is safe on every OS.
    safe_id = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in transcript.video_id) or "transcript"
    filename = f"{safe_id}{extension_for(values['fmt'])}"
    return Response(
        rendered,
        content_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.route("/health")
def health():
    """Tiny status page. Hosting platforms poll this to check the app is alive."""
    return jsonify({"status": "ok", "version": __version__, **config.describe()})


@app.route("/api/transcript")
def api_transcript():
    """A machine-friendly endpoint, e.g. for scripts or other apps.

    ``GET /api/transcript?url=<link>&format=json`` returns the transcript as
    JSON (the default). Any other format returns that format as plain text.
    Errors come back as JSON with an HTTP 400 status.
    """
    source = request.args.to_dict()
    source.setdefault("format", "json")
    values = _form_values(source)
    try:
        transcript, rendered = _run(values)
    except TranscriptError as exc:
        return jsonify({"error": str(exc)}), 400

    if values["fmt"] == "json":
        return Response(rendered, content_type="application/json; charset=utf-8")
    return Response(rendered, content_type="text/plain; charset=utf-8")


def main() -> None:
    """Start the built-in development server (the ``ytranscript-web`` command).

    This is fine on your own computer. On a real host use gunicorn instead
    (see the Dockerfile and Procfile), which is built for many users at once.
    """
    host, port = config.host(), config.port()
    print(f"YTranscript web UI running at http://{host}:{port}  (press Ctrl+C to stop)")
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
