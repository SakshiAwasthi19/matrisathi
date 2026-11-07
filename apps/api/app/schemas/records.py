from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.models.records import (
    CorrectionReason,
    ObservationKind,
    ObservationSource,
    PrescriptionSource,
    ReferralClosureReason,
    ReferralUrgency,
    ServiceType,
)

# --- Investigations / reports (F009) ---------------------------------------------


class InvestigationIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    requested_on: date | None = None
    # An outside report that arrives with no known request: recorded as
    # received straight away; earlier dates stay unknown.
    received_file_id: str | None = None
    source: Literal["ORDERED_HERE", "OUTSIDE_REPORT"] = "ORDERED_HERE"


class InvestigationStepIn(BaseModel):
    expected_version: int
    performed_on: date | None = None  # for "performed"; may be unknown
    file_id: str | None = None  # for "received"


class InvestigationOut(BaseModel):
    id: str
    episode_id: str
    name: str
    status: str
    requested_on: date | None
    performed_on: date | None
    received_at: datetime | None
    source: str | None
    file_id: str | None
    reviewed_at: datetime | None
    reviewed_by_name: str | None
    version: int


# --- Prescriptions (F010) -------------------------------------------------------


class PrescriptionIn(BaseModel):
    source: PrescriptionSource
    source_file_id: str | None = None
    issued_on: date | None = None


class PrescriptionReviewIn(BaseModel):
    expected_version: int
    decision: Literal["CONFIRMED", "UNCLEAR"]
    # The instruction exactly as written on the original, transcribed by
    # the clinician. Never generated, never rewritten into doses.
    confirmed_instruction: str | None = Field(default=None, max_length=2000)
    reminder_enabled: bool = False
    reminder_start: date | None = None
    reminder_end: date | None = None

    @model_validator(mode="after")
    def _rules(self) -> "PrescriptionReviewIn":
        if self.decision == "CONFIRMED" and not (self.confirmed_instruction or "").strip():
            raise ValueError("a confirmed instruction must be transcribed as written")
        if self.decision == "UNCLEAR" and (self.confirmed_instruction or self.reminder_enabled):
            raise ValueError("an unclear instruction cannot carry text or a reminder")
        if self.reminder_start and self.reminder_end and self.reminder_end < self.reminder_start:
            raise ValueError("reminder_end is before reminder_start")
        return self


class PrescriptionOut(BaseModel):
    id: str
    episode_id: str
    source: str
    source_file_id: str | None
    issued_on: date | None
    recorded_by_name: str | None
    instruction_status: str
    confirmed_instruction: str | None
    reviewed_by_name: str | None
    reviewed_at: datetime | None
    reminder_enabled: bool
    reminder_start: date | None
    reminder_end: date | None
    created_at: datetime
    version: int


# --- Observations (F012) ----------------------------------------------------------


class ObservationIn(BaseModel):
    kind: ObservationKind = ObservationKind.MEASUREMENT
    name: str = Field(min_length=1, max_length=100)
    value_text: str = Field(min_length=1, max_length=500)
    unit: str | None = Field(default=None, max_length=30)
    observed_on: date | None = None
    source: ObservationSource


class ObservationCorrectionIn(ObservationIn):
    expected_version: int
    correction_reason: CorrectionReason


class ObservationOut(BaseModel):
    id: str
    episode_id: str
    kind: str
    name: str
    value_text: str
    unit: str | None
    observed_on: date | None
    source: str
    recorded_by_name: str | None
    corrects_id: str | None
    correction_reason: str | None
    superseded_at: datetime | None
    created_at: datetime
    version: int


# --- Local contacts (F044) ----------------------------------------------------------


class LocalContactIn(BaseModel):
    facility_id: str
    service_type: ServiceType
    name: str = Field(min_length=1, max_length=200)
    phone: str = Field(min_length=3, max_length=32)
    alternate_phone: str | None = Field(default=None, max_length=32)
    landmarks: str | None = Field(default=None, max_length=300)
    availability_note: str | None = Field(default=None, max_length=200)


class LocalContactVerifyIn(BaseModel):
    expected_version: int


class LocalContactOut(BaseModel):
    id: str
    facility_id: str
    service_type: str
    name: str
    phone: str
    alternate_phone: str | None
    landmarks: str | None
    availability_note: str | None
    verified_by_name: str | None
    verified_on: date
    # Administrative: not re-verified within the stale period.
    stale: bool
    version: int


# --- Referrals (F011) ------------------------------------------------------------------


class ReferralIn(BaseModel):
    destination_contact_id: str | None = None
    destination_name: str | None = Field(default=None, max_length=200)
    urgency: ReferralUrgency
    clinician_instruction: str | None = Field(default=None, max_length=2000)
    owner_staff_user_id: str | None = None

    @model_validator(mode="after")
    def _destination(self) -> "ReferralIn":
        if not self.destination_contact_id and not (self.destination_name or "").strip():
            raise ValueError("choose a verified contact or name the destination")
        return self


class ReferralStepIn(BaseModel):
    expected_version: int
    to: Literal["CONTACTED", "ATTENDED", "ADVICE_RECEIVED", "FOLLOW_UP_COMPLETED", "CLOSED"]
    attended_on: date | None = None
    advice_file_id: str | None = None
    closure_reason: ReferralClosureReason | None = None

    @model_validator(mode="after")
    def _closure(self) -> "ReferralStepIn":
        if (self.to == "CLOSED") != (self.closure_reason is not None):
            raise ValueError("closing needs a reason, and only closing takes one")
        return self


class ReferralOut(BaseModel):
    id: str
    episode_id: str
    destination_contact_id: str | None
    destination_name: str | None
    urgency: str
    clinician_instruction: str | None
    referred_by_name: str | None
    owner_staff_user_id: str
    owner_name: str | None
    status: str
    contacted_at: datetime | None
    attended_on: date | None
    advice_received_at: datetime | None
    advice_file_id: str | None
    follow_up_completed_at: datetime | None
    closure_reason: str | None
    closed_at: datetime | None
    created_at: datetime
    version: int
