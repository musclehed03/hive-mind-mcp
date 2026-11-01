# Hive-Mind — 3-minute demo script

Total: 3:00. Read from the spec and the brainstorm doc only; no new
features. Run the GUI server first (`python -m app.gui_server`, open
http://127.0.0.1:8765/), and keep a terminal with the stdio MCP server
ready. All demo calls use the fake Meta client — the live gate is
separate (see README, "Live gates — UNVERIFIED").

## 0:00–0:45 — Bedroom Epiphany (capture + Burn-After-Reading)

Say it as a messy voice note, out loud, with a slip in it:

> "I just realised the shop website should open at 9am on Saturdays —
> oh, and my API key is sk-demo… never mind, send that to the coding
> repo. Also tell Day the shop sells fresh bread."

Run `hivemind_capture_idea` with that text (source_type "voice",
domain_hint "coding"). Show: the scrubber traps the key before storage
(`trapped_count` in the payload), the fact lands in the coding repo,
and the bread fact is routed cross-domain with provenance — one
capture, never restated.

## 0:45–1:30 — Cross-Hatch Compression & Temporal Callback

From a different client (or a second terminal), run
`hivemind_query_temporal` for "shop opening hours" with
`temporal_tier` "recent_0_3m", `format_mode` "caveman". Show: the
Caveman shorthand line, the Token Ekonomi Meter (raw vs injected
tokens, % saved), and the inline citation
`fact [source]` on the cross-hatch verified line. Then run
`hivemind_crosshatch_verify` with a conflicting opening time and a
`supersede_id`: show the refusal to silently overwrite, then the
Conflict Diff & Merge entry (`- old / + new [Attested]`) once the
supersede is confirmed.

## 1:30–2:15 — Money Shot GUI

In the browser: the nebula graph. A new memory node ignites — show the
node appearing, its shape (circle/square/triangle by domain) and its
edge line style (solid shared entity, dashed superseded). Switch the
metaphor dropdown to Tree of Life, then back. Turn on the
Achromatopsia preset: the whole UI goes pure grayscale and every node
is still distinguishable by shape and line style alone. Turn on
read-aloud on one node: the screen-reader callout reads the fact.

## 2:15–3:00 — Micro-Bot Spawn & 1-Click Weekly Backup

Run `hivemind_spawn_microbot` (template "digest", mode "simple"):
show the 8–14KB script, its size and SHA-256, and run it with
`--dry-run`. Slide the mode to Pro with the Sentinel template and no
allowance: show the refusal to arm. Then run
`hivemind_snapshot_backup` with a handshake token: show the local
bundle, the verified callback (re-download + hash check), and the
`local_only` result when no adapter is configured — a failed upload
is never reported as backed up.

Close: "One memory layer, every client, nothing restated. Local-first,
scrubbed before storage, verified before recall."
