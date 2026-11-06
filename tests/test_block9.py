"""Block 9 gate tests: Variant A (Velvet Boudoir & Brushed Gold) is the
real GUI default, dark + light, from the canonical Posh/Mature tokens
(Dollhouse Deviants website repo draft PR #4,
src/theme/posh-mature-palette.css). The other six typed palettes and
achromatopsia must not move.
"""

import json
import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(name):
    with open(os.path.join(REPO, "gui", name), encoding="utf-8") as f:
        return f.read()


def _extract_json_object(source, name):
    start = source.index(name)
    brace = source.index("{", start)
    depth = 0
    for i in range(brace, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(source[brace:i + 1])
    raise ValueError(name)


def _css_vars(css, selector):
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert match, selector
    out = {}
    for decl in match.group(1).split(";"):
        if ":" in decl:
            key, value = decl.split(":", 1)
            out[key.strip()] = value.strip()
    return out


# Sonja 2026-11-06: dark base moved to True Black, light theme to
# actual white. Variant A hues (accent/edge/metal/text) unchanged.
VARIANT_A_DARK = {
    "background": "#000000", "text": "#ddd3d7", "accent": "#ad3375",
    "border": "#241d23", "node": "#120d11", "edge": "#547c6d",
    "metal": "#a8891f",
}

VARIANT_A_LIGHT = {
    "--bg": "#ffffff", "--text": "#211820", "--accent": "#7c254f",
    "--border": "#32262d", "--node": "#ece5e7", "--edge": "#1f483f",
}


def test_default_palette_is_variant_a_dark():
    palettes = _extract_json_object(_read("settings-data.js"), "HIVEMIND_PALETTES")
    default = palettes["default"]
    for key, value in VARIANT_A_DARK.items():
        assert default[key] == value, (key, default.get(key))
    assert default["grayscale"] is False


def test_css_root_defaults_match_variant_a_dark():
    css = _read("styles.css")
    root = _css_vars(css, ":root")
    assert root["--bg"] == "#000000"  # True Black base, Sonja 2026-11-06
    assert root["--text"] == "#ddd3d7"
    assert root["--accent"] == "#ad3375"
    assert root["--border"] == "#241d23"
    assert root["--node"] == "#120d11"
    assert root["--edge"] == "#547c6d"
    assert root["--metal"] == "#a8891f"


def test_light_theme_rule_is_variant_a_light():
    css = _read("styles.css")
    light = _css_vars(css, "body.light-theme")
    for var, value in VARIANT_A_LIGHT.items():
        assert light[var] == value, (var, light.get(var))


def test_other_palettes_and_achromatopsia_unchanged():
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
        got = palettes[name]
        assert (got["background"], got["text"], got["accent"]) == (bg, text, accent), name
    ach = palettes["achromatopsia"]
    assert ach == {"label": "Achromatopsia (pure grayscale)",
                   "background": "#ffffff", "text": "#000000",
                   "accent": "#595959", "border": "#000000",
                   "node": "#808080", "edge": "#000000", "grayscale": True}


def test_metal_is_only_a_pinstripe():
    # Metal appears in CSS only as the 1px header top border and the
    # --metal variable itself: never as a fill, never as text colour.
    css = _read("styles.css")
    assert "border-top: 1px solid var(--metal)" in css
    assert css.count("var(--metal)") == 1
    assert "#c9b276" not in css and "#66501f" not in css


def test_no_placeholder_palette_colours_remain_in_gui_defaults():
    # The pre-Variant-A placeholder orchid must be gone from the
    # defaults; it survives nowhere the GUI paints by default.
    assert "#c86dd7" not in _read("settings-data.js")
    assert "#c86dd7" not in _read("styles.css")
    assert "#c86dd7" not in _read("app.js")


def test_app_js_applies_metal_from_palette():
    js = _read("app.js")
    assert '"--metal"' in js
    assert "palette.metal" in js
