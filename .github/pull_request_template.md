## Task
<Task ID>: <work package> (lane: Dev A | Dev B)

## Spec links
F-IDs: … T-IDs: … AT/P: …

## What changed

## How it was verified
- [ ] pytest: <n passed>  - [ ] ruff  - [ ] mypy
- [ ] web typecheck  - [ ] vitest: <n passed>  - [ ] build
- [ ] migration up/down on fresh DB (if changed)
- Manual check on staging: <steps>

## Clinical boundary check
- [ ] No scoring, thresholds, interpretation or generated clinical advice
- [ ] Unknown stays unknown; clinician-only actions enforced server-side

## Privacy check
- [ ] Synthetic data only; no patient text, message content or secrets in logs/fixtures/screenshots

## Review
Self-reviewed + automated checks. Independent review: pending (manager at Saturday demo).

## Progress log
- [ ] docs/delivery/progress.md updated
