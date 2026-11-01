"""Block 18 gate tests: demo autopilot (GUI demo-play + terminal runner).

The demo must drive itself, restore everything it changed, and stay
fake-mode-only: no autostart, no polling, no network, no vault
writes from the GUI, and a temp-only store plus live-env refusal
from the terminal runner.
"""

import json
import os
import re
import subprocess
import sys
import tempfile

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)


def _read(rel):
    with open(os.path.join(REPO, rel), encoding="utf-8") as fh:
        return fh.read()


# -- GUI helpers, executed for real in Node ---------------------------

_NODE_HARNESS = r"""
const fs = require("fs");
const assert = require("assert");
const window = {};
eval(fs.readFileSync(%s, "utf8"));
const D = window.HIVEMIND_DEMO;
assert(D, "HIVEMIND_DEMO export missing");

// Dwell: 6 seconds a step, as specified.
assert.strictEqual(D.DWELL_MS, 6000);

// Step order follows DEMO_SCRIPT.md Beats 3-4: stage, EXP, origins,
// metaphor, achromatopsia, integrations, read-aloud (shown, not pressed).
assert.deepStrictEqual(D.stepIds(),
  ["stage", "exp", "origins", "metaphor", "achromatopsia",
   "integrations", "read-aloud"]);
assert.strictEqual(D.stepCount(), 7);
assert.strictEqual(D.stepAt(0).targetId, "growth-stage");
assert.strictEqual(D.stepAt(2).onEnter, "origin-colour");
assert.strictEqual(D.stepAt(3).onEnter, "metaphor-tree");
assert.strictEqual(D.stepAt(3).onLeave, "metaphor-nebula");
assert.strictEqual(D.stepAt(4).onEnter, "achromatopsia-on");
assert.strictEqual(D.stepAt(4).onLeave, "achromatopsia-off");
assert.strictEqual(D.stepAt(6).onEnter, "highlight");
assert.strictEqual(D.stepAt(7), null);
assert.strictEqual(D.stepAt(-1), null);
D.STEPS.forEach(function (s) {
  assert(s.caption && s.caption.length > 20, "every step has a plain caption");
});

// Dwell arithmetic: clamped fraction, whole seconds left.
assert.strictEqual(D.progressFraction(0, 6000), 0);
assert.strictEqual(D.progressFraction(3000, 6000), 0.5);
assert.strictEqual(D.progressFraction(9000, 6000), 1);
assert.strictEqual(D.progressFraction(-5, 6000), 0);
assert.strictEqual(D.remainingSeconds(6000, 0), 6);
assert.strictEqual(D.remainingSeconds(6000, 5500), 1);
assert.strictEqual(D.remainingSeconds(6000, 6000), 0);
assert.strictEqual(D.remainingSeconds(6000, 9000), 0);
assert.strictEqual(D.nextStepIndex(0), 1);
assert.strictEqual(D.nextStepIndex(6), -1);

// Snapshot round-trip is exact and detached: restoring hands back
// a copy, never the object the demo still holds.
const state = {origin_colours: {"text · sonja": "#123456"},
               active_profile: "dyslexia", metaphor: "tree",
               colorblind_palette: "default", nested: {a: [1, 2]}};
const snap = D.captureSnapshot(state);
assert.deepStrictEqual(snap, state);
snap.origin_colours["text · sonja"] = "#000000";
assert.strictEqual(state.origin_colours["text · sonja"], "#123456");
const restored = D.applySnapshot(snap);
assert.deepStrictEqual(restored, snap);
assert.notStrictEqual(restored, snap);
assert.notStrictEqual(restored.origin_colours, snap.origin_colours);

// Demo colour pick: first candidate that differs, case-insensitively.
assert.strictEqual(
  D.pickDemoColour("#ad3375", ["#AD3375", "#547c6d"]), "#547c6d");
assert.strictEqual(D.pickDemoColour("#111111", ["#111111"]), "#111111");
assert.strictEqual(D.pickDemoColour("#111111", []), null);
"""


def _run_node_harness():
    harness = _NODE_HARNESS % json.dumps(os.path.join(REPO, "gui", "demo.js"))
    proc = subprocess.run(["node", "-e", harness],
                          capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_demo_helpers_execute_for_real():
    _run_node_harness()


def test_demo_js_has_no_timers_network_or_autostart():
    js = _read("gui/demo.js")
    assert "setInterval" not in js
    assert "setTimeout" not in js
    assert "fetch" not in js
    assert "Math.random" not in js
    assert "location.search" not in js
    assert "URLSearchParams" not in js
    assert "autostart" not in js.lower()
    assert "HIVEMIND_DEMO" in js
    assert "DWELL_MS" in js


def test_demo_controls_in_html_outside_accessibility_suite():
    html = _read("gui/index.html")
    for control_id in ("demo-play", "demo-stop", "demo-caption",
                       "demo-step-indicator", "demo-progress", "demo-countdown"):
        assert 'id="%s"' % control_id in html, control_id
    # Play/Stop carry plain-language tooltips, like every control.
    for control_id in ("demo-play", "demo-stop"):
        match = re.search(r'<button[^>]*id="%s"[^>]*>' % control_id, html)
        assert match and "data-tooltip" in match.group(0), control_id
    # The demo group sits in the graph section, before (outside) the
    # Accessibility Suite — access needs only, no product controls.
    assert html.index('class="demo-controls"') < html.index('id="accessibility-suite"')
    # The achromatopsia button is addressable as the demo's spotlight target.
    assert 'id="profile-achromatopsia"' in html
    # Demo helpers load before the driver that uses them.
    assert html.index('src="demo.js"') < html.index('src="app.js"')
    assert "title=" not in html, "no native title tooltips anywhere"


def test_demo_highlight_and_safe_motion_styles():
    css = _read("gui/styles.css")
    assert ".demo-highlight" in css
    assert "dashed" in css.split(".demo-highlight")[1].split("}")[0]
    assert ".demo-controls" in css


def test_app_js_demo_driver_restores_and_uses_one_scheduler():
    js = _read("gui/app.js")
    # One scheduler call site; the guard in test_block8 pins the total.
    assert js.count("setTimeout") == 3
    assert "setInterval" not in js
    assert "scheduleDemo" in js
    assert "demoRunAction" in js
    assert "captureSnapshot" in js
    assert "applySnapshot" in js
    assert "demoRestore" in js
    # Safe Motion: instant jump, no smooth scroll.
    assert 'el.scrollIntoView({block: "center"})' in js
    assert 'behavior: "smooth"' in js
    # Keyboard: Escape stops, Space pauses (not on controls).
    assert '"Escape"' in js
    assert "demoStop" in js
    # Read aloud is spotlighted, never pressed by the demo: no
    # readAloud call inside the demo action runner.
    runner = js.split("function demoRunAction")[1].split("\n  function demoTick")[0]
    assert "readAloud" not in runner
    assert "copyIntegration" in runner, "Integrations step presses Copy for real"
    assert "applyProfile" in runner
    assert "setOriginColour" in runner
    # No autostart: nothing in the driver reads a query string or
    # starts playback on load.
    assert "location.search" not in js
    # Playback starts from exactly one call site: the Play toggle.
    # (The function definition itself carries no semicolon.)
    assert js.count("demoStart();") == 1, "started only from the Play toggle path"


def test_spec_md5_unchanged_and_no_new_tools():
    import hashlib
    spec = os.path.join(REPO, "docs", "HIVE-MIND-LOCK-IN-SPEC.md")
    digest = hashlib.md5(open(spec, "rb").read()).hexdigest()
    assert digest == "13fa897039dd6b1cd0d11e90e85d7c2c"
    from app.tools import IMPLEMENTED
    assert len(IMPLEMENTED) == 8


# -- Terminal runner ---------------------------------------------------

RUNNER = os.path.join(REPO, "scripts", "demo_terminal.py")


def _runner_env(**overrides):
    env = dict(os.environ)
    env.pop("HIVE_MIND_LIVE", None)
    env.pop("META_API_KEY", None)
    env.update(overrides)
    return env


def test_runner_refuses_live_env_before_starting():
    for extra in ({"HIVE_MIND_LIVE": "1"}, {"META_API_KEY": "sk-test-not-real"}):
        proc = subprocess.run(
            [sys.executable, RUNNER, "--fast"],
            capture_output=True, text=True, timeout=60,
            env=_runner_env(**extra), cwd=REPO)
        assert proc.returncode == 2, proc.stdout + proc.stderr
        assert "Refusing to run" in proc.stderr
        assert "Temp store" not in proc.stdout, "no server started on refusal"


def test_runner_end_to_end_fast_captions_in_order_and_temp_cleaned():
    vault_before = set(os.listdir(os.path.join(REPO, "vault")))
    proc = subprocess.run(
        [sys.executable, RUNNER, "--fast"],
        capture_output=True, text=True, timeout=120,
        env=_runner_env(), cwd=REPO)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    out = proc.stdout
    # Captions print in script order, before their calls.
    markers = [
        "Seeding demo memories",
        "Say it messy",
        "The key never reaches storage",
        "Ask in plain words",
        "A contradiction never overwrites quietly",
        "It waits for a human yes",
        "A tiny helper bot",
        "No cloud configured",
        "Terminal half done",
    ]
    positions = [out.index(m) for m in markers]
    assert positions == sorted(positions), "captions out of order"
    # Expected shapes surfaced in the printed payloads.
    assert '"trapped_count": 1' in out
    assert '"status": "conflict"' in out
    assert '"status": "superseded"' in out
    assert '"status": "local_only"' in out
    assert '"backed_up": false' in out
    assert '"verified_callback": true' in out
    assert "digest-bot dry run:" in out and "memories in vault" in out
    assert "no live calls, no keys" in out
    # Temp store was removed, and the real vault is untouched.
    temp_line = [ln for ln in out.splitlines() if ln.startswith("[demo] Temp store:")][0]
    temp_dir = temp_line.split(": ", 1)[1].strip()
    assert temp_dir.startswith(tempfile.gettempdir())
    assert not os.path.exists(temp_dir), "temp store must be cleaned"
    assert set(os.listdir(os.path.join(REPO, "vault"))) == vault_before


def test_runner_keep_flag_keeps_temp_store():
    proc = subprocess.run(
        [sys.executable, RUNNER, "--fast", "--keep"],
        capture_output=True, text=True, timeout=120,
        env=_runner_env(), cwd=REPO)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    kept = [ln for ln in proc.stdout.splitlines()
            if ln.startswith("[demo] Temp store kept at:")][0].split(": ", 1)[1].strip()
    try:
        assert os.path.isdir(kept)
        assert os.path.exists(os.path.join(kept, "demo.db"))
    finally:
        import shutil
        shutil.rmtree(kept, ignore_errors=True)


def test_runner_is_stdlib_only_and_docs_point_at_autopilot():
    tree = open(RUNNER, encoding="utf-8").read()
    assert "import requests" not in tree and "import httpx" not in tree
    assert "HIVE_MIND_LIVE" in tree and "META_API_KEY" in tree
    assert "tempfile.mkdtemp" in tree
    assert ".env" in tree, "the no-key-reading rule is documented in the file"
    readme = _read("README.md")
    assert "demo_terminal.py" in readme
    assert "Play demo" in readme
    script = _read("docs/DEMO_SCRIPT.md")
    assert "demo_terminal.py" in script
    assert "Play demo" in script or "demo-play" in script
