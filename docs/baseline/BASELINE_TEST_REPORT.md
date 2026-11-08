# Baseline test report — 2026-11-02

- **Commit:** `39059e9` (fresh clone; no code modified).
- **Machine:** Windows 11, Python 3.12.14, Node 26.8.1, PostgreSQL 16.4 (portable) on :5433.
- **Data:** synthetic only. No test was modified.

## 1. Summary

| Suite | Where | Result |
|---|---|---|
| Backend pytest (52) | local | **52 passed**, 0 failed (58.7 s) |
| Backend ruff | local | clean |
| Backend mypy (32 files) | local | clean |
| Alembic empty-DB upgrade + `alembic check` | local | 4 revisions applied; no drift |
| Frontend `tsc --noEmit` | local | clean |
| Frontend vitest (18) | local | **18 passed** |
| Frontend `vite build` | local | OK (159 kB JS, 51 kB gzip) |
| CI at `39059e9` | GitHub Actions run 41196159598 | **success** (backend: 52 passed, ruff, mypy; frontend: typecheck, 18 tests, build) |
| Live API journey probe (my script, real server + DB) | local | **49 passed, 0 failed**, 18 defect observations |
| Real-browser journey (headless Edge via playwright-core, my script) | local | **19 passed, 0 failed**, no unexpected console errors |
| API restart persistence | local | records created in the browser were still served after the API process was killed and restarted |
| `npm audit` (production deps) | local | 0 vulnerabilities |
| `npm audit` (incl. dev) | local | 8 (2 critical vitest/tinypool, 2 high vite/source-map-js, 4 moderate) — dev tooling only |
| `pip-audit` (locked backend deps) | local | **26 advisories in runtime deps**: PyJWT 2.9.0 (17), Starlette 0.38.6 (7), certifi (1); plus pytest (1, dev). I haven't assessed whether each one is reachable. |

**Not present / not run:**
- **BLOCKED (missing tooling):** frontend lint (no ESLint configured), automated browser smoke in CI, secret scanning, and dependency scanning in CI. T007 requires all four.
- Database-only tests: none separate from pytest. Load tests: none.
- Acceptance tests AT06–AT32: **NOT RUN.** The features don't exist.

## 2. Backend tests by file (all PASS, local and in CI)

| File | # | What it verifies |
|---|---|---|
| `test_auth.py` | 12 | Login cookies; no session / malformed / wrong-secret token → 401; generic errors; disabled user can't log in and loses access mid-session; throttling; logout needs CSRF and revokes the refresh token; refresh rotation + old token dead |
| `test_access_isolation.py` | 4 | Cross-facility read denied; revoked membership loses access immediately; disabled facility blocks registration; two-organization isolation |
| `test_admin_membership.py` | 4 | Org admin creates facility/grants membership; revoke removes access; non-admin denied; org A admin can't act on an org B facility |
| `test_org_admin.py` | 4 | Admin grant not inferred from role; cross-org denied; revoked grant loses authority; admin grant alone gives no clinical access |
| `test_person_pregnancy_authz.py` | 6 | Episode for an inaccessible or nonexistent person rejected; facility derived server-side; register under a non-member facility rejected; idempotent retries for person and episode |
| `test_person_search_and_intake.py` | 11 | Facility-scoped search (phone and partial name); shared phone → distinct people; search result can't be linked without access; contact verification attribution + scoping; age-precision validator; unknown age stores nothing; dating stays null |
| `test_shared_phone.py` | 2 | Two people on one phone not merged; no cross-org leak |
| `test_idempotency_concurrency.py` | 5 | Real two-thread race creates exactly one person; sequential retry; same key + different payload → 409; keys isolated per staff user; replay re-checks authorization |
| `test_audit.py` | 4 | One audit row per create/read; denied access audited; audit survives caller rollback; runtime DB role can't UPDATE/DELETE audit rows |

Frontend: `attempts.test.ts` has 5 tests (idempotency-key reuse and rotation). `client.test.ts` has 13 tests (Idempotency-Key header, network retries, no retry on HTTP error, refresh-and-replay, single-flight refresh, Web Locks, session-ended handling, logout refresh).

## 3. Live end-to-end verification (beyond the existing suites)

**API journeys, all PASS:**
1. Generic login errors and a successful seeded login with httpOnly, SameSite=Lax cookies.
2. Register a mother (CSRF enforced). An idempotent retry returns the same person.
3. Episode created and persisted (ACTIVE, dating UNKNOWN).
4. A second mother on the same phone is a separate person. Phone search returns 2 distinct records.
5. Partial-name search works. A search with no criteria returns 422.
6. Contact verification records who verified it.
7. Second organization (seeded via SQL, because no API exists for it):
   - Its admin creates a facility, a staff user and a membership.
   - Its staff get empty search results and 404 on the org-1 person and episode.
   - Linking an org-1 person into an episode → 404. Registering under an org-1 facility → 404. Verifying an org-1 contact → 404.
   - Revoking membership takes effect on the same live token.
8. Session lifecycle: refresh rotates; replaying an old refresh token → 401 and revokes all sessions; logout needs CSRF; after logout `/me` → 401.
9. Audit:
   - Success and denial rows exist.
   - No patient phone numbers or names appear in audit metadata.
   - The runtime role is blocked from UPDATE and DELETE on `audit_event`.
   - The DB holds exactly one Person row after retries.

**Browser journey, all PASS (headless Edge, 19 checks):**
- Login page, then a bad password, then a successful login.
- Register an approximate-age mother → episode view. The record persists after reload.
- Contact confirmation persists after reload.
- A second mother on the same phone → search shows 2 separate cards → "Select & create episode" opens the correct mother.
- The empty-search and no-results states display.
- An expired access token is renewed transparently. A fully revoked session shows "Your session has ended".
- Staff from another organization find nothing, and the direct episode URL shows "Not found" with no record content.
- Logout works.

**Restart:** I stopped and restarted the API process. Login works and the browser-created records are intact.

## 4. Defects observed (code unchanged, all reproduced)

| # | Observation | Severity (proposed) |
|---|---|---|
| O1 | `GET /people/{bad-uuid}`, `GET /pregnancy-episodes/{bad-uuid}`, `POST /pregnancy-episodes {person_id:"nope"}` and `POST /people {facility_id:"nope"}` → **500** (`ValueError`). The admin path params have the same pattern (from reading the code). | Medium |
| O2 | A phone number longer than 32 chars → **500**, and the server log prints the full SQL parameters, **including the phone value**. Any DB error on person insert would also log the name and medical history. This breaks T006 ("no patient text / phone numbers in ordinary diagnostics"). | **High (privacy)** |
| O3 | Accepted with 201: an empty name and empty phone, `reported_age_years = -5`, DOB `2999-01-01`, episode `dating_estimate = 1900-01-01`, and a phone containing letters. | Medium |
| O4 | After 5 failed logins **by anyone**, the correct password is refused for 15 min. The username-only throttle lets anyone lock out any staff account. | Medium |
| O5 | An org admin can grant **themselves** a facility membership (including DOCTOR), which gives them clinical access. It is audited, but there's no separation of duties. | Medium (needs decision) |
| O6 | An org-2 admin can grant a membership to a staff user belonging to org 1, because `StaffUser` has no organization binding. Identical memberships can be granted twice. | Medium / Low |
| O7 | A second ACTIVE episode can be created for the same mother, and there's no way to list or reopen existing episodes (already flagged in status.md). | Product decision |
| O8 | Name search `%` returns every record in the caller's facilities. LIKE wildcards aren't escaped. This stays within the caller's authorized scope. | Low |
| O9 | `verify_contact` denials aren't audited (0 DENIED rows); every other endpoint audits its denials. | Low |
| O10 | No startup guard rejects the default `JWT_SECRET` or `COOKIE_SECURE=false` outside development, and the `env` setting is never read. | Medium (deployment) |
| O11 | `/health` returns ok without checking the database. | Low |

## 5. Acceptance tests

| AT | Verifies | Tracker says | Baseline result | Where | Notes |
|---|---|---|---|---|---|
| AT01 | Staff login and sessions | Pass | **PASS** (technical) | local + CI + live | Reviewer acceptance missing. Note O4. |
| AT02 | Org/facility isolation | Pass | **PASS** (technical) | local + CI + live | O5/O6 are policy gaps the AT's wording doesn't test. |
| AT03 | Shared phone and reference injection | Pass | **PASS** | local + CI + live + browser | |
| AT04 | Audit integrity | Pass | **PASS with caveats** | local + CI + live | O2 (sensitive data in server logs) conflicts with "no sensitive payloads"; O9. |
| AT05 | Repeatable foundation | **Blocked** | **Technical evidence now complete** | fresh clone + CI | Fresh checkout of `39059e9`, `uv sync --frozen` + `npm ci`, migrations on an empty DB, real UI login/create/read, reload, restart, and CI output tied to the SHA (run 41196159598). The Tester/Tech lead has to accept it; I haven't changed the tracker. |
| AT06–AT10, AT28 | SG2 | Not run | **NOT RUN — not implemented** | — | |
| AT11–AT14 | SG3 | Not run | **NOT RUN — not implemented; blocked by D06** | — | |
| AT15–AT18, AT29 | SG4 | Not run | **NOT RUN — not implemented** | — | |
| AT19–AT23, AT30–AT32 | SG5 | Not run | **NOT RUN — not implemented** | — | AT32 already has a known failure (O2). |
| AT24–AT27 | SG6 | Not run | **NOT RUN** | — | Needs field users, D10, D11. |

**Reviewer acceptance:** none of AT01–AT05 has a named reviewer in the tracker. "Pass" here means the technical evidence passes. It does not mean the gate passes.
