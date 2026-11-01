"""Block 2 — Burn-After-Reading scrubber (local, zero cost, no network).

Deterministic regex + Shannon entropy pre-gate. It runs BEFORE any disk
write or any LLM call, and it never stores or returns the raw input:
the only outputs are the scrubbed text and an audit of *kinds* and
*counts* of trapped items. Trapped values themselves are never kept,
logged, or echoed back — that is the whole point of Burn-After-Reading
(Pillar 6, Security).

Strictness levels (the tool's ``strictness_level`` argument; no enum is
given in the spec, so these three are the documented contract):
  lenient  — API keys, tokens, Bearer strings, SSNs only.
  standard — lenient + emails, phone numbers, password assignments,
             credential URLs. This is the default.
  strict   — standard + high-entropy tokens + protected real names
             (see below).

Protected real names: guessing names from prose would over-redact, so
names are trapped only when supplied explicitly via ``protected_names``
(a local, never-committed list). The MCP tool reads that list from a
local ``protected_names.txt`` file in the working directory if one
exists, and otherwise traps no names. Without the list, name trapping
is honestly unavailable — the tool never pretends otherwise.
"""

import math
import os
import re
from collections import Counter

LEVELS = ("lenient", "standard", "strict")

# (kind, pattern). Applied in order; each match is replaced with a
# "[REDACTED:<kind>]" placeholder so later passes cannot re-trap the
# placeholder text. These patterns are *detectors*, not secrets: they
# match the *shape* of secrets and contain no real credential values.
_PATTERNS = {
    "lenient": [
        ("BEARER", re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/=]+")),
        ("GITHUB_TOKEN", re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}")),
        ("GITHUB_TOKEN", re.compile(r"github_pat_[A-Za-z0-9_]+")),
        # Any sk- prefixed token of 4+ chars is key-shaped: Burn-After-
        # Reading over-traps rather than risk storing a spoken key.
        # (Demo regression: "sk-demo-trap-me" must be trapped.)
        ("API_KEY", re.compile(r"sk-[A-Za-z0-9\-_]{4,}")),
        ("API_KEY", re.compile(r"LLM_[A-Za-z0-9\-_]{8,}")),
        ("API_KEY", re.compile(r"AKIA[0-9A-Z]{16}")),
        ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ],
    "standard": [
        ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
        ("PHONE", re.compile(
            r"(?:\+\d{1,3}[\s.\-]?)?(?:\(\d{3}\)|\d{3})[\s.\-]?\d{3}[\s.\-]?\d{4}\b")),
        ("PHONE", re.compile(r"\b\d{10}\b")),
        ("SECRET_ASSIGNMENT", re.compile(
            r"(?i)(?:api[_-]?key|apikey|secret|passwd|password|access[_-]?token)"
            r"\s*[:=]\s*['\"]?[^\s'\";]{8,}['\"]?")),
        ("CREDENTIAL_URL", re.compile(r"https?://[^\s]*:[^\s]*@[^\s]*")),
    ],
    "strict": [],
}


def shannon_entropy(text):
    """Shannon entropy in bits per character (0 for empty text)."""
    if not text:
        return 0.0
    counts = Counter(text)
    total = len(text)
    return -sum((c / total) * math.log2(c / total) for c in counts.values())


def _is_high_entropy_token(token):
    """A long token with mixed letters+digits and high per-char entropy.

    Ordinary prose words, URLs, and file paths do not qualify: the
    token must be at least 20 characters, contain both a letter and a
    digit, and exceed 4.2 bits/character. Threshold chosen so English
    words (~3-4 bits/char) never trip it; random tokens (~5+) do.
    """
    if len(token) < 20:
        return False
    if not any(c.isalpha() for c in token) or not any(c.isdigit() for c in token):
        return False
    return shannon_entropy(token) > 4.2


def load_protected_names(path="protected_names.txt"):
    """Read a local protected-names list, one name per line.

    The file is git-ignored and never committed. Missing file means no
    names are trapped. Blank lines and '#' comments are ignored.
    """
    try:
        with open(path, encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip() and not line.startswith("#")]
    except OSError:
        return []


def _normalise_level(strictness_level):
    level = (strictness_level or "standard").strip().lower()
    if level in ("normal", "default"):
        level = "standard"
    if level not in LEVELS:
        raise ValueError(f"unknown strictness_level: {strictness_level!r}; use lenient, standard, or strict")
    return level


def scrub_text(raw_text, strictness_level="standard", protected_names=None):
    """Scrub raw_text. Returns scrubbed text + audit counts only.

    Never returns, stores, or logs the raw input. ``trapped`` lists
    kinds and counts only — no trapped values, no offsets, no lengths
    that could be used to reconstruct a secret.
    """
    if not isinstance(raw_text, str):
        raise TypeError("raw_text must be a string")
    level = _normalise_level(strictness_level)
    counts = Counter()
    text = raw_text

    active = list(_PATTERNS["lenient"])
    if level in ("standard", "strict"):
        active += _PATTERNS["standard"]

    for kind, pattern in active:
        def _repl(match, kind=kind):
            counts[kind] += 1
            return f"[REDACTED:{kind}]"
        text = pattern.sub(_repl, text)

    if level == "strict":
        names = list(protected_names) if protected_names is not None else load_protected_names()
        for name in names:
            if not name:
                continue
            pattern = re.compile(r"\b" + re.escape(name) + r"\b", re.IGNORECASE)
            text, n = pattern.subn("[REDACTED:PROTECTED_NAME]", text)
            if n:
                counts["PROTECTED_NAME"] += n
        # Entropy pass last, over remaining whitespace-separated tokens,
        # skipping placeholders left by the regex passes.
        parts = text.split(" ")
        for i, token in enumerate(parts):
            core = token.strip(".,;:!?()[]{}\"'")
            if token.startswith("[REDACTED"):
                continue
            if _is_high_entropy_token(core):
                counts["HIGH_ENTROPY_SECRET"] += 1
                parts[i] = token.replace(core, "[REDACTED:HIGH_ENTROPY_SECRET]")
        text = " ".join(parts)

    trapped = [{"kind": kind, "count": counts[kind]} for kind in sorted(counts)]
    return {
        "scrubbed_text": text,
        "trapped_count": sum(counts.values()),
        "trapped": trapped,
        "strictness_level": level,
        "raw_stored": False,
    }


def scrub_before_write(raw_text, strictness_level="standard", protected_names=None):
    """The capture pre-step: scrub, and only the scrubbed text may be stored.

    Returns the scrub result dict. Callers must store
    ``result["scrubbed_text"]`` and nothing else from the raw input.
    This is the callable Block 3's capture_idea uses before any disk
    write; Block 2 tests it against a fake/temporary store.
    """
    return scrub_text(raw_text, strictness_level, protected_names)


def contains_secret(text, strictness_level="strict", protected_names=None):
    """True if scrubbing would trap anything. Values are never returned."""
    return scrub_text(text, strictness_level, protected_names)["trapped_count"] > 0
