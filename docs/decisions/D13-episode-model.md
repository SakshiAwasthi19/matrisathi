# D13: Pregnancy episode model

**Status:** Proposed. **Decides:** manager. **Written:** 2026-11-07 (W1-B8).
**Blocks:** the second half of W1-A5 (409 on a second active episode, enforced by a database index). The first half (list a mother's episodes, continue an existing active one) is being built now and works under every option below.

## The question

How many **active** pregnancy episodes may one mother have at the same time, and how does staff start a new one?

## What the system does today

- An episode has status `ACTIVE` or `CLOSED` (`apps/api/app/models/pregnancy.py`). There is a `closed_at` field.
- **No endpoint closes an episode.** Every episode ever created is still `ACTIVE`.
- On the Find screen, "Select & create episode" (`apps/web/src/pages/FindMother.tsx`) always creates a **new** episode. A mother found twice gets two active episodes.
- Retried creates are already safe: the same `Idempotency-Key` never creates a second episode. That protects against network retries, not against a second deliberate click.
- The episode's facility is always taken from the mother's record on the server, never from the browser.

## Why it matters later

Every later phase hangs work off the episode: the ANC plan and appointments (Phase 1), reminders (Phase 2), birth and outcome (Phase 3). Two active episodes for one mother would mean two plans, duplicate reminders and confusion over which record is current. Readmission and transfer (Phase 3) also need a clear "current episode".

## Options

### A. One active episode per mother, enforced by the database (recommended)
- A partial unique index allows at most one `ACTIVE` episode per mother.
- Creating a second one returns **409** with a link to the existing episode. The Find screen offers "Continue episode" instead.
- A new pregnancy can only start once the previous episode is closed. The close action comes with the birth and outcome work (Phase 3); until then, a second pregnancy for the same mother cannot be recorded (rare in a pilot of weeks, and visible as a clear 409, not silent).
- **Risk:** existing synthetic data already has mothers with several active episodes; the migration must find and report them first, and refuse to apply until they are resolved (dev and shared team data only; staging starts empty).

### B. Several active episodes allowed; the screen warns
- No database rule. The Find screen shows existing active episodes and warns before creating another.
- **Risk:** the warning can be clicked through, by mistake or on a slow connection. Duplicates reach Phase 1 plans and Phase 2 reminders. Every later feature must handle "which episode?".

### C. One active episode, plus a staff "close and start new" action now
- As option A, plus an audited, staff-only action to close the current episode with a reason and start a new one.
- **Risk:** closing an episode is close to a clinical event (birth, loss, transfer). Building a free-text close reason now, before the Phase 3 outcome model and doctor-approved wording, invites inconsistent records. Choosing the reason list needs the doctor.

## Recommendation

**Option A now.** It makes the safe path (continue the existing episode) the only path, matches the system's rule of preventing duplicates at the database, and costs little. The close action (option C's addition) arrives with the Phase 3 birth and outcome work, where the reasons are designed with the doctor.

Nothing in this decision involves clinical judgement: it decides only how records are counted and which actions staff can take.

## If A is chosen, W1-A5 part 2 builds

- The partial unique index, with a pre-check that lists any mother with more than one active episode.
- 409 on a second active episode, with the existing episode's ID.
- Tests: the 409, the index, and isolation across facilities.

## Questions for the manager

1. Approve option A? (yes / no, choose B or C)
2. Is it acceptable that a second pregnancy for the same mother cannot be recorded until the Phase 3 close action exists? (yes / no)
