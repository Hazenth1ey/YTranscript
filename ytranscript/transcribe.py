"""Optional fallback: download the audio and run speech-to-text.

Not every video has captions, and not every video is on YouTube. For those
cases this file:

1. uses ``yt-dlp`` (a downloader that understands thousands of video sites)
   to save just the audio track to a temporary folder, and
2. runs ``faster-whisper``, an open-source speech-recognition model from
   OpenAI's Whisper family, over that audio.

Both libraries are *optional*: install them with ``pip install -e ".[whisper]"``.
If they're missing we raise ``WhisperNotInstalledError`` with instructions,
so the rest of the program keeps working without them.

Heads-up: the first run downloads the model (roughly 150 MB for "base",
1.5 GB for "large-v3") and transcribing takes real CPU time, roughly the
length of the video for the small models on a laptop.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Callable

from .errors import TranscriptError, WhisperNotInstalledError
from .models import Segment, Transcript
from .urls import canonical_url, extract_video_id, is_youtube_url

# Model sizes offered by faster-whisper, smallest/fastest first.
WHISPER_MODELS = ("tiny", "base", "small", "medium", "large-v3")
DEFAULT_WHISPER_MODEL = "base"

_INSTALL_HINT = (
    "The Whisper fallback needs extra packages. Install them with:\n"
    '    pip install -e ".[whisper]"\n'
    "(or: pip install yt-dlp faster-whisper)"
)


def _import_yt_dlp():
    try:
        import yt_dlp  # noqa: WPS433 - imported lazily on purpose
    except ImportError as exc:
        raise WhisperNotInstalledError(_INSTALL_HINT) from exc
    return yt_dlp


def _import_whisper():
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise WhisperNotInstalledError(_INSTALL_HINT) from exc
    return WhisperModel


def download_audio(url: str, target_dir: Path, progress: Callable[[str], None] | None = None) -> tuple[Path, dict]:
    """Download only the audio of ``url`` into ``target_dir``.

    Returns the path of the audio file and the metadata yt-dlp collected
    (title, duration, ...). We deliberately don't convert the audio, so
    ``ffmpeg`` is *not* required: faster-whisper can read the raw m4a/webm.
    """
    yt_dlp = _import_yt_dlp()
    log = progress or (lambda _msg: None)

    options = {
        "format": "bestaudio/best",  # smallest download that still has the speech
        "outtmpl": str(target_dir / "audio.%(ext)s"),
        "noplaylist": True,  # if the link is inside a playlist, only take this video
        "quiet": True,
        "no_warnings": True,
    }

    log("Downloading audio...")
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
    except Exception as exc:  # noqa: BLE001
        raise TranscriptError(f"Could not download audio from {url}: {exc}") from exc

    files = [p for p in target_dir.iterdir() if p.name.startswith("audio.")]
    if not files:
        raise TranscriptError(f"yt-dlp finished but no audio file was found for {url}.")
    return files[0], info or {}


def transcribe_audio_file(
    audio_path: Path,
    model_size: str = DEFAULT_WHISPER_MODEL,
    language: str | None = None,
    progress: Callable[[str], None] | None = None,
) -> tuple[list[Segment], str]:
    """Run Whisper on a local audio file.

    Returns the list of segments and the language code Whisper detected.
    ``language=None`` lets Whisper auto-detect; pass ``"en"`` etc. to force it.
    """
    WhisperModel = _import_whisper()
    log = progress or (lambda _msg: None)

    log(f"Loading Whisper model '{model_size}' (downloads on first use)...")
    try:
        # ``int8`` uses less memory and is plenty accurate for speech on a CPU.
        model = WhisperModel(model_size, device="auto", compute_type="int8")
    except Exception as exc:  # noqa: BLE001
        raise TranscriptError(
            f"Could not load the Whisper model '{model_size}'. The first run downloads it from "
            "huggingface.co, so check your internet connection, VPN, proxy or firewall. "
            f"(Details: {exc.__class__.__name__}: {exc})"
        ) from exc

    log("Transcribing... this can take a while.")
    try:
        raw_segments, info = model.transcribe(
            str(audio_path),
            language=language,
            vad_filter=True,  # skip long silences; faster and fewer hallucinated words
        )
        # ``model.transcribe`` returns a *generator*: nothing is actually
        # transcribed until we loop over it, so the loop below is where the
        # time goes and where audio-decoding errors would surface.
        raw_segments = list(raw_segments)
    except Exception as exc:  # noqa: BLE001
        raise TranscriptError(f"Whisper could not transcribe the audio: {exc}") from exc

    segments = [
        Segment(text=s.text.strip(), start=float(s.start), duration=float(s.end - s.start))
        for s in raw_segments
        if s.text.strip()
    ]
    return segments, info.language


def transcribe_with_whisper(
    url: str,
    model_size: str = DEFAULT_WHISPER_MODEL,
    language: str | None = None,
    progress: Callable[[str], None] | None = None,
) -> Transcript:
    """Download ``url``'s audio and transcribe it. Works for any yt-dlp site."""
    if model_size not in WHISPER_MODELS:
        raise ValueError(f"Unknown Whisper model '{model_size}'. Choose one of: {', '.join(WHISPER_MODELS)}")

    # A temporary folder that is deleted automatically when we're done,
    # even if something goes wrong halfway.
    temp_dir = Path(tempfile.mkdtemp(prefix="ytranscript-"))
    try:
        audio_path, info = download_audio(url, temp_dir, progress)
        segments, detected = transcribe_audio_file(audio_path, model_size, language, progress)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    if is_youtube_url(url):
        video_id = extract_video_id(url)
        source_url = canonical_url(video_id)
    else:
        video_id = str(info.get("id") or url)
        source_url = str(info.get("webpage_url") or url)

    return Transcript(
        video_id=video_id,
        source_url=source_url,
        language=detected,
        language_code=detected,
        is_generated=True,
        source=f"whisper-{model_size}",
        segments=segments,
        title=info.get("title"),
    )
