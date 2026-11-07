# JananiSaathi / MatriSathi: phase plan

This file lives at `docs/delivery/PHASE_PLAN.md` and is committed to the repository (it was kept local until 2026-11-07).

**Dates:** Week 1 restarted on Mon 9 Nov (decided 7 Nov). Use the "If restarted 9 Nov" column below; every tracker date shifts +1 week.

It groups the two-developer tracker into **Phase 0 (foundation) plus six build phases**. For each phase it gives:
- the goal and scope
- the tasks
- the exit criteria
- the meeting evidence

Task-level detail (what to build, files, acceptance criteria) lives in `docs/delivery/CLAUDE_BUILD_PLAN.md`, Part H. This file never repeats it. Claude reads both.

---

## 1. The phases at a glance

| Phase | Name | Gate | Tracker week | Tracker dates | If restarted 9 Nov | Care stages | Spec IDs | Dev A h | Dev B h |
|---|---|---|---|---|---|---|---|---|---|
| 0 | Foundation | SG0 + SG1 | 1 | 2–6 Nov | 9–13 Nov | 1 (registration) | F001–F004 | 25 | 30 |
| 1 | Pregnancy care | SG2 | 2 | 9–13 Nov | 16–20 Nov | 1, 2, 3 | F005–F015, F044 | 21 | 20 |
| 2 | Messaging | SG3 | 3 | 16–20 Nov | 23–27 Nov | 2 (all stages use it) | F016–F020 | 20 | 20 |
| 3 | Birth & postpartum | SG4 | 4 | 23–27 Nov | 30 Nov–4 Dec | 4, 5, 6 | F021–F028 | 20 | 20 |
| 4 | Child care & field work | SG5 part 1 | 5 | 30 Nov–4 Dec | 7–11 Dec | 7, 8 + field worker | F029–F035 | 20 | 21 |
| 5 | MVP complete | SG5 | 6 | 7–11 Dec | 14–18 Dec | All | F036–F040 | 21 | 21 |
| 6 | Pilot readiness | SG6 + SG7 | 7–8 | 14–24 Dec | 21–31 Dec | All | F041–F043 | 34 | 35 |
| R | Reserve | — | 9 | 28–31 Dec | 4–8 Jan | — | — | — | — |

The hours come from the tracker's Role Tasks sheet (the workbook is not in the repo; `CLAUDE_BUILD_PLAN.md` Part H is the source). Phase 0 also includes the added tasks W1-A5 (4 h) and W1-B7 (8 h), plus W1-B8 (2 h, estimate) added 7 Nov, which is not in the 30 h above.

**Rule:** a phase starts only when the previous phase's exit gate is accepted at the Saturday review. If a gate fails, the next phase may start only on work that does not depend on the failed part, and the weekly report must say so.

**Dates:** if Week 1 starts on 9 Nov, Phase 6 falls in the holiday week. Agree with the manager whether the release candidate moves to around 31 Dec or into the reserve week.

---

## 2. How Claude works with phases

Each phase follows the same four steps.

1. **Phase kick-off.** Claude writes `docs/delivery/phases/P<n>-plan.md`. It confirms:
   - entry criteria, met or not
   - open decisions
   - the task order for both lanes
   - the demo script outline

   Then Claude waits for approval.
2. **Tasks.** Claude runs each task ID through the loop in Part C of `CLAUDE_BUILD_PLAN.md`.
3. **Phase close.** Claude writes `docs/delivery/phases/P<n>-close.md` containing:
   - each exit criterion with its actual evidence
   - AT and pilot-check results
   - Dev A and Dev B % accepted, as proposals
   - open defects
   - carry-over tasks
4. **Phase dashboard.** Claude updates `docs/delivery/phases.md` (template in section 10). This is the single page to show at the meeting.

Claude never marks a phase or task `Accepted`. Only the manager does that, at the Saturday review.

---

## Phase 0: Foundation (SG0 + SG1)

**Goal:** a working, CI-verified, deployed foundation that everything else builds on. That means:
- staff login
- registering a mother
- a pregnancy episode
- facility isolation
- audit
- the new UI kit

**Entry criteria:** none. This phase starts now.

**Scope in:**
- branch protection and the PR flow
- green CI tied to a commit SHA
- a hardened, synthetic-only staging deployment
- the D04 auth design document
- the episode model
- the UI foundation and app shell
- the WhatsApp provider comparison
- the doctor's intake review packet
- the reporting files

**Scope out:** any new clinical feature.

**Tasks:**

| Dev A (backend and platform) | Dev B (frontend and quality) |
|---|---|
| W1-A1 Protect main, PR flow, CI tied to SHA | W1-B1 Prove green frontend CI on a PR (reduced) |
| W1-A2 Prove green backend CI on a PR (reduced) | W1-B2 Frontend staging on Vercel, STAGING banner |
| W1-A3 D04 auth/tenant/audit design proposal | W1-B3 Run AT01–AT05; rewrite SG1 evidence pack |
| W1-A4 Harden and deploy backend staging (all committed defaults; separate Supabase project) | W1-B4 status.md, progress.md, reporting files |
| W1-A5 (added) Episode model part 1: list + continue (late in week; index held for D13) | W1-B5 WhatsApp provider comparison (D06) |
| | W1-B6 Doctor intake review packet (M008) |
| | W1-B7 (added) UI foundation and app shell |
| | W1-B8 (added) D13–D15 decision proposals |

**Screens delivered:**
- Staff console: Login, Find mother, Register mother and Pregnancy view, rebuilt on the new UI kit
- App shell: STAGING banner and role-aware navigation

**Decisions needed:**
- D01 team change and hours
- D02 pilot sites, language and pediatric reviewer
- D03 merge approver
- D04 auth design
- D13 episode model (manager; not decided; blocks only the 409 + partial unique index part of W1-A5)
- D14 UI dependencies (Part G list approved by the developer 7 Nov; manager informed Saturday)
- D15 review rule for one developer (manager). Until D03/D15 are decided, the developer approves and merges every PR.

D13–D15 are recorded as `docs/decisions/D13-*.md`, `D14-*.md`, `D15-*.md` (status "Proposed") by W1-B8. The human adds them to the tracker workbook.

**Gap decisions to settle:** G01, G02, G03, G04, G07, G09, G15, G17 and G20, which are all "before build".

**Exit criteria:**
- AT01–AT04 pass in CI on one SHA.
- AT05 passes as a manual run on staging (fresh checkout, browser login/create/read, reload and restart), recorded with that commit SHA.
- Pilot checks P01 (shared phone) and P03 (wrong facility denied) pass.
- Staging runs synthetic data only, on its own Supabase project (never the shared team database), with no committed default working (seed password, app-role password, JWT secret), migrations run as a separate release step, and the app database role unable to change the schema.
- The manager accepts the SG1 evidence pack.
- D13, D14 and D15 are decided.

**Saturday demo:**
1. Merge a PR with green CI.
2. Log in on staging.
3. Register a synthetic mother, then find her and continue her existing episode (no new episode created).
4. Show a wrong-facility request being blocked.
5. Repeat it on a phone.

**Evidence folder:** `docs/delivery/evidence/SG1/`

**Main risk:** WhatsApp business verification has a long lead time. The manager must start it in this phase, or Phase 2 slips.

---

## Phase 1: Pregnancy care (SG2)

**Goal:** a clinician-approved ANC plan drives the rest of pregnancy care: appointments, owned tasks, reports, referrals, the birth plan, and the mother's next-step view.

**Entry criteria:**
- The Phase 0 gate is accepted.
- D04 is decided.
- D07 (patient access) is proposed.
- The ANC template (D05) is at least drafted. Until the doctor approves it, Claude uses a labelled placeholder template.

**Scope in:**
- dating, with provisional, confirmed and unknown states
- a versioned ANC plan
- appointment states
- owned tasks with a backup owner
- private file storage
- reports that move requested → performed → received → reviewed
- prescriptions shown from the original document
- raw observations
- referral states through to closure
- verified local contacts
- the birth plan
- public urgent help
- caregiver access

**Scope out (excluded by the gap decisions):**
- risk scores (G01)
- vital-sign thresholds or alerts (G01)
- hospital matching (G03)
- SOS dispatch or ETA (G03)

**Tasks:**

| Dev A | Dev B |
|---|---|
| W2-A1 Plan and task state model; private files | W2-B1 Dating, ANC plan, calendar, task list, Today worklist |
| W2-A2 Patient/caregiver access; propose D07 | W2-B2 Report upload "Pending review", prescriptions, referrals |
| W2-A3 API: dating, ANC plan, appointments, tasks | W2-B3 My next step, birth plan, urgent help, caregiver screens |
| W2-A4 API: reports, prescriptions, observations, referrals, contacts | W2-B4 Synthetic test cases and manual scripts |
| W2-A5 API: next action, birth plan, caregiver | W2-B5 Doctor packet: ANC template and urgent wording |

**Screens delivered:**
- Staff console: Today worklist v1, dating card, plan publishing, calendar, tasks, reports, referrals
- Mother: My next step, printable birth plan, public Urgent help page

**Decisions needed:** D05 ANC template and urgent wording (doctor); D07 patient access (manager).

**Gap decisions to settle:** G05 (local schedules), G06 (role limits), G10 (identity and episodes) and G14 (privacy enforcement).

**Exit criteria:**
- AT06–AT10 and AT28 pass.
- Pilot checks P02, P04, P05, P08, P09 and P10 pass.
- An uploaded report is never shown as reviewed.
- A date correction moves only future tasks.
- Urgent help works signed out with location denied.

**Saturday demo:**
1. Publish an ANC plan for a late-presenting mother with an unknown LMP.
2. Correct the date and show that only future tasks moved.
3. Upload a report and show it stays "Pending review".
4. Track a referral through to return advice.
5. Open urgent help signed out.

**Evidence folder:** `docs/delivery/evidence/SG2/`

**Main risk:** the doctor approves the ANC template late. Mitigation: build against the placeholder template held as data, and swap it without code changes.

---

## Phase 2: Messaging (SG3)

**Goal:** real WhatsApp and voice working end to end. An approved template reaches a phone, and the mother's text, voice and photo replies land in a staffed inbox.

**Entry criteria:**
- The Phase 1 gate is accepted.
- D06 (provider) is decided.
- Message templates are submitted or approved.
- Consenting staff test numbers are available.

**Scope in:**
- the provider adapter
- signed webhooks
- a durable outbox, with lease-claimed jobs and bounded retries
- four distinct delivery states
- checks at send time (opt-out, current appointment, service-window rules)
- inbound text, voice and photo
- the unlinked queue
- identity confirmation before linking
- the staff inbox
- approved audio with its text equivalent
- contact preferences
- phone fallback

**Scope out:**
- automated replies with clinical content
- transcription agents
- automated calling (deferred under R09)

**Tasks:**

| Dev A | Dev B |
|---|---|
| W3-A1 Provider adapter, signed webhook, durable outbox | W3-B1 Staff inbox: owner, backup, link, reply, close |
| W3-A2 Media privacy and inbox access rules | W3-B2 Audio playback, preferences, opt-out, phone fallback |
| W3-A3 Outbound templates, delivery states, send-time checks | W3-B3 Tests: duplicate webhook, failed send, opt-out, shared phone, bad file |
| W3-A4 Inbound items: one event makes one item | W3-B4 Doctor packet: templates and audio |

**Screens delivered:**
- Staff console: inbox, item view (audio player, photo viewer), contact preferences
- Mother: WhatsApp templates; audio on the My next step page

**Decisions needed:**
- D06 WhatsApp provider, budget and test numbers
- D08 narrator and language reviewer

**Gap decisions to settle:** G13 (content approval and withdrawal).

**Exit criteria:**
- AT11–AT14 pass on real consenting staff numbers. **A mock connector does not pass.**
- Pilot checks P06 and P07 pass.
- A duplicate webhook creates one item.
- Nothing is sent after opt-out.
- Two workers never send the same message twice.

**Saturday demo:**
1. Send an approved reminder to a team phone.
2. Reply by voice and by photo.
3. The coordinator links, replies and closes.
4. Repeat the duplicate-webhook and opt-out tests live.

**Evidence folder:** `docs/delivery/evidence/SG3/`. Screenshots must not show real phone numbers.

**Main risk:** provider onboarding or template approval is late. If so, build and test on the provider's sandbox, and report the gate as **Blocked: D06**, never as passed. Phase 3 can still start, because it does not depend on live messaging.

---

## Phase 3: Birth & postpartum (SG4)

**Goal:** separate records, discharge and follow-up for the mother and each baby, with loss, transfer and readmission handled safely.

**Entry criteria:** the Phase 2 gate is accepted, or Phase 2 is blocked only on the live provider.

**Scope in:**
- birth events
- twins
- a child as its own subject, including a child with incomplete history
- discharge recorded separately per subject, by a clinician only
- loss pausing incompatible messages immediately
- transfer with a named receiving owner and an accept step
- readmission
- postnatal contacts at 48 h, 7–14 days and 6 weeks
- private wellbeing concerns routed to a human
- family-planning notes

**Scope out (excluded by the gap decisions):**
- discharge-readiness evaluation (G02)
- PPD/EPDS scoring (G07)
- dehydration and colic detection (G07)
- contraction triage and geofencing (G03)

**Tasks:**

| Dev A | Dev B |
|---|---|
| W4-A1 Birth, outcome and child data model | W4-B1 Birth, twins, child linking, separate discharge screens |
| W4-A2 Pause and transfer concurrency design | W4-B2 Loss pause, transfer, readmission screens |
| W4-A3 API: birth, twins, child linking, discharge | W4-B3 Postpartum and newborn follow-up; missed contacts |
| W4-A4 API: loss pause, transfer, readmission | W4-B4 Tests: twins, discharge, loss, transfer, queued messages |

**Screens delivered:**
- Staff console: birth entry for 1–N children, a page per child, discharge cards, loss pause, transfer handover, postnatal follow-up views

**Decisions needed:** the doctor and pediatric reviewer approve the birth and loss wording (M031). The manager books the Phase 6 field users (M030).

**Gap decisions to settle:** G11 (closure states) and G12 (loss, readmission and transfer).

**Exit criteria:**
- AT15–AT18 and AT29 pass.
- Pilot checks P11, P12 and P13 pass.
- In a twin loss, one child is affected and the sibling is not.
- No metric can clear a discharge.

**Saturday demo:**
1. Take a twin birth through separate discharge.
2. Report a loss and show the queued messages pause.
3. Transfer follow-up to another named team.

**Evidence folder:** `docs/delivery/evidence/SG4/`

**Main risk:** sensitive wording for loss. Every message stays placeholder until the doctor approves it.

---

## Phase 4: Child care & field work (SG5 part 1)

**Goal:**
- child care that continues independently of the mother's episode
- a field worker view with offline drafts
- an approved content library

**Entry criteria:** the Phase 3 gate is accepted.

**Scope in:**
- a clinician-approved, versioned child plan
- vaccine doses with source (given here, outside, unknown) and a verification step
- raw measurements
- reported milestones
- child referrals
- the guardian permission lifecycle
- offline visit drafts with operation IDs, version checks and conflicts sent for human review
- the field worker's mobile view as an installable app (PWA)
- content publishing and withdrawal

**Scope out:**
- growth classification and WHO chart interpretation (G07)
- screening prompts (G07)
- official vaccine certificates (G08)
- Anganwadi sync (G08)
- a parent-selected vaccine schedule switch (G08)

**Tasks:**

| Dev A | Dev B |
|---|---|
| W5-A1 Offline draft rules | W5-B1 Infancy, early childhood, vaccines, measurements screens |
| W5-A2 Child schedule, guardian, content withdrawal | W5-B2 Offline field drafts in the browser (PWA) |
| W5-A3 API: infancy and early childhood, vaccines, measurements | W5-B3 Content publish/withdraw, guardian screens |
| W5-A4 API: guardian, content publish/withdraw | W5-B4 Low-end Android and weak-network tests |

**Screens delivered:**
- Staff console: child record (vaccines, measurement history, milestones, referrals), content library
- Field worker: today's visits, visit form, offline status

**Decisions needed:**
- The doctor and pediatric reviewer approve child schedules and content (M039).
- The manager prepares the 12 education packages (M038) and starts the D09 hosting review.

**Gap decisions to settle:** G08 (vaccines) and G16 (offline correctness).

**Exit criteria (interim check, not a gate):**
- AT19–AT21 pass.
- Pilot checks P14–P17 pass.
- An offline draft replayed twice produces exactly one server record.
- A stale draft can never overwrite a clinician's change.

**Saturday demo:**
1. Record an outside vaccine and a raw measurement.
2. Create a visit draft offline.
3. Reconnect twice and show a single record.
4. Make a conflicting clinician edit and show it goes to review.

**Evidence folder:** `docs/delivery/evidence/SG5/interim/`

**Main risk:** offline sync is the hardest engineering in the project. Keep it narrow: drafts of assigned visits only, never full records stored on the device.

---

## Phase 5: MVP complete (SG5)

**Goal:** all eight care stages built, traced to the spec and passing. The operations, privacy and audit tools are in place, and everything works with AI turned off.

**Entry criteria:** the Phase 4 interim check has passed.

**Scope in:**
- the security review
- a traceability matrix mapping F001–F044 to code, tests and evidence
- staging/production separation
- the backup and deploy plan
- privacy rights requests
- audit views
- safe, scoped exports
- the operational worklist
- the failure queue
- the reminder pause switch
- a full run with AI disabled
- the full test suite at one commit SHA

**Scope out:** new features. Anything new goes through a scope swap agreed with the manager.

**Tasks:**

| Dev A | Dev B |
|---|---|
| W6-A1 Security review and traceability | W6-B1 Ops worklist, failure queue, reminder pause |
| W6-A2 Staging/prod separation, backup and deploy plan | W6-B2 Audit view and export screens |
| W6-A3 API: rights requests, audit views, safe exports | W6-B3 Close scope gaps; AI-disabled runs |
| W6-A4 Fix defects from the full-suite run | W6-B4 Full functional suite at the candidate SHA |

**Screens delivered:**
- Staff console: ops worklist, failure queue, pause switch, audit view, exports, privacy requests

**Decisions needed:**
- D09 hosting, retention and vendor review
- D10 recovery, load and budget thresholds
- The doctor signs or blocks the 12 content packages (M047).

**Exit criteria:**
- AT01–AT23 and AT28–AT32 pass at one SHA.
- Pilot check P18 passes.
- Every mandatory requirement is mapped to evidence in `traceability.md`.
- No scoring or interpretation exists anywhere in the code.

**Saturday demo:**
1. Run the full suite at the candidate SHA.
2. Show the worklist, failure queue, reminder pause, audit view and a safe export.
3. Repeat the core journeys with AI disabled.

**Evidence folder:** `docs/delivery/evidence/SG5/`

**Main risk:** defects pile up from earlier phases. Every phase closes its own defects, so this phase is not a catch-all.

---

## Phase 6: Pilot readiness (SG6 + SG7)

**Goal:**
- real users complete the core tasks
- restore, rollback and load drills succeed
- one release-candidate SHA is ready with complete evidence, trained staff and three sign-offs

**Entry criteria:**
- The Phase 5 gate is accepted.
- Field users are booked (M030).
- Sign-off meetings are booked.

**Scope in:**
- field sessions with 3 rural and 3 semi-urban users
- usability fixes
- restore, rollback and load drills
- an ops rehearsal
- security and field triage
- the candidate SHA
- migration and deploy rehearsal
- the technical review pack
- defect fixes
- the staff training guide
- a clean setup on a fresh machine

**Scope out:** any feature work. From the start of this phase, only fixes are allowed.

**Tasks:**

| Week | Dev A | Dev B |
|---|---|---|
| 7 (SG6) | W7-A1 Restore, rollback and load drills | W7-B1 Devices, accounts, observation sheet |
| | W7-A2 Triage security and field findings | W7-B2 Fix usability defects from field sessions |
| | W7-A3 Hardening regressions | W7-B3 Re-check drills and regressions |
| 8 (SG7) | W8-A1 Candidate SHA, migration and deploy rehearsal | W8-B1 Release-candidate fixes (frontend) |
| | W8-A2 Technical release review pack | W8-B2 Setup package, training guide, final demo |
| | W8-A3 Release-candidate fixes (backend) | W8-B3 Clean setup on a fresh machine |

**Decisions needed:** D11 live support roster; D12 pilot go/no-go.

**Gap decisions to settle:** G18 (storage, recovery and monitoring) and G19 (live support owner).

**Exit criteria:**
- **SG6:**
  - AT24–AT27 pass.
  - At least 5 of 6 users succeed with no safety-critical misunderstanding.
  - Restore meets RPO ≤ 24 h and RTO ≤ 4 h.
  - Pilot checks P19–P22 pass.
- **SG7:**
  - AT01–AT32 are current at the candidate SHA.
  - No critical or high defects remain.
  - Pilot checks P23 and P24 pass.
  - Technical, clinical and operating sign-offs are recorded.

**Saturday demos:**
- SG6: field-session results and the fixes made; a timed restore and rollback.
- SG7: a clean setup on a fresh machine, and the final end-to-end demo on the deployed candidate.

**Evidence folders:** `docs/delivery/evidence/SG6/` and `docs/delivery/evidence/SG7/`

**Main risk:** the holiday week. If sign-offs cannot happen before the reserve week ends, record an explicit hold and a new date. Do not hold a partial go-live.

---

## Reserve: corrections only

Tasks W9-A1 and W9-B1 cover fixes to the release candidate only. The manager agrees a re-estimated date for anything unfinished (W9-W1).

---

## 10. Phase dashboard (the page for the meeting)

Claude keeps `docs/delivery/phases.md` in this format and updates it at every phase close and every Friday:

```markdown
# Phase dashboard (updated <date>, SHA <short-sha>)

| Phase | Gate | Status | Dev A tasks accepted | Dev B tasks accepted | ATs pass / required | Pilot checks pass / required | Open decisions | Blockers |
|---|---|---|---|---|---|---|---|---|
| 0 Foundation | SG0+SG1 | Not started / In progress / Ready for review / Accepted / Blocked | 0/5 | 0/8 | 0/5 | 0/2 | D01 D02 … | … |
| 1 Pregnancy care | SG2 | … | 0/5 | 0/5 | 0/6 | 0/6 | D05 D07 | … |
| 2 Messaging | SG3 | … | 0/4 | 0/4 | 0/4 | 0/2 | D06 D08 | … |
| 3 Birth & postpartum | SG4 | … | 0/4 | 0/4 | 0/5 | 0/3 | — | … |
| 4 Child & field | SG5 interim | … | 0/4 | 0/4 | 0/3 | 0/4 | — | … |
| 5 MVP complete | SG5 | … | 0/4 | 0/4 | 0/28 | 0/1 | D09 D10 | … |
| 6 Pilot readiness | SG6+SG7 | … | 0/6 | 0/6 | 0/32 | 0/6 | D11 D12 | … |

## Current phase: <n>, <one-line status>
## What was shown at the last Saturday review
## Next phase entry criteria: met / not met (which)
```

Count rules:
- A task counts as accepted only when the manager has accepted it.
- An AT counts as passing only if it was actually run at a recorded SHA.
- Never copy an expected result into the actual-result field.

---

## 11. Prompts to paste into Claude Code

**Start a phase**
```
Read CLAUDE.md, docs/delivery/CLAUDE_BUILD_PLAN.md and docs/delivery/PHASE_PLAN.md.
Start Phase <n>. Write docs/delivery/phases/P<n>-plan.md: entry criteria (met or not, with evidence),
open decisions and what each blocks, task order for Dev A and Dev B lanes, and the Saturday demo outline.
Do not write code yet; wait for my approval.
```

**Work a task inside the phase**
```
Phase <n>: do task <TASK-ID> following Part C of CLAUDE_BUILD_PLAN.md. Propose the plan first and wait.
```

**Close a phase**
```
Close Phase <n>. Check every exit criterion in PHASE_PLAN.md against real evidence (merged PRs, CI runs at one SHA,
AT and pilot-check results you actually ran). Write docs/delivery/phases/P<n>-close.md and update docs/delivery/phases.md.
Mark unmet criteria clearly. Propose Dev A / Dev B % accepted. List carry-over tasks and defects.
```
