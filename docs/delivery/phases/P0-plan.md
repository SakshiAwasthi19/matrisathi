# Phase 0 plan: Foundation (SG0 + SG1)

Written 2026-11-07 at SHA `c72ef5e` (branch `w1/w1-b4-reporting-files`). Status: **Proposed, awaiting approval.**

Week 1 restarted: **Mon 9 – Fri 13 Nov 2026, review Sat 14 Nov.**
Task detail lives in `CLAUDE_BUILD_PLAN.md` Part H; progress in `docs/delivery/progress.md`.

## 1. Entry criteria

| Criterion | Met? | Evidence |
|---|---|---|
| None (Phase 0 starts now) | Met | `PHASE_PLAN.md`, Phase 0 |

Starting point already in place: SG1 slice on `main` (`39059e9`), CI green on `main` for `6aa6217`, `d0dd5f9`, `d6bef28`, `fa515a9` (see `docs/status.md`).

## 2. Open decisions and what each blocks

| ID | Owner | State | Blocks in Phase 0 | How we proceed meanwhile |
|---|---|---|---|---|
| D01 team and hours | Manager | Open | No code. Affects capacity (see section 6). | Plan as one developer covering both lanes. |
| D02 sites, language, pediatric reviewer | Manager + doctor | Open | Naming the pediatric reviewer in W1-B6; the second locale's content in W1-B7. | W1-B6 leaves the reviewer as a question; W1-B7 ships an empty second locale. |
| D03 merge approver | Manager | Open | The approver setting in branch protection (W1-A1). | Interim: the developer approves and merges every PR. |
| D04 auth/runtime design | Tech lead | Proposed | Nothing; W1-A3 writes it. | W1-A4's role/secret changes go ahead under the developer's 7 Nov approval. |
| D13 episode model | Manager | Proposed (doc in W1-B8) | Second half of W1-A5 (409 + partial unique index). | Build list + continue only. |
| D14 UI dependencies | Manager informed | Approved by the developer 7 Nov | Nothing. | W1-B7 installs the Part G list, exact versions. |
| D15 review rule, one developer | Manager | Proposed (doc in W1-B8) | Same as D03. | Same interim rule. |

**Gap decisions marked "before build"** (G01, G02, G03, G04, G07, G09, G15, G17, G20): none blocks Phase 0 code. They are scope limits on later phases, already reflected in the plan. Two touch this phase:
- **G15 / R09:** the workbook still says "reuse Care". The proposed amendment (`docs/specifications/R09-G15-proposed-amendments.md`) is the operative text until the manager updates the workbook. Staging (W1-A4, W1-B2) is the "own stack proven in staging" evidence it asks for.
- **G17:** staging holds synthetic data only; no hosting claim is made.

## 3. Task order

One person works both lanes. The order puts the work with the longest human lead time first (decisions, doctor packet, staging accounts, WhatsApp verification) and the evidence pack last.

| Day | Task | Lane | Planned h | Why here |
|---|---|---|---|---|
| Mon 9 | W1-A1 Protect main, PR template, `branching.md` | A | 6 | Every later PR uses the flow. |
| Mon 9 | W1-A2, W1-B1 Prove green CI on a PR | A, B | 4 + 5 | Should be satisfied by the CI runs on the first PRs (W1-B4, W1-A1). Actual hours recorded honestly; saved time goes to W1-A4. |
| Mon 9 | W1-B8 D13–D15 proposals | B | 2 (est.) | Gives the manager the week to decide D13 before W1-A5. |
| Mon 9 | W1-B6 Doctor intake packet (M008) | B | 2 | Doctor needs time to answer before Saturday. |
| Tue 10 | W1-A3 D04 proposal | A | 5 | Documents the auth boundary before W1-A4 changes it. |
| Tue 10–Wed 11 | W1-A4 Staging hardening + `staging.md` | A | 6 + saved | Human creates the separate Supabase project and Render service from the checklist. |
| Wed 11 | W1-B5 WhatsApp provider comparison (D06) | B | 4 | Manager must start business verification this week. |
| Thu 12 | W1-B7 UI foundation and app shell | B | 8 | Builds the shell, including the STAGING banner, once. |
| Thu 12 | W1-A5 Episode list + continue | A | 4 | Late in the week, per decision; built on the new UI. |
| Fri 13 | W1-B2 Vercel deploy, `VITE_ENV_LABEL` | B | 3 | After W1-B7 so the banner is not built twice. Human deploys. |
| Fri 13 | W1-B3 AT01–AT05, rewrite SG1 report | B | 6 | Needs staging up and a candidate SHA. |
| Fri 13 | Week close: `weekly/W1.md`, `phases.md` | — | — | |

W1-B4 (2 h) is done and awaiting review.

## 4. Exit criteria and where each stands

| Exit criterion | Now | Delivered by |
|---|---|---|
| AT01–AT04 pass in CI on one SHA | Pass on `main` CI, not yet at a recorded candidate SHA | W1-B3 |
| AT05 manual staging run (fresh checkout, browser login/create/read, reload, restart) recorded with the SHA | Not run; no staging | W1-A4, W1-B2, W1-B3 |
| P01 shared phone, P03 wrong facility denied | Covered by tests; not run as pilot checks | W1-B3 |
| Staging synthetic-only, own Supabase project, no committed default works, migrations as a release step, app role cannot run DDL | Not started | W1-A4 |
| Manager accepts the SG1 evidence pack | Report out of date | W1-B3, Saturday review |
| D13, D14, D15 decided | D14 approved by developer; D13, D15 not decided | W1-B8, manager |

## 5. Saturday demo outline (14 Nov, synthetic data only)

1. Merge a PR with green CI; show the run tied to the merge SHA.
2. Log in on staging; STAGING banner visible on every page.
3. Register a synthetic mother, then find her and continue her existing episode (no new episode created).
4. Show a wrong-facility request blocked, and the denied audit event.
5. Repeat steps 2–3 on a phone at 360 px.

If staging is not up by Friday: run steps 2–5 locally, and report the gate as **partly met: staging not deployed**, never as passed.

## 6. Risks

- **Capacity.** Phase 0 plans 25 h (Dev A) + 32 h (Dev B, including W1-B8) = **57 h for one person in one week**. D01's developer baseline is 20–25 h. Unless hours change, expect carry-over; the likely candidates are W1-B7 and W1-B5. Raise with the manager on Saturday.
- **Push access.** Pushing to `matrisathi/jananisaathi` currently fails (403 for the account logged in on this machine). Nothing reaches CI until that is fixed.
- **Human steps.** Staging, branch protection and Vercel all need dashboard work by the developer.
- **WhatsApp verification lead time.** The manager must start it this week, or Phase 2 slips.
- **Holiday dates.** Restarted Week 8 is 28–31 Dec; agree the release-candidate date with the manager.

## 7. Human checklist for this week

- [ ] Fix push access (collaborator access, or push from your own account); optionally `gh auth login`.
- [ ] Merge the `CLAUDE.md` and W1-B4 PRs.
- [ ] Apply the GitHub branch protection checklist (from W1-A1).
- [ ] Create the separate staging Supabase project and the Render service (from `staging.md`, W1-A4).
- [ ] Create the Vercel project (W1-B2).
- [ ] Send the M008 packet to the doctor (W1-B6).
- [ ] Hand D13–D15 to the manager (W1-B8); manager starts WhatsApp verification (W1-B5).
