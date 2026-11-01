"""Deterministic prune (no assigned game-plan block; pairs with Block 4).

Destructive writes need an explicit human confirmation token. No
token, no deletion — ever. Supported targets:

* a memory id (with decay_policy "manual" or empty) — delete it;
* "stale_after" (target or decay_policy) — purge active memories
  whose provenance stale_after date is in the past;
* "superseded" (target or decay_policy) — purge superseded rows,
  keeping the changelog entries as the audit trail.

Unknown targets/rules are errors, never silent no-ops.
"""

from datetime import datetime, timezone


def _is_expired(memory):
    stale = (memory.get("provenance") or {}).get("stale_after", "")
    if not stale:
        return False
    try:
        stale_dt = datetime.fromisoformat(str(stale).replace("Z", "+00:00"))
        if stale_dt.tzinfo is None:
            stale_dt = stale_dt.replace(tzinfo=timezone.utc)
        return stale_dt < datetime.now(timezone.utc)
    except ValueError:
        try:
            stale_date = datetime.strptime(str(stale), "%Y-%m-%d").replace(tzinfo=timezone.utc)
            return stale_date < datetime.now(timezone.utc)
        except ValueError:
            return False


def prune_memory(target_id_or_rule, decay_policy, human_confirm_token, store):
    """Prune deterministically. Returns deleted ids + counts."""
    if not human_confirm_token or not str(human_confirm_token).strip():
        raise ValueError("human_confirm_token is required: destructive writes need explicit human confirmation")
    rule = (target_id_or_rule or "").strip()
    policy = (decay_policy or "").strip().lower()
    deleted = []

    if rule == "stale_after" or policy == "stale_after":
        for mem in store.list_memories(limit=1000):
            if _is_expired(mem) and store.forget(mem["id"]):
                deleted.append(mem["id"])
        return {"status": "ok", "deleted": deleted, "deleted_count": len(deleted), "rule": "stale_after"}

    if rule == "superseded" or policy == "superseded":
        for mem in store.list_memories(status="superseded", limit=1000):
            if store.forget(mem["id"]):
                deleted.append(mem["id"])
        return {"status": "ok", "deleted": deleted, "deleted_count": len(deleted), "rule": "superseded"}

    mem = store.get_memory(rule)
    if mem is None:
        raise ValueError(f"unknown target_id_or_rule: {rule!r}")
    if store.forget(rule):
        deleted.append(rule)
    return {"status": "ok", "deleted": deleted, "deleted_count": len(deleted), "rule": "manual"}
