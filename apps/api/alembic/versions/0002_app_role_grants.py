"""restricted application db role, and audit_event append-only grant

Revision ID: 0002_app_role_grants
Revises: c000bd49c621
Create Date: 2026-09-28 00:00:00.000000

Creates a login role dedicated to the running application (matrisathi_app),
distinct from the migration-owner role that applies schema changes. The app
role gets ordinary read/write on everything except audit_event, where it
gets INSERT and SELECT only — no UPDATE, no DELETE. That makes "audit is
append-only" a database-enforced fact, not just an application convention:
even a compromised or buggy application process cannot alter or erase an
audit row, because the role it connects as is not permitted to.
"""

import os
import re
from collections.abc import Mapping

from alembic import op

revision = "0002_app_role_grants"
down_revision = "c000bd49c621"
branch_labels = None
depends_on = None

APP_ROLE = "matrisathi_app"
# Overridable so a shared, internet-reachable database (e.g. Supabase) isn't
# left with the same password that's sitting in this file in git history.
# Local Docker Postgres isn't reachable from outside the machine, so the
# default here is fine for that case unchanged.
DEV_APP_ROLE_PASSWORD = "matrisathi_app_dev_pw"  # noqa: S105
MIN_APP_ROLE_PASSWORD_LENGTH = 16
# The password is interpolated into SQL below (inside '...' and a $$ block),
# so only characters that cannot end either quoting are allowed. This also
# keeps it safe to paste into a connection URL without percent-encoding.
_SAFE_PASSWORD = re.compile(r"^[A-Za-z0-9_.~-]+$")


def resolve_app_role_password(env: str, environ: Mapping[str, str]) -> str:
    """Development may use the committed default. Anywhere else,
    MATRISATHI_APP_DB_PASSWORD must be set to a non-default value."""
    value = environ.get("MATRISATHI_APP_DB_PASSWORD") or ""
    if env.strip().lower() != "development":
        if value == DEV_APP_ROLE_PASSWORD or len(value) < MIN_APP_ROLE_PASSWORD_LENGTH:
            raise RuntimeError(
                f"Refusing to migrate with ENV={env.strip()!r}: set MATRISATHI_APP_DB_PASSWORD "
                f"(at least {MIN_APP_ROLE_PASSWORD_LENGTH} characters, not the committed dev password)"
            )
    password = value or DEV_APP_ROLE_PASSWORD
    if not _SAFE_PASSWORD.match(password):
        raise RuntimeError(
            "MATRISATHI_APP_DB_PASSWORD may contain only letters, digits and _ . ~ -"
        )
    return password


def upgrade() -> None:
    from app.core.config import settings

    app_role_password = resolve_app_role_password(settings.env, os.environ)
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                CREATE ROLE {APP_ROLE} LOGIN PASSWORD '{app_role_password}';
            ELSE
                ALTER ROLE {APP_ROLE} LOGIN PASSWORD '{app_role_password}';
            END IF;
        END
        $$;
        """
    )
    op.execute(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE};")
    op.execute(f"GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE};")
    op.execute(
        f"""
        GRANT SELECT, INSERT, UPDATE, DELETE
        ON ALL TABLES IN SCHEMA public
        TO {APP_ROLE};
        """
    )
    # Narrow audit_event back down to append-only: revoke the UPDATE/DELETE
    # just granted above, leaving INSERT + SELECT.
    op.execute(f"REVOKE UPDATE, DELETE ON audit_event FROM {APP_ROLE};")


def downgrade() -> None:
    op.execute(f"REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM {APP_ROLE};")
    op.execute(f"REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM {APP_ROLE};")
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {APP_ROLE};")
    op.execute(f"DROP ROLE IF EXISTS {APP_ROLE};")
