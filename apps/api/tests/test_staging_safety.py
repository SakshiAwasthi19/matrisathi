"""Staging safety (W1-A4): committed defaults must not work outside
development, the app DB role cannot change the schema, /health reports the
environment, and login/refresh require the CSRF header."""

import importlib.util
import os
from pathlib import Path

import psycopg
import pytest

from app.core.config import Settings
from app.core.startup_checks import UnsafeConfigurationError, check_runtime_settings
from app.scripts.seed_dev import DEV_PASSWORD, UnsafeSeedError, resolve_seed_password
from tests.conftest import CSRF_HEADERS
from tests.factories import make_facility, make_membership, make_org, make_staff

STRONG_SECRET = "s" * 40
DEFAULT_MIGRATOR_URL = Settings.model_fields["database_url_migrator"].default


def _staging_settings(**overrides) -> Settings:
    values = {
        "env": "staging",
        "jwt_secret": STRONG_SECRET,
        "cookie_secure": True,
        # conftest puts a migrator URL in os.environ for the test database;
        # pin the field to its default so each test controls this itself.
        "database_url_migrator": DEFAULT_MIGRATOR_URL,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


# --- API startup checks ---------------------------------------------------


def test_safe_staging_settings_start():
    check_runtime_settings(_staging_settings(), environ={})


def test_development_skips_the_checks():
    dev = _staging_settings(env="development", jwt_secret="dev-only-secret-change-me", cookie_secure=False)
    check_runtime_settings(dev, environ={"DATABASE_URL_MIGRATOR": "postgresql://x"})


@pytest.mark.parametrize("secret", ["dev-only-secret-change-me", "too-short-secret"])
def test_staging_refuses_default_or_short_jwt_secret(secret):
    with pytest.raises(UnsafeConfigurationError, match="JWT_SECRET") as exc:
        check_runtime_settings(_staging_settings(jwt_secret=secret), environ={})
    assert secret not in str(exc.value)


def test_staging_refuses_migrator_credentials_in_api_environment():
    url = "postgresql+psycopg://matrisathi_migrator:not-shown-anywhere@db.example/x"
    with pytest.raises(UnsafeConfigurationError, match="DATABASE_URL_MIGRATOR") as exc:
        check_runtime_settings(_staging_settings(), environ={"DATABASE_URL_MIGRATOR": url})
    assert "not-shown-anywhere" not in str(exc.value)

    with pytest.raises(UnsafeConfigurationError, match="DATABASE_URL_MIGRATOR") as exc:
        check_runtime_settings(_staging_settings(database_url_migrator=url), environ={})
    assert "not-shown-anywhere" not in str(exc.value)


def test_staging_refuses_insecure_cookies():
    with pytest.raises(UnsafeConfigurationError, match="COOKIE_SECURE"):
        check_runtime_settings(_staging_settings(cookie_secure=False), environ={})


# --- Seed script ---------------------------------------------------------


def test_seed_uses_committed_password_only_in_development():
    assert resolve_seed_password("development", {}) == DEV_PASSWORD


@pytest.mark.parametrize("environ", [{}, {"SEED_PASSWORD": DEV_PASSWORD}, {"SEED_PASSWORD": "short"}])
def test_seed_refuses_missing_committed_or_short_password_on_staging(environ):
    with pytest.raises(UnsafeSeedError):
        resolve_seed_password("staging", environ)


def test_seed_accepts_environment_password_on_staging():
    assert resolve_seed_password("staging", {"SEED_PASSWORD": "a-real-staging-pw-1"}) == "a-real-staging-pw-1"


# --- App-role password in migration 0002 ----------------------------------


def _migration_0002():
    path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0002_app_role_grants.py"
    spec = importlib.util.spec_from_file_location("migration_0002", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_uses_committed_app_password_only_in_development():
    m = _migration_0002()
    assert m.resolve_app_role_password("development", {}) == m.DEV_APP_ROLE_PASSWORD


@pytest.mark.parametrize(
    "environ",
    [{}, {"MATRISATHI_APP_DB_PASSWORD": "matrisathi_app_dev_pw"}, {"MATRISATHI_APP_DB_PASSWORD": "short"}],
)
def test_migration_refuses_missing_committed_or_short_app_password_on_staging(environ):
    m = _migration_0002()
    with pytest.raises(RuntimeError, match="MATRISATHI_APP_DB_PASSWORD"):
        m.resolve_app_role_password("staging", environ)


@pytest.mark.parametrize("bad", ["has'quote-0123456789", "dollar$$sign-0123456789", "space here 0123456789"])
def test_migration_refuses_passwords_that_could_break_the_sql(bad):
    m = _migration_0002()
    with pytest.raises(RuntimeError, match="may contain only"):
        m.resolve_app_role_password("staging", {"MATRISATHI_APP_DB_PASSWORD": bad})


# --- App DB role cannot change the schema ----------------------------------


@pytest.mark.parametrize(
    "statement",
    [
        "CREATE TABLE ddl_probe (id integer)",
        "ALTER TABLE person ADD COLUMN ddl_probe integer",
        "DROP TABLE person",
        "CREATE SCHEMA ddl_probe",
        "CREATE INDEX ddl_probe_idx ON person (full_name)",
    ],
)
def test_app_db_role_cannot_run_ddl(statement):
    app_url = os.environ["DATABASE_URL_APP"].replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(app_url, autocommit=True) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(statement)


# --- /health and CSRF on login/refresh --------------------------------------


def test_health_reports_environment_label(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "env": "development"}


def test_login_requires_csrf_header(client, db_session):
    org = make_org(db_session)
    facility = make_facility(db_session, org)
    staff = make_staff(db_session, username="csrf_user", password="synthetic-password-123")
    make_membership(db_session, staff, facility)

    resp = client.post("/api/v1/auth/login", json={"username": "csrf_user", "password": "synthetic-password-123"})
    assert resp.status_code == 403
    assert "access_token" not in resp.cookies


def test_refresh_requires_csrf_header(client, db_session):
    org = make_org(db_session)
    facility = make_facility(db_session, org)
    staff = make_staff(db_session, username="csrf_user", password="synthetic-password-123")
    make_membership(db_session, staff, facility)
    client.post(
        "/api/v1/auth/login",
        json={"username": "csrf_user", "password": "synthetic-password-123"},
        headers=CSRF_HEADERS,
    )
    old_refresh = client.cookies.get("refresh_token")

    resp = client.post("/api/v1/auth/refresh")
    assert resp.status_code == 403

    # The refused request did not rotate the token: the original still works.
    client.cookies.set("refresh_token", old_refresh)
    resp = client.post("/api/v1/auth/refresh", headers=CSRF_HEADERS)
    assert resp.status_code == 200
