"""Block 1 gate tests (game plan / test plan, Block 1 only).

No network, no API keys, no Supabase, no live calls anywhere here.
The server is exercised over real stdio in a subprocess.
"""

import json
import os
import re
import subprocess
import sys

import pytest

from app.mcp_server import handle_request
from app.store import Store
from app.tools import TOOLS, TOOL_NAMES, get_tool, not_implemented

EXPECTED_TOOLS = [
    "hivemind_capture_idea",
    "hivemind_scrub_input",
    "hivemind_crosshatch_verify",
    "hivemind_query_temporal",
    "hivemind_spawn_microbot",
    "hivemind_snapshot_backup",
    "hivemind_explain",
    "hivemind_prune_memory",
]

SCALAR_TYPES = {"string", "integer", "number", "boolean"}
SNAKE = re.compile(r"^[a-z][a-z0-9_]*$")


# -- registry ------------------------------------------------------------

def test_exact_tool_names_in_spec_order():
    assert TOOL_NAMES == EXPECTED_TOOLS


def test_all_args_flat_scalar_and_snake_case():
    for tool in TOOLS:
        schema = tool["inputSchema"]
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False
        assert schema["required"] == list(schema["properties"])
        for name, prop in schema["properties"].items():
            assert SNAKE.match(name), name
            assert prop["type"] in SCALAR_TYPES, (name, prop["type"])
            assert prop["description"]


def test_explainer_metadata_present_on_every_tool():
    for tool in TOOLS:
        explainer = tool["_meta"]["explainer"]
        assert explainer["plain_language"]
        assert explainer["when_to_use"]
        assert explainer["reading_level"] == "ages 12 to 80+"
        assert "Explainer:" in tool["description"]


def test_read_write_separation_marked():
    read_only = {t["name"] for t in TOOLS if t["_meta"]["read_only"]}
    assert read_only == {
        "hivemind_scrub_input",
        "hivemind_query_temporal",
        "hivemind_explain",
    }
    for tool in TOOLS:
        assert tool["annotations"]["readOnlyHint"] is tool["_meta"]["read_only"]


def test_get_tool_unknown_returns_none():
    assert get_tool("hivemind_nope") is None
    assert get_tool(123) is None


# -- stubs ---------------------------------------------------------------

VALID_ARGS = {
    "hivemind_capture_idea": {"content": "x", "source_type": "text",
                              "domain_hint": "coding", "client_id": "c1"},
    "hivemind_scrub_input": {"raw_text": "hello", "strictness_level": "standard"},
    "hivemind_crosshatch_verify": {"candidate_fact": "f", "domain_repo": "coding",
                                   "source_citation": "s", "supersede_id": ""},
    "hivemind_query_temporal": {"query": "q", "temporal_tier": "recent_0_3m",
                                "token_budget": 200, "format_mode": "caveman"},
    "hivemind_spawn_microbot": {"template_name": "digest", "mode_level": "simple",
                                "allowance_limit": 0, "cooldown_sec": 60},
    "hivemind_snapshot_backup": {"destination_target": "supabase",
                                 "schedule_interval": "7d",
                                 "user_handshake_token": "fake-token"},
    "hivemind_explain": {"topic_or_tool_name": "hivemind_capture_idea",
                         "reading_level": "plain"},
    "hivemind_prune_memory": {"target_id_or_rule": "abc", "decay_policy": "stale_after",
                              "human_confirm_token": "fake-token"},
}


def test_tools_call_stubs_return_not_implemented_never_crash():
    for name in EXPECTED_TOOLS:
        resp = handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": name, "arguments": VALID_ARGS[name]},
        })
        assert "error" not in resp, resp
        payload = json.loads(resp["result"]["content"][0]["text"])
        assert payload == not_implemented(name)
        assert payload["status"] == "not_implemented"
        assert payload["block"] == get_tool(name)["_meta"]["block"]
        assert resp["result"]["isError"] is False


def test_tools_call_rejects_nested_arguments():
    resp = handle_request({
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "hivemind_capture_idea",
                   "arguments": {"content": {"nested": True}, "source_type": "text",
                                 "domain_hint": "coding", "client_id": "c1"}},
    })
    assert resp["error"]["code"] == -32602


def test_tools_call_missing_argument_is_an_error_not_a_crash():
    resp = handle_request({
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {"name": "hivemind_scrub_input", "arguments": {"raw_text": "hi"}},
    })
    assert resp["error"]["code"] == -32602


def test_tools_call_unknown_tool_is_an_error():
    resp = handle_request({
        "jsonrpc": "2.0", "id": 4, "method": "tools/call",
        "params": {"name": "hivemind_nope", "arguments": {}},
    })
    assert resp["error"]["code"] == -32602


def test_initialize_and_unknown_method():
    init = handle_request({"jsonrpc": "2.0", "id": 5, "method": "initialize",
                           "params": {}})
    assert init["result"]["serverInfo"]["name"] == "hive-mind-mcp"
    assert init["result"]["capabilities"] == {"tools": {}}
    unknown = handle_request({"jsonrpc": "2.0", "id": 6, "method": "tools/nope"})
    assert unknown["error"]["code"] == -32601
    assert handle_request({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


# -- stdio subprocess ----------------------------------------------------

def _run_stdio(requests):
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    payload = "".join(json.dumps(r) + "\n" for r in requests)
    proc = subprocess.run(
        [sys.executable, "-m", "app.mcp_server", "--stdio"],
        input=payload, capture_output=True, text=True, cwd=repo, timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    return [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]


def test_server_starts_over_stdio_and_lists_all_8_tools():
    responses = _run_stdio([
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "hivemind_explain", "arguments": VALID_ARGS["hivemind_explain"]}},
    ])
    assert len(responses) == 3
    names = [t["name"] for t in responses[1]["result"]["tools"]]
    assert names == EXPECTED_TOOLS
    stub = json.loads(responses[2]["result"]["content"][0]["text"])
    assert stub["status"] == "not_implemented"


# -- store primitives ----------------------------------------------------

@pytest.fixture()
def store(tmp_path):
    s = Store(db_path=str(tmp_path / "test.db"), vault_dir=str(tmp_path / "vault"))
    yield s
    s.close()


def test_sqlite_jsonl_round_trip_including_restart(tmp_path):
    db = str(tmp_path / "round.db")
    vault = str(tmp_path / "vault")
    with Store(db_path=db, vault_dir=vault) as s:
        mid = s.remember("The shop opens at 9am on Saturdays",
                         entities=["shop"], source="test", domain="local")
        assert s.recall("when does the shop open")[0]["id"] == mid
    # Restart: a brand-new Store on the same files must read it back.
    with Store(db_path=db, vault_dir=vault) as s2:
        matches = s2.recall("shop opens Saturday")
        assert [m["id"] for m in matches] == [mid]
        assert matches[0]["text"] == "The shop opens at 9am on Saturdays"
    jsonl = os.path.join(vault, "memories.jsonl")
    assert os.path.exists(jsonl)
    assert any(json.loads(line)["id"] == mid for line in open(jsonl))
    assert os.path.exists(os.path.join(vault, "memories", f"{mid}.md"))


def test_store_round_trip_without_sqlite_vec(tmp_path):
    s = Store(db_path=str(tmp_path / "novec.db"),
              vault_dir=str(tmp_path / "vault"), use_vec=False)
    try:
        assert s.vec_available is False
        mid = s.remember("Fallback recall still works without sqlite-vec")
        assert s.recall("fallback recall")[0]["id"] == mid
    finally:
        s.close()


def test_store_forget_and_stats(store):
    a = store.remember("alpha fact", domain="coding")
    store.remember("beta fact", domain="cooking")
    assert store.memory_stats()["total"] == 2
    assert store.memory_stats()["by_domain"] == {"coding": 1, "cooking": 1}
    assert store.forget(a) is True
    assert store.forget(a) is False
    assert store.recall("alpha") == []
    assert store.memory_stats()["total"] == 1
    with pytest.raises(ValueError):
        store.remember("   ")


def test_store_recall_empty_query_returns_recent(store):
    store.remember("first fact")
    store.remember("second fact")
    assert len(store.recall("", limit=5)) == 2


# -- no-network guard ------------------------------------------------------

def test_no_network_or_secret_code_in_app():
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app_dir = os.path.join(repo, "app")
    for fname in os.listdir(app_dir):
        if not fname.endswith(".py"):
            continue
        src = open(os.path.join(app_dir, fname)).read()
        for banned in ("httpx", "requests.", "urllib.request", "socket.",
                       "META_API_KEY", "SUPABASE_", "sk-", "Bearer "):
            assert banned not in src, (fname, banned)
