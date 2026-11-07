import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk


class CaregiverScope(str, enum.Enum):
    """What an adult caregiver may see or receive for the mother (D07 draft).
    Private concerns, history, allergies and reports are deliberately absent."""

    NEXT_ACTION = "NEXT_ACTION"
    BIRTH_PLAN = "BIRTH_PLAN"
    REMINDERS = "REMINDERS"


class VerificationMethod(str, enum.Enum):
    """How staff confirmed identity in person. Phone possession is never one."""

    IN_PERSON_DOCUMENT = "IN_PERSON_DOCUMENT"
    IN_PERSON_KNOWN_TO_STAFF = "IN_PERSON_KNOWN_TO_STAFF"
    IN_PERSON_OTHER = "IN_PERSON_OTHER"


class RevokeReason(str, enum.Enum):
    # A fixed list, not free text, so no private detail lands in the record.
    REQUESTED_BY_SUBJECT = "REQUESTED_BY_SUBJECT"
    SAFETY_CONCERN = "SAFETY_CONCERN"
    REPLACED = "REPLACED"
    RECORDED_IN_ERROR = "RECORDED_IN_ERROR"


_SCOPE_VALUES = ", ".join(f"'{s.value}'" for s in CaregiverScope)


class CaregiverGrant(Base, TimestampMixin):
    """A mother's consent for one adult caregiver to see or receive specific
    things. Never deleted: revocation is recorded so the history stays.
    Unused until D07 is decided (settings.patient_access_enabled)."""

    __tablename__ = "caregiver_grant"
    __table_args__ = (
        CheckConstraint("subject_person_id <> grantee_person_id", name="ck_caregiver_grant_not_self"),
        CheckConstraint("cardinality(scopes) > 0", name="ck_caregiver_grant_has_scope"),
        CheckConstraint(f"scopes <@ ARRAY[{_SCOPE_VALUES}]::varchar[]", name="ck_caregiver_grant_known_scopes"),
        CheckConstraint(
            "(revoked_at IS NULL AND revoked_by_staff_user_id IS NULL AND revoke_reason IS NULL)"
            " OR (revoked_at IS NOT NULL AND revoked_by_staff_user_id IS NOT NULL AND revoke_reason IS NOT NULL)",
            name="ck_caregiver_grant_revocation_complete",
        ),
        Index("ix_caregiver_grant_subject_grantee", "subject_person_id", "grantee_person_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    subject_person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("person.id"), nullable=False
    )
    grantee_person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("person.id"), nullable=False
    )
    scopes: Mapped[list[str]] = mapped_column(ARRAY(String(32)), nullable=False)
    recorded_by_staff_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_user.id"), nullable=False
    )
    verified_by_staff_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_user.id"), nullable=False
    )
    verification_method: Mapped[VerificationMethod] = mapped_column(
        Enum(VerificationMethod, name="caregiver_verification_method"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by_staff_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_user.id"), nullable=True
    )
    revoke_reason: Mapped[RevokeReason | None] = mapped_column(
        Enum(RevokeReason, name="caregiver_revoke_reason"), nullable=True
    )
    # Optimistic concurrency (W2-A1 rule: every updatable table has a version).
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
