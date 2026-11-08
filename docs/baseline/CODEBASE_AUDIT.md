# Codebase audit — baseline 2026-11-02

Audited commit: `39059e9` (`main`, HEAD of `origin/main`), fresh clone, clean working tree.
Everything below was checked against source code and the running system, not just the docs.
Companion documents in this folder: `ARCHITECTURE.md`, `LOCAL_SETUP.md`,
`BASELINE_TEST_REPORT.md`, `IMPLEMENTATION_STATUS.md`.

## 1. Repository overview

| Item | Finding |
|---|---|
| Remote | `https://github.com/matrisathi/jananisaathi`. **Public** repository. |
| Branches | `main` only. No other remote branches. No pull requests, open or closed. |
| History | **8 commits** (not 6 as the 31-Oct execution plan says): 6 commits 29 Sep–2 Oct 2026 by "MatriSathi Dev", 2 commits on 31 Oct 2026 (`fa515a9` web-client idempotency/refresh, `39059e9` status update). |
| Working practice | Every commit went straight to `main`. D03 (branches + PR review) is not in force. |
| Branch protection | Can't verify: the auditing account (`SakshiAwasthi19`) has read-only access (`push: false`), and the protection API returns 404 for that account. |
| CI | GitHub Actions `CI` workflow. 5 runs, all `success`, the latest at `39059e9` (run 41196159598). The first 3 commits predate the remote, so they have no CI. |
| Product name | Code, UI, API title, package names and DB roles all say **MatriSathi**. "JananiSaathi" appears only in the repo name and in `JananiSaathi_Week_by_Week_Execution_Plan.docx`. |

## 2. Directory structure (verified)

```
.claude/settings.json         Claude Code permissions (plan mode; asks before git commit/push/merge/reset)
.github/workflows/ci.yml      backend (Postgres 16.4 service, uv, alembic, ruff, mypy, pytest) + frontend (npm ci, tsc, vitest, build)
CLAUDE.md                     product/clinical boundaries + working rules (authoritative for contributors)
README.md                     setup, session/CSRF design, Supabase + staging notes
infra/docker-compose.yml      local Postgres 16.4-alpine on host port 5433
docs/status.md                project status (updated 31 Oct)
docs/delivery/evidence/SG1/report.md   SG1 evidence written by the previous implementer (30 Sep)
docs/specifications/          spec workbook (v2), stage-gate tracker (status-edited copy), R09/G15 proposed amendment
apps/api/                     FastAPI backend
  app/main.py                 app, CORS, /api/v1 router, /health
  app/core/                   config (pydantic-settings), db (two engines), deps (authn/authz), security (JWT, argon2, refresh tokens)
  app/models/                 SQLAlchemy 2.0 models (13 tables incl. alembic_version)
  app/schemas/                Pydantic request/response models
  app/api/routers/            auth, people, pregnancies, admin
  app/services/               audit_service (independent-transaction audit), idempotency_service (INSERT ... ON CONFLICT)
  app/scripts/seed_dev.py     synthetic org/facility/coordinator seed (idempotent)
  alembic/                    4 migrations (linear chain)
  tests/                      52 pytest tests against real PostgreSQL
apps/web/                     React 18 + Vite 5 + TypeScript 5.6 SPA
  src/api/client.ts           fetch wrapper: cookies, CSRF header, Idempotency-Key retries, single-flight refresh + Web Locks
  src/lib/                    attempts (idempotency keys), age (display)
  src/pages/                  Login, MotherRegister (tabs), FindMother, RegisterNewMother, PregnancyView
  src/state/session.ts        React context for the signed-in staff user
```

There is no shared-types package. The frontend types in `client.ts` are hand-copied from the Pydantic schemas (no codegen). There's no linter for the frontend (no ESLint config).

## 3. Technologies (pinned, verified from lockfiles)

| Layer | Stack |
|---|---|
| Backend runtime | Python 3.12.14 (`.python-version`, `uv.lock`), FastAPI 0.115.0 (→ Starlette 0.38.6), Uvicorn 0.31.0, SQLAlchemy 2.0.35, Alembic 1.13.3, psycopg 3.2.3, Pydantic 2.9.2, PyJWT 2.9.0, pwdlib[argon2] 0.2.1 |
| Backend dev | pytest 8.3.3, httpx 0.27.2, ruff 0.6.9, mypy 1.11.2; uv 0.12.13 (pinned in CI) |
| Frontend | Node 26.8.1 (`.nvmrc`, `engines`), React 18.3.1, Vite 5.4.21, TypeScript 5.6.3 (`strict`), Vitest 2.1.9 |
| Database | PostgreSQL 16.4 (docker-compose and CI service image) |

## 4. Database architecture

These 12 application tables come from 4 Alembic revisions: `c000bd49c621` → `0002_app_role_grants` → `79d282bcc5f3` → `67ca239c7fe7` (head).

- **Tenancy:** `organization`, `facility(organization_id, active)`, `organization_admin(org, staff, revoked_at)`.
- **Staff:** `staff_user(username unique, active)`, `staff_membership(staff, facility, role ∈ ASHA|NURSE|COORDINATOR|DOCTOR, active, revoked_at)`, `refresh_token(hash unique, expires_at, revoked_at, replaced_by_id)`, `login_attempt`.
- **Identity:** `person` (age_precision + exactly-one of DOB / birth_year / reported_age_years, free-text history/allergies, `registering_facility_id` = ownership boundary) and `contact_method(person_id, PHONE, value, verified_at, verified_by)`. The phone is deliberately **not unique**.
- **Care:** `pregnancy_episode(mother_person_id, facility_id [server-derived], dating_estimate, dating_source, status ACTIVE|CLOSED, closed_at)`.
- **Cross-cutting:** `audit_event` (append-only for the runtime role), `idempotency_key(staff, endpoint, key) unique + payload_hash`.

**DB roles.** The migrations run as the owner (`matrisathi_migrator` locally, `postgres` on Supabase). Migration `0002` creates the runtime role `matrisathi_app` with DML on everything except UPDATE/DELETE on `audit_event`. `ALTER DEFAULT PRIVILEGES` grants future tables automatically. I verified this live: the app role gets `InsufficientPrivilege` on UPDATE and DELETE of `audit_event`.

**Verified properties:**
- `alembic upgrade head` works on an empty database.
- `alembic check` reports no drift between the models and the migrations.

**Not present:**
- `version` columns (T002/T003).
- Check constraints for the age-field exclusivity. It's enforced only in Pydantic.
- DB-side defaults for `created_at`.
- Child, caregiver, task, appointment, content, messaging and file tables (all SG2+).

## 5. Authentication and authorization

- **Staff login:** username + argon2 password. A failed login returns the same generic 401 whatever the cause. Throttling is per username (5 failures in 15 minutes) and **not per IP or client**.
- **Session:** the access token is a JWT (HS256, 15 min) in an httpOnly cookie on `/`. The refresh token is opaque, stored as a SHA-256 hash, lasts 14 days, rotates on every use, and is scoped to `/api/v1/auth`. Reuse of a rotated token revokes all of that user's sessions.
- **CSRF:** every mutating route requires `X-MatriSathi-Client: web` (`/auth/refresh` does not, by design). CORS allows only the configured origin, with credentials.
- **Live checks:** each request re-reads `staff_user.active` and the facility membership, so nothing is cached at login.
- **Authorization model:**
  - Access to a record is decided by an active `StaffMembership` at the record's facility.
  - Org-admin authority is a separate grant (`organization_admin`) and gives no clinical access by itself.
  - Denials return **404** (not 403), so they don't confirm the record exists.
  - **Roles are stored but not enforced:** an ASHA, nurse, coordinator and doctor can all do exactly the same things (F004 deferred).

## 6. Existing integrations

None are live. Supabase is supported only as a plain Postgres connection string (the Supabase SDK keys are declared but never read). Render/Vercel staging is documented but not deployed. There's no WhatsApp, voice, object storage, worker, email or SMS. GitHub Actions is the only external service in use.

## 7. Modules and responsibilities

| Module | Responsibility | Notes |
|---|---|---|
| `core/deps.py` | `get_current_staff`, `require_csrf_header`, `require_facility_membership`, `require_active_facility`, `require_org_admin` | The central authorization primitives. Routers call them inline; there is no policy layer. |
| `core/db.py` | Request engine + a separate audit engine | Audit rows commit on their own connection, so a denied request still leaves its audit row. |
| `services/idempotency_service.py` | Atomic claim with `INSERT ... ON CONFLICT DO NOTHING RETURNING` | One transaction with the entity insert. Proven by a real multi-threaded test. |
| `services/audit_service.py` | Writes an `AuditEvent` | Not transactional with the business write (see the critical issues). |
| `routers/auth.py` | login / refresh / logout / me | |
| `routers/people.py` | search (phone exact / name ILIKE, capped at 50), create (idempotent), get, verify contact | |
| `routers/pregnancies.py` | create (idempotent; facility derived from the person), get | There's no list endpoint and no close/update endpoint. |
| `routers/admin.py` | create facility, create staff, grant/revoke membership | There's no API to create an organization or an org-admin grant. |
| `web/src/api/client.ts` | Cookie session, network retry of keyed creates, single-flight refresh + cross-tab Web Locks | Covered by 13 vitest tests. |
| `web/src/pages/*` | Login, find/register mother, episode view | Inline styles, hash routing, no router library, no i18n. |

## 8. Code-quality observations

**Strengths:**
- The code is small, readable and heavily commented with the reasoning behind decisions.
- Server-side ownership derivation is consistent.
- The tests use real PostgreSQL, not mocks.
- Status reporting is honest: the previous implementer corrected their own over-claims in the tracker.

**Weaknesses:**
- There is no input validation beyond types:
  - Empty names and phone numbers are accepted.
  - A negative age is accepted.
  - A date of birth in the year 2999 is accepted.
  - Letters in the phone number are accepted.
  - The phone number is not normalized, and phone search needs an exact match.
- Malformed UUIDs and over-length strings cause **HTTP 500**.
- Authorization checks are repeated in each router rather than centralized, which will scale poorly in SG2+.
- Audit-on-deny is applied inconsistently (`verify_contact` doesn't record denials).

The full issue list is in `ARCHITECTURE.md` §9 and in the baseline report.
