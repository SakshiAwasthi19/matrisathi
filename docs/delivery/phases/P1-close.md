# Phase 1 close: Pregnancy care (SG2)

**Written:** 2026-11-07 at SHA `7df67ff` (`w2/w2-b4-sg2-scenarios-and-scripts`), for the Saturday review.
**Status proposed:** **Ready for review: not passed.** Every Phase 1 task is built, merged to `main` (PRs #15–#26) and **green in CI at `1895994`** ([run 42380238581](https://github.com/matrisathi/jananisaathi/actions/runs/42380238581)). Nothing has been run on staging, and two decisions block parts of the gate. Only the manager can accept tasks or the gate.

**Context:** Phase 1 was started early, before the Phase 0 gate (developer's decision, 7 Nov; see `P1-plan.md` section 1). The Phase 0 gate is still open for the same reasons listed below (no CI, no staging, reviews pending).

---

## 1. Exit criteria with actual evidence

"Local" = ran and passed on the developer machine at `7df67ff` (Python 3.12.13, Node 24, PostgreSQL 16.4). CI and staging columns are empty because neither has run.

| Exit criterion (`PHASE_PLAN.md`) | Local | CI | Staging | State |
|---|---|---|---|---|
| AT06 late/unknown dating and schedules | Pass: `test_sg2_acceptance.py::test_AT06_…` + `test_care_api.py` | **Pass** at `1895994` | not run | **Not passed** (needs the staging script run) |
| AT07 appointments and overdue work | Pass: `test_AT07_…` + `test_care_api.py` | **Pass** at `1895994` | not run | **Not passed** |
| AT08 reports and medicine records | Pass: `test_AT08_…` + `test_records_api.py`, `test_files_api.py` | **Pass** at `1895994` | not run | **Not passed** |
| AT09 referral closure | Pass: `test_AT09_…` + `test_records_api.py` | **Pass** at `1895994` | not run | **Not passed** |
| AT10 birth plan and urgent help | Pass: `test_AT10_…` + `test_next_step_api.py`, `test_public_urgent_help.py` | **Pass** at `1895994` | not run | **Not passed** |
| AT28 patient/caregiver access | Model level only: `test_AT28_…`, `test_caregiver_access.py` | not run | — | **Blocked: D07** |
| P02, P05, P08, P09, P10 | Covered by the tests above (mapping in `test-scripts/SG2.md`) | **Pass** at `1895994` | not run | **Not passed** |
| P04 caregiver revocation | Model level only | — | — | **Blocked: D07** |
| An uploaded report is never shown as reviewed | `test_uploaded_outside_report_is_received_not_reviewed`, `test_AT08_…`; DB constraint `ck_investigation_review_attributed` | **Pass** at `1895994` | not run | Evidenced locally |
| A date correction moves only future items | `test_correction_keeps_history_and_past_intact`, `test_AT06_…` | **Pass** at `1895994` | not run | Evidenced locally (week-timed items are cancelled and re-booking is a review task, because no week rule is approved: D05) |
| Urgent help works signed out with location denied | `test_signed_out_user_gets_verified_service_numbers_only`, `test_AT10_…`; page never requests location | **Pass** at `1895994` | not run | API evidenced; **browser check (signed out, location blocked, Slow 3G) not run** |

**Suite totals at `7df67ff`:** pytest **342 passed**, ruff clean, mypy clean (53 files); vitest **46 passed**, typecheck clean, build OK (main JS 136.84 kB gzipped, limit 250 kB).

## 2. Tasks

All ten are **Ready for review**; none is **Accepted**.

| Task | Lane | Planned h | Actual h (est.) | Branch / commit |
|---|---|---|---|---|
| W2-A1 Plan/task model, private files | A | 4 | 3 | `w2/w2-a1-plan-task-files` `d20cd5c` |
| W2-A2 D07 options, caregiver grant | A | 4 | 2.5 | `w2/w2-a2-patient-access` `aa26bec` |
| W2-A3 Dating, plan, appointments, tasks API | A | 5 | 3.5 | `w2/w2-a3-dating-plan-appointments-tasks` `9b12cce` |
| W2-A4 Reports, prescriptions, observations, referrals, contacts API | A | 6 | 3.5 | `w2/w2-a4-reports-prescriptions-referrals` `d81df42` |
| W2-A5 Next action, birth plan API | A | 2 | 2 | `w2/w2-a5-next-action-birth-plan` `e71a9ee` |
| W2-B1 Dating, plan, calendar, tasks, Today screens | B | 4 | 3 | `w2/w2-b1-dating-plan-calendar-today` `a0869f7` |
| W2-B2 Reports, prescriptions, referrals, contacts screens | B | 4 | 3 | `w2/w2-b2-reports-prescriptions-referrals-ui` `97c4235` |
| W2-B3 Next step, birth plan print, public Urgent help | B | 6 | 3.5 | `w2/w2-b3-next-step-birth-plan-urgent-help` `0fa0ab5` |
| W2-B4 Synthetic scenarios, manual scripts | B | 5 | 2 | `w2/w2-b4-sg2-scenarios-and-scripts` `7df67ff` |
| W2-B5 Doctor packet (D05) | B | 1 | 0.5 | `w2/w2-b5-d05-doctor-packet` `74ad3d9` |

**Dev A % accepted (proposed):** 0% accepted (0 of 21 planned hours). 100% of planned hours are Ready for review.
**Dev B % accepted (proposed):** 0% accepted (0 of 20 planned hours). 100% Ready for review.
Actual effort is an estimate of the work, about 14.5 h (A) and 12 h (B), not measured clock time.

## 3. Defects and findings in this phase

| Finding | Found | State |
|---|---|---|
| Earlier claim that no default grants existed was wrong (`79d282bcc5f3` sets `ALTER DEFAULT PRIVILEGES`) | W2-A2, by the new rights test | **Fixed**: default removed (`b9d0e2a7c3f1`); errata in the SG1 report, D04 and the plans |
| Task rule blocked cancelling an unowned task when a plan is replaced | W2-A3, by the republish test | **Fixed** in `e6f1b3c8d205` |
| Audit helper parameter clash recorded a task outcome in the wrong field | W2-A3, by test | **Fixed** before commit |
| Docstring tripped the "no thresholds" scan | W2-A4 | **Fixed**: scan now reads code tokens only, with a test that it fires on real code |
| CORS lacked PUT (D04 F7) | W2-A5 | **Fixed** for PUT |
| D04 F2 (per-username throttling), F3 (optional Idempotency-Key), F4–F6 (minor) | W1-A3 | Open: tech lead questions |

No open defect is known in the Phase 1 code. The browser checks below may find some.

## 4. What is still needed to pass the gate

1. ~~Open the pull requests so CI runs~~ **Done 2026-11-07:** PRs #1–#27 merged in order, each green; CI green on `main` at `1895994`; SHAs and runs in `progress.md`.
2. **Deploy staging** (`docs/delivery/staging.md`, now including the private storage bucket and the placeholder-template seed) and run `docs/delivery/test-scripts/SG2.md` there, filling the Actual column.
3. **Browser checks:** every Phase 1 screen at 360 px and 1280 px; Urgent help signed out, location blocked, Slow 3G.
4. **D07** (manager + tech lead): unblocks patient sign-in, caregiver screens, AT28 and P04.
5. **D05** (doctor): the real ANC template, observation list, urgent-help wording, and the pregnancy-week rule. The placeholder must be replaced before any real use.
6. **Support hours** for the urgent-help page (facility).

## 5. Carry-over

| Item | Why | To |
|---|---|---|
| Caregiver screens; patient sign-in | Wait for D07 | When D07 is decided |
| Week-timed scheduling | Waits for the doctor's rule (D05 Q2) | After D05 |
| Observation allowed list and units | Waits for D05 section 3 | After D05 |
| Audio on My next step | Approved recordings come with messaging (Phase 2, D08) | Phase 2 |
| Name search fuzziness; phone normalisation | Known limitations from SG1 | Later, if pilot users need it |

## 6. Phase 2 entry criteria

| Criterion | Met? |
|---|---|
| Phase 1 gate accepted | No (this document) |
| D06 provider decided | No: proposal recommends Meta Cloud API direct |
| Message templates submitted or approved | No |
| Consenting staff test numbers available | No |
