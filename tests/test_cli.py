"""Tests for the command-line tool.

We call ``main()`` directly with a list of arguments, exactly as the shell
would pass them, and capture what it prints with pytest's ``capsys``.
The network is replaced by a fake ``get_transcript``.
"""

import json

import pytest

from ytranscript import cli
from ytranscript.errors import NoCaptionsError

URL = "https://youtu.be/dQw4w9WgXcQ"


@pytest.fixture
def fake_get_transcript(monkeypatch, sample_transcript):
    """Make the CLI return our sample transcript and record the options it used."""
    calls = []

    def fake(url, **kwargs):
        calls.append((url, kwargs))
        if "nocaptions" in url:
            raise NoCaptionsError("Captions are turned off for this video.")
        return sample_transcript

    monkeypatch.setattr(cli, "get_transcript", fake)
    return calls


def test_prints_text_by_default(fake_get_transcript, capsys):
    code = cli.main([URL])
    out, err = capsys.readouterr()
    assert code == 0
    assert out.startswith("We're no strangers to love")
    assert "[0:00]" not in out


def test_timestamps_flag(fake_get_transcript, capsys):
    cli.main([URL, "--timestamps"])
    out, _ = capsys.readouterr()
    assert out.startswith("[0:00] We're no strangers to love")


def test_srt_format(fake_get_transcript, capsys):
    cli.main([URL, "-f", "srt"])
    out, _ = capsys.readouterr()
    assert out.startswith("1\n00:00:00,000 --> 00:00:02,500\n")


def test_json_format(fake_get_transcript, capsys):
    cli.main([URL, "--format", "json"])
    out, _ = capsys.readouterr()
    assert json.loads(out)["video_id"] == "dQw4w9WgXcQ"


def test_options_are_passed_through(fake_get_transcript):
    cli.main([URL, "-l", "es, en", "--translate-to", "fr", "--whisper-fallback", "--whisper-model", "small", "-q"])
    url, kwargs = fake_get_transcript[0]
    assert url == URL
    assert kwargs["languages"] == ["es", "en"]
    assert kwargs["translate_to"] == "fr"
    assert kwargs["whisper_fallback"] is True
    assert kwargs["use_whisper"] is False
    assert kwargs["whisper_model"] == "small"


def test_output_file(fake_get_transcript, tmp_path, capsys):
    target = tmp_path / "out.vtt"
    code = cli.main([URL, "-f", "vtt", "-o", str(target)])
    out, err = capsys.readouterr()
    assert code == 0
    assert out == ""  # nothing on stdout when saving to a file
    assert target.read_text(encoding="utf-8").startswith("WEBVTT")
    assert "Saved 3 lines" in err


def test_output_auto_names_file_after_video_id(fake_get_transcript, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # so the file lands in a temp folder
    cli.main([URL, "-f", "md", "-o", "auto"])
    assert (tmp_path / "dQw4w9WgXcQ.md").exists()


def test_error_is_friendly_and_exit_code_1(fake_get_transcript, capsys):
    code = cli.main(["https://www.youtube.com/watch?v=nocaptions1"])
    out, err = capsys.readouterr()
    assert code == 1
    assert out == ""
    assert err.strip() == "Error: Captions are turned off for this video."


def test_invalid_link_error(capsys):
    code = cli.main(["https://vimeo.com/1"])
    _, err = capsys.readouterr()
    assert code == 1
    assert "not a YouTube link" in err


def test_list_languages(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "list_available_languages",
        lambda url: [
            {"language": "English", "language_code": "en", "is_generated": False, "is_translatable": True},
            {"language": "Spanish (auto)", "language_code": "es", "is_generated": True, "is_translatable": False},
        ],
    )
    code = cli.main([URL, "--list-languages"])
    out, _ = capsys.readouterr()
    assert code == 0
    lines = out.strip().splitlines()
    assert lines[0].split() == ["code", "language", "type", "translatable"]
    assert lines[1].split() == ["en", "English", "manual", "yes"]
    assert lines[2].split() == ["es", "Spanish", "(auto)", "auto", "no"]


def test_list_languages_none(monkeypatch, capsys):
    monkeypatch.setattr(cli, "list_available_languages", lambda url: [])
    cli.main([URL, "--list-languages"])
    out, _ = capsys.readouterr()
    assert "no captions" in out


def test_help_mentions_formats(capsys):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--help"])
    assert excinfo.value.code == 0
    out, _ = capsys.readouterr()
    assert "srt" in out and "--whisper" in out
