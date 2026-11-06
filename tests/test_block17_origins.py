"""Block 17 gate tests: origin-denoting colours + legend.

Sonja's question, answered yes: the map must show WHICH model,
client, or coder made each memory, with colours the USER assigns.
Origin labels come only from recorded values (never invented);
MCP `initialize` clientInfo is recorded additively in capture
provenance; colours live in Regular Settings (never the
Accessibility Suite); and colour is NEVER the only carrier —
each origin also gets a ring pattern plus a text legend, so
achromatopsia mode keeps the full meaning.

The stage.js helpers are executed for real with Node; the
app.js wiring, HTML, and CSS are asserted statically.
"""

import hashlib
import json
import os
import re
import subprocess

import pytest

from app.capture import capture_idea
from app.crosshatch import crosshatch_verify
from app.dispatch import dispatch_tool
import app.dispatch as dispatch_mod
from app.gui_export import export_data
from app.mcp_server import handle_request
from app.origin import origin_label
from app.store import Store

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def store(tmp_path):
    s = Store(db_path=str(tmp_path / "v.db"), vault_dir=str(tmp_path / "vault"))
    yield s
    s.close()


@pytest.fixture
def routed_store(store):
    """Route dispatch's process-wide store at the temp store, so
    handle_request tools/call sequences write where we can read."""
    old = dispatch_mod._STORE
    dispatch_mod._STORE = store
    yield store
    dispatch_mod._STORE = old


# -- origin derivation (pure, recorded values only) ---------------------

def test_verified_model_wins_and_names_the_model():
    assert origin_label(
        {"verified_by_model": "muse-spark-1.3", "source_type": "text",
         "client_name": "Codex"}, "notes") == "verified by muse-spark-1.3"
    assert origin_label(
        {"verified_by_model": "muse-spark-1.3-fake"}, "notes") == \
        "verified by muse-spark-1.3-fake"


def test_model_key_falls_back_for_live_facts():
    # Live facts carry "model" in provenance (see app/live_meta.py).
    assert origin_label({"model": "muse-spark-1.3"}, "notes") == \
        "verified by muse-spark-1.3"


def test_clipper_origin_is_the_clipped_hostname():
    assert origin_label(
        {"source_type": "clipper"},
        "https://user:pass@example.com:8080/page?q=1") == "clipper · example.com"
    assert origin_label(
        {"source_type": "clipper"}, "example.com/page") == "clipper · example.com"
    assert origin_label(
        {"source_type": "clipper"}, "http://localhost:8000/") == "clipper · localhost"
    assert origin_label({"source_type": "clipper"}, "not a url") == "clipper · not a url"


def test_client_name_beats_client_id():
    assert origin_label(
        {"source_type": "text", "client_name": "Codex",
         "client_id": "sonja"}, "text") == "text · Codex"
    assert origin_label(
        {"source_type": "text", "client_id": "sonja"}, "text") == "text · sonja"
    # A recorded "unknown" client name falls through to client_id.
    assert origin_label(
        {"source_type": "text", "client_name": "unknown",
         "client_id": "sonja"}, "text") == "text · sonja"


def test_fallbacks_never_invent_a_name():
    assert origin_label({"source_type": "voice"}, "voice") == "voice"
    assert origin_label({}, "text") == "unknown origin"
    assert origin_label(None, "") == "unknown origin"
    assert origin_label({"client_name": "  "}, "text") == "unknown origin"


def test_long_labels_are_capped_not_wrapped():
    label = origin_label(
        {"verified_by_model": "a-very-long-model-name-that-keeps-going-forever-1.0"},
        "notes")
    assert len(label) <= 48
    assert label.startswith("verified by a-very-long-model")


# -- Cross-Hatch records the verifying model, wording untouched --------

def test_crosshatch_records_verified_by_model(store):
    result = crosshatch_verify("the shop opens at 9am", "general",
                               "test notes", "", store)
    assert result["status"] == "verified"
    mem = store.list_memories()[0]
    assert mem["provenance"]["verified_by_model"] == "muse-spark-1.3-fake"
    # Block 4 pins this wording: the new key is additive only.
    assert mem["provenance"]["verified_by"] == \
        "fake-meta verify + local token-overlap conflict check"
    assert origin_label(mem["provenance"], mem["source"]) == \
        "verified by muse-spark-1.3-fake"


# -- MCP clientInfo recording (no tool-signature changes) ---------------

def _capture_via_rpc(client_context, fact):
    init = handle_request({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"clientInfo": {"name": "Codex", "version": "1.2.3"}}},
        client_context)
    assert init["result"]["serverInfo"]["name"] == "hive-mind-mcp"
    resp = handle_request({
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "hivemind_capture_idea",
                   "arguments": {"content": fact, "source_type": "text",
                                 "domain_hint": "", "client_id": "sonja"}}},
        client_context)
    assert "error" not in resp


def test_initialize_clientinfo_reaches_capture_provenance(routed_store):
    ctx = {}
    _capture_via_rpc(ctx, "the library opens at 10am on weekdays")
    mem = routed_store.list_memories()[0]
    assert mem["provenance"]["client_name"] == "Codex"
    assert mem["provenance"]["client_id"] == "sonja"
    assert origin_label(mem["provenance"], mem["source"]) == "text · Codex"


def test_no_clientinfo_means_unknown_never_a_failure(routed_store):
    ctx = {}
    handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {}}, ctx)
    resp = handle_request({
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "hivemind_capture_idea",
                   "arguments": {"content": "the garden grows tomatoes",
                                 "source_type": "text", "domain_hint": "",
                                 "client_id": "sonja"}}}, ctx)
    assert "error" not in resp
    mem = routed_store.list_memories()[0]
    assert mem["provenance"]["client_name"] == "unknown"
    # Origin falls back to the recorded client_id, not "unknown".
    assert origin_label(mem["provenance"], mem["source"]) == "text · sonja"


def test_malformed_clientinfo_never_fails_a_call(routed_store):
    for params in ({"clientInfo": {"version": "1.0"}},
                   {"clientInfo": "Codex"},
                   {"clientInfo": None},
                   None):
        ctx = {}
        req = {"jsonrpc": "2.0", "id": 1, "method": "initialize"}
        if params is not None:
            req["params"] = params
        assert handle_request(req, ctx)["result"]["serverInfo"]["name"] == \
            "hive-mind-mcp"
        assert ctx.get("client_name", "unknown") == "unknown"


def test_initialize_notification_still_records_clientinfo():
    ctx = {}
    assert handle_request({
        "jsonrpc": "2.0", "method": "initialize",
        "params": {"clientInfo": {"name": "Kilo"}}}, ctx) is None
    assert ctx["client_name"] == "Kilo"


def test_two_connections_keep_separate_client_names(routed_store):
    ctx_a, ctx_b = {}, {}
    handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"clientInfo": {"name": "Codex"}}}, ctx_a)
    handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"clientInfo": {"name": "Kilo"}}}, ctx_b)
    for ctx, fact in ((ctx_a, "the shop opens at 9am"),
                      (ctx_b, "the garden grows tomatoes")):
        handle_request({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "hivemind_capture_idea",
                       "arguments": {"content": fact, "source_type": "text",
                                     "domain_hint": "", "client_id": "sonja"}}},
            ctx)
    names = {m["provenance"]["client_name"]
             for m in routed_store.list_memories()}
    assert names == {"Codex", "Kilo"}


def test_dispatch_client_name_is_additive_only(store):
    payload, _ = dispatch_tool("hivemind_capture_idea",
                               {"content": "bake bread at home",
                                "source_type": "text", "domain_hint": "",
                                "client_id": "c1"},
                               store=store, client_name="Codex")
    assert payload["status"] == "ok"
    by_text = {m["text"]: m for m in store.list_memories()}
    assert by_text["bake bread at home"]["provenance"]["client_name"] == "Codex"
    # Direct callers that pass none keep the old shape exactly.
    capture_idea("fix the docker bug", "text", "", "c1", store)
    by_text = {m["text"]: m for m in store.list_memories()}
    assert "client_name" not in by_text["fix the docker bug"]["provenance"]


def test_old_vault_provenance_still_derives_an_origin(store):
    # A memory stored before Block 17 has no client_name key at all.
    store.remember("the shop opens at 9am", source="text", domain="general",
                   provenance={"source_type": "text", "client_id": "sonja",
                               "cross_domains": [], "scrubbed": False})
    mem = store.list_memories()[0]
    assert "client_name" not in mem["provenance"]
    assert origin_label(mem["provenance"], mem["source"]) == "text · sonja"


# -- GUI export carries the origin field ---------------------------------

def test_gui_export_nodes_carry_origin(store):
    store.remember("the shop opens at 9am", source="text", domain="general",
                   provenance={"source_type": "text", "client_id": "sonja",
                               "cross_domains": [], "scrubbed": False})
    nodes = export_data(store)["nodes"]
    assert len(nodes) == 1
    assert nodes[0]["origin"] == "text · sonja"
    assert nodes[0]["provenance"]["client_id"] == "sonja"


# -- JS helpers, executed for real in Node -------------------------------

_NODE_HARNESS = """
const fs = require("fs");
const src = fs.readFileSync(%s, "utf8");
global.window = {};
eval(src);
const O = global.window.HIVEMIND_ORIGINS;
const assert = require("assert");
assert(O, "HIVEMIND_ORIGINS missing");
for (const fn of ["originColourFor", "originPattern", "patternDash",
                  "originOf", "groupOrigins", "legendEntries",
                  "mixHex", "parseColour"]) {
  assert.strictEqual(typeof O[fn], "function", fn);
}

const POSH = {accent: "#ad3375", edge: "#547c6d", text: "#ddd3d7",
              bg: "#080609", metal: "#a8891f", border: "#241d23"};
// Six defaults, all distinct, all palette-derived.
const defaults = [0, 1, 2, 3, 4, 5].map(i => O.originColourFor(i, POSH));
assert.strictEqual(new Set(defaults).size, 6, defaults.join(","));
assert.strictEqual(defaults[0], "#ad3375", "first default is the accent");
assert.strictEqual(defaults[1], "#547c6d", "second default is the edge");
assert.strictEqual(defaults[2], O.mixHex("#ad3375", "#ddd3d7", 0.45));
assert.strictEqual(defaults[3], "#a8891f", "fourth default is the metal");
assert.strictEqual(defaults[5], O.mixHex("#ad3375", "#080609", 0.4));
// Cycling: the seventh origin reuses the first default.
assert.strictEqual(O.originColourFor(6, POSH), defaults[0]);
// Computed-style rgb() values (what the browser actually returns)
// parse the same as hex.
assert.strictEqual(O.originColourFor(0, {accent: "rgb(173, 51, 117)", edge: "#547c6d",
  text: "#ddd3d7", bg: "#080609", metal: "#a8891f"}), "#ad3375");
// A different palette gives different defaults: never hardcoded.
const LIGHT = {accent: "#7c254f", edge: "#1f483f", text: "#211820",
               bg: "#dcd2d5", metal: "#a8891f", border: "#32262d"};
assert.notStrictEqual(O.originColourFor(0, LIGHT), defaults[0]);
// No hardcoded neon/electric colours anywhere in the defaults.
for (const c of defaults) {
  assert.ok(!["#ff00ff", "#00ffff", "#ff1e89", "#00ff00"].includes(c), c);
  assert.ok(/^#[0-9a-f]{6}$/.test(c), c);
}

// Patterns cycle solid / dashed / dotted / double, index only.
assert.deepStrictEqual(
  [0, 1, 2, 3, 4].map(O.originPattern),
  ["solid", "dashed", "dotted", "double", "solid"]);
assert.deepStrictEqual(O.patternDash("dashed"), [6, 4]);
assert.deepStrictEqual(O.patternDash("dotted"), [2, 4]);
assert.deepStrictEqual(O.patternDash("solid"), []);
assert.deepStrictEqual(O.patternDash("double"), []);

// Patterns and legend entries never depend on colours: the SAME
// result under a greyscale palette as under the Posh palette.
const GREY = {accent: "#808080", edge: "#808080", text: "#ffffff",
              bg: "#000000", metal: "#808080", border: "#808080"};
const nodes = [
  {origin: "text · sonja"}, {origin: "verified by muse-spark-1.3"},
  {origin: "text · sonja"}, {origin: "clipper · example.com"},
  {origin: "verified by muse-spark-1.3"}, {}
];
assert.deepStrictEqual(O.legendEntries(nodes), [
  {origin: "text · sonja", count: 2, pattern: "solid", patternIndex: 0},
  {origin: "verified by muse-spark-1.3", count: 2, pattern: "dashed", patternIndex: 1},
  {origin: "clipper · example.com", count: 1, pattern: "dotted", patternIndex: 2},
  {origin: "unknown origin", count: 1, pattern: "double", patternIndex: 3}
]);
// Grouping never hides an origin from the legend: counts are per
// memory, not per drawn group.
assert.strictEqual(O.legendEntries(nodes).reduce((s, e) => s + e.count, 0), 6);
// Group origins: first-seen unique, representative fallback, empty safe.
assert.deepStrictEqual(
  O.groupOrigins({members: [{origin: "text · sonja"}, {origin: "clipper · example.com"}, {origin: "text · sonja"}]}),
  ["text · sonja", "clipper · example.com"]);
assert.deepStrictEqual(
  O.groupOrigins({representative: {origin: "verified by muse-spark-1.3"}}),
  ["verified by muse-spark-1.3"]);
assert.deepStrictEqual(O.groupOrigins({members: []}), ["unknown origin"]);
assert.strictEqual(O.originOf(null), "unknown origin");
assert.strictEqual(O.originOf({}), "unknown origin");

// Settings round-trip, using the real DEFAULTS literal from app.js:
// saved origin_colours survive the load merge; a fresh load keeps
// the empty map; the accessibility reset key list (checked in
// Python below) is what protects the map from resets.
const appSrc = fs.readFileSync(%s, "utf8");
const defaultsSrc = appSrc.match(/var DEFAULTS = \\{([\\s\\S]*?)\\n  \\};/)[1];
const DEFAULTS = eval("({" + defaultsSrc + "})");
assert.deepStrictEqual(DEFAULTS.origin_colours, {});
const saved = Object.assign({}, DEFAULTS, {origin_colours: {"text · sonja": "#123456"}});
const reloaded = Object.assign({}, DEFAULTS, JSON.parse(JSON.stringify(saved)));
assert.strictEqual(reloaded.origin_colours["text · sonja"], "#123456");
assert.strictEqual(reloaded.tooltips_enabled, true);
"""


def _run_node_harness():
    harness = _NODE_HARNESS % (
        json.dumps(os.path.join(REPO, "gui", "stage.js")),
        json.dumps(os.path.join(REPO, "gui", "app.js")),
    )
    proc = subprocess.run(["node", "-e", harness],
                          capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_js_origin_helpers_execute_for_real():
    _run_node_harness()


# -- Static wiring: HTML, CSS, app.js ------------------------------------

def _read(rel):
    with open(os.path.join(REPO, rel), encoding="utf-8") as fh:
        return fh.read()


def test_legend_present_in_html_with_counts_and_no_title_attrs():
    html = _read("gui/index.html")
    assert '<ul id="origin-legend" class="origin-legend" ' \
        'aria-label="Memory origins, with counts"></ul>' in html
    assert '<h3 class="glow-auto">Origins</h3>' in html
    # The legend sits in the graph section, before the text list.
    assert html.index('id="origin-legend"') < html.index('id="node-list"')
    # Fast-tooltips SOP: zero title attributes anywhere in the GUI.
    for rel in ("gui/index.html", "gui/app.js", "gui/stage.js"):
        assert "title=" not in _read(rel), rel


def test_origin_colours_group_is_regular_settings_not_accessibility():
    html = _read("gui/index.html")
    regular_start = html.index('id="regular-settings"')
    integrations_start = html.index('id="integrations"')
    group = html.index('id="origin-colours"')
    assert regular_start < group < integrations_start
    assert '<h3 class="glow-auto">Origin colours</h3>' in html
    assert 'id="reset-origin-colours"' in html
    # No colour input inside the Accessibility Suite section.
    suite_start = html.index('id="accessibility-suite"')
    assert 'id="origin-colours"' not in html[suite_start:regular_start]
    # No password/key input of any kind in the group.
    assert 'type="password"' not in html


def test_appjs_origin_settings_survive_accessibility_reset():
    app = _read("gui/app.js")
    assert "origin_colours: {}" in app
    keys_block = app[app.index("var ACCESSIBILITY_KEYS"):app.index("];", app.index("var ACCESSIBILITY_KEYS")) + 2]
    assert "origin_colours" not in keys_block
    assert "tooltips_enabled" not in keys_block
    assert 'document.getElementById("reset-origin-colours")' in app
    assert "state.origin_colours = {}" in app


def test_appjs_colour_inputs_carry_tooltips_and_bind_late():
    app = _read("gui/app.js")
    assert 'input.type = "color"' in app
    assert "bindTooltipElement(input)" in app
    assert 'input.setAttribute("data-tooltip"' in app
    assert "Choose the ring colour for memories from" in app
    assert "__hivemindTooltipBound" in app


def test_appjs_canvas_uses_origin_colour_and_pattern():
    app = _read("gui/app.js")
    assert "ringColour = originColour(firstOrigin" in app
    assert "ringPattern = originPatternFor(firstOrigin" in app
    assert "api.patternDash(ringPattern)" in app
    assert "drawShapeOutline(ctx, rep.shape" in app
    assert "ctx.setLineDash([])" in app, "dash must be cleared after the node"
    # Node fill stays the palette node colour.
    assert 'styles.getPropertyValue("--node")' in app
    # Text list and SVG view name the origin in words.
    assert '", origin " + nodeOrigin + ": "' in app
    assert '" — " + (originApi() ? originApi().originOf(node)' in app
    # Legend renders from every memory with counts.
    assert "renderOriginLegend(originPalette, originOrder)" in app
    assert "api.legendEntries(graphData.nodes)" in app
    assert "entry.count" in app


def test_css_swatches_carry_pattern_by_border_style():
    css = _read("gui/styles.css")
    assert ".origin-swatch-dashed { border-style: dashed; }" in css
    assert ".origin-swatch-dotted { border-style: dotted; }" in css
    assert ".origin-swatch-double { border-style: solid; outline: 2px solid" in css
    assert 'input[type="color"]' in css


def test_pattern_code_paths_do_not_depend_on_colour_variables():
    stage = _read("gui/stage.js")
    start = stage.index("Origin colours + ring patterns")
    end = stage.index("Integrations status words")
    block = stage[start:end]
    for forbidden in ("getComputedStyle", "getPropertyValue", "--accent",
                      "--edge", "--node", "var(--", "saturation"):
        assert forbidden not in block, forbidden
    # The pattern/legend helpers are defined inside that block.
    for name in ("function originPattern", "function patternDash",
                 "function legendEntries", "function groupOrigins"):
        assert name in block, name


def test_lock_in_spec_unchanged():
    digest = hashlib.md5(
        open(os.path.join(REPO, "docs", "HIVE-MIND-LOCK-IN-SPEC.md"), "rb").read()
    ).hexdigest()
    assert digest == "13fa897039dd6b1cd0d11e90e85d7c2c"
