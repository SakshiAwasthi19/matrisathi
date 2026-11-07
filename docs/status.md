# MatriSathi — project status

Last updated: 2026-11-07. Delivery tracking now lives in
`docs/delivery/progress.md` (one row per task) and `docs/delivery/phases.md`
(phase dashboard). Week 1 (SG0 + SG1) restarted Mon 9 Nov 2026; every
tracker date shifts +1 week. Full SG1 detail and closure table:
`docs/delivery/evidence/SG1/report.md` (written 2026-09-30 — its remote/CI
sections predate the remote being added; see "CI" below).

## Completed (locally verified and CI-verified; not reviewer-accepted)

Staff sign-in, mother registration (with intake precision for age/DOB and
free-text history/allergies), pregnancy episode creation, an
authorized-existing-person search by phone and/or name, contact
verification, and viewing the persisted record — backend (FastAPI +
PostgreSQL) and a React/Vite web UI. Selecting an existing mother never
duplicates her person record, and a shared phone number is never merged or
auto-selected.

Also covered: password-based staff auth (throttled, generic failures,
rotating refresh with reuse detection, live disabled-user checks);
explicit organization-admin authority with an admin API; facility-scoped
authorization everywhere, ownership derived server-side; shared-phone
isolation; append-only audit logging enforced at the database role level;
database-level duplicate prevention for retried creates.

**Since 2026-09-30:**
- **Shared team database option** (Supabase) and portability fixes found
  while connecting one (2026-10-02).
- **Staging preparation** (2026-10-02): configurable API base URL, CORS
  origins and cookie SameSite; README steps for a synthetic-data-only
  Render + Vercel deployment. Not deployed from this project.
- **Web client fixes** (2026-10-31, `fa515a9`): the browser now sends an
  `Idempotency-Key` on creates and retries network failures with the same
  key, so a lost response or a failed second registration step no longer
  creates a duplicate mother; a failed episode step after registration
  retries only the episode. The session renews automatically on expiry
  (single refresh per tab, serialized across tabs) and shows "Your session
  has ended" when renewal is refused. First frontend tests (vitest, 18).
  Browser-verified locally against synthetic data.

## CI

GitHub remote `matrisathi/jananisaathi` is configured and
`.github/workflows/ci.yml` runs on every push to `main` (backend: migrations
against a service Postgres, ruff, mypy, pytest; frontend: typecheck, tests,
build). Runs so far, all on `main`:

| Commit | Result | Run |
|---|---|---|
| `6aa6217` | success | [37049405155](https://github.com/matrisathi/jananisaathi/actions/runs/37049405155) |
| `d0dd5f9` | success | [37051664697](https://github.com/matrisathi/jananisaathi/actions/runs/37051664697) |
| `d6bef28` | success | [37062927432](https://github.com/matrisathi/jananisaathi/actions/runs/37062927432) |
| `fa515a9` | success (backend + frontend, incl. vitest) | [41196038674](https://github.com/matrisathi/jananisaathi/actions/runs/41196038674) |

AT05's tracker Result is still "Blocked" pending a reviewer re-checking it
against a CI run tied to a SHA — those runs now exist; updating the tracker
is the reviewer's call.

## Open decisions

- SG0 decisions D01–D03 (team roles, hours, pilot site/language,
  repo/merge policy): still Open. From 2026-11-07 work goes on task
  branches; until D03 and D15 are decided, the developer approves and
  merges every PR. Branch protection on `main` is not yet set (W1-A1).
- D04 (auth/session/runtime versions): proposal built and tested, awaiting
  tech-lead approval. The written proposal is W1-A3.
- **D13 episode model**: decided 2026-11-07, option A (one ACTIVE episode per
  mother), by the developer; manager informed. Built in W1-A5: staff continue a
  mother's active episode; a second one returns 409; a partial unique index
  enforces it. No episode can be closed yet (Phase 3), so a second pregnancy
  for the same mother cannot be recorded until then.
- **D14 UI dependencies**: the build plan's UI library list was approved by
  the developer on 2026-11-07; the manager is informed at the 14 Nov
  review. Not installed yet (W1-B7).
- **D15 review rule for one developer** (manager, Proposed).
- D15 (review rule) and D03 (merge approver): proposals in `docs/decisions/`; interim rule in force.
- D02 pilot language: Open. i18n will start with English plus an empty
  second locale; no language assumed.
- Contact **value** editing (changing a phone number): needs a decision on
  the identity-transfer risk first.
- WhatsApp/BSP vendor: not chosen.
- D09 hosting/compliance for real patient data: open. Staging is
  synthetic-data-only and will use its own Supabase project, never the
  shared team database (W1-A4).

## Known limitations

- No Child, CaregiverLink, CareTask, ApprovedContent or MessagingEvent
  tables (out of SG1 scope).
- No entity `version`/optimistic-concurrency columns — needed with SG2's
  first update endpoint.
- No role-based capability differences beyond facility membership.
- Admin capabilities are API-only, not in the browser UI.
- Name search is plain `ILIKE`; phone search is exact-match with no
  normalization.
- Idempotency keys are kept in browser memory: a page reload mid-attempt
  starts a new attempt. Cross-tab refresh coordination needs the Web Locks
  API (all current browsers).
- vitest 2.1.9 (dev-only) carries `npm audit` advisories, as do the
  existing Vite 5 / esbuild dev dependencies; fixes need a deliberate
  Vite 6+ / vitest 4 upgrade.
- Staging as documented would share the team database, accept the
  committed seed login, and give the web process migrator credentials —
  address before deploying it.
- No doctor/clinical review, no legal/hosting review. Not production-ready.

## Next proposed task

Week 1 (9–13 Nov) tasks are listed in `docs/delivery/progress.md`. Next:
write the Phase 0 plan (`docs/delivery/phases/P0-plan.md`), then work the
Week 1 tasks in its order. W1-A5 (episode list and continue) runs late in
the week. SG2 work still waits on the Phase 0 gate, SG1's human reviews
(M003, M008) and the SG0 decisions.
