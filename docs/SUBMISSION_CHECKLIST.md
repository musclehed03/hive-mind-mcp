# Hive-Mind — submission package checklist

Deadline: Nov 4, 2026, 9:00 PM ET (8:00 PM CT). Track: Indie Developer.
Theme: Build for Your World.

Last re-checked: Nov 1, 2026 (Blocks 1–17 built; live gates run).

## Code (this repo)

- [x] All 8 `hivemind_` tools implemented, exact spec names/signatures
- [x] Full pytest suite green (247 passed, Nov 1, 2026; see README
      for the current count)
- [x] Live adapters (`app/live_meta.py`, `app/live_supabase.py`)
      are env-gated (`HIVE_MIND_LIVE=1`), tested with mocked HTTP,
      and fake by default; live calls were made ONLY in the gated
      verification runs below, inside the $150 free credits
      ($0.02 used, $0.00 charged; $100 spend notification on)
- [x] No keys, tokens, secrets, or card details anywhere in the repo
- [x] `.env.example` placeholders only; `.env` git-ignored
- [x] Docker zero-config run verified on Sonja's Linux machine
      (Nov 1, 2026: image built, stdio server answered `initialize`)
- [x] Live gate, Block 4: 3 facts verified live via the Meta Model
      API from Sonja's machine (Nov 1, 2026, 05:22 CT)
- [x] Live gate, Block 5: one real snapshot to the private Supabase
      bucket, hash-check passed, test snapshot deleted via the live
      adapter (Nov 1, 2026, 05:50 CT)
- [x] Live gate, GUI: Variant A palette, growth stages, EXP meter,
      origin colours + legend, and Integrations box all checked
      live in the browser; achromatopsia re-checked by Day
      (Nov 1, 2026) — works in pure grayscale
- [x] License chosen: MIT (`LICENSE`, Copyright 2026 Sonja Kelley)

## Known limits (state honestly in the submission, do not oversell)

- SSE transport (`app/sse_server.py`) is protocol-tested on
  localhost only. A real-client check was SKIPPED by Sonja's
  choice (Nov 1, 2026 — she does not use VS Code); stdio is the
  verified transport. Do not claim SSE was client-verified.
- Recall is lexical only; no embeddings are written to the `vecs`
  table. Vector recall is future work, not a shipped feature.
- Local-model (Ollama) live check: NOT RUN — Ollama is not
  installed on the Linux machine (Sonja, Nov 1, 2026). The
  key-optional-for-loopback fix (Block 15) is built and tested,
  but no local endpoint was verified end to end.
- Demo script refreshed for Blocks 9–17 (stages, EXP, Integrations
  box, origin colours; fake mode only on camera), Nov 1, 2026.
  Docs (README, `docs/INTEGRATIONS.md`, demo script) re-checked
  the same day: nothing behind, ports and gate results current.

## Demo

- [x] 3-minute script: `docs/DEMO_SCRIPT.md` (refreshed for
      Blocks 9–17, Nov 1, 2026)
- [ ] Demo recorded (screen capture, GUI + terminal, captions on)
- [ ] Demo run-through done end-to-end on the demo machine
      (re-run after Blocks 9–17 changes, with the refreshed script)

## Submission (Cerebral Valley platform)

- [ ] Project title, description, and theme selected
- [ ] Repo link added (https://github.com/musclehed03/hive-mind-mcp)
- [ ] Demo video link added
- [ ] Meta tooling used listed — claim ONLY what is true: Muse
      Spark via the Meta Model API (Cross-Hatch verification +
      Caveman compression, live-verified Nov 1, 2026); Llama open
      weights noted as the offline-fallback architecture (NOT
      live-verified — Ollama is not installed on the demo
      machine). Do NOT list Muse Code: it was not used to build
      this repo.
- [ ] Accessibility + security (Pillars 5–6) stated as v1 features,
      not future work
- [ ] Submitted before 9:00 PM ET, Nov 4, 2026 — with time to spare
      for the platform's own upload/processing step
