# Hive-Mind MCP — "Never Restate Yourself"

Persistent-memory MCP server built for the Meta Global AI Developer Hackathon
2026 (Indie Developer track, theme: Build for Your World). One memory layer
that every client and sub-bot shares, so nothing ever has to be restated —
facts are captured once, verified against provenance, and recalled as
ultra-compressed payloads.

**Status:** all 8 blocks built (Blocks 1–8). The approved master lock-in
spec is the source of truth: see `docs/HIVE-MIND-LOCK-IN-SPEC.md`. Do not
invent tool names, signatures, or pillar definitions — the spec settles them.

## The 6 pillars

Efficiency (1–4), gated by accessibility and security as first-class
foundations that ship in v1 (5–6):

1. Computing-in-memory · 2. Event-driven spiking · 3. Extreme sparsity /
   dynamic routing · 4. Continuous local learning · 5. Accessibility ·
   6. Security

## The 8 MCP tools

All snake_case, hivemind_ prefix, flat scalar arguments, strict read/write
separation. All 8 are implemented; see `app/tools.py` for the exact
signatures and `app/dispatch.py` for the handlers.

| Tool | Role | Block |
| --- | --- | --- |
| hivemind_capture_idea | Ingest text / voice / web-clipper payloads (auto-runs the scrub pre-step) | 3 |
| hivemind_scrub_input | Zero-cost local regex + entropy pre-gate (Burn-After-Reading) | 2 |
| hivemind_crosshatch_verify | Verify facts, embed OKF trust signals, inline citations, supersede on conflict | 4 |
| hivemind_query_temporal | Query the 3-tier temporal index, Caveman shorthand + Token Ekonomi stats | 3 |
| hivemind_spawn_microbot | Spawn 8–14 KB micro-agents, Simple Mode to Pro Mode slider | 7 |
| hivemind_snapshot_backup | Weekly snapshot hook (SQLite/JSONL/Markdown bundle) | 5 |
| hivemind_explain | Zero-jargon explainer, ages 12 to 80+ | 6 |
| hivemind_prune_memory | Deterministic deletion / expiration, human confirmation required | 4 |

## What is real, what is fake — read this first

Honesty is part of the build. In this repo, as submitted:

- **Real:** the MCP server, the SQLite + JSONL store, the scrubber, the
  temporal index, Caveman compression, cross-hatch conflict detection,
  the snapshot bundler with verified callbacks, the GUI, the
  Accessibility Suite, and the micro-bot templates. All of it runs
  local-first with nothing configured.
- **Fake (clearly labelled in code):** the Meta client
  (`app/fake_meta.py`, `FakeMetaClient`, model name
  `muse-spark-1.3-fake`) and the Supabase/Drive adapters
  (`app/fake_supabase.py`, in-memory only). They return canned,
  deterministic responses and make no network calls. Every payload
  that used one says so (`live: false`, and the cross-hatch trust
  signals name the fake client).
- **UNVERIFIED live gates:** the real Meta API calls (Block 4) and the
  real Supabase snapshot (Block 5) have never run from this codebase.
  They are documented below as exact commands for Sonja's machine.
  Nothing in this repo claims they passed.

## Blocks 2–8 — what landed

- **Block 2 — Burn-After-Reading scrubber** (`app/scrubber.py`): local
  regex + Shannon entropy pre-gate, three strictness levels, audit
  counts of trapped items, raw values never stored. Runs automatically
  before every capture and every snapshot.
- **Block 3 — Capture + Temporal + Caveman** (`app/capture.py`,
  `app/caveman.py`): Temporary Cache Buffer, cross-domain routing with
  provenance, 3-tier temporal index (recent 0–3m / warm 3–6m / archival
  6m+), Caveman shorthand + Token Ekonomi Meter, file-passing
  pagination. The clipper payload format (`URL:` first line) is parsed
  here.
- **Block 4 — Cross-hatch verify + prune** (`app/crosshatch.py`,
  `app/prune.py`): 6-Pillar check, OKF 5 Trust Signals, inline
  citations, conflict refusal until a `supersede_id` is given,
  Conflict Diff & Merge entries. Prune requires a non-empty human
  confirmation token.
- **Block 5 — Snapshot backup** (`app/snapshot.py`): ZIP bundle
  (SQLite binary copy + JSONL + Markdown + SHA-256 manifest), scrub
  gate before upload, verified callback (re-download + hash compare),
  failure never reported as backed up, `local_only` mode when no
  adapter is configured.
- **Block 6 — GUI + Accessibility Suite** (`gui/`): 2D canvas nebula
  graph with metaphor dropdown (Nebula / Tree of Life / Spherical
  Mandala / Mythical Road Map), nodes by shape + line style, never
  colour alone; ARIA labels and alt text throughout. Accessibility
  Suite (7 toggles + typed colour-blind palettes incl. pure-grayscale
  achromatopsia + one-tap profiles + granular controls under presets,
  letter-spacing moderate by default, capped, turnable down) is kept
  structurally separate from Regular Settings (graph, snapshot,
  token budget, reading level, micro-bot mode, sound, notifications).
  Settings persist in `localStorage`; OS reduced-motion/contrast is
  respected on first load. `hivemind_explain` is the Index-Key
  Explainer. GUI defaults in `gui/settings-data.js` are not the
  canonical Deluxe Posh tokens — those live in the Dollhouse Deviants
  website repo.
- **Block 7 — Micro-bot + clipper** (`app/microbot.py`,
  `gui/clipper.html`, `gui/bookmarklet.js`): 8–14KB runnable templates
  (Morning Digest / Allowance-Gated Sentinel), Pro refuses to arm
  without a positive allowance and a ≥30s cooldown, 0.5% slippage
  guard, simulation only — no orders, no network. The clipper builds
  a capture payload in the browser; nothing is sent from the page.
- **Block 8 — Demo + polish**: `docs/DEMO_SCRIPT.md` (3 minutes),
  `docs/SUBMISSION_CHECKLIST.md`, this README, and the polish gate in
  `tests/test_block8.py` (no dead references, no polling, no TODOs in
  shipped code, pinned dependencies).

## Design system

Deluxe Posh / Mature App Palette (orchid-to-wine pinks, dark teal to
greenish-navy, metal only as 1px pinstripe + one ornament). Canonical tokens
live in the Dollhouse Deviants website repo
(`src/theme/posh-mature-palette.css`); explicit 2px borders and geometric
node shapes carry all hierarchy in pure grayscale for achromatopsia.

## Layout

- `docs/HIVE-MIND-LOCK-IN-SPEC.md` — approved master lock-in spec (settled)
- `app/` — MCP core (stdlib only, plus `sqlite-vec`)
- `gui/` — plain HTML/JS/CSS graph + Accessibility Suite + clipper
- `tests/` — pytest gates, one file per block
- `docs/DEMO_SCRIPT.md`, `docs/SUBMISSION_CHECKLIST.md` — demo + submission

## License

No license chosen yet — TODO before public distribution.

## Block 1 — Foundation (implemented)

Local-first only: SQLite (+ `sqlite-vec` when the extension loads, with a
clean lexical fallback when it does not) and a JSONL / Markdown vault
mirror. No network, no LLM, no Meta API calls, no Supabase calls. The
MCP server is standard-library-only stdio JSON-RPC — no SDK, no HTTP
framework — so it runs on a Linux Mint Surface with just Python 3.12.

The foundation primitives (`remember` / `recall` / `forget` /
`memory_stats` in `app/store.py`) are wired underneath and tested
directly. Recall is lexical (token overlap). Vector recall arrives with
the embedding wiring in a later block. The `vecs` table is created when
`sqlite-vec` loads, but no embeddings are written into it yet. SSE is
not implemented; stdio is the transport, and the same tool registry
serves SSE when it lands.

### Run locally

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt   # sqlite-vec only
.venv/bin/python -m pytest tests/ -q        # full gate: 107 tests
.venv/bin/python -m app.mcp_server --stdio # MCP over stdio, exits on EOF
.venv/bin/python -m app.mcp_server --list-tools
```

Data lives in `data/hive-mind.db` and `vault/` (both git-ignored).
Override with `HIVE_MIND_DB_PATH` / `HIVE_MIND_VAULT_DIR`.

### Run the GUI

```bash
.venv/bin/python -m app.gui_server   # http://127.0.0.1:8765/ (localhost only)
```

Serves `gui/` plus `/api/memories` and `/api/changelog` from the local
store. The graph renders in chunked batches (50 nodes per animation
frame) so a large vault never hangs the page, and it fetches its data
once — no polling. Open `gui/clipper.html` from the same server for the
web clipper, and `gui/bookmarklet.js` for the install instructions.

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

See `.env.example` (placeholders only, never real values). With nothing
configured, everything runs local-first: the fake Meta client answers
verification calls and the snapshot backup runs in `local_only` mode.
Real clients are wired only by the live-gate steps below, on Sonja's
machine, with her own keys — never in this repo.

## Live gates — UNVERIFIED (Sonja-side only)

Budget guard, verified Oct 31, 2026 from the dev.meta.ai Billing
screenshot: **$150.00 in free credits in use**, card on file, and the
only spend control available is the **email notification at $100.00
monthly spend — there is no second notification and no hard cap**.
Treat **$100 as the hard stop** and keep a $50 buffer. Do not run the
live gate until Billing shows the free credits applied.

### Block 4 — 3–5 real Meta Model API calls

Prerequisite: `META_API_KEY` set in the shell (never written to a file
in this repo, never pasted in chat), Billing shows free credits, and
the $100 notification is on.

```bash
cd hive-mind-mcp && git pull
export META_API_KEY='PASTE_KEY_HERE_IN_THIS_SHELL_ONLY'
.venv/bin/python - <<'PYEOF'
import os
print("key present:", bool(os.environ.get("META_API_KEY")))
print("key prefix:", os.environ["META_API_KEY"][:4])
PYEOF
```

Then, and only then, wire the real client: the fake client in
`app/fake_meta.py` must be replaced by an OpenAI-compatible call to
`https://api.meta.ai/v1` behind the same interface (same method names,
same payload shape), run the 3–5 verification calls through
`hivemind_crosshatch_verify`, and confirm the spend on the Billing
page stays under $100. If the Billing page does not show the free
credits, stop — the card will be charged instead.

### Block 5 — one real snapshot to Supabase

Prerequisite: the `hive-mind` project exists inside the existing
"Dollhouse Deviants Co." organisation on Supabase (sign in with
GitHub as `musclehed03`), the private bucket `hive-mind-snapshots`
exists, and `.env` holds the Supabase URL + keys (created with `nano
.env` on that machine — never in a word processor, never committed,
never pasted in chat).

```bash
cd hive-mind-mcp && git pull
nano .env   # SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY
.venv/bin/python -m pytest tests/test_block5.py -q
```

Then run one `hivemind_snapshot_backup` with destination `supabase`
and a handshake token, confirm the re-download hash check passes in
the payload, confirm the object in the private bucket, then delete
the test snapshot from the bucket. If the upload fails, the payload
must say so — never report a failed upload as backed up.
