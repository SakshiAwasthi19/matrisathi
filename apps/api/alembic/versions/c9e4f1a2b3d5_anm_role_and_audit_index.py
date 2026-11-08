"""ANM staff role (F004) and an index for the organisation audit view (F037)

Revision ID: c9e4f1a2b3d5
Revises: a8b3d5e1f407
Create Date: 2026-11-08 00:00:00.000000

Adds 'ANM' to the staff_role enum. Postgres cannot drop an enum value, so the
downgrade rebuilds the type without it, and refuses (changing nothing) if any
membership still uses ANM.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c9e4f1a2b3d5"
down_revision: str | None = "a8b3d5e1f407"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX = "ix_audit_event_actor_occurred"


def upgrade() -> None:
    op.execute("ALTER TYPE staff_role ADD VALUE IF NOT EXISTS 'ANM' BEFORE 'NURSE'")
    op.create_index(INDEX, "audit_event", ["actor_staff_user_id", "occurred_at"])


def downgrade() -> None:
    op.drop_index(INDEX, table_name="audit_event")
    in_use = op.get_bind().execute(sa.text("SELECT count(*) FROM staff_membership WHERE role::text = 'ANM'")).scalar_one()
    if in_use:
        raise RuntimeError(
            f"{in_use} membership(s) use the ANM role, so it cannot be removed. No data was changed. "
            "Change those memberships to another role first."
        )
    op.execute("ALTER TYPE staff_role RENAME TO staff_role_old")
    op.execute("CREATE TYPE staff_role AS ENUM ('ASHA', 'NURSE', 'COORDINATOR', 'DOCTOR')")
    op.execute("ALTER TABLE staff_membership ALTER COLUMN role TYPE staff_role USING role::text::staff_role")
    op.execute("DROP TYPE staff_role_old")
