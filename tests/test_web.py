"""Tests for the web page, using Flask's built-in test client.

``client.get("/")`` and ``client.post("/", data=...)`` pretend to be a
browser, so no real server or network is needed.
"""

import pytest

from ytranscript import web
from ytranscript.errors import NoCaptionsError

URL = "https://youtu.be/dQw4w9WgXcQ"


@pytest.fixture
def client(monkeypatch, sample_transcript):
    calls = []

    def fake(url, **kwargs):
        calls.append((url, kwargs))
        if "nocaptions" in url:
            raise NoCaptionsError("Captions are turned off for this video.")
        return sample_transcript

    monkeypatch.setattr(web, "get_transcript", fake)
    web.app.config["TESTING"] = True
    test_client = web.app.test_client()
    test_client.calls = calls  # so tests can inspect what was requested
    return test_client


def test_form_page_loads(client):
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "<form" in html
    assert 'name="url"' in html
    assert "Get transcript" in html
    assert "<pre>" not in html  # no result yet


def test_post_shows_transcript(client):
    resp = client.post("/", data={"url": URL, "format": "txt", "languages": "en"})
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "We&#39;re no strangers to love" in html  # HTML-escaped apostrophe
    assert "English (en)" in html
    assert "human-made" in html
    assert "Download .txt" in html


def test_post_srt_and_options(client):
    resp = client.post(
        "/",
        data={"url": URL, "format": "srt", "languages": "es,en", "translate_to": "fr",
              "timestamps": "on", "whisper_fallback": "on", "whisper_model": "small"},
    )
    assert resp.status_code == 200
    assert "00:00:00,000 --&gt; 00:00:02,500" in resp.get_data(as_text=True)
    url, kwargs = client.calls[0]
    assert url == URL
    assert kwargs["languages"] == ["es", "en"]
    assert kwargs["translate_to"] == "fr"
    assert kwargs["whisper_fallback"] is True
    assert kwargs["use_whisper"] is False
    assert kwargs["whisper_model"] == "small"


def test_post_error_shows_message(client):
    resp = client.post("/", data={"url": "https://www.youtube.com/watch?v=nocaptions1"})
    assert resp.status_code == 400
    html = resp.get_data(as_text=True)
    assert "Captions are turned off" in html
    assert "<form" in html  # the form is still there to try again


def test_download_sends_file(client):
    resp = client.get("/download", query_string={"url": URL, "format": "srt"})
    assert resp.status_code == 200
    assert resp.headers["Content-Disposition"] == 'attachment; filename="dQw4w9WgXcQ.srt"'
    assert resp.get_data(as_text=True).startswith("1\n00:00:00,000 --> 00:00:02,500\n")


def test_download_error(client):
    resp = client.get("/download", query_string={"url": "https://www.youtube.com/watch?v=nocaptions1"})
    assert resp.status_code == 400
    assert "Error:" in resp.get_data(as_text=True)


def test_unknown_format_falls_back_to_txt(client):
    resp = client.post("/", data={"url": URL, "format": "docx"})
    assert resp.status_code == 200
    assert "Download .txt" in resp.get_data(as_text=True)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "ok"
    assert "version" in body and "whisper_enabled" in body and "proxy" in body


def test_api_returns_json_by_default(client):
    resp = client.get("/api/transcript", query_string={"url": URL})
    assert resp.status_code == 200
    assert resp.content_type.startswith("application/json")
    body = resp.get_json()
    assert body["video_id"] == "dQw4w9WgXcQ"
    assert len(body["segments"]) == 3


def test_api_other_format_is_plain_text(client):
    resp = client.get("/api/transcript", query_string={"url": URL, "format": "srt", "languages": "es"})
    assert resp.status_code == 200
    assert resp.content_type.startswith("text/plain")
    assert resp.get_data(as_text=True).startswith("1\n00:00:00,000")
    assert client.calls[0][1]["languages"] == ["es"]


def test_api_error_is_json(client):
    resp = client.get("/api/transcript", query_string={"url": "https://www.youtube.com/watch?v=nocaptions1"})
    assert resp.status_code == 400
    assert "Captions are turned off" in resp.get_json()["error"]


def test_whisper_options_shown_when_enabled(client, monkeypatch):
    monkeypatch.setenv("YTRANSCRIPT_ENABLE_WHISPER", "1")
    html = client.get("/").get_data(as_text=True)
    assert 'name="whisper_fallback"' in html
    assert "hosted version fetches YouTube captions only" not in html


def test_whisper_disabled_hides_options_and_ignores_requests(client, monkeypatch):
    monkeypatch.setenv("YTRANSCRIPT_ENABLE_WHISPER", "0")
    html = client.get("/").get_data(as_text=True)
    assert 'name="whisper_fallback"' not in html
    assert 'name="whisper_model"' not in html
    assert "hosted version fetches YouTube captions only" in html

    # Even if someone sends the fields by hand, the server ignores them.
    client.post("/", data={"url": URL, "whisper": "on", "whisper_fallback": "on"})
    _, kwargs = client.calls[0]
    assert kwargs["use_whisper"] is False
    assert kwargs["whisper_fallback"] is False
