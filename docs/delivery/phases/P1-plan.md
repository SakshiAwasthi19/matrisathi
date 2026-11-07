# Phase 1 plan: Pregnancy care (SG2)

Written 2026-11-07 at SHA `8391172`. Status: **Approved by the developer 2026-11-07**, including the four W2-A1 choices in section 5 (recommended options).
Week 2 restarted: **16–20 Nov 2026, review Sat 21 Nov.** Task detail: `CLAUDE_BUILD_PLAN.md` Part H, Week 2. Progress: `docs/delivery/progress.md`.

**Goal:** a clinician-approved ANC plan drives the rest of pregnancy care: appointments, owned tasks, reports, referrals, the birth plan and the mother's next-step view.

## 1. Entry criteria: not met; starting early by the developer's decision

| Criterion | Met? | Evidence / what is missing |
|---|---|---|
| Phase 0 gate accepted | **No** | All Phase 0 tasks are built and Ready for review, except W1-B3 (In progress: CI at one SHA and the AT05 staging run are pending). Push access expected 2026-11-08; staging not deployed; review Sat 14 Nov. |
| D04 decided | **No** | Proposal ready: `docs/decisions/D04-auth-runtime.md` (tech lead). |
| D07 (patient access) proposed | **No** | Written in W2-A2, first thing this phase. |
| D05 ANC template at least drafted | **No** | Doctor packet W2-B5 goes out first; build uses a labelled placeholder template held as data. |

**Decision (2026-11-07):** the developer chose to start Phase 1 before the Phase 0 gate so the project finishes on time. `PHASE_PLAN.md` allows that only for work that does not depend on the failed or pending part. Every Phase 1 task depends on the Phase 0 foundation code, which is built and passing locally, not on the pending CI/staging/review steps. The weekly report must state this deviation. If the Phase 0 review finds a defect, fixing it comes before further Phase 1 work.

## 2. Decisions and what each blocks

| ID | Owner | State | Blocks | How we proceed |
|---|---|---|---|---|
| D04 auth/runtime | Tech lead | Proposed | Role capabilities (clinician-only actions) used from W2-A3 | Build the capability check with **DOCTOR = clinician** as a single, easily changed map; tech lead and doctor (M008 Q10) confirm. |
| D05 ANC template, urgent wording | Doctor | Not drafted | Real schedule and wording (W2-A3, W2-B3) | Placeholder template stored as data, labelled **"SYNTHETIC PLACEHOLDER – NOT CLINICALLY APPROVED"** in every screen and API response. Its items are generic contacts relative to the publish date, never gestational weeks or clinical content. Swapped for the approved template without code changes. |
| D07 patient/caregiver access | Manager + tech lead | Not proposed | Patient-facing access (W2-B3 caregiver screens, AT28) | W2-A2 writes the options; only the `caregiver_grant` model and server-side scope check are built, **behind a feature flag that is off**. |
| D06 WhatsApp provider | Manager | Proposed (Meta direct) | Nothing in Phase 1 | Business verification should already be under way. |
| T009 file limits and access mechanism | Tech lead | Not decided | W2-A1 storage | Proposed in W2-A1 (section 5). |
| G05 local schedules, G06 role limits, G10 identity and episodes, G14 privacy | Doctor / team lead / tech lead | Gap decisions | Scope limits | Built as the plan says: locally approved versioned templates, role limits server-side, shared-phone separation, private files. |

Scope exclusions (G01, G03) hold throughout: no risk scores, no vital-sign thresholds or alerts, no hospital matching, no dispatch or ETA.

## 3. Task order (one developer, both lanes)

Ordered so that work needing other people's answers goes out first.

| # | Task | Lane | h | Why here |
|---|---|---|---|---|
| 1 | W2-B5 Doctor packet: ANC template structure and urgent-help text slots | B | 1 | The doctor needs the most time (D05). |
| 2 | W2-A2 D07 options document + `caregiver_grant` model and scope check (flag off) | A | 4 | Manager/tech lead decision lead time. |
| 3 | W2-A1 Plan/task/appointment/investigation state model, `version` columns, private file storage | A | 4 | Foundation for everything below. |
| 4 | W2-A3 API: dating, ANC plan publish, appointments, owned tasks | A | 5 | AT06, AT07. |
| 5 | W2-B1 Screens: dating card, plan publish, calendar, task list, Today worklist v1 | B | 4 | Uses W2-A3. |
| 6 | W2-A4 API: reports, prescriptions, observations, referrals, verified contacts | A | 6 | AT08, AT09. |
| 7 | W2-B2 Screens: report upload (Pending review), prescriptions, referrals, contacts | B | 4 | Uses W2-A4. |
| 8 | W2-A5 API: next action, birth plan, help requests | A | 2 | |
| 9 | W2-B3 My next step, printable birth plan, public Urgent help, caregiver screens (flag) | B | 6 | AT10, AT28 (AT28 needs D07). |
| 10 | W2-B4 Synthetic scenarios + `test-scripts/SG2.md` | B | 5 | Last, against the finished slice. |

Planned: Dev A 21 h, Dev B 20 h. At the Phase 0 pace (about 45% of planned hours), roughly 20 hours of work.

## 4. Saturday demo outline (21 Nov, synthetic data only)

1. Publish the placeholder ANC plan for a late-presenting mother with an unknown LMP; the placeholder label is visible.
2. A clinician (DOCTOR) corrects the date: only future, not-yet-attended items move; past items and the change are kept and audited.
3. Upload a report: it shows **Pending review**; a non-clinician cannot mark it reviewed (button absent, and a forced API call is refused).
4. Track a referral through to return advice; a sent message alone cannot close it.
5. Open **Urgent help** signed out, with location denied: verified numbers as `tel:` links, support hours, no "wait for a reply".

**Exit criteria (from `PHASE_PLAN.md`):** AT06–AT10 and AT28 pass; P02, P04, P05, P08, P09, P10 pass; an uploaded report is never shown as reviewed; a date correction moves only future tasks; Urgent help works signed out with location denied. AT28 and the real template depend on D07 and D05; without them the gate is reported **Blocked: D07 / D05**, never passed on placeholders.

## 5. W2-A1 decisions needed before building it

W2-A1 adds six tables and the file-storage path. Four choices need the developer's approval (database roles, a runtime dependency, file limits):

1. **Grants for new tables.** Recommended: a small migration helper `grant_app_role(table, read_only=False)` called explicitly in every new migration, plus a test that the app role has exactly the expected rights on every table (catches a forgotten grant and any future `alembic_version`-style slip). Alternative: `ALTER DEFAULT PRIVILEGES`, which is implicit and depends on which role runs the migration (different on Supabase).
2. **File storage.** Recommended: a `FileStore` interface with a **local-disk** implementation now (development and tests), and a **Supabase Storage** implementation using its HTTP API through `httpx`. `httpx` is already locked (as a test dependency); making it a runtime dependency counts as a new dependency. Files are never publicly reachable: downloads go only through an authorised API endpoint that streams the file.
3. **File limits (T009).** Recommended: PDF, JPEG and PNG only; 10 MB maximum; type checked from the file's content, not its name; stored under a random key, with the original filename kept only as metadata; SHA-256 checksum recorded.
4. **Clinician role.** Recommended: `DOCTOR` only for clinician-only actions (confirm dating, publish plan, mark report reviewed), in one map that the tech lead and doctor can change.

## 6. Risks

- **Doctor time.** D05 and M015 drive the real schedule and wording. Mitigation: placeholder held as data; packet goes out first.
- **D07 undecided.** AT28 cannot pass without it. Mitigation: model and scope check behind a flag; the gate reports Blocked: D07 rather than passing.
- **Phase 0 defects found late.** Mitigation: fix first, before more Phase 1 work.
- **Scope creep into clinical logic.** Every PR keeps the clinical-boundary checklist; a grep for threshold comparisons runs in W2-A4.
