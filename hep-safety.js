/*
 * PhysioWorks HEP safety engine (Phase 1).
 * Pure functions, no DOM access. Runs in the browser (window.HEPSafety)
 * and in Node (require("./hep-safety.js")) so the same rules are unit-tested.
 *
 * Fail-safe rule: when the engine cannot tell whether a restriction applies,
 * it returns "warn", never a silent "ok".
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.HEPSafety = api;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const MOVEMENT_TYPES = ["PROM", "AAROM", "AROM", "Resisted", "Stretch"];
  const ACTIVE_TYPES = ["AAROM", "AROM", "Resisted"];
  const JOINTS = ["shoulder", "elbow", "wrist", "hand", "cervical", "thoracic", "lumbar", "hip", "knee", "ankle", "foot"];

  // ---------------------------------------------------------------------------
  // Text helpers
  // ---------------------------------------------------------------------------
  const ABBREVIATIONS = [
    [/\bslrs?\b/g, "straight leg raise"],
    [/\blaqs?\b/g, "long arc quad"],
    [/\bsaqs?\b/g, "short arc quad"],
    [/\btkes?\b/g, "terminal knee extension"],
    [/\brdls?\b/g, "romanian deadlift"],
    [/\bsl\b/g, "single leg"],
    [/\bdl\b/g, "double leg"],
    [/\bext\b\.?/g, "extension"],
    [/\bflex\b\.?/g, "flexion"],
    [/\babd\b\.?/g, "abduction"],
    [/\badd\b\.?(?=\s|$)/g, "adduction"],
    [/\bp\.?r\.?o\.?m\b/g, "prom"],
    [/\ba\.?a\.?r\.?o\.?m\b/g, "aarom"],
    [/\ba\.?r\.?o\.?m\b/g, "arom"],
    [/\bpassive range of motion\b/g, "prom"],
    [/\bactive assisted range of motion\b|\bactive[- ]assisted rom\b/g, "aarom"],
    [/\bactive range of motion\b|\bactive rom\b/g, "arom"],
    [/\bpassive rom\b/g, "prom"],
    [/\bexternal rotation\b/g, "er"],
    [/\binternal rotation\b/g, "ir"],
    [/\bhs\b/g, "hamstring"],
    [/\bquads\b/g, "quad"],
    [/\bdon'?t\b/g, "do not"],
    [/\bcan'?t\b|\bcannot\b/g, "can not"],
    [/\bw\/o\b/g, "without"],
    [/\bw\//g, "with "]
  ];

  function normalize(text) {
    let out = String(text || "").toLowerCase()
      .replace(/[\u2018\u2019]/g, "'")
      .replace(/[\u2013\u2014]/g, "-")
      .replace(/°/g, " deg ")
      .replace(/>=?|≥/g, " greater than ")
      .replace(/<=?|≤/g, " less than ");
    ABBREVIATIONS.forEach(([re, rep]) => { out = out.replace(re, rep); });
    return out.replace(/[^a-z0-9%\-\/'.,;:\n ]+/g, " ").replace(/[ \t]+/g, " ").trim();
  }

  const STOP = new Set(["a", "an", "the", "and", "or", "with", "of", "on", "at", "to", "for", "in", "into", "from", "your", "his", "her", "their", "is", "are", "be", "any", "all", "until", "x", "exercise", "exercises", "progression", "progressions", "variations", "variation", "reps", "rep", "sets", "set", "weeks", "week", "wks", "day", "days", "per", "as", "tolerated", "allowed", "permitted", "please", "patient", "pt"]);

  function stem(word) {
    if (word.length > 4 && word.endsWith("ies")) return word.slice(0, -3) + "y";
    if (word.length > 3 && /(ss|us)$/.test(word)) return word;
    if (word.length > 3 && word.endsWith("es") && /(ch|sh|x)es$/.test(word)) return word.slice(0, -2);
    if (word.length > 3 && word.endsWith("s")) return word.slice(0, -1);
    return word;
  }

  function tokens(text) {
    return normalize(text).split(/[^a-z0-9%]+/).filter(Boolean).filter(w => !STOP.has(w)).map(stem);
  }

  function sentences(text) {
    return String(text || "").replace(/\r/g, "").split(/(?<=[.;!?])\s+|\n+/).map(s => s.trim()).filter(Boolean);
  }

  // ---------------------------------------------------------------------------
  // Exercise classification (movementType, joints, motions, weight bearing)
  // ---------------------------------------------------------------------------
  const CATEGORY_JOINT = {
    knee: "knee", ankle: "ankle", shoulder: "shoulder", hip: "hip", lumbar: "lumbar", core: "lumbar",
    cervical: "cervical", thoracic: "thoracic", elbow_wrist: "elbow", hand: "hand", balance: "ankle"
  };

  const RULES = {
    stretch: /\bstretch|child'?s pose|thread the needle|open book|knee to chest|press-up|press up on elbow|lower trunk rotation|cat-camel|90\/90|greatest stretch|prone lying|sidebend|figure-4|piriformis|thomas|tfl|nerve glide|tendon gliding|knee hang|prone knee extension hang|rock backs?|foam roller thoracic|thoracic extension|lumbar extension|lumbar flexion|cervical prom|contract relax/,
    prom: /\bprom\b|\bpassive\b|pendulum|codman|arm hangs?|patellar glide|patella(r)? mob|\bcpm\b|knee hang|extension hang/,
    aarom: /\baarom\b|\bwand\b|\bcane\b|pulley|table slide|wall slides?(?! with band)|heel slide|ball assisted|physioball knee flexion|knee bend off table|ue assistance|aarom with physioball|seated knee bend|flexion on step|rolling patterns/,
    resisted: /\bband\b|resist|weight|\bdb\b|dumbbell|\bkb\b|kettlebell|cable|machine|press\b|presses|squat|lunge|deadlift|romanian|\brow\b|rows|curl|plank|bridge|hop|jump|plyo|step[- ]?(up|down)s?|step downs?|sled|shuttle|wall sit|leg press|push[- ]?ups?|pull[- ]?down|pulldown|carry|carries|farmer|chop|lift\b|pallof|copenhagen|nordic|hurdle|sprint|jog|run|cutting|agility|shuffle|ladder|decel|swing|superman|bird dog|dead bug|clamshell|marching|march\b|heel raise|toe raise|calf raise|isotonic|bench|trx|\bys\b|y\/t|i y t|scaption|full can|chest press|bicep|tricep|biceps|triceps|hip hike|hyperextension|kick|catch|taps|drops|walk outs|walking|walks|gait|stance|balance|romberg|weight shift|star drill|baps|reach|rotational|anti-rotation|tib bar|slider|putty|grip|squeeze|isometric|quad set|glute(al)? set|hamstring set|bracing|drawing-in|eccentric|straight leg raise|sidelying hip|side-lying hip|hip abduction|hip adduction|hip extension|hip flexion|serratus|retraction|external rotation|internal rotation|shoulder taps|rhythmic stabilization|d2 pattern|pnf|ube|halos|pass through|rotator cuff series|light isotonics|ckc|stool|toe curl|towel scrunch|toe spread|short foot|intrinsic|tibial rotation|great toe|toe lifts|holds?\b|mountain climber|lsd|lateral step|machine|activation|get up from floor|feet together|rowing/,
    arom: /\barom\b|active|circles?|circumduction|pumps?|range of motion|\brom\b|pronation|supination|chin tuck|pelvic tilt|tilts?|rotations?|unweighted|knee flexion|knee extension|long arc quad|short arc quad|marching|toe curl|toe lifts|toe spread|great toe|towel scrunch|short foot|seated cervical|wall hip flexion|seated hip flexion|standing hip flexion|standing knee flexion|tibial rotation|\bbike\b|nu-step|fallouts/
  };

  const ISOMETRIC = /isometric|straight leg raise|quad set|glute(al)? sets?|hamstring set|\bbracing\b|drawing-in|squeeze|\bholds?\b|wall sit|plank|kicking into physio ball/;
  const IMPACT = /\bhops?\b|jump|plyo|\bjog|\brun\b|running|sprint|bound|skip|agility|cutting|cone|shuffle|depth|snap down|ladder|decel|reactive|pro agility|weighted ball taps|ball catch|mini jumps|medicine ball drops/;
  const WEIGHT_BEARING = /squat|lunge|step|wall sit|stance|balance|heel raise|toe raise|calf raise|walk|gait|jog|\brun\b|running|sprint|hop|jump|deadlift|romanian|rdl|sled|star drill|standing baps|weighted baps|marching on foam|farmer|carry|carries|agility|cutting|shuffle|hurdle|tandem|romberg|weight shift|single leg|split|kb swing|swings|standing (heel|toe|hip|knee|gastroc|soleus|lumbar|sidebend)|decel|ladder|cone|retro walking|tm walking|treadmill|weight shifting|kickstand|slantboard|slant board|toe walks|heel walks|get up from floor|lateral step|forward step|closed chained|lsd|feet together|in the boot|crutches|bulgarian/;

  function inferJointsAndMotions(name, category) {
    const n = normalize(name);
    const joints = new Set();
    const motions = new Set();
    const add = (j, m) => { joints.add(j); if (m) motions.add(j + "_" + m); };

    // Shoulder
    if (/shoulder|scap(?!ulae)|rotator cuff|pendulum|codman|wand|pulley|sleeper|serratus|scaption|full can|\bys\b|trx ys|y\/t|i y t|y\/t\/i\/w|lat pull|pulldown|chest press|shoulder press|push press|bench press|bench progression|push[- ]?ups?|\brows?\b|rowing|d2|pnf|ube|arm hangs?|behind the back|halos|pass through|doorway|overhead|rhythmic stabilization|shoulder taps|walk outs|ball taps|ball catch|horizontal abduction|bicep|tricep/.test(n)) joints.add("shoulder");
    if (joints.has("shoulder")) {
      if (/flexion|wand|pulley|elevation|scaption|full can|overhead|press\b|\bys\b|y\/t|i y t|d2|wall slide|serratus|unweighted flex|pendulum|halos|flexion\/abduction/.test(n)) motions.add("shoulder_flexion");
      if (/abduction|scaption|full can|\bys\b|\bts\b|y\/t|i y t|horizontal abduction|d2|lateral raise|flexion\/abduction/.test(n)) motions.add("shoulder_abduction");
      if (/\ber\b|external|er\/ir|ir\/er|rotator cuff series|breakout|sleeper|90\/90/.test(n)) motions.add("shoulder_er");
      if (/\bir\b|internal|er\/ir|ir\/er|sleeper|behind the back|rotator cuff series/.test(n)) motions.add("shoulder_ir");
      if (/extension|\brows?\b|rowing|pull ?down|pulldown|behind the back|\bext\b/.test(n)) motions.add("shoulder_extension");
      if (/isometric|rhythmic stabilization|holds?/.test(n)) motions.add("shoulder_isometric");
    }
    // Elbow / wrist / hand
    if (/elbow|bicep|tricep|pronation|supination|curls and triceps|forearm/.test(n)) add("elbow", /bicep|curl|flexion/.test(n) ? "flexion" : (/tricep|extension/.test(n) ? "extension" : null));
    if (/wrist|forearm|pronation|supination/.test(n)) add("wrist", /extens/.test(n) ? "extension" : null);
    if (/hand|finger|tendon gliding|putty|grip|web space|thumb/.test(n)) joints.add("hand");
    // Spine
    if (/cervical|chin tuck|neck|upper trap|levator/.test(n)) add("cervical", /flexion/.test(n) ? "flexion" : (/extension|retraction/.test(n) ? "extension" : (/rotation|sidebend/.test(n) ? "rotation" : null)));
    if (/thoracic|open book|thread the needle/.test(n)) joints.add("thoracic");
    if (/lumbar|pelvic tilt|bird dog|dead bug|plank|curl-up|superman|cat-camel|child'?s pose|press-up|trunk rotation|bracing|drawing-in|core|chop|lift with resistance|pallof|anti-rotation|sidebends|hyperextension|mountain climber/.test(n)) add("lumbar", /flexion|knee to chest|curl-up|child/.test(n) ? "flexion" : (/extension|press-up|superman|hyperextension/.test(n) ? "extension" : (/rotation|chop|open book/.test(n) ? "rotation" : null)));
    // Hip
    if (/\bhip\b|glute|clamshell|bridge|piriformis|figure-4|thomas|tfl|adduction|abduction(?! .*shoulder)|copenhagen|deadlift|romanian|rdl|kb swing|swings|lunge|squat|step|march|straight leg raise|monster|side stepping|hip hike|90\/90|greatest stretch|runner'?s stretch|bike|nu-step|hyperextension|fallouts|knee to chest|bird dog|superman|mountain climber|get up from floor/.test(n)) {
      if (!(joints.has("shoulder") && /abduction|adduction/.test(n) && !/\bhip\b/.test(n))) {
        joints.add("hip");
        if (/hip flexion|march|straight leg raise|knee to chest|bike|nu-step|90\/90|squat|lunge|step|ball assisted hip flexion|wall hip flexion|seated hip flexion|standing hip flexion/.test(n)) motions.add("hip_flexion");
        if (/hip extension|bridge|deadlift|romanian|rdl|swing|prone hip|quadruped hip|hyperextension|superman|bird dog|thomas|hip flexor stretch/.test(n)) motions.add("hip_extension");
        if (/abduction|clamshell|side stepping|monster|sidelying hip abd|side-lying hip abd|fallouts|hip hike/.test(n)) motions.add("hip_abduction");
        if (/adduction|copenhagen|ball squeeze|ball at knees/.test(n)) motions.add("hip_adduction");
        if (/\bir\b|internal rotation|\ber\b|external rotation|rotations? on stool|hip rotation|piriformis|figure-4|clamshell|90\/90|circumduction|hip circles/.test(n)) motions.add("hip_rotation");
      }
    }
    // Knee (ignore positional words such as "from knees" or "half-kneeling")
    const kneeText = n.replace(/\b(?:from|on) (?:the )?knees\b|\bkneeling\b|\bquadruped\b|\bball at knees\b/g, " ");
    if (/knee|\bquads?\b|hamstring|leg curl|patellar|patella|heel slide|squat|lunge|step|wall sit|leg press|shuttle|nordic|sled|split|hurdle|hop|jump|jog|run|sprint|cutting|agility|kick|terminal|bike|nu-step|slantboard|slant board|deadlift|romanian|lsd|ckc|machine extension|dl extension|sl extension|single leg|double leg|straight leg raise|leg raise|tibial rotation|bridge with heels|get up from floor|feet together/.test(kneeText)) {
      joints.add("knee");
      if (/heel slide|hamstring curl|leg curl|knee flexion|knee bend|nordic|hamstring ball curl|ball curls|flexion on step|physioball knee flexion|squat|lunge|step|split|bike|nu-step|prone quad stretch|bridge with heels|wall slides/.test(n)) motions.add("knee_flexion");
      if (/long arc quad|short arc quad|terminal knee extension|knee extension|quad set|straight leg raise|leg press|squat|step|wall sit|shuttle|kick|sled|lunge|split|extension holds|dl extension|sl extension|machine extension|lsd|sit to stand|extension hang|knee hang/.test(n)) motions.add("knee_extension");
    }
    // Ankle / foot
    if (/ankle|calf|gastroc|soleus|heel raise|toe raise|toe walk|heel walk|baps|achilles|dorsiflexion|plantar|inversion|eversion|\binv\b|tib bar|4-way ankle|pumps|star drill|hop|jump|jog|run|sprint|cutting|agility|\bstance\b|\bbalance\b|romberg|walking|walks|\bgait\b|squat|lunge|step\b|steps|step[- ]|split|feet together|in the boot/.test(n)) {
      joints.add("ankle");
      if (/pumps|heel raise|toe raise|calf|gastroc|soleus|dorsiflexion|plantar|tib bar|toe walk|heel walk|4-way ankle|circles|baps|hop|jump/.test(n)) { motions.add("ankle_dorsiflexion"); motions.add("ankle_plantarflexion"); }
      if (/inversion|eversion|\binv\b|4-way ankle|circles|baps|circumduction/.test(n)) { motions.add("ankle_inversion"); motions.add("ankle_eversion"); }
    }
    if (/toe|foot|intrinsic|towel scrunch|short foot/.test(n)) joints.add("foot");

    if (!joints.size && CATEGORY_JOINT[category]) joints.add(CATEGORY_JOINT[category]);
    if (category === "elbow_wrist" && joints.has("elbow") && /wrist|hand/.test(n)) joints.add("wrist");
    return { joints: JOINTS.filter(j => joints.has(j)), motions: [...motions].sort() };
  }

  function classifyExercise(ex) {
    const name = String(ex && ex.name || "");
    const category = String(ex && ex.category || "").toLowerCase();
    const n = normalize(name);
    let movementType = null;
    let confident = true;
    // Mixed labels ("PROM/AROM") take the more active type so restrictions stay strict.
    if (/\barom\b/.test(n)) movementType = "AROM";
    else if (/\baarom\b/.test(n)) movementType = "AAROM";
    else if (RULES.prom.test(n)) movementType = "PROM";
    else if (RULES.stretch.test(n)) movementType = "Stretch";
    else if (RULES.aarom.test(n) && !/squat|band|resist|press/.test(n)) movementType = "AAROM";
    else if (RULES.resisted.test(n)) movementType = "Resisted";
    else if (RULES.arom.test(n)) movementType = "AROM";
    else if (ex && ex.type === "stretch") { movementType = "Stretch"; confident = false; }
    else { movementType = "Resisted"; confident = false; }
    // AROM wins over Resisted for named unloaded range-of-motion drills.
    if (movementType === "Resisted" && /\barom\b|\bactive\b|circles?|pumps?|seated cervical|chin tuck|pelvic tilt|toe curl|toe spread|toe lifts|great toe|unweighted|tibial rotation|long arc quad|short arc quad|wall hip flexion|seated hip flexion|standing hip flexion|standing knee flexion|knee circles|\bbike\b|nu-step|fallouts/.test(n) && !/band|resist|\bweight|weighted|machine|\bdb\b|\bkb\b|cable|ube/.test(n)) movementType = "AROM";
    const jm = inferJointsAndMotions(name, category);
    const isometric = ISOMETRIC.test(n);
    const impact = IMPACT.test(n);
    const lowerBody = jm.joints.some(j => ["hip", "knee", "ankle", "foot"].includes(j));
    const weightBearing = lowerBody && WEIGHT_BEARING.test(n) && !/seated|supine|prone|sidelying|side-lying|quadruped|hooklying|long sitting/.test(n);
    const chain = weightBearing || /leg press|shuttle|wall sit|closed chain|ckc|sled|terminal knee extension|bike|nu-step/.test(n) ? "closed" : "open";
    if (!jm.joints.length) confident = false;
    return {
      movementType,
      joints: jm.joints,
      motions: jm.motions,
      isometric,
      weightBearing,
      impact,
      chain,
      needsReview: !confident
    };
  }

  // Ensures an exercise object carries safety fields (catalog entries already do).
  function safetyProfile(ex) {
    if (ex && ex.movementType && Array.isArray(ex.joints)) {
      return {
        movementType: ex.movementType, joints: ex.joints, motions: ex.motions || [],
        isometric: !!ex.isometric, weightBearing: !!ex.weightBearing, impact: !!ex.impact,
        chain: ex.chain || "open", needsReview: !!ex.needsReview
      };
    }
    return classifyExercise(ex || {});
  }

  // ---------------------------------------------------------------------------
  // Protocol context: surgery, phase, operative side
  // ---------------------------------------------------------------------------
  const SURGERIES = [
    { id: "achilles", name: "Achilles Repair", joint: "ankle", re: /\bachilles(?:\s+tendon)?(?:\s+(?:repair|rupture|reconstruction|debridement))?\b/ },
    { id: "acl", name: "ACL Reconstruction", joint: "knee", re: /\bacl(?:-?r)?\b(?:[^.\n]{0,30}\b(?:reconstruction|recon|repair|graft)\b)?|\banterior cruciate\b/ },
    { id: "advanced_meniscal", name: "Advanced Meniscal Repair", joint: "knee", re: /\b(?:advanced|complex|radial|root|bucket[- ]handle)\b[^.\n]{0,25}\bmenisc(?:al|us)\b[^.\n]{0,10}\brepair\b|\bmenisc(?:al|us)\s+(?:root\s+)?repair\b[^.\n]{0,25}\b(?:advanced|complex|radial|root|bucket[- ]handle)\b/ },
    { id: "simple_meniscal", name: "Simple Meniscal Repair", joint: "knee", re: /\bmenisc(?:al|us)\s+repair\b/ },
    { id: "meniscectomy", name: "Meniscectomy", joint: "knee", re: /\b(?:partial\s+)?meniscectomy\b/ },
    { id: "mpfl", name: "MPFL Reconstruction", joint: "knee", re: /\bmpfl\b|\bmedial patellofemoral ligament\b/ },
    { id: "patella_quad", name: "Patella/Quad Tendon Repair", joint: "knee", re: /\b(?:patellar?|quad(?:riceps)?)\s+tendon\s+repair\b|\bpatella\s*\/\s*quad\b/ },
    { id: "tibial_plateau", name: "Tibial Plateau Fracture", joint: "knee", re: /\btibial plateau\b/ },
    { id: "tka", name: "Total Knee Arthroplasty (TKA)", joint: "knee", re: /\b(?:tka|tkr|total knee(?:\s+arthroplasty|\s+replacement)?)\b/ },
    { id: "hip_labral", name: "Hip Labral Repair", joint: "hip", re: /\bhip\b[^.\n]{0,25}\blabr(?:al|um)\b|\blabr(?:al|um)\b[^.\n]{0,25}\bhip\b|\bfai\b|\bhip arthroscopy\b/ },
    { id: "shoulder_labrum", name: "Shoulder Labrum Repair", joint: "shoulder", re: /\bbankart\b|\bslap\s+repair\b|\b(?:shoulder\s+)?labr(?:al|um)\s+repair\b|\bshoulder\b[^.\n]{0,25}\blabr(?:al|um)\b/ },
    { id: "rcr", name: "Rotator Cuff Repair (RCR)", joint: "shoulder", re: /\brcr\b|\brotator cuff repair\b|\bcuff repair\b/ },
    { id: "sad", name: "Subacromial Decompression", joint: "shoulder", re: /\bsubacromial decompression\b/, raw: /\bSAD\b/ },
    { id: "lumbar_fusion", name: "Lumbar Fusion", joint: "lumbar", re: /\b(?:lumbar fusion|spinal fusion|tlif|plif|alif)\b/ },
    { id: "lumbar_disc", name: "Lumbar Discectomy", joint: "lumbar", re: /\b(?:lumbar discectomy|microdiscectomy|discectomy)\b/ }
  ];

  function detectSurgeries(text) {
    const raw = String(text || "");
    const lowered = raw.toLowerCase().replace(/[\u2013\u2014]/g, "-");
    const found = [];
    SURGERIES.forEach(s => {
      const m = s.re.exec(lowered) || (s.raw && s.raw.exec(raw));
      if (!m) return;
      // "Meniscal repair" inside an advanced-repair phrase should not double count.
      if (s.id === "simple_meniscal" && found.some(f => f.id === "advanced_meniscal")) return;
      // Hip labral wins over the generic labrum rule when the hip is named.
      if (s.id === "shoulder_labrum" && found.some(f => f.id === "hip_labral") && !/shoulder|bankart|slap/.test(lowered)) return;
      found.push({ id: s.id, name: s.name, joint: s.joint, index: m.index, match: m[0] });
    });
    found.sort((a, b) => a.index - b.index);
    return found;
  }

  const ROMAN = { i: 1, ii: 2, iii: 3, iv: 4, v: 5, vi: 6, vii: 7 };
  const WORD_NUM = { one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7 };

  function detectPhase(text) {
    const t = String(text || "").replace(/[\u2013\u2014]/g, "-");
    const phases = [];
    const re = /\bphase\s*[:#-]?\s*(vii|vi|iv|v|i{1,3}|[1-7]|one|two|three|four|five|six|seven)\b/gi;
    let m;
    while ((m = re.exec(t))) {
      const token = m[1].toLowerCase();
      const n = ROMAN[token] || WORD_NUM[token] || Number(token);
      if (n >= 1 && n <= 7 && !phases.includes(n)) phases.push(n);
    }
    const weeks = [];
    const weekRes = [
      /\b(?:weeks?|wks?)\s*(\d{1,2})\s*(?:-|to|through)\s*(\d{1,2})\b/gi,
      /\b(\d{1,2})\s*(?:-|to|through)\s*(\d{1,2})\s*(?:weeks?|wks?)\b/gi
    ];
    weekRes.forEach(r => {
      let w;
      while ((w = r.exec(t))) {
        const a = Number(w[1]); const b = Number(w[2]);
        if (b >= a && !weeks.some(x => x[0] === a && x[1] === b)) weeks.push([a, b]);
      }
    });
    const single = /\b(?:week|wk)\s*(\d{1,2})\b(?!\s*(?:-|to|through))/i.exec(t);
    const months = /\b(\d{1,2})\s*(?:-|to)\s*(\d{1,2})\s*months?\b/i.exec(t);
    const parts = [];
    if (phases.length) parts.push("Phase " + phases[0]);
    if (weeks.length) parts.push("Weeks " + weeks[0][0] + "-" + weeks[0][1]);
    else if (single) parts.push("Week " + single[1]);
    if (months) parts.push(months[1] + "-" + months[2] + " Months");
    if (/\bacute\b/i.test(t) && !parts.length) parts.push("Acute");
    if (!parts.length) return null;
    return {
      number: phases.length ? phases[0] : null,
      phases,
      weeks: weeks.length ? weeks[0] : (single ? [Number(single[1]), Number(single[1])] : null),
      label: parts.join(", "),
      multiple: phases.length > 1
    };
  }

  const SIDE_WORD = /\b(left|right|bilateral|bilat|lt|rt|l|r)\b/;
  function sideFromWord(word) {
    const w = String(word || "").toLowerCase();
    if (w === "left" || w === "lt" || w === "l") return "Left";
    if (w === "right" || w === "rt" || w === "r") return "Right";
    if (w === "bilateral" || w === "bilat") return "Bilateral";
    return null;
  }

  const JOINT_WORDS = {
    knee: /\bknees?\b/, shoulder: /\bshoulders?\b/, hip: /\bhips?\b/, ankle: /\bankles?\b|\bachilles\b|\bfoot\b/, elbow: /\belbows?\b/, wrist: /\bwrists?\b/, lumbar: /\b(?:back|lumbar|spine)\b/
  };

  // Returns { side, confident, warnings[] }.
  function detectOperativeSide(text, surgeries) {
    const raw = String(text || "");
    const lowered = raw.toLowerCase();
    const warnings = [];
    const surgery = surgeries && surgeries[0];
    let side = null;
    if (surgery) {
      const sentenceStart = Math.max(lowered.lastIndexOf(".", surgery.index - 1), lowered.lastIndexOf("\n", surgery.index - 1)) + 1;
      const before = lowered.slice(Math.max(sentenceStart, surgery.index - 30), surgery.index);
      const afterEnd = lowered.indexOf(".", surgery.index + surgery.match.length);
      const after = lowered.slice(surgery.index + surgery.match.length, Math.min(afterEnd === -1 ? lowered.length : afterEnd, surgery.index + surgery.match.length + 25));
      const b = before.match(/\b(left|right|bilateral|bilat|lt|rt|l|r)\b[^a-z]*(?:[a-z]+\s*){0,2}$/);
      const a = after.match(/^\s*(?:,|\(|of the|on the|-)?\s*\(?\b(left|right|bilateral|bilat|lt|rt|l|r)\b/);
      side = sideFromWord((b && b[1]) || (a && a[1]));
    }
    if (!side) {
      // Fall back to a side named next to the operative joint, then any side word.
      const joint = surgery ? surgery.joint : null;
      const jointRe = joint && JOINT_WORDS[joint];
      const near = jointRe ? new RegExp("\\b(left|right|bilateral)\\s+" + jointRe.source.replace(/\\b/g, "")).exec(lowered) : null;
      if (near) side = sideFromWord(near[1]);
      else {
        const hasLeft = /\bleft\b/.test(lowered);
        const hasRight = /\bright\b/.test(lowered);
        if (/\bbilateral\b/.test(lowered)) side = "Bilateral";
        else if (hasLeft && !hasRight) side = "Left";
        else if (hasRight && !hasLeft) side = "Right";
        else if (hasLeft && hasRight) {
          warnings.push("Both left and right are mentioned and the surgical side is unclear. Confirm the operative side.");
          return { side: "Unknown", confident: false, warnings };
        }
      }
    }
    if (!side) return { side: "Unknown", confident: false, warnings: surgery ? ["Operative side not stated. Confirm the side before printing."] : [] };
    // Wrong-side check: the opposite side mentioned with the operative joint.
    if (surgery && (side === "Left" || side === "Right")) {
      const other = side === "Left" ? "right" : "left";
      const jointRe = JOINT_WORDS[surgery.joint];
      if (jointRe) {
        const re = new RegExp("\\b" + other + "\\s+" + jointRe.source.replace(/\\b/g, ""), "i");
        const m = re.exec(raw);
        if (m) warnings.push("Wrong-side check: the text mentions \"" + m[0] + "\" but the surgical side is " + side + ". Confirm which side each exercise is for.");
      }
    }
    return { side, confident: true, warnings };
  }

  // ---------------------------------------------------------------------------
  // Restriction parsing
  // ---------------------------------------------------------------------------
  const NEG_BEFORE = /\b(?:no|avoid|avoiding|do not|does not|should not|must not|never|not to|refrain from|hold off on|prohibited:?|contraindicated:?|not allowed to|nothing)\b/;
  const NEG_AFTER = /\b(?:not allowed|not permitted|is prohibited|are prohibited|prohibited|contraindicated|to be avoided|should be avoided|must be avoided|not recommended|is not allowed|are not allowed|not yet|on hold)\b/;
  const MOTION_WORDS = [
    ["flexion", /\bflexion\b|\bflex\b|\bbend(?:ing)?\b/], ["extension", /\bextension\b/], ["abduction", /\babduction\b/],
    ["adduction", /\badduction\b/], ["er", /\ber\b/], ["ir", /\bir\b/], ["rotation", /\brotation\b/],
    ["dorsiflexion", /\bdorsiflexion\b/], ["plantarflexion", /\bplantar ?flexion\b/]
  ];

  function jointInText(t) {
    for (const [joint, re] of Object.entries(JOINT_WORDS)) if (re.test(t)) return joint;
    if (/\bcervical\b|\bneck\b/.test(t)) return "cervical";
    return null;
  }

  function motionKeys(t, joint) {
    const keys = [];
    MOTION_WORDS.forEach(([word, re]) => {
      if (!re.test(t)) return;
      if (word === "rotation") { keys.push(joint + "_er", joint + "_ir", joint + "_rotation"); return; }
      keys.push(joint + "_" + word);
    });
    return keys;
  }

  function clip(text) {
    const s = String(text || "").replace(/\s+/g, " ").trim();
    return s.length > 160 ? s.slice(0, 157) + "…" : s;
  }

  // Parse free text (protocol, notes, dictation) into structured rules.
  // ctx: { joint } default operative joint, from the detected surgery.
  function parseRestrictions(text, ctx) {
    const context = ctx || {};
    const defaultJoint = context.joint || null;
    const rules = [];
    const seen = new Set();
    const push = rule => {
      const key = rule.kind + "|" + (rule.joint || "") + "|" + (rule.motions || []).join(",") + "|" + (rule.phrase || "") + "|" + rule.source;
      if (seen.has(key)) return;
      seen.add(key);
      rules.push(rule);
    };
    sentences(text).forEach(sentence => {
      const t = normalize(sentence);
      const named = detectSurgeries(sentence)[0];
      const joint = jointInText(t) || (named ? named.joint : null) || defaultJoint;
      const source = clip(sentence);

      // No open-chain knee extension (ACL): blocks open-chain active knee extension.
      if (/\b(?:no|avoid|do not)\s+(?:open[- ]chain|okc)\b[^.;]{0,30}\bextension\b/.test(t)) {
        const j = jointInText(t) || joint || "knee";
        push({ kind: "no_okc_extension", joint: j, motions: [j + "_extension"], source, severity: "block" });
      }

      // PROM only / passive only
      if (/\bprom only\b|\bpassive (?:motion |rom |range )?only\b|\bonly prom\b|\bpassive only\b/.test(t)) {
        push({ kind: "prom_only", joint, source, severity: joint ? "block" : "warn" });
      }
      // AAROM only => no AROM or resisted
      if (/\baarom only\b|\bonly aarom\b/.test(t)) push({ kind: "aarom_only", joint, source, severity: joint ? "block" : "warn" });
      const resistedTail = /\bno resist(?:ed|ance)?\s+([^.;]{0,90})/.exec(t);
      const resistedMotions = resistedTail && MOTION_WORDS.some(([, re]) => re.test(resistedTail[1]));
      if (resistedMotions) {
        // "No resisted elbow flex, shoulder flex, or horizontal adduction" / "No resisted knee extension past 60"
        const angleOnly = /\b(?:past|beyond|greater than|over|more than|exceeding|less than|below)\s*\d{1,3}/.test(resistedTail[1]);
        let current = jointInText(resistedTail[1]) || joint;
        resistedTail[1].split(/,|\bor\b|\band\b|\//).forEach(segment => {
          current = jointInText(segment) || current;
          const motions = current ? motionKeys(segment, current) : [];
          if (!motions.length) return;
          push({ kind: "no_resisted_motion", joint: current, motions, source, severity: current && !angleOnly ? "block" : "warn" });
        });
      } else if (/\barom only\b|\bonly arom\b|\bno resist(?:ed|ance)?\b|\bno strengthening\b|\bno (?:weights|loading|lifting)\b|\bno resisted\b/.test(t) && !/\baarom only\b/.test(t)) {
        push({ kind: "no_resisted", joint, source, severity: joint ? "block" : "warn" });
      }
      // No AROM / no active motion (optionally a specific motion)
      const activeRe = /\b(?:no|avoid|do not|without|not allowed)\s+(?:any\s+)?(?:active|arom|active-assisted|aarom)\b([^,.;]{0,40})/g;
      let am;
      while ((am = activeRe.exec(t))) {
        const tail = am[1] || "";
        const j = jointInText(tail) || joint;
        const motions = j ? motionKeys(tail, j) : [];
        push({ kind: "no_active", joint: j, motions, includesAAROM: !/aarom|active-assisted/.test(am[0]) || true, source, severity: j ? "block" : "warn" });
      }
      // "Active X not allowed"
      const activeAfter = /\bactive\s+([a-z ]{0,30}?)\s+(?:is |are )?(?:not allowed|not permitted|prohibited|contraindicated)/.exec(t);
      if (activeAfter) {
        const j = jointInText(activeAfter[1]) || joint;
        push({ kind: "no_active", joint: j, motions: j ? motionKeys(activeAfter[1], j) : [], source, severity: j ? "block" : "warn" });
      }
      // No ROM at all / immobilized
      if (/\bno (?:rom|range of motion|motion)\b|\bimmobiliz/.test(t)) push({ kind: "no_motion", joint, source, severity: joint ? "block" : "warn" });

      // Motion limits: "flexion limited to 90", "no ER past 30", "ER to 30 deg max"
      const limitRe = /\b(flexion|extension|abduction|adduction|er|ir|rotation)\b[^.;,]{0,25}?\b(?:limited to|limit(?:ed)?|restricted to|not to exceed|do not exceed|no more than|max(?:imum)?|past|beyond|greater than|>|<|under|up to)\s*(\d{1,3})/g;
      let lm;
      while ((lm = limitRe.exec(t))) {
        const j = jointInText(t) || joint;
        if (!j) { push({ kind: "motion_limit", joint: null, motions: [], source, severity: "warn" }); continue; }
        push({ kind: "motion_limit", joint: j, motions: motionKeys(lm[1], j), limit: Number(lm[2]), source, severity: "warn" });
      }
      // "No flexion" / "avoid ER" without a number and without "active" => block that motion for all types
      const noMotion = /\b(?:no|avoid|do not)\s+(?:passive\s+|resisted\s+)?(flexion|extension|abduction|adduction|er|ir|rotation)\b(?!\s+(?:past|beyond|greater|more|>|over|exceeding))/.exec(t);
      if (noMotion && !/\b(?:no|avoid|do not)\s+(?:any\s+)?active\b/.test(t)) {
        const j = jointInText(t) || joint;
        const resistedOnly = /resisted/.test(noMotion[0]);
        push({ kind: resistedOnly ? "no_resisted_motion" : "no_motion_dir", joint: j, motions: j ? motionKeys(noMotion[1], j) : [], source, severity: j ? "block" : "warn" });
      }

      // Weight bearing
      if (/\bnwb\b|\bnon[- ]?weight[- ]?bearing\b|\bno weight[- ]?bearing\b/.test(t) && !/\bno(?:t)? nwb\b/.test(t)) push({ kind: "nwb", joint: joint || "lower", source, severity: "block" });
      else if (/\bttwb\b|\btoe[- ]touch\b|\bpwb\b|\bpartial weight[- ]?bearing\b|\bfoot flat\b|\bffwb\b/.test(t)) push({ kind: "limited_wb", joint: joint || "lower", source, severity: "warn" });
      if (/\bno (?:impact|running|jumping|jogging|plyometrics?|hopping|cutting|pivoting)\b|\bavoid (?:impact|running|jumping|plyometrics?)\b/.test(t)) push({ kind: "no_impact", joint: null, source, severity: "block" });
      if (/\bhip precautions?\b|\bposterior hip\b|\bhip past 90\b/.test(t)) push({ kind: "hip_precautions", joint: "hip", source, severity: "warn" });
      if (/\b(?:no|do not)\s+lift(?:ing)?\b[^.;]{0,30}\b\d+\s*(?:lbs?|pounds?|kg)\b|\blifting restriction/.test(t)) push({ kind: "lift_limit", joint, source, severity: "warn" });

      // Negated exercise phrases, e.g. "Ankle pumps not allowed", "no squats", "avoid lunges".
      t.split(/[.;:\n]/).forEach(rawClause => {
        // A clause that opens with "without" is a prohibition ("Without squats for 6 weeks");
        // mid-clause "without" describes a progression ("shoe without wedges") and is ignored.
        const clause = rawClause.replace(/^\s*without\b/, "no");
        const durationOnly = /\b(?:prolonged|long periods?|extended periods?|too long|too much|excessive)\b/.test(clause);
        const negSeverity = durationOnly ? "warn" : "block";
        const before = new RegExp(NEG_BEFORE.source + "\\s+(?:perform(?:ing)?\\s+|doing\\s+|any\\s+)?([a-z0-9 ,/'-]{3,80})", "g");
        let bm;
        while ((bm = before.exec(clause))) {
          const list = bm[1].split(/\b(?:but|until|unless|except|ok|okay|may|can|begin|start|then|after|before|while|for)\b/)[0];
          list.split(/,|\bor\b|\band\b|\/|\bnor\b/).map(s => s.trim()).filter(s => s.length > 2).forEach(phrase => {
            push({ kind: "negated", phrase, joint: null, source, severity: negSeverity });
          });
        }
        const afterRe = new RegExp("([a-z0-9 /'-]{3,60}?)\\s+(?:is\\s+|are\\s+)?" + NEG_AFTER.source, "g");
        let fm;
        while ((fm = afterRe.exec(clause))) {
          fm[1].split(/,|\band\b|\bor\b|\//).map(seg => seg.replace(/^\s*(?:exercises?|performing|doing)\s+/, "").trim())
            .filter(seg => seg.length > 2)
            .forEach(phrase => push({ kind: "negated", phrase, joint: null, source, severity: negSeverity }));
        }
      });
    });
    return rules;
  }

  // ---------------------------------------------------------------------------
  // Evaluation
  // ---------------------------------------------------------------------------
  const GENERIC_PHRASES = /^(?:pain|more|more than|than|weight|weights|more than \d+.*|lifting.*|driving|heat|ice|swelling|brace|sling|crutches|boot|the brace|limit|limits|restriction|restrictions|exercise|exercises|activities|activity|sports?|return|progression)$/;

  function exerciseKeyTokenSets(ex) {
    const keys = [ex.name].concat(Array.isArray(ex.aliases) ? ex.aliases : []).filter(Boolean);
    return keys.map(k => new Set(tokens(k))).filter(s => s.size);
  }

  function phraseMatchesExercise(phrase, ex) {
    const p = normalize(phrase);
    if (!p || GENERIC_PHRASES.test(p)) return false;
    const ptoks = tokens(p);
    if (!ptoks.length) return false;
    // Motion/type words are handled by structured rules, not by name matching.
    const motionOnly = ptoks.every(w => /^(active|passive|arom|aarom|prom|flexion|extension|abduction|adduction|er|ir|rotation|rom|motion|range|resisted|resistance|knee|shoulder|hip|ankle|elbow|wrist|past|beyond|deg|degree|open|chain|closed|okc|ckc|limit|limited|greater|than|full|end|\d+%?)$/.test(w));
    if (motionOnly) return false;
    const pset = new Set(ptoks);
    return exerciseKeyTokenSets(ex).some(kset => {
      const k = [...kset];
      const allKInP = k.every(w => pset.has(w)) && ptoks.length <= k.length + 3;
      const allPInK = ptoks.every(w => kset.has(w));
      return allKInP || (allPInK && ptoks.some(w => w.length > 3));
    });
  }

  function jointsOverlap(rule, profile) {
    if (!rule.joint) return null; // unknown joint
    if (rule.joint === "lower") return profile.joints.some(j => ["hip", "knee", "ankle", "foot"].includes(j));
    return profile.joints.includes(rule.joint);
  }

  // ctx: { surgicalSide: "Left"|"Right"|"Bilateral"|"Unknown", surgicalJoint }
  function evaluateExercise(ex, rules, ctx, itemSide) {
    const profile = safetyProfile(ex);
    const context = ctx || {};
    const reasons = [];
    const add = (level, rule, why) => reasons.push({ level, kind: rule.kind, why, source: rule.source });
    // Exercises on the non-operative limb are not limited by operative-limb rules.
    const otherLimb = itemSide && (itemSide === "Left" || itemSide === "Right")
      && (context.surgicalSide === "Left" || context.surgicalSide === "Right")
      && itemSide !== context.surgicalSide;

    (rules || []).forEach(rule => {
      if (rule.kind === "negated") {
        if (phraseMatchesExercise(rule.phrase, ex)) {
          if (rule.severity === "warn") add("warn", rule, "Restriction limits this activity (\"" + rule.phrase + "\"); keep it brief.");
          else add("block", rule, "Restriction names this exercise (\"" + rule.phrase + "\").");
        }
        return;
      }
      if (otherLimb && rule.joint && rule.joint !== "lumbar") return;
      const overlap = jointsOverlap(rule, profile);
      const type = profile.movementType;
      const active = ACTIVE_TYPES.includes(type);
      const motionHit = (rule.motions || []).length ? rule.motions.some(m => profile.motions.includes(m)) : true;
      const primaryJoint = profile.joints.length === 1 || CATEGORY_JOINT[String(ex && ex.category || "").toLowerCase()] === rule.joint;
      const scapularOnly = rule.joint === "shoulder" && /\bscap/.test(normalize(ex && ex.name))
        && !profile.motions.some(m => /^shoulder_(flexion|extension|abduction|adduction|er|ir|rotation)$/.test(m));
      const motionUnknown = (rule.motions || []).length > 0 && primaryJoint && !profile.isometric
        && !profile.motions.some(m => m.startsWith((rule.joint || "") + "_"));
      switch (rule.kind) {
        case "prom_only":
        case "no_motion": {
          const allowed = rule.kind === "prom_only" ? ["PROM"] : [];
          if (overlap === null) { if (!allowed.includes(type)) add("warn", rule, "Restriction applies to an unstated joint; confirm this exercise is allowed."); break; }
          if (overlap && !allowed.includes(type) && scapularOnly) { add("warn", rule, "Scapular exercise while the shoulder is " + (rule.kind === "prom_only" ? "PROM only" : "immobilized") + "; confirm it is allowed."); break; }
          if (overlap && !allowed.includes(type)) add(rule.severity, rule, rule.kind === "prom_only" ? type + " exercise while " + rule.joint + " is PROM only." : "No motion allowed at the " + rule.joint + ".");
          break;
        }
        case "aarom_only":
          if (overlap === null) { if (["AROM", "Resisted"].includes(type)) add("warn", rule, "AAROM-only restriction with an unstated joint."); break; }
          if (overlap && ["AROM", "Resisted"].includes(type)) add(rule.severity, rule, type + " exercise while " + rule.joint + " is AAROM only.");
          break;
        case "no_resisted":
          if (overlap === null) { if (type === "Resisted") add("warn", rule, "No-resistance restriction with an unstated joint."); break; }
          if (overlap && type === "Resisted") add(rule.severity, rule, "Resisted exercise at the " + rule.joint + " is restricted.");
          break;
        case "no_active": {
          if (overlap === null) { if (active) add("warn", rule, "No-active-motion restriction with an unstated joint."); break; }
          if (!overlap || !active) break;
          if (scapularOnly) { add("warn", rule, "Scapular exercise under a no-active-shoulder restriction; confirm it is allowed."); break; }
          if ((rule.motions || []).length && !motionHit) { if (motionUnknown) add("warn", rule, "Motion for this exercise is unclear; confirm it avoids the restricted motion."); break; }
          if (profile.isometric) { add("warn", rule, "Isometric at a joint with an active-motion restriction; confirm it is allowed."); break; }
          if (profile.chain === "closed" && (rule.motions || []).length) { add("warn", rule, "Closed-chain exercise uses the restricted motion; confirm it is allowed."); break; }
          add(rule.severity, rule, "Active " + (rule.motions && rule.motions.length ? rule.motions.join("/").replace(/_/g, " ") : rule.joint + " motion") + " is restricted.");
          break;
        }
        case "no_motion_dir":
        case "no_resisted_motion": {
          if (overlap === null || !rule.joint) { add("warn", rule, "Motion restriction with an unstated joint; confirm."); break; }
          if (!overlap) break;
          if (rule.kind === "no_resisted_motion" && type !== "Resisted") break;
          if (motionHit && (rule.motions || []).length) add(rule.severity, rule, (rule.motions || []).join("/").replace(/_/g, " ") + " is restricted.");
          else if (motionUnknown) add("warn", rule, "Motion for this exercise is unclear; confirm it avoids the restricted motion.");
          break;
        }
        case "no_okc_extension":
          if (overlap && ACTIVE_TYPES.includes(type) && profile.chain === "open" && profile.motions.includes(rule.motions[0])) {
            if (profile.isometric) add("warn", rule, "Isometric knee extension under an open-chain restriction; confirm it is allowed.");
            else add("block", rule, "Open-chain extension is restricted.");
          }
          break;
        case "motion_limit":
          if (overlap === null) { add("warn", rule, "ROM limit with an unstated joint; keep within the limit."); break; }
          if (overlap && (motionHit || motionUnknown)) add("warn", rule, "ROM limit applies" + (rule.limit != null ? " (" + rule.limit + "°)" : "") + "; keep within the limit.");
          break;
        case "nwb":
          if (profile.weightBearing && (overlap || rule.joint === "lower")) add("block", rule, "Weight-bearing exercise while non-weight bearing.");
          break;
        case "limited_wb":
          if (profile.weightBearing && (overlap || rule.joint === "lower")) add("warn", rule, "Weight-bearing exercise under a limited weight-bearing order.");
          break;
        case "no_impact":
          if (profile.impact) add("block", rule, "Impact exercise is restricted.");
          break;
        case "hip_precautions":
          if (profile.joints.includes("hip") && profile.motions.some(m => /hip_(flexion|rotation|adduction)/.test(m))) add("warn", rule, "Hip precautions: check flexion, adduction and rotation limits.");
          break;
        case "lift_limit":
          if (type === "Resisted" && (overlap || overlap === null)) add("warn", rule, "Lifting limit: keep resistance within the surgeon limit.");
          break;
        default:
          break;
      }
    });
    if (profile.needsReview && (rules || []).some(r => r.kind !== "negated")) {
      reasons.push({ level: "warn", kind: "classification", why: "Exercise not fully classified; confirm against the restrictions.", source: "" });
    }
    if (context.surgicalJoint && (context.surgicalSide === "Left" || context.surgicalSide === "Right")
        && (itemSide === "Left" || itemSide === "Right") && itemSide !== context.surgicalSide
        && profile.joints.includes(context.surgicalJoint)) {
      reasons.push({ level: "warn", kind: "wrong_side", why: "Set to " + itemSide + " but the surgical side is " + context.surgicalSide + ".", source: "" });
    }
    const status = reasons.some(r => r.level === "block") ? "block" : (reasons.length ? "warn" : "ok");
    return { status, reasons, profile };
  }

  // Full protocol parse used by the ingest modal and by tests.
  function analyzeProtocolText(text) {
    const surgeries = detectSurgeries(text);
    const surgery = surgeries[0] || null;
    const phase = detectPhase(text);
    const sideInfo = detectOperativeSide(text, surgeries);
    const rules = parseRestrictions(text, { joint: surgery ? surgery.joint : null });
    const warnings = [].concat(sideInfo.warnings);
    if (surgeries.length > 1) warnings.push("More than one procedure detected (" + surgeries.map(s => s.name).join(", ") + "). Confirm the primary procedure.");
    if (phase && phase.multiple) warnings.push("More than one phase found (" + phase.phases.map(n => "Phase " + n).join(", ") + "). Exercises from every phase were matched; review before applying.");
    return { surgeries, surgery, phase, side: sideInfo.side, sideConfident: sideInfo.confident, rules, warnings };
  }

  // ---------------------------------------------------------------------------
  // Zero-PHI scrubber
  // ---------------------------------------------------------------------------
  const MONTHS = "jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?";
  const PHI_RULES = [
    { type: "email", re: /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi },
    { type: "dob", re: /\b(?:dob|d\.o\.b\.?|date of birth|born|birthdate|birthday)\b\s*[:#-]?\s*[^\n,;]{0,24}/gi },
    { type: "ssn", re: /\b\d{3}-\d{2}-\d{4}\b/g },
    { type: "phone", re: /(?:\+?1[\s.-]?)?\(?\b\d{3}\)?[\s.-]?\d{3}[\s.-]\d{4}\b/g },
    { type: "mrn", re: /\b(?:mrn|mr#|medical record(?: number| no\.?| #)?|chart(?: number| no\.?| #)?|acct|account(?: number| no\.?| #)?|patient id|pt id|member id|policy(?: number)?)\b\s*[:#-]?\s*[A-Z0-9-]{3,}/gi },
    { type: "date", re: /\b\d{1,2}[\/.-]\d{1,2}[\/.-](?:\d{4}|\d{2})\b/g },
    { type: "date", re: /\b(?:19|20)\d{2}[\/.-]\d{1,2}[\/.-]\d{1,2}\b/g },
    { type: "date", re: new RegExp("\\b(?:" + MONTHS + ")\\.?\\s+\\d{1,2}(?:st|nd|rd|th)?,?\\s+(?:19|20)\\d{2}\\b", "gi") },
    { type: "date", re: new RegExp("\\b\\d{1,2}(?:st|nd|rd|th)?\\s+(?:" + MONTHS + ")\\.?,?\\s+(?:19|20)\\d{2}\\b", "gi") },
    { type: "date", re: /\b(?:1[0-2]|0?[1-9])\/(?:3[01]|[12]\d|0?[1-9])\b(?!\s*(?:pain|nprs|vas))/g, skip: (m, after) => /\/10$/.test(m) || (/\/[2348]$/.test(m) && /^\s+[a-z]/.test(after)) },
    { type: "date", re: new RegExp("\\b(?:" + MONTHS.replace("|may", "") + ")\\.?\\s+\\d{1,2}(?:st|nd|rd|th)?\\b", "gi") },
    { type: "address", re: /\b\d{1,6}\s+(?:[A-Z][a-z0-9]+\.?\s+){1,4}(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|Lane|Ct|Court|Way|Pl|Place|Hwy|Highway|Pkwy|Parkway|Cir|Circle|Ter|Terrace|Loop|Trl|Trail)\b\.?(?:\s*(?:#|Apt|Unit|Suite)\s*\w+)?/g },
    { type: "address", re: /\b(?:WA|OR|CA|ID|AK|NV|AZ|TX|NY|FL)\s+\d{5}(?:-\d{4})?\b/g },
    { type: "name", re: /\b(?:[Pp]atient|[Pp]t|PT|[Cc]lient|M(?:r|rs|s|iss|x)|MR|MRS|MS)\b\.?(?:\s*[Nn]ame)?(?:\s*[:,-]\s*|\s+)((?:[A-Z][a-zA-Z'’-]+)(?:\s+[A-Z][a-zA-Z'’-]+){0,2})/g, group: 1 },
    { type: "name", re: /\bname\s*[:=-]\s*([A-Za-z'’-]+(?:\s+[A-Za-z'’-]+){0,2})/gi, group: 1 },
    { type: "id", re: /\b\d{7,}\b/g }
  ];
  // Words that commonly follow "pt"/"patient" and are not names.
  const NAME_FALSE_POSITIVES = /^(?:Should|Will|May|Can|Is|Was|To|Education|Ed|Edu|Instructions?|Tolerates?|Tolerated|Reports?|Demonstrates?|Performs?|Must|Needs?|Has|Had|Wears?|Using|Uses?|Able|Ambulates?|Home|Program|Exercise|Exercises|Goals?|Status|Phase|Protocol|PT|Ice|Heat|Daily|Weeks?|Week|The|A|An|And|With|Without|Per|Post|Pre|Op|Surgery|Surgeon|Left|Right|Bilateral)$/;

  function scrubPHI(text) {
    let out = String(text == null ? "" : text);
    const found = [];
    PHI_RULES.forEach(rule => {
      out = out.replace(rule.re, (match, ...args) => {
        const g1 = rule.group ? args[0] : undefined;
        const whole = args[args.length - 1];
        const offset = args[args.length - 2];
        if (rule.skip && rule.skip(match, String(whole).slice(offset + match.length, offset + match.length + 12))) return match;
        if (rule.group) {
          const words = String(g1 || "").split(/\s+/);
          if (!words.length || NAME_FALSE_POSITIVES.test(words[0])) return match;
          found.push(rule.type);
          return match.replace(g1, "[removed]");
        }
        found.push(rule.type);
        return "[removed]";
      });
    });
    return { text: out, removed: found.length, types: [...new Set(found)] };
  }

  // ---------------------------------------------------------------------------
  // Compact share payload (v2): "2~<code>~<clinic>~<directive ids>~<items>~<title>~<notes>"
  // Item: id:sets:reps:hold:side[:freq]   custom item: "!" + urlencoded name + same fields
  // ---------------------------------------------------------------------------
  const FREQ_CODES = { D: "Daily (7x/wk)", W: "3-4x/week", T: "2-3x/day", B: "2x/day", O: "1-2x/day" };
  const SIDE_CODES = { L: "Left", R: "Right", B: "Bilateral", U: "Unilateral" };

  function encField(v) {
    return encodeURIComponent(String(v == null ? "" : v)).replace(/[~:;!*'()]/g, c => "%" + c.charCodeAt(0).toString(16).toUpperCase());
  }
  function decField(v) {
    try { return decodeURIComponent(String(v || "")); } catch (e) { return String(v || ""); }
  }

  // Clinical directive presets. Share links carry only these ids; keep in sync with index.html.
  const DIRECTIVE_PRESETS = [
    { id: "ice", icon: "\u{1F9CA}", text: "Use ice on the affected extremity for 20 min, 2-3x/day (max 1x/hour)." },
    { id: "heat", icon: "\u{1F525}", text: "Use moist heat for 15-20 min prior to exercises or for stiffness." },
    { id: "elevation", icon: "\u{1F4D0}", text: "Elevate your affected extremity against gravity / above heart level as much as possible." },
    { id: "sleep", icon: "\u{1F6CF}\uFE0F", text: "Sleep propped at a ~45-degree angle with supportive pillows." },
    { id: "weight", icon: "\u26A0\uFE0F", text: "Per surgeon orders: Do not lift anything > 10 lbs with your affected extremity." },
    { id: "hip", icon: "\u{1F6D1}", text: "Hip precautions: Do not bend hip past 90\u00B0, do not cross legs, and do not rotate foot inward." },
    { id: "nsaid", icon: "\u{1F48A}", text: "Consider OTC anti-inflammatories (NSAIDs) with food for the next 3 days; clear with your MD or pharmacist if any concerns." }
  ];

  function encodeCompactProgram(program, opts) {
    const options = opts || {};
    const freqToCode = Object.fromEntries(Object.entries(FREQ_CODES).map(([k, v]) => [v, k]));
    const sideToCode = Object.fromEntries(Object.entries(SIDE_CODES).map(([k, v]) => [v, k]));
    const items = (program.exercises || []).map(item => {
      const hold = String(item.hold == null ? "" : item.hold).replace(/\s+/g, "");
      const fields = [encField(item.sets), encField(item.reps), encField(hold), sideToCode[item.side] || "B"];
      const freq = freqToCode[item.freq];
      if (freq) fields.push(freq);
      else if (item.freq) fields.push("x" + encField(item.freq));
      const head = item.id && item.id !== "custom" ? item.id : "!" + encField(item.name || "Exercise");
      return [head].concat(fields).join(":");
    }).join(";");
    const parts = [
      "2",
      encField(program.code || ""),
      encField(program.clinic || ""),
      (program.directiveIds || []).join(","),
      items,
      options.includeTitle === false ? "" : encField(program.title || ""),
      options.includeNotes === false ? "" : encField(program.notes || ""),
      options.includeCustomDirectives === false ? "" : (program.customDirectives || []).map(encField).join(",")
    ];
    while (parts.length && parts[parts.length - 1] === "") parts.pop();
    return parts.join("~");
  }

  function decodeCompactProgram(str) {
    const parts = String(str || "").split("~");
    if (parts[0] !== "2") throw new Error("Unsupported share format");
    const exercises = (parts[4] || "").split(";").filter(Boolean).map(chunk => {
      const f = chunk.split(":");
      const head = f[0];
      const freqField = f[5] || "";
      return {
        id: head.startsWith("!") ? "custom" : head,
        name: head.startsWith("!") ? decField(head.slice(1)) : "",
        sets: decField(f[1]),
        reps: decField(f[2]),
        hold: decField(f[3]),
        side: SIDE_CODES[f[4]] || "Bilateral",
        freq: FREQ_CODES[freqField] || (freqField.startsWith("x") ? decField(freqField.slice(1)) : "")
      };
    });
    return {
      code: decField(parts[1]),
      clinic: decField(parts[2]),
      directiveIds: (parts[3] || "").split(",").filter(Boolean),
      exercises,
      title: decField(parts[5]),
      notes: decField(parts[6]),
      customDirectives: (parts[7] || "").split(",").filter(Boolean).map(decField)
    };
  }

  return {
    MOVEMENT_TYPES, ACTIVE_TYPES, JOINTS, SURGERIES,
    normalize, tokens, classifyExercise, safetyProfile,
    detectSurgeries, detectPhase, detectOperativeSide, parseRestrictions,
    phraseMatchesExercise, evaluateExercise, analyzeProtocolText,
    scrubPHI, encodeCompactProgram, decodeCompactProgram, FREQ_CODES, DIRECTIVE_PRESETS
  };
});
