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

  /* Nebula layout + keyword labels (Block 13). The canvas is
     sized to its displayed size on every render (see app.js), so
     layout must derive its centre and radius from the real width
     and height — never from a fixed backing-store size. Labels
     are keywords, not sentences: the first three words of the
     memory text, capped at 20 characters. The full sentence stays
     in the text list below the graph. Labels sit on the side away
     from the canvas centre, 18px clear of the node circle, and are
     truncated with the canvas's own measureText so they never
     cross the canvas edge. */
  var KEYWORD_MAX_CHARS = 20;
  var LABEL_GAP_PX = 18;

  function keywordLabel(text) {
    var words = String(text || "").trim().split(/\s+/).filter(function (w) { return w.length > 0; });
    var joined = words.slice(0, 3).join(" ");
    if (joined.length > KEYWORD_MAX_CHARS) {
      return joined.slice(0, KEYWORD_MAX_CHARS - 1) + "…";
    }
    return joined;
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

  window.HIVEMIND_STAGE = {
    STAGES: STAGES,
    stageFor: stageFor,
    countVerified: countVerified,
    isVerified: isVerified
  };
  window.HIVEMIND_GRAPH = {
    keywordLabel: keywordLabel,
    layoutNodes: layoutNodes,
    dustPoint: dustPoint,
    labelSide: labelSide,
    labelGeometry: labelGeometry,
    fitLabel: fitLabel,
    KEYWORD_MAX_CHARS: KEYWORD_MAX_CHARS,
    LABEL_GAP_PX: LABEL_GAP_PX
  };
})();
