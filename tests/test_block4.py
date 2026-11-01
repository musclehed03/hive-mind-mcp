"""Block 4 gate tests: cross-hatch verify + prune (fake Meta only)."""

import pytest

from app.crosshatch import crosshatch_verify, find_conflict, trust_signals
from app.dispatch import dispatch_tool
from app.fake_meta import FakeMetaClient
from app.prune import prune_memory
from app.store import Store


@pytest.fixture()
def store(tmp_path):
    s = Store(db_path=str(tmp_path / "v.db"), vault_dir=str(tmp_path / "vault"))
    yield s
    s.close()


def _verify(store, fact, domain="coding", citation="test notes", supersede=""):
    return crosshatch_verify(fact, domain, citation, supersede, store)


# -- trust signals ---------------------------------------------------------

def test_trust_signals_carry_all_okf_keys():
    signals = trust_signals("my notes")
    for key in ("sources", "generated_by", "verified_by", "stale_after",
                "status", "attested_computation"):
        assert signals[key]
    assert signals["sources"] == ["my notes"]
    assert "fake" in signals["generated_by"]


def test_verified_fact_carries_inline_citation_and_provenance(store):
    result = _verify(store, "The shop opens at 9am on Saturdays", "general", "shop notes")
    assert result["status"] == "verified"
    assert result["verified_fact"] == "The shop opens at 9am on Saturdays [shop notes]"
    mem = store.get_memory(result["memory_id"])
    assert mem["provenance"]["sources"] == ["shop notes"]
    assert mem["provenance"]["status"] == "verified"
    assert mem["status"] == "active"


def test_rejected_fact_is_not_stored(store):
    result = _verify(store, "This unsafe plan bypasses all checks", "coding", "notes")
    assert result["status"] == "rejected"
    assert store.memory_stats()["total"] == 0


def test_conflict_refuses_silent_overwrite(store):
    first = _verify(store, "The meeting starts at 10am on Monday", "general", "calendar")
    assert first["status"] == "verified"
    clash = _verify(store, "The meeting starts at 2pm on Monday", "general", "calendar v2")
    assert clash["status"] == "conflict"
    assert clash["conflicting_id"] == first["memory_id"]
    assert store.get_memory(first["memory_id"])["status"] == "active"
    assert store.memory_stats()["active"] == 1


def test_supersede_marks_old_and_writes_diff(store):
    first = _verify(store, "The meeting starts at 10am on Monday", "general", "calendar")
    second = _verify(store, "The meeting starts at 2pm on Monday", "general",
                     "calendar v2", supersede=first["memory_id"])
    assert second["status"] == "superseded"
    assert second["superseded_id"] == first["memory_id"]
    assert "- The meeting starts at 10am on Monday / + The meeting starts at 2pm on Monday [Attested]" == second["diff"]
    old = store.get_memory(first["memory_id"])
    assert old["status"] == "superseded"
    assert old["superseded_by"] == second["memory_id"]
    assert store.changelog()[0]["diff"] == second["diff"]
    # Recall only returns the active, new fact.
    assert [m["id"] for m in store.list_memories()] == [second["memory_id"]]


def test_supersede_unknown_or_inactive_id_is_an_error(store):
    with pytest.raises(ValueError):
        _verify(store, "New fact here", "general", "notes", supersede="nope")
    first = _verify(store, "Old fact at 9am today", "general", "notes")
    _verify(store, "New fact at 5pm today", "general", "notes", supersede=first["memory_id"])
    with pytest.raises(ValueError):
        _verify(store, "Third fact at 7pm today", "general", "notes",
                supersede=first["memory_id"])


def test_verify_scrubs_secret_before_storage(store):
    fake = "sk-fake-000000000000000000000000"
    result = _verify(store, f"The key is {fake} for the demo", "coding", "notes")
    assert result["trapped_count"] == 1
    assert fake not in store.get_memory(result["memory_id"])["text"]


def test_verify_requires_fact_and_citation(store):
    with pytest.raises(ValueError):
        _verify(store, "   ", "coding", "notes")
    with pytest.raises(ValueError):
        _verify(store, "A fact", "coding", "")


def test_fake_client_is_used_and_counted(store):
    client = FakeMetaClient()
    _verify(store, "A plain fact about bread", "cooking", "notes")
    result = crosshatch_verify("Another plain fact about bread", "cooking",
                               "notes", "", store, fake_client=client)
    assert client.call_count == 1
    assert result["fake_meta_calls"] == 1


def test_find_conflict_needs_shared_tokens_and_differing_number(store):
    _verify(store, "The shop opens at 9am on Saturdays", "general", "notes")
    assert find_conflict(store, "The shop opens at 9am on Saturdays", "general") is None
    assert find_conflict(store, "The shop opens at 10am on Saturdays", "general") is not None
    assert find_conflict(store, "Something entirely different", "general") is None


# -- prune -----------------------------------------------------------------

def test_prune_requires_confirmation_token(store):
    mid = store.remember("Delete me please")
    with pytest.raises(ValueError):
        prune_memory(mid, "manual", "", store)
    assert store.get_memory(mid) is not None


def test_prune_by_id(store):
    mid = store.remember("Delete me please")
    result = prune_memory(mid, "manual", "user-said-yes", store)
    assert result == {"status": "ok", "deleted": [mid], "deleted_count": 1, "rule": "manual"}
    assert store.get_memory(mid) is None


def test_prune_stale_after_and_superseded(store):
    expired = store.remember("Old expired fact", provenance={"stale_after": "2020-01-01"})
    fresh = store.remember("Fresh fact", provenance={"stale_after": "2999-01-01"})
    result = prune_memory("stale_after", "stale_after", "yes", store)
    assert result["deleted"] == [expired]
    assert store.get_memory(fresh) is not None
    # Supersede one, then purge superseded rows.
    first = _verify(store, "Event at 10am Monday", "general", "notes")
    _verify(store, "Event at 3pm Monday", "general", "notes", supersede=first["memory_id"])
    purged = prune_memory("superseded", "superseded", "yes", store)
    assert purged["deleted"] == [first["memory_id"]]
    assert store.changelog()  # audit trail survives the purge


def test_prune_unknown_target_is_an_error(store):
    with pytest.raises(ValueError):
        prune_memory("no-such-id", "manual", "yes", store)


def test_verify_and_prune_via_dispatch(store):
    payload, err = dispatch_tool("hivemind_crosshatch_verify", {
        "candidate_fact": "The library opens at 10am", "domain_repo": "general",
        "source_citation": "notes", "supersede_id": ""}, store=store)
    assert err is False and payload["status"] == "verified"
    payload2, err2 = dispatch_tool("hivemind_prune_memory", {
        "target_id_or_rule": payload["memory_id"], "decay_policy": "manual",
        "human_confirm_token": "yes"}, store=store)
    assert err2 is False and payload2["deleted_count"] == 1
