Work out where we are, without asking me:
1. Read docs/delivery/progress.md, docs/delivery/phases.md, docs/delivery/PHASE_PLAN.md and docs/delivery/CLAUDE_BUILD_PLAN.md.
   If progress.md doesn't exist yet, we are at Phase 0, Week 1, and the next task is W1-B4 (it creates progress.md).
2. Current phase = the lowest phase not yet Accepted. Current week = that phase's tracker week.
3. Next task = the first task in the current phase that is Not started or In progress, and is not Blocked,
   in the order given in docs/delivery/phases/P<n>-plan.md (or the plan's table order if that file doesn't exist).
   If the phase has no plan file yet, the next step is to write it (PHASE_PLAN.md section 2, step 1).
4. If every task in the phase is Ready for review or Accepted, tell me to run the phase close instead.

Tell me in 3 lines: "Phase X, Week Y. Next: <task ID> — <one line>. Blocked: <anything>".
Then start that task following CLAUDE_BUILD_PLAN.md Part C: propose the plan and wait for my approval.
