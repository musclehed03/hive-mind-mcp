/* Hive-Mind growth stages: the living nebula (Block 10).

   The nebula is procedural canvas art only — no image assets, no
   copied artwork. A stage is derived from the memories the server
   already returns: the total count picks the stage, and the share
   of checked facts (a memory whose provenance carries a non-empty
   `verified_by`, i.e. it passed Cross-Hatch Verify) brightens the
   picture within the stage. Stage meaning is always carried in
   text too (the growth-stage label next to the graph, plus the
   text node list), never by colour alone, and the density/shape
   changes keep working in pure grayscale.

   Thresholds (defaults, in one place so they can be tuned):
     0–9 memories    = Nebula
     10–29 memories  = Protostar
     30–74 memories  = Star
     75+ memories    = Radiant Sun
   "Dust" is the count of faint background points drawn behind the
   nodes; "scale" grows the node size. Both are decorative: the
   label text is the source of truth for the stage. */
(function () {
  "use strict";
  var STAGES = [
    {name: "Nebula", minCount: 0,
     description: "A young cloud: a few memories, still gathering.",
     dust: 12, scale: 1.0},
    {name: "Protostar", minCount: 10,
     description: "The cloud is pulling together: memories are clustering.",
     dust: 30, scale: 1.15},
    {name: "Star", minCount: 30,
     description: "A shining star: enough memories to light the picture.",
     dust: 60, scale: 1.3},
    {name: "Radiant Sun", minCount: 75,
     description: "A radiant sun: a large, bright, well-checked memory sky.",
     dust: 100, scale: 1.5}
  ];

  function isVerified(node) {
    var prov = node && node.provenance;
    return !!(prov && typeof prov.verified_by === "string" && prov.verified_by);
  }

  function countVerified(nodes) {
    var n = 0;
    (nodes || []).forEach(function (node) { if (isVerified(node)) n += 1; });
    return n;
  }

  function stageFor(count, verifiedCount) {
    count = Math.max(0, Math.floor(Number(count) || 0));
    verifiedCount = Math.max(0, Math.min(count, Math.floor(Number(verifiedCount) || 0)));
    var picked = STAGES[0];
    var next = null;
    for (var i = 0; i < STAGES.length; i++) {
      if (count >= STAGES[i].minCount) {
        picked = STAGES[i];
        next = STAGES[i + 1] || null;
      }
    }
    return {
      name: picked.name,
      description: picked.description,
      minCount: picked.minCount,
      nextName: next ? next.name : null,
      nextMin: next ? next.minCount : null,
      dust: picked.dust,
      scale: picked.scale,
      count: count,
      verifiedCount: verifiedCount,
      verifiedFraction: count === 0 ? 0 : verifiedCount / count
    };
  }

  /* Nebula layout + keyword labels (Blocks 13-14). The canvas
     is sized to its displayed size on every render (see app.js),
     so layout must derive its centre and radius from the real
     width and height — never from a fixed backing-store size.
     Labels are MEANINGFUL keywords, not sentences and not the
     first words regardless of meaning: small filler words are
     stripped and the first two remaining content words are kept
     (verbs count — "opens" and "grows" are the meaningful part
     of "The library opens" / "The garden grows"). Duplicate
     memories are grouped into one canvas node (see
     groupGraphNodes); the full sentences stay, each listed
     individually, in the text list below the graph. Labels sit on
     the side away from the canvas centre, 18px clear of the node
     circle, and are truncated with the canvas's own measureText
     so they never cross the canvas edge. */
  var KEYWORD_MAX_CHARS = 20;
  var LABEL_GAP_PX = 18;
  var LABEL_FONT_PX = 12;
  var LABEL_STAGGER_PX = 16;

  /* Filler words carry no meaning on a star map: "The library
     opens" and "The garden grows" must not both collapse to
     "The". Matching is on the cleaned lowercase word; verbs,
     nouns, names, and times ("opens", "grows", "9am") are kept. */
  var STOP_WORDS = {
    "the": true, "a": true, "an": true, "at": true, "on": true,
    "in": true, "of": true, "to": true, "and": true, "is": true,
    "are": true, "was": true, "were": true, "for": true,
    "with": true, "by": true, "from": true
  };

  function cleanWord(word) {
    return String(word || "").replace(/^[^a-z0-9]+|[^a-z0-9]+$/gi, "");
  }

  function contentWords(text) {
    return String(text || "").trim().split(/\s+/).map(function (w) {
      return cleanWord(w).toLowerCase();
    }).filter(function (w) {
      return w.length > 0 && !STOP_WORDS[w];
    });
  }

  function keywordLabel(text) {
    var joined = contentWords(text).slice(0, 2).join(" ");
    if (!joined) return "";
    joined = joined.charAt(0).toUpperCase() + joined.slice(1);
    if (joined.length > KEYWORD_MAX_CHARS) {
      return joined.slice(0, KEYWORD_MAX_CHARS - 1) + "…";
    }
    return joined;
  }

  /* Grouping key for duplicate memories (canvas only): case,
     extra whitespace, and leading/trailing punctuation do not
     make a new fact. The text list below the graph is NOT grouped
     — every memory stays listed individually there. */
  function normalizeFactKey(text) {
    return String(text || "").trim().replace(/\s+/g, " ").toLowerCase();
  }

  /* Group nodes by normalised fact text, first-seen order. Each
     group draws ONE canvas node labelled with the meaningful
     keyword plus " ×N" when N memories share the fact. The group
     counts as checked when ANY member passed Cross-Hatch Verify.
     Stage counts, EXP, and the text list keep using the TOTAL
     memory count — grouping changes only the picture. */
  function groupGraphNodes(nodes) {
    var groups = [];
    var byKey = {};
    (nodes || []).forEach(function (node) {
      var key = normalizeFactKey(node.text || node.label || "");
      var group = byKey[key];
      if (!group) {
        group = {
          id: node.id, representative: node, members: [],
          count: 0, verified: false, label: ""
        };
        byKey[key] = group;
        groups.push(group);
      }
      group.members.push(node);
      group.count += 1;
      if (isVerified(node)) group.verified = true;
    });
    groups.forEach(function (group) {
      var keyword = keywordLabel(
        group.representative.text || group.representative.label || "");
      group.label = group.count > 1
        ? keyword + " ×" + group.count
        : keyword;
    });
    return groups;
  }

  /* Remap edges onto groups (canvas only): endpoints become their
     group id, edges inside one group are dropped, and identical
     group pairs are drawn once, keeping the first line style. */
  function mapGroupEdges(edges, groups) {
    var memberToGroup = {};
    (groups || []).forEach(function (group) {
      group.members.forEach(function (member) {
        memberToGroup[member.id] = group.id;
      });
    });
    var seen = {};
    var out = [];
    (edges || []).forEach(function (edge) {
      var from = memberToGroup[edge.from];
      var to = memberToGroup[edge.to];
      if (!from || !to || from === to) return;
      var key = from + "→" + to;
      if (seen[key]) return;
      seen[key] = true;
      out.push({
        from: from, to: to,
        kind: edge.kind, line_style: edge.line_style, label: edge.label
      });
    });
    return out;
  }

  function layoutNodes(nodes, width, height) {
    var positions = {};
    var cx = width / 2, cy = height / 2;
    var radius = Math.max(40, Math.min(width, height) / 2 - 56);
    (nodes || []).forEach(function (node, i) {
      var angle = (2 * Math.PI * i) / Math.max(1, nodes.length);
      positions[node.id] = {x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle)};
    });
    return positions;
  }

  function dustPoint(index, width, height) {
    var hx = ((index + 1) * 2654435761) % width;
    var hy = ((index + 1) * 40503) % height;
    return {
      x: hx < 0 ? hx + width : hx,
      y: hy < 0 ? hy + height : hy
    };
  }

  function labelSide(pos, canvasWidth) {
    return pos.x >= canvasWidth / 2 ? "right" : "left";
  }

  /* Where a label goes: on the outer side of the node, LABEL_GAP_PX
     clear of the node circle's edge, so text never overlaps the
     circle. Returns the anchor x and the canvas textAlign to use
     with it. Callers clamp the text itself (fitLabel) to the space
     between this anchor and the canvas edge. */
  function labelGeometry(pos, canvasWidth, nodeSize) {
    if (labelSide(pos, canvasWidth) === "right") {
      return {x: pos.x - nodeSize - LABEL_GAP_PX, textAlign: "right"};
    }
    return {x: pos.x + nodeSize + LABEL_GAP_PX, textAlign: "left"};
  }

  /* Truncate text with a real measurement function (the canvas
     context's measureText in the page) so the fitted text fits
     maxWidth. Returns "" when even an ellipsis does not fit. */
  function fitLabel(text, maxWidth, measure) {
    if (!text || maxWidth <= 0) return "";
    if (measure(text) <= maxWidth) return text;
    if (measure("…") > maxWidth) return "";
    var trimmed = text;
    while (trimmed.length > 0 && measure(trimmed + "…") > maxWidth) {
      trimmed = trimmed.slice(0, -1);
    }
    return trimmed === "" ? "…" : trimmed + "…";
  }

  function boxesOverlap(a, b) {
    return a.x0 < b.x1 + 2 && a.x1 > b.x0 - 2 &&
           a.y0 < b.y1 + 2 && a.y1 > b.y0 - 2;
  }

  /* Place one label: fit it to the room between the anchor and
     the canvas edge, then stagger it vertically (16px steps, away
     from the canvas centre, at most 4 steps) while its box would
     overlap an already-placed label. Returns null when there is
     no room at all. The returned box is in canvas coordinates and
     never overlaps the node circle: the anchor is already
     LABEL_GAP_PX clear of it (see labelGeometry) and the box
     extends only away from the node. Callers push the returned
     box into `placed` before placing the next label. */
  function placeLabel(geo, keyword, baseY, measure, placed, canvasWidth, canvasHeight) {
    if (!keyword) return null;
    var room = geo.textAlign === "right"
      ? geo.x - 8
      : canvasWidth - 8 - geo.x;
    if (room < 24) return null;
    var fitted = fitLabel(keyword, room, measure);
    if (!fitted) return null;
    var width = measure(fitted);
    var x0 = geo.textAlign === "right" ? geo.x - width : geo.x;
    var centreY = canvasHeight / 2;
    var dir = baseY >= centreY ? 1 : -1;
    var y = baseY;
    var box = null;
    var tries = 0;
    while (tries <= 4) {
      box = {
        x0: x0, x1: x0 + width,
        y0: y - LABEL_FONT_PX / 2, y1: y + LABEL_FONT_PX / 2
      };
      var clash = (placed || []).some(function (other) {
        return boxesOverlap(box, other);
      });
      if (!clash) break;
      if (tries === 4) break;
      y += LABEL_STAGGER_PX * dir;
      if (y < 8) y = 8;
      if (y > canvasHeight - 8) y = canvasHeight - 8;
      tries += 1;
    }
    return {text: fitted, x: geo.x, y: y, box: box};
  }

  /* Origin colours + ring patterns (Block 17). Every memory
     carries an origin label (which model, client, or coder made
     it — see app/origin.py). The map shows the origin two ways
     at once, so colour is never the only carrier: a user-assignable
     ring colour AND a ring pattern that cycles solid / dashed /
     dotted / double by first-seen order. The pattern is purely
     index-based — it never reads a colour variable — so in
     achromatopsia mode, where the page filter collapses every
     colour to grey, the patterns, the legend, and the text list
     keep the full meaning. Default colours are derived from the
     active palette itself (accent, edge, and muted mixes of the
     two), never hardcoded neon: Posh direction, orchid/wine/teal
     family. All helpers here are pure so tests can execute them
     for real; app.js supplies the palette values it reads from
     the page's own CSS variables. */
  var ORIGIN_PATTERNS = ["solid", "dashed", "dotted", "double"];
  var ORIGIN_FALLBACK_PALETTE = {
    accent: "#ad3375", edge: "#547c6d", text: "#ddd3d7",
    bg: "#080609", metal: "#a8891f", border: "#241d23"
  };

  function parseColour(value) {
    var text = String(value || "").trim();
    var hex = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(text);
    if (hex) {
      var h = hex[1];
      if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
      return {
        r: parseInt(h.slice(0, 2), 16),
        g: parseInt(h.slice(2, 4), 16),
        b: parseInt(h.slice(4, 6), 16)
      };
    }
    var rgb = /^rgba?\((\d+),\s*(\d+),\s*(\d+)/i.exec(text);
    if (rgb) {
      return {
        r: Math.min(255, Number(rgb[1])),
        g: Math.min(255, Number(rgb[2])),
        b: Math.min(255, Number(rgb[3]))
      };
    }
    return null;
  }

  function toHex(rgb) {
    function part(n) {
      var s = Math.max(0, Math.min(255, Math.round(n))).toString(16);
      return s.length === 1 ? "0" + s : s;
    }
    return "#" + part(rgb.r) + part(rgb.g) + part(rgb.b);
  }

  function mixHex(first, second, t) {
    var a = parseColour(first), b = parseColour(second);
    if (!a) return toHex(parseColour(second) || {r: 0, g: 0, b: 0});
    if (!b) return toHex(a);
    return toHex({
      r: a.r + (b.r - a.r) * t,
      g: a.g + (b.g - a.g) * t,
      b: a.b + (b.b - a.b) * t
    });
  }

  function paletteValue(palette, key) {
    var value = palette && palette[key];
    var parsed = parseColour(value);
    if (parsed) return toHex(parsed);
    return ORIGIN_FALLBACK_PALETTE[key];
  }

  /* Default ring colour for the origin at `index` (first-seen
     order): accent, edge, muted accent, metal, deepened edge,
     deepened accent, then cycling. Every default is a palette
     value or a mix of two palette values. */
  function originColourFor(index, palette) {
    var p = palette || {};
    var accent = paletteValue(p, "accent");
    var edge = paletteValue(p, "edge");
    var text = paletteValue(p, "text");
    var bg = paletteValue(p, "bg");
    var metal = parseColour(p.metal) ? toHex(parseColour(p.metal)) : null;
    var bases = [
      accent,
      edge,
      mixHex(accent, text, 0.45),
      metal || mixHex(accent, edge, 0.5),
      mixHex(edge, bg, 0.45),
      mixHex(accent, bg, 0.4)
    ];
    var i = ((Math.floor(Number(index) || 0)) % bases.length + bases.length) % bases.length;
    return bases[i];
  }

  function originPattern(index) {
    var i = ((Math.floor(Number(index) || 0)) % ORIGIN_PATTERNS.length + ORIGIN_PATTERNS.length) % ORIGIN_PATTERNS.length;
    return ORIGIN_PATTERNS[i];
  }

  /* Canvas dash for a pattern: solid and double draw solid
     strokes (double adds a second outline in app.js); dashed
     and dotted use dash arrays. Pure index logic — no colours. */
  function patternDash(pattern) {
    if (pattern === "dashed") return [6, 4];
    if (pattern === "dotted") return [2, 4];
    return [];
  }

  function originOf(node) {
    return (node && node.origin) || "unknown origin";
  }

  /* Origins of one canvas group, first-seen order: a group that
     mixes origins lists each of them; the legend carries the
     detail while the canvas ring uses the first. */
  function groupOrigins(group) {
    var seen = {};
    var out = [];
    var members = (group && group.members) || [];
    if (!members.length && group && group.representative) members = [group.representative];
    members.forEach(function (member) {
      var origin = originOf(member);
      if (!seen[origin]) { seen[origin] = true; out.push(origin); }
    });
    return out.length ? out : ["unknown origin"];
  }

  /* Legend data from every memory (NOT groups): each origin's
     memory count, in first-seen order, with its ring pattern.
     Grouping never hides an origin from the legend. */
  function legendEntries(nodes) {
    var counts = {};
    var order = [];
    (nodes || []).forEach(function (node) {
      var origin = originOf(node);
      if (!(origin in counts)) { counts[origin] = 0; order.push(origin); }
      counts[origin] += 1;
    });
    return order.map(function (origin, i) {
      return {origin: origin, count: counts[origin], pattern: originPattern(i), patternIndex: i};
    });
  }

  /* Integrations status words (Block 16): the CSS class for a
     status word, so status is carried by border style as well as
     by the printed word — never by colour alone. Pure function,
     shared with app.js through the same export as the graph
     helpers, so tests can execute it for real. */
  function integrationStatusClass(statusWord) {
    if (statusWord === "Connected" || statusWord === "Available") {
      return "status-connected";
    }
    if (statusWord === "Not connected") return "status-off";
    if (statusWord === "Fake (tests only)") return "status-fake";
    return "status-local";
  }

  /* Origin colours + patterns (Block 17): exposed on their own
     handle so app.js can keep the graph helpers untouched. */
  window.HIVEMIND_ORIGINS = {
    originColourFor: originColourFor,
    originPattern: originPattern,
    patternDash: patternDash,
    originOf: originOf,
    groupOrigins: groupOrigins,
    legendEntries: legendEntries,
    mixHex: mixHex,
    parseColour: parseColour
  };

  window.HIVEMIND_STAGE = {
    STAGES: STAGES,
    stageFor: stageFor,
    countVerified: countVerified,
    isVerified: isVerified
  };
  window.HIVEMIND_INTEGRATIONS = {
    statusClassFor: integrationStatusClass
  };
  window.HIVEMIND_GRAPH = {
    keywordLabel: keywordLabel,
    contentWords: contentWords,
    normalizeFactKey: normalizeFactKey,
    groupGraphNodes: groupGraphNodes,
    mapGroupEdges: mapGroupEdges,
    placeLabel: placeLabel,
    layoutNodes: layoutNodes,
    dustPoint: dustPoint,
    labelSide: labelSide,
    labelGeometry: labelGeometry,
    fitLabel: fitLabel,
    KEYWORD_MAX_CHARS: KEYWORD_MAX_CHARS,
    LABEL_GAP_PX: LABEL_GAP_PX,
    LABEL_FONT_PX: LABEL_FONT_PX,
    LABEL_STAGGER_PX: LABEL_STAGGER_PX
  };
})();
