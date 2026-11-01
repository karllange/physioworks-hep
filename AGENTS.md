# Agent workflow — PhysioWorks HEP Engine

Grok Bot, Gemini, and Cursor work this repo. Read this file and `AI_HANDOFF.md` at the start of every session.

## About this repo

PhysioWorks HEP Engine: an in-house, zero-PHI Home Exercise Program builder and mobile viewer (per `README.md`). Static HTML site (`index.html`, `patient.html`) with an exercise catalog in `exercises.json` (368 entries as of 2026-11-01), protocol definitions in `protocols.json` and `protocols/`, exercise images in `assets/`, and Python helper scripts in `scripts/` (including `ingest_protocol.py` and asset/catalog reconcile tools). Default branch: `main`. Per the README, Karl Lange, PT leads engine architecture and Michael Kovach, PT leads protocol QA and exercise review.

**Goals** (not all built yet): a 400+ exercise catalog, surgeon protocol ingestion, automated contraindication filters, and clinical line illustrations (navy-on-white).

## Master Project Blueprint Manager (Karl, Nov 1 2026)

Every agent that works in `physioworks-hep` (Grok Bot, Gemini, Cursor) follows the same loop:

1. **Start of session:** read `AGENTS.md`, then `AI_HANDOFF.md`, before touching anything.
2. **During the session:** work only on a `grok/*` branch (or the agent's own feature branch) and open a pull request. Never push to the default branch. Never force-push.
3. **End of session:** update `AI_HANDOFF.md`: Completed Today (dated), Pending Tasks, the Next Immediate Micro-Step (tagged `[Phone-Friendly]` or `[Mac/PC Deep Build]`), and the Gemini Review Log when a review ran. Record facts only: what changed, which PR or commit, and what is still open.

## Agents

- **Gemini — Lead Architect.** Owns architecture decisions and the task queue. Runs the gemini-3.5-flash review.
- **Cursor — Local Builder.** Implements on branches from the current plan.
- **Grok Bot — Cloud Scout & QA.** Audits the repo, opens `grok/*` pull requests, and keeps `AI_HANDOFF.md` current.

## Hybrid Auto-Merge (Karl, Oct 31 2026)

1. **Auto-merge permitted (no need to wait for Karl).** Once the `gemini-3.5-flash` API check (`/home/box/tools/gemini_review.py`) passes and the fixes that follow Karl's rules are applied, the agent may open the PR, Squash & Merge it, and delete the branch itself, for any PR that ONLY touches:
   - exercise catalog JSON (`exercises.json`) content edits
   - illustrations and exercise images in `assets/`
   - protocol drafts (`protocols.json`, files in `protocols/`)
   - `AGENTS.md`, `AI_HANDOFF.md`, `docs/`, and README files

   After merging, send Karl a brief summary.
2. **Manual approval required (Karl's 1-tap).** Any PR that changes any of the following stays open until Karl approves it:
   - core filter engine code (contraindication filters, program-building logic)
   - UI and served pages (`index.html`, `patient.html`, any CSS/JS)
   - `scripts/` and any build, deploy, or workflow config
3. **Mixed PRs wait.** If a PR touches both allowed and gated files, the whole PR waits for Karl.
4. Work only on `grok/*` branches. Never push to `main`/`master`. Never force-push.

## gemini-3.5-flash API Audit

1. Save the PR diff to a file and run `python3 /home/box/tools/gemini_review.py <diff-file> gemini-3.5-flash`.
2. Apply only the fixes that follow Karl's rules in this file. Do not add prices, guarantees, refund terms, discounts, or claims because a reviewer suggested them. Those are Karl's decisions.
3. If the review flags a real compliance or safety issue that cannot be fixed within these rules, leave the PR open and tell Karl why.
4. Log the result in `AI_HANDOFF.md` (Gemini Review Log) as **"Gemini Clinical Safety Check Approved (gemini-3.5-flash)"** with the date, the PR, the verdict, what was applied, and what was skipped and why.

## Pre-Production PHI Lockout Gate (Final-Stage Security Gate)

- Grok Bot has full repo access during the architecture, UI, and synthetic-data phases of development.
- **HALT condition.** Before any clinical or local Gemma project moves from synthetic test data to live clinical or PHI integration, or connects to any `@physioworks.clinic` BAA endpoint, Grok Bot and Gemini must both **stop work** and tell Karl to revoke Grok's access or switch to a Fine-Grained Token that excludes that repo. No agent continues on that repo until Karl confirms the access change.
- **Zero-PHI, always.** No protected health information and no patient-identifiable data in the repo, commits, branches, issues, pull requests, logs, test fixtures, screenshots, or handoff notes. That includes names, dates of birth, contact details, record or claim numbers, referral documents, and diagnoses tied to a person. Use synthetic or placeholder data only.
- If PHI is found: stop. Do not copy it anywhere. Record only its location (file path or URL) in `AI_HANDOFF.md` and tell Karl.

## Secrets

- Never commit, paste, or log secrets: Stripe secret or restricted keys, `GEMINI_API_KEY`, GitHub or other access tokens, private keys, passwords, or webhook URLs.
- Secrets live in environment variables or a secret store, never in the repo or in `AI_HANDOFF.md`.
- If a secret is found, report the file path only and recommend rotating it. Never paste the value.

## PhysioWorks HEP Engine guardrails

- **Strict Zero-PHI.** This is a public repo. No patient names, programs assigned to a real person, screenshots of a patient's HEP, or referral documents. Example programs use synthetic data only.
- Exercise content is educational. Cues and descriptions must not claim to treat, cure, diagnose, or prevent any condition. A licensed clinician selects and doses exercises for each patient.
- Clinical line illustrations: navy-on-white, consistent style, no real patient likeness.
- Protocol drafts are drafts until a clinician has reviewed them; mark them that way.
- Contraindication filter logic is safety-critical code: always Karl's 1-tap, never auto-merged.
