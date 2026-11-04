# Hive-Mind MCP — "Never Restate Yourself"

Persistent-memory MCP server built for the Meta Global AI Developer Hackathon
2026 (Indie Developer track, theme: Build for Your World). One memory layer
that every client and sub-bot shares, so nothing ever has to be restated —
facts are captured once, verified against provenance, and recalled as
ultra-compressed payloads.


## Demo

3-minute demo video (3:07): an 11-second lead-in with title and "Has this ever happened to you?" scenario cards, then the autopilot terminal run and the GUI demo, narrated, with captions burned in.

Watch it on Rumble: [Hive-Mind — Your AI Finally Remembers: 3-minute demo](https://rumble.com/v7hueg0-hive-mind-your-ai-finally-remembers-never-restate-yourself-hive-mind-mcp-de.html)

The video is hosted on Rumble. Captions are burned into the picture; the caption sidecar is in `demo/hive-mind-demo-3min-v2.srt`, and `demo/embed-snippet.html` holds the Rumble embed code for a real webpage (GitHub strips iframes in rendered markdown).

**Status:** Blocks 1–17 built, full suite green (247 tests), and the
live gates verified Nov 1, 2026 (see "Live gates — VERIFIED" below).
The approved master lock-in spec is the source of truth: see
`docs/HIVE-MIND-LOCK-IN-SPEC.md`. Do not invent tool names, signatures,
or pillar definitions — the spec settles them. The 8 `hivemind_` tools
are unchanged since Block 1; Blocks 9–17 added GUI, transport, and
provenance features, not tools.

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
- **Fake (clearly labelled in code, and the default):** the Meta client
  (`app/fake_meta.py`, `FakeMetaClient`, model name
  `muse-spark-1.3-fake`) and the Supabase/Drive adapters
  (`app/fake_supabase.py`, in-memory only). They return canned,
  deterministic responses and make no network calls. Every payload
  that used one says so (`live: false`, and the cross-hatch trust
  signals name the fake client).
- **Live adapters exist but are never used by default:**
  `app/live_meta.py` (real Meta Model API, stdlib `urllib` only)
  and `app/live_supabase.py` (real Supabase Storage, stdlib
  `urllib` only), selected only by the factory in
  `app/live_clients.py` when `HIVE_MIND_LIVE=1` and the relevant
  credential is present in the environment. They are tested with
  mocked HTTP, and they were exercised in the verified live gates
  below — the only live calls ever made from this codebase, inside
  the $150 free credits ($0.02 used, $0.00 charged).
- **VERIFIED live gates:** the real Meta API calls (Block 4) and the
  real Supabase snapshot (Block 5) ran from Sonja's Linux machine
  on Nov 1, 2026, and passed — see "Live gates — VERIFIED" below
  for the exact commands and results. The GUI, Docker, and
  achromatopsia checks were verified live the same day.

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
  Explainer. The GUI default palette IS the canonical Deluxe Posh /
  Mature palette, Variant A (Velvet Boudoir & Brushed Gold), wired in
  Block 9 — see "Design system" below. Fast custom tooltips (~500ms,
  hover + keyboard focus, hide on leave/blur/Escape, toggleable and
  persisted) cover every user-definable control.
- **Block 7 — Micro-bot + clipper** (`app/microbot.py`,
  `gui/clipper.html`, `gui/bookmarklet.js`): 8–14KB runnable templates
  (Morning Digest / Allowance-Gated Sentinel), Pro refuses to arm
  without a positive allowance and a ≥30s cooldown, 0.5% slippage
  guard, simulation only — no orders, no network. The clipper builds
  a capture payload in the browser; nothing is sent from the page.
- **Block 8 — Demo + polish**: `docs/DEMO_SCRIPT.md` (3 minutes),
  `docs/SUBMISSION_CHECKLIST.md`, this README, and the polish gate in
  `tests/test_block8.py` (no dead references, no polling, no TODOs in
  shipped code, pinned dependencies). The demo script was refreshed
  for Blocks 9–17 before recording (fake mode only on camera).

## Blocks 9–17 — what landed after Block 8

- **Block 9 — Variant A palette wired in** (`gui/settings-data.js`,
  `gui/styles.css`): the GUI `default` palette is the canonical
  Deluxe Posh Variant A dark + light tokens; the other six typed
  palettes and achromatopsia are byte-identical. Metal appears only
  as the 1px brushed-gold header pinstripe.
- **Block 10 — Living nebula growth stages** (`gui/stage.js`): the
  graph grows with the vault — Nebula (0–9 memories) / Protostar
  (10–29) / Star (30–74) / Radiant Sun (75+), with verified counts
  from Cross-Hatch provenance. Stage meaning is carried in text
  (the growth-stage label), never colour alone; verified nodes get
  an extra ring (shape, not colour).
- **Block 11 — EXP, local only** (`app/exp.py`): points for memory
  health, never for API spend — endpoint attached 50 (once per
  distinct endpoint), verified recall 10, contradiction resolved
  25, snapshot backed up 15. Append-only log under the vault dir,
  totals recomputed on read, never decreasing. Read-only
  `GET /api/exp` on the GUI server; no new MCP tool.
- **Block 12 — Any endpoint + SSE + integration docs**
  (`app/live_meta.py`, `app/sse_server.py`, `docs/INTEGRATIONS.md`):
  the live model client already honoured `HIVE_MIND_META_BASE_URL` /
  `HIVE_MIND_META_MODEL`, so Ollama, OpenRouter, OpenWebUI, and the
  Meta Model API share one code path, one scrubber, and one 5-call
  budget. The SSE transport is stdlib `http.server` on localhost
  port 8765 (`GET /sse`, `POST /messages`), sharing the same
  `handle_request` as stdio — no forked tool logic. SSE is
  protocol-tested over localhost only; a real-client check was
  skipped by Sonja's choice (she does not use VS Code), and stdio
  is the verified transport.
- **Block 13 — Graph label + centring fix** (`gui/stage.js`,
  `gui/app.js`): the canvas is sized to its displayed size on every
  render, node layout derives from real dimensions, and labels are
  short keywords placed clear of node circles and canvas edges.
- **Block 14 — Meaningful keywords + grouping + header/footer
  centring** (`gui/stage.js`, `gui/app.js`, `gui/styles.css`):
  labels use content words with stop-words stripped ("Library
  opens", not "The library opens"); duplicate memories draw as one
  grouped node ("Library opens ×2") while the text list still shows
  every memory; overlapping labels stagger vertically; the
  header/footer centring bug (fixed 12px side margins vs `main`'s
  auto margins) is fixed.
- **Block 15 — Key optional for loopback endpoints**
  (`app/live_meta.py`): a missing `META_API_KEY` no longer refuses
  local endpoints (`localhost`, `127.x.x.x`, `::1`) — no
  `Authorization` header is sent, and a configured key is still
  sent. Remote endpoints (Meta, OpenRouter) still refuse without a
  key and make no network attempt. Lookalike hostnames
  (`localhost.example.com`) do not count as loopback.
- **Block 16 — Integrations box in settings** (`app/integrations.py`,
  `app/gui_server.py`, `gui/index.html`): a read-only status box in
  Regular Settings showing the MCP transports, model endpoint
  (base URL, model, live/fake, key present as a boolean only),
  Supabase status, and EXP total, via `GET /api/integrations`; copy
  buttons for the launch command, SSE URL, and a Codex config
  snippet; plain-words numbered setup instructions. Keys are never
  typed, shown, or stored in the GUI — they live only in `.env`.
- **Block 17 — Origin colours + legend** (`app/origin.py`,
  `app/gui_export.py`, `gui/stage.js`, `gui/app.js`): every memory
  carries an `origin` derived from stored provenance — which
  model verified it, which client captured it, which clipper page
  it came from. The MCP handshake's client name is recorded into
  new captures. Origins get user-assignable ring colours in Regular
  Settings plus a distinct ring pattern each (solid / dashed /
  dotted / double) and a written Origins legend with counts, so
  origins stay distinguishable in pure grayscale. The
  accessibility reset never wipes origin colours.
- **Block 18 — Demo autopilot** (`gui/demo.js`, `gui/app.js`,
  `scripts/demo_terminal.py`): the demo drives itself so no step
  has to be remembered mid-take. In the GUI, **Play demo** (above
  the graph, outside the Accessibility Suite) walks Beats 3–4 —
  growth stage, EXP, an origin ring-colour change, the metaphor
  switch, the achromatopsia profile on and off, the Integrations
  copy button, and the read-aloud button shown but never pressed
  — with a plain-words caption, a step counter, and a progress
  bar, 6 seconds a step; Space pauses, Escape stops, and every
  setting the demo changed is restored exactly at the end. In
  the terminal, `.venv/bin/python scripts/demo_terminal.py`
  (`--fast` for 1s pauses, `--step` to wait for Enter) runs Beats
  1–2 plus the Beat 4 micro-bot/snapshot calls against the stdio
  server in a throwaway temp store. Both halves are fake-mode
  only: the runner refuses to start with `HIVE_MIND_LIVE` set or
  `META_API_KEY` present, and the GUI demo never writes, never
  calls the network, and never starts on its own.

## Design system

Deluxe Posh / Mature App Palette (orchid-to-wine pinks, dark teal to
greenish-navy, metal only as 1px pinstripe + one ornament). The GUI
default is Variant A (Velvet Boudoir & Brushed Gold), wired in from
the canonical tokens in the Dollhouse Deviants website repo
(`src/theme/posh-mature-palette.css`, draft PR #4, branch
`posh-mature-app-palette`); explicit 2px borders and geometric node
shapes carry all hierarchy in pure grayscale for achromatopsia.

## Layout

- `docs/HIVE-MIND-LOCK-IN-SPEC.md` — approved master lock-in spec (settled)
- `app/` — MCP core (stdlib only, plus `sqlite-vec`)
- `gui/` — plain HTML/JS/CSS graph + Accessibility Suite + clipper
- `tests/` — pytest gates, one file per block
- `scripts/demo_terminal.py` — demo autopilot terminal runner
- `docs/DEMO_SCRIPT.md`, `docs/SUBMISSION_CHECKLIST.md` — demo + submission
- `docs/INTEGRATIONS.md` — MCP client configs, model endpoints, hotkeys

## License

MIT License — see `LICENSE` (Copyright 2026 Sonja Kelley).

## Block 1 — Foundation (implemented)

Local-first only: SQLite (+ `sqlite-vec` when the extension loads, with a
clean lexical fallback when it does not) and a JSONL / Markdown vault
mirror. No network, no LLM, no Meta API calls, no Supabase calls. The
MCP server is standard-library-only stdio JSON-RPC — no SDK, no HTTP
framework — so it runs on a Linux Mint Surface with just Python 3.12.

The foundation primitives (`remember` / `recall` / `forget` /
`memory_stats` in `app/store.py`) are wired underneath and tested
directly. Recall is lexical (token overlap) — the `vecs` table is
created when `sqlite-vec` loads, but no embeddings are written into
it, and vector recall is not built; that is a known limit, stated
honestly in `docs/SUBMISSION_CHECKLIST.md`. SSE is implemented
(Block 12, `app/sse_server.py`, localhost port 8765) and shares the
same tool registry as stdio; stdio remains the verified transport.

### Run locally

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt   # sqlite-vec only
.venv/bin/python -m pytest tests/ -q        # full gate: 247 tests
.venv/bin/python -m app.mcp_server --stdio # MCP over stdio, exits on EOF
.venv/bin/python -m app.mcp_server --list-tools
```

Data lives in `data/hive-mind.db` and `vault/` (both git-ignored).
Override with `HIVE_MIND_DB_PATH` / `HIVE_MIND_VAULT_DIR`.

### Run the GUI

```bash
.venv/bin/python -m app.gui_server   # http://127.0.0.1:8000/ (localhost only)
```

Serves `gui/` plus `/api/memories`, `/api/changelog`, `/api/exp`,
and `/api/integrations` from the local store. The graph renders in
chunked batches (50 nodes per animation frame) so a large vault never
hangs the page, and it fetches its data once — no polling. The server
sends no cache headers, so re-checks need a hard refresh
(`Ctrl+Shift+R`). Open `gui/clipper.html` from the same server for the
web clipper, and `gui/bookmarklet.js` for the install instructions.
For the SSE transport (a separate server, localhost port 8765):

```bash
.venv/bin/python -m app.sse_server   # http://127.0.0.1:8765/sse
```

### Run in Docker (zero-config, no .env needed)

```bash
docker compose run --rm hive-mind
```

The container is capped (256 MB, 0.5 CPU) and exposes no port: stdin /
stdout are the MCP transport. Docker was verified on Sonja's Linux
machine on Nov 1, 2026: the image built 10/10 and the stdio server
answered `initialize` correctly. (It was never verified in the build
VM, which has no Docker binary.)

### MCP clients

Any stdio MCP client: point it at `python -m app.mcp_server --stdio`
in this repo. Example `initialize` → `tools/list` → `tools/call` flow
is exercised end-to-end in `tests/test_block1.py`. For the SSE
transport and per-client copy-paste configs (Claude Code, Codex,
Claude Desktop, VS Code, Ollama, OpenRouter, OpenWebUI), see
`docs/INTEGRATIONS.md` — and the Integrations box in the GUI's
Regular Settings, which shows live status and copy buttons.

### Configuration

See `.env.example` (placeholders only, never real values). With nothing
configured, everything runs local-first: the fake Meta client answers
verification calls and the snapshot backup runs in `local_only` mode.
The live clients in `app/live_meta.py` / `app/live_supabase.py` are
selected only when `HIVE_MIND_LIVE=1` is set in the shell and the
relevant credential is present in the environment (see
`app/live_clients.py`); otherwise the factory always returns the
fakes. Keys live only in the shell / local `.env` on Sonja's
machine — never in this repo, never in chat.

## Live gates — VERIFIED Nov 1, 2026 (Sonja-side only)

Budget guard, verified Oct 31, 2026 from the dev.meta.ai Billing
screenshot: **$150.00 in free credits in use**, card on file, and the
only spend control available is the **email notification at $100.00
monthly spend — there is no second notification and no hard cap**.
Treat **$100 as the hard stop** and keep a $50 buffer. Both gates
below ran inside that guard: after the Block 4 gate, Billing showed
"Free credits in use $149.98" — **$0.02 used, $0.00 charged**, with
the $100 notification still on. The commands below are the record of
what ran; the key was loaded from the local `.env` in that shell
(never pasted, never typed into a command), and diagnostics printed
the `error` field directly, because the gate's print line hides it.

### Block 4 — 3 real Meta Model API calls (as run)

Prerequisite: `META_API_KEY` in the local `.env` on that machine
(never written to a file in this repo, never pasted in chat),
Billing shows free credits, and the $100 notification is on. The
live client (`app/live_meta.py`) is already wired behind the same
`verify()`/`compress()` interface as the fake client; the only
switch is `HIVE_MIND_LIVE=1`. It enforces a hard budget of 5 live
calls per process, runs the scrubber before anything is sent, and
returns an error dict — never a fake success — on any failure.
One finding from the run is recorded in code: Muse Spark is a
reasoning model and reasoning tokens count against `max_tokens`,
so `DEFAULT_MAX_TOKENS` is 1024 in `app/live_meta.py` — at 256 the
model spent 254 tokens reasoning and returned empty content.
The request shape is the OpenAI-compatible chat-completions call
to `https://api.meta.ai/v1` (endpoint/model configurable via
`HIVE_MIND_META_BASE_URL` / `HIVE_MIND_META_MODEL`); if Meta
rejects a field, adjust the configuration — do not guess a
different API.

```bash
cd hive-mind-mcp && git pull
set -a; source .env; set +a   # key loaded from the local .env only
export HIVE_MIND_LIVE=1
.venv/bin/python - <<'PYEOF'
import os, tempfile
from app.dispatch import dispatch_tool
from app.store import Store
store = Store(db_path=os.path.join(tempfile.mkdtemp(), "live-gate.db"),
              vault_dir=tempfile.mkdtemp())
facts = [
    ("The shop opens at 9am on Saturdays", "general", "live gate notes"),
    ("The garden grows tomatoes in summer", "general", "live gate notes"),
    ("The library opens at 10am on weekdays", "general", "live gate notes"),
]
for fact, domain, citation in facts:
    payload, err = dispatch_tool("hivemind_crosshatch_verify", {
        "candidate_fact": fact, "domain_repo": domain,
        "source_citation": citation, "supersede_id": ""}, store=store)
    print(payload["status"], "live:", payload.get("live"),
          payload.get("verified_fact", payload.get("error", ""))[:100])
store.close()
PYEOF
unset META_API_KEY HIVE_MIND_LIVE
```

**Result, Nov 1, 2026, 05:22 CT:** all three facts returned
`verified`, `live: True`, with an empty error field. The Block 4
live gate is COMPLETE. Check the Billing page afterwards: spend
must stay under the $100 notification, with the $50 buffer intact.
If any payload says `status: "error"`, or Billing does not show
the free credits, stop — the card will be charged instead of the
credits.

### Block 5 — one real snapshot to Supabase (as run)

Prerequisite: the `hive-mind` project exists inside the existing
"Dollhouse Deviants Co." organisation on Supabase (sign in with
GitHub as `musclehed03`), the private bucket `hive-mind-snapshots`
exists, and `.env` holds the Supabase URL + keys (created with `nano
.env` on that machine — never in a word processor, never committed,
never pasted in chat). The live adapter (`app/live_supabase.py`)
is already wired behind the fake adapter's interface; the only
switch is `HIVE_MIND_LIVE=1` with the credentials exported from
`.env` in that shell.

```bash
cd hive-mind-mcp && git pull
set -a; source .env; set +a
export HIVE_MIND_LIVE=1
.venv/bin/python - <<'PYEOF'
import os, tempfile
from app.dispatch import dispatch_tool
from app.live_clients import get_snapshot_adapter
from app.store import Store
store = Store(db_path=os.path.join(tempfile.mkdtemp(), "live-gate.db"),
              vault_dir=tempfile.mkdtemp())
payload, err = dispatch_tool("hivemind_snapshot_backup", {
    "destination_target": "supabase", "schedule_interval": "now",
    "user_handshake_token": "yes"}, store=store)
print(payload["status"], "backed_up:", payload.get("backed_up"),
      "verified_callback:", payload.get("verified_callback"),
      payload.get("storage_path", payload.get("error", "")))
assert payload["status"] == "ok" and payload["verified_callback"]
get_snapshot_adapter("supabase").delete(payload["storage_path"])
print("test snapshot deleted:", payload["storage_path"])
store.close()
PYEOF
unset META_API_KEY HIVE_MIND_LIVE SUPABASE_URL SUPABASE_ANON_KEY SUPABASE_SERVICE_ROLE_KEY
```

Confirm the object appeared in the private bucket before the
delete, and that the delete removed it. If the payload says
`status: "error"`, the upload failed — never report a failed
upload as backed up.

**Result, Nov 1, 2026, 05:50 CT:** `backed_up: True`,
`verified_callback: True` for the test snapshot, and the test
snapshot was deleted via the live adapter. The first attempt
(05:35 CT) failed with an HTTP 405 because the `SUPABASE_URL` in
`.env` was wrong; fixing the URL fixed the gate. The Block 5 live
gate is COMPLETE.

### Other live checks (Nov 1, 2026)

- **Docker:** image built 10/10 and the stdio server answered
  `initialize` on Sonja's Linux machine (02:22–02:23 CT).
  Compose is not installed there; Compose is optional, not a
  submission blocker.
- **GUI + achromatopsia:** Variant A palette, growth stages, EXP
  meter, origin colours + legend, and the Integrations box were
  checked live in the browser; Day verified the achromatopsia
  profile works in pure grayscale, needing only larger text and
  more spacing (user-definable settings).
- **Not run:** a local-endpoint (Ollama) end-to-end check —
  Ollama is not installed on the Linux machine. A real-client SSE
  check was skipped by Sonja's choice; SSE is protocol-tested
  over localhost only. See `docs/SUBMISSION_CHECKLIST.md` for the
  honest-limits record.
