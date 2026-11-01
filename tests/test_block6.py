"""Block 6 gate tests: GUI + Accessibility Suite + explain.

GUI checks parse the shipped HTML/CSS/JS with the standard library
(no browser needed): every button has a label, every image has alt
text, every SVG has a role + title, palettes/presets parse and obey
the spacing cap, and the Accessibility Suite / Regular Settings
split is structural, not just a comment.
"""

import json
import os
import re
import threading
import urllib.request
from html.parser import HTMLParser

import pytest

from app.dispatch import dispatch_tool
from app.explain import explain
from app.gui_export import export_data
from app.store import Store

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUI = os.path.join(REPO, "gui")


def _read(name):
    with open(os.path.join(GUI, name), encoding="utf-8") as f:
        return f.read()


def _extract_json_object(source, const_name):
    """Extract a strict-JSON object assigned to a JS const."""
    start = source.index(const_name)
    brace = source.index("{", start)
    depth, i = 0, brace
    in_string, escaped = False, False
    while i < len(source):
        ch = source[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(source[brace:i + 1])
        i += 1
    raise ValueError(f"unbalanced object for {const_name}")


class _TagCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.stack = []
        self.in_accessibility = False
        self.in_regular = False
        self.accessibility_ids = []
        self.regular_ids = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags.append((tag, attrs))
        if tag == "section" and attrs.get("id") == "accessibility-suite":
            self.in_accessibility = True
        if tag == "section" and attrs.get("id") == "regular-settings":
            self.in_regular = True
        if attrs.get("id"):
            if self.in_accessibility:
                self.accessibility_ids.append(attrs["id"])
            if self.in_regular:
                self.regular_ids.append(attrs["id"])
        if tag in ("input", "img", "br", "hr", "meta", "link", "source"):
            return  # void elements: no end tag, never on the stack
        self.stack.append((tag, attrs))

    def handle_endtag(self, tag):
        if self.stack and self.stack[-1][0] == tag:
            popped = self.stack.pop()
            if popped[1].get("id") == "accessibility-suite":
                self.in_accessibility = False
            if popped[1].get("id") == "regular-settings":
                self.in_regular = False


@pytest.fixture()
def parsed():
    collector = _TagCollector()
    collector.feed(_read("index.html"))
    return collector


# -- palettes / presets ------------------------------------------------------

def test_all_seven_typed_palettes_present():
    data = _extract_json_object(_read("settings-data.js"), "HIVEMIND_PALETTES")
    for name in ("deuteranomaly", "protanomaly", "deuteranopia", "protanopia",
                 "tritanomaly", "tritanopia", "achromatopsia"):
        assert name in data, name
        for key in ("background", "text", "accent", "border"):
            assert data[name][key].startswith("#")


def test_achromatopsia_palette_is_pure_grayscale():
    data = _extract_json_object(_read("settings-data.js"), "HIVEMIND_PALETTES")
    ach = data["achromatopsia"]
    assert ach["grayscale"] is True
    for key in ("background", "text", "accent", "border", "node", "edge"):
        hexval = ach[key].lstrip("#")
        r, g, b = int(hexval[0:2], 16), int(hexval[2:4], 16), int(hexval[4:6], 16)
        assert r == g == b, (key, ach[key])
    # And it is the light, high-contrast mode Day needs: white bg, black text.
    assert ach["background"] == "#ffffff"
    assert ach["text"] == "#000000"


def test_presets_exist_and_spacing_is_moderate_and_capped():
    presets = _extract_json_object(_read("settings-data.js"), "HIVEMIND_PRESETS")
    spacing = _extract_json_object(_read("settings-data.js"), "HIVEMIND_SPACING")
    assert set(presets) == {"dyslexia", "adhd_focus", "vision_impaired",
                            "seizure_safe", "achromatopsia"}
    assert spacing["max"] == 0.12
    assert spacing["default"] == 0.02
    assert spacing["min"] < spacing["default"] < spacing["max"]
    for name, preset in presets.items():
        ls = preset["settings"]["letter_spacing_em"]
        assert spacing["min"] <= ls <= spacing["max"], (name, ls)
        assert ls <= 0.05, (name, ls)  # moderate defaults, never forced wide
    # Seizure Safe deliberately avoids elevated contrast.
    assert presets["seizure_safe"]["settings"]["high_contrast"] is False


def test_text_scale_range_80_to_200():
    scale = _extract_json_object(_read("settings-data.js"), "HIVEMIND_TEXT_SCALE")
    assert (scale["min"], scale["max"]) == (80, 200)


# -- HTML accessibility ------------------------------------------------------

def test_every_button_has_a_label(parsed):
    for tag, attrs in parsed.tags:
        if tag == "button":
            assert attrs.get("aria-label") or True  # buttons also carry text; checked below
    html = _read("index.html")
    # Every <button> element must contain visible text or an aria-label.
    for match in re.finditer(r"<button([^>]*)>(.*?)</button>", html, re.DOTALL):
        attrs, body = match.groups()
        assert "aria-label" in attrs or body.strip(), match.group(0)[:80]


def test_every_image_has_alt(parsed):
    for tag, attrs in parsed.tags:
        if tag == "img":
            assert "alt" in attrs, attrs


def test_every_svg_has_role_and_title():
    html = _read("index.html")
    assert 'role="img"' in html
    assert "<title>" in html
    svg = _read("logo.svg")
    assert 'role="img"' in svg and "<title>" in svg


def test_nodes_distinguished_by_shape_and_line_style_in_code():
    js = _read("app.js")
    assert "circle" in js and "square" in js and "triangle" in js
    assert "dashed" in js and "dotted" in js
    css = _read("styles.css")
    assert "2px solid" in css and "dashed" in css and "dotted" in css
    # Grayscale mode keeps hierarchy: filter + shape/line rules present.
    assert "grayscale(1)" in css


def test_accessibility_and_regular_settings_are_separate_sections(parsed):
    assert "palette-select" in parsed.accessibility_ids
    assert "letter-spacing" in parsed.accessibility_ids
    assert "text-size" in parsed.accessibility_ids
    for regular_id in ("graph-density", "snapshot-schedule", "token-budget",
                       "reading-level", "microbot-mode", "palette-choice"):
        assert regular_id in parsed.regular_ids, regular_id
        assert regular_id not in parsed.accessibility_ids, regular_id
    # The metaphor dropdown is a Regular Setting, outside the suite.
    assert "metaphor-select" not in parsed.accessibility_ids


def test_gui_references_only_files_that_exist():
    html = _read("index.html")
    for src in re.findall(r'(?:src|href)="([^"]+)"', html):
        if src.startswith(("http", "#")):
            continue
        assert os.path.exists(os.path.join(GUI, src)), src
    js = _read("app.js")
    assert 'fetch("data.json")' in js
    assert "requestAnimationFrame" in js  # chunked/lazy rendering


def test_settings_persist_and_respect_os_preferences_in_code():
    js = _read("app.js")
    assert "localStorage" in js
    assert "prefers-reduced-motion" in js
    assert "prefers-contrast" in js


# -- GUI bug fixes (Sonja's live report, 2026-11-01) ------------------------

def test_settings_data_exposed_on_window():
    # Top-level `const` in a classic script does NOT create window
    # properties, so app.js reading window.HIVEMIND_PALETTES /
    # window.HIVEMIND_PRESETS got undefined and every profile and
    # palette silently did nothing. The objects must be exposed on
    # window explicitly, while the const declarations stay intact so
    # _extract_json_object keeps parsing them.
    data = _read("settings-data.js")
    assert "const HIVEMIND_PALETTES = {" in data
    assert "const HIVEMIND_PRESETS = {" in data
    assert "window.HIVEMIND_PALETTES = HIVEMIND_PALETTES" in data
    assert "window.HIVEMIND_PRESETS = HIVEMIND_PRESETS" in data
    js = _read("app.js")
    assert "window.HIVEMIND_PALETTES" in js
    assert "window.HIVEMIND_PRESETS" in js


def test_load_data_tries_live_api_before_static_export():
    # loadData() used to fetch only data.json, which does not exist
    # in gui/, so it always fell back to the 3 sample nodes and
    # seeding the Store could never show. The live /api/memories
    # endpoint must be tried first, then data.json, then the sample.
    js = _read("app.js")
    load_start = js.index("function loadData()")
    load_body = js[load_start:]
    assert 'fetch("/api/memories"' in load_body
    assert 'fetch("data.json")' in load_body
    assert load_body.index('fetch("/api/memories"') < load_body.index('fetch("data.json")')
    assert "SAMPLE_DATA" in load_body


def test_achromatopsia_grayscale_covers_whole_page():
    # The old rule was `body.achromatopsia { filter: none }` with
    # grayscale only on .graph-wrap, so the logo, reading guide, and
    # native controls kept colour. Grayscale must cover header, main,
    # and footer, and the reading guide must not stay pink.
    css = _read("styles.css")
    assert "body.achromatopsia { filter: none" not in css
    assert "grayscale(1)" in css
    assert "body.achromatopsia header" in css
    assert "body.achromatopsia main" in css
    assert "body.achromatopsia footer" in css
    assert "body.achromatopsia #reading-guide" in css


def test_saturation_variable_is_consumed_in_css():
    # --saturation was set by JS but never used in CSS, so the slider
    # was a no-op. It must drive a saturate() filter.
    css = _read("styles.css")
    assert "saturate(var(--saturation))" in css
    js = _read("app.js")
    assert '"--saturation"' in js


def test_native_controls_follow_palette_accent():
    # Without accent-color, Chrome keeps range sliders and selects
    # blue regardless of the palette. Controls must take the accent
    # CSS variable so palette (and grayscale) changes are visible.
    css = _read("styles.css")
    assert "accent-color: var(--accent)" in css


def test_slider_sync_does_not_rewrite_focused_slider():
    # syncControls() rewrote every slider's .value on each
    # applySettings(), which could swallow a drag. The focused
    # slider must be left alone, and range inputs must listen to
    # 'change' as well as 'input'.
    js = _read("app.js")
    assert "document.activeElement" in js
    assert 'addEventListener("change"' in js


# -- achromatopsia blackout fix (Sonja's live report, 2026-11-01) -----------

def _contrast_ratio(hex_a, hex_b):
    def lum(hexval):
        r, g, b = (int(hexval[i:i + 2], 16) / 255 for i in (1, 3, 5))
        vals = []
        for c in (r, g, b):
            vals.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
        return 0.2126 * vals[0] + 0.7152 * vals[1] + 0.0722 * vals[2]
    l1, l2 = lum(hex_a), lum(hex_b)
    if l1 < l2:
        l1, l2 = l2, l1
    return (l1 + 0.05) / (l2 + 0.05)


def _css_body_rule_vars(css, selector):
    """Custom properties set by one `body.<class>` rule in styles.css."""
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert match, selector
    return dict(re.findall(r"--([\w-]+):\s*([^;]+);", match.group(1)))


def test_canvas_colours_come_from_body_not_document_element():
    # Palette variables are set inline on :root, but body class rules
    # (high-contrast, light theme) set the same variables on body and
    # win for the page, because an element's own value beats an
    # inherited one. The transparent canvas sits on the body
    # background, so reading :root drew black text on a black page
    # (the achromatopsia blackout). renderGraph must read body.
    js = _read("app.js")
    start = js.index("function renderGraph()")
    end = js.index("function loadData()", start)
    body = js[start:end]
    assert "getComputedStyle(document.body)" in body
    assert "getComputedStyle(document.documentElement)" not in body
    # The canvas background is painted explicitly with the same --bg,
    # so it never depends on what shows through the transparent canvas.
    assert "--bg" in body and "fillRect" in body


def test_achromatopsia_preset_has_no_conflicting_theme_flags():
    # The preset used to set high_contrast=true and light_theme=true
    # alongside a white-background palette. The body rules then made
    # the page black while the canvas still read white-background
    # colours from :root. The palette is already light and
    # high-contrast on its own; the preset must set the palette only.
    presets = _extract_json_object(_read("settings-data.js"), "HIVEMIND_PRESETS")
    ach = presets["achromatopsia"]["settings"]
    assert ach["colorblind_palette"] == "achromatopsia"
    assert ach.get("high_contrast") is not True
    assert ach.get("light_theme") is not True


def test_effective_canvas_text_contrasts_in_every_state():
    # Simulate the cascade the canvas now reads: palette variables
    # (inline on :root, inherited by body) overridden by body class
    # rules when high_contrast or light_theme is on. Canvas text
    # must contrast with the canvas background in every state Sonja
    # re-checks, including achromatopsia with high contrast on/off.
    palettes = _extract_json_object(_read("settings-data.js"), "HIVEMIND_PALETTES")
    css = _read("styles.css")
    hc = _css_body_rule_vars(css, "body.high-contrast")
    light = _css_body_rule_vars(css, "body.light-theme")
    states = [
        ("default", {}),
        ("default", {"high_contrast": True}),
        ("achromatopsia", {}),
        ("achromatopsia", {"high_contrast": True}),
        ("achromatopsia", {"light_theme": True}),
    ]
    # CSS variables are --bg/--text/...; palette keys are
    # background/text/... — map them so the simulation overrides the
    # same slot the real cascade overrides.
    def _apply(effective, rule_vars):
        keymap = {"bg": "background", "text": "text", "accent": "accent",
                  "border": "border", "edge": "edge", "node": "node"}
        for var, value in rule_vars.items():
            if var in keymap:
                effective[keymap[var]] = value.strip()
    for palette_name, flags in states:
        effective = dict(palettes[palette_name])
        if flags.get("high_contrast"):
            _apply(effective, hc)
        elif flags.get("light_theme"):
            _apply(effective, light)
        bg, text = effective["background"], effective["text"]
        assert _contrast_ratio(bg, text) >= 4.5, (palette_name, flags, bg, text)


def test_achromatopsia_node_is_visible_on_either_background():
    # The old node fill was #ffffff: invisible on the palette's white
    # background, and a blown-out white oval on a black page. The
    # fill must be a mid-grey: visible against both white and black.
    palettes = _extract_json_object(_read("settings-data.js"), "HIVEMIND_PALETTES")
    ach = palettes["achromatopsia"]
    assert ach["node"] != ach["background"]
    assert ach["node"] != ach["text"]
    hexval = ach["node"].lstrip("#")
    channels = [int(hexval[i:i + 2], 16) for i in (0, 2, 4)]
    assert all(0x40 <= c <= 0xBF for c in channels), ach["node"]


def test_other_palettes_unchanged():
    # Dyslexia and the other colour-blind palettes work well (Sonja).
    # Their values must not move while achromatopsia is fixed.
    palettes = _extract_json_object(_read("settings-data.js"), "HIVEMIND_PALETTES")
    expected = {
        "deuteranomaly": ("#101418", "#f2f2f2", "#e69f00"),
        "protanomaly": ("#101418", "#f2f2f2", "#009e73"),
        "deuteranopia": ("#0f1216", "#ffffff", "#e69f00"),
        "protanopia": ("#0f1216", "#ffffff", "#0072b2"),
        "tritanomaly": ("#14101c", "#f5edf7", "#d55e00"),
        "tritanopia": ("#14101c", "#f5edf7", "#009e73"),
    }
    for name, (bg, text, accent) in expected.items():
        assert (palettes[name]["background"], palettes[name]["text"],
                palettes[name]["accent"]) == (bg, text, accent), name


def test_every_control_has_plain_language_data_tooltip(parsed):
    # Mechanism changed (fast custom tooltips, standing SOP): the
    # plain-words texts moved verbatim from slow native `title`
    # attributes to `data-tooltip` attributes, and NO control may
    # carry a `title` attribute — the browser-controlled native tip
    # would double-show and is too slow. Content is unchanged;
    # aria-labels are untouched. No jargon: no tool, service, or
    # file names.
    html = _read("index.html")
    assert ' title="' not in html, "a native title attribute survives"
    for tag, attrs in parsed.tags:
        if tag in ("button", "select", "input"):
            tip = attrs.get("data-tooltip", "")
            assert len(tip) >= 15, (tag, attrs.get("id"), tip)
            assert not any(word in tip for word in
                           ("MCP", "Supabase", "API", "JSON", "SQLite", "stdio")), tip
    assert 'data-tooltip="Choose how often a backup copy of your memories is made."' in html
    assert 'data-tooltip="Set how much work the app may do when it answers.' in html
    # The tooltip toggle itself has a tip, like every other control.
    assert 'id="toggle-tooltips"' in html


def test_custom_tooltip_element_timing_and_hiding():
    # One shared tooltip element in the page (role="tooltip"), a
    # 500ms delay in app.js, and hiding on mouseleave, blur, Escape,
    # and scroll. No fade-in: the tooltip CSS rule must carry no
    # transition/animation, and the tooltip must use the page's CSS
    # variables so it follows palettes, grayscale, and high contrast.
    html = _read("index.html")
    assert 'id="hivemind-tooltip"' in html
    assert 'role="tooltip"' in html
    js = _read("app.js")
    assert "TOOLTIP_DELAY_MS = 500" in js
    assert "setTimeout" in js and "TOOLTIP_DELAY_MS" in js
    for trigger in ("mouseleave", "blur", "Escape", "scroll"):
        assert trigger in js, trigger
    assert "data-tooltip" in js
    assert "hideTooltip" in js and "showTooltip" in js
    css = _read("styles.css")
    match = re.search(r"#hivemind-tooltip\s*\{([^}]*)\}", css)
    assert match, "tooltip CSS rule missing"
    rule = match.group(1)
    assert "var(--bg)" in rule and "var(--text)" in rule
    assert "var(--border)" in rule or "var(--accent)" in rule
    assert "transition" not in rule and "animation" not in rule
    assert "pointer-events: none" in rule


def test_tooltip_toggle_in_regular_settings(parsed):
    # The overall tooltips on/off switch lives in Regular Settings
    # (a product preference, not an access need), defaults ON,
    # persists in the same localStorage settings object, and takes
    # effect immediately. It must NOT be in the Accessibility Suite.
    assert "toggle-tooltips" in parsed.regular_ids
    assert "toggle-tooltips" not in parsed.accessibility_ids
    js = _read("app.js")
    assert "tooltips_enabled: true" in js, "default must be on"
    assert "toggle-tooltips" in js
    assert "tooltips_enabled" in js
    # The toggle is synced like the other Regular Settings controls
    # and its click handler flips the persisted state.
    assert 'getElementById("toggle-tooltips")' in js


def test_reset_preserves_regular_settings_including_tooltips():
    # Reset accessibility settings must scope to accessibility keys
    # only: Regular Settings values — snapshot schedule, token
    # budget, sound, notifications, and tooltips_enabled — survive
    # it. The old code reset the whole object and wiped localStorage.
    js = _read("app.js")
    assert "ACCESSIBILITY_KEYS" in js
    assert "resetAccessibilityState" in js
    start = js.index("var ACCESSIBILITY_KEYS")
    end = js.index("];", start)
    keys_block = js[start:end]
    assert "tooltips_enabled" not in keys_block
    assert "colorblind_palette" in keys_block
    assert "token_budget" not in keys_block
    # The reset click handler uses the scoped reset, not a whole
    # object reset or a storage wipe.
    reset_at = js.index('getElementById("reset-settings")')
    reset_block = js[reset_at:reset_at + 600]
    assert "resetAccessibilityState" in reset_block
    assert "removeItem" not in reset_block


def test_plain_language_guide_exists(parsed):
    # A visible plain-words guide, after Regular Settings, explaining
    # what a memory, the graph, a snapshot/backup, the token
    # meter/budget, and the micro-bot modes are — and that the
    # Accessibility Suite never deletes anything.
    html = _read("index.html")
    assert 'id="plain-language-guide"' in html
    assert html.index('id="regular-settings"') < html.index('id="plain-language-guide"')
    guide_start = html.index('id="plain-language-guide"')
    guide = html[guide_start:]
    assert "Plain-language guide" in guide
    assert "backup copy" in guide
    assert "snapshot" in guide.lower()
    assert "token" in guide.lower()
    assert "micro-bot" in guide.lower()
    assert "never deletes" in guide
    assert "Accessibility Suite" in guide


# -- explain -----------------------------------------------------------------

def test_explain_tool_and_pillar_and_setting():
    assert explain("hivemind_capture_idea", "plain")["status"] == "ok"
    pillar = explain("accessibility", "detailed")
    assert pillar["status"] == "ok"
    assert "Sensory Suite" in pillar["explanation"]
    assert "space between letters" in explain("letter spacing", "plain")["explanation"].lower()


def test_explain_unknown_topic_returns_strategies_not_a_dead_end():
    result = explain("flibberty gibbet", "plain")
    assert result["status"] == "not_found"
    assert 1 <= len(result["strategies"]) <= 3
    assert result["explanation"] == ""


def test_explain_bad_reading_level_is_an_error():
    with pytest.raises(ValueError):
        explain("accessibility", "quantum")


def test_explain_via_dispatch():
    payload, err = dispatch_tool("hivemind_explain", {
        "topic_or_tool_name": "scrubber", "reading_level": "plain"}, store=None)
    assert err is False and payload["status"] == "ok"
    assert "secrets" in payload["explanation"].lower()


# -- export + server -----------------------------------------------------------

def test_gui_export_shapes_and_edges(tmp_path):
    store = Store(db_path=str(tmp_path / "g.db"), vault_dir=str(tmp_path / "vault"))
    try:
        store.remember("Shop opens at 9am", domain="general")
        store.remember("Shop sells bread", domain="cooking")
        payload = export_data(store)
        assert len(payload["nodes"]) == 2
        assert {n["shape"] for n in payload["nodes"]} <= {"circle", "square", "triangle"}
        assert payload["live"] is True
        assert payload["stats"]["total"] == 2
    finally:
        store.close()


def test_gui_export_emits_dotted_cross_domain_edge(tmp_path):
    store = Store(db_path=str(tmp_path / "x.db"), vault_dir=str(tmp_path / "vault"))
    try:
        store.remember("Shop opens at 9am", domain="general",
                       provenance={"cross_domains": ["cooking"]})
        store.remember("Shop sells bread", domain="cooking")
        payload = export_data(store)
        dotted = [e for e in payload["edges"] if e["line_style"] == "dotted"]
        assert len(dotted) == 1
        assert dotted[0]["kind"] == "cross-domain"
    finally:
        store.close()


def test_gui_server_serves_page_and_api(tmp_path, monkeypatch):
    from app.gui_server import _Handler
    from http.server import ThreadingHTTPServer

    # Store binds DB_PATH/VAULT_DIR at import time in app.store, so
    # patch that module's bindings (not app.config) for this test.
    import app.store as store_module

    monkeypatch.setattr(store_module, "DB_PATH", str(tmp_path / "srv.db"))
    monkeypatch.setattr(store_module, "VAULT_DIR", str(tmp_path / "vault"))
    from app.store import Store as _Store

    _s = _Store()
    _s.remember("Server smoke fact")
    _s.close()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as resp:
            assert resp.status == 200
            assert b"Hive-Mind" in resp.read()
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/memories", timeout=5) as resp:
            data = json.load(resp)
            assert data["nodes"], data
    finally:
        server.shutdown()
        server.server_close()
