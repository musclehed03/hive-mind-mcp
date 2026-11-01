/* Hive-Mind GUI logic. Plain JS, no build step, no dependencies.
   Settings persist in localStorage. On first load with no saved
   settings, the OS prefers-reduced-motion / prefers-contrast choices
   are respected. Graph rendering is chunked with
   requestAnimationFrame so a large graph never blocks the page
   (lazy loading: data is fetched once, nodes render in batches). */
(function () {
  "use strict";
  var STORAGE_KEY = "hivemind-settings-v1";
  var SAMPLE_DATA = {
    live: false,
    nodes: [
      {id: "sample-1", label: "Shop opens at 9am on Saturdays", text: "Shop opens at 9am on Saturdays", domain: "general", shape: "circle", created_at: "2026-10-27T00:00:00Z", temporal_bucket: "recent_0_3m", source: "sample", entities: ["Shop"], provenance: {}, origin: "text · sonja"},
      {id: "sample-2", label: "Shop sells fresh bread", text: "Shop sells fresh bread", domain: "cooking", shape: "square", created_at: "2026-10-27T00:00:00Z", temporal_bucket: "recent_0_3m", source: "sample", entities: ["Shop"], provenance: {}, origin: "clipper · example.com"},
      {id: "sample-3", label: "Code the server in Python", text: "Code the server in Python", domain: "coding", shape: "triangle", created_at: "2026-10-27T00:00:00Z", temporal_bucket: "recent_0_3m", source: "sample", entities: [], provenance: {}, origin: "verified by muse-spark-1.3"}
    ],
    edges: [{from: "sample-1", to: "sample-2", kind: "shared-entity", line_style: "solid", label: "Shop"}],
    changelog: []
  };
  var DEFAULTS = {
    focus_mode: false, safe_motion: false, readable_font: false,
    high_contrast: false, light_theme: false, simplified: false,
    bold: false, underline_links: false, focus_outline: false,
    reading_guide: false, large_cursor: false,
    colorblind_palette: "default", text_scale: 100, line_height: 1.5,
    letter_spacing_em: 0.02, saturation: 100,
    metaphor: "nebula", graph_density: "balanced",
    snapshot_schedule: "7d", backup_destination: "supabase",
    token_budget: 200, reading_level: "plain", microbot_mode: "simple",
    palette_choice: "posh", sound: false, notifications: false,
    tooltips_enabled: true, origin_colours: {},
    active_profile: ""
  };
  /* Accessibility keys vs. everything else: "Reset accessibility
     settings" and applying/toggling a profile must only ever touch
     the accessibility keys. Regular Settings (graph, snapshot,
     token budget, sound, notifications, tooltips, origin colours)
     survive a reset and survive profile changes. tooltips_enabled
     and origin_colours are Regular Settings, so they are
     deliberately NOT in this list. */
  var ACCESSIBILITY_KEYS = [
    "focus_mode", "safe_motion", "readable_font", "high_contrast",
    "light_theme", "simplified", "bold", "underline_links",
    "focus_outline", "reading_guide", "large_cursor",
    "colorblind_palette", "text_scale", "line_height",
    "letter_spacing_em", "saturation", "active_profile"
  ];
  function resetAccessibilityState() {
    var kept = {};
    Object.keys(DEFAULTS).forEach(function (key) {
      if (ACCESSIBILITY_KEYS.indexOf(key) === -1) kept[key] = state[key];
    });
    state = Object.assign({}, DEFAULTS, kept);
    state.active_profile = "";
  }
  var state = loadSettings();

  function loadSettings() {
    try {
      var saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
      if (saved && typeof saved === "object") return Object.assign({}, DEFAULTS, saved);
    } catch (e) { /* corrupted storage: fall through to defaults */ }
    var fresh = Object.assign({}, DEFAULTS);
    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) fresh.safe_motion = true;
    if (window.matchMedia && window.matchMedia("(prefers-contrast: more)").matches) fresh.high_contrast = true;
    return fresh;
  }
  function saveSettings() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); } catch (e) { /* storage full/blocked: settings still apply this session */ }
  }
  function clamp(value, min, max) { return Math.min(max, Math.max(min, value)); }

  function applySettings() {
    var root = document.documentElement;
    var body = document.body;
    var palette = (window.HIVEMIND_PALETTES || {})[state.colorblind_palette] || (window.HIVEMIND_PALETTES || {}).default;
    if (palette) {
      root.style.setProperty("--bg", palette.background);
      root.style.setProperty("--text", palette.text);
      root.style.setProperty("--accent", palette.accent);
      root.style.setProperty("--border", palette.border);
      root.style.setProperty("--node", palette.node);
      root.style.setProperty("--edge", palette.edge);
      /* --metal exists only on the Variant A default palette; other
         palettes fall back to their border colour, so the 1px header
         pinstripe never introduces a colour a palette did not pick. */
      root.style.setProperty("--metal", palette.metal || palette.border);
    }
    root.style.setProperty("--font-scale", (state.text_scale / 100).toFixed(2));
    root.style.setProperty("--line-height", String(state.line_height));
    var spacing = clamp(Number(state.letter_spacing_em), -0.02, 0.12);
    root.style.setProperty("--letter-spacing", spacing.toFixed(2) + "em");
    root.style.setProperty("--saturation", clamp(Number(state.saturation), 0, 100) + "%");
    body.classList.toggle("focus-mode", !!state.focus_mode);
    body.classList.toggle("safe-motion", !!state.safe_motion);
    body.classList.toggle("readable-font", !!state.readable_font);
    body.classList.toggle("high-contrast", !!state.high_contrast);
    body.classList.toggle("light-theme", !!state.light_theme);
    body.classList.toggle("simplified", !!state.simplified);
    body.classList.toggle("bold-text", !!state.bold);
    body.classList.toggle("underline-links", !!state.underline_links);
    body.classList.toggle("strong-focus", !!state.focus_outline);
    body.classList.toggle("reading-guide", !!state.reading_guide);
    body.classList.toggle("large-cursor", !!state.large_cursor);
    body.classList.toggle("achromatopsia", state.colorblind_palette === "achromatopsia");
    syncControls();
    saveSettings();
  }

  function setToggle(id, value) {
    var el = document.getElementById(id);
    if (el) el.setAttribute("aria-pressed", value ? "true" : "false");
  }
  // Do not rewrite a range slider's value while the user is dragging
  // it: syncControls() runs on every applySettings(), and resetting
  // .value mid-drag can swallow the drag in some browsers. Labels
  // below always update; only the focused slider's own value is left
  // alone until it loses focus.
  function setRangeValue(el, value) {
    if (!el) return;
    if (document.activeElement !== el) el.value = value;
  }
  // Range inputs fire both 'input' (while dragging) and 'change'
  // (when the drag/track click settles). Listen to both so a value
  // change is never lost if one of the two is swallowed.
  function bindRange(el, onInput) {
    if (!el) return;
    el.addEventListener("input", onInput);
    el.addEventListener("change", onInput);
  }
  function syncControls() {
    setToggle("toggle-focus", state.focus_mode);
    setToggle("toggle-motion", state.safe_motion);
    setToggle("toggle-font", state.readable_font);
    setToggle("toggle-contrast", state.high_contrast);
    setToggle("toggle-light", state.light_theme);
    setToggle("toggle-simplified", state.simplified);
    setToggle("toggle-bold", state.bold);
    setToggle("toggle-underline", state.underline_links);
    setToggle("toggle-focus-outline", state.focus_outline);
    setToggle("toggle-guide", state.reading_guide);
    setToggle("toggle-cursor", state.large_cursor);
    var palette = document.getElementById("palette-select");
    if (palette) palette.value = state.colorblind_palette;
    var ts = document.getElementById("text-size");
    setRangeValue(ts, state.text_scale);
    var tsv = document.getElementById("text-size-value");
    if (tsv) tsv.textContent = state.text_scale + "%";
    var ls = document.getElementById("line-spacing");
    setRangeValue(ls, state.line_height);
    var lsv = document.getElementById("line-spacing-value");
    if (lsv) lsv.textContent = String(state.line_height);
    var lsp = document.getElementById("letter-spacing");
    setRangeValue(lsp, state.letter_spacing_em);
    var lspv = document.getElementById("letter-spacing-value");
    if (lspv) lspv.textContent = Number(state.letter_spacing_em).toFixed(2) + "em";
    var sat = document.getElementById("saturation");
    setRangeValue(sat, state.saturation);
    var satv = document.getElementById("saturation-value");
    if (satv) satv.textContent = state.saturation + "%";
    document.querySelectorAll(".profile-button").forEach(function (btn) {
      btn.setAttribute("aria-pressed", state.active_profile === btn.dataset.profile ? "true" : "false");
    });
    var metaphor = document.getElementById("metaphor-select");
    if (metaphor) metaphor.value = state.metaphor;
    var density = document.getElementById("graph-density");
    if (density) density.value = state.graph_density;
    var sched = document.getElementById("snapshot-schedule");
    if (sched) sched.value = state.snapshot_schedule;
    var dest = document.getElementById("backup-destination");
    if (dest) dest.value = state.backup_destination;
    var budget = document.getElementById("token-budget");
    setRangeValue(budget, state.token_budget);
    var bv = document.getElementById("token-budget-value");
    if (bv) bv.textContent = String(state.token_budget);
    var rl = document.getElementById("reading-level");
    if (rl) rl.value = state.reading_level;
    var mm = document.getElementById("microbot-mode");
    if (mm) mm.value = state.microbot_mode;
    var pc = document.getElementById("palette-choice");
    if (pc) pc.value = state.palette_choice;
    var sound = document.getElementById("toggle-sound");
    if (sound) { sound.setAttribute("aria-pressed", state.sound ? "true" : "false"); sound.textContent = "Sound: " + (state.sound ? "on" : "off"); }
    var notif = document.getElementById("toggle-notifications");
    if (notif) { notif.setAttribute("aria-pressed", state.notifications ? "true" : "false"); notif.textContent = "Notifications: " + (state.notifications ? "on" : "off"); }
    var tt = document.getElementById("toggle-tooltips");
    if (tt) { tt.setAttribute("aria-pressed", state.tooltips_enabled ? "true" : "false"); tt.textContent = "Tooltips: " + (state.tooltips_enabled ? "on" : "off"); }
    var slider = document.getElementById("microbot-slider-button");
    if (slider) slider.textContent = "Micro-bot: " + (state.microbot_mode === "pro" ? "Pro Mode" : "Simple Mode");
  }

  function applyProfile(name) {
    var presets = window.HIVEMIND_PRESETS || {};
    if (state.active_profile === name) {
      resetAccessibilityState();
    } else if (presets[name]) {
      resetAccessibilityState();
      state = Object.assign({}, state, presets[name].settings, {active_profile: name});
    }
    applySettings();
    renderGraph();
  }

  /* Fast custom tooltips (standing SOP: ~500ms, snap up, no slow
     native title delay). One shared element, styled with the same
     CSS variables as the page so it follows every palette, including
     grayscale and high contrast. No fade-in animation: the tip
     appears the instant the delay elapses. Shows after 500ms on
     hover AND on keyboard focus (touch: a tap focuses the control,
     so the tip shows there too). Hides at once on mouseleave, blur,
     Escape, scroll, and resize. Content comes from data-tooltip;
     there are no title attributes left, so the slow native tooltip
     can never double-show, on or off. When tooltips are off
     (Regular Settings), nothing ever shows. */
  var TOOLTIP_DELAY_MS = 500;
  var tooltipTimer = null;
  var tooltipTarget = null;
  function tooltipElement() {
    return document.getElementById("hivemind-tooltip");
  }
  function hideTooltip() {
    if (tooltipTimer) { clearTimeout(tooltipTimer); tooltipTimer = null; }
    tooltipTarget = null;
    var tip = tooltipElement();
    if (tip) tip.hidden = true;
  }
  function positionTooltip(target) {
    var tip = tooltipElement();
    if (!tip) return;
    var rect = target.getBoundingClientRect();
    var gap = 8;
    var tipWidth = tip.offsetWidth, tipHeight = tip.offsetHeight;
    var maxLeft = Math.max(8, window.innerWidth - tipWidth - gap);
    var left = Math.min(Math.max(8, rect.left + (rect.width - tipWidth) / 2), maxLeft);
    var top = rect.top - tipHeight - gap;
    if (top < 8) top = rect.bottom + gap;
    if (top + tipHeight > window.innerHeight - gap) {
      top = Math.max(8, window.innerHeight - tipHeight - gap);
    }
    tip.style.left = left + "px";
    tip.style.top = top + "px";
  }
  function showTooltip(target) {
    if (!state.tooltips_enabled) return;
    var text = target.getAttribute("data-tooltip");
    if (!text) return;
    var tip = tooltipElement();
    if (!tip) return;
    tooltipTarget = target;
    tip.textContent = text;
    tip.hidden = false;
    /* Measure while invisible so the first paint is already in
       the right place: no jump, no flash in the wrong spot. */
    tip.style.visibility = "hidden";
    positionTooltip(target);
    tip.style.visibility = "";
  }
  function scheduleTooltip(target) {
    hideTooltip();
    if (!state.tooltips_enabled) return;
    tooltipTimer = setTimeout(function () {
      tooltipTimer = null;
      showTooltip(target);
    }, TOOLTIP_DELAY_MS);
  }
  /* One element's tooltip wiring, guarded so a second bind is a
     no-op: the static page binds once at startup, and the
     origin-colour rows added later (Block 17) bind each new
     colour input as it is created. Same delay, same hiding
     rules, no duplicates. */
  function bindTooltipElement(el) {
    if (!el || el.__hivemindTooltipBound) return;
    el.__hivemindTooltipBound = true;
    el.addEventListener("mouseenter", function () { scheduleTooltip(el); });
    el.addEventListener("mouseleave", hideTooltip);
    el.addEventListener("focus", function () { scheduleTooltip(el); });
    el.addEventListener("blur", hideTooltip);
    /* A select's own dropdown opens on click; hide the tip so it
       never sits on top of the open list. Buttons and sliders
       keep the tip until the pointer/keyboard leaves them. */
    if (el.tagName === "SELECT") el.addEventListener("click", hideTooltip);
  }
  function bindTooltips() {
    document.querySelectorAll("[data-tooltip]").forEach(bindTooltipElement);
    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape") hideTooltip();
    });
    window.addEventListener("scroll", hideTooltip, true);
    window.addEventListener("resize", hideTooltip);
  }

  function bindControls() {
    var toggles = [
      ["toggle-focus", "focus_mode"], ["toggle-motion", "safe_motion"],
      ["toggle-font", "readable_font"], ["toggle-contrast", "high_contrast"],
      ["toggle-light", "light_theme"], ["toggle-simplified", "simplified"],
      ["toggle-bold", "bold"], ["toggle-underline", "underline_links"],
      ["toggle-focus-outline", "focus_outline"], ["toggle-guide", "reading_guide"],
      ["toggle-cursor", "large_cursor"]
    ];
    toggles.forEach(function (pair) {
      var el = document.getElementById(pair[0]);
      if (el) el.addEventListener("click", function () {
        state[pair[1]] = !state[pair[1]]; state.active_profile = ""; applySettings();
      });
    });
    document.querySelectorAll(".profile-button").forEach(function (btn) {
      btn.addEventListener("click", function () { applyProfile(btn.dataset.profile); });
    });
    var palette = document.getElementById("palette-select");
    if (palette) palette.addEventListener("change", function () { state.colorblind_palette = palette.value; state.active_profile = ""; applySettings(); renderGraph(); });
    var ts = document.getElementById("text-size");
    bindRange(ts, function () { state.text_scale = clamp(Number(ts.value), 80, 200); state.active_profile = ""; applySettings(); });
    var ls = document.getElementById("line-spacing");
    bindRange(ls, function () { state.line_height = clamp(Number(ls.value), 1.0, 2.0); state.active_profile = ""; applySettings(); });
    var lsp = document.getElementById("letter-spacing");
    bindRange(lsp, function () { state.letter_spacing_em = clamp(Number(lsp.value), -0.02, 0.12); state.active_profile = ""; applySettings(); });
    var sat = document.getElementById("saturation");
    bindRange(sat, function () { state.saturation = clamp(Number(sat.value), 0, 100); state.active_profile = ""; applySettings(); });
    var reset = document.getElementById("reset-settings");
    /* Reset covers accessibility keys only. Regular Settings —
       including the tooltips on/off switch — survive it. The saved
       settings are rewritten by applySettings(), not wiped. */
    if (reset) reset.addEventListener("click", function () { resetAccessibilityState(); applySettings(); renderGraph(); });
    var metaphor = document.getElementById("metaphor-select");
    if (metaphor) metaphor.addEventListener("change", function () { state.metaphor = metaphor.value; applySettings(); renderGraph(); });
    var density = document.getElementById("graph-density");
    if (density) density.addEventListener("change", function () { state.graph_density = density.value; applySettings(); renderGraph(); });
    var sched = document.getElementById("snapshot-schedule");
    if (sched) sched.addEventListener("change", function () { state.snapshot_schedule = sched.value; applySettings(); });
    var dest = document.getElementById("backup-destination");
    if (dest) dest.addEventListener("change", function () { state.backup_destination = dest.value; applySettings(); });
    var budget = document.getElementById("token-budget");
    bindRange(budget, function () { state.token_budget = clamp(Number(budget.value), 50, 1000); applySettings(); });
    var rl = document.getElementById("reading-level");
    if (rl) rl.addEventListener("change", function () { state.reading_level = rl.value; applySettings(); });
    var mm = document.getElementById("microbot-mode");
    if (mm) mm.addEventListener("change", function () { state.microbot_mode = mm.value; applySettings(); });
    var pc = document.getElementById("palette-choice");
    if (pc) pc.addEventListener("change", function () { state.palette_choice = pc.value; applySettings(); });
    var sound = document.getElementById("toggle-sound");
    if (sound) sound.addEventListener("click", function () { state.sound = !state.sound; applySettings(); });
    var notif = document.getElementById("toggle-notifications");
    if (notif) notif.addEventListener("click", function () { state.notifications = !state.notifications; applySettings(); });
    var tt = document.getElementById("toggle-tooltips");
    if (tt) tt.addEventListener("click", function () {
      state.tooltips_enabled = !state.tooltips_enabled;
      applySettings();
      if (!state.tooltips_enabled) hideTooltip();
    });
    /* Origin colours (Block 17): back to palette-derived
       defaults. Only origin_colours is cleared; every other
       setting stays. Rows rebuild on the next render. */
    var resetOrigins = document.getElementById("reset-origin-colours");
    if (resetOrigins) resetOrigins.addEventListener("click", function () {
      state.origin_colours = {};
      lastOriginRowKey = "";
      saveSettings();
      renderGraph();
    });
    var slider = document.getElementById("microbot-slider-button");
    if (slider) slider.addEventListener("click", function () {
      state.microbot_mode = state.microbot_mode === "pro" ? "simple" : "pro"; applySettings();
    });
    var refresh = document.getElementById("refresh-button");
    if (refresh) refresh.addEventListener("click", loadData);
    /* Integrations copy buttons (Block 16): each copies plain
       text only — a command, an address, or the Codex setup
       snippet. Never a key: no key is ever on this page. */
    document.querySelectorAll("[data-copy]").forEach(function (button) {
      button.addEventListener("click", function () { copyIntegration(button); });
    });
    var aloud = document.getElementById("read-aloud-button");
    if (aloud) aloud.addEventListener("click", readAloud);
    document.addEventListener("mousemove", function (ev) {
      var guide = document.getElementById("reading-guide");
      if (guide && state.reading_guide) guide.style.top = (ev.clientY - 16) + "px";
    });
  }

  function readAloud() {
    var list = document.getElementById("node-list");
    var text = list ? list.textContent : "";
    if ("speechSynthesis" in window && text.trim()) {
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(new SpeechSynthesisUtterance(text.slice(0, 2000)));
    } else {
      var status = document.getElementById("graph-status");
      if (status) status.textContent = "Read aloud is not available in this browser; the full text list is above.";
    }
  }

  var graphData = SAMPLE_DATA;
  var positions = {};

  /* Layout derives centre and radius from the canvas's real
     displayed size (Block 13): a fixed centre used to sit
     left-of-centre in the stretched box, and labels ran off the
     right edge. The shared helper lives in stage.js (loaded
     first); the inline fallback below uses the same formula so a
     missing helper can never strand the graph unlaid-out. */
  function layout(nodes, width, height) {
    var api = window.HIVEMIND_GRAPH || null;
    if (api && api.layoutNodes && width && height) {
      positions = api.layoutNodes(nodes, width, height);
      return;
    }
    positions = {};
    var cx = (width || 0) / 2, cy = (height || 0) / 2;
    var radius = Math.max(40, Math.min(width || 0, height || 0) / 2 - 56);
    nodes.forEach(function (node, i) {
      var angle = (2 * Math.PI * i) / Math.max(1, nodes.length);
      positions[node.id] = {x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle)};
    });
  }
  /* Size the canvas backing store to its displayed size, in CSS
     pixels, at the device pixel ratio (capped at 2, so a HiDPI
     screen stays sharp without a 3x/4x backing store). Drawing
     then happens in CSS pixels, so the picture fills the box it
     is actually shown in instead of being stretched from a
     smaller fixed size. */
  function fitCanvas(canvas) {
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var rect = canvas.getBoundingClientRect();
    var width = Math.max(1, rect.width || canvas.clientWidth || 0);
    var height = Math.max(1, rect.height || canvas.clientHeight || 0);
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    return {width: width, height: height, dpr: dpr};
  }
  var renderSeq = 0;
  function drawShape(ctx, shape, x, y, size, fill, stroke) {
    ctx.beginPath();
    if (shape === "square") ctx.rect(x - size, y - size, size * 2, size * 2);
    else if (shape === "triangle") { ctx.moveTo(x, y - size); ctx.lineTo(x + size, y + size); ctx.lineTo(x - size, y + size); ctx.closePath(); }
    else ctx.arc(x, y, size, 0, 2 * Math.PI);
    ctx.fillStyle = fill; ctx.fill();
    ctx.lineWidth = 2; ctx.strokeStyle = stroke; ctx.stroke();
  }
  /* Stroke-only outline of a shape, for the "double" origin ring
     (Block 17): a second outline a few pixels out from the first,
     same colour, same shape — no fill, so it never covers the
     node or its label. */
  function drawShapeOutline(ctx, shape, x, y, size, stroke) {
    ctx.beginPath();
    if (shape === "square") ctx.rect(x - size, y - size, size * 2, size * 2);
    else if (shape === "triangle") { ctx.moveTo(x, y - size); ctx.lineTo(x + size, y + size); ctx.lineTo(x - size, y + size); ctx.closePath(); }
    else ctx.arc(x, y, size, 0, 2 * Math.PI);
    ctx.lineWidth = 2; ctx.strokeStyle = stroke; ctx.stroke();
  }

  /* Origin colours + legend (Block 17). An origin is a plain
     label — which model, client, or coder made the memory — and
     the map carries it two ways at once: a ring colour the user
     can change, and a ring pattern (solid / dashed / dotted /
     double) fixed by first-seen order. Colour is never the only
     carrier: the pattern, the HTML legend, and the text list
     below the graph all name the origin in words. The pattern
     logic lives in stage.js and never reads a colour variable,
     so the achromatopsia greyscale filter cannot take the
     meaning away. */
  function originApi() { return window.HIVEMIND_ORIGINS || null; }
  function originColoursMap() {
    var saved = state.origin_colours;
    if (!saved || typeof saved !== "object" || Array.isArray(saved)) return {};
    var out = {};
    Object.keys(saved).forEach(function (key) {
      if (/^#[0-9a-fA-F]{6}$/.test(String(saved[key]))) out[key] = String(saved[key]);
    });
    return out;
  }
  function originOrderOf(nodes) {
    var api = originApi();
    var order = [];
    (nodes || []).forEach(function (node) {
      var origin = api ? api.originOf(node) : (node.origin || "unknown origin");
      if (order.indexOf(origin) === -1) order.push(origin);
    });
    return order;
  }
  function originColour(origin, palette, order) {
    var saved = originColoursMap()[origin];
    if (saved) return saved;
    var api = originApi();
    if (api) return api.originColourFor(order.indexOf(origin), palette);
    return (palette && palette.edge) || "#547c6d";
  }
  function originPatternFor(origin, order) {
    var api = originApi();
    return api ? api.originPattern(order.indexOf(origin)) : "solid";
  }
  function renderOriginLegend(palette, order) {
    var ul = document.getElementById("origin-legend");
    if (!ul) return;
    var api = originApi();
    var entries = api ? api.legendEntries(graphData.nodes) : order.map(function (o, i) {
      return {origin: o, count: 0, pattern: "solid", patternIndex: i};
    });
    ul.innerHTML = "";
    entries.forEach(function (entry) {
      var li = document.createElement("li");
      var swatch = document.createElement("span");
      swatch.className = "origin-swatch origin-swatch-" + entry.pattern;
      swatch.style.borderColor = originColour(entry.origin, palette, order);
      if (entry.pattern === "double") swatch.style.outlineColor = originColour(entry.origin, palette, order);
      swatch.setAttribute("aria-hidden", "true");
      li.appendChild(swatch);
      li.appendChild(document.createTextNode(
        " " + entry.origin + " — " + entry.pattern + " ring — " + entry.count +
        (entry.count === 1 ? " memory" : " memories")));
      ul.appendChild(li);
    });
  }
  /* One row per origin present in the loaded data: the label, a
     colour picker, and a plain-words tooltip. Rows rebuild only
     when the origin list itself changes, so dragging a picker
     never rebuilds the control under the pointer. Changing a
     colour saves it in the same settings key as everything else
     and redraws the graph; the accessibility reset does not
     touch origin_colours (it is not in ACCESSIBILITY_KEYS). */
  var lastOriginRowKey = "";
  function renderOriginColourRows(palette, order) {
    var container = document.getElementById("origin-colours");
    if (!container) return;
    var key = JSON.stringify(order);
    if (key === lastOriginRowKey && container.childNodes.length) return;
    lastOriginRowKey = key;
    container.innerHTML = "";
    if (!order.length) {
      var empty = document.createElement("p");
      empty.textContent = "No memories yet — origin colours appear here once the first memory is stored.";
      container.appendChild(empty);
      return;
    }
    order.forEach(function (origin) {
      var row = document.createElement("div");
      row.className = "origin-colour-row";
      var name = document.createElement("span");
      name.className = "origin-colour-label";
      name.textContent = origin;
      var input = document.createElement("input");
      input.type = "color";
      input.value = originColour(origin, palette, order);
      input.setAttribute("aria-label", "Ring colour for origin " + origin);
      input.setAttribute("data-tooltip",
        "Choose the ring colour for memories from " + origin +
        ". The ring pattern and the Origins list still tell origins apart without colour.");
      input.setAttribute("data-origin", origin);
      input.addEventListener("input", function () { setOriginColour(origin, input.value); });
      input.addEventListener("change", function () { setOriginColour(origin, input.value); });
      bindTooltipElement(input);
      row.appendChild(name);
      row.appendChild(input);
      container.appendChild(row);
    });
  }
  function setOriginColour(origin, value) {
    if (!/^#[0-9a-fA-F]{6}$/.test(String(value))) return;
    var map = originColoursMap();
    map[origin] = String(value);
    state.origin_colours = map;
    saveSettings();
    renderGraph();
  }
  function renderGraph() {
    var canvas = document.getElementById("graph-canvas");
    var svg = document.getElementById("graph-svg");
    var list = document.getElementById("node-list");
    var status = document.getElementById("graph-status");
    if (!canvas || !list) return;
    var seq = ++renderSeq;
    /* Growth stage (Block 10): derived from the live node list —
       total count picks the stage, checked facts brighten it. The
       label is the source of truth; canvas density/scale are
       decorative echoes of the same numbers. */
    var stageApi = window.HIVEMIND_STAGE || null;
    var verifiedCount = stageApi ? stageApi.countVerified(graphData.nodes) : 0;
    var stage = stageApi ? stageApi.stageFor(graphData.nodes.length, verifiedCount) : null;
    var stageEl = document.getElementById("growth-stage");
    if (stageEl && stage) {
      var nextText = stage.nextMin === null
        ? "Full-grown."
        : "Next: " + stage.nextName + " at " + stage.nextMin + " memories.";
      stageEl.textContent = "Growth stage: " + stage.name + " — " + stage.description +
        " (" + stage.count + " memories, " + stage.verifiedCount + " checked.) " + nextText;
    }
    /* Origins (Block 17): the palette the page is actually
       rendering with, the first-seen origin order, the HTML
       legend, and the Regular Settings colour rows. These render
       for every metaphor view, not only the canvas one. */
    var originStyles = getComputedStyle(document.body);
    var originPalette = {
      accent: originStyles.getPropertyValue("--accent").trim(),
      edge: originStyles.getPropertyValue("--edge").trim(),
      text: originStyles.getPropertyValue("--text").trim(),
      bg: originStyles.getPropertyValue("--bg").trim(),
      metal: originStyles.getPropertyValue("--metal").trim(),
      border: originStyles.getPropertyValue("--border").trim()
    };
    var originOrder = originOrderOf(graphData.nodes);
    renderOriginLegend(originPalette, originOrder);
    renderOriginColourRows(originPalette, originOrder);
    if (state.metaphor === "nebula") {
      canvas.style.display = "block"; if (svg) svg.style.display = "none";
      var dims = fitCanvas(canvas);
      var ctx = canvas.getContext("2d");
      ctx.setTransform(dims.dpr, 0, 0, dims.dpr, 0, 0);
      /* Canvas-only duplicate grouping (Block 14): memories that
         restate the same fact draw as ONE node labelled with the
         meaningful keyword plus " ×N". Stage counts, EXP, the
         status line, and the text list below still use every
         memory individually — grouping changes only the picture,
         so a fact stored twice never earns two dots. */
      var graphApi = window.HIVEMIND_GRAPH || null;
      var displayNodes = (graphApi && graphApi.groupGraphNodes)
        ? graphApi.groupGraphNodes(graphData.nodes)
        : graphData.nodes.map(function (n) {
            return {id: n.id, representative: n, members: [n], count: 1,
                    verified: stageApi ? stageApi.isVerified(n) : false,
                    label: n.label || n.text || ""};
          });
      layout(displayNodes, dims.width, dims.height);
      /* Read colours from body, NOT from documentElement. Palette
         variables are set inline on :root, but body class rules
         (high-contrast, light theme) set the same variables on body
         and win for everything the page actually paints, because an
         element's own value beats an inherited one. The canvas is
         transparent, so its background IS the body's background; if
         the canvas read :root it could draw black text on a black
         page (the achromatopsia blackout). Reading body makes the
         canvas use exactly the colours the page renders with, in
         every palette/toggle combination. The background is also
         painted explicitly below, so the canvas never depends on
         what shows through it. */
      var styles = getComputedStyle(document.body);
      ctx.clearRect(0, 0, dims.width, dims.height);
      ctx.fillStyle = styles.getPropertyValue("--bg").trim() || "#080609";
      ctx.fillRect(0, 0, dims.width, dims.height);
      /* Faint dust behind the nodes: deterministic positions from a
         hash of the index (no Math.random, so the picture is stable
         across redraws), count and brightness from the stage. Dust
         is decoration only — the stage label carries the meaning. */
      var dustCount = stage ? stage.dust : 12;
      var dustAlpha = 0.10 + 0.20 * (stage ? stage.verifiedFraction : 0);
      ctx.save();
      ctx.globalAlpha = dustAlpha;
      ctx.fillStyle = styles.getPropertyValue("--text").trim() || "#ddd3d7";
      for (var d = 0; d < dustCount; d++) {
        var dust = graphApi && graphApi.dustPoint
          ? graphApi.dustPoint(d, dims.width, dims.height)
          : {x: 0, y: 0};
        ctx.beginPath();
        ctx.arc(dust.x, dust.y, 1.5, 0, 2 * Math.PI);
        ctx.fill();
      }
      ctx.restore();
      // Chunked rendering: 50 nodes per animation frame, never blocking.
      var nodes = displayNodes.slice();
      var nodeSize = 14 * (stage ? stage.scale : 1);
      var placedLabels = [];
      var i = 0;
      (function drawChunk() {
        if (seq !== renderSeq) return; /* a newer render superseded this one */
        var end = Math.min(nodes.length, i + 50);
        for (; i < end; i++) {
          var group = nodes[i];
          var rep = group.representative || group;
          var pos = positions[group.id];
          /* Origin ring (Block 17): the group's first member's
             origin colour + pattern. Node fill stays the palette
             node colour, so palette changes still work; the ring
             carries the origin. The dash is set for the shape
             stroke only and cleared right after, so edges and the
             verified ring below are never dashed by accident. */
          var api = originApi();
          var groupOriginList = api ? api.groupOrigins(group) : [rep.origin || "unknown origin"];
          var firstOrigin = groupOriginList[0];
          var ringColour = originColour(firstOrigin, originPalette, originOrder);
          var ringPattern = originPatternFor(firstOrigin, originOrder);
          ctx.setLineDash(api ? api.patternDash(ringPattern) : []);
          drawShape(ctx, rep.shape || "circle", pos.x, pos.y, nodeSize,
            styles.getPropertyValue("--node").trim() || "#120d11",
            ringColour);
          ctx.setLineDash([]);
          if (ringPattern === "double") {
            drawShapeOutline(ctx, rep.shape || "circle", pos.x, pos.y, nodeSize + 3, ringColour);
          }
          /* Checked facts get an extra ring: verified-ness is carried
             by shape (ring vs. no ring) and by the text list, never
             by colour alone. A group is checked when ANY member
             passed Cross-Hatch Verify. */
          if (group.verified) {
            ctx.beginPath();
            ctx.arc(pos.x, pos.y, nodeSize + 5, 0, 2 * Math.PI);
            ctx.lineWidth = 2;
            ctx.strokeStyle = styles.getPropertyValue("--edge").trim() || "#547c6d";
            ctx.stroke();
          }
          /* Keyword labels (Blocks 13-14): the meaningful keyword
             from the group label (with " ×N" for duplicates),
             side-aware, fitted to the canvas edge, and staggered
             vertically while it would overlap an earlier label.
             The full sentence stays in the text list below the
             graph. */
          ctx.fillStyle = styles.getPropertyValue("--text").trim() || "#ddd3d7";
          ctx.font = "12px sans-serif";
          ctx.textBaseline = "middle";
          if (graphApi && graphApi.placeLabel && group.label) {
            var geo = graphApi.labelGeometry(pos, dims.width, nodeSize);
            var placed = graphApi.placeLabel(geo, group.label, pos.y,
              function (t) { return ctx.measureText(t).width; },
              placedLabels, dims.width, dims.height);
            if (placed) {
              placedLabels.push(placed.box);
              ctx.textAlign = geo.textAlign;
              ctx.fillText(placed.text, placed.x, placed.y);
              ctx.textAlign = "left";
            }
          } else if (graphApi && graphApi.keywordLabel) {
            var keyword = graphApi.keywordLabel(rep.label || rep.text || "");
            if (keyword) {
              var geo2 = graphApi.labelGeometry(pos, dims.width, nodeSize);
              var room = geo2.textAlign === "right"
                ? geo2.x - 8
                : dims.width - 8 - geo2.x;
              if (room >= 24) {
                var fitted = graphApi.fitLabel(keyword, room, function (t) { return ctx.measureText(t).width; });
                if (fitted) {
                  ctx.textAlign = geo2.textAlign;
                  ctx.fillText(fitted, geo2.x, pos.y);
                  ctx.textAlign = "left";
                }
              }
            }
          }
        }
        if (i < nodes.length) requestAnimationFrame(drawChunk);
      })();
      /* Edges are drawn between groups, not individual duplicate
         memories: an edge inside one group vanishes, and identical
         group pairs draw once. */
      var displayEdges = (graphApi && graphApi.mapGroupEdges)
        ? graphApi.mapGroupEdges(graphData.edges, displayNodes)
        : graphData.edges;
      displayEdges.forEach(function (edge) {
        var a = positions[edge.from], b = positions[edge.to];
        if (!a || !b) return;
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y);
        ctx.setLineDash(edge.line_style === "dashed" ? [6, 4] : edge.line_style === "dotted" ? [2, 4] : []);
        ctx.strokeStyle = styles.getPropertyValue("--edge").trim() || "#547c6d";
        ctx.lineWidth = 2; ctx.stroke(); ctx.setLineDash([]);
      });
    } else {
      canvas.style.display = "none"; if (svg) svg.style.display = "block";
      var group = document.getElementById("svg-nodes");
      if (group) {
        group.innerHTML = "";
        var ns = "http://www.w3.org/2000/svg";
        graphData.nodes.forEach(function (node, idx) {
          var text = document.createElementNS(ns, "text");
          text.setAttribute("x", 20); text.setAttribute("y", 30 + idx * 24);
          text.setAttribute("fill", "currentColor");
          text.textContent = node.shape + " — " + node.label + " — " + (originApi() ? originApi().originOf(node) : (node.origin || "unknown origin"));
          group.appendChild(text);
        });
        var title = document.createElementNS(ns, "title");
        title.textContent = state.metaphor + " view: " + graphData.nodes.length + " memories as text";
        svg.insertBefore(title, svg.firstChild);
      }
    }
    list.innerHTML = "";
    graphData.nodes.forEach(function (node) {
      var li = document.createElement("li");
      var nodeOrigin = originApi() ? originApi().originOf(node) : (node.origin || "unknown origin");
      li.textContent = node.shape + ", " + node.domain + ", " + node.temporal_bucket + ", origin " + nodeOrigin + ": " + node.text;
      li.setAttribute("aria-label", "Memory, shape " + node.shape + ", domain " + node.domain + ", origin " + nodeOrigin + ": " + node.text);
      list.appendChild(li);
    });
    var toast = document.getElementById("diff-toast");
    if (toast && graphData.changelog && graphData.changelog.length) {
      toast.textContent = graphData.changelog[0].diff;
    }
    if (status) status.textContent = (graphData.live ? "Live data" : "Sample data") + ": " + graphData.nodes.length + " memories, " + graphData.edges.length + " relationships.";
    var meter = document.getElementById("token-meter");
    if (meter && graphData.stats) {
      meter.textContent = "Token Ekonomi Meter: " + graphData.stats.total + " memories stored.";
    }
  }

  function loadExp() {
    /* EXP totals (Block 11): read-only, fetched with the graph data
       and on Refresh. A static export has no server, so a failed
       fetch leaves the default "EXP: 0" text in place — never an
       error, never a retry loop. */
    fetch("/api/exp", {cache: "no-store"}).then(function (r) { return r.ok ? r.json() : Promise.reject(new Error("no EXP API")); })
      .then(function (data) {
        var el = document.getElementById("exp-meter");
        if (el) el.textContent = "EXP: " + data.total + " — " + data.events + " healthy actions (checked facts, settled mix-ups, backups). Points never cost money.";
      })
      .catch(function () { /* no server: keep the default text */ });
  }

  /* Integrations copy (Block 16): clipboard with a plain
     fallback. The button briefly says "Copied" (or "Copy
     failed") and returns to its old text after one one-shot
     delay. Only plain setup text is ever copied — a command,
     an address, or the Codex snippet. No key is ever on this
     page, so no key can ever be copied from it. */
  function fallbackCopy(text) {
    var area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    document.body.removeChild(area);
    return ok;
  }
  function copyIntegration(button) {
    var kind = button.getAttribute("data-copy");
    var text = "";
    if (kind === "stdio") {
      var stdioValue = document.getElementById("value-stdio");
      text = stdioValue ? stdioValue.textContent : "python -m app.mcp_server";
    } else if (kind === "sse") {
      var sseValue = document.getElementById("value-sse");
      text = sseValue ? sseValue.textContent : "http://127.0.0.1:8765/sse";
    } else if (kind === "config") {
      var snippet = document.getElementById("codex-config-snippet");
      text = snippet ? snippet.textContent : "";
    }
    var original = button.textContent;
    function report(ok) {
      button.textContent = ok ? "Copied" : "Copy failed";
      setTimeout(function () { button.textContent = original; }, 1000);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(
        function () { report(true); },
        function () { report(fallbackCopy(text)); });
    } else {
      report(fallbackCopy(text));
    }
  }

  function loadIntegrations() {
    /* Integrations status (Block 16): read-only facts from the
       server — never a key. A static export has no server, so a
       failed fetch leaves the honest static defaults in place:
       "Not connected" / "Fake (tests only)", never an error. */
    fetch("/api/integrations", {cache: "no-store"}).then(function (r) { return r.ok ? r.json() : Promise.reject(new Error("no integrations API")); })
      .then(function (data) {
        var classFor = (window.HIVEMIND_INTEGRATIONS || {}).statusClassFor;
        function setRow(valueId, statusId, valueText, statusWord) {
          var valueEl = document.getElementById(valueId);
          if (valueEl) valueEl.textContent = valueText;
          var statusEl = document.getElementById(statusId);
          if (statusEl) {
            statusEl.textContent = statusWord;
            var cls = classFor ? classFor(statusWord) : "status-off";
            statusEl.className = "integration-status " + cls;
          }
        }
        if (data.mcp_stdio) setRow("value-stdio", "status-stdio", data.mcp_stdio.command, data.mcp_stdio.status);
        if (data.mcp_sse) setRow("value-sse", "status-sse", data.mcp_sse.url, data.mcp_sse.status);
        if (data.model) {
          var modelText = data.model.base_url + " · " + data.model.model;
          if (!data.model.key_present && data.model.key_required) modelText += " · key missing";
          if (data.model.key_present) modelText += " · key set";
          setRow("value-model", "status-model", modelText, data.model.status);
        }
        if (data.supabase) {
          setRow("value-supabase", "status-supabase", data.supabase.bucket, data.supabase.status);
        }
        if (data.exp) {
          setRow("value-exp", "status-exp", data.exp.events + " healthy actions", "Local only");
        }
      })
      .catch(function () { /* no server: keep the static defaults */ });
  }

  function loadData() {
    loadExp();
    loadIntegrations();
    // Live data first: the GUI server's /api/memories endpoint reads
    // the real Store, so seeding the Store shows up on Refresh. Only
    // if there is no server (static export / file://) fall back to a
    // pre-exported data.json, and only then to the built-in sample
    // data. The status text stays honest via graphData.live, which
    // the live and exported payloads set to true and SAMPLE_DATA
    // leaves false.
    fetch("/api/memories", {cache: "no-store"}).then(function (r) { return r.ok ? r.json() : Promise.reject(new Error("no live API")); })
      .then(function (data) { graphData = data; renderGraph(); })
      .catch(function () {
        fetch("data.json").then(function (r) { return r.ok ? r.json() : Promise.reject(new Error("no data.json")); })
          .then(function (data) { graphData = data; renderGraph(); })
          .catch(function () { graphData = SAMPLE_DATA; renderGraph(); });
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    applySettings();
    bindControls();
    bindTooltips();
    /* Re-render on resize: the canvas is sized to its displayed
       size on every render, so a width change re-centres the
       graph instead of stretching the old picture. No polling:
       this fires only on actual resize events. */
    window.addEventListener("resize", function () { renderGraph(); });
    loadData();
  });
  // Exposed for tests/debugging in the browser console only.
  window.HIVEMIND_GUI = {applySettings: applySettings, getState: function () { return state; },
    showTooltip: showTooltip, hideTooltip: hideTooltip, tooltipDelayMs: TOOLTIP_DELAY_MS};
})();
