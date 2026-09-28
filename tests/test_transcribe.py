"""Tests for the Whisper fallback.

Downloading audio and running a speech model are far too slow (and need the
internet) for a test, so we replace ``yt-dlp`` and ``WhisperModel`` with
tiny fakes and check that our code wires them together correctly.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from ytranscript import transcribe
from ytranscript.errors import TranscriptError, WhisperNotInstalledError


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeYoutubeDL:
    """Mimics ``yt_dlp.YoutubeDL`` used as ``with YoutubeDL(opts) as ydl:``."""

    last_options: dict = {}
    fail = False

    def __init__(self, options):
        FakeYoutubeDL.last_options = options

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def extract_info(self, url, download=True):
        if FakeYoutubeDL.fail:
            raise RuntimeError("404 not found")
        # Pretend we downloaded something: create the file the template names.
        template = FakeYoutubeDL.last_options["outtmpl"]
        Path(template.replace("%(ext)s", "m4a")).write_bytes(b"fake audio")
        return {"id": "abc123", "title": "A Test Video", "webpage_url": url}


class FakeWhisperModel:
    """Mimics ``faster_whisper.WhisperModel``."""

    init_args: tuple = ()
    transcribe_kwargs: dict = {}
    fail_load = False

    def __init__(self, *args, **kwargs):
        if FakeWhisperModel.fail_load:
            raise OSError("403 Forbidden")
        FakeWhisperModel.init_args = (args, kwargs)

    def transcribe(self, audio, **kwargs):
        FakeWhisperModel.transcribe_kwargs = kwargs
        segments = iter([
            SimpleNamespace(text=" Hello there. ", start=0.0, end=1.2),
            SimpleNamespace(text="   ", start=1.2, end=1.5),  # blank -> dropped
            SimpleNamespace(text="General Kenobi.", start=1.5, end=3.0),
        ])
        return segments, SimpleNamespace(language="en")


@pytest.fixture
def fakes(monkeypatch):
    FakeYoutubeDL.fail = False
    FakeWhisperModel.fail_load = False
    monkeypatch.setattr(transcribe, "_import_yt_dlp", lambda: SimpleNamespace(YoutubeDL=FakeYoutubeDL))
    monkeypatch.setattr(transcribe, "_import_whisper", lambda: FakeWhisperModel)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_download_audio(fakes, tmp_path):
    path, info = transcribe.download_audio("https://vimeo.com/1", tmp_path)
    assert path.name == "audio.m4a"
    assert info["title"] == "A Test Video"
    opts = FakeYoutubeDL.last_options
    assert opts["format"] == "bestaudio/best"
    assert opts["noplaylist"] is True


def test_download_audio_failure_is_friendly(fakes, tmp_path):
    FakeYoutubeDL.fail = True
    with pytest.raises(TranscriptError, match="Could not download audio"):
        transcribe.download_audio("https://vimeo.com/1", tmp_path)


def test_transcribe_audio_file(fakes, tmp_path):
    audio = tmp_path / "audio.m4a"
    audio.write_bytes(b"fake")
    segments, lang = transcribe.transcribe_audio_file(audio, model_size="small", language="en")
    assert lang == "en"
    assert [(s.text, s.start, s.duration) for s in segments] == [
        ("Hello there.", 0.0, 1.2),
        ("General Kenobi.", 1.5, 1.5),
    ]
    assert FakeWhisperModel.init_args[0] == ("small",)
    assert FakeWhisperModel.transcribe_kwargs["language"] == "en"
    assert FakeWhisperModel.transcribe_kwargs["vad_filter"] is True


def test_model_load_failure_is_friendly(fakes, tmp_path):
    FakeWhisperModel.fail_load = True
    audio = tmp_path / "audio.m4a"
    audio.write_bytes(b"fake")
    with pytest.raises(TranscriptError, match="Could not load the Whisper model"):
        transcribe.transcribe_audio_file(audio)


def test_transcribe_with_whisper_youtube(fakes):
    messages = []
    t = transcribe.transcribe_with_whisper("https://youtu.be/dQw4w9WgXcQ", progress=messages.append)
    assert t.video_id == "dQw4w9WgXcQ"
    assert t.source_url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert t.source == "whisper-base"
    assert t.language_code == "en"
    assert t.is_generated is True
    assert t.title == "A Test Video"
    assert len(t.segments) == 2
    assert messages[0] == "Downloading audio..."


def test_transcribe_with_whisper_other_site(fakes):
    t = transcribe.transcribe_with_whisper("https://vimeo.com/1")
    assert t.video_id == "abc123"  # from yt-dlp's metadata
    assert t.source_url == "https://vimeo.com/1"


def test_temp_folder_is_cleaned_up(fakes, monkeypatch, tmp_path):
    created = []
    real_mkdtemp = transcribe.tempfile.mkdtemp

    def recording_mkdtemp(**kwargs):
        d = real_mkdtemp(dir=tmp_path, **kwargs)
        created.append(Path(d))
        return d

    monkeypatch.setattr(transcribe.tempfile, "mkdtemp", recording_mkdtemp)
    transcribe.transcribe_with_whisper("https://vimeo.com/1")
    assert created and not created[0].exists()


def test_unknown_model_size(fakes):
    with pytest.raises(ValueError, match="Unknown Whisper model"):
        transcribe.transcribe_with_whisper("https://vimeo.com/1", model_size="huge")


def test_missing_dependencies_message(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def no_yt_dlp(name, *args, **kwargs):
        if name in ("yt_dlp", "faster_whisper"):
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_yt_dlp)
    with pytest.raises(WhisperNotInstalledError, match=r'pip install -e "\.\[whisper\]"'):
        transcribe._import_yt_dlp()
    with pytest.raises(WhisperNotInstalledError):
        transcribe._import_whisper()
