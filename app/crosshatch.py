"""Block 4 — Cross-Hatch Verify (fake Meta client only, no live calls).

A candidate fact is scrubbed first, then polled against the 6 Pillars
(via the FAKE Meta client — canned, deterministic, no network) and
against stored facts in the same domain repo with a local token
check. Nothing is overwritten silently: on conflict the old fact
stays active until the caller re-issues the call with
``supersede_id`` set, which marks it ``superseded`` and appends a
one-line Conflict Diff & Merge changelog entry.

Every stored fact carries the OKF trust signals (spec section 3):
``sources``, ``generated_by``, ``verified_by``, ``stale_after``,
``status``, ``attested_computation``. ``attested_computation`` names
exactly what computed the verdict — the fake client plus the local
conflict check — so a fake verification is never dressed up as a
live one.

LIVE GATE: UNVERIFIED. No live Meta call has been made from this
codebase; no API key exists here. The Sonja-side commands for the
3-5 live verification calls are in the README (Block 4 live gate).
"""

import re
from datetime import datetime, timedelta, timezone

from .caveman import _STOPWORDS
from .fake_meta import FakeMetaClient
from .scrubber import scrub_before_write

_FAKE_CLIENT = FakeMetaClient()
STALE_AFTER_DAYS = 90


def trust_signals(source_citation, status="verified"):
    """OKF trust signals for one verified fact."""
    stale = (datetime.now(timezone.utc) + timedelta(days=STALE_AFTER_DAYS)).date().isoformat()
    return {
        "sources": [source_citation],
        "generated_by": "hivemind_crosshatch_verify (fake-meta client, no live model)",
        "verified_by": "fake-meta verify + local token-overlap conflict check",
        "stale_after": stale,
        "status": status,
        "attested_computation": (
            "deterministic: scrub pre-gate, canned pillar check, "
            "token-overlap conflict check against stored active facts"
        ),
    }


def _content_tokens(text):
    tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {t for t in tokens if t not in _STOPWORDS}


def _numeric_tokens(text):
    return set(re.findall(r"\d+(?:[.,]\d+)?", text or ""))


def find_conflict(store, candidate_text, domain_repo):
    """First active fact in the domain that contradicts the candidate.

    Conflict = at least 2 shared content tokens AND a differing
    numeric/date token (a changed time, price, or count is the
    commonest real contradiction in stored facts). Returns the memory
    dict or None.
    """
    cand_tokens = _content_tokens(candidate_text)
    cand_nums = _numeric_tokens(candidate_text)
    for mem in store.list_memories(domain=domain_repo, limit=500):
        mem_tokens = _content_tokens(mem["text"])
        if len(cand_tokens & mem_tokens) < 2:
            continue
        if cand_nums and _numeric_tokens(mem["text"]) and cand_nums != _numeric_tokens(mem["text"]):
            return mem
    return None


def crosshatch_verify(candidate_fact, domain_repo, source_citation,
                      supersede_id, store, fake_client=None):
    """Verify, store, supersede, or report a conflict. Never overwrites."""
    if not candidate_fact or not candidate_fact.strip():
        raise ValueError("candidate_fact must not be empty")
    if not source_citation or not source_citation.strip():
        raise ValueError("source_citation must not be empty")
    scrubbed = scrub_before_write(candidate_fact, "standard")
    fact = scrubbed["scrubbed_text"]
    client = fake_client or _FAKE_CLIENT
    check = client.verify(fact, domain_repo)
    if check["verdict"] == "rejected":
        return {
            "status": "rejected",
            "reason": "failed the security pillar in the fake pillar check",
            "pillar_failures": check["pillar_failures"],
            "verified_fact": "",
            "trapped_count": scrubbed["trapped_count"],
        }

    old = None
    if supersede_id:
        old = store.get_memory(supersede_id)
        if old is None:
            raise ValueError(f"supersede_id not found: {supersede_id!r}")
        if old["status"] != "active":
            raise ValueError(f"supersede_id is not active: {supersede_id!r}")

    if old is None:
        # A local conflict is enough to refuse a silent overwrite,
        # whatever the fake client said. The caller decides explicitly
        # by re-issuing with supersede_id.
        conflict = find_conflict(store, fact, domain_repo)
        if conflict is not None:
            return {
                "status": "conflict",
                "conflicting_id": conflict["id"],
                "conflicting_fact": conflict["text"],
                "verified_fact": "",
                "action_required": (
                    "Call again with supersede_id set to the conflicting "
                    "id to replace it, or keep the existing fact."
                ),
                "trapped_count": scrubbed["trapped_count"],
            }

    from .capture import extract_entities

    provenance = trust_signals(source_citation)
    provenance["scrubbed"] = scrubbed["trapped_count"] > 0
    provenance["fake_verdict"] = check["verdict"]
    new_id = store.remember(
        fact, entities=extract_entities(fact), source=source_citation,
        domain=domain_repo, provenance=provenance,
    )
    diff = ""
    if old is not None:
        diff = f"- {old['text']} / + {fact} [Attested]"
        store.supersede(old["id"], new_id, diff)
    verified_fact = f"{fact} [{source_citation}]"
    return {
        "status": "superseded" if old is not None else "verified",
        "memory_id": new_id,
        "verified_fact": verified_fact,
        "provenance": provenance,
        "diff": diff,
        "superseded_id": old["id"] if old is not None else "",
        "trapped_count": scrubbed["trapped_count"],
        "fake_meta_calls": client.call_count,
    }
