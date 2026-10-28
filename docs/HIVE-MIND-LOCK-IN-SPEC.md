# HIVE-MIND MCP ("Never Restate Yourself") — APPROVED MASTER LOCK-IN SPEC
**Approved by:** Sonja Kelley | **Date:** Tue Oct 27, 2026
**Target:** Meta Global MCP Hackathon | **Deadline:** Wed Nov 4, 2026, 8:00 PM CT
**Judging Weights:** Impact (30%) | Meta Tooling (25%) | Demo (25%) | Tech Depth (20%)
**Status:** SETTLED & APPROVED FOR BUILD / CODEX `/plan`

---

## 1. THE 6 PILLARS OF ETHICS (Settled Definitions)
Pillars 1–4 govern efficiency. Pillars 5–6 are mandatory v1 gating foundations that constrain Pillars 1–4 across every module.

1. **Computing-in-memory** — Compute where the data lives (in-memory/SQLite compute) instead of shuttling raw payloads back and forth; efficiency is measured by work done per move avoided.
2. **Event-driven spiking** — The system stays silent until state changes, firing a sparse spike for that change only; zero polling, zero always-on compute burn.
3. **Extreme sparsity / dynamic routing** — Only the domain repos, sub-bots, and parameters an input actually requires are activated per request; everything else stays dormant.
4. **Continuous local learning** — State evolves locally with strict provenance and a non-destructive changelog (`superseded` status + diff toast); never silently overwrites or drifts.
5. **Accessibility (Gating Foundation)** — Ships in v1 with the full Sensory Suite: Focus Mode, Safe Motion, Readable Font, High Contrast, Color Blind Support (typed palettes including pure-grayscale achromatopsia), Light Theme, and Simplified View. Every screen, star-node, button, image, GIF, and logo carries explicit ARIA labels and alt text. Visual states are distinguished by geometry (Circle/Square/Triangle) and line style (`2px solid` vs. `2px dashed` vs. `2px dotted`), never color alone.
6. **Security (Gating Foundation)** — Zero-trust "Burn-After-Reading" Temporary Cache Buffer before any data touches persistent storage; least-privilege read/write tool separation; human-in-the-loop confirmation for destructive/financial actions; secrets never embedded in code or prompts; full audit trail.

---

## 2. DESIGN SYSTEM & PALETTE INTEGRATION
* **Source of Truth:** Uses the settled Deluxe Posh / Mature App Palette co-designed with Baxter, committed directly to the `Dollhouse Deviants Co.` website GitHub repository.
* **Structural & Accessibility Rules:** All borders remain explicit `2px` (`solid` for primary frames, `dashed` for secondary tags/links, `dotted` for tertiary controls) paired with distinct geometric node shapes so pure grayscale / achromatopsia mode retains 100% visual hierarchy without relying on pigment.

---

## 3. THE 8 SETTLED MCP TOOLS (Surface Architecture)
**Rules:** `snake_case`, `hivemind_` prefix, flat scalar arguments (no nested dicts), strict read/write separation, built-in explainer metadata. Maps cleanly over internal `remember`, `recall`, `forget`, and `memory_stats` primitives.

1. `hivemind_capture_idea(content, source_type, domain_hint, client_id)`
   * **Role:** Ingests text, voice transcripts, or Chrome web-clipper payloads into the Temporary Cache Buffer. Automatically invokes the internal `scrub_input` pre-step before any disk write.
2. `hivemind_scrub_input(raw_text, strictness_level)`
   * **Role:** Auditable Burn-After-Reading gate. Runs a zero-cost, 0ms local **Deterministic Regex + Shannon Entropy Pre-Gate** (trapping API keys, `sk-/ghp-` tokens, Bearer strings, emails, phone numbers, SSNs, and protected real names) before any LLM call. Returns scrubbed text + audit count of trapped items.
3. `hivemind_crosshatch_verify(candidate_fact, domain_repo, source_citation, supersede_id)`
   * **Role:** Polls candidate facts against the 6 Pillars + common-sense logic using Meta Llama API. Embeds the **5 OKF Trust Signals** (`sources`, `generated_by`, `verified_by`, `stale_after`, `status`, `attested_computation`). Injects citations **inline immediately after the claim**. On conflict, marks old fact `superseded` and emits a 1-line **Conflict Diff & Merge** changelog entry.
4. `hivemind_query_temporal(query, temporal_tier, token_budget, format_mode)`
   * **Role:** Queries across the 3-Tier Temporal Index (`recent_0_3m`, `warm_3_6m`, `archival_6m_plus`). Returns ultra-compressed **Caveman Shorthand** payloads + file-passing pagination + **Token Ekonomi Meter** stats (`raw_tokens` vs `injected_tokens` saved). On "not found", returns 1–3 reasoned refocus/workaround strategies.
5. `hivemind_spawn_microbot(template_name, mode_level, allowance_limit, cooldown_sec)`
   * **Role:** Spawns an 8KB–14KB downloadable/local micro-agent from the memory layer. Demo includes a 1-click slider scaling from **Simple Mode** ("Morning Newspaper/Digest Bot" for 12–80+ yr accessibility) to **Pro Mode** ("Allowance-Gated Crypto/DCA Sentinel" with cooldown & slippage guards).
6. `hivemind_snapshot_backup(destination_target, schedule_interval, user_handshake_token)`
   * **Role:** Automated weekly snapshot hook (default `7d`, user-tunable or manual "Sync Now"). Dumps inspectable SQLite/JSONL/Markdown bundle to Google Drive or Supabase storage with verified callback hook.
7. `hivemind_explain(topic_or_tool_name, reading_level)`
   * **Role:** Zero-jargon Index-Key Explainer accessible via MCP or GUI Settings/Manual. Explains any tool, parameter, or pillar clearly for ages 12 to 80+.
8. `hivemind_prune_memory(target_id_or_rule, decay_policy, human_confirm_token)`
   * **Role:** Deterministic deletion, `stale_after` expiration purge, or manual override. Requires explicit human-in-the-loop confirmation token for destructive writes.

---

## 4. FIVE LOCKED DIFFERENTIATOR FEATURES (For Demo & Rubric Dominance)
1. **Localhost Chrome Web-Clipper / Bookmarklet Bridge:** 1-click browser capture into `hivemind_capture_idea` to prove cross-client portability live on camera.
2. **OKF 5 Trust Signals Schema:** Every memory node carries `sources`, `verified_by`, `stale_after`, `status`, and `attested_computation` metadata.
3. **Live "Caveman Token Ekonomi Meter":** Real-time UI widget + tool response header showing exact token % and dollar savings per recall.
4. **Zero-Cost Local Regex + Entropy Pre-Scrubber:** Guarantees secrets are trapped locally in 0ms before any cloud model API is ever touched.
5. **Non-Destructive "Conflict Diff & Merge" Toast:** Visual `- Old Fact / + New Fact [Attested]` changelog on the knowledge graph whenever a memory updates.

---

## 5. NOV 4 BUILD & DEMO SCOPE LOCK
* **Storage Default:** Local-first **SQLite + JSONL** (zero-config Docker container) with 1-click cloud sync hook to **Supabase / Google Drive**.
* **Visual "Money Shot" GUI:** Interactive 2D/WebGL **Cosmic "Birth of a Star / Nebula" Knowledge Graph** as the active primary canvas, featuring a high-visibility dropdown selector that switches to interactive SVG mock-up placeholders for **Tree of Life**, **Spherical Mandala**, and **Mythical Road Map**.
* **Micro-Bot Demo:** 1-click toggle between **Simple Mode** (Daily Digest) and **Pro Mode** (Allowance-Gated Sentinel).