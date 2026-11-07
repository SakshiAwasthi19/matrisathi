# SG1 evidence report: MatriSathi foundation

**Prepared by:** Claude (implementer), 2026-11-07, task W1-B3.
**For:** the manager (SG1 acceptance), the tech lead (M003) and the doctor (M008).
**This is evidence for human reviewers. It is not a self-declared gate pass.**

The earlier versions of this report (2026-09-29 and 2026-09-30) are in this file's git history. They were written before the GitHub repository was connected and describe working-tree snapshots; this version replaces them and ties every result to a real commit.

---

## 0. How to read the results

| State | Means |
|---|---|
| **Local pass** | Ran and passed on the developer machine at the stated commit. |
| **CI pass** | Ran and passed in GitHub Actions at the stated commit. |
| **Staging pass** | Ran and passed on the deployed synthetic-only staging. |
| **Accepted** | A named human reviewer accepted it. Only the manager sets this. |

Nothing below is "Accepted". Nothing at the candidate commit is "CI pass" yet (section 1).

## 1. Candidate commit

| | |
|---|---|
| **Candidate SHA** | `48f6e0e2f9826f9f040538ab08fb9588abd81314` (`48f6e0e`) |
| Branch | `w1/w1-b2-vercel-staging`: the tip of the Week 1 branch stack, built on `main` at `39059e9` |
| Pushed? | **No.** The developer's GitHub account cannot push yet (403); access expected 2026-11-08. All Week 1 work is committed locally on stacked `w1/*` branches. |
| CI at this SHA | **Pending** until the branches are pushed and PRs opened. |
| Local runtime | Python 3.12.13 (pinned 3.12.14), Node 24.12.0 (pinned 26.8.1), PostgreSQL 16.4. The local uv (0.11.32) cannot install 3.12.14; CI uses the pinned versions. |
| Raw output | [`local-run-48f6e0e.txt`](local-run-48f6e0e.txt) |

**CI already run on `main`** (all success; GitHub Actions, backend + frontend):

| Commit | Run |
|---|---|
| `6aa6217` | [37049405155](https://github.com/matrisathi/jananisaathi/actions/runs/37049405155) |
| `d0dd5f9` | [37051664697](https://github.com/matrisathi/jananisaathi/actions/runs/37051664697) |
| `d6bef28` | [37062927432](https://github.com/matrisathi/jananisaathi/actions/runs/37062927432) |
| `fa515a9` | [41196038674](https://github.com/matrisathi/jananisaathi/actions/runs/41196038674) |

These prove the pipeline works; they do not cover the Week 1 changes.

## 2. Results at a glance

Phase 0 exit criterion (decided 2026-11-07): **AT01–AT04 pass in CI on one SHA; AT05 is a manual staging run recorded with the SHA.**

| Check | Local (`48f6e0e`, 2026-11-07) | CI | Staging | Notes |
|---|---|---|---|---|
| AT01 Staff login and sessions | **Pass** (14 tests) | Pending push | n/a | |
| AT02 Organization and facility isolation | **Pass** (12 tests) | Pending push | n/a | |
| AT03 Shared phone and reference injection | **Pass** (19 tests) | Pending push | n/a | |
| AT04 Audit integrity | **Pass** (9 tests) | Pending push | n/a | New finding F8 (section 5) |
| AT05 Repeatable foundation | **Pass** (fresh clone, section 3.5) | Pending push | **Not run**: staging not deployed | Gate needs the staging run |
| P01 Shared phone (pilot check) | **Pass** (4 tests) | Pending push | Not run | |
| P03 Wrong facility denied (pilot check) | **Pass** (5 tests) | Pending push | Not run | |
| Full suites | pytest **88 passed**, ruff clean, mypy clean (33 files); web typecheck clean, vitest **32 passed**, build OK (main JS 115.13 kB gzipped) | Pending push | | |

The pilot checks P01 and P03 have no standalone wording in either workbook (they appear only as references in G06, G10 and G14). They are taken here as the phase plan states them: "P01 (shared phone)" and "P03 (wrong facility denied)".

## 3. Each check: steps, actual result, evidence

Expected results are copied from the tracker's Acceptance sheet. **Actual** results are what ran on 2026-11-07 at `48f6e0e`.

### 3.1 AT01 Staff login and sessions

- **Steps (tracker):** login with seeded staff; reject invalid/expired tokens; refresh, logout, replay and disable account.
- **Expected:** valid session works; rotated/revoked sessions fail; generic errors and throttling evidenced.
- **Actual: Pass, 14/14.** `tests/test_auth.py` (12): cookies set on login; no/malformed/wrong-secret token rejected; one generic error for wrong password, unknown user and disabled account; throttling after repeated failures; disabled user loses access mid-session; logout requires the CSRF header and revokes the refresh token; refresh rotates, and replaying the old token revokes every session. Plus `test_login_requires_csrf_header` and `test_refresh_requires_csrf_header` (W1-A4, D04 finding F1).
- **Also:** with `ENV=staging` the API refuses to start with the committed JWT secret, and the seed script refuses the committed password (`tests/test_staging_safety.py`, W1-A4).

### 3.2 AT02 Organization and facility isolation

- **Steps:** two organizations, two facilities in one organization, coordinator and org admin; revoke membership.
- **Expected:** allowed access only; org admin cannot cross organization; same token loses revoked access.
- **Actual: Pass, 12/12.** `test_access_isolation.py` (4): facility B cannot read facility A's episode; revoked membership loses access on the next request; disabled facility blocks registration; two organizations isolated. `test_admin_membership.py` (4) and `test_org_admin.py` (4): admin authority is an explicit grant, cannot cross organizations, is revocable, and gives **no** record access by itself.

### 3.3 AT03 Shared phone and reference injection

- **Steps:** two people sharing one phone; try linking an inaccessible person into a new episode.
- **Expected:** people remain distinct; forbidden link and unauthorized search denied without exposing records.
- **Actual: Pass, 19/19.** `test_shared_phone.py` (2), `test_person_search_and_intake.py` (11), `test_person_pregnancy_authz.py` (6): two people on one phone stay separate and searchable as two; search is facility-scoped; an inaccessible person cannot be linked into an episode (404); the episode's facility is derived on the server; retried creates never duplicate; unknown age stores no invented values.

### 3.4 AT04 Audit integrity

- **Steps:** create/read records; trigger a denied request; try UPDATE/DELETE using the runtime DB role.
- **Expected:** successful and denied events persist with actor/time; runtime cannot alter history; no sensitive payloads.
- **Actual: Pass, 9/9.** `test_audit.py` (4): one audit row per create and read; denied access writes a DENIED row; the audit row survives a rollback of the request; the app role gets "permission denied" on UPDATE and DELETE of `audit_event`. `test_app_db_role_cannot_run_ddl` (5 cases): the app role cannot CREATE/ALTER/DROP tables, create a schema or an index.
- **Finding F8** (app role could write `alembic_version`) is fixed in W1-A6, after this candidate.

### 3.5 AT05 Repeatable foundation

- **Steps:** fresh checkout; locked install; migrations; real UI login/create/read; reload and restart.
- **Expected:** documented commands succeed; persisted record shown; CI output tied to SHA.
- **Actual, local: Pass.**
  1. `git clone` of the repository, checkout `48f6e0e`, no local changes.
  2. `uv sync --frozen` (locked) and `npm ci` (locked).
  3. `alembic upgrade head` on a brand-new database: all 5 migrations applied.
  4. `pytest`: 88 passed. `vitest`: 32 passed. `npm run build`: OK. Total 62 s.
  5. API login, create mother, create episode, read back; second episode for the same mother returns 409 with the existing episode's id (W1-A5).
  6. API restarted; after a fresh login the same episode (`f5c25c2e…`, synthetic) was read back as ACTIVE.
  7. Browser: the developer signed in and used the Find screen at 1280 px on the local build ([screenshot](screenshots/find-mother-1280px-2026-11-07.png)). The 360 px check and the full browser script are **not yet recorded**.
- **Not yet done (needed for the gate):** the same run on **staging** (`docs/delivery/staging.md` section 6) and CI output at the candidate SHA.

### 3.6 P01 Shared phone (pilot check)

**Local pass, 4/4:** two people on one phone are never merged (`test_shared_phone.py`, 2), search on a shared phone returns distinct people, and two women on one phone each get their own active pregnancy episode (`test_mothers_are_independent`).

### 3.7 P03 Wrong facility denied (pilot check)

**Local pass, 5/5:** reading another facility's episode, linking its person into an episode, searching its records, confirming its contact, and listing its episodes are all denied with 404 (never confirming the record exists), and the denial is audited.

## 4. Schema review (fresh database at `48f6e0e`)

**Tables (12 + `alembic_version`):** `organization`, `organization_admin`, `facility`, `staff_user`, `staff_membership`, `login_attempt`, `refresh_token`, `person`, `contact_method`, `pregnancy_episode`, `idempotency_key`, `audit_event`.

**Constraints and indexes that carry rules:**

| Table | Rule | Enforces |
|---|---|---|
| `staff_user` | unique `username` | one login per username |
| `refresh_token` | unique `token_hash` | a refresh token maps to one session |
| `idempotency_key` | unique (`staff_user_id`, `endpoint`, `key`) | a retried create returns the original record |
| `pregnancy_episode` | partial unique index `uq_pregnancy_episode_one_active` on `mother_person_id` where `status = 'ACTIVE'` | at most one active episode per mother (D13, W1-A5) |
| `contact_method` | **no** unique on `value` (deliberate) | a phone may belong to several people |
| all | 16 foreign keys | references point at real rows |

No CHECK constraints exist. The age-precision rule (exactly one of date of birth / birth year / approximate age, matching the chosen precision) is enforced in the API schema only, not in the database. Proposed for SG2 with the first update endpoint.

**Database roles:**

| Check | Result |
|---|---|
| App role (`matrisathi_app`) on business tables | SELECT, INSERT, UPDATE, DELETE |
| App role on `audit_event` | **INSERT, SELECT only** (append-only) |
| App role can create in schema `public` / create a schema | **No / No** |
| Tables owned by the app role | **0** |
| App role on `alembic_version` | SELECT, INSERT, UPDATE, DELETE at `48f6e0e`: **finding F8**, fixed in W1-A6 (none after `b2f8c41d9e02`) |
| Grants for new tables | Written by hand in each migration; there are **no default privileges**. |

**Correction to the previous report:** its section 9 said `ALTER DEFAULT PRIVILEGES` automatically grants future tables to the app role. That was wrong: no migration contains it (checked 2026-11-07). New tables need an explicit grant; W2-A1 proposes default privileges or a migration helper.

## 5. Defects and findings

| # | Finding | Status |
|---|---|---|
| D-1 | Idempotency check-then-insert race | Fixed 2026-09-30 (`test_truly_concurrent_identical_requests_create_exactly_one_person`) |
| D-2 | `create_person` denials not audited | Fixed 2026-09-30 |
| D-3 | No age/DOB precision | Fixed 2026-09-30 |
| D-4 | No person search | Fixed 2026-09-30 |
| D-5 | Contact verification had no endpoint | Fixed 2026-09-30 |
| D04-F1 | CSRF header not required on login/refresh | **Fixed** in W1-A4 |
| D04-F2 | Login throttling is per username only (lock-out by anyone who knows a username) | Open; tech lead question in D04 |
| D04-F3 | `Idempotency-Key` header optional on create endpoints | Open; tech lead question in D04 |
| D04-F4–F7 | Minor (audit event of refresh reuse not asserted; stale code comment; access token valid ≤15 min after logout; CORS lacks PATCH) | Open, low |
| **F8** | The app role could UPDATE/DELETE `alembic_version` (granted by `0002`'s "all tables" grant), so a compromised app process could falsify the recorded schema version. | **Fixed** in W1-A6 (migration `b2f8c41d9e02` revokes all app-role privileges on it; `test_app_db_role_has_no_access_to_alembic_version`). Not in candidate `48f6e0e`; included from the next candidate. |
| Episode model | "Select & create episode" always opened a new episode | **Fixed** in W1-A5 (D13 option A) |
| Staging defaults | Committed seed password, app-role password and JWT secret would have worked on staging; migrations ran in the web start command | **Fixed** in W1-A4 |

## 6. Reviews and approvals outstanding

| Review | Owner | Material | State |
|---|---|---|---|
| M003 identity/auth/tenant/audit design | Tech lead | `docs/decisions/D04-auth-runtime.md`; this report sections 3–5 | Not started |
| M008 intake fields and roles | Doctor | `docs/review/M008-intake-and-roles.md` | Ready to send; not sent |
| D13 episode model | Manager | `docs/decisions/D13-episode-model.md` | Decided by the developer 2026-11-07 (option A); manager to confirm |
| D14 UI dependencies | Manager | `docs/decisions/D14-ui-dependencies.md` | Approved by the developer; manager informed |
| D15 / D03 review rule, merge approver | Manager | `docs/decisions/D15-single-developer-review.md` | Proposed; interim rule in force |
| SG1 evidence acceptance | Manager | This report | Saturday 14 Nov review |

## 7. What is still needed to close SG1

1. **Push the Week 1 branches** (access expected 2026-11-08), open PRs in stack order, and record the CI run for the merge SHA of each. Then re-run this report's section 2 against **one** merged SHA and fill in the CI column.
2. **Deploy staging** (`docs/delivery/staging.md`) and record section 6 there: `/health` shows `staging`, the committed password fails, the app role cannot create, the web app shows the STAGING banner and deep links load.
3. **AT05 on staging:** fresh checkout, browser login, register, open episode, reload, restart; record it here with the SHA.
4. **Browser screenshots** at 360 px and 1280 px (synthetic data only) into `screenshots/`.
5. Re-run section 2 at a candidate that includes W1-A6 (F8 fix).
6. The reviews in section 6.

**Tracker cells to update by hand** (the developer maintains the workbook): Acceptance sheet AT01–AT04 "Pass (local, `48f6e0e`, 2026-11-07; CI pending)"; AT05 "Blocked: staging not deployed; local fresh-checkout pass at `48f6e0e`".
