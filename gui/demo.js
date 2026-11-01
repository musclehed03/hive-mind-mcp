/* Hive-Mind demo autopilot: pure helpers (Block 18).

   The demo walks the GUI through DEMO_SCRIPT.md Beats 3-4 by
   itself: Sonja presses Play, narrates, and never has to remember
   a step mid-take. This file holds ONLY pure, testable logic —
   the step list, the settings snapshot used to restore everything
   afterwards, dwell arithmetic, and the demo ring-colour pick.
   It never touches the DOM, never starts anything, never reads
   the network, and never rolls its own timing: the DOM driver
   lives in app.js and is the only place a one-shot delay is
   scheduled. Nothing here runs on load; playback starts only
   when the Play control is pressed, and there is no automatic
   start of any kind. */
(function () {
  "use strict";

  /* One dwell per step: long enough to say the caption out loud
     and let the recording catch the action. */
  var DEMO_DWELL_MS = 6000;

  /* Steps follow docs/DEMO_SCRIPT.md Beats 3-4 in order. Each
     step names the element to spotlight (by id), the plain-words
     caption shown on screen for the whole dwell, and the action
     to run when the step starts (onEnter) plus the action that
     undoes the visible part of it when the demo moves on
     (onLeave, null when there is nothing to undo). The action
     names are keys only — app.js maps each key to the same
     function a click would run. The read-aloud step is shown,
     never pressed: no surprise audio during a recording. */
  var DEMO_STEPS = [
    {id: "stage", targetId: "growth-stage",
     caption: "Growth stage: the sky grows as memories arrive and facts get checked.",
     onEnter: "highlight", onLeave: null},
    {id: "exp", targetId: "exp-meter",
     caption: "EXP: points for healthy memories only — checked facts, settled mix-ups, backups. Never for spending on API calls.",
     onEnter: "highlight", onLeave: null},
    {id: "origins", targetId: "origin-legend",
     caption: "Every dot says who made it — which model, which app, which person. You pick the ring colours; the ring pattern and this list carry the meaning without colour.",
     onEnter: "origin-colour", onLeave: null},
    {id: "metaphor", targetId: "metaphor-select",
     caption: "Same memories, different picture: Tree of Life — and back to the Nebula.",
     onEnter: "metaphor-tree", onLeave: "metaphor-nebula"},
    {id: "achromatopsia", targetId: "profile-achromatopsia",
     caption: "One click, pure grayscale, nothing lost — checked by Day, who sees in grayscale only. The demo turns the profile off again before moving on.",
     onEnter: "achromatopsia-on", onLeave: "achromatopsia-off"},
    {id: "integrations", targetId: "integrations",
     caption: "Connecting is copy-and-paste, not configuration archaeology. Keys are never typed here.",
     onEnter: "integrations-copy", onLeave: null},
    {id: "read-aloud", targetId: "read-aloud-button",
     caption: "Read aloud is shown, not pressed — no surprise audio during a recording. Press it yourself any time.",
     onEnter: "highlight", onLeave: null}
  ];

  function stepAt(index) {
    if (typeof index !== "number" || index < 0 || index >= DEMO_STEPS.length) return null;
    return DEMO_STEPS[index];
  }

  function stepCount() {
    return DEMO_STEPS.length;
  }

  function stepIds() {
    return DEMO_STEPS.map(function (step) { return step.id; });
  }

  /* Index after `index`, or -1 when the list is done. Pure
     arithmetic: the driver owns the clock. */
  function nextStepIndex(index) {
    var next = Math.floor(Number(index) || 0) + 1;
    return next >= DEMO_STEPS.length ? -1 : next;
  }

  /* Share of one dwell elapsed, clamped: drives the progress
     bar, which is always paired with the "Ns left" text. */
  function progressFraction(elapsedMs, dwellMs) {
    var dwell = Number(dwellMs) || DEMO_DWELL_MS;
    if (dwell <= 0) return 1;
    var frac = (Number(elapsedMs) || 0) / dwell;
    if (frac < 0) return 0;
    if (frac > 1) return 1;
    return frac;
  }

  /* Whole seconds left in a dwell, never below zero: the text
     next to the progress bar. */
  function remainingSeconds(dwellMs, elapsedMs) {
    var left = (Number(dwellMs) || DEMO_DWELL_MS) - (Number(elapsedMs) || 0);
    if (left <= 0) return 0;
    return Math.ceil(left / 1000);
  }

  /* Deep copy of a settings object, JSON-shaped only (the GUI
     settings state is plain data). The copy is what the demo
     restores when it stops or finishes, so the user's colours,
     profile, and graph view come back exactly as they were —
     including values the demo never touched. */
  function captureSnapshot(state) {
    return JSON.parse(JSON.stringify(state || {}));
  }

  /* A fresh copy of a snapshot, so restoring can never hand the
     live state an object the demo still holds a reference to. */
  function applySnapshot(snapshot) {
    return JSON.parse(JSON.stringify(snapshot || {}));
  }

  /* Pick the demo ring colour: the first candidate that is not
     the colour already in use (compared case-insensitively, so
     "#AD3375" and "#ad3375" count as the same). Falls back to
     the first candidate when every candidate matches, and to
     null when there are no candidates at all. Candidates come
     from the palette-derived defaults in stage.js, supplied by
     the driver — this helper never invents a colour. */
  function pickDemoColour(currentColour, candidates) {
    var list = candidates || [];
    if (!list.length) return null;
    var current = String(currentColour || "").toLowerCase();
    for (var i = 0; i < list.length; i++) {
      if (String(list[i]).toLowerCase() !== current) return list[i];
    }
    return list[0];
  }

  window.HIVEMIND_DEMO = {
    DWELL_MS: DEMO_DWELL_MS,
    STEPS: DEMO_STEPS,
    stepAt: stepAt,
    stepCount: stepCount,
    stepIds: stepIds,
    nextStepIndex: nextStepIndex,
    progressFraction: progressFraction,
    remainingSeconds: remainingSeconds,
    captureSnapshot: captureSnapshot,
    applySnapshot: applySnapshot,
    pickDemoColour: pickDemoColour
  };
})();
