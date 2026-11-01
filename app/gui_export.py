"""GUI data export: scrubbed, active memories as graph JSON.

Used by the GUI (Block 6) and by ``python -m app.gui_export``. Nodes
are distinguished by shape (never colour alone): the shape cycles
circle / square / triangle by domain. Edges are solid for shared
entities, dashed for superseded links, dotted for cross-domain links.
Only active, already-scrubbed facts are exported — the exporter
never reads raw input, and the JSON it writes contains no secrets
beyond what is already stored scrubbed.
"""

import argparse
import json
import os
from datetime import datetime, timezone

from .caveman import temporal_bucket
from .store import Store

_SHAPES = ("circle", "square", "triangle")


def export_data(store):
    """Return the graph payload dict for the GUI."""
    memories = store.list_memories(limit=500)
    domains = []
    for mem in memories:
        if mem["domain"] not in domains:
            domains.append(mem["domain"])
    shape_by_domain = {d: _SHAPES[i % len(_SHAPES)] for i, d in enumerate(domains)}
    nodes = []
    for mem in memories:
        nodes.append({
            "id": mem["id"],
            "label": mem["text"][:80],
            "text": mem["text"],
            "domain": mem["domain"],
            "shape": shape_by_domain[mem["domain"]],
            "created_at": mem["created_at"],
            "temporal_bucket": temporal_bucket(mem["created_at"]),
            "source": mem["source"],
            "entities": mem["entities"],
            "provenance": mem["provenance"],
        })
    edges = []
    entity_to_ids = {}
    for node in nodes:
        for ent in node["entities"]:
            entity_to_ids.setdefault(ent, []).append(node["id"])
    for ent, ids in entity_to_ids.items():
        for other in ids[1:]:
            edges.append({"from": ids[0], "to": other, "kind": "shared-entity",
                          "line_style": "solid", "label": ent})
    for mem in store.list_memories(status="superseded", limit=500):
        if mem["superseded_by"]:
            edges.append({"from": mem["id"], "to": mem["superseded_by"],
                          "kind": "superseded", "line_style": "dashed",
                          "label": "superseded by"})
    # Dotted cross-domain edges: a memory whose provenance lists a
    # cross-domain links (dotted) to the first memory in that domain.
    seen_cross = set()
    for node in nodes:
        cross = (node["provenance"] or {}).get("cross_domains") or []
        for domain in cross:
            for other in nodes:
                if other["domain"] == domain and other["id"] != node["id"]:
                    key = (node["id"], other["id"])
                    if key not in seen_cross:
                        seen_cross.add(key)
                        edges.append({"from": node["id"], "to": other["id"],
                                      "kind": "cross-domain", "line_style": "dotted",
                                      "label": domain})
                    break
    changelog = store.changelog(limit=5)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "live": True,
        "nodes": nodes,
        "edges": edges,
        "changelog": changelog,
        "stats": store.memory_stats(),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Export GUI graph data as JSON")
    parser.add_argument("--out", default="gui/data.json", help="Output JSON path")
    args = parser.parse_args(argv)
    store = Store()
    try:
        payload = export_data(store)
    finally:
        store.close()
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"wrote {args.out} ({len(payload['nodes'])} nodes, {len(payload['edges'])} edges)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
