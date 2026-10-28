# Hive-Mind MCP — "Never Restate Yourself"

Persistent-memory MCP server built for the Meta Global AI Developer Hackathon
2026 (Indie Developer track, theme: Build for Your World). One memory layer
that every client and sub-bot shares, so nothing ever has to be restated —
facts are captured once, verified against provenance, and recalled as
ultra-compressed payloads.

**Status:** spec approved Oct 27, 2026. Implementation lands here during the
hackathon build window (Oct 26 – Nov 4, 2026, 8:00 PM CT). The approved
master lock-in spec is the source of truth: see
`docs/HIVE-MIND-LOCK-IN-SPEC.md`.

## The 6 pillars

Efficiency (1–4), gated by accessibility and security as first-class
foundations that ship in v1 (5–6):

1. Computing-in-memory · 2. Event-driven spiking · 3. Extreme sparsity /
   dynamic routing · 4. Continuous local learning · 5. Accessibility ·
   6. Security

## The 8 MCP tools

All snake_case, hivemind_ prefix, flat scalar arguments, strict read/write
separation:

| Tool | Role |
| --- | --- |
| hivemind_capture_idea | Ingest text / voice / web-clipper payloads (auto-runs the scrub pre-step) |
| hivemind_scrub_input | Zero-cost local regex + entropy pre-gate (Burn-After-Reading) |
| hivemind_crosshatch_verify | Verify facts, embed OKF trust signals, inline citations, supersede on conflict |
| hivemind_query_temporal | Query the 3-tier temporal index, Caveman shorthand + Token Ekonomi stats |
| hivemind_spawn_microbot | Spawn 8–14 KB micro-agents, Simple Mode to Pro Mode slider |
| hivemind_snapshot_backup | Weekly snapshot hook (SQLite/JSONL/Markdown bundle) |
| hivemind_explain | Zero-jargon explainer, ages 12 to 80+ |
| hivemind_prune_memory | Deterministic deletion / expiration, human confirmation required |

## Design system

Deluxe Posh / Mature App Palette (orchid-to-wine pinks, dark teal to
greenish-navy, metal only as 1px pinstripe + one ornament). Canonical tokens
live in the Dollhouse Deviants website repo
(`src/theme/posh-mature-palette.css`); explicit 2px borders and geometric
node shapes carry all hierarchy in pure grayscale for achromatopsia.

## Layout

- `docs/HIVE-MIND-LOCK-IN-SPEC.md` — approved master lock-in spec (settled)
- Implementation lands here during the build window; stack details go in
  the spec's scope section as they are pinned down.

## License

No license chosen yet — TODO before public distribution.
