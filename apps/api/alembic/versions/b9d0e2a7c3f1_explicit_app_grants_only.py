"""new tables get only explicitly granted app-role rights

Revision ID: b9d0e2a7c3f1
Revises: b2f8c41d9e02
Create Date: 2026-11-07 00:00:00.000000

Migration 79d282bcc5f3 set ALTER DEFAULT PRIVILEGES so every table the
migrating role creates is automatically readable, writable and deletable by
the app role. Decided 2026-11-07 (Phase 1 plan section 5): app-role rights
are granted explicitly per table (app.core.migration_helpers.grant_app_role)
and checked by tests/test_db_grants.py, so a history table can be created
without DELETE and nothing is granted by accident. This removes the default.
Existing tables keep their current grants; no table created after
79d282bcc5f3 depended on the default.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b9d0e2a7c3f1"
down_revision: str | None = "b2f8c41d9e02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Same CURRENT_USER targeting as 79d282bcc5f3 (matrisathi_migrator locally,
# postgres on Supabase).
_ALTER_DEFAULTS = """
    DO $$
    BEGIN
        EXECUTE format(
            'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public '
            '{action} SELECT, INSERT, UPDATE, DELETE ON TABLES {direction} matrisathi_app',
            current_user
        );
    END
    $$;
"""


def upgrade() -> None:
    op.execute(_ALTER_DEFAULTS.format(action="REVOKE", direction="FROM"))


def downgrade() -> None:
    op.execute(_ALTER_DEFAULTS.format(action="GRANT", direction="TO"))
