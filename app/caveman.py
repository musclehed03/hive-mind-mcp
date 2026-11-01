"""Block 3 — Caveman Shorthand + Token Ekonomi Meter (local, no LLM).

Caveman shorthand is a deterministic local compression: filler words
are dropped, entities (capitalised words, numbers, dates) and content
words are kept, and the result is never longer than the input. It is
not a model summary and never invents facts — every kept word comes
from the stored text.

Token counts are estimates, documented as such: tokens ~= characters
/ 4, the standard rough heuristic for English text. The meter reports
raw vs injected counts and the saving; it never claims exact model
tokenisation.
"""

import re
from datetime import datetime, timezone

# Small, fixed stopword list. Domain words, names, numbers, and
# capitalised words are never dropped.
_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "i", "you", "he", "she", "it", "we", "they", "my", "your", "his",
    "her", "its", "our", "their", "this", "that", "these", "those",
    "and", "or", "but", "so", "of", "to", "in", "on", "at", "for",
    "with", "by", "from", "as", "about", "into", "over", "after",
    "before", "please", "just", "really", "very", "also", "then",
    "there", "here", "when", "where", "which", "who", "whom", "what",
    "have", "has", "had", "do", "does", "did", "will", "would",
    "should", "could", "can", "may", "might", "am", "an",
}

TIERS = ("recent_0_3m", "warm_3_6m", "archival_6m_plus")


def estimate_tokens(text):
    """Rough token estimate: ceil(chars / 4), 0 for empty text."""
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def temporal_bucket(created_at_iso, now=None):
    """3-tier temporal bucket from an ISO created_at timestamp.

    recent_0_3m: age <= ~90 days. warm_3_6m: <= ~180 days.
    archival_6m_plus: older. Unparseable timestamps bucket as recent
    rather than being silently dropped.
    """
    now = now or datetime.now(timezone.utc)
    try:
        created = datetime.fromisoformat(created_at_iso.replace("Z", "+00:00"))
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
    except (ValueError, AttributeError):
        return "recent_0_3m"
    age_days = (now - created).days
    if age_days <= 90:
        return "recent_0_3m"
    if age_days <= 180:
        return "warm_3_6m"
    return "archival_6m_plus"


def compress(text):
    """Caveman shorthand for one fact. Never longer than the input."""
    if not text or not text.strip():
        return ""
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'’\-]*|[^\w\s]", text)
    kept = []
    for word in words:
        if re.fullmatch(r"[^\w\s]", word):
            continue
        if word[0].isupper() or any(c.isdigit() for c in word):
            kept.append(word.upper() if len(word) <= 3 else word)
        elif word.lower() not in _STOPWORDS:
            kept.append(word)
    shorthand = " ".join(kept)
    if not shorthand or len(shorthand) >= len(text):
        return text.strip()
    return shorthand


def ekonomi_meter(raw_text, injected_text):
    """Token Ekonomi stats: raw vs injected, saving amount and percent."""
    raw = estimate_tokens(raw_text)
    injected = estimate_tokens(injected_text)
    saved = max(0, raw - injected)
    return {
        "raw_tokens": raw,
        "injected_tokens": injected,
        "tokens_saved": saved,
        "saved_pct": round(100.0 * saved / raw, 1) if raw else 0.0,
    }


def compress_payload(texts):
    """Compress a list of facts and meter the whole payload."""
    raw = "\n".join(texts)
    compressed = [compress(t) for t in texts]
    injected = "\n".join(compressed)
    return {
        "items": compressed,
        "meter": ekonomi_meter(raw, injected),
    }
