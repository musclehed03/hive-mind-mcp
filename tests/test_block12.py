"""Block 12 gate tests: native integrations, easy path.

(a) The live model client takes any OpenAI-compatible base URL /
model from the environment (mocked HTTP only — zero network).
(b) The SSE server speaks the same tools over a real localhost
stream, reusing app.mcp_server.handle_request (no forked logic).
(c) docs/INTEGRATIONS.md exists with literal snippets for every
client/endpoint, and no key-shaped literals anywhere in it.
"""

import http.client
import json
import os
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock

import pytest

from app.live_meta import LiveMetaClient, reset_live_call_budget
from app.tools import TOOLS

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_ENV_VARS = (
    "HIVE_MIND_LIVE", "META_API_KEY", "HIVE_MIND_META_MODEL",
    "HIVE_MIND_META_BASE_URL",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    reset_live_call_budget()
    for name in _ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    yield
    reset_live_call_budget()


class _Resp:
    def __init__(self, body=b"", status=200):
        self._body = body
        self.status = status

    def read(self):
        return self._body

    def close(self):
        pass


def _chat_body():
    payload = {"choices": [{"message": {"content": json.dumps({
        "verdict": "consistent", "pillar_failures": [], "reason": "mocked",
    })}}]}
    return json.dumps(payload).encode("utf-8")


def test_ollama_shaped_base_url_and_model(monkeypatch):
    """Ollama's local root works through the same code path."""
    monkeypatch.setenv("META_API_KEY", "LLM_fake-test")
    monkeypatch.setenv("HIVE_MIND_META_BASE_URL", "http://localhost:11434/v1/")
    monkeypatch.setenv("HIVE_MIND_META_MODEL", "gemma3:4b")
    seen = {}

    def _fake_urlopen(request, timeout=30):
        seen["url"] = request.full_url
        seen["body"] = json.loads(request.data.decode("utf-8"))
        return _Resp(_chat_body())

    with mock.patch("app.live_meta.urllib.request.urlopen", _fake_urlopen):
        client = LiveMetaClient()
        assert client.base_url == "http://localhost:11434/v1"
        assert client.model == "gemma3:4b"
        result = client.verify("The shop opens at 9am", "general")
    assert result["verdict"] == "consistent"
    assert seen["url"] == "http://localhost:11434/v1/chat/completions"
    assert seen["body"]["model"] == "gemma3:4b"


def test_openrouter_shaped_base_url(monkeypatch):
    monkeypatch.setenv("META_API_KEY", "LLM_fake-test")
    monkeypatch.setenv("HIVE_MIND_META_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("HIVE_MIND_META_MODEL", "meta-llama/llama-3.1-8b-instruct")
    seen = {}

    def _fake_urlopen(request, timeout=30):
        seen["url"] = request.full_url
        return _Resp(_chat_body())

    with mock.patch("app.live_meta.urllib.request.urlopen", _fake_urlopen):
        result = LiveMetaClient().verify("The shop opens at 9am", "general")
    assert result["verdict"] == "consistent"
    assert seen["url"] == ("https://openrouter.ai/api/v1/chat/completions")


def test_defaults_still_meta(monkeypatch):
    monkeypatch.setenv("META_API_KEY", "LLM_fake-test")
    client = LiveMetaClient()
    assert client.base_url == "https://api.meta.ai/v1"
    assert client.model == "muse-spark-1.3"


# -- SSE transport ---------------------------------------------------------

def _start_sse_server():
    from app.sse_server import _SSEHandler

    server = ThreadingHTTPServer(("127.0.0.1", 0), _SSEHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _read_event(resp):
    """Read one SSE event (lines until a blank line)."""
    event = None
    data = None
    while True:
        line = resp.readline().decode("utf-8").strip()
        if line == "":
            break
        if line.startswith("event:"):
            event = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            data = line.split(":", 1)[1].strip()
    return event, data


def _post(port, path, payload):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        conn.request("POST", path, body=json.dumps(payload),
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        status = resp.status
        resp.read()
        return status
    finally:
        conn.close()


def test_sse_full_flow_initialize_list_call():
    server = _start_sse_server()
    try:
        port = server.server_address[1]
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        conn.request("GET", "/sse")
        stream = conn.getresponse()
        assert stream.status == 200
        event, endpoint = _read_event(stream)
        assert event == "endpoint"
        assert endpoint.startswith("/messages?session_id=")
        session_path = endpoint

        assert _post(port, session_path, {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {}}) == 202
        event, data = _read_event(stream)
        assert event == "message"
        init = json.loads(data)
        assert init["result"]["protocolVersion"] == "2024-11-05"
        assert init["result"]["serverInfo"]["name"] == "hive-mind-mcp"

        assert _post(port, session_path, {
            "jsonrpc": "2.0", "id": 2, "method": "tools/list"}) == 202
        event, data = _read_event(stream)
        listed = json.loads(data)
        assert len(listed["result"]["tools"]) == 8
        assert {t["name"] for t in listed["result"]["tools"]} == {
            t["name"] for t in TOOLS}

        assert _post(port, session_path, {
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "hivemind_explain",
                       "arguments": {"topic_or_tool_name": "hivemind_capture_idea",
                                     "reading_level": "plain"}}}) == 202
        event, data = _read_event(stream)
        called = json.loads(data)
        assert called["result"]["isError"] is False
        payload = json.loads(called["result"]["content"][0]["text"])
        assert payload["status"] == "ok"

        # Unknown method over SSE: the same -32601 as stdio.
        assert _post(port, session_path, {
            "jsonrpc": "2.0", "id": 4, "method": "nope"}) == 202
        event, data = _read_event(stream)
        assert json.loads(data)["error"]["code"] == -32601
        conn.close()
    finally:
        server.shutdown()
        server.server_close()


def test_sse_unknown_session_and_paths():
    server = _start_sse_server()
    try:
        port = server.server_address[1]
        assert _post(port, "/messages?session_id=doesnotexist", {
            "jsonrpc": "2.0", "id": 1, "method": "ping"}) == 404
        assert _post(port, "/messages", {
            "jsonrpc": "2.0", "id": 1, "method": "ping"}) == 404
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as resp:
            health = json.load(resp)
        assert health["transport"] == "sse"
        with pytest.raises(urllib.error.HTTPError) as excinfo:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/nope", timeout=5)
        assert excinfo.value.code == 404
    finally:
        server.shutdown()
        server.server_close()


def test_sse_reuses_stdio_request_handler():
    with open(os.path.join(REPO, "app", "sse_server.py"), encoding="utf-8") as f:
        src = f.read()
    assert "from .mcp_server import handle_request" in src
    assert src.count("handle_request(") >= 1
    # No forked tool logic: the file must not name any tool handler.
    assert "dispatch_tool" not in src
    assert "hivemind_capture_idea" not in src


def test_sse_server_has_no_banned_network_words():
    # The existing no-network guards scan app/ for these literals;
    # the SSE server uses stdlib http.server only and must stay
    # clean of them (it makes no outbound call of its own).
    with open(os.path.join(REPO, "app", "sse_server.py"), encoding="utf-8") as f:
        src = f.read()
    for banned in ("socket", "urlopen", "urllib", "http.client",
                   "httpx", "requests.", "sk-", "ghp_", "eyJ"):
        assert banned not in src, banned
    assert "http.server" in src


# -- docs -------------------------------------------------------------------

def test_integrations_doc_covers_all_clients_and_endpoints():
    with open(os.path.join(REPO, "docs", "INTEGRATIONS.md"), encoding="utf-8") as f:
        doc = f.read()
    for needle in ("Claude Code", "Claude Desktop", "VS Code", "Ollama",
                   "OpenRouter", "OpenWebUI", "HIVE_MIND_META_BASE_URL",
                   "HIVE_MIND_META_MODEL", "/sse", "hotkey",
                   "ABSOLUTE_PATH_TO_HIVE_MIND_MCP",
                   "claude mcp add", "mcp.json", "11434"):
        assert needle in doc, needle
    assert "LLM_" not in doc, "no key-shaped literals in the doc"
    assert "outstanding" in doc.lower()


def test_env_example_documents_endpoint_options():
    with open(os.path.join(REPO, ".env.example"), encoding="utf-8") as f:
        text = f.read()
    assert "http://localhost:11434/v1" in text
    assert "https://openrouter.ai/api/v1" in text
    assert "8080" in text
