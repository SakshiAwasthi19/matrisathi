from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.models.care import AppointmentStatus, TaskOutcome
from app.models.dating import DatingEvidence, DatingPrecision

# Fixed lists instead of free text, so no private detail lands in these fields.
Barrier = Literal["TRAVEL", "COST", "MEDICINE_ACCESS", "CHILDCARE", "WORK", "FAMILY", "OTHER"]
ClosureReason = Literal[
    "DONE_AS_PLANNED",
    "FAMILY_DECLINED",
    "COULD_NOT_REACH",
    "OUTCOME_UNKNOWN",
    "NO_LONGER_NEEDED",
    "DUPLICATE",
    "RECORDED_IN_ERROR",
]
AppointmentReason = Literal["FAMILY_REQUEST", "FACILITY_UNAVAILABLE", "STAFF_UNAVAILABLE", "PLAN_CHANGED", "OTHER"]


# --- Dating -------------------------------------------------------------------


class DatingIn(BaseModel):
    lmp_date: date | None = None
    edd: date | None = None
    precision: DatingPrecision
    evidence: DatingEvidence

    @model_validator(mode="after")
    def _needs_a_date(self) -> "DatingIn":
        # Unknown dating is recorded by not creating an entry at all.
        if self.lmp_date is None and self.edd is None:
            raise ValueError("give lmp_date or edd; if neither is known, record nothing")
        return self


class DatingCorrectionIn(DatingIn):
    expected_version: int


class DatingConfirmIn(BaseModel):
    dating_id: str
    expected_version: int


class DatingOut(BaseModel):
    id: str
    lmp_date: date | None
    edd: date | None
    precision: DatingPrecision
    evidence: DatingEvidence
    state: str
    recorded_by_name: str | None
    confirmed_by_name: str | None
    confirmed_at: datetime | None
    superseded_at: datetime | None
    created_at: datetime
    version: int


class DatingHistoryOut(BaseModel):
    current: DatingOut | None  # None = unknown
    history: list[DatingOut]


# --- Templates and plans -----------------------------------------------------


class TemplateItemOut(BaseModel):
    id: str
    position: int
    name: str
    kind: str
    timing_basis: str
    offset_days: int | None
    week_from: int | None
    week_to: int | None
    performer_role: str | None
    preparation_text: str | None


class TemplateOut(BaseModel):
    id: str
    name: str
    version_label: str
    is_placeholder: bool
    approved_by_name: str | None
    approved_on: date | None
    items: list[TemplateItemOut]


class PublishPlanIn(BaseModel):
    template_id: str


class CarePlanOut(BaseModel):
    id: str
    episode_id: str
    template: TemplateOut
    status: str
    published_by_name: str | None
    published_at: datetime
    version: int
    # Items not scheduled because they are timed by pregnancy week and no
    # approved rule for converting dates to weeks exists yet (D05).
    unscheduled_item_names: list[str] = []


# --- Appointments ----------------------------------------------------------------


class AppointmentOut(BaseModel):
    id: str
    episode_id: str
    care_plan_id: str | None
    name: str | None
    status: AppointmentStatus
    requested_for: date | None
    confirmed_for: datetime | None
    location_note: str | None
    owner_staff_user_id: str | None
    previous_appointment_id: str | None
    status_reason: str | None
    version: int


class AppointmentTransitionIn(BaseModel):
    to: Literal["CONFIRMED", "ATTENDED", "MISSED", "CANCELLED"]
    expected_version: int
    confirmed_for: datetime | None = None
    location_note: str | None = Field(default=None, max_length=300)
    reason: AppointmentReason | None = None

    @model_validator(mode="after")
    def _confirm_needs_time(self) -> "AppointmentTransitionIn":
        if self.to == "CONFIRMED" and self.confirmed_for is None:
            raise ValueError("confirming needs the actual date and time (confirmed_for)")
        return self


class RescheduleIn(BaseModel):
    expected_version: int
    requested_for: date
    reason: AppointmentReason | None = None


class RescheduleOut(BaseModel):
    previous: AppointmentOut
    new: AppointmentOut


# --- Tasks -------------------------------------------------------------------------


class TaskOut(BaseModel):
    id: str
    episode_id: str
    mother_full_name: str
    name: str | None
    kind: str
    status: str
    owner_staff_user_id: str | None
    owner_name: str | None
    backup_staff_user_id: str | None
    due_at: datetime | None
    # Administrative only: past due and not closed. Never a clinical signal.
    overdue: bool
    source_appointment_id: str | None
    last_attempt_at: datetime | None
    barrier: str | None
    outcome: str | None
    closure_reason: str | None
    closed_at: datetime | None
    version: int


class TaskAssignIn(BaseModel):
    expected_version: int
    owner_staff_user_id: str
    backup_staff_user_id: str | None = None


class TaskAttemptIn(BaseModel):
    expected_version: int
    awaiting_patient: bool = False
    barrier: Barrier | None = None


class TaskCloseIn(BaseModel):
    expected_version: int
    outcome: TaskOutcome
    closure_reason: ClosureReason
