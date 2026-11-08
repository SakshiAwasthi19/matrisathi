from datetime import datetime

from pydantic import BaseModel, Field

from app.models.messaging import (
    DetailLevel,
    IdentityCheck,
    InboxKind,
    InboxOutcome,
    InboxStatus,
    MediaState,
    MessagePurpose,
    OptOutSource,
    OutboxKind,
    OutboxStatus,
)


class ContactPreferenceOut(BaseModel):
    person_id: str
    exists: bool
    language: str | None
    safe_from_hour: int | None
    safe_to_hour: int | None
    default_safe_from_hour: int
    default_safe_to_hour: int
    detail_level: DetailLevel
    messaging_consent: bool
    consent_recorded_at: datetime | None
    consent_recorded_by_name: str | None
    opted_out: bool
    opted_out_at: datetime | None
    opt_out_source: OptOutSource | None
    prefers_call: bool
    version: int
    phone_numbers: list[str]
    messaging_available: bool


class ContactPreferenceIn(BaseModel):
    expected_version: int | None = None  # None when creating
    language: str | None = Field(default=None, max_length=16)
    safe_from_hour: int | None = Field(default=None, ge=0, le=23)
    safe_to_hour: int | None = Field(default=None, ge=1, le=24)
    detail_level: DetailLevel = DetailLevel.MINIMAL
    # Only staff record consent, after asking her in person or on a call.
    messaging_consent: bool
    opted_out: bool = False
    prefers_call: bool = False


class MessageOut(BaseModel):
    id: str
    person_id: str
    kind: OutboxKind
    purpose: MessagePurpose
    status: OutboxStatus
    status_reason: str | None
    # What was (or will be) sent, as staff should read it.
    text: str
    audio_available: bool
    template_placeholder: bool
    appointment_id: str | None
    inbox_item_id: str | None
    attempts: int
    next_attempt_at: datetime
    submitted_at: datetime | None
    delivered_at: datetime | None
    read_at: datetime | None
    failed_at: datetime | None
    created_at: datetime
    created_by_name: str | None
    owner_name: str | None
    resolved_at: datetime | None
    person_name: str | None = None


class ReminderIn(BaseModel):
    send_at: datetime | None = None


class TemplateOut(BaseModel):
    id: str
    purpose: MessagePurpose
    language: str
    detail_level: DetailLevel
    version_label: str
    body_text: str
    variable_names: list[str]
    is_placeholder: bool
    approved_by_name: str | None
    audio_available: bool


class ResolveIn(BaseModel):
    note: str | None = Field(default=None, max_length=300)


class InboxItemOut(BaseModel):
    id: str
    facility_id: str | None
    kind: InboxKind
    text_body: str | None
    media_state: MediaState
    media_note: str | None
    media_content_type: str | None
    received_at: datetime
    # Shown in full only to people who may see the item; never an identity.
    from_number: str
    people_on_number: int
    person_id: str | None
    person_name: str | None
    linked_by_name: str | None
    linked_at: datetime | None
    identity_check: IdentityCheck | None
    status: InboxStatus
    owner_staff_user_id: str | None
    owner_name: str | None
    backup_staff_user_id: str | None
    backup_name: str | None
    due_at: datetime
    overdue: bool
    outcome: InboxOutcome | None
    closure_note: str | None
    closed_at: datetime | None
    version: int
    replies: list[MessageOut] = []
    can_reply_free_text: bool = False


class LinkIn(BaseModel):
    expected_version: int
    person_id: str
    identity_check: IdentityCheck


class AssignIn(BaseModel):
    expected_version: int
    owner_staff_user_id: str
    backup_staff_user_id: str | None = None


class ReplyIn(BaseModel):
    expected_version: int
    text: str | None = Field(default=None, min_length=1, max_length=1000)
    template_purpose: MessagePurpose | None = None


class CloseIn(BaseModel):
    expected_version: int
    outcome: InboxOutcome
    note: str | None = Field(default=None, max_length=500)


class InboxSummary(BaseModel):
    open: int
    unlinked: int
    mine: int
    overdue: int
    failed_messages: int
