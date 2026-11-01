#!/usr/bin/env node
/*
 * Headless page test: node tests/browser.js   (or: node tests/run.js --browser)
 * Needs puppeteer-core (npm i puppeteer-core, or set PUPPETEER_CORE_DIR) and
 * Chrome/Chromium (CHROME_PATH, default /usr/bin/google-chrome).
 * Serves the repo with a tiny static server, so no other tooling is needed.
 */
const http = require("http");
const fs = require("fs");
const path = require("path");
const assert = require("assert");

const ROOT = path.join(__dirname, "..");
let puppeteer;
try { puppeteer = require("puppeteer-core"); }
catch (err) {
  const dir = process.env.PUPPETEER_CORE_DIR;
  if (!dir) {
    console.error("SKIP browser tests: puppeteer-core not installed (npm i puppeteer-core, or set PUPPETEER_CORE_DIR).");
    process.exit(2);
  }
  puppeteer = require(path.join(dir, "node_modules", "puppeteer-core"));
}

const TYPES = { ".html": "text/html", ".js": "text/javascript", ".json": "application/json", ".png": "image/png", ".svg": "image/svg+xml", ".webp": "image/webp", ".jpg": "image/jpeg", ".css": "text/css" };
function serve() {
  return new Promise(resolve => {
    const server = http.createServer((req, res) => {
      const rel = decodeURIComponent(new URL(req.url, "http://x").pathname).replace(/^\/+/, "") || "index.html";
      const file = path.join(ROOT, rel);
      if (!file.startsWith(ROOT) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) { res.writeHead(404); res.end(); return; }
      res.writeHead(200, { "Content-Type": TYPES[path.extname(file)] || "application/octet-stream" });
      fs.createReadStream(file).pipe(res);
    });
    server.listen(0, "127.0.0.1", () => resolve(server));
  });
}

const results = [];
async function test(name, fn) {
  try { await fn(); results.push({ name, ok: true }); }
  catch (err) { results.push({ name, ok: false, err }); }
}

function watchConsole(page) {
  const errors = [];
  page.on("pageerror", err => errors.push("pageerror: " + err.message));
  page.on("console", msg => {
    // Failed requests are reported by the response listener below (with the URL).
    if (msg.type() === "error" && !/^Failed to load resource/.test(msg.text())) errors.push("console.error: " + msg.text());
  });
  page.on("response", res => {
    // The static test server has no favicon; GitHub Pages does not either.
    if (res.status() >= 400 && !/favicon\.ico$/.test(res.url())) errors.push("HTTP " + res.status() + " " + res.url());
  });
  return errors;
}

(async () => {
  const server = await serve();
  const base = `http://127.0.0.1:${server.address().port}/`;
  const browser = await puppeteer.launch({
    executablePath: process.env.CHROME_PATH || "/usr/bin/google-chrome",
    headless: true,
    args: ["--no-sandbox", "--disable-gpu"]
  });
  try {
    const page = await browser.newPage();
    const indexErrors = watchConsole(page);
    let dialogAnswer = null;
    page.on("dialog", async dialog => {
      if (dialog.type() === "prompt") {
        if (dialogAnswer == null) await dialog.dismiss(); else await dialog.accept(dialogAnswer);
      } else if (dialog.type() === "confirm") {
        await dialog.dismiss();
      } else {
        await dialog.accept();
      }
    });
    await page.goto(base + "index.html", { waitUntil: "networkidle0" });
    await page.waitForFunction(() => typeof catalogData !== "undefined" && catalogData.length > 300);

    await test("index.html loads with no console errors and the engine is present", async () => {
      assert.ok(await page.evaluate(() => !!window.HEPSafety));
      assert.deepStrictEqual(indexErrors, [], indexErrors.join("\n"));
    });

    await test("PHI warning is visible and dictation is off by default", async () => {
      const text = await page.$eval("#phiWarningProgram", el => el.offsetParent !== null && el.textContent);
      assert.match(text, /No patient names or DOBs/);
      const state = await page.evaluate(() => ({ consent: dictationConsent, listening: dictateListening }));
      assert.deepStrictEqual(state, { consent: false, listening: false });
    });

    await test("declining the dictation warning opens the paste box instead of the mic", async () => {
      const r = await page.evaluate(() => {
        window.SpeechRecognition = window.SpeechRecognition || function () { window.__micStarted = true; this.start = () => {}; };
        toggleDictatePlan();
        const open = !document.getElementById("dictatePasteModal").classList.contains("hidden");
        closeDictatePasteModal();
        return { open, mic: !!window.__micStarted, consent: dictationConsent };
      });
      assert.deepStrictEqual(r, { open: true, mic: false, consent: false });
    });

    await test("notes 'Ankle pumps not allowed' blocks the catalog card and shows why", async () => {
      await page.evaluate(() => {
        const notes = document.getElementById("patientNotesInput");
        notes.value = "Ankle pumps not allowed.";
        notes.dispatchEvent(new Event("input"));
        document.getElementById("searchInput").value = "ankle pumps";
        document.getElementById("searchInput").dispatchEvent(new Event("input"));
      });
      await new Promise(r => setTimeout(r, 400));
      const card = await page.evaluate(() => document.getElementById("catalogList").innerText);
      assert.match(card, /BLOCKED/);
      assert.match(card, /Ankle pumps not allowed/);
      const panel = await page.$eval("#safetyPanel", el => !el.classList.contains("hidden") && el.innerText);
      assert.match(panel, /Ankle pumps not allowed/);
    });

    await test("blocked add is refused without an override note", async () => {
      dialogAnswer = null;
      const n = await page.evaluate(() => { requestAddToProgram("ankle-pumps"); return currentProgram.length; });
      assert.strictEqual(n, 0);
    });

    await test("deliberate override adds it with a visible note, listed in the EMR note", async () => {
      dialogAnswer = "Surgeon cleared ankle pumps by phone";
      const r = await page.evaluate(async () => {
        requestAddToProgram("ankle-pumps");
        let clip = "";
        navigator.clipboard.writeText = async text => { clip = text; };
        copyEmrSnippet();
        await new Promise(res => setTimeout(res, 50));
        return {
          n: currentProgram.length,
          note: currentProgram[0] && currentProgram[0].override && currentProgram[0].override.note,
          shown: document.querySelector("#activeProgramList [data-override-note]") ? document.querySelector("#activeProgramList [data-override-note]").innerText : "",
          clip
        };
      });
      dialogAnswer = null;
      assert.strictEqual(r.n, 1);
      assert.strictEqual(r.note, "Surgeon cleared ankle pumps by phone");
      assert.match(r.shown, /Clinician override: Surgeon cleared/);
      assert.match(r.clip, /CLINICIAN OVERRIDES OF SAFETY BLOCKS/);
    });

    await test("print and share are refused while a blocked item has no override", async () => {
      const r = await page.evaluate(() => {
        delete currentProgram[0].override;
        renderActiveProgram();
        let printed = false;
        window.print = () => { printed = true; };
        triggerPrintHandout();
        const ok = confirmSafeToShare("Test");
        return { printed, ok };
      });
      assert.deepStrictEqual(r, { printed: false, ok: false });
    });

    await test("surgeon protocol: side, phase, blocked LAQ not applied", async () => {
      const r = await page.evaluate(() => {
        currentProgram = [];
        currentProgramState.directives = [];
        safetyContext = { protocolText: "", extraText: "" };
        document.getElementById("patientNotesInput").value = "";
        refreshSafety(true);
        const text = "Left ACL reconstruction with patellar tendon graft. Phase I, weeks 0-2. WBAT in brace locked in extension. No open-chain knee extension (no long arc quads) for 12 weeks. Quad sets, SLR, heel slides, long arc quads, ankle pumps.";
        const parsed = parseSurgeonProtocolText(text);
        document.getElementById("protocolPasteInput").value = text;
        applySurgeonProtocolToRoutine();
        return {
          side: parsed.side,
          phase: parsed.phase && parsed.phase.number,
          laq: parsed.exercises.filter(e => /long arc/i.test(e.name)).map(e => e.safety.status),
          program: currentProgram.map(i => i.name),
          sides: [...new Set(currentProgram.map(i => i.side))]
        };
      });
      assert.strictEqual(r.side, "Left");
      assert.strictEqual(r.phase, 1);
      assert.ok(r.laq.length && r.laq.every(s => s === "block"), "LAQ should be blocked: " + r.laq);
      assert.ok(!r.program.some(n => /long arc/i.test(n)), "LAQ must not be applied");
      assert.ok(r.program.some(n => /heel slide/i.test(n)));
      assert.strictEqual(r.program.filter(n => /ankle pump/i.test(n)).length, 1, "Ankle Pumps added once");
      assert.deepStrictEqual(r.sides, ["Left"]);
    });

    let shareUrl = "";
    await test("20-exercise share link is compact, scrubbed, and round-trips into patient.html", async () => {
      const r = await page.evaluate(() => {
        currentProgram = [];
        currentProgramState.directives = [directiveString(clinicalDirectivePresets[0])];
        safetyContext = { protocolText: "", extraText: "" };
        document.getElementById("programTitleInput").value = "Knee program for Patient John Smith";
        document.getElementById("patientNotesInput").value = "Mrs. Jane Doe DOB 01/02/1960, call 360-555-1234 or jane@example.com. MRN 12345678. Lives at 123 Main Street. Ice after.";
        refreshSafety(true);
        catalogData.slice(0, 20).forEach(ex => addToProgram(ex.id, "Left", null, false));
        renderActiveProgram();
        const link = patientShareLink(currentAccessCode, true);
        return { url: link.url, removed: link.removed, n: currentProgram.length, ids: currentProgram.map(i => i.baseId) };
      });
      assert.strictEqual(r.n, 20);
      assert.ok(r.url.length < 1200, "url length " + r.url.length);
      assert.ok(/#p=2~/.test(r.url));
      assert.ok(r.removed >= 5, "removed " + r.removed);
      const decoded = decodeURIComponent(r.url);
      for (const bad of ["John", "Smith", "Jane", "Doe", "1960", "555-1234", "example.com", "12345678", "Main Street"]) {
        assert.ok(!decoded.includes(bad), "share link leaked " + bad);
      }
      shareUrl = r.url;
      const patient = await browser.newPage();
      const patientErrors = watchConsole(patient);
      await patient.goto(shareUrl, { waitUntil: "networkidle0" });
      await patient.waitForFunction(() => document.querySelectorAll("#exerciseCardsList > *").length > 0);
      const shown = await patient.evaluate(() => ({
        cards: document.querySelectorAll("#exerciseCardsList > *").length,
        title: document.getElementById("programTitle").textContent,
        notes: document.getElementById("therapistNotes").textContent,
        directives: document.getElementById("clinicalDirectivesList").innerText
      }));
      assert.strictEqual(shown.cards, 20);
      assert.match(shown.title, /Knee program for .*\[removed\]/);
      assert.ok(!/John|Smith/.test(shown.title));
      assert.match(shown.notes, /Ice after/);
      assert.match(shown.directives, /Use ice/);
      assert.deepStrictEqual(patientErrors, [], patientErrors.join("\n"));
      await patient.close();
    });

    await test("patient.html loads cleanly with no hash and with a legacy #d link", async () => {
      const patient = await browser.newPage();
      const errors = watchConsole(patient);
      await patient.goto(base + "patient.html", { waitUntil: "networkidle0" });
      const legacy = Buffer.from(JSON.stringify({ code: "PW-1111", title: "Legacy", exercises: [{ id: "ankle-pumps", side: "Left", sets: 2, reps: 10, hold: "2s", freq: "Daily (7x/wk)" }] })).toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
      await patient.goto(base + "patient.html#d=" + legacy + "&code=PW-1111", { waitUntil: "networkidle0" });
      await patient.reload({ waitUntil: "networkidle0" });
      const cards = await patient.evaluate(() => document.querySelectorAll("#exerciseCardsList > *").length);
      assert.strictEqual(cards, 1);
      assert.deepStrictEqual(errors, []);
      await patient.close();
    });

    await test("20-exercise handout prints with a >=160px QR code", async () => {
      const r = await page.evaluate(() => {
        let printed = false;
        window.print = () => { printed = true; };
        triggerPrintHandout();
        const qr = document.getElementById("printQrCode");
        const img = qr.querySelector("canvas, img");
        return {
          printed,
          cards: document.querySelectorAll("#printExerciseSheet .exercise-card").length,
          rendered: qr.dataset.qrRendered,
          width: img ? Math.max(img.width || 0, img.getBoundingClientRect().width) : 0
        };
      });
      assert.strictEqual(r.printed, true);
      assert.strictEqual(r.cards, 20);
      assert.strictEqual(r.rendered, "true");
      assert.ok(r.width >= 160, "QR width " + r.width);
    });

    await test("oversized program falls back to a code instead of crashing", async () => {
      const r = await page.evaluate(() => {
        for (let i = 0; i < 40; i++) {
          gateCustomProgramItem({ uniqueInstanceId: "big" + i, baseId: "custom", name: "Very long custom exercise description number " + i + " with extra words", type: "strength", side: "Right", sets: 3, reps: 12, hold: "5s", freq: "Every other evening after work", cues: [], photos: [] });
        }
        document.getElementById("patientNotesInput").value = "x".repeat(3000);
        let printed = false;
        window.print = () => { printed = true; };
        triggerPrintHandout();
        return {
          printed,
          rendered: document.getElementById("printQrCode").dataset.qrRendered,
          text: document.getElementById("printQrCode").innerText + " " + document.getElementById("printQrFallback").innerText,
          code: currentAccessCode
        };
      });
      assert.strictEqual(r.printed, true);
      assert.strictEqual(r.rendered, "false");
      assert.ok(r.text.includes(r.code), "fallback shows the access code");
    });

    await test("no console errors across the whole index.html session", async () => {
      assert.deepStrictEqual(indexErrors, [], indexErrors.join("\n"));
    });
  } finally {
    await browser.close();
    server.close();
  }

  let failed = 0;
  for (const r of results) {
    console.log(`${r.ok ? "PASS" : "FAIL"}  browser: ${r.name}`);
    if (!r.ok) { failed++; console.log("      " + String(r.err && r.err.stack || r.err).split("\n").slice(0, 3).join("\n      ")); }
  }
  console.log(`\nbrowser: ${results.length - failed}/${results.length} passed`);
  process.exit(failed ? 1 : 0);
})().catch(err => { console.error(err); process.exit(1); });
