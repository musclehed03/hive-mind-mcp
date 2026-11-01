"""Block 11 — EXP: local-only points for memory health.

EXP rewards keeping memories healthy. It NEVER rewards API spend:
no points are earned for making a live call, for the number of
calls, or for anything that costs money. Points come only from
healthy-memory actions, and the same points are earned whether the
model endpoint behind a check is cloud or local:

* ``endpoint_attached`` (50): one of the env-gated live endpoints
  was actually configured when a server started — a cloud model
  endpoint and a local endpoint (e.g. Ollama) earn the same 50,
  once per distinct endpoint. "Configured" means the factory in
  ``app/live_clients.py`` would return a live client/adapter for
  it (live flag on + credentials present); merely naming an
  endpoint in a file earns nothing, and no network probe is ever
  made to detect an endpoint.
* ``verified_recall`` (10): a fact passed Cross-Hatch Verify and
  was stored.
* ``contradiction_resolved`` (25): a conflict was settled by an
  explicit supersede (the old fact was replaced on purpose, with
  a diff in the changelog).
* ``snapshot_backed_up`` (15): a snapshot finished with its
  verified callback passing (cloud upload or local-only bundle).

Storage is an append-only JSONL log under the vault dir
(``exp_events.jsonl``), next to the memories mirror. Totals are
recomputed from the log on every read, so totals can never
decrease: there is no delete, no edit, and no spend. EXP is not
an MCP tool, has no leaderboard, touches no network, and costs
nothing. Recording failures must never break the flow that earned
the points: callers wrap ``record_event`` so an EXP error is
swallowed and the tool payload is unaffected.
"""

import json
import os
from datetime import datetime, timezone

POINTS = {
    "endpoint_attached": 50,
    "verified_recall": 10,
    "contradiction_resolved": 25,
    "snapshot_backed_up": 15,
}

EXP_FILENAME = "exp_events.jsonl"

_DEFAULT_META_BASE_URL = "https://api.meta.ai/v1"
_DEFAULT_META_MODEL = "muse-spark-1.3"


def _log_path(vault_dir):
    return os.path.join(vault_dir, EXP_FILENAME)


def _read_events(vault_dir):
    """All well-formed events, oldest first. Bad lines are skipped."""
    path = _log_path(vault_dir)
    events = []
    if not os.path.exists(path):
        return events
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if isinstance(record, dict) and record.get("kind") in POINTS:
                events.append(record)
    return events


def totals(vault_dir):
    """Totals recomputed from the append-only log. Never decreases."""
    by_kind = {kind: 0 for kind in POINTS}
    endpoints = []
    count = 0
    for event in _read_events(vault_dir):
        kind = event["kind"]
        by_kind[kind] += int(event.get("points", POINTS[kind]))
        count += 1
        endpoint = event.get("endpoint")
        if endpoint and endpoint not in endpoints:
            endpoints.append(endpoint)
    return {
        "total": sum(by_kind.values()),
        "by_kind": by_kind,
        "events": count,
        "endpoints": sorted(endpoints),
    }


def record_event(vault_dir, kind, endpoint=None):
    """Append one EXP event. Returns the recomputed totals.

    ``endpoint_attached`` requires a non-empty ``endpoint`` key
    (the endpoint identity, never a credential) and is recorded
    at most once per distinct endpoint: a repeat for the same
    endpoint returns the unchanged totals with ``recorded`` False.
    Every other kind is recorded every time.
    """
    if kind not in POINTS:
        raise ValueError(f"unknown EXP kind: {kind!r}")
    if kind == "endpoint_attached":
        if not endpoint or not str(endpoint).strip():
            raise ValueError("endpoint_attached requires a non-empty endpoint")
        endpoint = str(endpoint).strip()
        for event in _read_events(vault_dir):
            if (event.get("kind") == "endpoint_attached"
                    and event.get("endpoint") == endpoint):
                result = totals(vault_dir)
                result["recorded"] = False
                return result
    else:
        endpoint = None
    record = {
        "event": "exp",
        "kind": kind,
        "points": POINTS[kind],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if endpoint is not None:
        record["endpoint"] = endpoint
    os.makedirs(os.path.abspath(vault_dir), exist_ok=True)
    with open(_log_path(vault_dir), "a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
    result = totals(vault_dir)
    result["recorded"] = True
    return result


def detect_configured_endpoints():
    """Endpoint identities the live factory would actually use.

    Environment only, no network probe, no credential values: the
    returned keys name the endpoint (base URL + model, or the
    Supabase project URL), never a key. An endpoint counts only
    when the live flag is on and its credentials are present —
    the same presence checks ``app/live_clients.py`` uses — so a
    name in a file, or a live flag without credentials, earns
    nothing.
    """
    endpoints = []
    if os.environ.get("HIVE_MIND_LIVE") != "1":
        return endpoints
    if os.environ.get("META_API_KEY"):
        base_url = (os.environ.get("HIVE_MIND_META_BASE_URL")
                    or _DEFAULT_META_BASE_URL).rstrip("/")
        model = os.environ.get("HIVE_MIND_META_MODEL") or _DEFAULT_META_MODEL
        endpoints.append(f"model-endpoint:{base_url} model {model}")
    if os.environ.get("SUPABASE_URL") and os.environ.get(
            "SUPABASE_SERVICE_ROLE_KEY"):
        endpoints.append(
            "supabase:" + os.environ["SUPABASE_URL"].rstrip("/"))
    return endpoints


def record_startup_endpoints(vault_dir):
    """Record endpoint_attached once per configured endpoint.

    Called once at server start. Never raises: EXP must never
    prevent a server from starting.
    """
    try:
        for endpoint in detect_configured_endpoints():
            try:
                record_event(vault_dir, "endpoint_attached", endpoint=endpoint)
            except (ValueError, OSError):
                continue
    except Exception:
        pass
    return totals(vault_dir)
