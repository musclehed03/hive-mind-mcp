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

  window.HIVEMIND_STAGE = {
    STAGES: STAGES,
    stageFor: stageFor,
    countVerified: countVerified,
    isVerified: isVerified
  };
})();
