# MatriSathi

An independent maternal & child health companion. See `CLAUDE.md` for
product scope and boundaries, and `docs/specifications/` for the approved
specification and its proposed amendments.

This is the first implementation slice only: staff login, registering a
synthetic mother, creating a pregnancy episode, and viewing the persisted
record. See `docs/status.md` for what's built and what's next.

## Prerequisites (pinned versions)

- Docker (for local Postgres) — any recent version with Compose v2
- Python **3.12.14**, managed via [`uv`](https://docs.astral.sh/uv/) (the
  backend pins this exactly in `apps/api/.python-version`; `uv` will fetch
  it automatically if not already installed)
- Node **26.8.1** (pinned in `apps/web/.nvmrc`)

## 1. Database — pick one

**Option A — local Docker Postgres** (default, solo/offline work):

```
cd infra
docker compose up -d db
```

Waits for a healthy container on `localhost:5433` (not 5432, to avoid
clashing with any other local Postgres). Your data is yours alone.

**Option B — shared team Supabase project** (everyone's local backend
points at the same database): see "Working with a shared team database"
below. One person sets the project up once; after that, teammates just
fill in their own `.env`.

## 2. Backend (one terminal)

```
cd apps/api
cp .env.example .env          # fill in Option A or Option B — see the file's comments
uv sync                       # installs pinned deps from uv.lock into apps/api/.venv
uv run alembic upgrade head   # creates schema AND the restricted app DB role
uv run python -m app.scripts.seed_dev   # creates one synthetic org/facility/coordinator
uv run uvicorn app.main:app --port 8000 --reload
```

The seed script prints a synthetic login (`coordinator1` / a generated
password) to the terminal — that's what you log in with in step 3.

## 3. Frontend (a second, separate terminal)

```
cd apps/web
npm install
npm run dev
```

Open `http://localhost:5173`.

## Verification commands

Run from `apps/api` (with `uv sync` already done):

```
uv run pytest -q          # 52 tests: auth, access isolation, org-admin,
                           # person/pregnancy authorization, shared-phone
                           # privacy, person search, contact verification,
                           # idempotency concurrency, and audit
                           # durability/DB-role enforcement
uv run ruff check .
uv run mypy app
```

Run from `apps/web`:

```
npm run typecheck          # tsc --noEmit
npm test                   # vitest: API client retry/idempotency/refresh
npm run build              # typecheck + production bundle
```

CI configuration exists at `.github/workflows/ci.yml` but does not run
anywhere yet — this repository has no git remote configured.

## What this slice deliberately does not include

No WhatsApp, no Child/Caregiver/CareTask/content/messaging tables (modeled
in the design doc, not migrated — kept provisional), no admin UI for
creating organizations/facilities (done via the seed script or directly in
tests for now). See `docs/status.md`.

## Session, tokens, and CSRF

- **Storage**: both the access token (JWT, 15 min) and refresh token
  (opaque, hashed at rest, 14 days, rotated on every use) ride as
  `httpOnly` cookies — never `localStorage`, never a JS-readable cookie.
  Page JavaScript cannot read either token, which is the main defense
  against token theft via XSS.
- **`SameSite=Lax`**, plus `Secure` in any real deployment
  (`COOKIE_SECURE=true`, currently `false` for local HTTP-only dev).
- **CSRF**: because auth is cookie-based, a browser attaches those cookies
  to same-origin *and* certain cross-site requests automatically. Every
  mutating request (`POST`) must carry an `X-MatriSathi-Client: web`
  header (`app/core/deps.py::require_csrf_header`). A classic cross-site
  form submission can't set a custom header; a cross-origin script
  attempting to via `fetch()` is blocked by CORS before the request is
  even sent, since the API only allows the configured frontend origin
  with credentials (`app/main.py`).
- **Revocation**: disabling a `StaffUser` takes effect on the very next
  request, not at token expiry — `get_current_staff` re-checks `active`
  against the database every time, it isn't decided purely from the JWT.
  Refresh-token reuse (replaying an already-rotated-out token) revokes
  every live session for that user, not just the one token.

## Working with a shared team database (Supabase)

For a team, everyone running their own local Docker Postgres means nobody
sees the same data — fine for solo work, awkward for reviewing each
other's changes. A shared Supabase project fixes that: one Postgres
database, everyone's local API instance (still running on their own
machine) points at it.

**One-time setup** (whoever creates the project):
1. Create a Supabase project. Note the project's database password you set
   at creation — that's the `postgres` superuser password.
2. In `apps/api/.env`, set `DATABASE_URL_MIGRATOR` to that project's
   **direct** connection (port 5432, not the 6543 pooler — migrations run
   DDL that the pooler doesn't reliably support) as the `postgres` user.
3. Pick a password for the app role and set `DATABASE_URL_APP` to
   `matrisathi_app` at the same host, with that password.
4. Run `uv run alembic upgrade head` once. This creates the schema *and*
   the restricted `matrisathi_app` role automatically
   (`alembic/versions/0002_app_role_grants.py`) — no manual SQL needed.
5. Share the resulting connection details with the team through a secure
   channel (password manager, not Slack/email/chat) — see `.env.example`
   for exactly which values are needed.

**Everyone else**: fill in the same Option B values in your own
`apps/api/.env` (never commit it — it's gitignored) and skip straight to
`uv run uvicorn ...`; the schema's already there.

**Know before you share a database**: everyone's synthetic test data is
now visible to everyone else. `seed_dev.py` is idempotent (safe to run
more than once), but anything you create by hand through the UI (test
mothers, episodes) is visible to the whole team, not just you — keep it
synthetic, as always, and expect to see teammates' test records too.

## Git and collaboration

Remote: `https://github.com/matrisathi/jananisaathi`, branch `main`. The
proposed approach (matches the project's stage-gate tracker, decision
D03): task branches, pull-request review, and human approval for every
commit/push — nobody pushes straight to `main`. Granting a new
collaborator access is a GitHub-side step (repo Settings -> Collaborators)
separate from anything in this file.

## Deploying a staging environment

A bounded, synthetic-data-only staging deployment for people who need to
see the app without running it locally (e.g. a reviewer who isn't a
developer) — not a production deployment, and not a substitute for the
actual hosting/compliance decision (tracker D09) that real patient data
would require. Two services, each its own manual sign-up — I can't create
accounts or click through web dashboards, so these steps are for you:

**Backend (e.g. Render — any host that runs a long-lived ASGI process
works; Vercel itself does not fit this app's architecture):**
1. New Web Service, pointed at `matrisathi/jananisaathi`, root directory
   `apps/api`.
2. Build command: `pip install uv && uv sync --frozen`
   Start command: `uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   (Running migrations on every boot is harmless — Alembic no-ops once
   already at head — and keeps this simple for a small staging app.)
3. Environment variables (set in the host's dashboard, never committed):
   `DATABASE_URL_MIGRATOR` / `DATABASE_URL_APP` (the same shared Supabase
   project — no need for a separate database for synthetic-only staging
   data), a **new, real** `JWT_SECRET` (not the dev placeholder),
   `COOKIE_SECURE=true`, `COOKIE_SAMESITE=none` (frontend and backend will
   be on different domains — see `app/core/config.py` for why both of
   these have to change together), and `CORS_ALLOWED_ORIGINS` (added after
   step below, once the Vercel URL is known).

**Frontend (Vercel):**
1. Import `matrisathi/jananisaathi`, root directory `apps/web`. Vite is
   auto-detected.
2. Environment variable `VITE_API_BASE` = `<backend URL from above>/api/v1`.
   Vite bakes this in at **build** time, not read at runtime — set it
   before the first deploy, or trigger a redeploy after adding it.

**Then**: go back to the backend host and set `CORS_ALLOWED_ORIGINS` to
the actual `*.vercel.app` URL Vercel assigned, and restart the backend
(it's read once at process startup).

**Label it as staging everywhere it's visible** — the login screen, any
shared link — so nobody mistakes it for a production system. It still
holds only synthetic data; nothing about this setup changes that.

## Known, low-severity dev-only advisory

`npm audit` flags an esbuild dev-server advisory
([GHSA-67mh-4wv8-2f99](https://github.com/advisories/GHSA-67mh-4wv8-2f99))
that Vite 5.x cannot avoid without a breaking major-version jump to Vite 6+.
It only affects the local Vite **dev server** (a malicious site could probe
it while you're running `npm run dev`), not the production build. Left as
Vite 5.4.21 for this slice; revisit alongside a deliberate Vite 6 upgrade
later rather than as an incidental bump here.
