#!/usr/bin/env python3
"""Terminal half of the Hive-Mind demo autopilot (Block 18).

Runs DEMO_SCRIPT.md Beats 1-2 (plus the Beat 4 terminal calls)
against the stdio MCP server, printing each narration caption
BEFORE its call and each result payload after it, with pauses
between steps so Sonja only has to narrate — no step to remember,
no command to type mid-take.

FAKE MODE ONLY, by construction:
- Refuses to start when HIVE_MIND_LIVE is set (other than "0") or
  META_API_KEY is present in the environment — exit code 2, before
  the server starts, in plain words.
- Builds its own throwaway store in a fresh temp dir (sets
  HIVE_MIND_DB_PATH / HIVE_MIND_VAULT_DIR for the server child
  only) and removes it on exit unless --keep is given. The real
  vault is never touched, and no key is ever read: this script
  never opens .env, and the child is started with the live-mode
  variables stripped.
- No network: the child is a local subprocess speaking JSON-RPC
  over pipes, and the fake client answers every verification.

Usage (from the repo folder, with the venv):
    .venv/bin/python scripts/demo_terminal.py [--fast] [--step] [--keep]

  --fast   1-second pauses instead of 6 (rehearsal / tests).
  --step   Wait for Enter before each step instead of pausing.
  --keep   Keep the temp store and print its path (debugging).

Exit codes: 0 = all steps ran and every expected shape matched;
2 = live-mode environment refused; 3 = a step returned an
unexpected shape (the build changed under the script).
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_DWELL_SEC = 6
FAST_DWELL_SEC = 1

# The messy voice note from Beat 1, verbatim from the script. The
# sk-demo-trap-me string is a made-up demo value, not a real key:
# the scrubber must trap it (trapped_count 1) before storage.
BEAT1_CONTENT = (
    "I just realised the shop website should open at 9am on Saturdays"
    " — oh, and my API key is sk-demo-trap-me… never mind,"
    " send that to the coding repo. Also tell Day the shop sells"
    " fresh bread."
)

SEEDS = [
    ("The shop opens at 9am on Saturdays", "text", "general", "sonja"),
    ("The garden grows tomatoes in summer", "text", "general", "sonja"),
    ("The library opens at 10am on weekdays", "text", "general", "sonja"),
    ("The shop sells fresh bread", "voice", "general", "sonja"),
    ("Code the server in Python", "text", "coding", "codex"),
    ("Pin the dependency versions before release", "text", "coding", "codex"),
    ("URL: https://example.com/bread\nThe bakery uses stone-milled flour",
     "clipper", "general", "sonja"),
    ("Simmer the soup for forty minutes", "text", "cooking", "sonja"),
    ("Buy basil at the Saturday market", "voice", "general", "sonja"),
    ("Back up the vault every Sunday night", "text", "general", "sonja"),
]

# Seed verifications: facts NOT in the seed set, so nothing appears
# twice. Each must store cleanly (status "verified").
SEED_VERIFIES = (
    "The tour bus leaves at 8am sharp",
    "Water the tomatoes after sunset",
)


class StepMismatch(Exception):
    """A step returned a shape the demo script does not promise."""


def refuse_live_env():
    """True when the environment forbids a fake-mode demo run."""
    live = os.environ.get("HIVE_MIND_LIVE", "")
    if live not in ("", "0"):
        print(
            "Refusing to run: HIVE_MIND_LIVE is set in this shell, so "
            "the server would try live calls. Unset it and run again "
            "— the demo runner is fake mode only and never spends "
            "credits.",
            file=sys.stderr,
        )
        return True
    if os.environ.get("META_API_KEY", ""):
        print(
            "Refusing to run: META_API_KEY is present in this shell. "
            "Unset it and run again — the demo runner is fake mode "
            "only and never reads a key.",
            file=sys.stderr,
        )
        return True
    return False


class StdioClient:
    """One JSON-RPC conversation with the stdio MCP server."""

    def __init__(self, proc):
        self.proc = proc
        self.next_id = 1

    def _send(self, obj):
        self.proc.stdin.write(json.dumps(obj) + "\n")
        self.proc.stdin.flush()

    def _read(self):
        line = self.proc.stdout.readline()
        if not line:
            raise StepMismatch("server closed its output mid-demo")
        return json.loads(line)

    def initialize(self):
        request_id = self.next_id
        self.next_id += 1
        self._send({
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "hive-mind-demo-runner",
                               "version": "1.0"},
            },
        })
        reply = self._read()
        if reply.get("id") != request_id or "result" not in reply:
            raise StepMismatch("initialize did not return a result: %r" % (reply,))
        # Notification: no reply is ever sent for this one.
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def call(self, tool_name, arguments):
        request_id = self.next_id
        self.next_id += 1
        self._send({
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        })
        reply = self._read()
        if reply.get("id") != request_id:
            raise StepMismatch("reply id mismatch for %s: %r" % (tool_name, reply))
        if "error" in reply:
            raise StepMismatch("tool %s errored: %r" % (tool_name, reply["error"]))
        result = reply.get("result", {})
        content = result.get("content", [])
        if not content or content[0].get("type") != "text":
            raise StepMismatch("tool %s returned no text payload: %r" % (tool_name, reply))
        payload = json.loads(content[0]["text"])
        if result.get("isError"):
            raise StepMismatch("tool %s reported an error payload: %r" % (tool_name, payload))
        return payload


class Runner:
    def __init__(self, dwell_sec, wait_for_enter):
        self.dwell_sec = dwell_sec
        self.wait_for_enter = wait_for_enter
        self.step_no = 0

    def pause(self):
        if self.wait_for_enter:
            try:
                input("[demo] Press Enter for the next step… ")
            except EOFError:
                pass
        elif self.dwell_sec > 0:
            time.sleep(self.dwell_sec)

    def caption(self, text):
        self.step_no += 1
        print("\n[demo step %d] %s" % (self.step_no, text))
        sys.stdout.flush()

    def show(self, payload):
        print(json.dumps(payload, sort_keys=True))
        sys.stdout.flush()

    @staticmethod
    def expect(condition, what):
        if not condition:
            raise StepMismatch("expected %s" % what)


def run_demo(client, runner, vault_dir):
    # -- Setup: seed the throwaway store, exactly as the script. --
    runner.caption("Seeding demo memories in a throwaway store "
                   "(12 memories, 2 checked). The real vault is untouched.")
    for content, source_type, hint, client_id in SEEDS:
        payload = client.call("hivemind_capture_idea", {
            "content": content, "source_type": source_type,
            "domain_hint": hint, "client_id": client_id})
        Runner.expect(payload.get("status") == "ok",
                      "capture status ok, got %r" % (payload,))
    for fact in SEED_VERIFIES:
        payload = client.call("hivemind_crosshatch_verify", {
            "candidate_fact": fact, "domain_repo": "general",
            "source_citation": "demo seed", "supersede_id": ""})
        Runner.expect(payload.get("status") == "verified",
                      "seed verify status verified, got %r" % (payload,))
    runner.show({"seeded_memories": len(SEEDS), "seed_verified": len(SEED_VERIFIES)})
    runner.pause()

    # -- Beat 1: capture + Burn-After-Reading. --
    runner.caption(
        "Say it messy, with the slip in it: \"I just realised the shop "
        "website should open at 9am on Saturdays — oh, and my API key "
        "is sk-demo-trap-me… never mind, send that to the coding repo. "
        "Also tell Day the shop sells fresh bread.\"")
    runner.pause()
    payload = client.call("hivemind_capture_idea", {
        "content": BEAT1_CONTENT, "source_type": "voice",
        "domain_hint": "coding", "client_id": "sonja"})
    runner.show(payload)
    Runner.expect(payload.get("trapped_count") == 1,
                  "trapped_count 1 for the demo key slip, got %r" % (payload,))
    runner.caption("The key never reaches storage. The scrubber traps it "
                   "first, every time, before anything is written or sent. "
                   "One capture, never restated.")

    # -- Beat 2: Cross-Hatch + Caveman. --
    runner.caption("Ask in plain words, get back shorthand. Fewer tokens, "
                   "same fact — and the answer says which client produced it.")
    runner.pause()
    payload = client.call("hivemind_query_temporal", {
        "query": "shop opening hours", "temporal_tier": "recent_0_3m",
        "token_budget": 200, "format_mode": "caveman"})
    runner.show(payload)
    Runner.expect(payload.get("status") == "ok" and "meter" in payload,
                  "query status ok with a Token Ekonomi Meter, got %r" % (payload,))
    runner.pause()

    runner.caption("A contradiction never overwrites quietly. Watch the "
                   "refusal first — then the human yes.")
    runner.pause()
    payload = client.call("hivemind_crosshatch_verify", {
        "candidate_fact": "The shop opens at 10am on Saturdays",
        "domain_repo": "general", "source_citation": "demo runner",
        "supersede_id": ""})
    runner.show(payload)
    Runner.expect(payload.get("status") == "conflict"
                  and payload.get("conflicting_id"),
                  "conflict with a conflicting_id, got %r" % (payload,))
    conflicting_id = payload["conflicting_id"]
    runner.pause()
    payload = client.call("hivemind_crosshatch_verify", {
        "candidate_fact": "The shop opens at 10am on Saturdays",
        "domain_repo": "general", "source_citation": "demo runner",
        "supersede_id": conflicting_id})
    runner.show(payload)
    Runner.expect(payload.get("status") == "superseded" and payload.get("diff"),
                  "superseded with a Conflict Diff & Merge entry, got %r" % (payload,))
    runner.caption("It waits for a human yes, and the change is written down.")

    # -- Beat 4 (terminal half): micro-bot + snapshot backup. --
    runner.caption("A tiny helper bot, grown from the same memories. "
                   "It rehearses before it ever acts.")
    runner.pause()
    payload = client.call("hivemind_spawn_microbot", {
        "template_name": "digest", "mode_level": "simple",
        "allowance_limit": 0, "cooldown_sec": 30})
    # Print a summary, not the whole 8KB script: on camera the full
    # script text would be a wall of unreadable output.
    runner.show({key: payload.get(key) for key in
                 ("status", "template_name", "mode_level", "size_bytes",
                  "path", "sha256")})
    Runner.expect(payload.get("status") == "ok"
                  and 8192 <= payload.get("size_bytes", 0) <= 14336,
                  "micro-bot 8KB–14KB, got %r" % (payload,))
    script_path = payload.get("path", "")
    dry = subprocess.run(
        [sys.executable, script_path, "--dry-run", "--vault", vault_dir],
        capture_output=True, text=True, timeout=60)
    print("[demo dry-run] exit=%d" % dry.returncode)
    print(dry.stdout[:2000])
    if dry.stderr:
        print(dry.stderr[:500], file=sys.stderr)
    Runner.expect(dry.returncode == 0, "micro-bot --dry-run exit 0")
    runner.pause()

    runner.caption("No cloud configured, no problem — a local bundle, "
                   "hash-checked back. A failed upload is never reported "
                   "as backed up.")
    runner.pause()
    payload = client.call("hivemind_snapshot_backup", {
        "destination_target": "supabase", "schedule_interval": "now",
        "user_handshake_token": "yes"})
    runner.show(payload)
    Runner.expect(payload.get("status") == "local_only"
                  and payload.get("verified_callback") is True
                  and payload.get("backed_up") is False,
                  "local_only + verified callback + backed_up false, got %r"
                  % (payload,))
    print("\n[demo] Terminal half done. Fake mode only: no live calls, "
          "no keys, nothing left the machine.")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Hive-Mind demo autopilot, terminal half (fake mode only).")
    parser.add_argument("--fast", action="store_true",
                        help="1-second pauses instead of 6.")
    parser.add_argument("--step", action="store_true",
                        help="Wait for Enter before each step.")
    parser.add_argument("--keep", action="store_true",
                        help="Keep the temp store and print its path.")
    args = parser.parse_args(argv)

    if refuse_live_env():
        return 2

    dwell = FAST_DWELL_SEC if args.fast else DEFAULT_DWELL_SEC
    tmp_dir = tempfile.mkdtemp(prefix="hive-mind-demo-")
    print("[demo] Temp store: %s" % tmp_dir)
    child_env = dict(os.environ)
    child_env["HIVE_MIND_DB_PATH"] = os.path.join(tmp_dir, "demo.db")
    child_env["HIVE_MIND_VAULT_DIR"] = os.path.join(tmp_dir, "vault")
    # Defence in depth: the child can never go live, even if the
    # refusal above is ever bypassed by a caller.
    child_env.pop("HIVE_MIND_LIVE", None)
    child_env.pop("META_API_KEY", None)

    proc = subprocess.Popen(
        [sys.executable, "-m", "app.mcp_server"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, cwd=REPO_ROOT, env=child_env)
    try:
        client = StdioClient(proc)
        client.initialize()
        run_demo(client, Runner(dwell, args.step),
                 child_env["HIVE_MIND_VAULT_DIR"])
    except StepMismatch as exc:
        print("[demo] UNEXPECTED: %s" % exc, file=sys.stderr)
        return 3
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)
        if proc.stderr:
            err = proc.stderr.read()
            if err.strip():
                print("[demo server stderr]\n%s" % err[:1000], file=sys.stderr)
        if args.keep:
            print("[demo] Temp store kept at: %s" % tmp_dir)
        else:
            shutil.rmtree(tmp_dir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
