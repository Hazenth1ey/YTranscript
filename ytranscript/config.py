"""Settings read from *environment variables*.

When you host a program on a server you usually can't edit its files to
change a setting. Instead you set named values in the server's environment
(the hosting dashboard has a page for this) and the program reads them when
it starts. That is what this file does.

Every setting has a sensible default, so running locally needs nothing.

Settings:

``PORT`` / ``YTRANSCRIPT_HOST``
    Which port and network address the web server listens on. Hosting
    platforms set ``PORT`` themselves, so we honour it. ``PORT`` wins over
    the older ``YTRANSCRIPT_PORT`` name.

``YTRANSCRIPT_ENABLE_WHISPER``
    ``1`` (default) or ``0``. Whisper speech-to-text needs a lot of CPU and
    memory, more than a free hosting tier gives, so hosted deployments turn
    it off. The web page then hides the Whisper options.

``YTRANSCRIPT_PROXY_URL``
    YouTube frequently refuses caption requests coming from cloud servers.
    Setting this to a proxy URL (``http://user:pass@host:port``) routes the
    requests through it instead.

``WEBSHARE_PROXY_USERNAME`` / ``WEBSHARE_PROXY_PASSWORD``
    Same idea, but for Webshare's rotating residential proxies, which the
    caption library supports natively (it retries with a new address when
    one is blocked). If both proxy styles are set, Webshare wins.
"""

from __future__ import annotations

import os

# These are the strings we treat as "yes" when reading on/off settings.
_TRUTHY = {"1", "true", "yes", "on"}


def _flag(name: str, default: bool) -> bool:
    """Read an on/off environment variable."""
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in _TRUTHY


def host() -> str:
    return os.environ.get("YTRANSCRIPT_HOST", "127.0.0.1")


def port() -> int:
    return int(os.environ.get("PORT") or os.environ.get("YTRANSCRIPT_PORT") or "5000")


def whisper_enabled() -> bool:
    return _flag("YTRANSCRIPT_ENABLE_WHISPER", default=True)


def build_proxy_config():
    """Return a proxy configuration for the caption library, or ``None``.

    Imported lazily so this module stays cheap to load.
    """
    from youtube_transcript_api.proxies import GenericProxyConfig, WebshareProxyConfig

    username = os.environ.get("WEBSHARE_PROXY_USERNAME", "").strip()
    password = os.environ.get("WEBSHARE_PROXY_PASSWORD", "").strip()
    if username and password:
        return WebshareProxyConfig(proxy_username=username, proxy_password=password)

    url = os.environ.get("YTRANSCRIPT_PROXY_URL", "").strip()
    if url:
        return GenericProxyConfig(http_url=url, https_url=url)

    return None


def describe() -> dict:
    """A summary of the active settings (secrets hidden), for /health."""
    return {
        "whisper_enabled": whisper_enabled(),
        "proxy": (
            "webshare" if os.environ.get("WEBSHARE_PROXY_USERNAME") and os.environ.get("WEBSHARE_PROXY_PASSWORD")
            else "generic" if os.environ.get("YTRANSCRIPT_PROXY_URL")
            else "none"
        ),
    }
