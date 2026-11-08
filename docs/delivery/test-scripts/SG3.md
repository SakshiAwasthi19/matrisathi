# SG3 manual test scripts: real WhatsApp and voice

**For:** whoever runs the Week 3 demo (manager or developer).
**Gate rule:** these must run against the **real provider** (Meta WhatsApp Cloud API test number, per D06's recommendation) on **consenting staff handsets only**. A mock connector does not pass SG3. Until D06 is decided and the templates are approved, record the gate as **Blocked: D06** — do not record a pass.
**Data:** synthetic mothers only. The phones are staff phones whose owners agreed in writing to receive test messages; register them under invented names.
**How to record:** fill "Actual" with what you saw, the date and the commit SHA. Never copy the expected result.

## Evidence rules (read before taking any screenshot)

- No real phone number may appear in a screenshot, log extract or report. Crop or blur the "From" line and the phone's status bar.
- No message text from a real person. Staff testers send only the scripted texts below.
- Screenshots of the app show synthetic names only.
- Never paste the access token, app secret or verify token anywhere (chat, report, screenshot).

---

## 0. Setup (once, by the developer, on staging)

1. Meta: business app created, WhatsApp test number added, the staff handsets added as allowed test recipients, and the four placeholder templates from `app/scripts/setup_messaging_sandbox.py` created with the **same names and text** (until the doctor's M023 templates are approved).
2. Staging environment (names only; values in the host's settings): `MESSAGING_PROVIDER=meta`, `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_APP_SECRET`, `WHATSAPP_VERIFY_TOKEN`, `MESSAGING_ALLOW_PLACEHOLDER_TEMPLATES=true` (staff test phones only).
3. Webhook registered in Meta's dashboard: `https://<staging-api>/api/v1/webhooks/whatsapp`, verify token as above, subscribed to `messages`.
4. Channel and placeholder templates: `uv run python -m app.scripts.setup_messaging_sandbox --organization "<org>" --phone-number-id <test number ID>` (migrator credentials, release step).
5. Worker running as its own process: `uv run python -m app.scripts.messaging_worker`.
6. As `coordinator1`, register "Synthetic Tester A" with staff handset A's number, and "Synthetic Tester B" **and** "Synthetic Tester C" both with handset B's number (shared phone). Open a pregnancy record for each.

---

## AT11: an approved template reaches a staff phone

| # | Step | Expected | Actual |
|---|---|---|---|
| 1 | Tester A → Messages tab → Contact preferences: record consent (after asking the tester), language English, detail **Minimal**. Save. | "Consent recorded by Synthetic Coordinator" with the time. | |
| 2 | Appointments → add a confirmed appointment for tomorrow → **Send reminder**. | Toast "Reminder queued". Message history shows **Queued** and the exact text, labelled "SYNTHETIC PLACEHOLDER – NOT APPROVED". | |
| 3 | Wait for the worker (≤ 10 s). | Handset A receives the template. History shows **Sent to WhatsApp**, then **Delivered**, then **Read** once opened (read only if Meta reports it). | |
| 4 | Set Tester A's safe hours to a window that excludes now, send another reminder. | History shows **Waiting for her safe hours**; nothing arrives until the window opens. | |
| 5 | Change detail level to **Standard** and send again. | The standard template arrives (mentions the visit place and time). | |

## AT12: one event makes one item; nothing is sent twice

| # | Step | Expected | Actual |
|---|---|---|---|
| 1 | From handset A send the text "SG3 test one". | One item in the Inbox within seconds. | |
| 2 | In Meta's dashboard, use **Resend** on that webhook delivery (or wait for Meta's own retry). | Still exactly one item. | |
| 3 | Stop the worker, queue a reminder, start **two** workers. | The reminder arrives **once**. | |
| 4 | Queue a reminder, then cut the API's network to Meta for one attempt (or use a wrong access token for one run). | History shows **Retrying**, then **Sent to WhatsApp** when restored; or **Failed** with a "Call instead" task after 5 attempts. Never "Delivered" without Meta's report. | |

## AT13: voice and photo land in a staffed inbox; a shared phone never auto-links

| # | Step | Expected | Actual |
|---|---|---|---|
| 1 | From handset B send a 5-second voice note saying "SG3 test voice". | Inbox → **Unlinked**: one voice item, "2 people are registered on this number", no name shown. The audio plays in the app. | |
| 2 | Sign in as `nurse1`. | The unlinked item is **not** visible to the nurse. | |
| 3 | As coordinator: **Link to a person** → choose Synthetic Tester C → identity check "Called her back". | Item shows "Synthetic Tester C", "Linked by Synthetic Coordinator", the check used. The nurse can now see it. | |
| 4 | From handset B send a photo of a blank sheet of paper. | Photo item appears; the image opens only inside the app. | |
| 5 | Send a short video. | Item says "only text, voice notes and photos are accepted"; nothing stored. | |
| 6 | Reply to the linked item with free text "SG3 reply". | Handset B receives it; the reply shows its status under the item. | |
| 7 | Assign owner = nurse, backup = doctor; close with outcome "Responded". | Item moves to Closed with who and when. | |

## AT14: opt-out and phone fallback

| # | Step | Expected | Actual |
|---|---|---|---|
| 1 | Queue a reminder for Tester B, then (before the worker sends it) from handset B send **STOP**. | Reminder shows **Not sent: she opted out**. Tester B **and** Tester C show "Opted out — she sent STOP". Nothing arrives. | |
| 2 | Try **Send reminder** again for Tester C. | Refused: "She has opted out of messages. Call her instead." | |
| 3 | On the failed/blocked message, press **Call instead**. | A call task appears on Today for the sender. | |
| 4 | Staff re-record consent for Tester B only after asking her, and clear opt-out. | Messages to Tester B resume; Tester C stays opted out. | |

## Security checks

| # | Step | Expected | Actual |
|---|---|---|---|
| 1 | `curl -X POST <staging-api>/api/v1/webhooks/whatsapp -d '{}'` (no signature). | 401, nothing recorded. | |
| 2 | Same with a wrong `X-Hub-Signature-256`. | 401. | |
| 3 | Open `<staging-api>/api/v1/inbox/<id>/media` signed out, and as a user from another facility. | 401 / 404. | |

Automated equivalents: `apps/api/tests/test_messaging_outbox.py`, `apps/api/tests/test_messaging_inbox.py`.
