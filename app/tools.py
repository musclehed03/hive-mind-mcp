"""Block 1 tool registry: the 8 settled hivemind_ tools, exact per spec.

Rules from the approved master lock-in spec (section 3), enforced here and
in the tests:

* ``snake_case``, ``hivemind_`` prefix, flat scalar arguments only — no
  nested dicts or lists in any tool's arguments.
* Built-in explainer metadata on every tool: plain-language text a reader
  aged 12 to 80+ can follow, plus when to use it. The explainer lives in
  the tool's ``_meta`` block and in its description.
* Strict read/write separation: ``read_only`` tools never write. Write
  tools are marked write and, where the spec requires it, need a
  human-confirmation token in a later block.

Status: tools return ``not_implemented`` until their block lands, and
never crash. The foundation primitives (remember/recall/forget/
memory_stats in :mod:`app.store`) are wired underneath and tested
directly; the hivemind_ surfaces land in Blocks 2-8. The ``IMPLEMENTED``
set below is the registry of landed tools.
"""

# (name, block, read_only, description, explainer plain language,
#  explainer when-to-use, {arg_name: (json-schema type, description)})
_TOOL_SPECS = [
    (
        "hivemind_capture_idea", 3, False,
        "Ingest text, a voice transcript, or a web-clipper payload into the "
        "Temporary Cache Buffer. The internal scrub_input pre-step runs "
        "before any disk write (Block 2).",
        "Save one idea so Hive-Mind can remember it later, in any client.",
        "Use when you have a thought, note, or clipped page to keep.",
        {
            "content": ("string", "The idea text, voice transcript, or clipper payload."),
            "source_type": ("string", "Where it came from: text, voice, or clipper."),
            "domain_hint": ("string", "Suggested domain repo, e.g. coding or cooking."),
            "client_id": ("string", "Which client sent it."),
        },
    ),
    (
        "hivemind_scrub_input", 2, True,
        "Auditable Burn-After-Reading gate. A zero-cost local regex + "
        "entropy pre-gate traps API keys, tokens, emails, phone numbers, "
        "SSNs, and protected real names before any LLM call, and returns "
        "the scrubbed text plus an audit count of trapped items.",
        "Check text for secrets and private details, and remove them, "
        "before anything is stored or sent anywhere.",
        "Use before saving or sending anything that might contain a secret.",
        {
            "raw_text": ("string", "The text to check and clean."),
            "strictness_level": ("string", "How strict the gate should be."),
        },
    ),
    (
        "hivemind_crosshatch_verify", 4, False,
        "Poll a candidate fact against the 6 Pillars and common sense using "
        "the Meta Llama API. Embeds the 5 OKF Trust Signals, injects the "
        "citation inline after the claim, and on conflict marks the old "
        "fact superseded with a one-line Conflict Diff & Merge entry.",
        "Check a new fact against what is already known, and keep the "
        "version with the better evidence.",
        "Use when a new fact might contradict something already remembered.",
        {
            "candidate_fact": ("string", "The fact to verify."),
            "domain_repo": ("string", "The domain repo to check it against."),
            "source_citation": ("string", "Where the fact came from."),
            "supersede_id": ("string", "Id of the fact this would replace, or empty."),
        },
    ),
    (
        "hivemind_query_temporal", 3, True,
        "Query the 3-tier temporal index (recent_0_3m, warm_3_6m, "
        "archival_6m_plus). Returns ultra-compressed Caveman Shorthand "
        "payloads, file-passing pagination, and Token Ekonomi Meter stats. "
        "On 'not found', returns 1-3 refocus/workaround strategies.",
        "Ask what Hive-Mind remembers, from any time period, in a short "
        "form that costs very few tokens.",
        "Use when you need past context injected into a new conversation.",
        {
            "query": ("string", "What to look for."),
            "temporal_tier": ("string", "recent_0_3m, warm_3_6m, or archival_6m_plus."),
            "token_budget": ("integer", "Maximum tokens the answer may use."),
            "format_mode": ("string", "How the answer should be formatted."),
        },
    ),
    (
        "hivemind_spawn_microbot", 7, False,
        "Spawn an 8KB-14KB downloadable/local micro-agent from the memory "
        "layer. A slider scales Simple Mode (Morning Newspaper/Digest Bot) "
        "to Pro Mode (Allowance-Gated Crypto/DCA Sentinel with cooldown "
        "and slippage guards).",
        "Make a tiny helper bot from a template, for one small job.",
        "Use when you want a small reusable bot instead of a one-off answer.",
        {
            "template_name": ("string", "Which micro-bot template to use."),
            "mode_level": ("string", "Simple Mode or Pro Mode."),
            "allowance_limit": ("number", "Spending allowance limit, 0 for no spending."),
            "cooldown_sec": ("integer", "Cooldown in seconds between actions."),
        },
    ),
    (
        "hivemind_snapshot_backup", 5, False,
        "Weekly snapshot hook (default 7d, tunable, or manual 'Sync Now'). "
        "Dumps an inspectable SQLite/JSONL/Markdown bundle to Google Drive "
        "or Supabase storage with a verified callback hook.",
        "Back up everything Hive-Mind remembers, and prove the backup "
        "is good by checking it back.",
        "Use on schedule, or any time before risky work, with Sync Now.",
        {
            "destination_target": ("string", "Where the snapshot goes: drive or supabase."),
            "schedule_interval": ("string", "How often, e.g. 7d, or 'now' for manual."),
            "user_handshake_token": ("string", "Token proving the user approved this backup."),
        },
    ),
    (
        "hivemind_explain", 6, True,
        "Zero-jargon Index-Key Explainer. Explains any tool, parameter, or "
        "pillar clearly for ages 12 to 80+.",
        "Get a plain-words explanation of any Hive-Mind tool or setting.",
        "Use whenever a name, setting, or result is unclear.",
        {
            "topic_or_tool_name": ("string", "The tool, parameter, or pillar to explain."),
            "reading_level": ("string", "Reading level to aim for, e.g. plain or detailed."),
        },
    ),
    (
        # No game-plan block owns prune yet; the forget primitive it wraps
        # is Block 1, the human-confirmation surface is unassigned. Do not
        # invent a block number for it.
        "hivemind_prune_memory", None, False,
        "Deterministic deletion, stale_after expiration purge, or manual "
        "override. Requires an explicit human-in-the-loop confirmation "
        "token for destructive writes.",
        "Delete old or wrong memories on purpose, with your approval, "
        "never silently.",
        "Use to remove a memory, or purge memories past their expiry.",
        {
            "target_id_or_rule": ("string", "Memory id to delete, or the rule to apply."),
            "decay_policy": ("string", "Which expiry/decay rule to use."),
            "human_confirm_token": ("string", "Token proving the user approved this deletion."),
        },
    ),
]


# Tools whose handler exists in app/dispatch.py. Updated as each block
# lands; every other tool stays "not_implemented" in tools/list.
IMPLEMENTED = {"hivemind_scrub_input", "hivemind_capture_idea",
               "hivemind_query_temporal", "hivemind_crosshatch_verify",
               "hivemind_prune_memory", "hivemind_snapshot_backup",
               "hivemind_explain", "hivemind_spawn_microbot"}


def build_tools():
    """Return the MCP tools/list entries, in spec order."""
    tools = []
    for name, block, read_only, desc, plain, when, args in _TOOL_SPECS:
        tools.append({
            "name": name,
            "description": desc + " Explainer: " + plain,
            "inputSchema": {
                "type": "object",
                "properties": {
                    arg: {"type": arg_type, "description": arg_desc}
                    for arg, (arg_type, arg_desc) in args.items()
                },
                "required": list(args),
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": read_only},
            "_meta": {
                "explainer": {
                    "plain_language": plain,
                    "when_to_use": when,
                    "reading_level": "ages 12 to 80+",
                },
                "read_only": read_only,
                "block": block,
                "status": "implemented" if name in IMPLEMENTED else "not_implemented",
            },
        })
    return tools


TOOLS = build_tools()
TOOL_NAMES = [t["name"] for t in TOOLS]
_TOOL_BY_NAME = {t["name"]: t for t in TOOLS}


def get_tool(name):
    return _TOOL_BY_NAME.get(name)


def not_implemented(tool_name):
    """The Block 1 stub response for a tool whose block has not landed."""
    tool = get_tool(tool_name)
    block = tool["_meta"]["block"] if tool else None
    landing = f"it lands in Block {block}" if block is not None else "its block is not assigned yet"
    return {
        "status": "not_implemented",
        "tool": tool_name,
        "block": block,
        "message": (
            f"{tool_name} is not implemented yet in Block 1; "
            f"{landing}. No state was changed."
        ),
    }
