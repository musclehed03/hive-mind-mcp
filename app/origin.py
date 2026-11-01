"""Origin labels: WHICH model, client, or coder made each memory.

One short plain label per memory, derived only from values already
recorded in its provenance/source — never invented. The label is
what the graph legend and the text list show, and what the
user-assignable origin colours key off. Priority (first match
wins):

1. A verifying model: provenance carries ``verified_by_model``
   (Cross-Hatch facts, live or fake) or ``model`` (live facts) —
   "verified by <model>".
2. Clipper captures: the source is the clipped page's URL —
   "clipper · <hostname>".
3. The MCP client that sent the capture (``client_name``, recorded
   from the client's ``initialize`` clientInfo) — "<source> · <client>".
4. The ``client_id`` argument the caller passed — "<source> · <id>".
5. The source type alone ("text", "voice", "clipper").
6. Nothing recorded at all — "unknown origin".

Old vaults whose provenance lacks the newer keys still derive a
label from whatever they do carry (client_id / source_type), so
nothing stored before Block 17 changes meaning.
"""

_MAX_LABEL_CHARS = 48


def _clean(value):
    """A recorded value as one trimmed line, or "" when absent."""
    if value is None:
        return ""
    text = str(value).strip()
    return " ".join(text.split())


def _clipper_host(source):
    """Hostname of a clipped URL, or "" when the source is not a URL.

    Parsed by hand on purpose: this module must stay free of
    network imports (the Block 8 no-network guard), and hostname
    parsing needs no I/O. userinfo, port, path, query, and
    fragment are all stripped; IPv6 brackets are dropped.
    """
    raw = _clean(source)
    if not raw:
        return ""
    rest = raw
    if "://" in rest:
        rest = rest.split("://", 1)[1]
    rest = rest.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    if "@" in rest:
        rest = rest.rsplit("@", 1)[1]
    if rest.startswith("["):
        host = rest[1:].split("]", 1)[0].strip().lower()
        if host:
            return host
        return raw[:24]
    if ":" in rest:
        host = rest.split(":", 1)[0]
    else:
        host = rest
    host = host.strip().lower()
    if host and ("." in host or host == "localhost"):
        return host
    # Not a URL after all: use the source itself, shortened.
    return raw[:24]


def origin_label(provenance, source):
    """One short plain origin label for a memory.

    ``provenance`` is the stored provenance dict (or None);
    ``source`` is the stored source string. Only recorded values
    are used; unknown parts fall back, never guessed.
    """
    prov = provenance if isinstance(provenance, dict) else {}
    model = _clean(prov.get("verified_by_model") or prov.get("model"))
    if model:
        label = "verified by " + model
        return label if len(label) <= _MAX_LABEL_CHARS else label[:_MAX_LABEL_CHARS - 1] + "…"
    source_type = _clean(prov.get("source_type"))
    if source_type == "clipper":
        host = _clipper_host(source)
        label = "clipper · " + host if host else "clipper"
        return label if len(label) <= _MAX_LABEL_CHARS else label[:_MAX_LABEL_CHARS - 1] + "…"
    client = _clean(prov.get("client_name"))
    if client and client.lower() != "unknown":
        who = client
    else:
        who = _clean(prov.get("client_id"))
    if who:
        base = source_type or "memory"
        label = base + " · " + who
        return label if len(label) <= _MAX_LABEL_CHARS else label[:_MAX_LABEL_CHARS - 1] + "…"
    if source_type:
        return source_type
    return "unknown origin"
