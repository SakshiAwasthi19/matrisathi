# MatriSathi: intake and roles review (M008)

**For:** the reviewing doctor. **Prepared:** 7 Nov 2026. **Time needed:** about 30 minutes.
**What we need back:** your answers to the questions in section 5 (yes / no, with a note where you want one).

MatriSathi is an assistive tool for staff. It records what is known, keeps unknown things as unknown, and never interprets, scores or advises. Everything shown here uses invented (synthetic) data; no real patient has been entered.

---

## 1. What staff record when registering a mother

Staff first search for an existing record by phone number or name. If she is already registered, they open her record. If not, they register her with the fields below.

| Field | How it is entered | Required? | Can be "unknown"? | Example (invented) |
|---|---|---|---|---|
| Facility | Chosen from the facilities the staff member works at | Yes | No | Synthetic Rural Facility |
| Full name | Free text | Yes | No | Sunita Devi (invented) |
| Contact phone | Number | Yes | No | +91 00000 00002 (invented) |
| Age / date of birth | One of four choices: exact date of birth; year of birth only; approximate age in years; unknown | Yes (one choice) | Yes: "Unknown" is a choice | "Approximate age: 24" |
| Reported medical history | Free text, "as told by the family" | No | Yes (left blank) | "Family reports one earlier pregnancy" |
| Known allergies / current medicines | Free text | No | Yes (left blank) | "None known" |

**Rules the system follows:**
- **Unknown age stays unknown.** If only the year is known, the system does not invent a day or month. An unknown age is never treated as zero or "normal".
- **History and allergies are stored exactly as told.** They are never read, scored or used to flag anything.
- **A phone number is not an identity.** Two women can share one phone (a household handset). Their records stay separate and are never merged because of the number. Having the number gives no access to anyone's record.
- **Contact verification.** Staff can mark that they confirmed which woman a phone number belongs to. The system records who confirmed it and when.

### Pregnancy episode

After registration, staff open a pregnancy episode for her. Today it records:

| Field | Required? | Can be "unknown"? | Notes |
|---|---|---|---|
| Expected date estimate | No | Yes | **Not yet on the screen.** Every episode is currently saved as "unknown". |
| Where the date came from | — | Yes | One of: self-reported, confirmed by a clinician, unknown. Currently always "unknown". |
| Status | — | — | Active or closed. There is no way to close an episode yet. |

Dating (provisional and confirmed dates, who confirmed them) is built in the next phase. Confirming a date will be a clinician-only action, recorded with name and time.

### Not recorded at all today

- **Preferred language.** The system can store it but the screen does not ask for it.
- **Where each piece of information came from** (the woman herself, a family member, a card or document). The specification lists this; it is not captured yet.
- **Identity numbers** (Aadhaar, ABHA), email and smartphone: deliberately **not** required.

---

## 2. Staff roles

The specification says (F004):
- An administrator manages staff accounts but **cannot see clinical records** just for being an administrator.
- Staff see only the facilities and records they are permitted by role and assignment.
- **Clinician-only actions** (for example approving a care plan or marking a report as reviewed) are reserved for clinical users. An ASHA cannot approve a plan or mark a report reviewed.
- Removing a staff member's access takes effect on their very next action.

**What the system does today:**
- Roles available: **ASHA, Nurse, Coordinator, Doctor.** There is no separate ANM role; ANMs would currently be recorded as "Nurse".
- **All four roles can currently do the same things** inside their own facility: search, register a mother, open an episode, view the record. No clinician-only actions exist yet, because the features that need them (plan approval, report review, date confirmation) start in the next phase.
- Facility limits **are** enforced: staff cannot see or create records in a facility they are not a member of, and denied attempts are logged.
- Administrator rights are separate and give no record access (tested).

---

## 3. Which care stages are covered

| Stage | Covered now? |
|---|---|
| 1. Registration | Yes (this packet) |
| 2. Pregnancy care (ANC plan, appointments, reports, referrals) | Next phase |
| 3. Birth preparation | Next phase |
| 4–6. Birth, discharge, postpartum | Later |
| 7–8. Infancy and early childhood | Later |

### Deliberately excluded (agreed scope limits)

The system will **not** do any of these, at any stage:

| Excluded | Reference |
|---|---|
| Risk scores, vital-sign thresholds or alerts, trend interpretation | G01 |
| Discharge-readiness checks (for example a diaper count unlocking discharge) | G02 |
| Ambulance dispatch, GPS tracking, arrival times, geofencing | G03 |
| Depression screening scores (EPDS), growth-faltering or dehydration detection | G07 |
| Official vaccine certificates; automatic government-system sync | G08 |
| Computer-generated medical answers | G01 |

Instead, values are stored as reported (with date, unit, source and who recorded them), and clinical decisions are recorded only by clinicians.

---

## 4. What happens with your answers

Your answers decide which intake fields are kept, added or made required before the next phase builds on them, and how the roles are limited. Nothing clinical is changed without your written approval.

---

## 5. Questions

Please answer yes or no; add a note where useful.

**Intake fields**
1. Are the six registration fields in section 1 enough to start registration in the pilot? ☐ Yes ☐ No: missing ____________
2. Is free-text "reported medical history" acceptable for now, rather than a fixed list? ☐ Yes ☐ No
3. Is free-text "known allergies / current medicines" acceptable for now? ☐ Yes ☐ No
4. Should any optional field become required? ☐ No ☐ Yes: ____________
5. Are the four age choices (exact date, year only, approximate age, unknown) right? ☐ Yes ☐ No
6. Should the screen ask for **preferred language** at registration? ☐ Yes ☐ No
7. Should the screen record **where each piece of information came from** (the woman, a family member, a card)? ☐ Yes ☐ No
8. Should staff be able to enter a **provisional expected date** at registration, marked "self-reported", before a clinician confirms it in the next phase? ☐ Yes ☐ No

**Roles**
9. Should **ANM** be its own role, separate from Nurse? ☐ Yes ☐ No
10. In the next phase, should only the **Doctor** role confirm dates, approve care plans and mark reports reviewed? ☐ Yes ☐ No: also allow ____________
11. Should an **ASHA** be able to register a mother and open an episode? ☐ Yes ☐ No
12. Should an **ASHA** see the reported medical history and allergies? ☐ Yes ☐ No

**Coverage and reviewers**
13. Is the list of excluded features in section 3 acceptable? ☐ Yes ☐ No: concern ____________
14. Who will review the child-care stages (pediatric reviewer)? Name: ____________
15. Is there anything a registering staff member must **never** be asked to record? ☐ No ☐ Yes: ____________

Signature / name: ____________ Date: ____________
