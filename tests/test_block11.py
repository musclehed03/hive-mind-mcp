"""Block 11 gate tests: EXP, local only, rewards memory health.

Points, once-per-endpoint dedupe, monotonic totals, dispatch wiring
(verify / supersede / snapshot), the read-only /api/exp endpoint,
and the guarantee that EXP adds no MCP tool.
"""

import json
import os
import threading
import urllib.request

import pytest

from app.dispatch import dispatch_tool
from app.exp import (
    POINTS, detect_configured_endpoints, record_event, record_startup_endpoints,
    totals,
)
from app.store import Store
from app.tools import TOOLS


@pytest.fixture()
def vault(tmp_path):
    return str(tmp_path / "vault")


def test_points_are_documented_values():
    assert POINTS == {
        "endpoint_attached": 50,
        "verified_recall": 10,
        "contradiction_resolved": 25,
        "snapshot_backed_up": 15,
    }


def test_totals_start_at_zero(vault):
    assert totals(vault) == {
        "total": 0,
        "by_kind": {k: 0 for k in POINTS},
        "events": 0,
        "endpoints": [],
    }
    assert not os.path.exists(os.path.join(vault, "exp_events.jsonl"))


def test_each_kind_records_its_points(vault):
    for kind, points in POINTS.items():
        if kind == "endpoint_attached":
            record_event(vault, kind, endpoint="model-endpoint:test model m")
        else:
            record_event(vault, kind)
    result = totals(vault)
    assert result["total"] == sum(POINTS.values())
    assert result["by_kind"] == dict(POINTS)
    assert result["events"] == 4


def test_endpoint_attached_dedupes_per_endpoint(vault):
    first = record_event(vault, "endpoint_attached", endpoint="model-endpoint:a model m")
    assert first["recorded"] is True
    assert first["total"] == 50
    second = record_event(vault, "endpoint_attached", endpoint="model-endpoint:a model m")
    assert second["recorded"] is False
    assert second["total"] == 50
    third = record_event(vault, "endpoint_attached", endpoint="supabase:https://example.test")
    assert third["recorded"] is True
    assert third["total"] == 100
    assert totals(vault)["endpoints"] == [
        "model-endpoint:a model m", "supabase:https://example.test"]
    # Local and cloud endpoints earn the same points: dedupe is by
    # identity, not by kind of endpoint.


def test_endpoint_attached_requires_endpoint(vault):
    with pytest.raises(ValueError):
        record_event(vault, "endpoint_attached")
    with pytest.raises(ValueError):
        record_event(vault, "endpoint_attached", endpoint="  ")


def test_unknown_kind_rejected(vault):
    with pytest.raises(ValueError):
        record_event(vault, "live_call_made")


def test_totals_never_decrease_and_bad_lines_skipped(vault):
    record_event(vault, "verified_recall")
    before = totals(vault)["total"]
    with open(os.path.join(vault, "exp_events.jsonl"), "a", encoding="utf-8") as f:
        f.write("not json\n")
        f.write(json.dumps({"kind": "nope", "points": 999}) + "\n")
        f.write("\n")
    assert totals(vault)["total"] == before
    record_event(vault, "verified_recall")
    assert totals(vault)["total"] == before + 10


def test_log_is_append_only_jsonl(vault):
    record_event(vault, "verified_recall")
    record_event(vault, "snapshot_backed_up")
    with open(os.path.join(vault, "exp_events.jsonl"), encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()]
    assert [line["kind"] for line in lines] == ["verified_recall", "snapshot_backed_up"]
    assert all("created_at" in line for line in lines)
    assert all("points" in line for line in lines)


def test_detect_endpoints_needs_live_flag_and_credentials(monkeypatch):
    monkeypatch.setenv("META_API_KEY", "LLM_fake-test")
    assert detect_configured_endpoints() == []
    monkeypatch.setenv("HIVE_MIND_LIVE", "1")
    endpoints = detect_configured_endpoints()
    assert len(endpoints) == 1
    assert endpoints[0].startswith("model-endpoint:https://api.meta.ai/v1")
    assert "LLM_fake-test" not in endpoints[0], "endpoint key must never hold a key"
    monkeypatch.setenv("SUPABASE_URL", "https://example.test")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "fake-service-key")
    endpoints = detect_configured_endpoints()
    assert len(endpoints) == 2
    assert "supabase:https://example.test" in endpoints
    # A local Ollama-style base URL earns the same endpoint identity
    # shape — and the same points — as the cloud default.
    monkeypatch.setenv("HIVE_MIND_META_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("HIVE_MIND_META_MODEL", "gemma3:4b")
    endpoints = detect_configured_endpoints()
    assert "model-endpoint:http://localhost:11434/v1 model gemma3:4b" in endpoints


def test_startup_endpoints_record_once(monkeypatch, vault):
    monkeypatch.setenv("HIVE_MIND_LIVE", "1")
    monkeypatch.setenv("META_API_KEY", "LLM_fake-test")
    record_startup_endpoints(vault)
    assert totals(vault)["total"] == 50
    record_startup_endpoints(vault)
    assert totals(vault)["total"] == 50


@pytest.fixture()
def store(tmp_path):
    s = Store(db_path=str(tmp_path / "v.db"), vault_dir=str(tmp_path / "vault"))
    yield s
    s.close()


def _verify_args(fact, supersede=""):
    return {
        "candidate_fact": fact, "domain_repo": "general",
        "source_citation": "test notes", "supersede_id": supersede,
    }


def test_dispatch_verify_earns_verified_recall(store):
    payload, is_error = dispatch_tool(
        "hivemind_crosshatch_verify",
        _verify_args("The meeting starts at 10am on Monday"), store=store)
    assert payload["status"] == "verified"
    assert not is_error
    assert totals(store.vault_dir)["by_kind"]["verified_recall"] == 10


def test_dispatch_conflict_earns_nothing_until_superseded(store):
    first, _ = dispatch_tool(
        "hivemind_crosshatch_verify",
        _verify_args("The meeting starts at 10am on Monday"), store=store)
    clash, _ = dispatch_tool(
        "hivemind_crosshatch_verify",
        _verify_args("The meeting starts at 2pm on Monday"), store=store)
    assert clash["status"] == "conflict"
    assert totals(store.vault_dir)["total"] == 10
    settled, _ = dispatch_tool(
        "hivemind_crosshatch_verify",
        _verify_args("The meeting starts at 2pm on Monday",
                     supersede=first["memory_id"]), store=store)
    assert settled["status"] == "superseded"
    assert totals(store.vault_dir)["by_kind"]["contradiction_resolved"] == 25


def test_dispatch_snapshot_earns_backup_points(store):
    payload, is_error = dispatch_tool("hivemind_snapshot_backup", {
        "destination_target": "supabase", "schedule_interval": "7d",
        "user_handshake_token": "yes",
    }, store=store)
    assert payload["status"] == "local_only"
    assert payload["verified_callback"] is True
    assert not is_error
    assert totals(store.vault_dir)["by_kind"]["snapshot_backed_up"] == 15


def test_no_exp_tool_added():
    names = [tool["name"] for tool in TOOLS]
    assert len(names) == 8
    # "explain" contains the letters "exp" — match a real EXP tool
    # name, not a substring.
    assert "hivemind_exp" not in names
    assert not any(name.endswith("_exp") for name in names)


def test_api_exp_endpoint(tmp_path, monkeypatch):
    from app.gui_server import _Handler
    from http.server import ThreadingHTTPServer

    import app.store as store_module

    monkeypatch.setattr(store_module, "DB_PATH", str(tmp_path / "srv.db"))
    monkeypatch.setattr(store_module, "VAULT_DIR", str(tmp_path / "vault"))
    record_event(str(tmp_path / "vault"), "verified_recall")
    record_event(str(tmp_path / "vault"), "verified_recall")
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/exp", timeout=5) as resp:
            assert resp.status == 200
            data = json.load(resp)
        assert data["total"] == 20
        assert data["events"] == 2
    finally:
        server.shutdown()
        server.server_close()
