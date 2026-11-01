"""Block 13 gate tests: canvas sized to its displayed size, keyword
labels that never overlap or clip (Sonja's live GUI check, Nov 1).

The label/layout helpers in gui/stage.js are executed for real with
Node — thresholds, keyword truncation, side-aware geometry, and
fit-to-width are asserted on live JS output, not on string matches.
The app.js wiring (displayed-size canvas, resize re-render, no
fixed 600x320 geometry) is asserted statically.
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
const G = global.window.HIVEMIND_GRAPH;
const assert = require("assert");
assert(G, "HIVEMIND_GRAPH missing");
assert.strictEqual(typeof G.keywordLabel, "function");
assert.strictEqual(typeof G.layoutNodes, "function");
assert.strictEqual(typeof G.dustPoint, "function");
assert.strictEqual(typeof G.labelSide, "function");
assert.strictEqual(typeof G.labelGeometry, "function");
assert.strictEqual(typeof G.fitLabel, "function");
assert.strictEqual(G.KEYWORD_MAX_CHARS, 20);
assert.strictEqual(G.LABEL_GAP_PX, 18);

// Keywords: first three words only.
assert.strictEqual(G.keywordLabel("Shop opens at 9am on Saturdays"), "Shop opens at");
assert.strictEqual(G.keywordLabel("The library opens at 10am on weekdays"), "The library opens");
assert.strictEqual(G.keywordLabel("The garden grows tomatoes in summer"), "The garden grows");
assert.strictEqual(G.keywordLabel("one two three"), "one two three");
assert.strictEqual(G.keywordLabel("single"), "single");
assert.strictEqual(G.keywordLabel(""), "");
assert.strictEqual(G.keywordLabel("   "), "");
assert.strictEqual(G.keywordLabel("  spaced   out   words  here "), "spaced out words");
// Long words: capped at 20 chars total, with an ellipsis.
const long = G.keywordLabel("supercalifragilisticexpialidocious words here");
assert.ok(long.length <= 20, long);
assert.ok(long.endsWith("\\u2026"), long);
assert.strictEqual(G.keywordLabel("abcdefghijklmnopqrstuv wxyz"), "abcdefghijklmnopqrs\\u2026");
// Punctuation/numbers pass through untouched.
assert.strictEqual(G.keywordLabel("Shop opens at 9am"), "Shop opens at");

// Layout: centre and radius derive from the passed width/height.
const pos = G.layoutNodes(
  [{id: "a"}, {id: "b"}, {id: "c"}, {id: "d"}], 1036, 420);
assert.deepStrictEqual(
  {x: Math.round(pos.a.x), y: Math.round(pos.a.y)}, {x: 672, y: 210},
  "first node sits at centre + radius on a wide canvas");
assert.strictEqual(Math.round(pos.c.x), 364, "opposite node mirrors: centre 518 minus radius 154");
assert.strictEqual(Math.round(518 - pos.c.x), 154, "radius = min/2 - 56 on 1036x420");
const small = G.layoutNodes([{id: "a"}], 160, 160);
assert.strictEqual(Math.round(small.a.x), 120, "radius floors at 40 on a small canvas: centre 80 + 40");
assert.strictEqual(Math.round(small.a.y), 80);
const tall = G.layoutNodes([{id: "a"}, {id: "b"}], 300, 800);
assert.ok(Math.abs(tall.a.x - 244) < 1, "radius follows the smaller dimension");
// Every node stays inside the canvas.
for (const [w, h] of [[1036, 420], [600, 320], [320, 340], [1920, 1080]]) {
  const p = G.layoutNodes([{id: "a"}, {id: "b"}, {id: "c"}], w, h);
  for (const k of Object.keys(p)) {
    assert.ok(p[k].x >= 0 && p[k].x <= w, [w, h, k, p[k]]);
    assert.ok(p[k].y >= 0 && p[k].y <= h, [w, h, k, p[k]]);
  }
}

// Dust: deterministic, inside the real width/height, never 600/320.
for (const [w, h] of [[1036, 420], [800, 340], [375, 500]]) {
  for (let d = 0; d < 120; d++) {
    const pt = G.dustPoint(d, w, h);
    assert.ok(pt.x >= 0 && pt.x < w, [w, h, d, pt]);
    assert.ok(pt.y >= 0 && pt.y < h, [w, h, d, pt]);
    assert.deepStrictEqual(pt, G.dustPoint(d, w, h), "dust is deterministic");
  }
}

// Side-aware geometry: label anchor is 18px clear of the node circle.
const nodeSize = 21;
const rightGeo = G.labelGeometry({x: 800, y: 210}, 1036, nodeSize);
assert.strictEqual(rightGeo.textAlign, "right");
assert.strictEqual(rightGeo.x, 800 - nodeSize - 18);
const leftGeo = G.labelGeometry({x: 200, y: 210}, 1036, nodeSize);
assert.strictEqual(leftGeo.textAlign, "left");
assert.strictEqual(leftGeo.x, 200 + nodeSize + 18);
assert.strictEqual(G.labelSide({x: 518, y: 0}, 1036), "right", "centre line belongs to the right half");
assert.strictEqual(G.labelSide({x: 517, y: 0}, 1036), "left");
// The anchor never overlaps the node circle on either side.
assert.ok(rightGeo.x <= 800 - nodeSize, "right label ends clear of the circle");
assert.ok(leftGeo.x >= 200 + nodeSize, "left label starts clear of the circle");

// fitLabel with a stub measure (7px per character).
const measure = (t) => t.length * 7;
assert.strictEqual(G.fitLabel("short", 100, measure), "short");
assert.strictEqual(G.fitLabel("12345678901234567890", 140, measure), "12345678901234567890", "20 chars fit exactly in 140px");
const fitted = G.fitLabel("a fairly long keyword label", 70, measure);
assert.ok(fitted.endsWith("\\u2026"), fitted);
assert.ok(measure(fitted) <= 70, fitted);
assert.strictEqual(G.fitLabel("anything", 0, measure), "");
assert.strictEqual(G.fitLabel("anything", 6, measure), "", "even an ellipsis does not fit");
assert.strictEqual(G.fitLabel("", 100, measure), "");
console.log(JSON.stringify({ok: true}));
"""


def _read_gui(name):
    with open(os.path.join(REPO, "gui", name), encoding="utf-8") as f:
        return f.read()


def test_label_helpers_execute_in_node():
    stage_path = os.path.join(REPO, "gui", "stage.js")
    script = _NODE_HARNESS % json.dumps(stage_path)
    result = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.strip()) == {"ok": True}


def test_app_js_sizes_canvas_to_displayed_size():
    js = _read_gui("app.js")
    assert "devicePixelRatio" in js
    assert "setTransform" in js
    assert "getBoundingClientRect" in js or "clientWidth" in js
    assert "fitCanvas" in js
    assert "HIVEMIND_GRAPH" in js
    assert "keywordLabel" in js
    assert "labelGeometry" in js
    assert "fitLabel" in js
    # Resize re-renders; no polling.
    assert "addEventListener(\"resize\"" in js
    assert "renderGraph()" in js
    assert "setInterval" not in js


def test_no_fixed_canvas_geometry_remains():
    js = _read_gui("app.js")
    assert "canvas.width = 600" not in js
    assert "canvas.height = 320" not in js
    assert "% 600" not in js
    assert "% 320" not in js
    assert "label.slice(0, 28)" not in js, "sentence labels are gone; keywords only"
    stage = _read_gui("stage.js")
    assert "% 600" not in stage
    assert "% 320" not in stage
    assert "600" not in stage, "no fixed 600 in stage.js"
    assert "320" not in stage, "no fixed 320 in stage.js"


def test_stage_js_has_no_timers_or_network():
    js = _read_gui("stage.js")
    assert "setInterval" not in js
    assert "setTimeout" not in js
    assert "fetch" not in js
    assert "Math.random" not in js, "dust positions must stay deterministic"


def test_chunked_rendering_and_stage_wiring_kept():
    js = _read_gui("app.js")
    assert "requestAnimationFrame(drawChunk)" in js, "chunked rendering kept"
    assert "i + 50" in js, "50 nodes per frame kept"
    assert "HIVEMIND_STAGE" in js
    assert "growth-stage" in js
    assert "12px sans-serif" in js, "canvas font size unchanged"
