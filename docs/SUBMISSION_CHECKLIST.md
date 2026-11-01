# Hive-Mind — submission package checklist

Deadline: Nov 4, 2026, 9:00 PM ET (8:00 PM CT). Track: Indie Developer.
Theme: Build for Your World.

## Code (this repo)

- [x] All 8 `hivemind_` tools implemented, exact spec names/signatures
- [x] Full pytest suite green (see README for the current count)
- [x] No live network calls made; default is fake Meta/Supabase
      clients; live adapters (`app/live_meta.py`,
      `app/live_supabase.py`) are env-gated (`HIVE_MIND_LIVE=1`) and
      tested with mocked HTTP only
- [x] No keys, tokens, secrets, or card details anywhere in the repo
- [x] `.env.example` placeholders only; `.env` git-ignored
- [x] Docker zero-config run documented (verify on a Docker machine —
      NOT verified in the build VM; see README)
- [ ] Live gate, Block 4: 3–5 real Meta Model API calls from Sonja's
      machine (commands in README; UNVERIFIED until run)
- [ ] Live gate, Block 5: one real snapshot to the private Supabase
      bucket, hash-check, then delete the test snapshot (UNVERIFIED)
- [x] License chosen: MIT (`LICENSE`, Copyright 2026 Sonja Kelley)

## Demo

- [x] 3-minute script: `docs/DEMO_SCRIPT.md`
- [ ] Demo recorded (screen capture, GUI + terminal, captions on)
- [ ] Demo run-through done end-to-end on the demo machine (see
      "Demo run-through" in the build report; re-run after any change)

## Submission (Cerebral Valley platform)

- [ ] Project title, description, and theme selected
- [ ] Repo link added (https://github.com/musclehed03/hive-mind-mcp)
- [ ] Demo video link added
- [ ] Meta tooling used listed: Muse Spark via Meta Model API
      (Cross-Hatch verification + Caveman compression), Muse Code
      (build agent), Llama open weights noted as the offline fallback
- [ ] Accessibility + security (Pillars 5–6) stated as v1 features,
      not future work
- [ ] Submitted before 9:00 PM ET, Nov 4, 2026 — with time to spare
      for the platform's own upload/processing step
