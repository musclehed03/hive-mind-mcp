# Hive-Mind — 3-minute demo script

Total: 3:00 (beats sum to 2:50, plus 10 seconds of breathing room —
rehearse to finish the closing line by 2:50; do not run past 3:10).
Supersedes the Block 8 script: this version shows what shipped in
Blocks 9–17. Read from the spec and the shipped code only; no new
features.

## The one rule for recording: fake mode only

Every terminal call in this script runs in the DEFAULT fake mode:
no `HIVE_MIND_LIVE`, no key, no credits spent, nothing leaves the
machine. The payloads say so on screen (`live: false`,
`fake_meta_calls`). The live Meta/Supabase gates were verified
SEPARATELY on Nov 1, 2026 — Block 4: 3 facts verified live via the
Meta Model API; Block 5: one snapshot uploaded, hash-checked, and
deleted; $0.02 of the $150 free credits used, $0.00 charged — and
are NOT re-run on camera. Never type or paste a key while
recording. If a key prompt appears, stop the take.

## Setup (before recording)

Screen capture: GUI browser window + terminal side by side, captions
on. Record at the machine's native resolution; keep the terminal
font large enough to read at video size.

Autopilot (Block 18): the demo drives itself, so no step has to be
remembered mid-take. The terminal half is
`.venv/bin/python scripts/demo_terminal.py` (6-second pauses;
`--fast` for 1-second pauses, `--step` to wait for Enter) — it
seeds the throwaway store, runs Beats 1–2 plus the Beat 4
micro-bot/snapshot calls, and refuses to start with
`HIVE_MIND_LIVE` set or `META_API_KEY` present. The GUI half is
the **Play demo** button above the graph: it walks Beats 3–4
with a caption per step, 6 seconds a step; Space pauses, Escape
stops, and your colours, profile, and graph view come back
exactly as they were at the end. Either half may be used on its
own; the manual steps below are what the autopilot performs.

```bash
cd hive-mind-mcp && git pull
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt   # sqlite-vec only
```

Seed a throwaway demo store (12 memories, 2 verified, mixed
origins — the GUI stage reads "Protostar, 12 memories, 2 checked").
This uses a temp folder, so the real vault stays clean. Run it from
the repo folder, exactly as written:

```bash
export HIVE_MIND_DEMO_DIR="$(mktemp -d)"
export HIVE_MIND_DB_PATH="$HIVE_MIND_DEMO_DIR/demo.db"
export HIVE_MIND_VAULT_DIR="$HIVE_MIND_DEMO_DIR/vault"
.venv/bin/python - <<'PYEOF'
import os
from app.dispatch import dispatch_tool
from app.store import Store
store = Store(db_path=os.environ["HIVE_MIND_DB_PATH"],
              vault_dir=os.environ["HIVE_MIND_VAULT_DIR"])
seeds = [
    ("The shop opens at 9am on Saturdays", "text", "general", "sonja"),
    ("The garden grows tomatoes in summer", "text", "general", "sonja"),
    ("The library opens at 10am on weekdays", "text", "general", "sonja"),
    ("The shop sells fresh bread", "voice", "general", "sonja"),
    ("Code the server in Python", "text", "coding", "codex"),
    ("Pin the dependency versions before release", "text", "coding", "codex"),
    ("URL: https://example.com/bread\nThe bakery uses stone-milled flour", "clipper", "general", "sonja"),
    ("Simmer the soup for forty minutes", "text", "cooking", "sonja"),
    ("Buy basil at the Saturday market", "voice", "general", "sonja"),
    ("Back up the vault every Sunday night", "text", "general", "sonja"),
]
for content, st, hint, cid in seeds:
    dispatch_tool("hivemind_capture_idea", {
        "content": content, "source_type": st,
        "domain_hint": hint, "client_id": cid}, store=store)
# Verify two facts NOT in the seed set, so nothing appears twice.
for fact in ("The tour bus leaves at 8am sharp",
             "Water the tomatoes after sunset"):
    dispatch_tool("hivemind_crosshatch_verify", {
        "candidate_fact": fact, "domain_repo": "general",
        "source_citation": "demo seed", "supersede_id": ""}, store=store)
store.close()
PYEOF
```

Then start the GUI server in the SAME shell (so it reads the same
temp store) and open the URL it prints:

```bash
.venv/bin/python -m app.gui_server
# Hive-Mind GUI at http://127.0.0.1:8000/ (localhost only)
```

The server sends no cache headers: hard-refresh the page
(`Ctrl+Shift+R`) before recording. Pre-flight: the growth-stage
line reads "Protostar", the EXP line reads 20, and the Origins
list shows more than one origin. If any of those is missing, stop
— the seed did not land in the store the server is reading.

Keep a SECOND terminal ready in the same shell (same exported
variables) for the stdio MCP calls in Beats 1–2. The stdio server
reads one JSON object per line; send `initialize`, then
`notifications/initialized`, then each `tools/call`. Do not set
`HIVE_MIND_LIVE` in either terminal.

## Beat 1 — 0:00–0:40 — Bedroom Epiphany: Capture + Burn-After-Reading (terminal)

On screen: the stdio terminal. Say the voice note out loud, messy,
with the slip in it:

> "I just realised the shop website should open at 9am on
> Saturdays — oh, and my API key is sk-demo-trap-me… never mind,
> send that to the coding repo. Also tell Day the shop sells
> fresh bread."

Send the `hivemind_capture_idea` call (source_type "voice",
domain_hint "coding", client_id "sonja"). Point at the result:
`trapped_count: 1`, kind `API_KEY`. Say:

> "The key never reaches storage. The scrubber traps it first,
> every time, before anything is written or sent. One capture,
> never restated."

Note for the presenter: `sk-demo-trap-me` is a made-up demo
string, not a real key. The stored text reads `REDACTED API KEY`
— show that in Beat 2's query result.

## Beat 2 — 0:40–1:20 — Cross-Hatch + Caveman (terminal)

On screen: the same terminal. Run `hivemind_query_temporal` for
"shop opening hours", tier `recent_0_3m`, format `caveman`.
Point at the shorthand line, the Token Ekonomi Meter (raw vs
injected tokens, % saved), and the `fake_meta_calls` field — the
fake client is labelled, not hidden. Say:

> "Ask in plain words, get back shorthand. Fewer tokens, same
> fact, and the answer says which client produced it."

Then run `hivemind_crosshatch_verify` with a conflicting opening
time ("The shop opens at 10am on Saturdays") and NO `supersede_id`.
Show the refusal to silently overwrite. Then re-run it WITH the
`supersede_id` from the refusal and show the Conflict Diff & Merge
entry (`- old / + new [Attested]`). Say:

> "A contradiction never overwrites quietly. It waits for a
> human yes, and the change is written down."

## Beat 3 — 1:20–2:10 — Money Shot GUI (browser)

On screen: the GUI at `http://127.0.0.1:8000/`. Walk it in this
order, one action per sentence:

1. The palette: near-black background, orchid-pink accents, one
   thin brushed-gold line under the header. Say: "This is the
   Posh palette — quiet, not neon."
2. The growth-stage line: "Protostar — 12 memories, 2 checked."
   Say: "The sky grows as memories arrive. More memories, and
   more checked facts, make it brighter. Ten memories wakes the
   Protostar; thirty makes a Star; seventy-five, a Radiant Sun."
3. The EXP line (reads 20). Say: "Points for healthy memories
   only — checked facts, settled mix-ups, backups. Never for
   spending on API calls."
4. The Origins list under the graph, then Regular Settings →
   Origin colours: change ONE origin's ring colour. Say: "Every
   dot says who made it — which model, which app, which person.
   You pick the colours. And every origin also has its own ring
   pattern, so the meaning survives without colour at all."
5. The metaphor dropdown: switch to Tree of Life, then back to
   Nebula. Say: "Same memories, different picture."
6. Click the Achromatopsia profile. The whole page goes pure
   grayscale. Point at the graph: rings, patterns, and the
   Origins list are all still readable. Say: "One click, pure
   grayscale, nothing lost. This was checked by Day, who sees in
   grayscale only." Click the profile off again.
7. Click Read aloud. Say: "And it reads itself out loud."

## Beat 4 — 2:10–2:50 — Integrations, Micro-Bot, Backup (browser + terminal)

On screen: scroll the GUI to the Integrations box. Point at the
status rows (MCP server, model endpoint, backup, EXP), press one
Copy button, watch it say "Copied". Say:

> "Connecting is copy-and-paste, not configuration archaeology.
> Keys are never typed here — they live in one local file, and
> this page only ever says whether one is present."

Back in the terminal, run `hivemind_spawn_microbot` (template
"digest", mode "simple"): show the 8–14KB script and run it with
`--dry-run`. Say: "A tiny helper bot, grown from the same
memories. It rehearses before it ever acts." Then run
`hivemind_snapshot_backup` (destination "supabase", schedule
"now", handshake "yes"): show `status: local_only`, the local
bundle path, `verified_callback: true`, and `backed_up: false`.
Say:

> "No cloud configured, no problem — a local bundle, hash-checked
> back. A failed upload is never reported as backed up."

One honest line, spoken plainly, then move on — do not dwell:

> "What this demo doesn't show: the live checks ran separately,
> recall here matches words rather than meanings, and the
> browser-streaming option is tested on this machine only."

## Close — 2:50–3:00

On screen: the GUI graph, Protostar stage visible. Say:

> "Hive-Mind. Never Restate Yourself — one memory layer, every
> client, scrubbed before storage, verified before recall.
> github.com/musclehed03/hive-mind-mcp"

## After recording

Unset the demo variables and remove the temp store (the seed was
throwaway; the real vault was never touched):

```bash
unset HIVE_MIND_DEMO_DIR HIVE_MIND_DB_PATH HIVE_MIND_VAULT_DIR
```

Captions on, file named `hive-mind-demo-3min.mp4`, link added to
the submission before Nov 4, 2026, 9:00 PM ET (8:00 PM CT).
