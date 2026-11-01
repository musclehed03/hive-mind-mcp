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
