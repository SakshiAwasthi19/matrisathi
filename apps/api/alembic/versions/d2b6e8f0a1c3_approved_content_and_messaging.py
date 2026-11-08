"""Approved urgent-help wording (D05) and WhatsApp messaging (SG3)

Revision ID: d2b6e8f0a1c3
Revises: c9e4f1a2b3d5
Create Date: 2026-11-08 12:00:00.000000

Adds urgent_help_content, messaging_channel, message_template,
contact_preference, outbox_message, inbound_event, inbox_item and
inbound_media. Content tables (urgent help, message templates, channels) are
read-only for the app role: they are loaded by script from approved
material. Messaging records are never deleted by the app.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

from app.core.migration_helpers import APPEND_ONLY, NO_DELETE, grant_app_role

revision: str = "d2b6e8f0a1c3"
down_revision: str | None = "c9e4f1a2b3d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

READ_ONLY = ("SELECT",)

ENUMS: dict[str, tuple[str, ...]] = {
    "message_purpose": ("APPOINTMENT_REMINDER", "FOLLOW_UP", "GENERAL"),
    "detail_level": ("MINIMAL", "STANDARD"),
    "outbox_status": ("QUEUED", "SENDING", "SUBMITTED", "DELIVERED", "READ", "FAILED", "UNKNOWN", "BLOCKED"),
    "outbox_kind": ("TEMPLATE", "TEXT"),
    "inbox_kind": ("TEXT", "VOICE", "IMAGE", "OTHER"),
    "media_state": ("NONE", "PENDING", "STORED", "REJECTED", "FAILED"),
    "inbox_status": ("OPEN", "CLOSED"),
    "inbox_outcome": ("RESPONDED", "CALLED", "NO_ACTION_NEEDED", "NOT_FOR_US", "OTHER"),
    "identity_check": ("CALLED_BACK", "ASKED_IDENTIFYING_DETAILS", "IN_PERSON"),
    "opt_out_source": ("STAFF", "INBOUND_KEYWORD"),
}

MEDIA_TYPES = ("image/jpeg", "image/png", "audio/ogg", "audio/mpeg", "audio/mp4", "audio/amr")


def _enum(name: str) -> pg.ENUM:
    if name == "template_status":
        return pg.ENUM(name=name, create_type=False)
    return pg.ENUM(*ENUMS[name], name=name, create_type=False)


def _col(name: str, target: str, nullable: bool = False, **kw: object) -> sa.Column:
    return sa.Column(name, pg.UUID(as_uuid=True), sa.ForeignKey(target), nullable=nullable, **kw)


def _ts() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def _id() -> sa.Column:
    return sa.Column("id", pg.UUID(as_uuid=True), primary_key=True)


def _version() -> sa.Column:
    return sa.Column("version", sa.Integer(), nullable=False, server_default="1")


def upgrade() -> None:
    bind = op.get_bind()
    for name, values in ENUMS.items():
        pg.ENUM(*values, name=name).create(bind, checkfirst=False)

    op.create_table(
        "urgent_help_content",
        _id(),
        _col("organization_id", "organization.id"),
        sa.Column("version_label", sa.String(50), nullable=False),
        sa.Column("status", _enum("template_status"), nullable=False),
        sa.Column("heading", sa.String(200), nullable=False),
        sa.Column("instruction_text", sa.Text(), nullable=False),
        sa.Column("when_to_call_text", sa.Text(), nullable=False),
        sa.Column("not_monitored_text", sa.Text(), nullable=False),
        sa.Column("support_hours_text", sa.String(300), nullable=True),
        sa.Column("outside_hours_text", sa.Text(), nullable=True),
        sa.Column("approved_by_name", sa.String(200), nullable=True),
        sa.Column("approved_by_role", sa.String(100), nullable=True),
        sa.Column("approved_on", sa.Date(), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=True),
        *_ts(),
        sa.UniqueConstraint("organization_id", "version_label", name="uq_urgent_help_content_version"),
        sa.CheckConstraint(
            "status <> 'APPROVED' OR (approved_by_name IS NOT NULL AND approved_on IS NOT NULL"
            " AND effective_from IS NOT NULL)",
            name="ck_urgent_help_approval_recorded",
        ),
    )
    grant_app_role("urgent_help_content", READ_ONLY)

    op.create_table(
        "messaging_channel",
        _id(),
        _col("organization_id", "organization.id"),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("phone_number_id", sa.String(64), nullable=False, unique=True),
        sa.Column("display_label", sa.String(100), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        *_ts(),
    )
    grant_app_role("messaging_channel", READ_ONLY)

    op.create_table(
        "message_template",
        _id(),
        _col("organization_id", "organization.id"),
        sa.Column("purpose", _enum("message_purpose"), nullable=False),
        sa.Column("language", sa.String(16), nullable=False),
        sa.Column("detail_level", _enum("detail_level"), nullable=False),
        sa.Column("version_label", sa.String(50), nullable=False),
        sa.Column("provider_template_name", sa.String(100), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("variable_names", pg.ARRAY(sa.String(50)), nullable=False),
        sa.Column("audio_storage_key", sa.String(100), nullable=True),
        sa.Column("status", _enum("template_status"), nullable=False),
        sa.Column("is_placeholder", sa.Boolean(), nullable=False),
        sa.Column("approved_by_name", sa.String(200), nullable=True),
        sa.Column("approved_on", sa.Date(), nullable=True),
        *_ts(),
        sa.UniqueConstraint(
            "organization_id", "purpose", "language", "detail_level", "version_label",
            name="uq_message_template_version",
        ),
        sa.CheckConstraint(
            "status <> 'APPROVED' OR is_placeholder OR (approved_by_name IS NOT NULL AND approved_on IS NOT NULL)",
            name="ck_message_template_approval_recorded",
        ),
    )
    grant_app_role("message_template", READ_ONLY)

    op.create_table(
        "contact_preference",
        _id(),
        _col("person_id", "person.id", unique=True),
        sa.Column("language", sa.String(16), nullable=True),
        sa.Column("safe_from_hour", sa.Integer(), nullable=True),
        sa.Column("safe_to_hour", sa.Integer(), nullable=True),
        sa.Column("detail_level", _enum("detail_level"), nullable=False),
        sa.Column("messaging_consent", sa.Boolean(), nullable=False),
        sa.Column("consent_recorded_at", sa.DateTime(timezone=True), nullable=True),
        _col("consent_recorded_by_staff_user_id", "staff_user.id", nullable=True),
        sa.Column("opted_out", sa.Boolean(), nullable=False),
        sa.Column("opted_out_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("opt_out_source", _enum("opt_out_source"), nullable=True),
        sa.Column("prefers_call", sa.Boolean(), nullable=False),
        _col("updated_by_staff_user_id", "staff_user.id", nullable=True),
        _version(),
        *_ts(),
        sa.CheckConstraint(
            "(safe_from_hour IS NULL AND safe_to_hour IS NULL) OR "
            "(safe_from_hour BETWEEN 0 AND 23 AND safe_to_hour BETWEEN 1 AND 24 AND safe_from_hour < safe_to_hour)",
            name="ck_contact_preference_hours",
        ),
        sa.CheckConstraint(
            "NOT messaging_consent OR (consent_recorded_at IS NOT NULL AND consent_recorded_by_staff_user_id IS NOT NULL)",
            name="ck_contact_preference_consent_recorded",
        ),
        sa.CheckConstraint("NOT opted_out OR opted_out_at IS NOT NULL", name="ck_contact_preference_opt_out_time"),
    )
    grant_app_role("contact_preference", NO_DELETE)

    op.create_table(
        "inbound_event",
        _id(),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_event_id", sa.String(200), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("provider", "provider_event_id", name="uq_inbound_event_provider_id"),
    )
    grant_app_role("inbound_event", APPEND_ONLY)

    op.create_table(
        "inbox_item",
        _id(),
        _col("organization_id", "organization.id"),
        _col("facility_id", "facility.id", nullable=True),
        _col("channel_id", "messaging_channel.id"),
        _col("inbound_event_id", "inbound_event.id", unique=True),
        sa.Column("from_number", sa.String(32), nullable=False),
        sa.Column("kind", _enum("inbox_kind"), nullable=False),
        sa.Column("text_body", sa.Text(), nullable=True),
        sa.Column("provider_media_id", sa.String(200), nullable=True),
        sa.Column("media_state", _enum("media_state"), nullable=False),
        sa.Column("media_note", sa.String(200), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        _col("person_id", "person.id", nullable=True),
        _col("linked_by_staff_user_id", "staff_user.id", nullable=True),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("identity_check", _enum("identity_check"), nullable=True),
        sa.Column("status", _enum("inbox_status"), nullable=False),
        _col("owner_staff_user_id", "staff_user.id", nullable=True),
        _col("backup_staff_user_id", "staff_user.id", nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("outcome", _enum("inbox_outcome"), nullable=True),
        sa.Column("closure_note", sa.String(500), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        _col("closed_by_staff_user_id", "staff_user.id", nullable=True),
        _version(),
        *_ts(),
        sa.CheckConstraint(
            "person_id IS NULL OR (linked_by_staff_user_id IS NOT NULL AND identity_check IS NOT NULL"
            " AND linked_at IS NOT NULL)",
            name="ck_inbox_item_link_recorded",
        ),
        sa.CheckConstraint(
            "status <> 'CLOSED' OR (outcome IS NOT NULL AND closed_at IS NOT NULL)",
            name="ck_inbox_item_closure_recorded",
        ),
    )
    op.create_index("ix_inbox_item_facility_status", "inbox_item", ["facility_id", "status"])
    op.create_index("ix_inbox_item_org_unlinked", "inbox_item", ["organization_id", "person_id"])
    grant_app_role("inbox_item", NO_DELETE)

    op.create_table(
        "inbound_media",
        _id(),
        _col("inbox_item_id", "inbox_item.id", unique=True),
        sa.Column("storage_key", sa.String(100), nullable=False, unique=True),
        sa.Column("content_type", sa.String(50), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        *_ts(),
        sa.CheckConstraint("size_bytes > 0", name="ck_inbound_media_size_positive"),
        sa.CheckConstraint(
            "content_type IN (" + ", ".join(f"'{t}'" for t in MEDIA_TYPES) + ")", name="ck_inbound_media_type"
        ),
    )
    grant_app_role("inbound_media", APPEND_ONLY)

    op.create_table(
        "outbox_message",
        _id(),
        _col("facility_id", "facility.id"),
        _col("person_id", "person.id"),
        _col("contact_method_id", "contact_method.id"),
        _col("channel_id", "messaging_channel.id"),
        sa.Column("kind", _enum("outbox_kind"), nullable=False),
        sa.Column("purpose", _enum("message_purpose"), nullable=False),
        _col("template_id", "message_template.id", nullable=True),
        sa.Column("variables", pg.JSONB(), nullable=False),
        sa.Column("free_text", sa.Text(), nullable=True),
        _col("appointment_id", "appointment.id", nullable=True),
        sa.Column("appointment_version", sa.Integer(), nullable=True),
        _col("inbox_item_id", "inbox_item.id", nullable=True),
        sa.Column("status", _enum("outbox_status"), nullable=False),
        sa.Column("status_reason", sa.String(64), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("leased_by", sa.String(64), nullable=True),
        sa.Column("provider_message_id", sa.String(128), nullable=True, unique=True),
        sa.Column("last_error", sa.String(200), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        _col("created_by_staff_user_id", "staff_user.id"),
        _col("owner_staff_user_id", "staff_user.id", nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        _col("resolved_by_staff_user_id", "staff_user.id", nullable=True),
        _version(),
        *_ts(),
        sa.CheckConstraint(
            "(kind = 'TEMPLATE' AND template_id IS NOT NULL AND free_text IS NULL)"
            " OR (kind = 'TEXT' AND template_id IS NULL AND free_text IS NOT NULL)",
            name="ck_outbox_kind_content",
        ),
    )
    op.create_index("ix_outbox_due", "outbox_message", ["status", "next_attempt_at"])
    op.create_index("ix_outbox_person", "outbox_message", ["person_id", "created_at"])
    grant_app_role("outbox_message", NO_DELETE)


def downgrade() -> None:
    for table in (
        "outbox_message",
        "inbound_media",
        "inbox_item",
        "inbound_event",
        "contact_preference",
        "message_template",
        "messaging_channel",
        "urgent_help_content",
    ):
        op.drop_table(table)
    bind = op.get_bind()
    for name in ENUMS:
        pg.ENUM(name=name).drop(bind, checkfirst=False)
