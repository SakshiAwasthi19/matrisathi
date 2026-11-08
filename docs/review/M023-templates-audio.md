# MatriSathi: WhatsApp message templates and audio (M023)

**For:** the reviewing doctor (and the manager for the provider submission). **Prepared:** 8 Nov 2026 (W3-B4).
**What we need back:** the wording below approved or rewritten, one row per language, and the audio scripts approved for recording (D08 narrator).

MatriSathi sends only messages you approve here, word for word. It never writes medical advice, never interprets anything a mother sends, and never decides who wrote a message from the phone number. Until you approve, the app uses the placeholders below, labelled "SYNTHETIC PLACEHOLDER – NOT APPROVED", and they go only to staff test phones.

## How the templates are used

- **Two detail levels.** Staff set each mother's level with her:
  - **Minimal**, for shared or family phones: says nothing about pregnancy, health or care. It only names the facility and asks her to come or reply.
  - **Standard**: may name the visit place and time.
- **Slots.** `{{1}}`, `{{2}}`, … are filled by the app with facility name, visit place, date or time — never with anything clinical.
- **When it sends.** Only inside her safe hours, only with her recorded consent, and never after she opts out (she can send STOP at any time). A reminder is dropped if the appointment changed after it was queued.
- **Provider rules.** WhatsApp requires each template to be approved by Meta as a "utility" message before it can be sent. The manager submits your approved wording.

## 1. Templates to approve

Rewrite freely. Keep the slots you want; remove the ones you don't.

| # | Purpose | Detail | Placeholder text (not approved) | Slots | Your approved wording | Language(s) |
|---|---|---|---|---|---|---|
| 1 | Appointment reminder | Minimal | Reminder from {{1}}: please come on {{2}}. Reply here if you cannot come. | 1 = facility name, 2 = date | | |
| 2 | Appointment reminder | Standard | Your visit at {{1}} is on {{2}} {{3}}. Reply here if you cannot come or need help. | 1 = place, 2 = date, 3 = time | | |
| 3 | Follow-up after no reply or a missed visit | Minimal | {{1}} tried to reach you. Please reply or call us. | 1 = facility name | | |
| 4 | Follow-up after no reply or a missed visit | Standard | {{1}} would like to talk to you about your next visit. Please reply or call us. | 1 = facility name | | |

## 2. Audio scripts (for the narrator, D08)

Each approved template also gets a recorded audio version with exactly the same meaning, so a mother who cannot read can listen. The app always shows the text next to the audio.

| # | Template | Script to record (your approved wording, in spoken form) | Language | Approved? |
|---|---|---|---|---|
| 1 | Appointment reminder, minimal | | | ☐ |
| 2 | Appointment reminder, standard | | | ☐ |
| 3 | Follow-up, minimal | | | ☐ |
| 4 | Follow-up, standard | | | ☐ |

## 3. Questions (yes / no)

1. Is "Minimal" the right default for every mother until staff ask her? ☐ Yes ☐ No: ____________
2. Default safe hours are 8 am to 8 pm. Is that right? ☐ Yes ☐ No: ____________
3. When a message fails or nobody can tell whether it was sent, the app creates a "call her instead" task for the person who sent it. Is that right? ☐ Yes ☐ No: ____________
4. Should a reply received from a mother (text, voice or photo) be answered within 24 hours (administrative target, not a clinical one)? ☐ Yes ☐ No: ____ hours
5. Inbound messages are **not monitored for emergencies**. The urgent-help page says so (D05 section 4). Should the reminder templates also carry a short line pointing to urgent help? ☐ Yes ☐ No. If yes, wording: ____________

## How your answers get into the app

Your approved wording is typed into the content file (`docs/review/D05-approved-content.example.json`, section `message_templates`) exactly as written, then loaded with `app/scripts/load_approved_content.py`. The app records your name and the approval date with every template, and keeps earlier versions.

**Sign-off**

I approve the templates and audio scripts above for use in the MatriSathi pilot, as filled in.

Name: ____________ Role: ____________ Signature: ____________ Date: ____________
