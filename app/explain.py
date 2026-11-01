"""Block 6 — Index-Key Explainer (zero jargon, ages 12 to 80+).

Explains any tool, parameter, pillar, setting, or concept in plain
words. Unknown topics never dead-end: they return 1-3 refocus
strategies instead. Reading levels: "plain" (short) or "detailed"
(short + an example). No network, no model — every explanation is a
fixed, reviewed string, so the explainer can never hallucinate one.
"""

from .tools import TOOLS

_PILLARS = {
    "computing-in-memory": (
        "Work where the facts live, instead of copying them back and forth.",
        "The memory store does its work inside SQLite, so a question is "
        "answered where the data already is. Fewer copies moved means "
        "less work and less waiting. Example: recall searches the "
        "database directly instead of loading every note into memory first."),
    "event-driven spiking": (
        "Stay quiet until something changes, then act once.",
        "Nothing polls or spins in the background. The server waits, and "
        "only does work when a new idea arrives or a question is asked. "
        "Example: the MCP server blocks on stdin and exits cleanly on EOF."),
    "extreme sparsity / dynamic routing": (
        "Wake up only the parts a job actually needs.",
        "A cooking question never wakes the coding tools. Only the domain "
        "repo and checks that job needs are activated; everything else "
        "stays dormant. Example: a capture routes to one domain repo, "
        "not all of them."),
    "continuous local learning": (
        "Learn locally, keep the history, never silently overwrite.",
        "State changes on this machine, with provenance and a changelog. "
        "An old fact is marked superseded, never deleted in secret. "
        "Example: cross-hatch verify appends a Conflict Diff & Merge entry."),
    "accessibility": (
        "Everyone can use it, from the first version — not added later.",
        "The Sensory Suite ships in v1: focus mode, safe motion, readable "
        "font, high contrast, typed colour-blind palettes including pure "
        "grayscale, light theme, and simplified view. Every screen and "
        "graph node has a label a screen reader can read, and meaning is "
        "never carried by colour alone."),
    "security": (
        "Secrets are stopped before they reach storage or any model.",
        "The Burn-After-Reading gate scrubs text locally before any disk "
        "write or API call, and destructive actions need a human "
        "confirmation token. Example: an API key in a note is replaced "
        "with a redaction marker and only the count is recorded."),
}

_CONCEPTS = {
    "caveman": (
        "Short, token-cheap shorthand for a remembered fact.",
        "Caveman drops filler words and keeps names, numbers, and content "
        "words, so past context costs far fewer tokens when it is injected "
        "into a new conversation. Example: a long note about shop hours "
        "becomes 'shop opens 9AM Saturdays'."),
    "crosshatch": (
        "Checking a new fact against what is already known, twice over.",
        "Cross-hatch polls a fact against the 6 Pillars and against stored "
        "facts in the same domain. A contradiction is reported, never "
        "silently overwritten; replacing it needs an explicit supersede."),
    "scrubber": (
        "The local gate that removes secrets before anything is stored.",
        "The scrubber uses fixed patterns plus an entropy check, runs in "
        "the local process, and returns only the cleaned text and counts "
        "of what it trapped. Example: an API key becomes [REDACTED:API_KEY]."),
    "temporal": (
        "Three time buckets: recent, a while ago, and a long time ago.",
        "Recent covers the last 3 months, warm covers 3-6 months, and "
        "archival covers older memories. Asking one bucket keeps answers "
        "small and relevant."),
    "token ekonomi": (
        "A meter showing how many tokens a short answer saved.",
        "It compares the full text with the Caveman shorthand actually "
        "injected, and reports raw tokens, injected tokens, and the "
        "saving. Token counts are estimates (characters / 4)."),
    "microbot": (
        "A tiny helper bot built from a template, 8 to 14 kilobytes.",
        "Simple Mode makes a morning digest bot; Pro Mode makes an "
        "allowance-gated sentinel that refuses to act without a spending "
        "limit and a cooldown. Pro Mode never trades live."),
    "snapshot": (
        "A backup bundle that proves itself by being checked back.",
        "A snapshot zips the database, JSONL vault, and notes, uploads "
        "the bundle, downloads it again, and only reports success if the "
        "hashes match. A failed check is never called backed up."),
    "supabase": (
        "The cloud backup shelf. Local storage stays the source of truth.",
        "Supabase only holds snapshot bundles and a mirror of verified "
        "facts. If it is not configured, everything still works locally."),
}

_SETTINGS = {
    "focus mode": "Hides distractions so one thing is on screen at a time. Accessibility Suite.",
    "safe motion": "Stops animations and transitions. Accessibility Suite.",
    "readable font": "Switches to a clearer font and steadier spacing. Accessibility Suite.",
    "high contrast": "Stronger contrast between text and background. Accessibility Suite.",
    "color blind support": "Re-colours the interface for a chosen colour-vision type, including pure grayscale. Accessibility Suite.",
    "light theme": "Light background, dark text. Accessibility Suite.",
    "simplified view": "Hides images and extra detail. Accessibility Suite.",
    "letter spacing": "Space between letters. Kept moderate by default: too wide breaks letter grouping for dyslexic readers. Accessibility Suite.",
    "graph metaphor": "Which picture the knowledge graph uses: nebula, tree of life, mandala, or road map. Regular Settings — not an access need.",
    "token budget": "The maximum tokens a query answer may use. Regular Settings.",
    "snapshot schedule": "How often backups run, or Sync Now. Regular Settings.",
}


def _find_topic(topic):
    key = (topic or "").strip().lower()
    if not key:
        return None
    for tool in TOOLS:
        if key in tool["name"].lower() or key in tool["name"].replace("hivemind_", ""):
            explainer = tool["_meta"]["explainer"]
            return (
                explainer["plain_language"],
                explainer["plain_language"] + " " + explainer["when_to_use"],
            )
    for name, (plain, detailed) in _PILLARS.items():
        if key in name or name in key:
            return plain, detailed
    for name, (plain, detailed) in _CONCEPTS.items():
        if key in name or name in key:
            return plain, detailed
    for name, text in _SETTINGS.items():
        if key in name or name in key:
            return text, text
    return None


def explain(topic_or_tool_name, reading_level="plain"):
    """Explain a topic in plain words. Unknown topics get strategies."""
    level = (reading_level or "plain").strip().lower()
    if level not in ("plain", "detailed"):
        raise ValueError(f"unknown reading_level: {reading_level!r}; use plain or detailed")
    found = _find_topic(topic_or_tool_name)
    if found is None:
        return {
            "status": "not_found",
            "topic": topic_or_tool_name,
            "explanation": "",
            "strategies": [
                "Try the exact tool name, e.g. hivemind_capture_idea.",
                "Try a pillar name, e.g. accessibility or security.",
                "Ask about a setting by name, e.g. letter spacing or token budget.",
            ],
        }
    plain, detailed = found
    return {
        "status": "ok",
        "topic": topic_or_tool_name,
        "explanation": detailed if level == "detailed" else plain,
        "reading_level": level,
    }
