"""app role gets no access to alembic_version (SG1 finding F8)

Revision ID: b2f8c41d9e02
Revises: a13d5e0c7f01
Create Date: 2026-11-07 00:00:00.000000

Migration 0002 granted the restricted app role SELECT/INSERT/UPDATE/DELETE
on "all tables", which at that moment included alembic_version. The running
API never reads or writes that table; only the migrator does. With write
access, a compromised API process could falsify the recorded schema version
and make later migrations skip or repeat steps. This revokes every
privilege the app role holds on it.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b2f8c41d9e02"
down_revision: str | None = "a13d5e0c7f01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "matrisathi_app"


def upgrade() -> None:
    op.execute(f"REVOKE ALL PRIVILEGES ON TABLE alembic_version FROM {APP_ROLE};")


def downgrade() -> None:
    # Restores exactly what 0002 had granted.
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE alembic_version TO {APP_ROLE};")
