#!/usr/bin/env node
/*
 * Report-only: runs each protocols.json phase's own precautions through the
 * safety engine against that phase's exercise_ids. Prints conflicts for
 * clinician review; it never edits data. Usage: node scripts/check_protocol_conflicts.js
 */
const path = require("path");
const H = require("../hep-safety.js");
const catalog = require(path.join(__dirname, "..", "exercises.json"));
const registry = require(path.join(__dirname, "..", "protocols.json"));
const byId = new Map(catalog.map(e => [e.id, e]));
let blocks = 0, warns = 0;
for (const entry of registry) {
  const text = [entry.protocol_title, entry.phase, entry.precautions].filter(Boolean).join(". ");
  const a = H.analyzeProtocolText(text);
  const ctx = { surgicalSide: a.side, surgicalJoint: a.surgery && a.surgery.joint };
  for (const id of entry.exercise_ids || []) {
    const ex = byId.get(id);
    if (!ex) continue;
    const ev = H.evaluateExercise(ex, a.rules, ctx, "Bilateral");
    if (ev.status === "block") {
      blocks++;
      const r = ev.reasons.find(x => x.level === "block");
      console.log(`BLOCK ${entry.id || entry.protocol_title} :: ${ex.name} :: ${r.why}${r.source ? " [" + r.source + "]" : ""}`);
    } else if (ev.status === "warn") warns++;
  }
}
console.log(`\n${blocks} blocked, ${warns} caution item(s) across ${registry.length} protocol phases.`);
