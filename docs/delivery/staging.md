# Staging checklist (synthetic data only)

A staging deployment so reviewers can use the app without running it locally. **Synthetic data only.** It is not production, and it makes no hosting or compliance claim (D09, G17).

Claude cannot create accounts or click through dashboards. The developer follows these steps. Settings are listed **by name only**; values never go in this file, in git, in chat or in screenshots.

Layout: a **separate** Supabase project (never the shared team database), a Render web service for the API, and Vercel for the web app (section 5, completed in W1-B2).

---

## 1. Create the staging database (Supabase)

1. Create a **new** Supabase project, for example `matrisathi-staging`. Do not reuse the shared team project.
   - Region: Mumbai (`ap-south-1`) is the proposed default. This is a preference, not a legal hosting decision (D09).
   - Save the database password you set. That is the `postgres` (migrator) password. Keep it in a password manager.
   - Free-tier notes: an organization gets two free projects (team + staging uses both); free projects pause after about a week without activity and must be resumed in the dashboard.
2. Project Settings → Database → Connection string. Use the **session-mode pooler** (port 5432, host `aws-0-<region>.pooler.supabase.com`). Not the direct connection (IPv6-only), and not the transaction pooler on 6543 (migrations fail there).
   - Migrator URL shape: `postgresql+psycopg://postgres.<project-ref>:<postgres-password>@aws-0-<region>.pooler.supabase.com:5432/postgres`
   - App URL shape: `postgresql+psycopg://matrisathi_app.<project-ref>:<app-password>@aws-0-<region>.pooler.supabase.com:5432/postgres`
3. Storage → **New bucket** named `matrisathi-files`. Leave **Public bucket off** (private). Add no policies: the API reaches it only with the service-role key, server side, and serves files itself after checking the user's facility.
4. Project Settings → API: copy the project URL and the **service_role** key into the password manager. The service-role key bypasses Supabase's access rules for this project, so it goes only into the Render API service (section 4), never into the web app or Vercel.
5. Generate the **app-role password** (letters, digits and `_ . ~ -` only, at least 16 characters; migration `0002` refuses anything else outside development):
   ```
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

## 2. Run migrations (release step, from your machine)

Migrations are a **separate release step**. They never run inside the web service, and the web service never holds migrator credentials (the API refuses to start if `DATABASE_URL_MIGRATOR` is set).

Run this from `apps/api` before the first deploy and before any deploy that adds a migration. Set the values **in this terminal only**, never in a file.

PowerShell:
```powershell
cd apps/api
$env:ENV = "staging"
$env:DATABASE_URL_MIGRATOR = "<staging migrator URL>"
$env:MATRISATHI_APP_DB_PASSWORD = "<app-role password>"   # needed for the first run
uv run alembic upgrade head
Remove-Item Env:DATABASE_URL_MIGRATOR, Env:MATRISATHI_APP_DB_PASSWORD, Env:ENV
```

Bash:
```bash
cd apps/api
ENV=staging DATABASE_URL_MIGRATOR='<staging migrator URL>' MATRISATHI_APP_DB_PASSWORD='<app-role password>' \
  uv run alembic upgrade head
```

The first run creates the schema and the restricted `matrisathi_app` role with your app-role password. With `ENV=staging`, a missing or committed app-role password stops the migration.

Shell values override `apps/api/.env`, so a local `.env` pointing at the team database is not used for these settings. Check the migrator URL is the staging one before pressing Enter.

## 3. Seed one synthetic login

```powershell
cd apps/api
$env:ENV = "staging"
$env:DATABASE_URL_APP = "<staging app URL>"
$env:SEED_PASSWORD = "<a new password, at least 12 characters>"
uv run python -m app.scripts.seed_dev
Remove-Item Env:DATABASE_URL_APP, Env:SEED_PASSWORD, Env:ENV
```

This creates the synthetic organization, facility and `coordinator1`. With `ENV=staging` the committed dev password is refused and the password is never printed. Keep it in the password manager; share it with reviewers through it, not chat.

## 4. Deploy the API (Render)

1. New → Web Service → repository `matrisathi/jananisaathi`, branch `main`, root directory `apps/api`.
2. Build command: `pip install uv && uv sync --frozen`
3. Start command: `uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT` (no migration step).
4. Health check path: `/health`.
5. Environment variables (names only):

   | Name | Value |
   |---|---|
   | `ENV` | `staging` |
   | `DATABASE_URL_APP` | staging **app** URL (section 1) |
   | `JWT_SECRET` | new value, at least 32 characters: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
   | `COOKIE_SECURE` | `true` |
   | `COOKIE_SAMESITE` | `none` (API and web app are on different domains) |
   | `CORS_ALLOWED_ORIGINS` | the Vercel URL, set after section 5 |
   | `FILE_STORE_BACKEND` | `supabase` (the API refuses to start on staging with anything else) |
   | `SUPABASE_URL` | the staging project URL (section 1) |
   | `SUPABASE_SERVICE_ROLE_KEY` | the staging project's service_role key (section 1) |
   | `SUPABASE_STORAGE_BUCKET` | `matrisathi-files` |

   **Do not set:** `DATABASE_URL_MIGRATOR` (the API refuses to start), `MATRISATHI_APP_DB_PASSWORD`, `SEED_PASSWORD`, `GITHUB_TOKEN`, `SUPABASE_ANON_KEY`.
6. Free-tier note: free Render services sleep after about 15 minutes idle; the first request then takes up to a minute. Open `/health` a minute before a demo.

If the deploy log shows `Refusing to start with ENV='staging': …`, it names the setting to fix (never its value).

## 5. Deploy the web app (Vercel)

1. Add New → Project → import `matrisathi/jananisaathi`. Root directory: `apps/web`. Framework preset: Vite (detected). Build command `npm run build`, output directory `dist` (the defaults).
2. Node version: Project Settings → Build and Deployment → Node.js Version. Pick the highest Vercel offers that is not above the pinned `26.8.1` (`apps/web/.nvmrc`), and note which one in `progress.md` if it differs.
3. Environment variables (names only; set for **Production** of this staging project, since Vercel calls every main-branch deploy "Production"):

   | Name | Value |
   |---|---|
   | `VITE_API_BASE` | `<Render URL>/api/v1` |
   | `VITE_ENV_LABEL` | `staging` (shows the STAGING banner on every page; only `production` hides it) |

   Vite reads both at **build** time. Redeploy after changing either.
4. Deploy. `apps/web/vercel.json` already sends every path to `index.html`, so links such as `/episodes/<id>` open directly, and adds basic security headers.
5. Back on Render, set `CORS_ALLOWED_ORIGINS` to the exact Vercel URL (`https://<project>.vercel.app`, no trailing slash) and redeploy the API. Cookies work across the two domains because the API sends them `Secure` + `SameSite=None` (section 4).
6. Do not add a custom domain or share the URL outside the review group until section 6 passes.

## 6. Verify (record results in `progress.md`, W1-A4 and W1-B2 rows)

1. **Environment label.** Open `<Render URL>/health`. Expect `{"status":"ok","env":"staging"}`.
2. **Committed dev password fails.**
   ```
   curl -i -X POST <Render URL>/api/v1/auth/login -H "Content-Type: application/json" -H "X-MatriSathi-Client: web" -d "{\"username\":\"coordinator1\",\"password\":\"synthetic-dev-password-123\"}"
   ```
   Expect `401`. (Your `SEED_PASSWORD` should return `200`.)
3. **App role cannot change the schema.** In the Supabase SQL editor for the staging project:
   ```sql
   SELECT has_schema_privilege('matrisathi_app', 'public', 'CREATE') AS can_create_in_public,
          has_database_privilege('matrisathi_app', current_database(), 'CREATE') AS can_create_schema;
   SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tableowner = 'matrisathi_app';
   ```
   Expect `false`, `false`, and no rows. If either is `true` or any row appears, **stop, do not share staging**, and report it: fixing it is a database-role change that needs approval.
4. **Web app.** Open the Vercel URL: the purple **STAGING** banner shows on the sign-in page. Sign in with your `SEED_PASSWORD`, register an invented mother, then reload `/episodes/<id>` directly: the record loads (deep link works) and the banner is still there.
5. **Synthetic data only.** Every record entered on staging is invented. No real names or phone numbers, including in screenshots.

## What is enforced in code

| Rule | Where | Test |
|---|---|---|
| API refuses to start outside development with the default/short `JWT_SECRET`, migrator credentials present, or `COOKIE_SECURE=false` | `apps/api/app/core/startup_checks.py` | `tests/test_staging_safety.py` |
| Migration refuses a missing/default/short/unsafe app-role password outside development | `apps/api/alembic/versions/0002_app_role_grants.py` | `tests/test_staging_safety.py` |
| Seed refuses the committed password outside development and never prints it | `apps/api/app/scripts/seed_dev.py` | `tests/test_staging_safety.py` |
| App role cannot run DDL | database grants | `test_app_db_role_cannot_run_ddl` |
| `/health` reports the environment | `apps/api/app/main.py` | `test_health_reports_environment_label` |
| Login and refresh require the CSRF header | `apps/api/app/api/routers/auth.py` | `test_login_requires_csrf_header`, `test_refresh_requires_csrf_header` |

## Duplicate active episodes (migration `a13d5e0c7f01`)

From W1-A5 (D13) a mother can have at most one ACTIVE pregnancy episode. If a database already holds a mother with more than one, the migration stops with `… mother(s) have more than one ACTIVE pregnancy episode … No data was changed.` A brand-new staging database never hits this.

For **synthetic** development or team data only, as the migrator role:

```sql
-- 1. How many mothers are affected
SELECT mother_person_id, count(*) AS active_episodes
FROM pregnancy_episode WHERE status = 'ACTIVE'
GROUP BY mother_person_id HAVING count(*) > 1;

-- 2. Keep each mother's newest ACTIVE episode; close the older ones
UPDATE pregnancy_episode AS e
SET status = 'CLOSED', closed_at = now()
WHERE e.status = 'ACTIVE'
  AND EXISTS (
    SELECT 1 FROM pregnancy_episode AS newer
    WHERE newer.mother_person_id = e.mother_person_id
      AND newer.status = 'ACTIVE'
      AND newer.created_at > e.created_at
  );
```

Then run `uv run alembic upgrade head` again. Never run step 2 on real patient data: closing an episode there is a clinical-record decision for a person, not a script.
