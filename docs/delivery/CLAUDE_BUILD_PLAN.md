# JananiSaathi / MatriSathi: build plan for Claude

This file lives at `docs/delivery/CLAUDE_BUILD_PLAN.md` and is committed to the repository (it was kept local until 2026-11-07).
Every work session starts by reading it.

It turns the two-developer tracker (`JananiSaathi_Two_Dev_Task_Tracker.xlsx`) into instructions Claude can execute task by task. The tracker's task IDs are kept, so the Saturday meeting can show progress against the same plan.

---

## Part A: For the human (read once)

### How to use this file

1. Keep this file at `docs/delivery/CLAUDE_BUILD_PLAN.md` in the repository.
2. Start every Claude Code session with the **session prompt** in Part F.
3. Give Claude **one task ID at a time** (for example `W1-A1`). Claude plans it, waits for your approval, builds it, tests it, opens a PR and updates the progress log.
4. On Friday, run the **week-close prompt**. It produces `docs/delivery/weekly/W<n>.md`, which is your meeting report. Copy its numbers into the tracker's amber cells.

### What you do that Claude cannot

Claude cannot click through web dashboards, create accounts, send messages to people or attend reviews. For each such step, Claude writes the exact checklist and you carry it out:

- GitHub repository settings (branch protection, required checks, collaborators)
- Render, Vercel and Supabase dashboards (services, environment variables, secrets)
- WhatsApp provider sign-up, business verification, template submission, test numbers
- Sending review packets to the doctor and pediatric reviewer, and recording their answers
- Field sessions, sign-off meetings, and every manager or doctor decision (D01–D15)
- Opening and merging PRs: `gh` is not authenticated on this machine, so Claude pushes the branch (with approval) and the human opens the PR. Until D03 and D15 are decided, the developer approves and merges every PR.

### Honest reporting

The tracker has two lanes: Dev A (backend and platform) and Dev B (frontend and quality). Both lanes are now done by one person working with Claude. Report them as **two workstreams with one owner**.

The tracker's "peer reviewer" was the other developer. That person no longer exists, so every PR records review as:

> Self-reviewed + automated checks; independent review: pending (manager at Saturday demo)

Do not write that the other developer reviewed it. Ask the manager to approve this substitute rule at the first meeting.

### Dates

The tracker's Week 1 was 2–6 Nov 2026. No commits landed that week; the last commit is 31 Oct.

**Decided: Week 1 restarts Mon 9 Nov.** Every tracker date shifts +1 week (recorded in `progress.md`). Every gate moves one week later. The release candidate moves from Thu 24 Dec to around Thu 31 Dec, which falls inside the reserve week.

Tell the manager at the first meeting. Do not quietly squeeze two weeks into one.

---

## Part B: Instructions for Claude

### Order of authority

1. `CLAUDE.md` in the repo root. Its permissions, privacy and clinical boundaries always win over this file.
2. This file. It sets task scope, acceptance criteria and reporting format.
3. `docs/specifications/MatriSathi_Stage_Gate_Task_Tracker_with_FS_and_TS.xlsx`:
   - Functional Specs F001–F044
   - Technical Specs T001–T023
   - Acceptance AT01–AT32
4. `docs/specifications/R09-G15-proposed-amendments.md`. MatriSathi is a standalone app with no reuse of any other platform.
5. The Gap Decisions G01–G20 in the tracker. These are proposals until accepted; treat them as binding scope limits anyway.

If these sources conflict, stop and ask. Do not resolve a conflict in scope, clinical behaviour, data ownership, security or cost yourself.

### Clinical boundary (never cross)

The app is assistive only. Never build any of the following, even if the original spec sheet asks for it:

- risk scores
- vital-sign thresholds or alerts
- trend interpretation
- discharge-readiness evaluation
- PPD or EPDS scoring
- growth-faltering or dehydration detection
- labour "when to go" triage
- geofencing, GPS arrival, ambulance ETA or dispatch
- generated medical answers

What to build instead:

- **Unknown values** stay unknown.
- **Reported values** are stored raw, with date, unit, source and recorder.
- **Clinical decisions** (date confirmation, plan approval, report review, discharge) are recorded only by clinician roles, and every one is audited.
- **"Overdue"** means administrative delay, never clinical risk.

### Fixed engineering rules (from the repo)

- Never identify or merge people by phone number. A phone number is a contact, not an identity.
- Derive the facility or organization scope server-side. Never accept it from the client.
- Every create endpoint is idempotent (`Idempotency-Key`). Every update after W2 uses an optimistic `version`.
- Audit successful and denied actions. Logs must contain no patient text, message content or secrets.
- Use synthetic data only.
- Backend: FastAPI, SQLAlchemy, Alembic, PostgreSQL. Frontend: React, Vite, TypeScript. Build a modular monolith; no new services.
- New dependencies need approval. The Part G list is approved by the developer (D14, manager informed at the Saturday review); anything outside it still needs approval.
- Every new table needs explicit grants for the `matrisathi_app` role via `grant_app_role` (the automatic default grant from `79d282bcc5f3` was removed in W2-A2; `tests/test_db_grants.py` lists every table).
- Every commit and push needs explicit approval from the human.

---

## Part C: The loop for every task

Run this loop for each task ID.

1. **Read.** Read the task below, the linked F/T/AT rows in the spec workbook, and the code it touches.
2. **Propose.** Post a short plan containing:
   - task ID and lane
   - files you will touch
   - migrations, if any
   - acceptance criteria, copied from this file and the AT rows
   - tests you will add
   - any decision that blocks the task

   Then **wait for approval.**
3. **Branch.** Name the branch `w<week>/<task-id-lowercase>-<short-slug>`, for example `w1/w1-a1-protect-main`.
4. **Build.** Add or extend tests first for access isolation, shared phones, idempotency and audit where relevant.
5. **Verify.** Run every check below and report the exact output:
   - in `apps/api`: `uv run pytest -q`, `uv run ruff check .`, `uv run mypy app`
   - in `apps/web`: `npm run typecheck`, `npm test`, `npm run build`
   - `alembic upgrade head` then `alembic downgrade -1` on a fresh database, when a migration changed

   If you skip a check, say so explicitly.
6. **Commit and PR.** Do this only after approval. Use the PR template in Part E. The PR title starts with the task ID, for example `W2-A3: dating, ANC plan and appointments API`.
7. **Log.** Update `docs/delivery/progress.md` in the same PR (format in Part D).
8. **Hand over.** Finish with a summary: what changed, the verification results, known limitations, and the next task ID.

**Status rules.** Claude may set only these statuses: `In progress`, `Ready for review` or `Blocked`. Only the human or reviewer sets `Accepted`, after the Saturday demo.

**Hours.** Each task carries planned hours from the tracker. Report actual effort honestly in the progress log. If a task will exceed its hours by more than 50%, stop and say so. Do not cut the tests to fit the time.

**Added tasks.** If new work appears during a week, give it the next free ID in that week and lane (for example `W3-A5`). Mark it "(added)" in the progress log, and do not start it without approval.

---

## Part D: Reporting files (the meeting evidence)

Create these files in W1-B4 and keep them current.

### `docs/delivery/progress.md`

One row per task, in task-ID order, with these columns:

```
| Task ID | Week | Lane | Work package | Planned h | Actual h | Status | PR | Merge SHA | CI run | AT / P checks | Evidence | Feedback IDs | Notes |
```

- Lane is `Dev A` or `Dev B`, as in the tracker.
- Status uses the tracker values: `Not started`, `In progress`, `Ready for review`, `Accepted`, `Blocked`.
- CI run is a link to the GitHub Actions run for the merge SHA.

### `docs/delivery/weekly/W<n>.md`

Generate this on Friday with the week-close prompt. Use this template:

```markdown
# Week <n> report: <gate> (<dates>)

## Goal (from tracker)
<copied goal>

## Result in one line
<met / partly met / not met: why>

## Dev A lane (backend and platform)
| Task | Status | PR | Evidence |
...
Dev A % accepted (proposed): <accepted planned hours / total planned hours in lane>

## Dev B lane (frontend and quality)
| Task | Status | PR | Evidence |
...
Dev B % accepted (proposed): <same>

## Acceptance checks
| AT / P | Result (Pass/Fail/Not run) | How verified | Evidence |

## Saturday demo script
1. <exact clicks on staging, synthetic data only>
...

## Pass condition (from tracker) and status of each part

## Decisions needed (D-IDs) and who is blocking

## New feedback (F-IDs) and defects

## Hours: planned vs actual

## Carry-over to next week (task IDs)
```

The "% accepted" figures are proposals. The manager confirms them in the meeting, and the human then types them into the tracker's amber cells.

### `docs/delivery/evidence/SG<n>/`

Each gate gets one evidence folder. It holds `report.md`, test output tied to a SHA, screenshots, and the schema review. Screenshots show synthetic data only.

---

## Part E: PR template

Create this as `.github/pull_request_template.md` in W1-A1.

```markdown
## Task
<Task ID>: <work package> (lane: Dev A | Dev B)

## Spec links
F-IDs: … T-IDs: … AT/P: …

## What changed

## How it was verified
- [ ] pytest: <n passed>  - [ ] ruff  - [ ] mypy
- [ ] web typecheck  - [ ] vitest: <n passed>  - [ ] build
- [ ] migration up/down on fresh DB (if changed)
- Manual check on staging: <steps>

## Clinical boundary check
- [ ] No scoring, thresholds, interpretation or generated clinical advice
- [ ] Unknown stays unknown; clinician-only actions enforced server-side

## Privacy check
- [ ] Synthetic data only; no patient text, message content or secrets in logs/fixtures/screenshots

## Review
Self-reviewed + automated checks. Independent review: pending (manager at Saturday demo).

## Progress log
- [ ] docs/delivery/progress.md updated
```

---

## Part F: Prompts to paste into Claude Code

### Session start

```
Read CLAUDE.md and docs/delivery/CLAUDE_BUILD_PLAN.md, then docs/delivery/progress.md and docs/status.md.
We are in Week <n>. Tell me in five lines: which tasks in this week are done, in progress, blocked, and what you suggest next.
Do not change any files yet.
```

### Start a task

```
Do task <TASK-ID> from docs/delivery/CLAUDE_BUILD_PLAN.md.
Follow Part C exactly: propose the plan with acceptance criteria and files, then wait for my approval.
```

### Week close (Friday)

```
Close Week <n>. Using docs/delivery/progress.md, the merged PRs and CI runs, write docs/delivery/weekly/W<n>.md with the template in Part D.
Run the AT/P checks listed for this week on staging (or locally if staging is not up) and record actual results; do not mark anything Pass you did not run.
Write the Saturday demo script step by step with synthetic data. Propose Dev A / Dev B % accepted. List carry-over tasks.
```

---

## Part G: UI rules (apply from W1-B7 onward)

There are three surfaces, all in one React app:

1. **Staff console** for coordinators, doctors and admins, on desktop or tablet. It opens on a **Today** worklist (my tasks, overdue, inbox), then the patient record. The layout is dense and table-based.
2. **Field worker view** for ASHA, ANM and nurse users. It is mobile-first: today's visits and large forms. In W5 it becomes an installable PWA with offline drafts.
3. **Mother and family.** The main channel is WhatsApp and voice. The web side has two pages: a simple **My next step** page and a public **Urgent help** page that needs no login.

The stack needs approval as D14 before you install anything:

- Tailwind CSS with shadcn/ui components, built on Radix
- react-router and @tanstack/react-query
- react-i18next, set up for English plus the pilot language from day one
- lucide-react icons
- Noto Sans fonts, including the pilot-language script
- vite-plugin-pwa, added in W5

Pin exact versions in `package.json`.

Design rules:
- Every status shows an icon plus a word; never use colour alone.
- Red is reserved for Urgent help only. Use amber for "Pending review" or "Unknown", and neutral grey for "Not recorded".
- Mobile: 48 px touch targets, 16–18 px base text, one primary action per screen, and test at 360 px wide.
- Pair key labels for mothers with an icon and an audio slot.
- Write in plain language, and put all strings in i18n files (no hard-coded copy).
- Show a STAGING banner on every page whenever `VITE_ENV_LABEL` is not `production`.
- Every screen designs an empty state, a loading state, an error state and a "you don't have access" state.

---

## Part H: Week-by-week task specs

Every task below shows: tracker ID, lane, planned hours, what to build, acceptance criteria and spec links.
Tasks owned by the manager or doctor are listed at the end of each week. Claude only prepares the material for those.

### Week 1: SG0 + SG1 close-out
Tracker dates: 2–6 Nov. **Restarted: 9–13 Nov, demo Sat 14 Nov.** (Later weeks shift +1 week the same way.)

**Task order in this week:** W1-A5 runs late in the week (after W1-A4), so D13 has time to be decided.

**Goal:** Prove the foundation. Deliver a CI-verified, reviewer-accepted SG1 slice and unblock the week-1 decisions.

**Saturday demo:**
1. Show the first green CI run tied to a commit SHA.
2. Log in on staging.
3. Register a synthetic mother.
4. Create a pregnancy episode.
5. Show a request to the wrong facility being blocked.

**Pass condition:** AT01–AT04 pass in CI. AT05 is a manual run on staging (fresh checkout, locked install, browser login/create/read, reload and restart) recorded with the commit SHA. The manager accepts the SG1 evidence pack (SHA, CI output, browser demo, schema review).

#### W1-A1 · Dev A · 6 h · Protect main, task branches, first green CI tied to a SHA
Spec: M002, AT05, T007, D03.

Build:
- Add `.github/pull_request_template.md` (Part E).
- Add `docs/delivery/branching.md`, covering branch naming, the PR flow, who approves (D03; until D03/D15 are decided, the developer approves and merges every PR) and squash-merge.
- Confirm `.github/workflows/ci.yml` runs on `pull_request`. It already does; remove the stale comment saying it "is not yet executed anywhere".
- Write the GitHub settings checklist for the human: protect `main`, require PRs, require the `backend` and `frontend` checks, block force-push.

Accept when:
- This task's own PR ran CI on the PR and on merge.
- The merge SHA and run URL are recorded in `progress.md`.
- A direct push to `main` is rejected (the human verifies).

#### W1-A2 · Dev A · 4 h · Prove a green backend CI run on a PR (reduced)
Spec: T007.

Reduced scope (decided 7 Nov): backend CI is already green on `main` (runs for `6aa6217`, `d0dd5f9`, `d6bef28`, `fa515a9`). This task only proves the backend job is green on a PR. If it finds anything, fix it without weakening any test or lint rule. Record actual hours honestly; saved time goes to W1-A4.

Accept when the backend CI job is green on the PR. Report the test count (52 or more).

#### W1-A3 · Dev A · 5 h · Review identity, auth, tenant and audit design; write the D04 proposal
Spec: M003, T002–T006, G14.

Build: Write `docs/decisions/D04-auth-runtime.md`. It should cover:
- current behaviour, with file references
- session and cookie model, CSRF, refresh rotation
- DB roles (migrator vs app)
- facility scoping, audit append-only
- pinned runtime versions
- known gaps: no role capability differences yet; no `version` columns yet
- the proposed SG2 changes: role capabilities (clinician-only actions), and optimistic concurrency

Accept when the document exists, every claim in it points to code or a test, and the open questions for the manager are listed.

#### W1-A4 · Dev A · 6 h (+ time saved on W1-A2 and W1-B1) · Deploy synthetic-only backend staging (Render + Supabase)
Spec: M002, AT05, G17.

The developer approved this list as the CLAUDE.md approval for role/secret changes (7 Nov). Still show the diff before committing.

Fix the limitations listed in `status.md` first:
- The web process runs with `DATABASE_URL_APP` (restricted role) only; it already uses it at runtime (`app/core/db.py`). Migrations run as a **separate release/pre-deploy step** with migrator credentials, never in the web start command (the README's current start command runs `alembic upgrade head` — change it).
- Use the existing `ENV` setting (`settings.env`); do **not** add `APP_ENV`. `/health` returns the environment label.
- When `ENV=staging`, every committed default must fail or refuse to start:
  - the seed password in `app/scripts/seed_dev.py` (seed refuses unless `SEED_PASSWORD` comes from the environment)
  - the app-role password default in `alembic/versions/0002_app_role_grants.py` (`MATRISATHI_APP_DB_PASSWORD` required)
  - the default `JWT_SECRET` (the API refuses to start with it)
- Add a test proving the app role cannot run DDL.
- Staging uses its **own separate Supabase project**, never the shared team database. The human creates it.

Write `docs/delivery/staging.md`. It is the step-by-step dashboard checklist for the human: creating the separate Supabase project, the release-step migration command, and every env var by name (never values), including `ENV=staging`, `COOKIE_SECURE`, `COOKIE_SAMESITE=none` and `CORS_ALLOWED_ORIGINS`.

Accept when:
- Staging `/health` shows `staging`.
- The app role cannot run DDL (a test proves it).
- With `ENV=staging`, the committed seed password, app-role password and JWT secret each fail or refuse to start (tests prove it).
- The web start command contains no migration step.

The human performs the actual deployment.

#### W1-A5 (added) · Dev A · 4 h · Episode model, part 1 (D13 not decided)
Spec: F002, `status.md` open decision.

Runs late in the week. D13 is **not** decided, so build only the non-controversial part now:
- `GET /people/{id}/episodes` (facility-scoped, audited).
- A "continue existing episode" path on the Find screen: staff can open a mother's existing ACTIVE episode instead of always creating a new one (today "Select & create episode" always creates a new one).

**Held until D13 is decided:** the 409 on a second ACTIVE episode and the partial unique index. Do not build them.

Accept when there are tests covering:
- listing a mother's episodes
- continuing an existing ACTIVE episode creates no new episode
- isolation across facilities (list and continue)

#### W1-B1 · Dev B · 5 h · Prove a green frontend CI run on a PR (reduced)
Spec: T007.

Reduced scope (decided 7 Nov): all SG1 work is already committed and on `origin/main`, and frontend CI is green (`fa515a9`). This task only proves the frontend job is green on a PR. Record actual hours honestly; saved time goes to W1-A4.

Accept when the frontend CI job is green on the PR.

#### W1-B2 · Dev B · 3 h · Deploy frontend to Vercel, labelled staging everywhere
Spec: AT05.

Build:
- ~~Add a `VITE_ENV_LABEL` build variable and show a STAGING banner on every page, including Login.~~ Done in W1-B7 (7 Nov).
- Add the Vercel single-page-app rewrite (so `/episodes/<id>` deep links load), and set `VITE_ENV_LABEL=staging`.
- Write the Vercel checklist in `docs/delivery/staging.md`.

Accept when the staging URL shows the banner on every page, and login works against the staging API across domains.

#### W1-B3 · Dev B · 6 h · Run AT01–AT05 on staging; assemble the SG1 evidence pack
Spec: AT01–AT05, P01, P03.

Build: Rewrite `docs/delivery/evidence/SG1/report.md` so it no longer says "no remote" or "uncommitted" anywhere, and every result is tied to a real commit SHA and CI run. It must include:
- the candidate SHA
- CI run links
- each AT's steps, actual result and date
- browser screenshots of synthetic data
- a schema review (table list, constraints, roles)

Accept when every AT has an actual result, not a copied expected one. AT01–AT04 link to a CI run on that SHA; AT05 is a manual staging run (fresh checkout + browser login/create/read) recorded with that SHA.

#### W1-B4 · Dev B · 2 h · Refresh docs/status.md and create the reporting files
Build:
- Update `status.md`.
- Create `docs/delivery/progress.md` with every W1–W8 task row from this file, set to `Not started`. Task IDs and planned hours come from this file (the two-dev tracker workbook is not in the repo; the human updates it by hand from `progress.md`). Record at the top that Week 1 restarted on 9 Nov and all tracker dates shift +1 week.
- Create the `docs/delivery/weekly/` folder.

Accept when `progress.md` lists all tracker task IDs.

#### W1-B5 · Dev B · 4 h · WhatsApp provider comparison for the manager
Spec: M007, D06, G09, T011.

Build: Write `docs/decisions/D06-whatsapp-provider.md`. Compare Meta Cloud API direct with two or three Indian BSPs on:
- onboarding steps
- business verification lead time
- template approval
- per-conversation pricing in India
- webhook signing
- media access
- data location
- sandbox and test numbers
- support

Verify every price and rule on the provider's current site, cite it with a date, and mark anything unverified as unverified.

Accept when the document ends with a recommendation, a budget estimate for the pilot profile (200 messages a day), and a list of what the manager must start this week.

#### W1-B6 · Dev B · 2 h · Intake-field review packet for the doctor
Spec: M008, F002–F004.

Build: Write `docs/review/M008-intake-and-roles.md`. It contains:
- every intake field, with its type, whether it can be unknown, and a sample synthetic value
- the role limits per F004
- stage coverage, plus the excluded features with their G-IDs
- yes/no questions the doctor can answer quickly

Accept when the human can send it as-is.

#### W1-B7 (added) · Dev B · 8 h · UI foundation (D14 approved by the developer)
Build:
- Install the Part G stack (approved by the developer as D14 on 7 Nov), with exact pinned versions. Nothing outside the list.
- Add design tokens (colours, spacing, type) in one file.
- Replace the hash routing in `App.tsx` with react-router.
- Add a TanStack Query client wrapping the existing `api/client.ts`, keeping its retry, idempotency and refresh behaviour and its tests.
- Set up i18n with `en` only plus one empty second locale file. Do not assume a pilot language (D02 is open).
- Build the role-aware app shell (header, nav, STAGING banner, sign-out).
- Rebuild Login, Find mother, Register and Pregnancy view on the new components.

Accept when:
- The existing vitest suite still passes.
- All existing flows work at 360 px and 1280 px.
- The bundle size is reported (main JS gzipped). Flag it if over 250 KB.

#### W1-B8 (added) · Dev B · 2 h (estimate, not from the tracker) · D13–D15 decision proposals for the manager
Build: Write `docs/decisions/D13-episode-model.md`, `docs/decisions/D14-ui-dependencies.md` and `docs/decisions/D15-single-developer-review.md`. Each has status "Proposed", the options with risks, and Claude's recommendation. D14 also records that the developer approved the Part G list on 7 Nov. The manager decides; the human adds them to the tracker workbook.

Accept when the human can hand all three to the manager as-is.

**Not Claude's tasks this week:**
- Manager: record D01 (now one developer), D02 sites, language and pediatric reviewer, D03 merge approver, approve D04, decide D13, D14 and D15 (review rule); start WhatsApp verification.
- Doctor: M008 review.

---

### Week 2: SG2, pregnancy care
Tracker dates: 9–13 Nov. Demo Sat 14 Nov.

**Goal:** A clinician-approved ANC plan drives appointments, owned tasks, reports, referrals and a birth plan.

**Depends on:** the W1 gate, D04 and D07.

**Saturday demo:**
1. Publish an ANC plan.
2. Change a date and show that only future tasks move.
3. Upload a report and show it stays pending review.
4. Open the patient next-action view and urgent help.

**Pass condition:** AT06–AT10 and AT28 pass. An uploaded report is never shown as reviewed.

Note: D05 (the ANC template and urgent wording) arrives mid-week. Build against a clearly labelled **synthetic placeholder template** stored as data, never hard-coded. Swap in the approved one when D05 lands.

#### W2-A1 · Dev A · 4 h · Plan and task state model; private file storage
Spec: M009, T008, T009.

Build:
- Migrations for:
  - `care_plan_template` (versioned, approver, effective date)
  - `care_plan` (episode, template version, approved_by)
  - `appointment` (states: requested, confirmed, attended, missed, rescheduled, cancelled; `previous_appointment_id`)
  - `care_task` (states: new, assigned, awaiting patient, completed, cancelled; owner, backup, due, closure reason)
  - `investigation` (requested → performed → received → reviewed)
  - `file_object` (private)
- Add a `version` column for optimistic concurrency on every updatable table.
- Grants: done in W2-A2 (default grant removed, `grant_app_role` helper, `tests/test_db_grants.py`). Each new W2-A1 table calls the helper and is added to the test's list.
- Add a storage adapter: local disk in dev and Supabase Storage on staging. Downloads go only through an authorised API endpoint that streams the file or issues a signed URL valid for 5 minutes or less.
- Write the state-transition rules as pure functions, with unit tests.

Accept when:
- Illegal transitions are rejected.
- A stale `version` returns 409.
- A file is not reachable without auth, or from another facility.

#### W2-A2 · Dev A · 4 h · Patient and caregiver access mechanism; propose D07
Spec: M010, T010, F015, G10, G14.

Build: Write `docs/decisions/D07-patient-access.md`. It must cover:
- verification by staff-assisted check (phone possession alone is never enough)
- session on shared devices
- grant scope, expiry and revocation on the next request
- recovery

Do not invent the method. Present two or three options, with risks, for the manager. Implement only the data model (`caregiver_grant`) and the server-side scope check behind a feature flag until D07 is accepted.

Accept when the document is ready for decision, and the model and scope-check tests pass.

#### W2-A3 · Dev A · 5 h · API: dating, ANC plan, appointments, owned tasks
Spec: F005–F008, M011, AT06, AT07.

Build:
- Dating keeps provisional and confirmed values, with source and precision. Unknown stays null; never default it.
- Confirming or correcting dating is clinician-only and audited.
- Publishing a plan from the approved template version generates future appointments and tasks.
- A date correction cancels or replaces only **future, not-yet-attended** items. Past and completed events are untouched, and the change is audited.
- A missed visit creates exactly one owned follow-up task.

Accept when there are tests for:
- late presentation
- unknown LMP
- a correction that keeps the past intact
- a missed visit producing one task
- a non-clinician attempting to confirm (403)
- isolation across facilities

#### W2-A4 · Dev A · 6 h · API: reports, prescriptions, observations, referrals, contacts
Spec: F009–F012, F044, M012, AT08, AT09.

Build:
- Upload sets status to `received`. Only a clinician can set `reviewed`, with reviewer and time recorded.
- Prescriptions keep the original source and date. An ambiguous instruction creates review work and no reminder.
- Observations store the raw value, unit, service date, source and recorder. There is no threshold logic anywhere.
- Referral states: sent, contacted, attended, advice received, follow-up completed, or closed with a reason. Sending a message cannot close a referral.
- Add a verified local contacts table, with verifier and date.

Accept when the AT08 and AT09 scenarios run as API tests, and a grep confirms no code compares observation values to thresholds.

#### W2-A5 · Dev A · 2 h · API support for next-action view, birth plan and caregiver access
Spec: M013, F006, F013, F015.

Build:
- `GET /episodes/{id}/next-action` returns the single next confirmed action with date, place, preparation, status and help route.
- Birth-plan CRUD. Patient-reported "done", "not done" or "need help" stays separate from staff verification.
- Help requests create an owned task.

Accept when the endpoint returns "unknown" states honestly, and there are tests for both a patient report and staff verification.

#### W2-B1 · Dev B · 4 h · Screens: dating, ANC plan, appointment calendar, task list
Spec: M011.

Build:
- A dating card showing "Provisional" or "Confirmed by <clinician>" and "Unknown".
- Plan publish, available to clinician roles only.
- An appointment calendar and list with each state.
- A task list with owner, backup and overdue (worded as administrative).
- The staff **Today** worklist, version 1.

Accept when all four states plus the access-denied state are visible, and the screens work at 360 px.

#### W2-B2 · Dev B · 4 h · Screens: report upload, prescriptions, referrals, contacts
Spec: M012, AT08, AT09.

Build:
- Upload with a visible **Pending review** badge (amber, icon plus text).
- A review button shown only to clinicians, and enforced server-side as well.
- A referral tracker with a timeline of states.
- Prescription view showing the original document.

Accept when, for a non-clinician user, the review button is absent and a forced API call is rejected.

#### W2-B3 · Dev B · 6 h · Next-action view, birth plan, public urgent help, caregiver access
Spec: F006, F013–F015, M013, AT10, AT28.

Build:
- **My next step**: a large single card with an audio slot and buttons for "Done", "Couldn't go" and "Need help".
- A printable birth plan, using a print stylesheet.
- A public **Urgent help** route, with no login and no location permission. It shows the approved text, the verified numbers as `tel:` links and the support hours. It never says "wait for a reply" or implies dispatch.
- Caregiver grant screens behind a flag until D07.

Accept when urgent help works signed out with location denied, and on a slow 3G profile.

#### W2-B4 · Dev B · 5 h · Synthetic test cases for AT01–AT10 and AT28
Spec: M016.

Build: Extend `apps/api/tests/factories.py` with named synthetic scenarios:
- late presentation
- unknown LMP
- two women on one phone
- a caregiver who is then revoked
- an outside report

Write `docs/delivery/test-scripts/SG2.md`. It holds step-by-step manual scripts the manager can repeat at the demo.

Accept when every AT06–AT10 and AT28 case has both an automated test and a manual script.

#### W2-B5 · Dev B · 1 h · Doctor packet: ANC template and urgent wording
Spec: D05.

Build: Write `docs/review/D05-anc-template-urgent-wording.md`. It shows the placeholder template structure for the doctor to fill in and the urgent-help text slots. Never write the clinical content yourself.

**Not Claude's tasks this week:**
- Manager: provider choice, budget and template submission (M014, D06).
- Doctor: approve the ANC template and urgent wording (D05, M015).

---

### Week 3: SG3, real WhatsApp and voice
Tracker dates: 16–20 Nov. Demo Sat 21 Nov.

**Goal:** An approved template reaches a staff phone. Inbound text, voice and photo land in a staffed inbox.

**Depends on:** the W2 gate, D06, and approved templates.

**Saturday demo:**
1. Send an approved test reminder to a team phone.
2. Reply by voice and by photo.
3. The coordinator links, responds and closes.
4. Repeat the duplicate-webhook and opt-out tests.

**Pass condition:** AT11–AT14 pass on consenting staff numbers. One event creates one item. Nothing is sent after opt-out. **A mock connector does not pass this gate.**

If D06 or template approval is late, build against the provider's sandbox and mark the gate **Blocked: D06** in the weekly report. Never fake a pass.

#### W3-A1 · Dev A · 7 h · Provider adapter, signed webhook, durable outbox
Spec: M017, T011, T012, AT12, AT30.

Build:
- A `MessagingProvider` interface, with one real implementation for the D06 provider.
- Webhook signature verification; reject unsigned requests.
- An `outbox_message` table written in the **same transaction** as the business change.
- A worker that claims jobs with a lease (`SELECT … FOR UPDATE SKIP LOCKED`), retries with bounded backoff, and has a dead-letter state with an owner.
- Inbound dedupe on the provider event ID through a unique constraint.

Accept when there are tests for:
- the same webhook delivered twice gives one record
- two workers give no double send
- a worker killed mid-job recovers without resending

#### W3-A2 · Dev A · 3 h · Media privacy and inbox access rules
Spec: M018, F019, T013.

Build:
- Download inbound media into private storage immediately; never keep the provider URL as the access path.
- Size and type limits.
- An **unlinked** queue visible only to coordinators.

Accept when there are tests for an unsupported or oversized file and an unauthorised download.

#### W3-A3 · Dev A · 6 h · Outbound templates with delivery callbacks; four delivery states
Spec: M019, F017, AT11, AT12.

Build:
- States: `queued`, `submitted`, `delivered`, `failed`, kept distinct, plus `read` only if the provider reports it.
- Check eligibility **at send time**: opt-out, safe timing, the current appointment (so a stale reminder is dropped), and the service-window rules.

Accept when an opt-out made between queueing and sending blocks the send, and a provider timeout leaves the status as unknown and reconciled, never "delivered".

#### W3-A4 · Dev A · 4 h · Inbound text, voice and photo become inbox items
Spec: M020, F018, AT13.

Build:
- One event creates one inbox item.
- A shared number never auto-links. The item stays unlinked until staff confirm identity.
- Each item gets an owner and a backup.

Accept when the AT13 scenario passes as an automated test.

#### W3-B1 · Dev B · 8 h · Staff inbox for text, voice and photo
Spec: M020, F018.

Build: The inbox list, with filters for unlinked, mine and overdue. The item view includes:
- an audio player for the original voice note
- a photo viewer
- "Link to person", which requires choosing the person after an identity check and is audited
- reply, using a template or free text inside the service window
- assigning an owner or backup
- closing with an outcome

Accept when every action is audited and the screen works on a tablet.

#### W3-B2 · Dev B · 6 h · Audio playback, contact preferences, opt-out, phone fallback
Spec: M021, F016, F020, AT14.

Build:
- Approved audio, always shown with its text equivalent.
- Preferences: language, safe timing, detail level (minimal wording for shared phones), opt-out.
- A "Call instead" fallback task.

Accept when the AT14 scenario passes and preferences change what is sent.

#### W3-B3 · Dev B · 5 h · Test cases: duplicate webhook, failed send, opt-out, shared phone, bad file
Spec: M024, P06, P07.

Build:
- Automated tests.
- `docs/delivery/test-scripts/SG3.md`, covering consenting staff handsets only.
- An evidence checklist that keeps any real phone number or message text out of screenshots.

#### W3-B4 · Dev B · 1 h · Doctor packet: first audio batch and templates
Build: Write `docs/review/M023-templates-audio.md`, listing each template's wording and the audio scripts awaiting approval.

**Not Claude's tasks this week:**
- Manager: messaging demo, costs, safe-contact rules, inbox hours (M022), D08 narrator.
- Doctor: M023.

---

### Week 4: SG4, birth and early postpartum
Tracker dates: 23–27 Nov. Demo Sat 28 Nov.

**Goal:** Separate records, discharge and follow-up for the mother and each baby.

**Saturday demo:**
1. Move a twin birth through separate discharge.
2. Pause messages after a reported loss.
3. Transfer follow-up to another named team.

**Pass condition:** AT15–AT18 and AT29 pass. Maternal and pediatric reviewers validate the event handling.

#### W4-A1 · Dev A · 5 h · Birth, outcome and child data model with migrations
Spec: M025, T014, F021, F022.

Build:
- `child` as its own subject (`person` plus a child link). Each child has an explicit mother or guardian link.
- `birth_event` linking the episode to one or more children.
- Outcome and discharge events are per subject.
- A child can exist **without** a known pregnancy episode (AT29).

Accept when there are tests for twins with independent histories and for a child with incomplete history and no fabricated dates.

#### W4-A2 · Dev A · 4 h · Message pause and transfer concurrency design
Spec: M026, T015.

Build: Write `docs/decisions/M026-pause-transfer.md`. It covers:
- a pause flag checked inside the send transaction
- how in-flight messages are handled and logged
- transfer as a handover with an accept step

Accept when the design is reviewed by the human and the edge cases are listed.

#### W4-A3 · Dev A · 6 h · API: birth, twins, child linking, separate discharge
Spec: M027, F021, F023, AT15, AT16.

Build: Discharge is recorded per subject, clinician-only, with instructions and follow-up. **No metric can clear a discharge.**

Accept when the AT15 and AT16 tests pass.

#### W4-A4 · Dev A · 5 h · API: loss pause, transfer, readmission
Spec: M028, F026–F028, AT17, AT18.

Build:
- A reported loss **immediately** pauses incompatible unsent messages for the affected subject only. Confirmation follows, and maternal support continues.
- Transfer: open tasks move to a named receiving owner and must be accepted; there is no silent closure.
- Readmission preserves the original dates and source.

Accept when the AT17 test passes with one twin affected and the sibling unaffected, and the AT18 test passes.

#### W4-B1 · Dev B · 5 h · Screens: birth, twins, child linking, separate discharge
Spec: M027.

Build: Birth entry for one to N children, with each child getting its own record page. Discharge is a separate card per subject.

#### W4-B2 · Dev B · 4 h · Screens: loss pause, transfer, readmission
Spec: M028.

Build:
- Loss reporting uses careful, minimal wording and shows the pause confirmation. All wording is placeholder until the doctor approves it.
- A transfer handover screen with an accept step.
- Readmission entry.

#### W4-B3 · Dev B · 7 h · Separate postpartum and newborn follow-up views; missed contacts
Spec: M029, F024, F025.

Build:
- Due/overdue tracking for postnatal contacts, using the local approved schedule (placeholder until approved).
- A private wellbeing or safety concern entry that routes to a human. There is **no screening score**.
- A family-planning note.

#### W4-B4 · Dev B · 4 h · Test cases: twins, discharge, loss, transfer, queued messages
Spec: M032.

Build: Automated tests plus `docs/delivery/test-scripts/SG4.md`.

**Not Claude's tasks this week:**
- Manager: book week-7 field users (M030).
- Doctor and pediatric reviewer: M031.

---

### Week 5: SG5 part 1, child care, offline drafts, content
Tracker dates: 30 Nov–4 Dec. Demo Sat 5 Dec.

**Goal:** Child journeys independent of the mother's episode, plus offline field drafts.

**Saturday demo:**
1. Record an outside vaccine and raw measurements with no interpretation.
2. Create a visit draft offline.
3. Reconnect twice and show a single server record.

**Pass condition:** AT19–AT21 pass. This is an interim check, not a gate.

#### W5-A1 · Dev A · 7 h · Offline draft rules
Spec: M033, M036, T016, F033, AT20.

Build:
- Each draft carries a client operation ID (UUID) and a base `version`.
- The server applies a draft once per operation ID.
- If the base version is stale against a clinician change, the result is a **conflict for human review**, never an overwrite.
- Only drafts of visits assigned to that worker are accepted.

Accept when there are tests for replaying the same draft twice, a stale base version and an unassigned worker.

#### W5-A2 · Dev A · 4 h · Child schedule boundaries; guardian and content-withdrawal controls
Spec: M033, M034, F032, T017.

Build: The child plan is clinician-approved and versioned. The child plan continues when the maternal episode closes. Guardian grants have a lifecycle.

#### W5-A3 · Dev A · 5 h · API: infancy and early-childhood workflows, vaccines, measurements
Spec: M035, F029–F031, AT19.

Build:
- Vaccine doses carry a source (given here / outside / unknown) and a verification step. Duplicate doses are prevented.
- Measurements are raw only, with **no growth classification**.
- Milestones are recorded as reported.

#### W5-A4 · Dev A · 4 h · API: guardian permissions; content publish and withdraw
Spec: M037, F032, F034, AT21.

Build: Content versions carry language, matching text and audio, approver and expiry. A withdrawn version can never be newly distributed.

#### W5-B1 · Dev B · 6 h · Screens: infancy, early childhood, vaccines, measurements with no interpretation
Spec: M035.

Build: A vaccine list showing due/given/unknown against the approved plan, a measurement history table, milestones, and child referrals.

#### W5-B2 · Dev B · 8 h · Offline field drafts in the browser
Spec: M036, F033, AT20, P16, P18.

Build:
- Add vite-plugin-pwa (needs approval).
- Store drafts in IndexedDB, holding drafts only, never full patient records.
- Show pending and failed states honestly, with one-record retry.
- Show conflicts visibly.
- Clear local drafts on logout, as designed.

Accept when the test passes on Chrome on a low-end Android device (or emulation): offline, reload, reconnect twice, one server record.

#### W5-B3 · Dev B · 3 h · Content publish/withdraw and guardian screens
Spec: M037.

#### W5-B4 · Dev B · 4 h · Test child access and weak-network drafts on a low-end Android
Spec: M040.

Build: Write the device test report at `docs/delivery/evidence/SG5/device-tests.md`, recording device, network profile, steps and results.

**Not Claude's tasks this week:**
- Manager: 12 education packages (M038), D09 review.
- Doctor and pediatric reviewer: M039.

---

### Week 6: SG5, MVP complete
Tracker dates: 7–11 Dec. Demo Sat 12 Dec.

**Goal:** All eight journey stages built, traced and passing.

**Saturday demo:**
1. Run the full functional suite at the candidate SHA.
2. Show the worklist, failure queue, reminder pause, audit view and a safe export.
3. Run everything with AI disabled.

**Pass condition:** AT01–AT23 and AT28–AT32 pass, and every mandatory requirement is mapped to evidence.

#### W6-A1 · Dev A · 6 h · Security review and requirement traceability
Spec: M041, AT32.

Build:
- Write `docs/delivery/traceability.md`, mapping each of F001–F044 to its code, tests, AT and evidence.
- Run a security pass: authz on every route (generate the route list and check that each one has a scope dependency), `pip-audit`, `npm audit`, log scrubbing, and file upload rules.

Accept when no route is left unchecked and every finding is logged with its severity.

#### W6-A2 · Dev A · 5 h · Staging/production separation, backup and deploy plan
Spec: M042, T020.

Build: Write `docs/delivery/release-plan.md` covering separate configuration and secrets, the migration order, backup schedule, rollback steps and the vendor data-flow list for D09.

#### W6-A3 · Dev A · 5 h · API: privacy rights requests, audit views, safe exports
Spec: M043, F036, F037, AT22.

Build: An owned rights-request workflow, where deletion goes to review and is never automatic. Exports are scoped and protected against spreadsheet formula injection. Audit queries are restricted to authorised roles.

#### W6-A4 · Dev A · 5 h · Fix defects from the Dev B full-suite run
Each fix links to an F-ID in the Feedback sheet.

#### W6-B1 · Dev B · 7 h · Operational worklist, failure queue, reminder pause
Spec: M044, F038, F039, AT23.

Build: The worklist, failure queue and reminder pause switch, each showing owner/backup and a last-updated time. Administrative metrics only.

#### W6-B2 · Dev B · 3 h · Audit view and export screens
Spec: M043.

#### W6-B3 · Dev B · 5 h · Close scope gaps; AI-disabled runs
Spec: M045, F040, AT31.

Build: Add a single `AI_FEATURES_ENABLED=false` switch (AI should already be off everywhere). Run every core journey with it off, and confirm no scoring or interpretation exists anywhere.

#### W6-B4 · Dev B · 6 h · Full functional suite at the candidate SHA
Spec: M048.

Build: Write `docs/delivery/evidence/SG5/report.md` with the actual result of every AT at one SHA.

**Not Claude's tasks this week:**
- Manager: feature completeness, pilot ops draft (M046), D10, booking sign-off meetings.
- Doctor: sign or block the 12 content packages (M047).

---

### Week 7: SG6, field validation and resilience
Tracker dates: 14–18 Dec. Demo Sat 19 Dec.

**Pass condition:**
- AT24–AT27 pass.
- At least 5 of 6 users succeed with no safety-critical misunderstanding.
- RPO is 24 h or less, and RTO is 4 h or less.

#### W7-A1 · Dev A · 8 h · Timed restore, rollback and load drills
Spec: M049, AT25, AT26, T021, T022.

Build:
- A load script for the pilot profile: 100 synthetic records, 10 concurrent staff, 200 messages a day. Report p95 times and errors.
- A restore into an isolated database, with timings.
- A release rollback, with timings.

Record everything in `docs/delivery/evidence/SG6/drills.md`.

#### W7-A2 · Dev A · 4 h · Triage security and field findings
Spec: M050.

#### W7-A3 · Dev A · 6 h · Hardening regressions
Spec: M052.

#### W7-B1 · Dev B · 3 h · Prepare devices, staging accounts and observation sheet for field sessions
Build: Write `docs/delivery/field-sessions/observation-sheet.md` and a per-user script for: next action, audio, and asking for help.

#### W7-B2 · Dev B · 10 h · Fix usability defects seen in field sessions
Spec: M051, AT24.

Each fix gets an F-ID and a retest.

#### W7-B3 · Dev B · 6 h · Independent re-check of drills and regressions
Spec: M055.

You are the same person who ran the drills, so record this honestly as a "self re-run". Ask the manager to witness one drill live.

**Not Claude's tasks this week:**
- Manager: field sessions, ops rehearsal (M053), D11 support roster.
- Doctor: M054.

---

### Week 8: SG7, pilot release candidate
Tracker dates: 21–24 Dec. Release candidate Thu 24 Dec.

**Pass condition:**
- AT01–AT32 are current at the candidate SHA.
- No critical or high defects remain.
- Technical, clinical and operating sign-offs are recorded.

#### W8-A1 · Dev A · 6 h · Candidate SHA, migration and deploy rehearsal
Spec: M056.

#### W8-A2 · Dev A · 4 h · Technical release review pack
Spec: M057.

Build: `docs/delivery/evidence/SG7/technical-review.md`.

#### W8-A3 · Dev A · 6 h · Release-candidate defect fixes, backend only
Spec: M058.

#### W8-B1 · Dev B · 5 h · Release-candidate defect fixes, frontend only
Spec: M058.

#### W8-B2 · Dev B · 6 h · Setup package, training guide and final demo
Spec: M059.

Build: `docs/training/staff-guide.md` (plain language, with screenshots of synthetic data) and `docs/training/demo-script.md`.

#### W8-B3 · Dev B · 5 h · Release acceptance and clean-setup check on a fresh machine
Spec: M062.

Build: Follow the README from a fresh clone and record every step that failed or was unclear.

**Not Claude's tasks this week:**
- Manager: three sign-offs and go/no-go (D12).
- Doctor and pediatric reviewer: final acceptance or explicit hold (M061).

### Reserve: 28–31 Dec
W9-A1 and W9-B1: release-candidate corrections only. No new features.

---

## Part I: Stop conditions (Claude must stop and ask)

Stop and ask before going further if any of these happens:

- A task needs a clinical rule, schedule, dose, threshold or wording that a doctor has not approved.
- A decision listed under "depends on" is still Open, and the work cannot proceed behind a flag or placeholder.
- A test would have to be weakened, skipped or deleted to pass.
- A change touches authentication, the database roles, secrets, a paid service or production.
- Real patient data or a real phone number appears anywhere.
- A task is heading 50% or more over its planned hours.
