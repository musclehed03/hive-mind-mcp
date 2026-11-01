"""Block 14 gate tests: meaningful keyword labels, canvas-only
duplicate grouping, label stagger, and the header/footer
centring fix (Sonja's live GUI re-check, Nov 1).

Sonja's vault holds 3 facts stored twice each; the old
first-three-words labels gave two identical "The library opens"
labels that collided. Keywords must now be meaningful content
words, duplicates must draw as one node labelled "keyword ×N",
and the header/footer must share <main>'s centred column.

The stage.js helpers are executed for real with Node; the
app.js wiring and the CSS centring are asserted statically.
"""

import hashlib
import json
import os
import re
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
for (const fn of ["keywordLabel", "contentWords", "normalizeFactKey",
                  "groupGraphNodes", "mapGroupEdges", "placeLabel",
                  "layoutNodes", "labelGeometry", "fitLabel"]) {
  assert.strictEqual(typeof G[fn], "function", fn);
}

// --- Meaningful keywords (not the first three words) ---
// Sonja's three example facts map to three DISTINCT keywords.
assert.strictEqual(
  G.keywordLabel("The library opens at 10am on weekdays"), "Library opens");
assert.strictEqual(
  G.keywordLabel("The garden grows tomatoes in summer"), "Garden grows");
assert.strictEqual(
  G.keywordLabel("The shop opens at 9am on Saturdays"), "Shop opens");
// Verbs are meaningful and kept; filler words are stripped.
assert.deepStrictEqual(G.contentWords("The library opens"), ["library", "opens"]);
assert.deepStrictEqual(G.contentWords("The garden grows"), ["garden", "grows"]);
assert.strictEqual(G.keywordLabel("The door opens"), "Door opens");
assert.strictEqual(G.keywordLabel("The cat is on the mat"), "Cat mat");
assert.strictEqual(G.keywordLabel("Meeting at 9am in room 4"), "Meeting 9am");
assert.strictEqual(G.keywordLabel("Hello, world!"), "Hello world");
assert.strictEqual(G.keywordLabel("single"), "Single");
assert.strictEqual(G.keywordLabel(""), "");
assert.strictEqual(G.keywordLabel("   "), "");
assert.strictEqual(G.keywordLabel("the at on in of"), "", "all filler -> no label");
assert.strictEqual(G.keywordLabel("  spaced   out   words  here "), "Spaced out");
// Cap: 20 chars total including the ellipsis.
const long = G.keywordLabel("supercalifragilisticexpialidocious words here");
assert.ok(long.length <= 20, long);
assert.ok(long.endsWith("\\u2026"), long);
assert.strictEqual(G.KEYWORD_MAX_CHARS, 20);

// --- Grouping key: case / whitespace / edge punctuation don't split a fact ---
assert.strictEqual(
  G.normalizeFactKey("  The Library   Opens at 10am "),
  G.normalizeFactKey("the library opens at 10am"));
assert.notStrictEqual(
  G.normalizeFactKey("The library opens at 10am on weekdays"),
  G.normalizeFactKey("The shop opens at 9am on Saturdays"));

// --- Duplicate grouping (canvas only) ---
const nodes = [
  {id: "a1", text: "The library opens at 10am on weekdays", shape: "circle", provenance: {}},
  {id: "a2", text: "The library opens at 10am on weekdays", shape: "circle", provenance: {}},
  {id: "b1", text: "The garden grows tomatoes in summer", shape: "circle", provenance: {}},
  {id: "b2", text: "the  garden grows tomatoes in summer ", shape: "circle", provenance: {verified_by: "crosshatch"}},
  {id: "c1", text: "The shop opens at 9am on Saturdays", shape: "circle", provenance: {}},
  {id: "c2", text: "The shop opens at 9am on Saturdays", shape: "circle", provenance: {}},
];
const groups = G.groupGraphNodes(nodes);
assert.strictEqual(groups.length, 3, "six memories, three facts -> three nodes");
assert.deepStrictEqual(groups.map(g => g.label),
  ["Library opens \\u00d72", "Garden grows \\u00d72", "Shop opens \\u00d72"]);
assert.deepStrictEqual(groups.map(g => g.count), [2, 2, 2]);
assert.strictEqual(groups.reduce((n, g) => n + g.members.length, 0), 6,
  "grouping never drops a memory");
assert.strictEqual(groups[0].representative.id, "a1", "first member represents");
assert.strictEqual(groups[0].verified, false);
assert.strictEqual(groups[1].verified, true, "checked when ANY member is checked");
assert.strictEqual(groups[2].verified, false);
assert.strictEqual(nodes.length, 6, "input array untouched");
assert.ok(!("members" in nodes[0]), "input nodes not mutated");
// Singletons carry no count suffix.
const solo = G.groupGraphNodes([{id: "s", text: "Only memory here", shape: "square", provenance: {}}]);
assert.strictEqual(solo.length, 1);
assert.strictEqual(solo[0].label, "Only memory");
assert.strictEqual(solo[0].count, 1);
// Empty input groups to nothing.
assert.deepStrictEqual(G.groupGraphNodes([]), []);

// --- Edge remapping onto groups ---
const edges = [
  {from: "a1", to: "a2", kind: "dup", line_style: "solid"},
  {from: "a1", to: "b1", kind: "x", line_style: "solid"},
  {from: "a2", to: "b2", kind: "x", line_style: "dashed"},
  {from: "b1", to: "c1", kind: "y", line_style: "dotted"},
  {from: "a1", to: "ghost", kind: "z", line_style: "solid"},
];
const mapped = G.mapGroupEdges(edges, groups);
assert.strictEqual(mapped.length, 2, "in-group edge dropped, duplicate pair deduped, ghost dropped");
assert.deepStrictEqual([mapped[0].from, mapped[0].to], ["a1", "b1"]);
assert.strictEqual(mapped[0].line_style, "solid", "first line style kept");
assert.deepStrictEqual([mapped[1].from, mapped[1].to], ["b1", "c1"]);
assert.strictEqual(edges.length, 5, "input edges untouched");

// --- placeLabel: stagger, circle clearance, edge fit ---
const measure = (t) => t.length * 7;
const W = 1036, H = 420, nodeSize = 21;
function geoFor(x, y) { return G.labelGeometry({x: x, y: y}, W, nodeSize); }
// Two labels that would sit on top of each other: the second staggers 16px.
const placed = [];
const g1 = geoFor(800, 210);
const p1 = G.placeLabel(g1, "Library opens \\u00d72", 210, measure, placed, W, H);
assert.ok(p1, "first label places");
placed.push(p1.box);
const g2 = geoFor(810, 210);
const p2 = G.placeLabel(g2, "Garden grows \\u00d72", 210, measure, placed, W, H);
assert.ok(p2, "second label places");
assert.strictEqual(p2.y, p1.y + 16, "stagger is one 16px step away from centre");
assert.ok(p2.box.y0 >= p1.box.y1 + 2 || p2.box.y1 <= p1.box.y0 - 2, "boxes no longer overlap");
// Circle clearance on both sides: the box never reaches the node circle.
assert.ok(p1.box.x1 <= 800 - nodeSize, "right label ends clear of the circle");
const gL = geoFor(200, 210);
const pL = G.placeLabel(gL, "Shop opens", 210, measure, [], W, H);
assert.ok(pL.box.x0 >= 200 + nodeSize, "left label starts clear of the circle");
// Stagger direction follows the half: above centre staggers up.
const upPlaced = [];
const up1 = G.placeLabel(geoFor(800, 100), "Library opens", 100, measure, upPlaced, W, H);
upPlaced.push(up1.box);
const up2 = G.placeLabel(geoFor(810, 100), "Garden grows", 100, measure, upPlaced, W, H);
assert.strictEqual(up2.y, up1.y - 16, "above-centre labels stagger upward");
// No room at all -> null, never a clipped label.
assert.strictEqual(
  G.placeLabel({x: 10, textAlign: "right"}, "Library opens", 210, measure, [], W, H),
  null, "room under 24px places nothing");
// Long keyword truncates to the room with an ellipsis.
const tight = G.placeLabel({x: 120, textAlign: "right"}, "Supercalifragilistic keyword here", 210, measure, [], W, H);
assert.ok(tight && tight.text.endsWith("\\u2026"), tight && tight.text);
assert.ok(measure(tight.text) <= 112, "fitted text fits the room");
console.log(JSON.stringify({ok: true}));
"""


def _read_gui(name):
    with open(os.path.join(REPO, "gui", name), encoding="utf-8") as f:
        return f.read()


def test_keyword_grouping_and_placement_execute_in_node():
    stage_path = os.path.join(REPO, "gui", "stage.js")
    script = _NODE_HARNESS % json.dumps(stage_path)
    result = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.strip()) == {"ok": True}


def test_app_js_uses_grouping_and_place_label():
    js = _read_gui("app.js")
    assert "groupGraphNodes" in js
    assert "mapGroupEdges" in js
    assert "placeLabel" in js
    assert "placedLabels" in js
    assert "displayNodes" in js
    assert "displayEdges" in js
    assert "label.slice(0, 28)" not in js, "sentence labels are gone"
    assert "keywordLabel" in js, "fallback keyword path kept"
    # Stage counts, EXP, status, and the text list use TOTAL memories.
    assert "stageFor(graphData.nodes.length" in js
    assert "countVerified(graphData.nodes)" in js
    assert "graphData.nodes.forEach" in js
    assert 'document.createElement("li")' in js
    # Chunked rendering and sizing kept.
    assert "requestAnimationFrame(drawChunk)" in js
    assert "fitCanvas" in js
    assert "setInterval" not in js


def test_stage_js_has_no_timers_network_or_fixed_geometry():
    js = _read_gui("stage.js")
    assert "setInterval" not in js
    assert "setTimeout" not in js
    assert "fetch" not in js
    assert "Math.random" not in js
    assert "600" not in js
    assert "320" not in js
    assert "STOP_WORDS" in js


def test_header_footer_share_main_centring():
    css = _read_gui("styles.css")
    # The shared rule centres all three on the same 1080px column.
    assert re.search(
        r"header,\s*main,\s*footer\s*\{[^}]*max-width:\s*1080px[^}]*"
        r"margin-left:\s*auto[^}]*margin-right:\s*auto", css), "shared centred column"
    # Header/footer must NOT reintroduce fixed side margins: the old
    # shorthand overrode the auto margins and shifted the cards
    # against <main> on wide viewports.
    assert "margin: 20px 12px 4px" not in css
    assert "margin: 4px 12px 20px" not in css
    assert re.search(r"header\s*\{[^}]*margin:\s*20px auto 4px", css)
    assert re.search(r"footer\s*\{[^}]*margin:\s*4px auto 20px", css)
    assert re.search(r"header\s*\{[^}]*width:\s*calc\(100% - 24px\)", css)
    assert re.search(r"footer\s*\{[^}]*width:\s*calc\(100% - 24px\)", css)
    # No other horizontal-overflow sources: no negative margins,
    # no viewport-width boxes, canvas/svg capped at container width.
    assert "margin: -" not in css
    assert "100vw" not in css
    assert "canvas, svg.graph { width: 100%" in css
    assert "overflow: hidden" in css, ".graph-wrap clips the canvas"


def test_lock_in_spec_unchanged():
    digest = hashlib.md5(
        open(os.path.join(REPO, "docs", "HIVE-MIND-LOCK-IN-SPEC.md"), "rb").read()
    ).hexdigest()
    assert digest == "13fa897039dd6b1cd0d11e90e85d7c2c"
