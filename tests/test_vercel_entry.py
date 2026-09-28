"""Check the Vercel entry point (api/index.py) exposes the app correctly.

Importing that file changes an environment variable, so we run it in a
separate Python process to keep the other tests unaffected.
"""

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SCRIPT = """
import json, os
import api.index as entry
client = entry.app.test_client()
health = client.get("/health").get_json()
page = client.get("/").get_data(as_text=True)
print(json.dumps({
    "app_name": entry.app.name,
    "whisper_env": os.environ.get("YTRANSCRIPT_ENABLE_WHISPER"),
    "health": health,
    "whisper_hidden": 'name="whisper_fallback"' not in page,
}))
"""


def _run(extra_env: dict | None = None) -> dict:
    env = {k: v for k, v in __import__("os").environ.items() if not k.startswith("YTRANSCRIPT_")}
    env.update(extra_env or {})
    out = subprocess.run(
        [sys.executable, "-c", SCRIPT], cwd=REPO_ROOT, env=env, capture_output=True, text=True, check=True
    )
    return json.loads(out.stdout)


def test_entry_point_serves_app_with_whisper_off():
    result = _run()
    assert result["app_name"] == "ytranscript.web"
    assert result["whisper_env"] == "0"
    assert result["health"]["status"] == "ok"
    assert result["health"]["whisper_enabled"] is False
    assert result["whisper_hidden"] is True


def test_dashboard_setting_still_wins():
    result = _run({"YTRANSCRIPT_ENABLE_WHISPER": "1"})
    assert result["health"]["whisper_enabled"] is True
    assert result["whisper_hidden"] is False


def test_vercel_config_routes_everything_to_the_function():
    config = json.loads((REPO_ROOT / "vercel.json").read_text())
    assert config["rewrites"] == [{"source": "/(.*)", "destination": "/api/index"}]
    assert "api/index.py" in config["functions"]
