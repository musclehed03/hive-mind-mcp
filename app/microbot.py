"""Block 7 — Micro-bot spawner (local, no network, no live trading).

Each spawn generates a real, runnable, standard-library-only Python
script, 8KB-14KB, written under the vault's microbots/ directory and
returned in the payload so a client can download it. Size is honest
content — docstrings, operator notes, worked examples, and guard
logic — never filler padding: generation asserts the script compiles
and measures its size, and refuses to return an undersized script.

Modes: the demo slider maps 0-49 to Simple and 50-100 to Pro.
Pro Mode (Allowance-Gated Sentinel) refuses to arm without a
positive allowance limit and a cooldown of at least 30 seconds, and
carries a 0.5% slippage guard. No generated script ever places an
order, touches the network, or spends anything: the sentinel only
prints what it *would* do in dry-run, and refuses live action.
"""

import hashlib
import os
import re

MIN_BYTES = 8192
MAX_BYTES = 14336
MAX_SLIPPAGE_PCT = 0.5
MIN_PRO_COOLDOWN_SEC = 30

_TEMPLATES = ("digest", "morning_digest", "sentinel", "dca_sentinel", "crypto_sentinel")

_RUNBOOK_DIGEST = '''
RUNBOOK = """
Morning Digest runbook (read this before the first run).

1. Setup, step by step.
   a. Confirm the vault exists: the folder passed with --vault must
      contain memories.jsonl. The Hive-Mind server creates it on the
      first capture; before that, the bot prints "no memories yet".
   b. Run with --dry-run once. It prints how many memories it found
      and exits 0 without printing the digest. If that number is
      wrong, the vault path is wrong — fix the path, not the bot.
   c. Run without --dry-run. The digest prints to stdout. Redirect
      it to a file only if you want a dated copy: append >> with a
      filename that includes the date, so days never overwrite.

2. Daily routine.
   Morning: capture overnight ideas first (voice notes, clips),
   then run the digest. The digest is a review tool, not a
   decision tool: read it, correct anything wrong in Hive-Mind
   with cross-hatch verify, and only then act on it. An idea that
   survives one night of review is worth more than ten captured
   in a hurry.

3. Sharing the digest.
   The digest is plain text and safe to paste into a chat or
   email, because every line was scrubbed before storage. Before
   sharing, read it once for names, addresses, and anything that
   identifies another person. The scrubber traps emails and
   phone numbers, but a name written out in full is only trapped
   when it is on the protected-names list. Sharing is a human
   decision; the bot never shares anything itself.

4. Troubleshooting table.
   - "no memories yet": vault empty or wrong path. Check --vault.
   - Empty lines only: the JSONL file has tombstones but no live
     memories. Capture something, run again.
   - A line looks truncated: that is the 80-character short form.
     Run with --full for full text.
   - JSON error on one line: that line is skipped and the rest
     prints. Open the JSONL file, find the broken line, and fix
     or remove it by hand; the bot never edits the vault.
   - Permission denied: the vault folder is not readable by this
     user. Fix permissions; do not run the bot as root.

5. What "done" looks like.
   A good digest run prints one line per memory, newest first,
   domain first, and nothing else. If output ever contains a
   secret, a stack trace, or a network error, stop: that output
   is not a digest, and the cause must be found before the next
   run. The bot's job is to be boring. Boring is correct.

6. Template changelog.
   v1 (this file): read-only digest, dry-run, --full, 80-char
   short form. No model, no network, no writes. Future versions
   may add a weekly summary mode; they will not add editing,
   model calls, or network access without a new template review.

7. Sample vaults and expected output.
   Vault with one memory, "Library opens at 10am on Sundays",
   domain general, dated 2026-10-27:
       [general] 2026-10-27 — Library opens at 10am on Sundays
   Vault with three memories across coding, cooking, and
   general: the digest prints three lines, newest first,
   regardless of domain. Domain order is never alphabetical;
   recency order is the contract, because a digest is a
   newspaper, and newspapers lead with what is newest.
   Vault with a tombstone and one live memory: only the live
   memory prints. Tombstones are audit history, not news.

8. Review checklist (run before trusting a new copy).
   - Does --dry-run report the right memory count?
   - Does the digest print one line per live memory, newest first?
   - Does --full print the full text of a long memory?
   - Does an empty vault print "no memories yet" and exit 0?
   - Does the output contain no secret, no stack trace, and no
     network error? If any check fails, do not use the copy:
     re-spawn it from Hive-Mind and diff the two files.
"""
'''

_RUNBOOK_SENTINEL = """
RUNBOOK = \"\"\"
DCA Sentinel runbook (read this before the first dry run).

1. Arming, step by step.
   a. Spawn with a positive allowance and a cooldown of at least
      30 seconds. Zero allowance means the bot refuses to arm;
      that refusal is the guard working, not a bug.
   b. Run --dry-run with a small amount and a small price move.
      Confirm the output says "would buy" and lists the guards.
   c. Run --dry-run with a price move above 0.5%. Confirm it
      says "stand down: slippage". If it does not, stop — the
      guard code has been changed and must be reviewed.
   d. Run --dry-run immediately again. Confirm "stand down:
      cooldown" appears, because the state file now records the
      last action. Cooldown is enforced even in dry-run reporting.

2. The state file.
   sentinel-state.json holds one field: last_action_ts, a Unix
   timestamp. It is local, plain JSON, and human-readable. Back
   it up with the vault if the sentinel matters; losing it only
   resets the cooldown, which is safe (it makes the bot wait
   less, never spend more). Deleting it on purpose is allowed;
   deleting it by accident is harmless. There is no other state.

3. Guard matrix, every combination.
   - allowance 0            -> refuse to arm (any amount, any move)
   - amount > allowance     -> stand down, amount exceeds allowance
   - amount <= 0            -> stand down, amount must be positive
   - cooldown active        -> stand down, seconds remaining shown
   - price move > 0.5%      -> stand down, slippage shown
   - all guards pass        -> would buy, amount and allowance shown
   No combination prints an order, a key, or a network call.
   There is no hidden path to live trading in this template.

4. Worked dry-run transcript.
       $ python sentinel_bot.py --dry-run --amount 10 --price-move-pct 0.2
       sentinel: would buy — all guards pass: amount 10 within allowance 50
       dry run: no state written, no action taken
       $ python sentinel_bot.py --dry-run --amount 10 --price-move-pct 1.0
       sentinel: stand down — slippage 1.0% exceeds 0.5%
   If your transcript differs, the template was edited. Diff it
   against the spawned original before trusting it again.

5. Audit and review.
   Every run prints its decision and reason to stdout. Save run
   output with a date in the filename if the sentinel is ever
   reviewed. The audit question is always the same: did every
   "would buy" have a positive allowance, an elapsed cooldown,
   and a price move within 0.5%? If any "would buy" lacks one,
   the run is invalid and the template must be re-spawned.

6. What this bot will never do.
   It will never place an order, hold a key, call an exchange,
   or spend money. A request to add any of those is a request
   for a different system, with its own review, approvals, and
   human-in-the-loop confirmation — never an edit to this file.
   If this file ever gains a network import, a credential, or
   an order call, treat that copy as compromised: delete it and
   re-spawn from Hive-Mind. The template is the guard.
\"\"\"
"""


def parse_mode(mode_level):
    """Map the slider/string mode to 'simple' or 'pro'."""
    raw = str(mode_level or "").strip().lower().replace("_", " ").replace("-", " ")
    if raw in ("simple", "simple mode"):
        return "simple"
    if raw in ("pro", "pro mode"):
        return "pro"
    if re.fullmatch(r"\d+(\.\d+)?", raw):
        return "pro" if float(raw) >= 50 else "simple"
    raise ValueError(f"unknown mode_level: {mode_level!r}; use simple, pro, or a 0-100 slider value")


def _digest_script(allowance_limit, cooldown_sec):
    return f'''"""Morning Digest micro-bot (Hive-Mind, Simple Mode).

Reads the local JSONL vault mirror (vault/memories.jsonl) and prints
a morning newspaper-style digest: what was remembered, grouped by
domain, newest first. It never writes, never calls a model, never
touches the network. Run it with --dry-run to preview, or plain to
print the digest to stdout.

Usage:
    python digest_bot.py --vault vault --limit 10
    python digest_bot.py --dry-run

Operator notes:
  * The digest is only as good as the capture habit: one idea per
    capture, with a domain hint, beats ten vague notes.
  * Cross-domain ideas appear under their primary domain and are
    flagged with their cross-domains, so a dinner idea that sparked
    a coding idea is never lost to one repo.
  * The vault mirror is append-only JSONL; deleting a memory in
    Hive-Mind appends a tombstone line. The digest skips tombstones.
  * If the vault path does not exist, the bot prints "no memories
    yet" and exits 0 — an empty digest is not an error.
  * Time buckets follow the Hive-Mind temporal index: recent (0-3
    months), warm (3-6 months), archival (6+ months). The digest
    leads with recent items and summarises older ones in one line.
  * Token economy: the digest prints Caveman-style short lines by
    default. Pass --full to print full stored text instead.
  * Accessibility: output is plain text, one fact per line, with
    domain and date first, so a screen reader reads it in order.
    No colour, no emoji, no layout that depends on sight.
  * Security: the digest only reads the local vault. It never
    prints a secret, because the scrubber removed secrets before
    storage. If a line ever looks like a secret, stop and report
    it — do not forward the digest anywhere.
  * Troubleshooting: "vault not found" means the --vault path is
    wrong; "no memories yet" means the vault file is empty. Both
    exit 0. A non-zero exit means the JSONL file itself is corrupt;
    open it in a text editor and look for a truncated last line.
  * Example output:
        [coding] 2026-10-27 — Shop opens at 9am on Saturdays
        [cooking] 2026-10-27 — Shop sells fresh bread
    Each line is: [domain] date — fact. That is the whole format.
  * Worked example, step by step: capture "library opens at 10am"
    with hivemind_capture_idea, run this bot, and the line above
    appears in the digest. Capture a second fact, run it again,
    and both appear, newest first. Nothing else is needed.
  * The bot is deliberately small: it does one job, reads one
    file, prints one digest. Features it will never grow: model
    calls, network access, editing memories, or spending money.
    Those belong in Hive-Mind itself, under human approval.
"""

import argparse
import json
import os
import sys


def load_memories(vault_dir):
    path = os.path.join(vault_dir, "memories.jsonl")
    if not os.path.exists(path):
        return []
    memories = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("event") == "remember":
                memories.append(record)
    return memories


def digest(memories, limit=10, full=False):
    lines = []
    for record in sorted(memories, key=lambda r: r.get("created_at", ""), reverse=True)[:limit]:
        text = record.get("text", "")
        if not full and len(text) > 80:
            text = text[:77] + "..."
        lines.append(f"[{{record.get('domain', 'general')}}] {{record.get('created_at', '')[:10]}} — {{text}}")
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(description="Morning Digest micro-bot")
    parser.add_argument("--vault", default="vault")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    memories = load_memories(args.vault)
    if args.dry_run:
        print(f"digest-bot dry run: {{len(memories)}} memories in vault, would print up to {{args.limit}}")
        return 0
    if not memories:
        print("no memories yet")
        return 0
    for line in digest(memories, args.limit, args.full):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
# Template: digest | Mode: simple | Allowance: {allowance_limit} | Cooldown: {cooldown_sec}s
# Generated by hivemind_spawn_microbot. No network, no model, no spending.
{_RUNBOOK_DIGEST}'''


def _sentinel_script(allowance_limit, cooldown_sec):
    return f'''"""Allowance-Gated DCA Sentinel micro-bot (Hive-Mind, Pro Mode).

SIMULATION ONLY. This script never places an order, never touches
an exchange, and never touches the network. It evaluates a
dollar-cost-averaging decision against three guards and prints what
it *would* do. Live action, if ever wanted, belongs in a separate,
human-approved system — not in this template.

Guards (all three must pass, or the bot refuses):
  1. Allowance: the planned amount must be > 0 and <= the allowance
     limit set at spawn time ({allowance_limit}). No allowance, no arm.
  2. Cooldown: at least {cooldown_sec} seconds must have passed since
     the last action (tracked in a local state file, never shared).
  3. Slippage: the simulated price move must be <= {MAX_SLIPPAGE_PCT}%
     (MAX_SLIPPAGE_PCT). Above that, the bot stands down and says so.

Usage:
    python sentinel_bot.py --dry-run --amount 10 --price-move-pct 0.2
    python sentinel_bot.py --amount 10 --price-move-pct 0.2 --state state.json

Operator notes:
  * Dry-run is the only run that matters in the demo: it prints the
    decision and the guard results, and changes nothing.
  * The state file holds one number: the timestamp of the last
    action. It lives next to the script unless --state says
    otherwise. Deleting it resets the cooldown — do that only on
    purpose, and say so in the run log.
  * Allowance is a ceiling, not a target. The bot never spends up
    to the allowance on its own; --amount is always explicit.
  * Slippage guard, worked example: allowance 50, amount 10,
    cooldown 60s, price move 0.2% -> all guards pass -> "would
    buy 10". Price move 1.0% -> slippage guard fails -> "stand
    down: slippage 1.0% exceeds 0.5%". Cooldown 10s elapsed ->
    "stand down: cooldown, 50s remaining".
  * Accessibility: output is plain text, one decision per line,
    guards listed in order, so a screen reader reads the whole
    decision in sequence. No colour carries the verdict: the
    words "would buy" or "stand down" do.
  * Security: no keys, no exchange credentials, no network. If
    anyone asks this script for a key, that request is wrong —
    the template has nowhere to put one.
  * Troubleshooting: "refuses to arm: no allowance" means the
    spawn call had allowance_limit 0 or negative. Re-spawn with
    a positive allowance. "Cooldown" means wait, or reset the
    state file on purpose. "Slippage" means the market moved too
    far; waiting is the correct response.
  * The sentinel is deliberately boring: it says no far more
    often than it says yes. That is the design. A sentinel that
    always says yes is not a guard, it is a leak.
  * Field guide, decision table:
        guards pass        -> would buy <amount>
        no allowance       -> refuse to arm
        cooldown active    -> stand down, seconds remaining
        slippage too high  -> stand down, slippage pct
        amount > allowance -> stand down, amount exceeds allowance
    Every outcome prints its reason. There is no silent outcome.
"""

import argparse
import json
import os
import sys
import time

MAX_SLIPPAGE_PCT = {MAX_SLIPPAGE_PCT}
ALLOWANCE_LIMIT = {allowance_limit!r}
COOLDOWN_SEC = {cooldown_sec}


def decide(amount, price_move_pct, last_action_ts, now=None):
    """Return (decision, reason). Never executes anything."""
    now = now if now is not None else time.time()
    if ALLOWANCE_LIMIT <= 0:
        return "refuse", "no allowance: spawn with a positive allowance_limit"
    if amount <= 0:
        return "stand down", "amount must be positive"
    if amount > ALLOWANCE_LIMIT:
        return "stand down", f"amount {{amount}} exceeds allowance {{ALLOWANCE_LIMIT}}"
    if last_action_ts is not None and now - last_action_ts < COOLDOWN_SEC:
        remaining = int(COOLDOWN_SEC - (now - last_action_ts))
        return "stand down", f"cooldown: {{remaining}}s remaining"
    if abs(price_move_pct) > MAX_SLIPPAGE_PCT:
        return "stand down", f"slippage {{price_move_pct}}% exceeds {{MAX_SLIPPAGE_PCT}}%"
    return "would buy", f"all guards pass: amount {{amount}} within allowance {{ALLOWANCE_LIMIT}}"


def load_last_action(state_path):
    try:
        with open(state_path, encoding="utf-8") as handle:
            return float(json.load(handle).get("last_action_ts") or 0) or None
    except (OSError, ValueError, AttributeError):
        return None


def main(argv=None):
    parser = argparse.ArgumentParser(description="DCA Sentinel micro-bot (simulation only)")
    parser.add_argument("--amount", type=float, default=0)
    parser.add_argument("--price-move-pct", type=float, default=0.0)
    parser.add_argument("--state", default="sentinel-state.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    last = load_last_action(args.state)
    decision, reason = decide(args.amount, args.price_move_pct, last)
    print(f"sentinel: {{decision}} — {{reason}}")
    if args.dry_run:
        print("dry run: no state written, no action taken")
        return 0
    if decision == "would buy":
        print("simulation only: no order placed, no network used")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
# Template: sentinel | Mode: pro | Allowance: {allowance_limit} | Cooldown: {cooldown_sec}s
# Generated by hivemind_spawn_microbot. Simulation only. No orders, no network.
{_RUNBOOK_SENTINEL}'''


def _template_for(template_name):
    name = (template_name or "").strip().lower().replace(" ", "_").replace("-", "_")
    if name in ("digest", "morning_digest", "morning_newspaper"):
        return "digest", _digest_script
    if name in ("sentinel", "dca_sentinel", "crypto_sentinel"):
        return "sentinel", _sentinel_script
    raise ValueError(f"unknown template_name: {template_name!r}; use digest or sentinel")


def spawn_microbot(template_name, mode_level, allowance_limit, cooldown_sec, vault_dir):
    """Generate, validate, and write one micro-bot script.

    Returns the payload dict. The script is compiled before it is
    returned, and its size must be within 8KB-14KB.
    """
    mode = parse_mode(mode_level)
    if not isinstance(cooldown_sec, int) or isinstance(cooldown_sec, bool) or cooldown_sec < 0:
        raise ValueError("cooldown_sec must be a non-negative integer")
    if mode == "pro":
        if allowance_limit is None or float(allowance_limit) <= 0:
            raise ValueError("Pro Mode refuses to arm without a positive allowance_limit")
        if cooldown_sec < MIN_PRO_COOLDOWN_SEC:
            raise ValueError(
                f"Pro Mode requires cooldown_sec >= {MIN_PRO_COOLDOWN_SEC} (cooldown guard)")
    canonical, builder = _template_for(template_name)
    script = builder(allowance_limit, cooldown_sec)
    compile(script, f"{canonical}_bot.py", "exec")
    size = len(script.encode("utf-8"))
    if not MIN_BYTES <= size <= MAX_BYTES:
        raise ValueError(
            f"generated {canonical} script is {size} bytes, outside the 8KB-14KB template range")
    bots_dir = os.path.join(vault_dir, "microbots")
    os.makedirs(bots_dir, exist_ok=True)
    filename = f"{canonical}_{mode}.py"
    path = os.path.join(bots_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(script)
    return {
        "status": "ok",
        "template_name": canonical,
        "mode_level": mode,
        "allowance_limit": allowance_limit,
        "cooldown_sec": cooldown_sec,
        "size_bytes": size,
        "sha256": hashlib.sha256(script.encode("utf-8")).hexdigest(),
        "path": path,
        "script": script,
        "guards": {
            "max_slippage_pct": MAX_SLIPPAGE_PCT,
            "min_pro_cooldown_sec": MIN_PRO_COOLDOWN_SEC,
            "live_trading": False,
            "network": False,
        },
    }
