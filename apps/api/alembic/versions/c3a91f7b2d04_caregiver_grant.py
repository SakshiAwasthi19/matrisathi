"""caregiver_grant table (W2-A2, D07 draft; unused until D07 is decided)

Revision ID: c3a91f7b2d04
Revises: b9d0e2a7c3f1
Create Date: 2026-11-07 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core.migration_helpers import NO_DELETE, grant_app_role, revoke_app_role

revision: str = "c3a91f7b2d04"
down_revision: str | None = "b9d0e2a7c3f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCOPES = "'NEXT_ACTION', 'BIRTH_PLAN', 'REMINDERS'"


def upgrade() -> None:
    op.create_table(
        "caregiver_grant",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("subject_person_id", sa.UUID(), nullable=False),
        sa.Column("grantee_person_id", sa.UUID(), nullable=False),
        sa.Column("scopes", postgresql.ARRAY(sa.String(length=32)), nullable=False),
        sa.Column("recorded_by_staff_user_id", sa.UUID(), nullable=False),
        sa.Column("verified_by_staff_user_id", sa.UUID(), nullable=False),
        sa.Column(
            "verification_method",
            sa.Enum(
                "IN_PERSON_DOCUMENT",
                "IN_PERSON_KNOWN_TO_STAFF",
                "IN_PERSON_OTHER",
                name="caregiver_verification_method",
            ),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_staff_user_id", sa.UUID(), nullable=True),
        sa.Column(
            "revoke_reason",
            sa.Enum(
                "REQUESTED_BY_SUBJECT",
                "SAFETY_CONCERN",
                "REPLACED",
                "RECORDED_IN_ERROR",
                name="caregiver_revoke_reason",
            ),
            nullable=True,
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["subject_person_id"], ["person.id"]),
        sa.ForeignKeyConstraint(["grantee_person_id"], ["person.id"]),
        sa.ForeignKeyConstraint(["recorded_by_staff_user_id"], ["staff_user.id"]),
        sa.ForeignKeyConstraint(["verified_by_staff_user_id"], ["staff_user.id"]),
        sa.ForeignKeyConstraint(["revoked_by_staff_user_id"], ["staff_user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("subject_person_id <> grantee_person_id", name="ck_caregiver_grant_not_self"),
        sa.CheckConstraint("cardinality(scopes) > 0", name="ck_caregiver_grant_has_scope"),
        sa.CheckConstraint(f"scopes <@ ARRAY[{_SCOPES}]::varchar[]", name="ck_caregiver_grant_known_scopes"),
        sa.CheckConstraint(
            "(revoked_at IS NULL AND revoked_by_staff_user_id IS NULL AND revoke_reason IS NULL)"
            " OR (revoked_at IS NOT NULL AND revoked_by_staff_user_id IS NOT NULL AND revoke_reason IS NOT NULL)",
            name="ck_caregiver_grant_revocation_complete",
        ),
    )
    op.create_index(
        "ix_caregiver_grant_subject_grantee", "caregiver_grant", ["subject_person_id", "grantee_person_id"]
    )
    # Grants are revoked, never deleted: the app role gets no DELETE.
    grant_app_role("caregiver_grant", NO_DELETE)


def downgrade() -> None:
    revoke_app_role("caregiver_grant")
    op.drop_index("ix_caregiver_grant_subject_grantee", table_name="caregiver_grant")
    op.drop_table("caregiver_grant")
    sa.Enum(name="caregiver_revoke_reason").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="caregiver_verification_method").drop(op.get_bind(), checkfirst=True)
