# D15: Code review with one developer

**Status:** Proposed. **Decides:** manager (together with D03, merge approver). **Written:** 2026-11-07 (W1-B8).
**Blocks:** the approver setting in branch protection (W1-A1). Interim rule in force until decided.

## The question

The tracker assumed two developers who review each other's pull requests. There is now one developer, working with an AI assistant. Who reviews code before it reaches `main`?

## Interim rule (in force now)

- The developer approves and merges every PR.
- Every PR records: *Self-reviewed + automated checks. Independent review: pending (manager at Saturday demo).*
- Branch protection requires a PR and green `backend` and `frontend` CI checks, with 0 approvals (GitHub does not let you approve your own PR).

## What automated checks cover

Every PR runs migrations on a fresh database, lint (ruff), type checks (mypy, tsc), backend tests (pytest) and frontend tests (vitest), and a production build. They catch regressions in tested behaviour. They do not catch a wrong design, a missing test, or an access rule that was never written.

## Options

### A. Self-review plus automated checks; the manager reviews at the Saturday demo
- What happens now, made permanent.
- **Cost:** none. **Risk:** the manager sees behaviour, not code. Security and data-access mistakes can reach `main` and be found weeks later.

### B. A part-time external reviewer for every PR
- **Cost:** paid hours, and a delay on every merge. **Risk:** a reviewer new to the project needs onboarding; slow reviews push the weekly plan.

### C. The tech lead reviews high-risk PRs only
- PRs that touch authentication, database roles, secrets, facility or caregiver access, clinician-only actions, or migrations are labelled `needs-tech-lead` and wait for the tech lead's review before merge. Everything else follows option A.
- **Cost:** a few hours of tech-lead time a week. **Risk:** depends on labelling honestly; a missed label skips review.

### Not an option on its own: AI review
The assistant already reviews its own work and can run an automated code review. `CLAUDE.md` is explicit: *AI review does not replace executable tests or tech-lead review.* It is a supplement under any option.

## Recommendation

**Option A plus option C.** Routine PRs move at the speed the plan needs; the changes that can leak patient data or break access control get a human expert's review before merge. The weekly report lists every `needs-tech-lead` PR and its review state.

## If chosen, what changes

- `docs/delivery/branching.md`: the review section, and the label rule.
- Branch protection: still 0 required approvals (GitHub cannot express "only for labelled PRs"); the tech lead's review is recorded on the PR and checked at the Saturday review.
- PR template: one checkbox, "touches a high-risk area → `needs-tech-lead`".

## Questions for the manager

1. Approve option A + C? (yes / no, choose another)
2. Who is the tech lead reviewer for `needs-tech-lead` PRs, and how fast can they review (target: 2 working days)?
3. Who is the merge approver (D03)? Proposed: the developer, until a second developer joins.
