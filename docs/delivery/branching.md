# Branching and pull requests

How work reaches `main`. Applies to every task from Week 1 on.

## Rules

- **Nothing goes straight to `main`.** Every change arrives through a pull request.
- **One task per branch and per PR.** Name the branch `w<week>/<task-id-lowercase>-<short-slug>`, for example `w1/w1-a1-protect-main`. Work that is not a task (such as a phase plan) uses `w<week>/<short-slug>`.
- **PR title starts with the task ID**, for example `W2-A3: dating, ANC plan and appointments API`.
- **Use the PR template** (`.github/pull_request_template.md`). Fill in every check with real results; write "not run" for anything skipped.
- **Update `docs/delivery/progress.md` in the same PR.**
- **Merge method:** a single, independent PR is squash-merged. A **stack** of PRs (each based on the previous task's branch) is merged with **merge commits**, in order: squashing a stack would make every later PR show the earlier tasks' changes again. Either way each task has one merge SHA on `main`, recorded in `progress.md`. (Decided 2026-11-07; PRs #1–#27 were merged this way.)
- **Every commit and every push needs the developer's explicit approval** (`CLAUDE.md`).
- **Never force-push `main`**, and never rewrite history that is already pushed.

## Who approves (D03, D15)

D03 (merge approver) and D15 (review rule for one developer) are with the manager.
Until they are decided:

- The developer approves and merges every PR.
- Each PR records review as: *Self-reviewed + automated checks. Independent review: pending (manager at Saturday demo).*
- Never write that someone else reviewed a PR.

When D03 and D15 are decided, update this section and the branch protection settings below.

## Stacked branches

When a task needs files from a branch that is not merged yet, branch from that branch and say so in the PR description ("based on #<n>"). Merge stacked PRs in order, oldest first. After the base merges, retarget the next PR to `main` before merging it.

## CI

`.github/workflows/ci.yml` runs on every pull request and on every push to `main`:

- `backend`: migrations against a service Postgres, ruff, mypy, pytest
- `frontend`: npm ci, typecheck, vitest, build

A PR merges only when both jobs are green. Record the merge SHA and the Actions run link for that SHA in `progress.md`.

## GitHub settings checklist (the developer does this)

Repository → Settings.

**General → Pull Requests**
- [ ] Allow squash merging: on. Allow merge commits: off. Allow rebase merging: off.
- [ ] Automatically delete head branches: on.

**Branches → Add branch protection rule** (or Rules → Rulesets, targeting `main`)
- [ ] Branch name pattern: `main`
- [ ] Require a pull request before merging: on
  - [ ] Required approvals: **0** for now. GitHub does not let you approve your own PR, and there is one developer. Raise this when D03/D15 name a reviewer.
- [ ] Require status checks to pass before merging: on
  - [ ] Require branches to be up to date before merging: on
  - [ ] Required checks: `backend` and `frontend` (they appear in the search box after the workflow has run once on a PR)
- [ ] Do not allow bypassing the above settings (applies to administrators too): on
- [ ] Allow force pushes: off
- [ ] Allow deletions: off

**Collaborators**
- [ ] The account that pushes from the development machine has write access.

## Verify it works (the developer does this)

1. From an up-to-date local `main`, make an empty commit and run `git push origin main`. It must be **rejected** with a protected-branch error. Then delete the local commit: `git reset --hard origin/main`.
2. Open a PR whose CI is still running or red. The merge button must be **blocked**.
3. Record both results (date, and the rejection message without any tokens) in the W1-A1 row of `progress.md`.
