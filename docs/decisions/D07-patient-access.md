# D07: How mothers and caregivers get access

**Status:** Proposed. **Decides:** manager with the tech lead. **Written:** 2026-11-07 (W2-A2).
**Spec:** M010, T010, F015, G10, G14. **Blocks:** any patient-facing sign-in, the caregiver screens (W2-B3) and AT28.

## The question

How does a mother (or an adult she trusts) prove who she is to see her own "My next step" page and birth plan, on phones that are often shared by a whole family, and how does she give and take back access for a caregiver?

## Fixed rules (from the specification; every option must keep them)

- **Owning or using a phone number is never enough** to see someone's record (F015, T010). Two women on one handset stay separate.
- Access is checked on **every request and every download**. A revoked or expired grant fails on the very next request.
- Unclear identity stays restricted. A changed phone number never moves access to someone else.
- Shared devices: no long-lived sign-in, no record content in notifications.
- Private concerns are never shown to a caregiver automatically.
- People without a phone can be helped in person by staff.

## What is built now (behind a switch that is off)

- A `caregiver_grant` record: whose record (the mother), who receives access (the caregiver, as a separate person record), which actions, who recorded the consent, who verified identity and how, expiry, and revocation (when, by whom, why). Grants are never deleted; revoking keeps the history.
- One server-side check, `caregiver_access_allowed(...)`, that every future patient/caregiver endpoint must call. It answers "no" unless a grant exists, covers the action, has not expired and has not been revoked, and the subject and caregiver are different people.
- The setting `PATIENT_ACCESS_ENABLED` defaults to **off**. With it off, the check always answers "no", so nothing patient-facing can work by accident.

No sign-in method is built until this decision is made.

## Options for how a mother proves who she is

### Option 1: Staff verify in person, then give a one-time code (recommended)

1. The mother (or caregiver) is at the facility or with an ASHA. Staff check identity in person, using what the facility already accepts (for example the MCP card, a known family, a photo ID), and record **who verified, how, and when**.
2. The app shows a **one-time code** (printed or written down) that works once, within 24 hours.
3. On first use she chooses a short **PIN**. After that she signs in with her code-linked account and PIN; the session ends after 15 minutes idle and is never remembered on the device by default.
4. Lost code or forgotten PIN: staff verify her again in person; the old code and sessions are cancelled.

- **Strengths:** no phone needed to verify; works on shared phones; nothing depends on SMS or WhatsApp; clear audit of who verified.
- **Risks:** needs a staff visit to start or recover; a PIN can be seen by others on a shared phone (mitigated by short sessions and no saved sign-in).
- **Cost:** none beyond staff time.

### Option 2: Staff verify in person, plus a code sent by SMS or WhatsApp at each sign-in

As option 1, but each sign-in also needs a code sent to her phone.

- **Strengths:** a second factor.
- **Risks:** on a **shared phone** the code reaches whoever holds the phone, so it adds little; it depends on the messaging provider (D06) and costs per message; fails without signal.
- **Cost:** per-message charges (see D06), provider setup.

### Option 3: No mother sign-in for the pilot

Mothers get their next step through WhatsApp messages (Phase 2), printed plans and phone calls. The "My next step" page is used **by staff with the mother**, on staff devices. Caregiver grants still exist, but only control what staff may tell or send to whom.

- **Strengths:** simplest and safest for a short pilot; no patient accounts to recover or protect.
- **Risks:** the mother cannot look things up herself on the web; AT28 then tests grants and revocation through staff and messaging, not a patient sign-in (the manager must accept that reading of AT28).
- **Cost:** none.

## Caregiver grants (the same under every option)

| Field | Proposal |
|---|---|
| Who can grant | The mother herself, in front of staff, who record her consent |
| Who can receive | An adult, registered as their own person record (never "whoever has the phone") |
| What can be granted | Any of: see the next step; see the birth plan; receive reminders on her behalf |
| How long | Until a set date (proposed default 90 days), renewable |
| Revocation | The mother, through staff, at any time; takes effect on the next request |
| Never included | Private concerns, reported history, allergies, reports, unless a later decision adds them |

## Recommendation

**Option 1 for the pilot**, with Option 3 as the fallback if the team cannot support in-person code issuing and recovery. Option 2 is not recommended: on a shared phone it adds cost without adding much protection.

## Questions for the manager and tech lead

1. Which option? ☐ 1 ☐ 2 ☐ 3
2. What may staff accept as in-person identity evidence? ____________
3. Default caregiver grant length (proposed 90 days)? ____________
4. May a caregiver ever see reported history, allergies or reports? ☐ No ☐ Yes, if the mother chooses
5. Who may revoke on the mother's behalf if she cannot come in (for example, a reported safety concern)? ____________
6. If option 3: do you accept AT28 being tested through staff and messaging rather than a patient sign-in? ☐ Yes ☐ No
