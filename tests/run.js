#!/usr/bin/env node
/*
 * One-command test run:  node tests/run.js
 * Engine + catalog tests run in plain Node. Add --browser to also run the
 * headless page test (tests/browser.js, needs puppeteer-core and Chrome).
 */
const assert = require("assert");
const path = require("path");
const fs = require("fs");
const H = require("../hep-safety.js");

const ROOT = path.join(__dirname, "..");
const catalog = JSON.parse(fs.readFileSync(path.join(ROOT, "exercises.json"), "utf8"));
const registry = JSON.parse(fs.readFileSync(path.join(ROOT, "protocols.json"), "utf8"));
const byName = name => {
  const ex = catalog.find(e => e.name.toLowerCase() === name.toLowerCase());
  if (!ex) throw new Error("catalog missing " + name);
  return ex;
};
const evaluateText = (text, ex, side) => {
  const a = H.analyzeProtocolText(text);
  return H.evaluateExercise(ex, a.rules, { surgicalSide: a.side, surgicalJoint: a.surgery && a.surgery.joint }, side);
};

const results = [];
function test(name, fn) {
  try { fn(); results.push({ name, ok: true }); }
  catch (err) { results.push({ name, ok: false, err }); }
}

// --- Audit regression cases -------------------------------------------------
test("'Ankle pumps not allowed' blocks Ankle Pumps (catalog and custom)", () => {
  const ev = evaluateText("Ankle pumps not allowed.", byName("Ankle Pumps"));
  assert.strictEqual(ev.status, "block");
  assert.match(ev.reasons[0].source, /Ankle pumps not allowed/);
  const custom = evaluateText("Ankle pumps not allowed.", { name: "Ankle Pumps", category: "ankle" });
  assert.strictEqual(custom.status, "block");
  assert.strictEqual(evaluateText("Ankle pumps not allowed.", byName("Heel Slide")).status, "ok");
});

test("Negation forms: no / avoid / do not / don't / without / prohibited", () => {
  const squat = byName("Squat");
  ["No squats.", "Avoid squats.", "Do not perform squats.", "Don't squat.", "Squats are prohibited.", "Without squats for 6 weeks."].forEach(text => {
    assert.strictEqual(evaluateText(text, squat).status, "block", text);
  });
  assert.strictEqual(evaluateText("Quad sets and ankle pumps not allowed.", byName("Quad Set with Towel Roll")).status, "block");
});

const ACL_SAMPLE = "Left ACL reconstruction with patellar tendon graft. Phase I, weeks 0-2. WBAT in brace locked in extension. "
  + "No open-chain knee extension (no long arc quads) for 12 weeks. Avoid active knee extension 90-40 degrees. "
  + "Quad sets, SLR, heel slides, patellar mobs, ankle pumps.";

test("ACL sample: captures surgery, phase, side and restrictions; Long Arc Quad blocked", () => {
  const a = H.analyzeProtocolText(ACL_SAMPLE);
  assert.strictEqual(a.surgery.id, "acl");
  assert.strictEqual(a.phase.number, 1);
  assert.deepStrictEqual(a.phase.weeks, [0, 2]);
  assert.strictEqual(a.side, "Left");
  assert.ok(a.rules.some(r => r.kind === "no_okc_extension"), "open-chain rule");
  assert.ok(a.rules.some(r => r.kind === "no_active" && r.joint === "knee"), "active extension rule");
  const laq = evaluateText(ACL_SAMPLE, byName("Long Arc Quad"));
  assert.strictEqual(laq.status, "block");
  assert.ok(laq.reasons.every(r => r.source), "every block shows the matched restriction text");
  assert.notStrictEqual(evaluateText(ACL_SAMPLE, byName("Heel Slide")).status, "block");
  assert.notStrictEqual(evaluateText(ACL_SAMPLE, byName("Quad Set with Towel Roll")).status, "block");
});

test("'RCR PROM only' blocks active shoulder flexion, allows PROM/pendulum", () => {
  const text = "Right RCR PROM only.";
  assert.strictEqual(evaluateText(text, byName("Standing Unweighted Flex")).status, "block");
  assert.strictEqual(evaluateText(text, byName("Wand Shoulder Flexion")).status, "block");
  assert.strictEqual(evaluateText(text, byName("Standing Scaption (Full Can)")).status, "block");
  assert.strictEqual(evaluateText(text, byName("Standing Pendulum")).status, "ok");
  assert.strictEqual(evaluateText(text, byName("Supine Passive External Rotation")).status, "ok");
  assert.strictEqual(evaluateText(text, byName("Ankle Pumps")).status, "ok");
});

test("'Left TKA. Right knee…' resolves Left with a wrong-side warning", () => {
  const a = H.analyzeProtocolText("Left TKA. Right knee pain with stairs, monitor.");
  assert.strictEqual(a.side, "Left");
  assert.ok(a.warnings.some(w => /Wrong-side/.test(w)));
  const b = H.analyzeProtocolText("s/p R TKA 10/2. WBAT.");
  assert.strictEqual(b.side, "Right");
  const c = H.analyzeProtocolText("TKA phase 1.");
  assert.strictEqual(c.side, "Unknown");
  assert.ok(c.warnings.length, "unknown side warns instead of defaulting to Bilateral");
});

test("Phases I-VII parse (roman and arabic), plus week ranges", () => {
  const cases = { "Phase I": 1, "Phase II": 2, "Phase III": 3, "Phase IV": 4, "Phase V": 5, "Phase VI": 6, "Phase VII": 7, "phase 5": 5, "Phase 6:": 6, "PHASE 7 (16-20 weeks)": 7, "Phase Four": 4 };
  Object.entries(cases).forEach(([text, n]) => assert.strictEqual(H.detectPhase(text).number, n, text));
  assert.deepStrictEqual(H.detectPhase("Weeks 6-12").weeks, [6, 12]);
  assert.deepStrictEqual(H.detectPhase("6 to 12 weeks").weeks, [6, 12]);
  assert.ok(H.detectPhase("Phase V then Phase VI").multiple);
});

test("Every surgery type in protocols.json is detected from its title", () => {
  const titles = [...new Set(registry.filter(e => e.type === "surgeon").map(e => e.protocol_title.replace(/\s*[-–]\s*Phase.*$/i, "")))];
  assert.ok(titles.length >= 12, "expected 12 surgeon procedures, found " + titles.length);
  titles.forEach(title => assert.ok(H.detectSurgeries(title).length, "not detected: " + title));
  const expect = {
    "Advanced Meniscal Repair": "advanced_meniscal", "Simple Meniscal Repair": "simple_meniscal", "Meniscectomy": "meniscectomy",
    "Hip Labral Repair": "hip_labral", "Shoulder Labrum Repair": "shoulder_labrum", "MPFL Reconstruction": "mpfl",
    "Patellar tendon repair": "patella_quad", "Tibial plateau fracture ORIF": "tibial_plateau", "Achilles repair": "achilles", "Right TKR": "tka"
  };
  Object.entries(expect).forEach(([text, id]) => assert.strictEqual(H.detectSurgeries(text)[0].id, id, text));
});

test("NWB blocks weight-bearing lower-extremity work; no impact blocks hops", () => {
  assert.strictEqual(evaluateText("Achilles repair. NWB in boot.", byName("Squat")).status, "block");
  assert.strictEqual(evaluateText("Achilles repair. NWB in boot.", byName("Ankle Pumps")).status, "ok");
  assert.strictEqual(evaluateText("No impact or jumping until 16 weeks.", byName("Mini Hops")).status, "block");
});

test("Exercises on the non-operative limb are not blocked by operative-limb rules", () => {
  const text = "Right RCR PROM only.";
  const other = evaluateText(text, byName("Wand Shoulder Flexion"), "Left");
  assert.notStrictEqual(other.status, "block");
  assert.ok(other.reasons.every(r => r.kind === "wrong_side"), "only a wrong-side caution remains");
  assert.strictEqual(evaluateText(text, byName("Wand Shoulder Flexion"), "Right").status, "block");
  assert.strictEqual(evaluateText(text, byName("Wand Shoulder Flexion"), "Bilateral").status, "block");
});

test("Qualified restrictions warn instead of over-blocking (registry false positives)", () => {
  // Angle-limited: keep within the limit, do not block the whole joint.
  assert.strictEqual(evaluateText("Rotator cuff repair. No ER > 30°.", byName("Rotator Cuff Series")).status, "warn");
  assert.strictEqual(evaluateText("ACL reconstruction. No resisted knee extension past 60°.", byName("SL Balance Reaches")).status !== "block", true);
  // Motion-specific resisted limits apply to those motions only.
  const rcr = "Rotator cuff repair. No resisted elbow flex, shoulder flex, or supination horizontal adduction.";
  assert.notStrictEqual(evaluateText(rcr, byName("Band External Rotation at 0° with Towel Roll")).status, "block");
  // Duration-qualified avoidance is a caution.
  assert.strictEqual(evaluateText("Avoid standing and walking for a prolonged period.", byName("Standing Heel Raise (Double to Single Leg)")).status, "warn");
  // Mid-sentence "without" describes a progression; leading "without" still prohibits.
  assert.notStrictEqual(evaluateText("Begin in CAM boot > shoe with wedge > shoe without wedges.", byName("Squat")).status, "block");
  assert.strictEqual(evaluateText("Without squats for 6 weeks.", byName("Squat")).status, "block");
  // Long restriction clauses do not match a short alias inside them.
  assert.notStrictEqual(evaluateText("TKA. Avoid putting pillows or towel rolls under knee to promote extension.", byName("Prone Knee Extension Hang")).status, "block");
  // Scapular drills under shoulder PROM only: caution, not block. Glenohumeral active motion still blocks.
  assert.strictEqual(evaluateText("RCR: PROM only.", byName("Scapular Retraction and Depression")).status, "warn");
  assert.strictEqual(evaluateText("RCR: PROM only.", byName("Wand Shoulder Flexion")).status, "block");
});

// --- Catalog ------------------------------------------------------------------
test("Every exercise has a structured movementType and joint list", () => {
  catalog.forEach(e => {
    assert.ok(H.MOVEMENT_TYPES.includes(e.movementType), e.id + " movementType");
    assert.ok(Array.isArray(e.joints) && e.joints.length, e.id + " joints");
    assert.strictEqual(e.type, ["Stretch", "PROM"].includes(e.movementType) ? "stretch" : "strength", e.id + " type");
  });
  assert.strictEqual(byName("Standing Pendulum").movementType, "PROM");
  assert.strictEqual(byName("Standing Pendulum").type, "stretch");
});

test("Catalog cleanup: removed rows are gone and no protocol references a missing id", () => {
  const removals = Object.keys(require("../scripts/catalog_removals.json")).concat(["lat-pull-down", "dip-bar-assisted-slant-board-squat"]);
  const ids = new Set(catalog.map(e => e.id));
  removals.forEach(id => assert.ok(!ids.has(id), "still present: " + id));
  assert.ok(ids.has("lat-pulldown") && ids.has("dip-bar-assisted-slantboard-squat"));
  registry.forEach(entry => (entry.exercise_ids || []).forEach(id => assert.ok(ids.has(id), entry.id + " -> " + id)));
  registry.forEach(entry => Object.keys(entry.exercise_doses || {}).forEach(id => assert.ok(ids.has(id), entry.id + " dose -> " + id)));
  const { execFileSync } = require("child_process");
  execFileSync(process.execPath, [path.join(ROOT, "scripts/classify_catalog.js"), "--check"], { stdio: "pipe" });
});

// --- Zero-PHI -----------------------------------------------------------------
test("scrubPHI removes names, DOB/dates, phone, email, MRN and addresses", () => {
  const input = "Patient John Smith, DOB 03/14/1962, MRN 00482913. Call 425-555-0199 or jsmith@example.com. Lives at 1234 Maple Ave, Seattle WA 98101. Mrs. Garcia seen 2026-10-30.";
  const out = H.scrubPHI(input).text;
  ["John", "Smith", "03/14/1962", "00482913", "425-555-0199", "jsmith@example.com", "1234 Maple Ave", "98101", "Garcia", "2026-10-30"].forEach(s => assert.ok(!out.includes(s), "leaked " + s + " -> " + out));
  const clinical = "Phase 2, weeks 6-12. Flexion limited to 90 deg. 3 sets of 10 reps. Pt should ice 15 min.";
  assert.strictEqual(H.scrubPHI(clinical).text, clinical, "clinical text untouched");
});

// --- Compact share payload ------------------------------------------------------
test("Compact payload round-trips 20 exercises and stays QR-sized", () => {
  const ids = catalog.slice(0, 20).map(e => e.id);
  const program = {
    code: "PW-AB12", clinic: "PhysioWorks", directiveIds: ["ice", "elevation"], title: "Knee Phase 1", notes: "Ice after.",
    exercises: ids.map((id, i) => ({ id, sets: 3, reps: 10, hold: i % 2 ? "5s" : "", side: i % 3 ? "Left" : "Bilateral", freq: "Daily (7x/wk)" }))
      .concat([{ id: "custom", name: "Towel Roll Calf Stretch", sets: 2, reps: 3, hold: "30s", side: "Right", freq: "2x/day" }])
  };
  const enc = H.encodeCompactProgram(program);
  const dec = H.decodeCompactProgram(enc);
  assert.strictEqual(dec.exercises.length, 21);
  assert.strictEqual(dec.exercises[20].name, "Towel Roll Calf Stretch");
  assert.strictEqual(dec.exercises[1].side, "Left");
  assert.strictEqual(dec.exercises[1].hold, "5s");
  assert.strictEqual(dec.title, "Knee Phase 1");
  assert.deepStrictEqual(dec.directiveIds, ["ice", "elevation"]);
  assert.ok(/^[\x20-\x7e]+$/.test(enc), "ASCII only");
  const url = "https://karllange.github.io/physioworks-hep/patient.html#p=" + enc;
  assert.ok(url.length < 1200, "URL length " + url.length);
});

let failed = 0;
results.forEach(r => {
  console.log((r.ok ? "PASS " : "FAIL ") + r.name);
  if (!r.ok) { failed++; console.log("     " + (r.err && r.err.message)); }
});
console.log(`\n${results.length - failed}/${results.length} engine tests passed`);

if (process.argv.includes("--browser")) {
  const { execFileSync } = require("child_process");
  try { execFileSync(process.execPath, [path.join(__dirname, "browser.js")], { stdio: "inherit" }); }
  catch (err) { failed++; }
}
process.exit(failed ? 1 : 0);
