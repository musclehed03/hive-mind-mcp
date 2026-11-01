"""Block 3 gate tests: capture + temporal + Caveman (fake Meta only)."""

import json
import os
from datetime import datetime, timedelta, timezone

import pytest

from app.capture import (
    _CURSORS,
    capture_idea,
    extract_entities,
    fake_client_calls,
    query_temporal,
    route_domain,
)
from app.caveman import (
    compress,
    ekonomi_meter,
    estimate_tokens,
    temporal_bucket,
)
from app.dispatch import dispatch_tool
from app.fake_meta import FakeMetaClient
from app.store import Store


@pytest.fixture()
def store(tmp_path):
    s = Store(db_path=str(tmp_path / "t.db"), vault_dir=str(tmp_path / "vault"))
    yield s
    s.close()


def _ago(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


# -- temporal buckets ------------------------------------------------------

def test_temporal_buckets_1_day_4_months_9_months():
    assert temporal_bucket(_ago(1)) == "recent_0_3m"
    assert temporal_bucket(_ago(120)) == "warm_3_6m"
    assert temporal_bucket(_ago(270)) == "archival_6m_plus"
    assert temporal_bucket("not-a-date") == "recent_0_3m"


def test_capture_routes_to_domain_and_keeps_cross_domain(store):
    _CURSORS.clear()
    result = capture_idea(
        "Refactor the python server code while dinner cooks in the kitchen",
        "text", "coding", "client-1", store)
    assert result["domain"] == "coding"
    assert result["cross_domains"] == ["cooking"]
    mem = store.get_memory(result["memory_id"])
    assert mem["provenance"]["cross_domains"] == ["cooking"]
    assert mem["provenance"]["source_type"] == "text"


def test_capture_without_hint_infers_domain_and_general_fallback(store):
    assert capture_idea("bake bread at home", "text", "", "c1", store)["domain"] == "general"
    assert capture_idea("fix the docker bug", "text", "", "c1", store)["domain"] == "coding"


def test_capture_scrubs_secret_before_storage(store):
    fake = "sk-fake-000000000000000000000000"
    result = capture_idea(f"the demo key is {fake}", "text", "", "c1", store)
    assert result["trapped_count"] == 1
    mem = store.get_memory(result["memory_id"])
    assert fake not in mem["text"]
    assert fake not in open(os.path.join(store.vault_dir, "memories.jsonl")).read()


def test_capture_rejects_empty_and_unknown_source(store):
    with pytest.raises(ValueError):
        capture_idea("   ", "text", "", "c1", store)
    with pytest.raises(ValueError):
        capture_idea("hello", "telepathy", "", "c1", store)


def test_extract_entities_keeps_names_and_numbers():
    assert extract_entities("Met Day at the Shop on 9am Saturday") == ["Met Day", "Shop", "Saturday"]


# -- caveman / meter -------------------------------------------------------

def test_caveman_shorter_than_prose_and_keeps_entities():
    prose = "I really need to remember that the shop opens at 9am on Saturdays and sells fresh bread."
    short = compress(prose)
    assert len(short) < len(prose)
    assert "9am" in short or "Saturdays" in short
    assert compress("Bread.") == "Bread"  # shorthand drops punctuation


def test_ekonomi_meter_positive_saving():
    prose = "I really need to remember that the shop opens at 9am on Saturdays."
    meter = ekonomi_meter(prose, compress(prose))
    assert meter["raw_tokens"] > meter["injected_tokens"]
    assert meter["tokens_saved"] > 0
    assert meter["saved_pct"] > 0


def test_estimate_tokens_empty_is_zero():
    assert estimate_tokens("") == 0
    assert estimate_tokens("hello world") == 3


# -- query -----------------------------------------------------------------

def _seed(store):
    capture_idea("The shop opens at 9am on Saturdays", "text", "", "c1", store)
    capture_idea("The shop sells fresh bread on Saturdays", "text", "", "c1", store)
    # Backfilled older facts, created_at overridden for honest tiers.
    store.remember("Winter shop market ran in December with hot soup",
                   domain="general", created_at=_ago(120))
    store.remember("First shop opened years ago with a tiny oven",
                   domain="general", created_at=_ago(270))


def test_query_returns_caveman_within_budget_and_meter(store):
    _CURSORS.clear()
    _seed(store)
    result = query_temporal("shop Saturdays", "recent_0_3m", 200, "caveman", store)
    assert result["status"] == "ok"
    assert len(result["items"]) == 2
    assert result["meter"]["injected_tokens"] <= 200
    assert result["meter"]["tokens_saved"] >= 0
    assert all("Saturdays" in i["text"] or "shop" in i["text"].lower() for i in result["items"])


def test_query_tier_filtering(store):
    _CURSORS.clear()
    _seed(store)
    warm = query_temporal("shop", "warm_3_6m", 200, "full", store)
    assert [i["text"] for i in warm["items"]] == ["Winter shop market ran in December with hot soup"]
    old = query_temporal("shop", "archival_6m_plus", 200, "full", store)
    assert [i["text"] for i in old["items"]] == ["First shop opened years ago with a tiny oven"]


def test_query_not_found_returns_strategies(store):
    _CURSORS.clear()
    result = query_temporal("quantum zebras", "recent_0_3m", 200, "caveman", store)
    assert result["status"] == "not_found"
    assert result["items"] == []
    assert 1 <= len(result["strategies"]) <= 3


def test_query_pagination_by_file(store):
    _CURSORS.clear()
    _seed(store)
    first = query_temporal("shop", "all", 10, "caveman", store)
    assert first["more_available"] is True
    assert os.path.exists(first["page_file"])
    page_data = json.load(open(first["page_file"]))
    assert len(page_data["items"]) == 4
    second = query_temporal("shop", "all", 10, "caveman-next", store)
    assert len(second["items"]) >= 1
    assert {i["id"] for i in first["items"]} & {i["id"] for i in second["items"]} == set()


def test_query_rejects_bad_tier_budget_mode(store):
    with pytest.raises(ValueError):
        query_temporal("q", "yesterday", 100, "caveman", store)
    with pytest.raises(ValueError):
        query_temporal("q", "recent_0_3m", 0, "caveman", store)
    with pytest.raises(ValueError):
        query_temporal("q", "recent_0_3m", 100, "telepathy", store)


def test_fake_client_records_calls_and_is_not_live():
    client = FakeMetaClient()
    assert client.call_count == 0
    out = client.verify("plain fact", "coding")
    assert out["live"] is False
    assert out["verdict"] == "consistent"
    assert client.call_count == 1
    assert client.calls[0]["model"].endswith("-fake")


def test_no_real_network_in_fake_client():
    import app.fake_meta as mod
    import inspect

    src = inspect.getsource(mod)
    for banned in ("socket", "urllib", "requests", "httpx", "http.client"):
        assert banned not in src


def test_capture_and_query_via_dispatch(store):
    _CURSORS.clear()
    payload, err = dispatch_tool("hivemind_capture_idea", {
        "content": "The library opens at 10am on Sundays", "source_type": "text",
        "domain_hint": "", "client_id": "c1"}, store=store)
    assert err is False and payload["status"] == "ok"
    payload2, err2 = dispatch_tool("hivemind_query_temporal", {
        "query": "library Sundays", "temporal_tier": "recent_0_3m",
        "token_budget": 200, "format_mode": "caveman"}, store=store)
    assert err2 is False and payload2["status"] == "ok"
    assert len(payload2["items"]) == 1
    assert fake_client_calls() >= 1
