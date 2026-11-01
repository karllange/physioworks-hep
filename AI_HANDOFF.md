# AI handoff clipboard — PhysioWorks HEP Engine

Shared state for every agent in `AGENTS.md`. Newest entry first in each section. Never paste PHI, secrets, or personal information; if any shows up, record only its location.

## Completed Today

### 2026-11-01

- Read-only deep audit completed; roadmap added under Pending Tasks (PR grok/audit-roadmap). No code changed.
- Master Project Blueprint Manager installed: `AGENTS.md` and `AI_HANDOFF.md` created (PR grok/blueprint-manager).

## Pending Tasks

- Catalog is at 368 exercises; goal is 400+.
- Automated contraindication filters: goal, not yet built.
- Asset gaps are tracked in `docs/asset_gaps.md`.

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

- [Mac/PC Deep Build] List the exercises still missing to reach 400, by body region, as a docs-only PR.

## Gemini Review Log

Newest entry first. Each entry: date, PR, verdict, applied fixes, skipped suggestions and why.

### 2026-11-01 — Gemini Clinical Safety Check Approved (gemini-3.5-flash)

- Scope: grok/audit-roadmap, docs-only (`AI_HANDOFF.md`). Read-only audit roadmap. PHI: none.
- Verdict: pass, 0 compliance issues. The only note: this is internal docs, not marketing copy.
- Architecture second opinion on the audit draft: adopted points are labeled in the roadmap above. Corrected: the negation bug is in the browser parser, not in the ingest script.
- Merged under Hybrid Auto-Merge (docs only).

### 2026-11-01 — Gemini Clinical Safety Check Approved (gemini-3.5-flash)

- Scope: PR #2, docs-only (`AGENTS.md`, `AI_HANDOFF.md`). Master Project Blueprint Manager install. PHI: none.
- Verdict: pass, 0 compliance issues, 0 conversion notes. Run with `gemini_review.py`; no exercise or clinical content changed in this PR.
- Merged under Hybrid Auto-Merge (docs only).
