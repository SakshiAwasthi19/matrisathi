"""WhatsApp and voice messaging (SG3: F016-F020, T011-T013).

- `messaging_channel` maps the provider's phone-number ID to an organization.
- `message_template` holds approved outbound templates (loaded by script,
  read-only for the app, like care-plan templates).
- `contact_preference` holds a person's consent, opt-out, language, safe
  hours and detail level. Opt-out always wins.
- `outbox_message` is the durable outbox: written in the same transaction as
  the business change, sent by the worker with a lease, never sent twice.
- `inbound_event` dedupes provider webhooks on the provider's event ID.
- `inbox_item` is one inbound text, voice note or photo for staff. It is
  never linked to a person automatically: a phone number is not an identity.
- `inbound_media` is the privately stored copy of an inbound voice note or
  photo; the provider's URL is never kept as an access path.

Delivery states are reported, never inferred: UNKNOWN means we cannot tell
whether the provider accepted the message, and it is never shown as sent.
"""

import enum
import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk
from app.models.care import TemplateStatus


def _fk(target: str, nullable: bool = False) -> Any:
    return mapped_column(UUID(as_uuid=True), ForeignKey(target), nullable=nullable)


class MessagePurpose(str, enum.Enum):
    APPOINTMENT_REMINDER = "APPOINTMENT_REMINDER"
    FOLLOW_UP = "FOLLOW_UP"
    GENERAL = "GENERAL"


class DetailLevel(str, enum.Enum):
    # MINIMAL: nothing about the pregnancy or care, for shared phones.
    MINIMAL = "MINIMAL"
    STANDARD = "STANDARD"


class OutboxStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    SENDING = "SENDING"  # handed to the provider call; outcome not yet known
    SUBMITTED = "SUBMITTED"  # provider accepted it
    DELIVERED = "DELIVERED"
    READ = "READ"  # only if the provider reports it
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"  # cannot tell if the provider accepted it; never shown as sent
    BLOCKED = "BLOCKED"  # not sent because a rule said no (opt-out, stale, no consent...)


class OutboxKind(str, enum.Enum):
    TEMPLATE = "TEMPLATE"
    TEXT = "TEXT"  # free text, only inside the provider's service window


class InboxKind(str, enum.Enum):
    TEXT = "TEXT"
    VOICE = "VOICE"
    IMAGE = "IMAGE"
    OTHER = "OTHER"


class MediaState(str, enum.Enum):
    NONE = "NONE"
    PENDING = "PENDING"
    STORED = "STORED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class InboxStatus(str, enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class InboxOutcome(str, enum.Enum):
    RESPONDED = "RESPONDED"
    CALLED = "CALLED"
    NO_ACTION_NEEDED = "NO_ACTION_NEEDED"
    NOT_FOR_US = "NOT_FOR_US"
    OTHER = "OTHER"


class IdentityCheck(str, enum.Enum):
    """How staff confirmed who sent the message before linking it."""

    CALLED_BACK = "CALLED_BACK"
    ASKED_IDENTIFYING_DETAILS = "ASKED_IDENTIFYING_DETAILS"
    IN_PERSON = "IN_PERSON"


class OptOutSource(str, enum.Enum):
    STAFF = "STAFF"  # recorded by staff on the person's request
    INBOUND_KEYWORD = "INBOUND_KEYWORD"  # STOP received from that number


class MessagingChannel(Base, TimestampMixin):
    __tablename__ = "messaging_channel"

    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID] = _fk("organization.id")
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    phone_number_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    display_label: Mapped[str] = mapped_column(String(100), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class MessageTemplate(Base, TimestampMixin):
    __tablename__ = "message_template"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "purpose", "language", "detail_level", "version_label",
            name="uq_message_template_version",
        ),
        CheckConstraint(
            "status <> 'APPROVED' OR is_placeholder OR (approved_by_name IS NOT NULL AND approved_on IS NOT NULL)",
            name="ck_message_template_approval_recorded",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID] = _fk("organization.id")
    purpose: Mapped[MessagePurpose] = mapped_column(Enum(MessagePurpose, name="message_purpose"), nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    detail_level: Mapped[DetailLevel] = mapped_column(Enum(DetailLevel, name="detail_level"), nullable=False)
    version_label: Mapped[str] = mapped_column(String(50), nullable=False)
    # The name the provider approved the template under.
    provider_template_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # The exact text the provider sends, with {{1}}-style slots; staff see it.
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    variable_names: Mapped[list[str]] = mapped_column(ARRAY(String(50)), nullable=False, default=list)
    # Approved audio with the same meaning as body_text (D08); none until approved.
    audio_storage_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[TemplateStatus] = mapped_column(
        Enum(TemplateStatus, name="template_status", create_type=False), nullable=False
    )
    is_placeholder: Mapped[bool] = mapped_column(Boolean, nullable=False)
    approved_by_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    approved_on: Mapped[date | None] = mapped_column(Date, nullable=True)


class ContactPreference(Base, TimestampMixin):
    __tablename__ = "contact_preference"
    __table_args__ = (
        CheckConstraint(
            "(safe_from_hour IS NULL AND safe_to_hour IS NULL) OR "
            "(safe_from_hour BETWEEN 0 AND 23 AND safe_to_hour BETWEEN 1 AND 24 AND safe_from_hour < safe_to_hour)",
            name="ck_contact_preference_hours",
        ),
        CheckConstraint(
            "NOT messaging_consent OR (consent_recorded_at IS NOT NULL AND consent_recorded_by_staff_user_id IS NOT NULL)",
            name="ck_contact_preference_consent_recorded",
        ),
        CheckConstraint("NOT opted_out OR opted_out_at IS NOT NULL", name="ck_contact_preference_opt_out_time"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("person.id"), nullable=False, unique=True
    )
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # Local hours [from, to) when messages may be sent. NULL: the default window.
    safe_from_hour: Mapped[int | None] = mapped_column(Integer, nullable=True)
    safe_to_hour: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail_level: Mapped[DetailLevel] = mapped_column(
        Enum(DetailLevel, name="detail_level", create_type=False), nullable=False, default=DetailLevel.MINIMAL
    )
    messaging_consent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    consent_recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consent_recorded_by_staff_user_id: Mapped[uuid.UUID | None] = _fk("staff_user.id", nullable=True)
    opted_out: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    opted_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    opt_out_source: Mapped[OptOutSource | None] = mapped_column(
        Enum(OptOutSource, name="opt_out_source"), nullable=True
    )
    prefers_call: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_by_staff_user_id: Mapped[uuid.UUID | None] = _fk("staff_user.id", nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    __mapper_args__ = {"version_id_col": version}


class OutboxMessage(Base, TimestampMixin):
    __tablename__ = "outbox_message"
    __table_args__ = (
        Index("ix_outbox_due", "status", "next_attempt_at"),
        Index("ix_outbox_person", "person_id", "created_at"),
        CheckConstraint(
            "(kind = 'TEMPLATE' AND template_id IS NOT NULL AND free_text IS NULL)"
            " OR (kind = 'TEXT' AND template_id IS NULL AND free_text IS NOT NULL)",
            name="ck_outbox_kind_content",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    facility_id: Mapped[uuid.UUID] = _fk("facility.id")
    person_id: Mapped[uuid.UUID] = _fk("person.id")
    contact_method_id: Mapped[uuid.UUID] = _fk("contact_method.id")
    channel_id: Mapped[uuid.UUID] = _fk("messaging_channel.id")
    kind: Mapped[OutboxKind] = mapped_column(Enum(OutboxKind, name="outbox_kind"), nullable=False)
    purpose: Mapped[MessagePurpose] = mapped_column(
        Enum(MessagePurpose, name="message_purpose", create_type=False), nullable=False
    )
    template_id: Mapped[uuid.UUID | None] = _fk("message_template.id", nullable=True)
    variables: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False, default=dict)
    free_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # A reminder is dropped at send time if its appointment changed since queueing.
    appointment_id: Mapped[uuid.UUID | None] = _fk("appointment.id", nullable=True)
    appointment_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    inbox_item_id: Mapped[uuid.UUID | None] = _fk("inbox_item.id", nullable=True)
    status: Mapped[OutboxStatus] = mapped_column(Enum(OutboxStatus, name="outbox_status"), nullable=False)
    status_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    leased_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    # A short, scrubbed description: never the message text or a phone number.
    last_error: Mapped[str | None] = mapped_column(String(200), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_staff_user_id: Mapped[uuid.UUID] = _fk("staff_user.id")
    # Who follows up when it fails or is unknown.
    owner_staff_user_id: Mapped[uuid.UUID | None] = _fk("staff_user.id", nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by_staff_user_id: Mapped[uuid.UUID | None] = _fk("staff_user.id", nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    __mapper_args__ = {"version_id_col": version}


class InboundEvent(Base):
    """One row per provider event ID: a repeated webhook is a no-op."""

    __tablename__ = "inbound_event"
    __table_args__ = (UniqueConstraint("provider", "provider_event_id", name="uq_inbound_event_provider_id"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # MESSAGE or STATUS
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class InboxItem(Base, TimestampMixin):
    __tablename__ = "inbox_item"
    __table_args__ = (
        Index("ix_inbox_item_facility_status", "facility_id", "status"),
        Index("ix_inbox_item_org_unlinked", "organization_id", "person_id"),
        CheckConstraint(
            "person_id IS NULL OR (linked_by_staff_user_id IS NOT NULL AND identity_check IS NOT NULL"
            " AND linked_at IS NOT NULL)",
            name="ck_inbox_item_link_recorded",
        ),
        CheckConstraint(
            "status <> 'CLOSED' OR (outcome IS NOT NULL AND closed_at IS NOT NULL)",
            name="ck_inbox_item_closure_recorded",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID] = _fk("organization.id")
    # Set when the sender's number belongs to people at exactly one facility,
    # or when staff link the item. The item stays unlinked either way.
    facility_id: Mapped[uuid.UUID | None] = _fk("facility.id", nullable=True)
    channel_id: Mapped[uuid.UUID] = _fk("messaging_channel.id")
    inbound_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inbound_event.id"), nullable=False, unique=True
    )
    from_number: Mapped[str] = mapped_column(String(32), nullable=False)
    kind: Mapped[InboxKind] = mapped_column(Enum(InboxKind, name="inbox_kind"), nullable=False)
    text_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_media_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    media_state: Mapped[MediaState] = mapped_column(Enum(MediaState, name="media_state"), nullable=False)
    media_note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    person_id: Mapped[uuid.UUID | None] = _fk("person.id", nullable=True)
    linked_by_staff_user_id: Mapped[uuid.UUID | None] = _fk("staff_user.id", nullable=True)
    linked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    identity_check: Mapped[IdentityCheck | None] = mapped_column(
        Enum(IdentityCheck, name="identity_check"), nullable=True
    )
    status: Mapped[InboxStatus] = mapped_column(Enum(InboxStatus, name="inbox_status"), nullable=False)
    owner_staff_user_id: Mapped[uuid.UUID | None] = _fk("staff_user.id", nullable=True)
    backup_staff_user_id: Mapped[uuid.UUID | None] = _fk("staff_user.id", nullable=True)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    outcome: Mapped[InboxOutcome | None] = mapped_column(Enum(InboxOutcome, name="inbox_outcome"), nullable=True)
    closure_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by_staff_user_id: Mapped[uuid.UUID | None] = _fk("staff_user.id", nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    __mapper_args__ = {"version_id_col": version}


INBOUND_MEDIA_TYPES = (
    "image/jpeg",
    "image/png",
    "audio/ogg",
    "audio/mpeg",
    "audio/mp4",
    "audio/amr",
)


class InboundMedia(Base, TimestampMixin):
    __tablename__ = "inbound_media"
    __table_args__ = (
        CheckConstraint("size_bytes > 0", name="ck_inbound_media_size_positive"),
        CheckConstraint(
            "content_type IN (" + ", ".join(f"'{t}'" for t in INBOUND_MEDIA_TYPES) + ")",
            name="ck_inbound_media_type",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    inbox_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inbox_item.id"), nullable=False, unique=True
    )
    storage_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
