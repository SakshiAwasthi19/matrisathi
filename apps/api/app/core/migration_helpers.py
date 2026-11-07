"""Helpers for Alembic migrations.

Every migration that creates a table calls `grant_app_role` explicitly
(decided 2026-11-07, Phase 1 plan section 5). Nothing is granted
implicitly: migration b9d0e2a7c3f1 removed the ALTER DEFAULT PRIVILEGES
that 79d282bcc5f3 had set. `tests/test_db_grants.py` checks the app role's
rights on every table, so a forgotten or excessive grant fails the build.
"""

from alembic import op

APP_ROLE = "matrisathi_app"

READ_WRITE = ("SELECT", "INSERT", "UPDATE", "DELETE")
# History-keeping tables: rows are updated (e.g. revoked) but never deleted.
NO_DELETE = ("SELECT", "INSERT", "UPDATE")
APPEND_ONLY = ("SELECT", "INSERT")


def grant_app_role(table: str, privileges: tuple[str, ...] = READ_WRITE) -> None:
    allowed = {"SELECT", "INSERT", "UPDATE", "DELETE"}
    if not privileges or not set(privileges) <= allowed:
        raise ValueError(f"privileges must be a non-empty subset of {sorted(allowed)}")
    if not table.replace("_", "").isalnum():
        raise ValueError("table must be a plain identifier")
    op.execute(f"GRANT {', '.join(privileges)} ON TABLE {table} TO {APP_ROLE};")


def revoke_app_role(table: str) -> None:
    if not table.replace("_", "").isalnum():
        raise ValueError("table must be a plain identifier")
    op.execute(f"REVOKE ALL PRIVILEGES ON TABLE {table} FROM {APP_ROLE};")
