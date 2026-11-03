# AI handoff clipboard — PhysioWorks HEP Engine

Shared state for every agent in `AGENTS.md`. Newest entry first in each section. Never paste PHI, secrets, or personal information; if any shows up, record only its location.

## Completed Today

### 2026-11-02

- Hamstring Curls, Hamstring Ball Curls, and Prone Hamstring Curls are catalog category `knee` (was `ankle`). The Swap Match tag and the Knee filter both read that field from `exercises.json`.
- Karl approved the merge. `main` is `47062ec` (fast-forward of `feat/reasoning-engine`) and is pushed to origin. GitHub Pages publishes `main`. Standing-hip drawing remains the `bdc07d5` file. `missing-illustrations-queue.json` remains the cleared `e928221` queue (0 missing, 290 illustrated). `.DS_Store` is now in `.gitignore`.
- Dictate Plan / Paste now best-guesses a library exercise instead of dropping straight to "Custom Clinic Movement". Cue clauses ("as you…", "making sure to…", "holding for…", "on the edge of…") leave the title and land on the card as spoken cues. A non-exact match loads the top library exercise (real start/end images) and shows a Swap Match / Options picker: top alternatives, a library search box, and Keep as Custom with the cleaned dictated name. Exact titles and voice aliases stay exact and do not show the picker. Lives in `index.html`. Checked in the browser with "Hamstring stretch in seated position as you lean forward from the hips holding for 30 seconds" (best guess Seated Hamstring Stretch, alternatives are the other hamstring exercises, hold 30s, cues preserved through swap and Keep as Custom). Rare clinical words outrank a generic word such as "stretch". A phrase that shares no muscle, movement, position, or equipment word, and fewer than two title words, stays a custom card under the full cleaned name. UI change, waits for Karl's tap.
- Resolved all merge conflicts on `feat/reasoning-engine` with `origin/main`.
- Staged and committed a clean resolution:
  - **`exercises.json`**: Resolved conflict by retaining our active/illustrated list, then ran `node scripts/classify_catalog.js` to process safety metadata and protocol references, producing a compliant, valid **290-exercise database**.
  - **`index.html`**: Handled all 5 conflict blocks including safety card rendering, gating custom exercises, and knee-106 voice aliases.
  - **`tests/run.js`**: Updated tests to match the cleaned catalog. Verified all 14/14 clinical safety/reasoning engine tests pass.

### 2026-11-01

- Phase 1 code PR opened (grok/phase1-contraindication-engine), waiting for Karl's tap; not merged. Adds `hep-safety.js` (block-and-warn contraindication engine with negation, PROM-only, surgery/phase I–VII/side detection), structured `movementType`/joint fields on every exercise, removal of 24 junk/duplicate catalog rows, a compact PHI-scrubbed share link with a 160 px QR and code fallback, dictation off by default, and "No patient names or DOBs" warnings. Tests: `node tests/run.js --browser`.
- Read-only deep audit completed; roadmap added under Pending Tasks (PR grok/audit-roadmap). No code changed.
- Master Project Blueprint Manager installed: `AGENTS.md` and `AI_HANDOFF.md` created (PR grok/blueprint-manager).

## Pending Tasks

- Catalog is at 344 exercises after the Phase 1 cleanup (was 368); goal is 400+.
- Automated contraindication filters: built in the Phase 1 PR; live once Karl merges it.
- Asset gaps are tracked in `docs/asset_gaps.md`. `docs/asset_gaps.md`, `docs/asset_batches` and `scripts/batch_asset_prompts.py` still list some removed ids; clean up in a later PR.

### Phase 1 follow-ups for clinician review (from `node scripts/check_protocol_conflicts.js`)

- 4 exercises in `protocols.json` conflict with their own phase precautions and are now skipped when that preset is loaded: RCR phase 1 Band External Rotation at 0° and Scapular Plane Shoulder Elevation < 90° ("No AROM"); RCR phase 2 Scapular Rowing Off Of Table ("No extension"); RCR phase 3 Rotator Cuff Series ("No active IR"). Karl or Michael decide: fix the precaution text or the exercise list.
- 6 catalog rows were kept for review rather than removed: 1-2-kneeling-hip, more-aggressive-prom, aggressive-prom-stretching-to-achieve, initiate-wb-with-crutches-in-the-boot, sl-holds, flexion-on-step.
- The printed paper handout shows the therapist notes as typed; only the share link and QR are scrubbed.
- The access code still works only on the device that created it (localStorage).

### Audit roadmap — 2026-11-01 (read-only audit, no code changed)

Evidence from a fresh clone and headless-browser runs. Line numbers refer to `main` at 3510e72.

**Catalog and illustrations**
- `exercises.json` (368 entries) has no contraindication, precaution, tag, phase, equipment or position fields. `type` is only `strength` (333) or `stretch` (35).
- 254 entries (69%) use external placeholder images. No entry has a video. 259 entries use the templated cue "Set up for … in a comfortable position" (`scripts/ingest_protocol.py` `default_cues`).
- About 20 entries are not exercises; they came from protocol parsing ("Add Weight", "Active Knee", "Double Leg", "4 Exercises Performed In Succession", …). There are 2 near-duplicates: lat-pull-down/lat-pulldown and the two slantboard squats.
- Thin regions: thoracic 3, hand 3, balance 5, elbow/wrist 8, cervical 10.
- Category comes from the protocol region, so Achilles return-to-sport drills are all "ankle".
- 68 files in `assets/` are not used.

**Contraindications and clinical reasoning**
- Filtering is already instant: category plus synonym search runs in about 2 ms (`index.html` 797–822, 1078–1104). Speed is not the problem; safety is.
- There is no contraindication engine. Weight-bearing and ROM restrictions are pulled out as text only (`index.html` 2512–2573), and exercises are never checked against them.
- The parser ignores negation. "Ankle pumps not allowed" still adds Ankle Pumps, and adds it twice.
- `detectSurgery` (2447–2472) knows 6 surgery types; `protocols.json` has 13. `detectProtocolPhase` (2474–2487) reads phases I–IV only, but protocols go to phase 7.
- `detectOperativeSide` returns "Bilateral" when the text mentions both sides (for example "Left TKA. Right knee …").
- Phase week windows overlap in protocols (for example ACL phase 3 is weeks 6–12 and phase 4 is weeks 8–16).

**Protocols, print, share and PHI**
- The whole program is base64-encoded into the share URL (`index.html` 1611–1642). The QR is 72 px at level M (1659–1669).
- 20 exercises made the print step crash because the QR overflowed. At 5–12 exercises the QR is very dense.
- The patient "code" (PW-XXXX) works only on the same device, because it is stored in localStorage. The on-screen copy says "6-character".
- PHI exposure: free text (title, notes, custom names, pasted protocol, dictation) goes into the share URL and localStorage, and nothing scrubs it. Chrome dictation sends audio to Google's servers. Camera photos are stored in localStorage.

**Next micro-steps**
1. [Mac/PC Deep Build] Add `contraindications`/`precautions` fields and a block-and-warn check against parsed restrictions, including negation. Code PR; waits for Karl's tap.
2. [Phone-Friendly] Karl and Michael mark the ~20 non-exercise entries and the 2 near-duplicates to remove. Catalog JSON only.
3. [Mac/PC Deep Build] Fix the QR: encode only exercise ids and doses, enlarge the QR, and fall back to a link when the payload is too big. Code PR.
4. [Mac/PC Deep Build] Extend surgery, phase (to VII) and side detection to all 13 protocols, with a wrong-side warning. Code PR.
5. [Phone-Friendly] Decide the dictation policy: warn first or turn cloud dictation off. Then add a "no names, dates or identifiers" warning next to the free-text fields.

**Gemini second opinion (gemini-3.5-flash), adopted:** ship the negation fix and phase I–VII before any catalog growth. Get explicit consent before cloud dictation, or turn it off. Add a payload size limit with a link fallback for the QR. Correction to Gemini: the negation bug is in the browser parser (`index.html` `parseSurgeonProtocolText`), not in `ingest_protocol.py`.

## Next Immediate Micro-Step

- [Phone-Friendly] Karl checks the live Dictate Plan matcher at karllange.github.io/physioworks-hep/ after GitHub Pages finishes building `47062ec`.

## Gemini Review Log

Newest entry first. Each entry: date, PR, verdict, applied fixes, skipped suggestions and why.

### 2026-11-01 — Gemini Clinical Safety Check Approved (gemini-3.5-flash)

- Scope: grok/phase1-contraindication-engine, code PR. Reviewed as a clinical-safety code reviewer on a condensed summary: full `hep-safety.js` plus the `index.html` safety gate. PHI: none.
- Verdict: pass, 0 issues. Nothing to apply or skip.
- Before the review, a report-only run of every protocol's own precautions against its exercises found 39 over-blocks. Fixed: angle-limited rules ("No ER > 30°") and duration-limited avoidance now warn; motion-specific "no resisted" applies to those motions only; mid-sentence "without" no longer negates; scapular-only drills warn under shoulder limits. 4 genuine conflicts are left for clinician review (Pending Tasks).
- Not merged: code PR, waits for Karl's tap.

### 2026-11-01 — Gemini Clinical Safety Check Approved (gemini-3.5-flash)

- Scope: grok/audit-roadmap, docs-only (`AI_HANDOFF.md`). Read-only audit roadmap. PHI: none.
- Verdict: pass, 0 compliance issues. The only note: this is internal docs, not marketing copy.
- Architecture second opinion on the audit draft: adopted points are labeled in the roadmap above. Corrected: the negation bug is in the browser parser, not in the ingest script.
- Merged under Hybrid Auto-Merge (docs only).

### 2026-11-01 — Gemini Clinical Safety Check Approved (gemini-3.5-flash)

- Scope: PR #2, docs-only (`AGENTS.md`, `AI_HANDOFF.md`). Master Project Blueprint Manager install. PHI: none.
- Verdict: pass, 0 compliance issues, 0 conversion notes. Run with `gemini_review.py`; no exercise or clinical content changed in this PR.
- Merged under Hybrid Auto-Merge (docs only).
