"""Phase 1 care records: plan templates, published plans, appointments, owned
tasks and investigations (F005, F007, F008, F009, T008).

States and transitions live in app/domain/transitions.py, not here. Every
updatable table carries `version` for optimistic concurrency. Nothing in
these tables scores, interprets or flags clinical risk: "overdue" is an
administrative delay, unknown dates stay NULL.
"""

import enum
import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
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
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk


def _fk(target: str, nullable: bool = False) -> Any:
    return mapped_column(UUID(as_uuid=True), ForeignKey(target), nullable=nullable)


def _version() -> Any:
    return mapped_column(Integer, nullable=False, default=1, server_default="1")


# --- Templates (read-only for the app role) ----------------------------------


class TemplateStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    WITHDRAWN = "WITHDRAWN"


class CareItemKind(str, enum.Enum):
    VISIT = "VISIT"
    TEST_REQUEST = "TEST_REQUEST"
    FOLLOW_UP = "FOLLOW_UP"


class TimingBasis(str, enum.Enum):
    """How an item's due time is worked out. The doctor's template decides
    which is used; the placeholder uses only the first two."""

    AT_PUBLISH = "AT_PUBLISH"  # e.g. "at first contact"
    DAYS_AFTER_PUBLISH = "DAYS_AFTER_PUBLISH"
    GESTATIONAL_WEEKS = "GESTATIONAL_WEEKS"  # scheduled only once a date is recorded


class CarePlanTemplate(Base, TimestampMixin):
    __tablename__ = "care_plan_template"
    __table_args__ = (
        CheckConstraint(
            "status <> 'APPROVED' OR is_placeholder OR (approved_by_name IS NOT NULL AND approved_on IS NOT NULL)",
            name="ck_template_approval_recorded",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID] = _fk("organization.id")
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    version_label: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[TemplateStatus] = mapped_column(Enum(TemplateStatus, name="template_status"), nullable=False)
    # A placeholder is never clinical content; screens must label it.
    is_placeholder: Mapped[bool] = mapped_column(Boolean, nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # The approving doctor may not be a staff user of the system.
    approved_by_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    approved_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)


class CarePlanTemplateItem(Base, TimestampMixin):
    __tablename__ = "care_plan_template_item"
    __table_args__ = (
        CheckConstraint(
            "(timing_basis = 'AT_PUBLISH' AND offset_days IS NULL AND week_from IS NULL AND week_to IS NULL)"
            " OR (timing_basis = 'DAYS_AFTER_PUBLISH' AND offset_days >= 0 AND week_from IS NULL AND week_to IS NULL)"
            " OR (timing_basis = 'GESTATIONAL_WEEKS' AND offset_days IS NULL AND week_from IS NOT NULL"
            " AND week_to IS NOT NULL AND week_from <= week_to)",
            name="ck_template_item_timing",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    template_id: Mapped[uuid.UUID] = _fk("care_plan_template.id")
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[CareItemKind] = mapped_column(Enum(CareItemKind, name="care_item_kind"), nullable=False)
    timing_basis: Mapped[TimingBasis] = mapped_column(Enum(TimingBasis, name="timing_basis"), nullable=False)
    offset_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    week_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    week_to: Mapped[int | None] = mapped_column(Integer, nullable=True)
    performer_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    preparation_text: Mapped[str | None] = mapped_column(Text, nullable=True)


# --- Published plan ----------------------------------------------------------


class CarePlanStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    CANCELLED = "CANCELLED"


class CarePlan(Base, TimestampMixin):
    __tablename__ = "care_plan"
    __table_args__ = (
        Index(
            "uq_care_plan_one_active_per_episode",
            "episode_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    episode_id: Mapped[uuid.UUID] = _fk("pregnancy_episode.id")
    facility_id: Mapped[uuid.UUID] = _fk("facility.id")
    template_id: Mapped[uuid.UUID] = _fk("care_plan_template.id")
    status: Mapped[CarePlanStatus] = mapped_column(Enum(CarePlanStatus, name="care_plan_status"), nullable=False)
    published_by_staff_user_id: Mapped[uuid.UUID] = _fk("staff_user.id")
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = _version()


# --- Appointments --------------------------------------------------------------


class AppointmentStatus(str, enum.Enum):
    REQUESTED = "REQUESTED"
    CONFIRMED = "CONFIRMED"
    ATTENDED = "ATTENDED"
    MISSED = "MISSED"
    RESCHEDULED = "RESCHEDULED"
    CANCELLED = "CANCELLED"


class Appointment(Base, TimestampMixin):
    __tablename__ = "appointment"

    id: Mapped[uuid.UUID] = uuid_pk()
    episode_id: Mapped[uuid.UUID] = _fk("pregnancy_episode.id")
    facility_id: Mapped[uuid.UUID] = _fk("facility.id")
    care_plan_id: Mapped[uuid.UUID | None] = _fk("care_plan.id", nullable=True)
    template_item_id: Mapped[uuid.UUID | None] = _fk("care_plan_template_item.id", nullable=True)
    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(AppointmentStatus, name="appointment_status"), nullable=False
    )
    # A booking is a request until a person confirms the actual date (F007).
    requested_for: Mapped[date | None] = mapped_column(Date, nullable=True)
    confirmed_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    location_note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    owner_staff_user_id: Mapped[uuid.UUID | None] = _fk("staff_user.id", nullable=True)
    previous_appointment_id: Mapped[uuid.UUID | None] = _fk("appointment.id", nullable=True)
    status_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    version: Mapped[int] = _version()


# --- Owned tasks ---------------------------------------------------------------


class TaskStatus(str, enum.Enum):
    NEW = "NEW"
    ASSIGNED = "ASSIGNED"
    AWAITING_PATIENT = "AWAITING_PATIENT"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class TaskKind(str, enum.Enum):
    FOLLOW_UP_MISSED_VISIT = "FOLLOW_UP_MISSED_VISIT"
    CONTACT = "CONTACT"
    HELP_REQUEST = "HELP_REQUEST"
    REVIEW_WORK = "REVIEW_WORK"
    PLAN_ITEM = "PLAN_ITEM"


class TaskOutcome(str, enum.Enum):
    """Kept distinct on purpose (F008): declined, unreachable and unknown
    are different results, never collapsed into "not done"."""

    DONE = "DONE"
    DECLINED = "DECLINED"
    UNREACHABLE = "UNREACHABLE"
    UNKNOWN = "UNKNOWN"
    NOT_NEEDED = "NOT_NEEDED"


class CareTask(Base, TimestampMixin):
    __tablename__ = "care_task"
    __table_args__ = (
        CheckConstraint(
            "(status IN ('COMPLETED', 'CANCELLED')) = (outcome IS NOT NULL AND closed_at IS NOT NULL)",
            name="ck_task_closure_recorded",
        ),
        CheckConstraint("status = 'NEW' OR owner_staff_user_id IS NOT NULL", name="ck_task_owned_once_assigned"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    episode_id: Mapped[uuid.UUID] = _fk("pregnancy_episode.id")
    facility_id: Mapped[uuid.UUID] = _fk("facility.id")
    kind: Mapped[TaskKind] = mapped_column(Enum(TaskKind, name="task_kind"), nullable=False)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus, name="task_status"), nullable=False)
    owner_staff_user_id: Mapped[uuid.UUID | None] = _fk("staff_user.id", nullable=True)
    backup_staff_user_id: Mapped[uuid.UUID | None] = _fk("staff_user.id", nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_appointment_id: Mapped[uuid.UUID | None] = _fk("appointment.id", nullable=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    barrier: Mapped[str | None] = mapped_column(String(64), nullable=True)
    outcome: Mapped[TaskOutcome | None] = mapped_column(Enum(TaskOutcome, name="task_outcome"), nullable=True)
    closure_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = _version()


# --- Investigations ------------------------------------------------------------


class InvestigationStatus(str, enum.Enum):
    REQUESTED = "REQUESTED"
    PERFORMED = "PERFORMED"
    RECEIVED = "RECEIVED"
    REVIEWED = "REVIEWED"


class Investigation(Base, TimestampMixin):
    __tablename__ = "investigation"
    __table_args__ = (
        CheckConstraint(
            "(status = 'REVIEWED') = (reviewed_at IS NOT NULL AND reviewed_by_staff_user_id IS NOT NULL)",
            name="ck_investigation_review_attributed",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    episode_id: Mapped[uuid.UUID] = _fk("pregnancy_episode.id")
    facility_id: Mapped[uuid.UUID] = _fk("facility.id")
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[InvestigationStatus] = mapped_column(
        Enum(InvestigationStatus, name="investigation_status"), nullable=False
    )
    # Each date may be unknown (e.g. an outside report): stays NULL, never guessed.
    requested_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    performed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    file_object_id: Mapped[uuid.UUID | None] = _fk("file_object.id", nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by_staff_user_id: Mapped[uuid.UUID | None] = _fk("staff_user.id", nullable=True)
    version: Mapped[int] = _version()
