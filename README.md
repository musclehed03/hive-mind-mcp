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

## Block 1 — Foundation (implemented)

Local-first only: SQLite (+ `sqlite-vec` when the extension loads, with a
clean lexical fallback when it does not) and a JSONL / Markdown vault
mirror. No network, no LLM, no Meta API calls, no Supabase calls. The
MCP server is standard-library-only stdio JSON-RPC — no SDK, no HTTP
framework — so it runs on a Linux Mint Surface with just Python 3.12.

All 8 `hivemind_` tools are listed with their exact spec names, flat
scalar arguments, and explainer metadata. In Block 1 every `tools/call`
returns a clear `not_implemented` response naming its owning block; the
foundation primitives (`remember` / `recall` / `forget` / `memory_stats`
in `app/store.py`) are wired underneath and tested directly. Blocks 2–8
replace the stubs one block at a time. SSE is not in Block 1; stdio is
the transport, and the same tool registry serves SSE when it lands.

Recall in Block 1 is lexical (token overlap). Vector recall arrives with
the embedding wiring in a later block. The `vecs` table is created when
`sqlite-vec` loads, but Block 1 writes no embeddings into it.

### Run locally

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt   # sqlite-vec only
.venv/bin/python -m pytest tests/ -q        # Block 1 gate: 16 tests
.venv/bin/python -m app.mcp_server --stdio # MCP over stdio, exits on EOF
.venv/bin/python -m app.mcp_server --list-tools
```

Data lives in `data/hive-mind.db` and `vault/` (both git-ignored).
Override with `HIVE_MIND_DB_PATH` / `HIVE_MIND_VAULT_DIR`.

### Run in Docker (zero-config, no .env needed)

```bash
docker compose run --rm hive-mind
```

The container is capped (256 MB, 0.5 CPU) and exposes no port: stdin /
stdout are the MCP transport. Docker was **not** verified in the build
VM (no Docker binary there); verify with the command above on a machine
with Docker before demoing from a container.

### MCP clients

Any stdio MCP client: point it at `python -m app.mcp_server --stdio`
in this repo. Example `initialize` → `tools/list` → `tools/call` flow
is exercised end-to-end in `tests/test_block1.py`.

### Configuration

See `.env.example` (placeholders only, never real values). Block 1
ignores every credential variable; the Meta and Supabase clients do not
exist yet and are not called until Blocks 4 and 5 respectively, under
their own gates and budgets.
