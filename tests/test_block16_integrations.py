"""Block 16 gate tests: the Integrations box (Sonja's order, Nov 1).

A clean Integrations section in Regular Settings (never the
Accessibility Suite) showing live, read-only, secret-free status
from GET /api/integrations, with copy buttons for the stdio
command, the SSE URL, and the Codex setup snippet, plus plain
instructions for where keys live and where to find them. Keys are
never typed in the GUI, never displayed, never copied, and never
returned by the endpoint.
"""

import json
import os
import re
import subprocess
import threading
import urllib.request

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_ENV_KEYS = (
    "HIVE_MIND_LIVE",
    "HIVE_MIND_META_BASE_URL",
    "HIVE_MIND_META_MODEL",
    "META_API_KEY",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "HIVE_MIND_SUPABASE_BUCKET",
)

_META_SENTINEL = "sk-test-sentinel-9f8e7d6c5b4a"
_SB_SENTINEL = "sb-test-sentinel-1234567890abcdef"


def _clear_env(monkeypatch):
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def _serve(tmp_path, monkeypatch):
    """Start the GUI server on an ephemeral localhost port."""
    import app.store as store_module
    from app.gui_server import _Handler
    from http.server import ThreadingHTTPServer

    monkeypatch.setattr(store_module, "DB_PATH", str(tmp_path / "srv.db"))
    monkeypatch.setattr(store_module, "VAULT_DIR", str(tmp_path / "vault"))
    from app.store import Store as _Store

    _s = _Store()
    _s.remember("Integrations smoke fact")
    _s.close()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, server.server_address[1]


def _get(port, path):
    with urllib.request.urlopen(
        f"http://127.0.0.1:{port}{path}", timeout=5
    ) as resp:
        assert resp.status == 200, path
        return resp.read()


def test_endpoint_default_shape_is_fake_and_secret_free(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    server, port = _serve(tmp_path, monkeypatch)
    try:
        body = _get(port, "/api/integrations")
        data = json.loads(body)
    finally:
        server.shutdown()
        server.server_close()
    assert set(data) == {"mcp_stdio", "mcp_sse", "model", "supabase", "exp"}, data
    assert data["mcp_stdio"] == {
        "command": "python -m app.mcp_server",
        "status": "Available",
    }
    assert data["mcp_sse"]["url"] == "http://127.0.0.1:8765/sse"
    assert isinstance(data["mcp_sse"]["running"], bool)
    assert data["mcp_sse"]["status"] in ("Connected", "Not connected")
    assert data["mcp_sse"]["status"] == (
        "Connected" if data["mcp_sse"]["running"] else "Not connected"
    )
    assert data["model"]["base_url"] == "https://api.meta.ai/v1"
    assert data["model"]["model"] == "muse-spark-1.3"
    assert data["model"]["live"] is False
    assert data["model"]["key_present"] is False
    assert data["model"]["key_required"] is True
    assert data["model"]["status"] == "Fake (tests only)"
    assert data["supabase"] == {
        "configured": False,
        "bucket": "hive-mind-snapshots",
        "status": "Not connected",
    }
    assert data["exp"]["total"] == 0 and data["exp"]["events"] == 0
    # The Supabase URL is never returned, only the configured flag.
    assert "supabase.co" not in body.decode("utf-8")


def test_endpoint_never_returns_key_values(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("HIVE_MIND_LIVE", "1")
    monkeypatch.setenv("META_API_KEY", _META_SENTINEL)
    monkeypatch.setenv("SUPABASE_URL", "https://example-test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", _SB_SENTINEL)
    monkeypatch.setenv("HIVE_MIND_SUPABASE_BUCKET", "test-bucket-only")
    server, port = _serve(tmp_path, monkeypatch)
    try:
        body = _get(port, "/api/integrations").decode("utf-8")
        data = json.loads(body)
    finally:
        server.shutdown()
        server.server_close()
    assert _META_SENTINEL not in body
    assert _SB_SENTINEL not in body
    assert "example-test.supabase.co" not in body
    assert data["model"]["key_present"] is True
    assert data["model"]["status"] == "Connected"
    assert data["supabase"]["configured"] is True
    assert data["supabase"]["bucket"] == "test-bucket-only"
    assert data["supabase"]["status"] == "Connected"


def test_model_status_loopback_needs_no_key_and_remote_refuses(tmp_path, monkeypatch):
    import app.integrations as integ

    _clear_env(monkeypatch)
    monkeypatch.setenv("HIVE_MIND_LIVE", "1")
    monkeypatch.setenv("HIVE_MIND_META_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("HIVE_MIND_META_MODEL", "gemma3:4b")
    data = integ.status(str(tmp_path))
    assert data["model"]["key_required"] is False
    assert data["model"]["status"] == "Connected"
    monkeypatch.setenv("HIVE_MIND_META_BASE_URL", "https://openrouter.ai/api/v1")
    data = integ.status(str(tmp_path))
    assert data["model"]["key_required"] is True
    assert data["model"]["status"] == "Not connected"


def test_sse_probe_results_and_failures(tmp_path):
    import app.integrations as integ

    assert integ.status(str(tmp_path), sse_probe=lambda url: True)["mcp_sse"][
        "running"
    ] is True
    assert integ.status(str(tmp_path), sse_probe=lambda url: True)["mcp_sse"][
        "status"
    ] == "Connected"

    def _boom(url):
        raise RuntimeError("probe exploded")

    assert integ.status(str(tmp_path), sse_probe=_boom)["mcp_sse"][
        "running"
    ] is False
    # The default probe targets localhost only and never raises.
    assert integ._sse_running() is False or isinstance(integ._sse_running(), bool)


def test_status_never_raises_when_exp_log_is_broken(tmp_path, monkeypatch):
    import app.integrations as integ

    _clear_env(monkeypatch)
    monkeypatch.setattr(integ, "exp_totals", lambda vault_dir: 1 / 0)
    data = integ.status(str(tmp_path))
    assert data["exp"] == {"total": 0, "events": 0}
    assert data["model"]["status"] == "Fake (tests only)"


def test_integrations_source_is_secret_free_and_localhost_only():
    with open(os.path.join(REPO, "app", "integrations.py"), encoding="utf-8") as f:
        src = f.read()
    assert "LLM_" not in src
    assert "socket" not in src
    assert "http.client" not in src
    assert "requests" not in src
    # The only remote-looking literals are the localhost SSE check.
    for url in re.findall(r'https?://[^\s"\']+', src):
        assert url.startswith("http://127.0.0.1:8765"), url
    assert "127.0.0.1:8765" in src


def _read_gui(name):
    with open(os.path.join(REPO, "gui", name), encoding="utf-8") as f:
        return f.read()


def test_html_integrations_section_placement_and_controls():
    html = _read_gui("index.html")
    assert ' id="integrations"' in html
    # Placed with Regular Settings: after it, before the guide —
    # and never inside the Accessibility Suite section.
    assert html.index('id="regular-settings"') < html.index('id="integrations"')
    assert html.index('id="integrations"') < html.index('id="plain-language-guide"')
    suite = html[html.index('id="accessibility-suite"'):html.index("</section>", html.index('id="accessibility-suite"'))]
    assert 'id="integrations"' not in suite
    for button_id in ("copy-stdio", "copy-sse", "copy-config"):
        assert f'id="{button_id}"' in html, button_id
    for button_id in ("copy-stdio", "copy-sse", "copy-config"):
        chunk = html[html.index(f'id="{button_id}"') - 200:html.index(f'id="{button_id}"') + 400]
        assert "data-tooltip=" in chunk, button_id
        assert "aria-label=" in chunk, button_id
    assert "Keys are never typed here." in html
    assert 'type="password"' not in html
    assert "<input" not in html.split('id="integrations"')[1].split("</section>")[0], \
        "no input fields in the Integrations box"
    assert ' title="' not in html, "no native title attributes"
    # Plain instructions: .env + nano, providers, doc location.
    box = html.split('id="integrations"')[1].split("</section>")[0]
    assert "nano .env" in box or "nano" in box
    assert "dev.meta.ai" in box
    assert "ollama list" in box
    assert "OpenRouter" in box
    assert "docs/INTEGRATIONS.md" in box
    for row_id in ("value-stdio", "value-sse", "value-model", "value-supabase", "value-exp"):
        assert f'id="{row_id}"' in html, row_id
    for status_id in ("status-stdio", "status-sse", "status-model", "status-supabase", "status-exp"):
        assert f'id="{status_id}"' in html, status_id


def test_codex_snippet_matches_doc_literally():
    with open(os.path.join(REPO, "docs", "INTEGRATIONS.md"), encoding="utf-8") as f:
        doc = f.read()
    codex = doc[doc.index("### Codex"):]
    fence = re.search(r"```toml\n(.*?)```", codex, re.DOTALL)
    assert fence, "Codex TOML block missing from INTEGRATIONS.md"
    html = _read_gui("index.html")
    snippet = re.search(
        r'<code id="codex-config-snippet">(.*?)</code>', html, re.DOTALL
    )
    assert snippet, "snippet block missing from GUI"
    assert snippet.group(1).strip() == fence.group(1).strip()


def test_js_copy_handler_and_fetch():
    js = _read_gui("app.js")
    assert 'fetch("/api/integrations"' in js
    assert "navigator.clipboard.writeText" in js
    assert 'execCommand("copy")' in js
    assert '"Copied"' in js
    assert "codex-config-snippet" in js
    assert "data-copy" in js
    assert "setInterval" not in js
    # Exactly three one-shot delays: tooltip + copy revert + the
    # single Block 18 demo scheduler (guard revision disclosed in
    # test_block8.py).
    assert js.count("setTimeout") == 3
    css = _read_gui("styles.css")
    assert ".integration-status.status-connected" in css
    assert ".integration-status.status-off" in css
    assert ".integration-status.status-fake" in css
    assert "section.integrations" in css


_NODE_HARNESS = """
const fs = require("fs");
const src = fs.readFileSync(%s, "utf8");
global.window = {};
eval(src);
const I = global.window.HIVEMIND_INTEGRATIONS;
const assert = require("assert");
assert(I, "HIVEMIND_INTEGRATIONS missing");
assert.strictEqual(I.statusClassFor("Connected"), "status-connected");
assert.strictEqual(I.statusClassFor("Available"), "status-connected");
assert.strictEqual(I.statusClassFor("Not connected"), "status-off");
assert.strictEqual(I.statusClassFor("Fake (tests only)"), "status-fake");
assert.strictEqual(I.statusClassFor("Local only"), "status-local");
assert.strictEqual(I.statusClassFor("something else"), "status-local");
console.log(JSON.stringify({ok: true}));
"""


def test_status_class_helper_executes_in_node():
    stage_path = os.path.join(REPO, "gui", "stage.js")
    script = _NODE_HARNESS % json.dumps(stage_path)
    result = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.strip()) == {"ok": True}


def test_palettes_and_spec_unchanged():
    import hashlib

    with open(os.path.join(REPO, "gui", "settings-data.js"), encoding="utf-8") as f:
        data = f.read()
    assert '"accent": "#ad3375"' in data, "Variant A default untouched"
    assert '"node": "#808080"' in data, "achromatopsia node untouched"
    digest = hashlib.md5(
        open(os.path.join(REPO, "docs", "HIVE-MIND-LOCK-IN-SPEC.md"), "rb").read()
    ).hexdigest()
    assert digest == "13fa897039dd6b1cd0d11e90e85d7c2c"
    with open(os.path.join(REPO, "app", "tools.py"), encoding="utf-8") as f:
        tools_src = f.read()
    assert tools_src.count("hivemind_") >= 8, "tools still present"
