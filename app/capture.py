"""Block 3 — Capture + Temporal Query (local, fake Meta only).

Capture runs the Block 2 scrub pre-step before any disk write, routes
the idea to a domain repo, and keeps cross-domain mentions in the
provenance so a cross-domain idea is never lost to one repo.

Temporal query reads the 3-tier index, returns Caveman shorthand
within the caller's token budget, and paginates by file: the full
result set is written to a page file under the vault, and the
"caveman-next" format mode reads the next page from it. No network,
no live model — the fake client is only an audit counter here; the
compression itself is the local Caveman compressor.
"""

import hashlib
import json
import os
import re

from .caveman import TIERS, compress, ekonomi_meter, estimate_tokens, temporal_bucket
from .fake_meta import FakeMetaClient
from .scrubber import scrub_before_write

_DOMAIN_KEYWORDS = {
    "coding": ("code", "coding", "python", "github", "bug", "server", "api", "docker"),
    "cooking": ("cook", "cooking", "recipe", "dinner", "meal", "kitchen"),
    "music": ("song", "music", "playlist", "audio", "mix"),
    "finance": ("crypto", "money", "budget", "price", "spend", "allowance"),
}

# In-process pagination cursors: (query, tier) -> {"page_file": path, "offset": int}
_CURSORS = {}

_FAKE_CLIENT = FakeMetaClient()


def fake_client_calls():
    """How many fake Meta calls have been made (audit only)."""
    return _FAKE_CLIENT.call_count


def extract_entities(text):
    """Capitalised word sequences + numbers, de-duplicated, order kept."""
    found = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", text or "")
    seen = []
    for item in found:
        # A lone sentence-initial article is not an entity.
        if " " not in item and item.lower() in ("the", "a", "an", "i"):
            continue
        if item not in seen:
            seen.append(item)
    return seen


def route_domain(domain_hint, content):
    """Primary domain + cross-domain mentions, from hint + keywords."""
    hint = (domain_hint or "").strip().lower()
    lowered = content.lower()
    domains = []
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        if any(k in lowered for k in keywords):
            domains.append(domain)
    if hint:
        primary = hint
        if hint not in domains:
            domains.insert(0, hint)
    elif domains:
        primary = domains[0]
    else:
        primary = "general"
    cross = [d for d in domains if d != primary]
    return primary, cross


def capture_idea(content, source_type, domain_hint, client_id, store):
    """Capture one idea. Only scrubbed text ever reaches the store."""
    if not content or not content.strip():
        raise ValueError("content must not be empty")
    if source_type not in ("text", "voice", "clipper"):
        raise ValueError(f"unknown source_type: {source_type!r}")
    source = source_type
    body = content
    if source_type == "clipper":
        # Clipper payload format (Block 7): first line "URL: <url>".
        lines = content.splitlines()
        if lines and lines[0].lower().startswith("url:"):
            source = lines[0][4:].strip() or source_type
            body = "\n".join(lines[1:]).strip() or body
    scrubbed = scrub_before_write(body, "standard")
    primary, cross = route_domain(domain_hint, scrubbed["scrubbed_text"])
    entities = extract_entities(scrubbed["scrubbed_text"])
    provenance = {
        "source_type": source_type,
        "client_id": client_id,
        "cross_domains": cross,
        "scrubbed": scrubbed["trapped_count"] > 0,
    }
    mid = store.remember(
        scrubbed["scrubbed_text"], entities=entities, source=source,
        domain=primary, provenance=provenance,
    )
    return {
        "status": "ok",
        "memory_id": mid,
        "domain": primary,
        "cross_domains": cross,
        "entities": entities,
        "trapped_count": scrubbed["trapped_count"],
        "trapped": scrubbed["trapped"],
    }


def _matching(store, query, tier):
    """Active memories in the tier, best lexical match first."""
    query_tokens = set(re.findall(r"[a-z0-9]+", (query or "").lower()))
    scored = []
    for mem in store.list_memories(limit=500):
        if tier and tier != "all":
            if temporal_bucket(mem["created_at"]) != tier:
                continue
        overlap = len(query_tokens & set(re.findall(r"[a-z0-9]+", mem["text"].lower())))
        if query_tokens and overlap == 0:
            continue
        scored.append((overlap, mem))
    scored.sort(key=lambda item: (item[0], item[1]["created_at"]), reverse=True)
    return [mem for _, mem in scored]


def _write_page_file(store, query, tier, items):
    """File-passing pagination: full compressed set in one vault file."""
    key = hashlib.sha256(f"{query}|{tier}".encode()).hexdigest()[:16]
    pages_dir = os.path.join(store.vault_dir, "pages")
    os.makedirs(pages_dir, exist_ok=True)
    path = os.path.join(pages_dir, f"{key}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"query": query, "tier": tier, "items": items}, f)
    return path


def query_temporal(query, temporal_tier, token_budget, format_mode, store):
    """Query the temporal index. Returns Caveman payload + meter."""
    if temporal_tier not in TIERS and temporal_tier not in ("", "all"):
        raise ValueError(f"unknown temporal_tier: {temporal_tier!r}")
    if not isinstance(token_budget, int) or isinstance(token_budget, bool) or token_budget <= 0:
        raise ValueError("token_budget must be a positive integer")
    tier = temporal_tier or "all"
    mode = (format_mode or "caveman").strip().lower()

    if mode == "caveman-next":
        cursor = _CURSORS.get((query, tier))
        if not cursor:
            return {"status": "ok", "items": [], "more_available": False,
                    "meter": ekonomi_meter("", ""), "page_file": ""}
        page_file = cursor["page_file"]
        with open(page_file, encoding="utf-8") as f:
            all_items = json.load(f)["items"]
        offset = cursor["offset"]
    else:
        if mode not in ("caveman", "full"):
            raise ValueError(f"unknown format_mode: {format_mode!r}")
        matches = _matching(store, query, tier)
        # Record a fake-client audit call: compression is local, but the
        # call counter proves the query path touched only the fake.
        _FAKE_CLIENT.compress("\n".join(m["text"] for m in matches))
        all_items = []
        for mem in matches:
            text = compress(mem["text"]) if mode == "caveman" else mem["text"]
            all_items.append({
                "id": mem["id"], "text": text, "full_text": mem["text"],
                "domain": mem["domain"], "created_at": mem["created_at"],
                "temporal_bucket": temporal_bucket(mem["created_at"]),
                "source": mem["source"],
            })
        page_file = _write_page_file(store, query, tier, all_items)
        offset = 0

    # Fit one page inside the token budget (at least one item if any).
    page, used = [], 0
    idx = offset
    while idx < len(all_items):
        cost = estimate_tokens(all_items[idx]["text"])
        if page and used + cost > token_budget:
            break
        page.append(all_items[idx])
        used += cost
        idx += 1
    more = idx < len(all_items)
    _CURSORS[(query, tier)] = {"page_file": page_file, "offset": idx}

    if not page and offset == 0:
        return {
            "status": "not_found",
            "items": [],
            "more_available": False,
            "meter": ekonomi_meter(query, ""),
            "page_file": page_file,
            "strategies": [
                "Rephrase the query with different words and try again.",
                "Search the 'all' temporal tier instead of one tier.",
                "Capture the fact first with hivemind_capture_idea, then query it.",
            ],
        }
    raw = "\n".join(item["full_text"] for item in page)
    injected = "\n".join(item["text"] for item in page)
    return {
        "status": "ok",
        "items": [{k: item[k] for k in ("id", "text", "domain", "created_at",
                                        "temporal_bucket", "source")} for item in page],
        "more_available": more,
        "meter": ekonomi_meter(raw, injected),
        "page_file": page_file,
        "fake_meta_calls": _FAKE_CLIENT.call_count,
    }
