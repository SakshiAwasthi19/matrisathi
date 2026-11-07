"""Phase 1 records (W2-A4): prescriptions, observations, referrals and
verified local contacts (F010, F011, F012, F044).

Nothing here interprets anything:
- Observation values are stored as the text that was entered. There is no
  numeric column, so no code can compare a value with a threshold.
- A prescription keeps the original document and only a clinician's
  word-for-word transcription of the instruction. No dose or duration
  fields exist to calculate with.
- Referral destination and urgency are chosen by a clinician and recorded.
- Corrections and replacements keep the earlier row.
"""

import enum
import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk


def _fk(target: str, nullable: bool = False) -> Any:
    return mapped_column(UUID(as_uuid=True), ForeignKey(target), nullable=nullable)


def _version() -> Any:
    return mapped_column(Integer, nullable=False, default=1, server_default="1")


# --- Prescriptions (F010) -----------------------------------------------------


class PrescriptionSource(str, enum.Enum):
    PAPER_PRESCRIPTION = "PAPER_PRESCRIPTION"
    MCP_CARD = "MCP_CARD"
    DISCHARGE_SUMMARY = "DISCHARGE_SUMMARY"
    OTHER_DOCUMENT = "OTHER_DOCUMENT"


class InstructionStatus(str, enum.Enum):
    UNREVIEWED = "UNREVIEWED"  # recorded from the document; no reminder possible
    CONFIRMED = "CONFIRMED"  # a clinician transcribed the instruction as written
    UNCLEAR = "UNCLEAR"  # a clinician could not confirm it; review work is open


class Prescription(Base, TimestampMixin):
    __tablename__ = "prescription"
    __table_args__ = (
        CheckConstraint(
            "(instruction_status = 'UNREVIEWED') = (reviewed_by_staff_user_id IS NULL AND reviewed_at IS NULL)",
            name="ck_prescription_review_attributed",
        ),
        CheckConstraint(
            "instruction_status = 'CONFIRMED' OR (confirmed_instruction IS NULL AND reminder_enabled = false)",
            name="ck_prescription_reminder_only_when_confirmed",
        ),
        CheckConstraint(
            "instruction_status <> 'CONFIRMED' OR confirmed_instruction IS NOT NULL",
            name="ck_prescription_confirmed_has_text",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    episode_id: Mapped[uuid.UUID] = _fk("pregnancy_episode.id")
    facility_id: Mapped[uuid.UUID] = _fk("facility.id")
    source: Mapped[PrescriptionSource] = mapped_column(Enum(PrescriptionSource, name="prescription_source"), nullable=False)
    source_file_id: Mapped[uuid.UUID | None] = _fk("file_object.id", nullable=True)
    issued_on: Mapped[date | None] = mapped_column(Date, nullable=True)  # unknown stays unknown
    recorded_by_staff_user_id: Mapped[uuid.UUID] = _fk("staff_user.id")
    instruction_status: Mapped[InstructionStatus] = mapped_column(
        Enum(InstructionStatus, name="instruction_status"), nullable=False
    )
    confirmed_instruction: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_staff_user_id: Mapped[uuid.UUID | None] = _fk("staff_user.id", nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reminder_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    reminder_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    reminder_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    version: Mapped[int] = _version()

    __mapper_args__ = {"version_id_col": version}


# --- Observations and findings (F012) ------------------------------------------


class ObservationKind(str, enum.Enum):
    MEASUREMENT = "MEASUREMENT"
    CLINICIAN_FINDING = "CLINICIAN_FINDING"  # entered by a clinician, stored as written


class ObservationSource(str, enum.Enum):
    MEASURED_HERE = "MEASURED_HERE"
    OUTSIDE_RECORD = "OUTSIDE_RECORD"
    REPORTED_BY_FAMILY = "REPORTED_BY_FAMILY"


class CorrectionReason(str, enum.Enum):
    TYPING_ERROR = "TYPING_ERROR"
    WRONG_PERSON = "WRONG_PERSON"
    WRONG_DATE = "WRONG_DATE"
    WRONG_UNIT = "WRONG_UNIT"
    OTHER = "OTHER"


class Observation(Base, TimestampMixin):
    __tablename__ = "observation"
    __table_args__ = (
        CheckConstraint(
            "(superseded_at IS NULL) = (superseded_by_id IS NULL)", name="ck_observation_supersession_complete"
        ),
        CheckConstraint(
            "(corrects_id IS NULL) = (correction_reason IS NULL)", name="ck_observation_correction_has_reason"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    episode_id: Mapped[uuid.UUID] = _fk("pregnancy_episode.id")
    facility_id: Mapped[uuid.UUID] = _fk("facility.id")
    kind: Mapped[ObservationKind] = mapped_column(Enum(ObservationKind, name="observation_kind"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Raw text exactly as entered. Deliberately not numeric (F012, G01, G07).
    value_text: Mapped[str] = mapped_column(String(500), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    observed_on: Mapped[date | None] = mapped_column(Date, nullable=True)  # service date; may be unknown
    source: Mapped[ObservationSource] = mapped_column(Enum(ObservationSource, name="observation_source"), nullable=False)
    recorded_by_staff_user_id: Mapped[uuid.UUID] = _fk("staff_user.id")
    corrects_id: Mapped[uuid.UUID | None] = _fk("observation.id", nullable=True)
    correction_reason: Mapped[CorrectionReason | None] = mapped_column(
        Enum(CorrectionReason, name="observation_correction_reason"), nullable=True
    )
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("observation.id", deferrable=True, initially="DEFERRED"), nullable=True
    )
    version: Mapped[int] = _version()

    __mapper_args__ = {"version_id_col": version}


# --- Verified local contacts (F044) ---------------------------------------------


class ServiceType(str, enum.Enum):
    PHC = "PHC"
    REFERRAL_HOSPITAL = "REFERRAL_HOSPITAL"
    TRANSPORT = "TRANSPORT"
    NUTRITION = "NUTRITION"
    BENEFITS = "BENEFITS"
    OTHER = "OTHER"


class LocalContact(Base, TimestampMixin):
    __tablename__ = "local_contact"

    id: Mapped[uuid.UUID] = uuid_pk()
    facility_id: Mapped[uuid.UUID] = _fk("facility.id")
    service_type: Mapped[ServiceType] = mapped_column(Enum(ServiceType, name="service_type"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    alternate_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    landmarks: Mapped[str | None] = mapped_column(String(300), nullable=True)
    availability_note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    verified_by_staff_user_id: Mapped[uuid.UUID] = _fk("staff_user.id")
    verified_on: Mapped[date] = mapped_column(Date, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    version: Mapped[int] = _version()

    __mapper_args__ = {"version_id_col": version}


# --- Referrals (F011) -------------------------------------------------------------


class ReferralStatus(str, enum.Enum):
    SENT = "SENT"
    CONTACTED = "CONTACTED"
    ATTENDED = "ATTENDED"
    ADVICE_RECEIVED = "ADVICE_RECEIVED"
    FOLLOW_UP_COMPLETED = "FOLLOW_UP_COMPLETED"
    CLOSED = "CLOSED"


class ReferralUrgency(str, enum.Enum):
    """Chosen and recorded by a clinician; never computed."""

    ROUTINE = "ROUTINE"
    SOON = "SOON"
    URGENT = "URGENT"


class ReferralClosureReason(str, enum.Enum):
    FAMILY_DECLINED = "FAMILY_DECLINED"
    NOT_ATTENDED_AFTER_FOLLOW_UP = "NOT_ATTENDED_AFTER_FOLLOW_UP"
    CARE_TRANSFERRED_ELSEWHERE = "CARE_TRANSFERRED_ELSEWHERE"
    NO_LONGER_NEEDED_PER_CLINICIAN = "NO_LONGER_NEEDED_PER_CLINICIAN"
    RECORDED_IN_ERROR = "RECORDED_IN_ERROR"


class Referral(Base, TimestampMixin):
    __tablename__ = "referral"
    __table_args__ = (
        CheckConstraint("(status = 'CLOSED') = (closure_reason IS NOT NULL)", name="ck_referral_closure_has_reason"),
        CheckConstraint(
            "destination_contact_id IS NOT NULL OR destination_name IS NOT NULL", name="ck_referral_has_destination"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    episode_id: Mapped[uuid.UUID] = _fk("pregnancy_episode.id")
    facility_id: Mapped[uuid.UUID] = _fk("facility.id")
    destination_contact_id: Mapped[uuid.UUID | None] = _fk("local_contact.id", nullable=True)
    destination_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    urgency: Mapped[ReferralUrgency] = mapped_column(Enum(ReferralUrgency, name="referral_urgency"), nullable=False)
    clinician_instruction: Mapped[str | None] = mapped_column(Text, nullable=True)
    referred_by_staff_user_id: Mapped[uuid.UUID] = _fk("staff_user.id")
    owner_staff_user_id: Mapped[uuid.UUID] = _fk("staff_user.id")
    status: Mapped[ReferralStatus] = mapped_column(Enum(ReferralStatus, name="referral_status"), nullable=False)
    contacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attended_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    advice_received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    advice_file_id: Mapped[uuid.UUID | None] = _fk("file_object.id", nullable=True)
    follow_up_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closure_reason: Mapped[ReferralClosureReason | None] = mapped_column(
        Enum(ReferralClosureReason, name="referral_closure_reason"), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = _version()

    __mapper_args__ = {"version_id_col": version}
