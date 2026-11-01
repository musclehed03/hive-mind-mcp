"""Block 2 gate tests: Burn-After-Reading scrubber.

No network, no real secrets. All trapped values below are obviously
fake (sk-fake-0000, test@example.com, 555 numbers, 123-45-6789).
"""

import json

import pytest

from app.dispatch import dispatch_tool
from app.mcp_server import handle_request
from app.scrubber import (
    contains_secret,
    load_protected_names,
    scrub_before_write,
    scrub_text,
    shannon_entropy,
)
from app.store import Store

FAKE_KEY = "sk-fake-000000000000000000000000"
FAKE_GH = "ghp_fake00000000000000000000000000000000"
FAKE_BEARER = "Bearer fake-token-0000000000000000"


def test_short_sk_prefixed_key_spoken_aloud_is_trapped():
    # Demo regression (Block 8 run-through): a short spoken key must
    # be trapped, not stored. Over-trapping sk- shapes is the design.
    from app.scrubber import scrub_text

    result = scrub_text("my API key is sk-demo-trap-me please ignore", "standard")
    assert result["trapped_count"] == 1
    assert "sk-demo-trap-me" not in result["scrubbed_text"]
    assert "[REDACTED:API_KEY]" in result["scrubbed_text"]


def test_fake_api_key_trapped_and_counted():
    result = scrub_text(f"the key is {FAKE_KEY} end")
    assert FAKE_KEY not in result["scrubbed_text"]
    assert FAKE_KEY not in json.dumps(result)
    assert result["trapped_count"] == 1
    assert result["trapped"] == [{"kind": "API_KEY", "count": 1}]
    assert "[REDACTED:API_KEY]" in result["scrubbed_text"]
    assert result["raw_stored"] is False


def test_bearer_and_github_token_trapped():
    result = scrub_text(f"call with {FAKE_BEARER} and {FAKE_GH}")
    kinds = {t["kind"] for t in result["trapped"]}
    assert kinds == {"BEARER", "GITHUB_TOKEN"}
    assert FAKE_BEARER not in result["scrubbed_text"]
    assert FAKE_GH not in result["scrubbed_text"]
    assert result["trapped_count"] == 2


def test_email_phone_ssn_trapped_at_standard_not_lenient():
    text = "reach me at test@example.com or 555-123-4567, ssn 123-45-6789"
    standard = scrub_text(text, "standard")
    assert standard["trapped_count"] == 3
    assert "test@example.com" not in standard["scrubbed_text"]
    assert "123-45-6789" not in standard["scrubbed_text"]
    lenient = scrub_text(text, "lenient")
    # Lenient keeps email/phone but still traps the SSN.
    assert lenient["trapped"] == [{"kind": "SSN", "count": 1}]
    assert "test@example.com" in lenient["scrubbed_text"]


def test_clean_text_passes_unchanged():
    text = "The shop opens at 9am on Saturdays and sells bread."
    result = scrub_text(text)
    assert result["scrubbed_text"] == text
    assert result["trapped_count"] == 0
    assert result["trapped"] == []


def test_secret_assignment_and_credential_url_trapped():
    text = "api_key = fake-secret-value-12345678 and https://user:hunter2@example.com/x"
    result = scrub_text(text, "standard")
    assert "fake-secret-value" not in result["scrubbed_text"]
    assert "hunter2" not in result["scrubbed_text"]
    assert result["trapped_count"] >= 2


def test_high_entropy_token_only_in_strict():
    token = "aB3dE5fG7hJ9kL2mN4pQ6rS8tU0vW1xY3z"
    assert shannon_entropy(token) > 4.2
    text = f"note {token} done"
    assert scrub_text(text, "standard")["trapped_count"] == 0
    strict = scrub_text(text, "strict")
    assert strict["trapped_count"] == 1
    assert strict["trapped"][0]["kind"] == "HIGH_ENTROPY_SECRET"
    assert token not in strict["scrubbed_text"]


def test_protected_name_only_when_supplied():
    text = "Jordan Sheire called about the meeting"
    assert scrub_text(text, "strict")["trapped_count"] == 0
    result = scrub_text(text, "strict", protected_names=["Jordan Sheire"])
    assert "Jordan Sheire" not in result["scrubbed_text"]
    assert result["trapped"] == [{"kind": "PROTECTED_NAME", "count": 1}]


def test_unknown_strictness_is_an_error():
    with pytest.raises(ValueError):
        scrub_text("hello", "extreme")


def test_audit_never_contains_trapped_values():
    text = f"{FAKE_KEY} test@example.com 123-45-6789"
    result = scrub_text(text)
    blob = json.dumps(result)
    for secret in (FAKE_KEY, "test@example.com", "123-45-6789"):
        assert secret not in blob


def test_load_protected_names_missing_file_is_empty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert load_protected_names() == []


def test_scrub_before_write_only_scrubbed_text_reaches_store(tmp_path):
    # The Block 2 gate: scrub runs before capture writes to disk, tested
    # against a temporary store standing in for the capture path.
    store = Store(db_path=str(tmp_path / "s.db"), vault_dir=str(tmp_path / "vault"))
    try:
        result = scrub_before_write(f"idea: use {FAKE_KEY} for the demo")
        mid = store.remember(result["scrubbed_text"], domain="coding")
        assert store.recall("demo")[0]["id"] == mid
        assert FAKE_KEY not in store.recall("demo")[0]["text"]
        vault_text = open(tmp_path / "vault" / "memories.jsonl").read()
        assert FAKE_KEY not in vault_text
        assert result["trapped_count"] == 1
    finally:
        store.close()


def test_contains_secret_helper():
    assert contains_secret(f"key {FAKE_KEY}") is True
    assert contains_secret("plain bread note") is False


def test_scrub_tool_via_mcp_dispatch():
    payload, is_error = dispatch_tool(
        "hivemind_scrub_input",
        {"raw_text": f"key {FAKE_KEY}", "strictness_level": "standard"},
        store=None,
    )
    assert is_error is False
    assert payload["status"] == "ok"
    assert payload["trapped_count"] == 1
    assert FAKE_KEY not in payload["scrubbed_text"]


def test_scrub_tool_unknown_strictness_is_error_over_stdio():
    resp = handle_request({
        "jsonrpc": "2.0", "id": 9, "method": "tools/call",
        "params": {"name": "hivemind_scrub_input",
                   "arguments": {"raw_text": "hi", "strictness_level": "extreme"}},
    })
    assert resp["result"]["isError"] is True
    payload = json.loads(resp["result"]["content"][0]["text"])
    assert payload["status"] == "error"
