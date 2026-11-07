# SG2 manual test scripts: pregnancy care

**For:** whoever runs the Phase 1 demo (manager or developer), on staging or a local copy.
**Data:** synthetic only. Invent every name; use phone numbers in the reserved `+91 00000` range. Never show a real person's details on screen or in screenshots.
**How to record:** fill the "Actual" column with what you saw, the date, and the commit SHA shown in the PR. Never copy the expected result into "Actual".

---

## 0. Setup (once)

1. Staging deployed per `docs/delivery/staging.md` (or the local app running).
2. Seed run: `coordinator1` and `doctor1` exist (seed password from your password manager), and the **placeholder** care-plan template exists.
3. Signed in as `coordinator1`, open **Local contacts** and add two synthetic contacts:
   - Primary health centre, "Synthetic PHC", `+910000020001`, landmark "Behind the synthetic market".
   - Referral hospital, "Synthetic district hospital", `+910000020002`.
4. On **Find or register a mother**, register:
   - "Synthetic Late Presenter", phone `+910000020010`, age Approximate 26.
   - "Synthetic Unknown-Date Mother", phone `+910000020011`, age Unknown.

Use two browser windows: one signed in as `coordinator1`, one as `doctor1` (private window).

---

## AT06: late / unknown dating and schedules

| # | Step | Expected | Actual |
|---|---|---|---|
| 1 | Open "Synthetic Unknown-Date Mother" → Pregnancy dating card. | **Unknown**, "Nothing is assumed or calculated." No dates anywhere. | |
| 2 | As coordinator: Care plan panel. | "A clinician publishes the care plan." No publish button. | |
| 3 | As doctor: Care plan → choose the placeholder → Publish. | Amber "Synthetic placeholder: not clinically approved". Appointments appear as **Requested** from today; nothing backdated. | |
| 4 | Open "Synthetic Late Presenter" (coordinator) → Record a provisional date: expected date about one month ahead, Approximate, "Told by the mother or family". | Card shows **Provisional**. No Confirm button for the coordinator. | |
| 5 | Doctor: same card → Confirm this dating. | **Confirmed by Synthetic Doctor**. | |
| 6 | Coordinator: try Record a provisional date again. | Refused: "Only a clinician can correct it." | |
| 7 | Doctor: publish the placeholder plan; coordinator confirms the first appointment for now and marks it **Attended**. | First appointment shows Attended. | |
| 8 | Doctor: Correct the dating (a different date, Scan report). | History shows 2 entries, one "Replaced". The attended appointment is still **Attended**. | |

## AT07: appointments and overdue work

| # | Step | Expected | Actual |
|---|---|---|---|
| 1 | Unknown-Date Mother → Appointments: Confirm date on the first requested visit (date, time, "Synthetic sub-centre"). | Confirmed, with place. | |
| 2 | Mark it **Missed**. | Status Missed (indigo, not red). One new task "Follow up a missed visit", assigned to a named person. | |
| 3 | Missed visit → Reschedule to a date next week. | A new Requested appointment "Rescheduled from an earlier appointment". | |
| 4 | Try to reschedule the missed one again. | Refused (only the newest is current). | |
| 5 | Cancel another requested visit. | Cancelled. | |
| 6 | **Today** page → My tasks. | The follow-up task is listed; "Overdue" appears only if past due and is worded as administrative. | |
| 7 | Open My next step for her. | "No confirmed next step yet": nothing inferred about her. | |

## AT08: reports and medicine records

| # | Step | Expected | Actual |
|---|---|---|---|
| 1 | Tests and reports → Add an outside report: name "Synthetic outside report", choose a synthetic PDF. | Listed with amber **Pending review**; requested/performed dates not shown (unknown). | |
| 2 | Try uploading a `.txt` or a file over 10 MB. | Refused before upload with a plain message. | |
| 3 | As coordinator: look for Mark reviewed. | No button. | |
| 4 | As doctor: Mark reviewed. | Green "Reviewed"; "Reviewed by Synthetic Doctor on …". | |
| 5 | Open the original. | The PDF opens (only when signed in at this facility). | |
| 6 | Prescriptions → Record a prescription, Paper prescription, attach the PDF. | "Waiting for clinician review"; "No reminder until a clinician confirms the instruction." | |
| 7 | Doctor: Review → "Instruction is unclear". | "Unclear: review open"; still no reminder; a review task is with the doctor. | |
| 8 | Doctor: Review → "Instruction is clear", copy a synthetic instruction, set a reminder. | Instruction shown as written; "Reminder on from …". | |
| 9 | Observations → add "Placeholder measurement", value `120/80`, unit `mmHg`. | Shown exactly as `120/80 mmHg`; no colour, flag or "normal/high". | |

## AT09: referral closure

| # | Step | Expected | Actual |
|---|---|---|---|
| 1 | As coordinator: Referrals panel. | No "Refer" button. | |
| 2 | As doctor: Refer → Synthetic district hospital, urgency Soon. | Referral "Sent", owner named; note "Sending a message never closes a referral." | |
| 3 | Look at the step buttons. | Only "Mark service contacted" / "Mark attended" and "Close with a reason". No jump to completion. | |
| 4 | Step through contacted → attended (no date) → advice received → follow-up completed. | Timeline ticks each step with its time; advice creates one follow-up task for the owner. | |
| 5 | Create a second referral; Close with a reason → "Family declined". | "Closed: Family declined". | |

## AT10: birth plan and urgent help

| # | Step | Expected | Actual |
|---|---|---|---|
| 1 | Birth plan → Start a birth plan: birth place Synthetic PHC, companion, transport note, landmarks, primary Synthetic PHC, alternate hospital. | Each number shows "verified <date>". "Not yet gone through with the family". | |
| 2 | As coordinator: try to set the referral site. | Field disabled; "Only a clinician can choose the referral site." | |
| 3 | Doctor sets the referral site; coordinator presses "I went through this plan with the family". | Referral site "Chosen by Synthetic Doctor"; green verified badge. | |
| 4 | Edit any field and save. | Verified badge disappears (a changed plan is never shown as verified). | |
| 5 | Print birth plan. | Plain page: details, blank lines where nothing is recorded, and the urgent-help link. | |
| 6 | Open the urgent-help link in a **private window, signed out**, with location blocked in the browser. Repeat with network throttled to "Slow 3G". | Page loads; big red "Call Synthetic PHC" buttons open the dialler; "Messages … are not watched for emergencies"; hours "Not yet confirmed"; amber notice that instructions await approval. No location prompt. | |

## AT28: patient / caregiver access

**Blocked: D07.** Patient sign-in and caregiver screens are not built until the manager chooses the access method (`docs/decisions/D07-patient-access.md`). The grant model and the access check exist and are tested (`test_AT28_model_level_revoked_caregiver_and_same_handset`, `tests/test_caregiver_access.py`), with patient access switched off. Do not report AT28 as passed.

---

## Cross-check: acceptance case → automated test → this script

All automated tests are in `apps/api/tests/`. "Scenario" = the named builder in `tests/factories.py`.

| Case | Automated test (scenario) | Other automated coverage | Manual script |
|---|---|---|---|
| AT06 | `test_sg2_acceptance.py::test_AT06_late_and_unknown_dating_and_schedules` (`scenario_unknown_lmp`, `scenario_late_presenter`) | `test_care_api.py` dating and plan tests | AT06 steps 1–8 |
| AT07 | `test_AT07_appointments_missed_visit_backup_owner` (`scenario_unknown_lmp`) | `test_care_api.py` appointment and task tests | AT07 steps 1–7 |
| AT08 | `test_AT08_outside_report_and_prescriptions` (`scenario_outside_report`) | `test_records_api.py`, `test_files_api.py` | AT08 steps 1–9 |
| AT09 | `test_AT09_referral_closes_only_by_state_or_reason` (`scenario_unknown_lmp`) | `test_records_api.py::test_referral_lifecycle_and_closure_rules` | AT09 steps 1–5 |
| AT10 | `test_AT10_birth_plan_and_signed_out_urgent_help` (`scenario_unknown_lmp`) | `test_next_step_api.py`, `test_public_urgent_help.py` | AT10 steps 1–6 |
| AT28 | `test_AT28_model_level_revoked_caregiver_and_same_handset` (`scenario_revoked_caregiver`, `scenario_shared_phone`) — **model level only** | `test_caregiver_access.py` | Blocked: D07 |

### Pilot checks in this phase

| Check | Meaning (from the gap decisions) | Covered by |
|---|---|---|
| P02 | Early, late and unknown-date cases; date corrections preserve history | AT06 |
| P04 | Caregiver revocation; another person on the same phone denied | AT28 (model level; Blocked: D07) |
| P05 | Urgent contacts work without location or login; fallback visible | AT10 step 6 |
| P08 | A report is received, not reviewed, until a clinician reviews it | AT08 steps 1–4 |
| P09 | A missed visit produces owned follow-up; reschedule keeps one current | AT07 steps 1–4 |
| P10 | A referral closes only by a defined state or a reason | AT09 |

### What counts as a pass

A case passes only when **both** the automated test passes in CI at the candidate SHA **and** the manual script was run on staging with every "Actual" filled in and matching. AT28 stays **Blocked: D07** whatever the model-level tests show.
