"""Tests for reading settings from environment variables.

``monkeypatch.setenv`` / ``delenv`` change the environment for one test only,
so tests can't leak settings into each other.
"""

import pytest
from youtube_transcript_api.proxies import GenericProxyConfig, WebshareProxyConfig

from ytranscript import config, fetch

ENV_NAMES = [
    "PORT", "YTRANSCRIPT_PORT", "YTRANSCRIPT_HOST", "YTRANSCRIPT_ENABLE_WHISPER",
    "YTRANSCRIPT_PROXY_URL", "WEBSHARE_PROXY_USERNAME", "WEBSHARE_PROXY_PASSWORD",
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Start every test with none of our variables set."""
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_defaults():
    assert config.host() == "127.0.0.1"
    assert config.port() == 5000
    assert config.whisper_enabled() is True
    assert config.build_proxy_config() is None
    assert config.describe() == {"whisper_enabled": True, "proxy": "none"}


def test_port_prefers_hosting_platform_variable(monkeypatch):
    monkeypatch.setenv("YTRANSCRIPT_PORT", "5000")
    monkeypatch.setenv("PORT", "10000")
    assert config.port() == 10000


def test_host_override(monkeypatch):
    monkeypatch.setenv("YTRANSCRIPT_HOST", "0.0.0.0")
    assert config.host() == "0.0.0.0"


@pytest.mark.parametrize("value, expected", [
    ("0", False), ("false", False), ("no", False), ("off", False),
    ("1", True), ("true", True), ("YES", True), ("on", True),
    ("", True),  # empty = not set = default
])
def test_whisper_flag_values(monkeypatch, value, expected):
    monkeypatch.setenv("YTRANSCRIPT_ENABLE_WHISPER", value)
    assert config.whisper_enabled() is expected


def test_generic_proxy(monkeypatch):
    monkeypatch.setenv("YTRANSCRIPT_PROXY_URL", "http://user:pass@proxy.example:8080")
    proxy = config.build_proxy_config()
    assert isinstance(proxy, GenericProxyConfig)
    assert proxy.http_url == "http://user:pass@proxy.example:8080"
    assert proxy.https_url == "http://user:pass@proxy.example:8080"
    assert config.describe()["proxy"] == "generic"


def test_webshare_proxy_wins_over_generic(monkeypatch):
    monkeypatch.setenv("YTRANSCRIPT_PROXY_URL", "http://ignored")
    monkeypatch.setenv("WEBSHARE_PROXY_USERNAME", "alice")
    monkeypatch.setenv("WEBSHARE_PROXY_PASSWORD", "s3cret")
    proxy = config.build_proxy_config()
    assert isinstance(proxy, WebshareProxyConfig)
    assert config.describe()["proxy"] == "webshare"


def test_webshare_needs_both_values(monkeypatch):
    monkeypatch.setenv("WEBSHARE_PROXY_USERNAME", "alice")  # no password
    assert config.build_proxy_config() is None


def test_fetch_uses_proxy_setting(monkeypatch):
    """``default_api`` must hand the proxy to the YouTube client."""
    received = {}

    class RecordingApi:
        def __init__(self, proxy_config=None):
            received["proxy_config"] = proxy_config

    monkeypatch.setattr(fetch, "YouTubeTranscriptApi", RecordingApi)

    fetch.default_api()
    assert received["proxy_config"] is None

    monkeypatch.setenv("YTRANSCRIPT_PROXY_URL", "http://proxy.example:8080")
    fetch.default_api()
    assert isinstance(received["proxy_config"], GenericProxyConfig)
    assert received["proxy_config"].https_url == "http://proxy.example:8080"
