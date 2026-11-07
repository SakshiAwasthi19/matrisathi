# Phase dashboard (updated 2026-11-07, SHA `7df67ff`)

| Phase | Gate | Status | Dev A tasks accepted | Dev B tasks accepted | ATs pass / required | Pilot checks pass / required | Open decisions | Blockers |
|---|---|---|---|---|---|---|---|---|
| 0 Foundation | SG0+SG1 | Ready for review: not passed | 0/6 | 0/8 | 0/5 | 0/2 | D01 D02 D03 D04 D13 (decided by developer) D14 (approved by developer) D15 | No CI run on Week 1 work (PRs not opened); staging not deployed; reviews pending |
| 1 Pregnancy care | SG2 | Ready for review: not passed (started early) | 0/5 | 0/5 | 0/6 | 0/6 | D04 D05 D07 | No CI; no staging run; AT28 and P04 Blocked: D07; real template and wording wait for D05 |
| 2 Messaging | SG3 | Not started | 0/4 | 0/4 | 0/4 | 0/2 | D06 D08 | Phase 1 gate; WhatsApp business verification lead time |
| 3 Birth & postpartum | SG4 | Not started | 0/4 | 0/4 | 0/5 | 0/3 | — | Phase 2 gate |
| 4 Child & field | SG5 interim | Not started | 0/4 | 0/4 | 0/3 | 0/4 | — | Phase 3 gate |
| 5 MVP complete | SG5 | Not started | 0/4 | 0/4 | 0/28 | 0/1 | D09 D10 | Phase 4 check |
| 6 Pilot readiness | SG6+SG7 | Not started | 0/6 | 0/6 | 0/32 | 0/6 | D11 D12 | Phase 5 gate; holiday dates |

ATs and pilot checks count only when actually run at a recorded SHA in CI or on staging. Phase 0 and Phase 1 cases all pass **locally** (pytest 342, vitest 46 at `7df67ff`) but are not counted until CI and staging runs exist.

## Current phase: 1, all ten tasks built and pushed; gate not passed (no CI, no staging, D07/D05 open)
Close report: `docs/delivery/phases/P1-close.md`. Phase 0 evidence: `docs/delivery/evidence/SG1/report.md`.

## What was shown at the last Saturday review
Nothing yet. The first review is Sat 14 Nov.

## Next phase entry criteria: not met
Phase 2 needs: Phase 1 gate accepted; D06 decided; message templates submitted; consenting staff test numbers.

## The three things that unblock the most
1. Open the 26 pull requests in stack order (or run `gh auth login` so Claude can), so CI runs on every task.
2. Deploy staging (`docs/delivery/staging.md`) and run the SG1 and SG2 scripts there.
3. Manager decisions D07 (patient access) and D15/D03 (review), and the doctor's D05 answers.
