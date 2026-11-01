"""Tool dispatch: routes tools/call to the block that implements it.

Implemented tools return real payloads. Tools whose block has not
landed yet return the clear ``not_implemented`` stub from app.tools,
never a crash. Handler-level problems (bad strictness, missing
confirmation token, a refused Pro-mode arm) return a payload with
``status: "error"``; the MCP layer reports those with isError=True.

The store is created lazily once per process from the configured
paths, so the stdio server does not pay for a database it never uses.
Tests pass an explicit store and never touch the process singleton.
"""

import os

from .capture import capture_idea, query_temporal
from .crosshatch import crosshatch_verify
from .explain import explain
from .microbot import spawn_microbot
from .prune import prune_memory
from .scrubber import scrub_text
from .snapshot import snapshot_backup
from .tools import IMPLEMENTED as _IMPLEMENTED_NAMES
from .tools import get_tool, not_implemented

_STORE = None


def get_store():
    """Process-wide Store, created on first use from config paths."""
    global _STORE
    if _STORE is None:
        from .store import Store

        _STORE = Store()
    return _STORE


def _scrub_handler(arguments, store):
    result = scrub_text(
        arguments["raw_text"], arguments["strictness_level"]
    )
    return {
        "status": "ok",
        "scrubbed_text": result["scrubbed_text"],
        "trapped_count": result["trapped_count"],
        "trapped": result["trapped"],
        "strictness_level": result["strictness_level"],
        "raw_stored": False,
    }


def _capture_handler(arguments, store):
    return capture_idea(
        arguments["content"], arguments["source_type"],
        arguments["domain_hint"], arguments["client_id"],
        store if store is not None else get_store(),
    )


def _query_handler(arguments, store):
    return query_temporal(
        arguments["query"], arguments["temporal_tier"],
        arguments["token_budget"], arguments["format_mode"],
        store if store is not None else get_store(),
    )


def _verify_handler(arguments, store):
    return crosshatch_verify(
        arguments["candidate_fact"], arguments["domain_repo"],
        arguments["source_citation"], arguments["supersede_id"],
        store if store is not None else get_store(),
    )


def _prune_handler(arguments, store):
    return prune_memory(
        arguments["target_id_or_rule"], arguments["decay_policy"],
        arguments["human_confirm_token"],
        store if store is not None else get_store(),
    )


def _spawn_handler(arguments, store):
    store = store if store is not None else get_store()
    return spawn_microbot(arguments["template_name"], arguments["mode_level"],
                          arguments["allowance_limit"], arguments["cooldown_sec"],
                          store.vault_dir)


def _explain_handler(arguments, store):
    return explain(arguments["topic_or_tool_name"], arguments["reading_level"])


def _snapshot_handler(arguments, store):
    # No cloud adapter in the MCP server: local-only mode, by design.
    # A live adapter is supplied only by Sonja-side code after the
    # Block 5 live gate, never from this codebase's defaults.
    return snapshot_backup(
        arguments["destination_target"], arguments["schedule_interval"],
        arguments["user_handshake_token"],
        store if store is not None else get_store(),
        adapter=None,
    )


def dispatch_tool(name, arguments, store=None):
    """Dispatch one tool call. Returns (payload_dict, is_error_bool)."""
    tool = get_tool(name)
    if tool is None:
        raise KeyError(f"unknown tool: {name!r}")
    handler = _HANDLERS.get(name)
    if handler is None:
        return not_implemented(name), False
    try:
        # Handlers that need a store call get_store() themselves when
        # passed None, so read-only handlers (scrub) never create one.
        payload = handler(arguments, store)
    except ValueError as exc:
        return {"status": "error", "tool": name, "error": str(exc)}, True
    if isinstance(payload, dict) and payload.get("status") == "error":
        return payload, True
    return payload, False


_HANDLERS = {
    "hivemind_scrub_input": _scrub_handler,
    "hivemind_capture_idea": _capture_handler,
    "hivemind_query_temporal": _query_handler,
    "hivemind_crosshatch_verify": _verify_handler,
    "hivemind_prune_memory": _prune_handler,
    "hivemind_snapshot_backup": _snapshot_handler,
    "hivemind_explain": _explain_handler,
    "hivemind_spawn_microbot": _spawn_handler,
}

# Tools whose handlers exist. The registry in app/tools.py is the
# single source of truth for this set (no circular import).
IMPLEMENTED = frozenset(_IMPLEMENTED_NAMES)
