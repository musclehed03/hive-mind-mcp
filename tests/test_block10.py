"""Block 10 gate tests: living nebula growth stages.

The stage logic in gui/stage.js is executed for real with Node
(available in this VM) — thresholds, verified counting, and the
stage shape are asserted on live JS output, not on string matches.
The HTML wiring is asserted statically.
"""

import json
import os
import subprocess

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_NODE_HARNESS = """
const fs = require("fs");
const src = fs.readFileSync(%s, "utf8");
global.window = {};
eval(src);
const S = global.window.HIVEMIND_STAGE;
const assert = require("assert");
assert(S, "HIVEMIND_STAGE missing");
const names = S.STAGES.map(s => s.name);
assert.deepStrictEqual(names, ["Nebula", "Protostar", "Star", "Radiant Sun"]);
assert.deepStrictEqual(S.STAGES.map(s => s.minCount), [0, 10, 30, 75]);
assert.strictEqual(S.stageFor(0, 0).name, "Nebula");
assert.strictEqual(S.stageFor(9, 0).name, "Nebula");
assert.strictEqual(S.stageFor(10, 0).name, "Protostar");
assert.strictEqual(S.stageFor(29, 29).name, "Protostar");
assert.strictEqual(S.stageFor(30, 0).name, "Star");
assert.strictEqual(S.stageFor(74, 0).name, "Star");
assert.strictEqual(S.stageFor(75, 0).name, "Radiant Sun");
assert.strictEqual(S.stageFor(1000, 500).name, "Radiant Sun");
assert.strictEqual(S.stageFor(-3, -1).name, "Nebula");
assert.strictEqual(S.stageFor(-3, -1).count, 0);
assert.strictEqual(S.stageFor(20, 99).verifiedCount, 20, "verified capped at count");
assert.strictEqual(S.stageFor(20, 5).verifiedFraction, 0.25);
assert.strictEqual(S.stageFor(75, 0).nextMin, null);
assert.strictEqual(S.stageFor(9, 0).nextName, "Protostar");
assert.strictEqual(S.stageFor(9, 0).nextMin, 10);
assert.ok(S.stageFor(0, 0).description.length > 0);
assert.ok(S.STAGES.every(s => s.dust > 0 && s.scale >= 1.0));
assert.ok(S.STAGES[3].dust > S.STAGES[0].dust, "dust grows with stage");
const nodes = [
  {provenance: {verified_by: "fake-meta verify + check"}},
  {provenance: {verified_by: ""}},
  {provenance: {}},
  {provenance: null},
  {},
  {provenance: {verified_by: "live Meta verify + check"}},
];
assert.strictEqual(S.countVerified(nodes), 2);
assert.strictEqual(S.isVerified(nodes[0]), true);
assert.strictEqual(S.isVerified(nodes[1]), false);
console.log(JSON.stringify({ok: true}));
"""


def _read_gui(name):
    with open(os.path.join(REPO, "gui", name), encoding="utf-8") as f:
        return f.read()


def test_stage_logic_executes_in_node():
    stage_path = os.path.join(REPO, "gui", "stage.js")
    script = _NODE_HARNESS % json.dumps(stage_path)
    result = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.strip()) == {"ok": True}


def test_growth_stage_element_exists_with_tooltip():
    html = _read_gui("index.html")
    assert 'id="growth-stage"' in html
    assert 'aria-live="polite"' in html
    assert 'id="growth-stage" aria-live="polite" data-tooltip="' in html
    assert "stage.js" in html
    assert '<script src="stage.js"></script>' in html
    # stage.js loads before app.js so HIVEMIND_STAGE exists at render.
    assert html.index("stage.js") < html.index("app.js")


def test_app_js_uses_stage_api_and_updates_label():
    js = _read_gui("app.js")
    assert "HIVEMIND_STAGE" in js
    assert "growth-stage" in js
    assert "stageFor" in js
    assert "countVerified" in js
    assert "isVerified" in js


def test_stage_js_has_no_timers_or_network():
    js = _read_gui("stage.js")
    assert "setInterval" not in js
    assert "setTimeout" not in js
    assert "fetch" not in js
    assert "Math.random" not in js, "dust positions must be deterministic"


def test_no_native_title_attributes_added():
    html = _read_gui("index.html")
    assert 'title="' not in html
