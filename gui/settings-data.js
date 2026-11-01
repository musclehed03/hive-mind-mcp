/* Hive-Mind settings data: typed colour-blind palettes + one-tap profiles.
   Values below are GUI defaults for this app. The canonical Deluxe Posh
   palette tokens live in the Dollhouse Deviants website repo; these
   values are not presented as those canonical tokens. The achromatopsia
   palette is pure grayscale (every colour has R == G == B) by design.
   Objects are written as strict JSON so tests can parse them. */
const HIVEMIND_PALETTES = {
  "default": {"label": "Default (Deluxe Posh)", "background": "#14101c", "text": "#f5edf7", "accent": "#c86dd7", "border": "#3a2e4a", "node": "#2a2138", "edge": "#8e7aa8", "grayscale": false},
  "deuteranomaly": {"label": "Deuteranomaly", "background": "#101418", "text": "#f2f2f2", "accent": "#e69f00", "border": "#4a4a4a", "node": "#1c242c", "edge": "#56b4e9", "grayscale": false},
  "protanomaly": {"label": "Protanomaly", "background": "#101418", "text": "#f2f2f2", "accent": "#009e73", "border": "#4a4a4a", "node": "#1c242c", "edge": "#e69f00", "grayscale": false},
  "deuteranopia": {"label": "Deuteranopia", "background": "#0f1216", "text": "#ffffff", "accent": "#e69f00", "border": "#5a5a5a", "node": "#1a2028", "edge": "#56b4e9", "grayscale": false},
  "protanopia": {"label": "Protanopia", "background": "#0f1216", "text": "#ffffff", "accent": "#0072b2", "border": "#5a5a5a", "node": "#1a2028", "edge": "#e69f00", "grayscale": false},
  "tritanomaly": {"label": "Tritanomaly", "background": "#14101c", "text": "#f5edf7", "accent": "#d55e00", "border": "#3a2e4a", "node": "#241c30", "edge": "#009e73", "grayscale": false},
  "tritanopia": {"label": "Tritanopia", "background": "#14101c", "text": "#f5edf7", "accent": "#009e73", "border": "#3a2e4a", "node": "#241c30", "edge": "#cc79a7", "grayscale": false},
  "achromatopsia": {"label": "Achromatopsia (pure grayscale)", "background": "#ffffff", "text": "#000000", "accent": "#595959", "border": "#000000", "node": "#ffffff", "edge": "#000000", "grayscale": true}
};
const HIVEMIND_PRESETS = {
  "dyslexia": {"label": "Dyslexia", "settings": {"readable_font": true, "text_scale": 110, "line_height": 1.6, "letter_spacing_em": 0.02, "bold": false, "focus_mode": true, "safe_motion": true}},
  "adhd_focus": {"label": "ADHD / Focus", "settings": {"focus_mode": true, "safe_motion": true, "simplified": true, "reading_guide": true, "text_scale": 105, "line_height": 1.5, "letter_spacing_em": 0.01}},
  "vision_impaired": {"label": "Vision Impaired", "settings": {"high_contrast": true, "bold": true, "text_scale": 150, "line_height": 1.6, "letter_spacing_em": 0.02, "large_cursor": true, "focus_outline": true}},
  "seizure_safe": {"label": "Seizure Safe", "settings": {"safe_motion": true, "saturation": 20, "high_contrast": false, "focus_mode": true, "text_scale": 100, "line_height": 1.5, "letter_spacing_em": 0.01}},
  "achromatopsia": {"label": "Achromatopsia", "settings": {"colorblind_palette": "achromatopsia", "light_theme": true, "high_contrast": true, "bold": true, "text_scale": 110, "line_height": 1.6, "letter_spacing_em": 0.02}}
};
/* Letter-spacing slider bounds (em). Default 0.02em is moderate on
   purpose: spacing pulled too wide breaks letter grouping for
   dyslexic readers. The slider goes down as well as up, cap 0.12em. */
const HIVEMIND_SPACING = {"min": -0.02, "max": 0.12, "default": 0.02, "step": 0.01};
const HIVEMIND_TEXT_SCALE = {"min": 80, "max": 200, "default": 100, "step": 5};
