# Local setup — verified 2026-11-02

I ran every command below on Windows 11 against a fresh clone of `39059e9`, and every one worked. The
repo's README covers the Docker route (Option A) and the Supabase route (Option B). This file adds a
**Docker-free route on Windows**, which is what this machine used because Docker isn't installed.

## 1. Prerequisites

| Tool | Required version | Source of truth | How it was satisfied here |
|---|---|---|---|
| Git | any | — | 2.54 |
| uv | 0.12.13 (CI pin) | `.github/workflows/ci.yml` | `python -m pip install --user uv==0.12.13` |
| Python | 3.12.14 | `apps/api/.python-version` | fetched automatically by `uv sync` |
| Node | 26.8.1 | `apps/web/.nvmrc` + `package.json` `engines` | portable zip from nodejs.org (the system Node 24.18 doesn't match the pin) |
| PostgreSQL | 16.x (images pin 16.4) | `infra/docker-compose.yml`, CI | Docker, **or** portable EDB binaries 16.4 (below) |

On Windows the user-level uv scripts directory has to be on PATH:
`C:\Users\<you>\AppData\Roaming\Python\Python312\Scripts`.

## 2. Database

### Option A — Docker (README default)
```
cd infra
docker compose up -d db        # Postgres 16.4 on localhost:5433
```

### Option W — portable PostgreSQL without Docker (used for this baseline)
This mirrors the Docker container exactly: superuser `matrisathi_migrator`, database `matrisathi`, port 5433,
listening on localhost only. It needs no admin rights and no Windows service. Delete the folder to remove it.
```
# outside the repo, e.g. C:\Users\<you>\Documents\MCH\_localdev
curl -L -o pg16.zip https://get.enterprisedb.com/postgresql/postgresql-16.4-1-windows-x64-binaries.zip
unzip pg16.zip -d pg16
printf 'matrisathi_migrator_dev_pw' > pw.tmp
pg16/pgsql/bin/initdb.exe -D pgdata -U matrisathi_migrator --pwfile=pw.tmp -A scram-sha-256 -E UTF8 --locale=C
rm pw.tmp
pg16/pgsql/bin/pg_ctl.exe -D pgdata -l pg.log -o "-p 5433 -c listen_addresses=localhost" start
PGPASSWORD=matrisathi_migrator_dev_pw pg16/pgsql/bin/psql.exe -h localhost -p 5433 -U matrisathi_migrator -d postgres -c "CREATE DATABASE matrisathi;"
```
To stop it: `pg16/pgsql/bin/pg_ctl.exe -D pgdata stop`.

> In Git Bash, `pg_ctl start` keeps the terminal attached, because the server inherits the console handles.
> Run it in its own terminal, or check readiness from another one with `pg_isready -h localhost -p 5433`.

The passwords above are the **committed dev-only defaults**. Never use them for any reachable database.

## 3. Environment variables

`apps/api/.env` — create it only if it doesn't exist, and never overwrite one that does:
```
cd apps/api
[ -e .env ] || cp .env.example .env
```
The defaults in `.env.example` work unchanged for Option A and Option W.

| Variable | Required | Local value | Notes |
|---|---|---|---|
| `DATABASE_URL_MIGRATOR` | yes | `...matrisathi_migrator...@localhost:5433/matrisathi` | Schema owner; used only by Alembic |
| `DATABASE_URL_APP` | yes | `...matrisathi_app...@localhost:5433/matrisathi` | Runtime role, created by migration 0002 |
| `MATRISATHI_APP_DB_PASSWORD` | Supabase only | unset → `matrisathi_app_dev_pw` | Read by migration 0002 |
| `JWT_SECRET` | yes | `dev-only-secret-change-me` | **There is no startup guard.** You must set a real value for any deployment. |
| `CORS_ALLOWED_ORIGINS` | yes | `http://localhost:5173` | Comma-separated |
| `COOKIE_SECURE` / `COOKIE_SAMESITE` | yes | `false` / `lax` | Use `true` / `none` together for cross-site staging |
| `SUPABASE_*`, `GITHUB_TOKEN` | no | empty | Not read by the app |

`apps/web/.env` is optional. `VITE_API_BASE` defaults to `http://localhost:8000/api/v1`.

No external credentials are needed to run anything that exists today.

## 4. Install dependencies (lockfiles only; nothing upgraded)
```
cd apps/api && uv sync --frozen          # creates apps/api/.venv with Python 3.12.14
cd apps/web && npm ci                    # with Node 26.8.1 on PATH
```
npm 11.19 prints an `install-scripts` warning for `esbuild`'s postinstall. The build still works, because the
platform binary comes from the optional dependency `@esbuild/win32-x64`.

## 5. Migrate and seed
```
cd apps/api
uv run alembic upgrade head              # 4 revisions → head 67ca239c7fe7; also creates matrisathi_app role
uv run alembic check                     # expect: "No new upgrade operations detected."
uv run python -m app.scripts.seed_dev    # synthetic org/facility + login 'coordinator1' (password printed; dev-only)
```
The seed is idempotent: a second run prints "Already seeded".

## 6. Run
```
# terminal 1
cd apps/api && uv run uvicorn app.main:app --port 8000 --reload
# terminal 2
cd apps/web && npm run dev               # http://localhost:5173
```
Checks:
- `GET http://localhost:8000/health` → `{"status":"ok"}`. This **does not** check the DB.
- Swagger is at `http://localhost:8000/docs`.

## 7. Tests and checks
```
cd apps/api
uv run pytest -q          # 52 passed (~60 s on Windows). Creates/drops its own DB `matrisathi_test` on :5433.
uv run ruff check .
uv run mypy app

cd apps/web
npm run typecheck
npm test                  # 18 passed
npm run build
```
`pytest` needs Postgres running on `localhost:5433` with the migrator superuser, because the conftest connects to
the hard-coded `_ADMIN_URL`. The tests **cannot run against Supabase** as written.

## 8. Troubleshooting (all hit or checked during this baseline)

| Symptom | Cause / fix |
|---|---|
| `uv: command not found` | Add the user Scripts dir to PATH (§1). |
| `connection refused ... 5433` | Postgres isn't running, or it's on 5432. The project expects **5433**. |
| `password authentication failed for user "matrisathi_app"` | Migrations weren't run against this DB, or `MATRISATHI_APP_DB_PASSWORD` differs from the password in `DATABASE_URL_APP`. |
| pytest fails in the `_test_database` fixture | The migrator role must be able to `CREATE DATABASE`. That's a superuser in Docker/Option W; it fails on Supabase. |
| Login works, but every page then says "Your session has ended" | The frontend origin isn't in `CORS_ALLOWED_ORIGINS`, or you're cross-site with `SameSite=lax`. Use `localhost` for both, not `127.0.0.1` for one of them. |
| Login always 401 after typos | A throttle locks the **username** for 15 min after 5 failures. Wait, or delete rows from `login_attempt` in a dev DB. |
| `npm ci` engine warning | Node isn't 26.8.1. Use the pinned version. |
| HTTP 500 with a bad id in the URL | A known defect: malformed UUIDs aren't validated (see the baseline report). |
