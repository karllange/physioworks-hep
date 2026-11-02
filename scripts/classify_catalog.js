#!/usr/bin/env node
/*
 * Adds structured safety fields to exercises.json and cleans the catalog.
 *   node scripts/classify_catalog.js          (writes exercises.json + protocols.json)
 *   node scripts/classify_catalog.js --check  (exits 1 if the files are out of date)
 *
 * Fields written on every exercise:
 *   movementType  PROM | AAROM | AROM | Resisted | Stretch
 *   joints        regions the exercise loads or moves (knee, shoulder, ...)
 *   motions       joint_motion keys (knee_extension, shoulder_flexion, ...)
 *   isometric, weightBearing, impact, chain (open|closed), needsReview
 * `type` is kept in sync: "stretch" for Stretch/PROM, "strength" otherwise.
 */
const fs = require("fs");
const path = require("path");
const HEPSafety = require("../hep-safety.js");

const ROOT = path.join(__dirname, "..");
const CATALOG = path.join(ROOT, "exercises.json");
const REGISTRY = path.join(ROOT, "protocols.json");

// Rows that are protocol prose, not exercises. Also read by scripts/ingest_protocol.py.
const REMOVED_IDS = require("./catalog_removals.json");

// Manual corrections where the keyword classifier is wrong or unsure.
const OVERRIDES = {
  "core-mountain-climbers-slow-01": { movementType: "Resisted", joints: ["shoulder", "lumbar", "hip"], motions: ["hip_flexion"] },
  "hip-bent-knee-fallouts-01": { movementType: "AROM", joints: ["hip"], motions: ["hip_abduction", "hip_rotation"] },
  "snap-down-progression": { movementType: "Resisted", joints: ["hip", "knee", "ankle"], weightBearing: true, impact: true, chain: "closed" },
  "dl-extension": { movementType: "Resisted", joints: ["knee"], motions: ["knee_extension"], name: "DL Machine Knee Extension" },
  "sl-extension": { movementType: "Resisted", joints: ["knee"], motions: ["knee_extension"], weightBearing: false, chain: "open", name: "SL Machine Knee Extension" },
  "dl-machine-extension": { joints: ["knee"], motions: ["knee_extension"] },
  "dl-machine-extension-holds-at-0-degrees": { joints: ["knee"], motions: ["knee_extension"], isometric: true },
  "heavy-sl-machine-extension": { joints: ["knee"], motions: ["knee_extension"], weightBearing: false, chain: "open" },
  "sl-holds": { joints: ["knee"], motions: ["knee_extension"], isometric: true, needsReview: true },
  "standing-hamstring-curl": { joints: ["knee"], motions: ["knee_flexion"] },
  "nu-step": { movementType: "AROM", joints: ["hip", "knee", "ankle"], weightBearing: false, chain: "closed" },
  "nu-step-and-bike": { movementType: "AROM", weightBearing: false, chain: "closed" },
  "split-squat-progression": { joints: ["hip", "knee", "ankle"] },
  "hurdle-progression": { joints: ["hip", "knee", "ankle"], weightBearing: true },
  "gait-progression": { joints: ["hip", "knee", "ankle"], weightBearing: true },
  "cable-decels": { joints: ["hip", "knee", "ankle"], weightBearing: true },
  "supine-internal-rotation": { movementType: "AROM", joints: ["hip"], motions: ["hip_rotation"] },
  "seated-internal-rotation-external-rotation": { movementType: "AROM", joints: ["hip"], motions: ["hip_rotation"] },
  "scapular-plane-shoulder-elevation-90": { movementType: "AROM", motions: ["shoulder_flexion", "shoulder_abduction"] },
  "standing-unweighted-flex": { movementType: "AROM" },
  "ball-squeezes": { joints: ["hand"], needsReview: true },
  "1-2-kneeling-hip": { needsReview: true },
  "initiate-wb-with-crutches-in-the-boot": { joints: ["ankle"], weightBearing: true, chain: "closed", needsReview: true },
  "bike-no-recumbent-bike": { movementType: "AROM", name: "Stationary Bike (Upright; No Recumbent Bike)" },
  "feet-together-on-foam": { joints: ["ankle", "knee"], weightBearing: true, chain: "closed" },
  "get-up-from-floor-progression": { joints: ["hip", "knee"], weightBearing: true, chain: "closed" },
  "standing-hamstring-activation": { joints: ["knee"], motions: ["knee_flexion"] },
  "flexion-on-step": { movementType: "AAROM", needsReview: true },
  "cross-symmetry-walk-outs": { joints: ["shoulder"], weightBearing: false }
};

// Near-duplicates: removed id -> kept id.
const MERGED = {
  "lat-pull-down": "lat-pulldown",
  "dip-bar-assisted-slant-board-squat": "dip-bar-assisted-slantboard-squat"
};

function build(catalog, registry) {
  const removeSet = new Set(Object.keys(REMOVED_IDS).concat(Object.keys(MERGED)));
  const removed = catalog.filter(e => removeSet.has(e.id)).map(e => ({ id: e.id, name: e.name, reason: MERGED[e.id] ? "duplicate of " + MERGED[e.id] : "not an exercise" }));
  const kept = catalog.filter(e => !removeSet.has(e.id)).map(entry => {
    const o = OVERRIDES[entry.id] || {};
    const next = { ...entry };
    if (o.name) next.name = o.name;
    if (entry.id === "sl-holds") next.category = "knee";
    const p = HEPSafety.classifyExercise(next);
    const profile = {
      movementType: o.movementType || p.movementType,
      joints: o.joints || p.joints,
      motions: o.motions || p.motions,
      isometric: o.isometric != null ? o.isometric : p.isometric,
      weightBearing: o.weightBearing != null ? o.weightBearing : p.weightBearing,
      impact: o.impact != null ? o.impact : p.impact,
      chain: o.chain || p.chain,
      needsReview: o.needsReview != null ? o.needsReview : (OVERRIDES[entry.id] ? false : p.needsReview)
    };
    next.type = ["Stretch", "PROM"].includes(profile.movementType) ? "stretch" : "strength";
    // Drop stale copies, then append the fields in a stable order.
    ["movementType", "joints", "motions", "isometric", "weightBearing", "impact", "chain", "needsReview"].forEach(k => delete next[k]);
    return Object.assign(next, profile);
  });
  const keptIds = new Set(kept.map(e => e.id));
  const protocolChanges = [];
  const nextRegistry = registry.map(entry => {
    if (!Array.isArray(entry.exercise_ids)) return entry;
    const ids = [];
    const doses = {};
    const changes = [];
    entry.exercise_ids.forEach(id => {
      const target = MERGED[id] || id;
      if (MERGED[id]) changes.push(id + " -> " + target);
      if (!keptIds.has(target)) { changes.push("dropped " + id); return; }
      if (!ids.includes(target)) ids.push(target);
    });
    Object.entries(entry.exercise_doses || {}).forEach(([id, dose]) => {
      const target = MERGED[id] || id;
      if (ids.includes(target) && !doses[target]) doses[target] = dose;
    });
    if (changes.length) protocolChanges.push({ id: entry.id, changes });
    const next = { ...entry, exercise_ids: ids };
    if (entry.exercise_doses) next.exercise_doses = doses;
    return next;
  });
  // Every protocol reference must resolve.
  const dangling = [];
  nextRegistry.forEach(entry => (entry.exercise_ids || []).forEach(id => { if (!keptIds.has(id)) dangling.push(entry.id + ":" + id); }));
  return { catalog: kept, registry: nextRegistry, removed, protocolChanges, dangling };
}

if (require.main === module) {
  const catalog = JSON.parse(fs.readFileSync(CATALOG, "utf8"));
  const registry = JSON.parse(fs.readFileSync(REGISTRY, "utf8"));
  const out = build(catalog, registry);
  if (out.dangling.length) { console.error("Dangling protocol references:", out.dangling); process.exit(1); }
  const catalogText = JSON.stringify(out.catalog, null, 2) + "\n";
  const registryText = JSON.stringify(out.registry, null, 2) + "\n";
  if (process.argv.includes("--check")) {
    const ok = catalogText === fs.readFileSync(CATALOG, "utf8") && registryText === fs.readFileSync(REGISTRY, "utf8");
    console.log(ok ? "catalog up to date" : "catalog out of date: run node scripts/classify_catalog.js");
    process.exit(ok ? 0 : 1);
  }
  fs.writeFileSync(CATALOG, catalogText);
  fs.writeFileSync(REGISTRY, registryText);
  console.log(JSON.stringify({ removed: out.removed, protocolChanges: out.protocolChanges, kept: out.catalog.length }, null, 2));
}

module.exports = { build, REMOVED_IDS, MERGED, OVERRIDES };
