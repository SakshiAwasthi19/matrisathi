# Architecture (as built at `39059e9`)

This describes the system that actually exists. Proposed future components (worker, object storage, WhatsApp
adapter) are listed at the end as **absent**.

## 1. Shape

A modular monolith with two deployables:

```
Browser (React SPA, hash routes)  ──fetch, credentials: include──▶  FastAPI (/api/v1)  ──psycopg──▶  PostgreSQL 16
   localhost:5173                 cookies: access_token (/),          localhost:8000                    :5433
                                  refresh_token (/api/v1/auth)        2 engines, same runtime role:
                                  header: X-MatriSathi-Client         - request session
                                  header: Idempotency-Key (creates)   - audit session (independent commit)
                                                                       Alembic runs as the schema-owner role
```

## 2. Frontend

- React 18 function components, with no router library: `useHashRoute` switches between `#/episodes/<id>` and the find/register screen.
- State is local `useState`. The signed-in staff user lives in a `SessionContext`. There's no data cache library.
- `api/client.ts` is the only backend access point. It:
  - sends the CSRF header on non-GET requests;
  - retries keyed creates on network failure (1 s, then 3 s) with the same `Idempotency-Key`;
  - on a 401, makes one refresh (single-flight per tab, serialized across tabs via the `navigator.locks` lock `matrisathi-refresh`) and replays the request once;
  - calls a session-expired handler when the refresh is refused.
- `lib/attempts.ts` keeps one key per logical create, in memory. A page reload starts a new attempt.
- Screens:
  - Login.
  - Find existing mother: search by phone and/or name; result cards; "Select & create episode"; "Confirm this is their number".
  - Register new mother: facility, name, phone, age precision, history, allergies. Submitting creates the person and then the episode, and retries only the episode step if that fails.
  - Pregnancy episode view: re-fetches the episode and the mother on load.
- Styling: inline styles, English only, no i18n, no PWA/offline.

## 3. Backend

- `main.py` sets up CORS (GET/POST/DELETE; headers Content-Type, CSRF, Idempotency-Key) and mounts four routers under `/api/v1`, plus `/health`.
- Routers hold the business logic directly. There's no separate domain-service layer, except for audit and idempotency.
- Dependencies (`core/deps.py`) handle authentication. Authorization helpers are called inline in each handler.
- Pydantic schemas validate types. The only semantic validator is the age-precision exclusivity check.
- Errors are FastAPI defaults (`{"detail": ...}`). Unhandled exceptions return a plain 500. There's no global handler and no request IDs.

## 4. API

| Method | Path | Auth | CSRF | Idempotent | Audit |
|---|---|---|---|---|---|
| POST | `/auth/login` | — | no | no | success/denied |
| POST | `/auth/refresh` | refresh cookie | no | — | reuse → denied |
| POST | `/auth/logout` | access | yes | — | success |
| GET | `/auth/me` | access | — | — | none |
| GET | `/people?phone=&full_name=` | access | — | — | search (count only) |
| POST | `/people` | access + facility membership | yes | `Idempotency-Key` | success/denied |
| GET | `/people/{id}` | access + membership at registering facility | — | — | read success/denied |
| POST | `/people/{id}/contact/verify` | same | yes | no | success only |
| POST | `/pregnancy-episodes` | access + membership at person's facility | yes | `Idempotency-Key` | success/denied |
| GET | `/pregnancy-episodes/{id}` | access + membership at episode facility | — | — | read success/denied |
| POST | `/organizations/{org}/facilities` | org admin | yes | no | success |
| POST | `/staff` | org admin of body.organization_id | yes | no | success |
| POST | `/facilities/{id}/memberships` | org admin of the facility's org | yes | no | success |
| DELETE | `/facilities/{id}/memberships/{mid}` | same | yes | — | success |

These don't exist yet:
- A list of episodes, or of a person's episodes.
- Any update (PATCH) endpoint.
- Closing an episode.
- Creating an organization or an org admin.
- Listing staff, facilities or memberships.
- Pagination.

## 5. Authentication flow

1. `POST /auth/login`:
   - The throttle counts failed `login_attempt` rows for that username in the last 15 minutes. At 5 or more, the login is refused.
   - Otherwise the argon2 password is verified.
   - On success it sets the cookies: an access JWT (15 min, `sub` = staff id) and a refresh token (opaque, 14 days, only its SHA-256 hash stored).
   - It returns the staff user with their active memberships.
2. Every request: decode the JWT, then load `staff_user`. An inactive user gets 401.
3. `POST /auth/refresh`:
   - Look up the token hash.
   - If the token was already revoked, revoke every live token for that user and audit the reuse.
   - If it's expired, or the user is inactive, return 401.
   - Otherwise issue a new token, link `replaced_by_id`, and revoke the old one.
4. Logout revokes the presented refresh token and clears both cookies.

## 6. Authorization model

- **Tenant boundary.** `Person.registering_facility_id` is set at creation and never accepted from the client afterwards. `PregnancyEpisode.facility_id` is copied from the person. Facilities belong to organizations.
- **Rule.** A staff member can act on a record if they hold an active, unrevoked membership at that record's facility. This is checked live on every request, including on idempotent replays.
- **Org admin.** An `organization_admin` grant lets someone manage facilities, staff and memberships in that org. By itself it gives no access to records.
- **Not enforced:**
  - Role differences (ASHA, nurse, coordinator and doctor are equivalent).
  - Caregiver or patient access.
  - Assignment-level scoping (F004 "assigned records").
  - Facility `active` on reads and searches. It is only checked on creates.
- **Denials** return 404 and leave an audit row with outcome DENIED (except `verify_contact`).

## 7. Data flow — "register new mother"

1. The SPA builds the payload and gets or creates an idempotency key for it.
2. It sends `POST /people` with CSRF + `Idempotency-Key`. The server does all of this in one transaction:
   - claims the key with `INSERT ... ON CONFLICT`;
   - checks membership and that the facility is active;
   - inserts the `person`, then the `contact_method`;
   - attaches the result to the key;
   - commits.
3. After the commit, an audit row is written on the separate audit connection.
4. The SPA sends `POST /pregnancy-episodes` with its own key. The facility is derived from the person, and the same pattern follows.
5. The SPA navigates to `#/episodes/{id}`. The view does `GET` episode, then `GET` person.

Consequence: the audit write is **not atomic** with the business commit. A crash between the two leaves an unaudited success.

## 8. Database schema overview

See `CODEBASE_AUDIT.md` §4. Main relationships:
- organization 1─* facility 1─* staff_membership *─1 staff_user
- organization 1─* organization_admin *─1 staff_user
- facility 1─* person 1─* contact_method
- person 1─* pregnancy_episode *─1 facility

Every table has a UUID primary key and app-side `created_at`/`updated_at`. There are no `version` columns.

## 9. Architectural concerns

1. **Authorization is scattered across handlers.** SG2 brings many entity types and role-restricted transitions (T005/T008), which needs a central policy layer first.
2. **No consistent error contract or input validation layer** (T002 asks for consistent error shapes). This is the cause of the 500s on malformed IDs.
3. **SQLAlchemy logs bound parameters on errors** (`hide_parameters` isn't set), so patient data can end up in logs.
4. **No domain/service layer.** Routers will grow large as SG2 adds plans, tasks and appointments.
5. **No worker, outbox or object storage.** T009 and T012 (SG2/SG3) need them, and they're new infrastructure that needs approval.
6. **Frontend types are copied by hand** from the backend. OpenAPI codegen would remove that drift risk, but it would be a new dev dependency.
7. **Staging design** (README):
   - it shares the team database;
   - the web process runs migrations with migrator credentials;
   - it accepts the committed seed login;
   - Render/Vercel/Supabase hosting conflicts with D09 (India hosting) for any real data.

## 10. Integrations

None live. GitHub Actions only. Supabase is supported only as a Postgres URL. There's no WhatsApp, voice,
storage, SMS or email. All essential flows work today with AI, WhatsApp and GPS absent, because none of them exist.
