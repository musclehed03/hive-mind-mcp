"""Block 7 gate tests: micro-bot spawn + clipper bridge."""

import os
import subprocess
import sys

import pytest

from app.capture import capture_idea
from app.dispatch import dispatch_tool
from app.microbot import MIN_BYTES, MAX_BYTES, spawn_microbot
from app.store import Store

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture()
def store(tmp_path):
    s = Store(db_path=str(tmp_path / "b7.db"), vault_dir=str(tmp_path / "vault"))
    yield s
    s.close()


def _spawn(store, **kw):
    args = {"template_name": "digest", "mode_level": "simple",
            "allowance_limit": 0, "cooldown_sec": 0}
    args.update(kw)
    return spawn_microbot(args["template_name"], args["mode_level"],
                          args["allowance_limit"], args["cooldown_sec"],
                          store.vault_dir)


def test_digest_script_size_and_compiles_and_runs(store):
    payload = _spawn(store)
    assert payload["status"] == "ok"
    assert MIN_BYTES <= payload["size_bytes"] <= MAX_BYTES
    assert len(payload["script"].encode("utf-8")) == payload["size_bytes"]
    assert os.path.exists(payload["path"])
    assert "network" not in payload["script"].lower().split("no network")[0][-200:]
    assert "import socket" not in payload["script"]
    assert "urllib" not in payload["script"]
    result = subprocess.run([sys.executable, payload["path"], "--dry-run"],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0
    assert "dry run" in result.stdout


def test_digest_script_reads_vault_and_prints_digest(store):
    store.remember("Library opens at 10am", domain="general")
    payload = _spawn(store)
    result = subprocess.run([sys.executable, payload["path"], "--vault", store.vault_dir],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0
    assert "Library opens at 10am" in result.stdout


def test_sentinel_script_size_and_guards(store):
    payload = _spawn(store, template_name="sentinel", mode_level="pro",
                     allowance_limit=50, cooldown_sec=60)
    assert MIN_BYTES <= payload["size_bytes"] <= MAX_BYTES
    assert payload["guards"]["max_slippage_pct"] == 0.5
    assert payload["guards"]["live_trading"] is False
    result = subprocess.run([sys.executable, payload["path"], "--dry-run",
                             "--amount", "10", "--price-move-pct", "0.2"],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0
    assert "would buy" in result.stdout
    blocked = subprocess.run([sys.executable, payload["path"], "--dry-run",
                              "--amount", "10", "--price-move-pct", "1.0"],
                             capture_output=True, text=True, timeout=30)
    assert "stand down" in blocked.stdout
    assert "slippage" in blocked.stdout


def test_pro_mode_refuses_without_allowance(store):
    with pytest.raises(ValueError, match="allowance"):
        _spawn(store, template_name="sentinel", mode_level="pro",
               allowance_limit=0, cooldown_sec=60)
    with pytest.raises(ValueError, match="cooldown"):
        _spawn(store, template_name="sentinel", mode_level="pro",
               allowance_limit=50, cooldown_sec=10)


def test_slider_values_map_to_modes(store):
    assert _spawn(store, mode_level="25")["mode_level"] == "simple"
    assert _spawn(store, template_name="sentinel", mode_level="75",
                  allowance_limit=50, cooldown_sec=60)["mode_level"] == "pro"


def test_unknown_template_rejected(store):
    with pytest.raises(ValueError, match="unknown template"):
        _spawn(store, template_name="rocket")


def test_spawn_via_dispatch_and_status_implemented(store):
    payload, err = dispatch_tool("hivemind_spawn_microbot", {
        "template_name": "digest", "mode_level": "simple",
        "allowance_limit": 0, "cooldown_sec": 0}, store=store)
    assert err is False and payload["status"] == "ok"


def test_clipper_payload_is_captured_with_source_url(store):
    payload = "URL: https://example.org/notes\n\nThe library opens at 10am on Sundays."
    result = capture_idea(payload, source_type="clipper", domain_hint="general",
                          client_id="clipper", store=store)
    assert result["status"] == "ok"
    stored = store.get_memory(result["memory_id"])
    assert stored["source"] == "https://example.org/notes"
    assert stored["text"] == "The library opens at 10am on Sundays."
    assert stored["provenance"]["source_type"] == "clipper"


def test_clipper_files_exist_and_are_labelled():
    with open(os.path.join(REPO, "gui", "bookmarklet.js"), encoding="utf-8") as f:
        bookmarklet = f.read()
    assert "clipper.html" in bookmarklet
    assert "encodeURIComponent" in bookmarklet
    assert "getSelection" in bookmarklet
    with open(os.path.join(REPO, "gui", "clipper.html"), encoding="utf-8") as f:
        clipper = f.read()
    for field in ("clip-url", "clip-title", "clip-text", "clip-domain", "payload-output"):
        assert f'for="{field}"' in clipper or f'id="{field}"' in clipper
    assert 'alt="Hive-Mind logo' in clipper
    assert "URL: " in clipper
