# D04: Auth, session, tenant, audit and runtime design

**Status:** Proposed. **Decides:** tech lead. **Written:** 2026-11-07 (W1-A3), against `main` at `39059e9`.
**Spec:** M003, T002–T006, G14. **Tests referenced:** `apps/api/tests/`.

This describes what the system does today, with a file reference or test for every claim, then the known gaps, findings from writing this document, the changes proposed for Phase 1 (SG2), and the questions the tech lead needs to answer.

Paths below are relative to `apps/api/` unless they start with `apps/`.

---

## 1. Staff login

| Behaviour | Where | Test |
|---|---|---|
| Username + password login. Passwords hashed with argon2 (`pwdlib` recommended hasher). | `app/core/security.py:10-18` | `test_login_success_sets_cookies` |
| One generic error ("Invalid username or password", 401) for unknown user, wrong password, disabled account and throttling. | `app/api/routers/auth.py:23`, `:100-114` | `test_login_wrong_password_is_generic`, `test_login_unknown_username_is_same_generic_error`, `test_disabled_user_cannot_login` |
| Throttling: 5 failed attempts per **username** in 15 minutes blocks further attempts (still the generic error). | `app/core/config.py:56-57`; `auth.py:73-90` | `test_login_throttled_after_repeated_failures` |
| Every login attempt (success and failure) is audited. | `auth.py:103-110`, `:133-140` | `test_audit.py` (pattern) |

## 2. Sessions, cookies and CSRF

| Behaviour | Where | Test |
|---|---|---|
| Access token: signed JWT (HS256), 15 minutes. | `security.py:21-33`; `config.py:23-25` | `test_access_token_signed_with_wrong_secret_is_rejected`, `test_malformed_access_token_is_rejected` |
| Refresh token: random opaque value (not a JWT), 14 days. Only its SHA-256 hash is stored. | `security.py:36-48`; `config.py:26` | `test_refresh_rotates_token_and_old_one_stops_working` |
| Both tokens are `httpOnly` cookies (unreadable by page JavaScript). The refresh cookie is sent only to `/api/v1/auth`. | `auth.py:43-65` | `test_login_success_sets_cookies` |
| `Secure` and `SameSite` come from config: `COOKIE_SECURE` (default false), `COOKIE_SAMESITE` (default `lax`). Cross-domain staging needs `true` + `none`. | `config.py:30-39` | — |
| Refresh **rotates**: each use issues a new refresh token and revokes the old one. | `auth.py:185-195` | `test_refresh_rotates_token_and_old_one_stops_working` |
| **Reuse detection**: presenting an already-rotated refresh token revokes **all** of that user's live sessions and is audited. | `auth.py:159-176` | `test_refresh_rotates_token_and_old_one_stops_working` (revocation; the audit event is not asserted, see F4) |
| Every request re-checks the user's `active` flag in the database, so disabling a user takes effect at once. | `app/core/deps.py:15-34` | `test_disabled_user_loses_access_mid_session` |
| Logout revokes the presented refresh token and clears both cookies. | `auth.py:202-224` | `test_logout_revokes_refresh_token` |
| CSRF: mutating requests must carry the header `X-MatriSathi-Client: web`. A cross-site form cannot set a custom header, and CORS blocks cross-origin scripts. | `deps.py:37-50`; `config.py:44`; `app/main.py:9-15` | `test_logout_requires_csrf_header` |
| CORS allows only the configured origins, with credentials, for `GET`, `POST`, `DELETE`. | `main.py:9-15`; `config.py:50` | — |

## 3. Database roles

| Behaviour | Where | Test |
|---|---|---|
| Two roles: the **migrator** owns and changes the schema; the **app** role (`matrisathi_app`) runs the API. | `config.py` (`database_url_migrator`, `database_url_app`); `app/core/db.py:9`; `alembic/env.py` | — |
| The running API connects only as the app role. | `db.py:9`, `:19` | — |
| The app role has SELECT/INSERT/UPDATE/DELETE on tables, but only **INSERT/SELECT on `audit_event`** (append-only). | `alembic/versions/0002_app_role_grants.py:47-58` | `test_app_db_role_cannot_update_or_delete_audit_rows` |
| Grants are added **by hand per migration**; there are no default privileges. `idempotency_key` got its grant in `79d282bcc5f3`. | `0002_app_role_grants.py`; `alembic/versions/79d282bcc5f3_*.py:70` | — |
| The app role cannot `TRUNCATE` (tests use the migrator to clean up). | `tests/conftest.py` (`_clean_tables`) | — |
| No test yet proves the app role cannot run DDL (`CREATE`, `ALTER`, `DROP`). | — | Planned in W1-A4 |

## 4. Tenant scoping (organization and facility)

| Behaviour | Where | Test |
|---|---|---|
| Every record access checks **live** facility membership (active, not revoked) on each request; nothing is cached at login. | `deps.py:53-77` | `test_revoked_membership_loses_access_immediately`, `test_revoking_a_membership_through_the_admin_api_removes_access` |
| Denials return **404, not 403**, so a caller cannot learn that a record exists in another facility. | `deps.py:68-77` | `test_staff_at_facility_b_cannot_read_facility_a_episode` |
| An episode's facility is **derived on the server** from the mother's record, never taken from the request. | `app/api/routers/pregnancies.py:79-101` | `test_episode_facility_is_derived_server_side_not_from_request_body` |
| A person's registering facility is **chosen by the caller** from their own memberships and verified on the server. | `people.py:147`, `:178`; `app/schemas/person.py` (`facility_id`) | `test_person_creation_rejected_for_facility_caller_is_not_a_member_of` |
| Search returns only people registered at the caller's facilities; phone is exact match, name is case-insensitive partial match, capped. | `people.py:80-107` | `test_search_finds_only_records_at_callers_own_facility`, `test_search_by_partial_name_scoped_to_facility` |
| A phone number is never an identity: several people can share one; search returns them separately. | `app/models/identity.py` (`ContactMethod`) | `test_two_people_can_share_a_phone_without_being_merged`, `test_search_on_shared_phone_returns_distinct_people_not_merged`, `test_shared_phone_does_not_leak_across_organizations` |
| Organizations are isolated. | — | `test_two_organizations_are_isolated` |
| Organization admin is an **explicit grant**, never inferred from a facility role, and gives **no** record access. | `deps.py:87-103` | `test_org_admin_grant_is_required_not_inferred_from_membership_role`, `test_org_admin_authority_alone_grants_no_clinical_record_access`, `test_org_admin_of_org_a_cannot_administer_org_b` |
| Linking an inaccessible person into an episode is refused. | `pregnancies.py:79-84` | `test_episode_creation_rejected_for_inaccessible_person`, `test_search_result_cannot_be_linked_into_episode_without_access` |
| Idempotent creates: a retried request with the same `Idempotency-Key` returns the original record; a single atomic `INSERT … ON CONFLICT DO NOTHING` claims the key; a replay re-checks current authorization. | `app/services/idempotency_service.py:36-51`; `people.py:125-140` | `test_truly_concurrent_identical_requests_create_exactly_one_person`, `test_replay_re_enforces_current_authorization`, `test_same_key_different_payload_is_rejected` |

## 5. Audit

| Behaviour | Where | Test |
|---|---|---|
| Successful and **denied** actions are recorded with actor, action, entity, outcome and time. | `app/services/audit_service.py:7-38`; `app/models/audit.py:17-36` | `test_create_and_read_each_produce_one_audit_row`, `test_denied_access_writes_a_denied_audit_row` |
| Audit rows are written on a **separate connection** and committed at once, so they survive a rollback of the request. | `audit_service.py:16-24`; `db.py:12-19` | `test_audit_row_survives_rollback_of_the_caller_session` |
| The app role cannot change or delete audit rows. | see section 3 | `test_app_db_role_cannot_update_or_delete_audit_rows` |
| Metadata holds structural facts only (IDs, outcomes), never clinical text, passwords or tokens. Failed logins record the typed username. | `audit.py:22-24`; `auth.py:109` | — (convention; see finding F5) |

## 6. Pinned runtime versions

| Item | Version | Where |
|---|---|---|
| Python | 3.12.14 | `.python-version`; `pyproject.toml` `requires-python = "==3.12.*"` |
| Python dependencies | exact pins (e.g. FastAPI 0.115.0, SQLAlchemy 2.0.35, Alembic 1.13.3, psycopg 3.2.3, PyJWT 2.9.0, pwdlib 0.2.1) | `pyproject.toml`, `uv.lock` |
| uv | 0.12.13 (CI) | `.github/workflows/ci.yml` |
| Node | 26.8.1 | `apps/web/.nvmrc`; `apps/web/package.json` `engines` |
| Web dependencies | exact pins (React 18.3.1, Vite 5.4.21, TypeScript 5.6.3, vitest 2.1.9) | `apps/web/package.json`, `package-lock.json` |
| PostgreSQL | 16.4 (local and CI) | `infra/docker-compose.yml`; `ci.yml` |

---

## 7. Known gaps (already recorded)

1. **No role capabilities.** Roles exist (`ASHA`, `NURSE`, `COORDINATOR`, `DOCTOR`, `app/models/staff.py:12-16`) but no route checks them; every member of a facility can do everything there. Clinician-only actions start in SG2.
2. **No optimistic concurrency.** No `version` columns; there are no update endpoints yet.
3. **Committed defaults** (dev JWT secret `config.py:23`, app-role password `0002_app_role_grants.py:30`, seed password `app/scripts/seed_dev.py`) would work on staging today. W1-A4 makes each fail under `ENV=staging`.
4. **Migrations in the web start command** (README staging steps) give the web process migrator credentials. W1-A4 moves them to a release step.
5. **Phone search is exact match** with no normalisation (`+91…` vs `0…` do not match).
6. **Dev-only `npm audit` advisories** on Vite 5 / esbuild / vitest 2; fixing needs a deliberate upgrade.

## 8. Findings from writing this document (not fixed here)

| # | Finding | Severity (proposed) | Proposed fix |
|---|---|---|---|
| F1 | `POST /auth/login` and `POST /auth/refresh` do not require the CSRF header (`auth.py:88`, `:144`). With `SameSite=None` on cross-domain staging, another site can submit a login form (logging the victim's browser into an attacker's account) or force a token rotation. | Medium on staging; none locally (`lax`) | **Fixed in W1-A4:** both routes now require the header (`test_login_requires_csrf_header`, `test_refresh_requires_csrf_header`). |
| F2 | Throttling is per username only. Anyone can lock a known staff username out for 15 minutes by sending 5 wrong passwords. | Low (pilot scale) | Add a per-client limit alongside, or a shorter lockout; decide with the tech lead. |
| F3 | `Idempotency-Key` is **optional** on create endpoints (`people.py` `Header(default=None)`). The web client always sends it, but the API accepts creates without one. The build plan says every create is idempotent. | Low | Require the header on create endpoints (400 if missing). |
| F4 | Refresh-token reuse detection is tested for revocation, but no test asserts its `refresh_token_reuse_detected` audit event (`auth.py:168-175`). | Low | Extend `test_refresh_rotates_token_and_old_one_stops_working` to assert the DENIED audit row. |
| F5 | The audit model's comment points to `tests/test_audit_durability.py`, which does not exist (it is `tests/test_audit.py`). | Trivial | Fix the comment. |
| F6 | Logout clears the cookies, but a copied access token stays valid until it expires (up to 15 minutes). The live `active` and membership checks still apply. | Low (accepted trade-off of short JWTs) | Accept, or shorten the access-token lifetime. |
| F7 | CORS allows only `GET`, `POST`, `DELETE` (`main.py:13`). SG2 update endpoints using `PATCH`/`PUT` will fail from the browser until it is extended. | None yet | Add `PATCH` with the first update endpoint. |

## 9. Proposed changes for SG2

1. **Role capabilities.** A server-side capability check (for example `require_capability(staff, facility_id, "plan.approve")`) mapping roles to actions, applied per route. Clinician-only actions: date confirmation, plan approval, report review, discharge. Which roles count as clinicians is a question below and for the doctor (M008 Q10).
2. **Optimistic concurrency.** A `version` column on every updatable table; updates send the version they read; a stale version returns 409. Starts with W2-A1.
3. **Default grants for the app role.** `ALTER DEFAULT PRIVILEGES` for the migrator role (or a migration helper), plus a test that the app role can use every table it should and cannot change `audit_event`. Needs approval (database roles).
4. **Fix F1 and F3** before staging is shared with reviewers.

## 10. Questions for the tech lead

1. Are 15-minute access and 14-day refresh tokens right for shared devices and weak connectivity? Alternatives: a shorter refresh lifetime on shared devices, or an idle timeout. ☐ Keep ☐ Change: ______
2. Which roles are clinicians for clinician-only actions? Proposed: `DOCTOR` only, pending the doctor's M008 answers. ☐ Agree ☐ Also: ______
3. Approve fixing F1 (CSRF on login/refresh) and F3 (required `Idempotency-Key`) before staging is shared? ☐ Yes ☐ No
4. Approve default grants (section 9, item 3) for SG2? ☐ Yes ☐ No
5. Accept per-username throttling for the pilot (F2)? ☐ Yes ☐ No
6. Under D15, will you review PRs touching auth, roles, secrets and migrations? ☐ Yes ☐ No

Approved by: ____________ Date: ____________
