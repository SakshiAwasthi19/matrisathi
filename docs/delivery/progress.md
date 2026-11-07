# Progress log

Last updated: 2026-11-07, SHA `39059e9` (`main`).

**Dates:** Week 1 restarted on Mon 9 Nov 2026. Every tracker date shifts +1 week.
Task IDs and planned hours come from `docs/delivery/CLAUDE_BUILD_PLAN.md`, Part H. The two-developer tracker workbook is updated by hand from this file.

| Week | Gate | Tracker dates | Restarted dates | Saturday review |
|---|---|---|---|---|
| 1 | SG0 + SG1 | 2–6 Nov | 9–13 Nov | 14 Nov |
| 2 | SG2 | 9–13 Nov | 16–20 Nov | 21 Nov |
| 3 | SG3 | 16–20 Nov | 23–27 Nov | 28 Nov |
| 4 | SG4 | 23–27 Nov | 30 Nov–4 Dec | 5 Dec |
| 5 | SG5 interim | 30 Nov–4 Dec | 7–11 Dec | 12 Dec |
| 6 | SG5 | 7–11 Dec | 14–18 Dec | 19 Dec |
| 7 | SG6 | 14–18 Dec | 21–25 Dec | 26 Dec |
| 8 | SG7 | 21–24 Dec | 28–31 Dec | to agree with the manager |
| Reserve | — | 28–31 Dec | 4–8 Jan | — |

Weeks 7–8 now fall in the holiday period. Agree the release-candidate date with the manager.

**Status values:** `Not started`, `In progress`, `Ready for review`, `Accepted`, `Blocked`. Claude never sets `Accepted`; the manager does, at the Saturday review.

**Review:** every PR is self-reviewed plus automated checks. Independent review is pending (manager at the Saturday demo). Until D03 and D15 are decided, the developer approves and merges every PR.

| Task ID | Week | Lane | Work package | Planned h | Actual h | Status | PR | Merge SHA | CI run | AT / P checks | Evidence | Feedback IDs | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| W1-A1 | 1 | Dev A | Protect main, task branches, first green CI tied to a SHA | 6 | 1 (est.) | Ready for review | | | | AT05 | `.github/pull_request_template.md`, `docs/delivery/branching.md` | | Stale CI comment removed. Pending: push access (403), PR CI run, merge SHA + run link, branch protection applied and direct push to `main` rejected (developer verifies). |
| W1-A2 | 1 | Dev A | Prove a green backend CI run on a PR (reduced) | 4 | | Not started | | | | | | | Reduced 7 Nov: backend CI already green on `main` (`fa515a9`). Saved time goes to W1-A4. |
| W1-A3 | 1 | Dev A | D04 auth, tenant and audit design proposal | 5 | | Not started | | | | | | | Draft content exists in SG1 report §9. |
| W1-A4 | 1 | Dev A | Harden and deploy synthetic-only backend staging | 6 (+ time saved on W1-A2, W1-B1) | | Not started | | | | AT05 | | | Scope grown 7 Nov: all committed defaults refuse under `ENV=staging`, migrations as a release step, DDL test, separate Supabase project. |
| W1-A5 | 1 | Dev A | (added) Episode model part 1: list and continue episodes | 4 | | Not started | | | | | | | Late in the week. 409 and partial unique index held until D13. |
| W1-B1 | 1 | Dev B | Prove a green frontend CI run on a PR (reduced) | 5 | | Not started | | | | | | | Reduced 7 Nov: SG1 work already on `main`, frontend CI green (`fa515a9`). Saved time goes to W1-A4. |
| W1-B2 | 1 | Dev B | Frontend staging on Vercel, STAGING banner | 3 | | Not started | | | | AT05 | | | |
| W1-B3 | 1 | Dev B | Run AT01–AT05; rewrite SG1 evidence pack | 6 | | Not started | | | | AT01–AT05, P01, P03 | | | Existing report is out of date ("no remote", "uncommitted"). |
| W1-B4 | 1 | Dev B | Refresh status.md; create reporting files | 2 | 0.5 (est.) | Ready for review | | | | | `docs/delivery/progress.md`, `docs/delivery/phases.md` | | |
| W1-B5 | 1 | Dev B | WhatsApp provider comparison (D06) | 4 | | Not started | | | | | | | |
| W1-B6 | 1 | Dev B | Doctor intake review packet (M008) | 2 | 1 (est.) | Ready for review | | | | | `docs/review/M008-intake-and-roles.md` | | Ready to send. Flags gaps: no preferred language, dating or information source on the screen; no ANM role; no role differences yet. |
| W1-B7 | 1 | Dev B | (added) UI foundation and app shell | 8 | | Not started | | | | | | | D14 approved by the developer 7 Nov. i18n: English plus an empty second locale. |
| W1-B8 | 1 | Dev B | (added) D13–D15 decision proposals | 2 (est.) | 1 (est.) | Ready for review | | | | | `docs/decisions/D13-episode-model.md`, `D14-ui-dependencies.md`, `D15-single-developer-review.md` | | Added 7 Nov. Hours are an estimate, not from the tracker. D14 companion packages (shadcn helpers, @tailwindcss/vite, i18next, bundled Noto Sans) approved by the developer 7 Nov. |
| W2-A1 | 2 | Dev A | Plan and task state model; private file storage | 4 | | Not started | | | | | | | Includes the app-role grants proposal for new tables. |
| W2-A2 | 2 | Dev A | Patient and caregiver access; propose D07 | 4 | | Not started | | | | | | | |
| W2-A3 | 2 | Dev A | API: dating, ANC plan, appointments, owned tasks | 5 | | Not started | | | | AT06, AT07 | | | |
| W2-A4 | 2 | Dev A | API: reports, prescriptions, observations, referrals, contacts | 6 | | Not started | | | | AT08, AT09 | | | |
| W2-A5 | 2 | Dev A | API: next-action view, birth plan, caregiver access | 2 | | Not started | | | | | | | |
| W2-B1 | 2 | Dev B | Screens: dating, ANC plan, calendar, task list, Today worklist | 4 | | Not started | | | | | | | |
| W2-B2 | 2 | Dev B | Screens: report upload, prescriptions, referrals, contacts | 4 | | Not started | | | | AT08, AT09 | | | |
| W2-B3 | 2 | Dev B | Next step, birth plan, public urgent help, caregiver access | 6 | | Not started | | | | AT10, AT28 | | | |
| W2-B4 | 2 | Dev B | Synthetic test cases for AT01–AT10 and AT28 | 5 | | Not started | | | | | | | |
| W2-B5 | 2 | Dev B | Doctor packet: ANC template and urgent wording | 1 | | Not started | | | | | | | |
| W3-A1 | 3 | Dev A | Provider adapter, signed webhook, durable outbox | 7 | | Not started | | | | AT12, AT30 | | | |
| W3-A2 | 3 | Dev A | Media privacy and inbox access rules | 3 | | Not started | | | | | | | |
| W3-A3 | 3 | Dev A | Outbound templates, delivery states, send-time checks | 6 | | Not started | | | | AT11, AT12 | | | |
| W3-A4 | 3 | Dev A | Inbound text, voice and photo become inbox items | 4 | | Not started | | | | AT13 | | | |
| W3-B1 | 3 | Dev B | Staff inbox for text, voice and photo | 8 | | Not started | | | | | | | |
| W3-B2 | 3 | Dev B | Audio playback, contact preferences, opt-out, phone fallback | 6 | | Not started | | | | AT14 | | | |
| W3-B3 | 3 | Dev B | Tests: duplicate webhook, failed send, opt-out, shared phone, bad file | 5 | | Not started | | | | P06, P07 | | | |
| W3-B4 | 3 | Dev B | Doctor packet: templates and audio | 1 | | Not started | | | | | | | |
| W4-A1 | 4 | Dev A | Birth, outcome and child data model | 5 | | Not started | | | | AT29 | | | |
| W4-A2 | 4 | Dev A | Message pause and transfer concurrency design | 4 | | Not started | | | | | | | |
| W4-A3 | 4 | Dev A | API: birth, twins, child linking, separate discharge | 6 | | Not started | | | | AT15, AT16 | | | |
| W4-A4 | 4 | Dev A | API: loss pause, transfer, readmission | 5 | | Not started | | | | AT17, AT18 | | | |
| W4-B1 | 4 | Dev B | Screens: birth, twins, child linking, separate discharge | 5 | | Not started | | | | | | | |
| W4-B2 | 4 | Dev B | Screens: loss pause, transfer, readmission | 4 | | Not started | | | | | | | |
| W4-B3 | 4 | Dev B | Postpartum and newborn follow-up; missed contacts | 7 | | Not started | | | | | | | |
| W4-B4 | 4 | Dev B | Tests: twins, discharge, loss, transfer, queued messages | 4 | | Not started | | | | | | | |
| W5-A1 | 5 | Dev A | Offline draft rules | 7 | | Not started | | | | AT20 | | | |
| W5-A2 | 5 | Dev A | Child schedule, guardian, content withdrawal | 4 | | Not started | | | | | | | |
| W5-A3 | 5 | Dev A | API: infancy and early childhood, vaccines, measurements | 5 | | Not started | | | | AT19 | | | |
| W5-A4 | 5 | Dev A | API: guardian permissions; content publish and withdraw | 4 | | Not started | | | | AT21 | | | |
| W5-B1 | 5 | Dev B | Screens: infancy, early childhood, vaccines, measurements | 6 | | Not started | | | | | | | |
| W5-B2 | 5 | Dev B | Offline field drafts in the browser (PWA) | 8 | | Not started | | | | AT20, P16, P18 | | | |
| W5-B3 | 5 | Dev B | Content publish/withdraw and guardian screens | 3 | | Not started | | | | | | | |
| W5-B4 | 5 | Dev B | Low-end Android and weak-network tests | 4 | | Not started | | | | | | | |
| W6-A1 | 6 | Dev A | Security review and requirement traceability | 6 | | Not started | | | | AT32 | | | |
| W6-A2 | 6 | Dev A | Staging/production separation, backup and deploy plan | 5 | | Not started | | | | | | | |
| W6-A3 | 6 | Dev A | API: privacy rights requests, audit views, safe exports | 5 | | Not started | | | | AT22 | | | |
| W6-A4 | 6 | Dev A | Fix defects from the full-suite run | 5 | | Not started | | | | | | | |
| W6-B1 | 6 | Dev B | Ops worklist, failure queue, reminder pause | 7 | | Not started | | | | AT23 | | | |
| W6-B2 | 6 | Dev B | Audit view and export screens | 3 | | Not started | | | | | | | |
| W6-B3 | 6 | Dev B | Close scope gaps; AI-disabled runs | 5 | | Not started | | | | AT31 | | | |
| W6-B4 | 6 | Dev B | Full functional suite at the candidate SHA | 6 | | Not started | | | | | | | |
| W7-A1 | 7 | Dev A | Timed restore, rollback and load drills | 8 | | Not started | | | | AT25, AT26 | | | |
| W7-A2 | 7 | Dev A | Triage security and field findings | 4 | | Not started | | | | | | | |
| W7-A3 | 7 | Dev A | Hardening regressions | 6 | | Not started | | | | | | | |
| W7-B1 | 7 | Dev B | Devices, staging accounts, observation sheet | 3 | | Not started | | | | | | | |
| W7-B2 | 7 | Dev B | Fix usability defects from field sessions | 10 | | Not started | | | | AT24 | | | |
| W7-B3 | 7 | Dev B | Self re-run of drills and regressions | 6 | | Not started | | | | | | | |
| W8-A1 | 8 | Dev A | Candidate SHA, migration and deploy rehearsal | 6 | | Not started | | | | | | | |
| W8-A2 | 8 | Dev A | Technical release review pack | 4 | | Not started | | | | | | | |
| W8-A3 | 8 | Dev A | Release-candidate defect fixes (backend) | 6 | | Not started | | | | | | | |
| W8-B1 | 8 | Dev B | Release-candidate defect fixes (frontend) | 5 | | Not started | | | | | | | |
| W8-B2 | 8 | Dev B | Setup package, training guide, final demo | 6 | | Not started | | | | | | | |
| W8-B3 | 8 | Dev B | Clean setup on a fresh machine | 5 | | Not started | | | | | | | |
