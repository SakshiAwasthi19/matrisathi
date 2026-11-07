from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.birth_plan import AppointmentFamilyReport, FamilyReport
from app.schemas.care import Barrier


class HelpContactOut(BaseModel):
    id: str
    service_type: str
    name: str
    phone: str
    alternate_phone: str | None
    landmarks: str | None
    verified_on: str
    stale: bool


class NextActionOut(BaseModel):
    """The single next confirmed action, or an honest "none"."""

    state: Literal["CONFIRMED", "NONE"]
    appointment_id: str | None
    name: str | None
    confirmed_for: datetime | None
    location_note: str | None
    preparation_text: str | None
    is_placeholder: bool
    family_report: AppointmentFamilyReport | None
    family_reported_at: datetime | None
    # Requested but not yet confirmed by a person: shown as a count, never as a date.
    unconfirmed_requests: int
    help_contacts: list[HelpContactOut]
    version: int | None


class AppointmentFamilyReportIn(BaseModel):
    expected_version: int
    report: AppointmentFamilyReport
    barrier: Barrier | None = None


class BirthPlanIn(BaseModel):
    expected_version: int  # 0 when no plan exists yet
    chosen_birth_place_contact_id: str | None = None
    chosen_birth_place_note: str | None = Field(default=None, max_length=200)
    referral_site_contact_id: str | None = None  # clinician-only
    companion_name: str | None = Field(default=None, max_length=200)
    transport_arrangement: str | None = Field(default=None, max_length=300)
    landmarks: str | None = Field(default=None, max_length=300)
    primary_contact_id: str | None = None
    alternate_contact_id: str | None = None


class BirthPlanFamilyReportIn(BaseModel):
    expected_version: int
    report: FamilyReport
    barrier: Barrier | None = None


class BirthPlanVerifyIn(BaseModel):
    expected_version: int


class BirthPlanOut(BaseModel):
    id: str
    episode_id: str
    chosen_birth_place: HelpContactOut | None
    chosen_birth_place_note: str | None
    referral_site: HelpContactOut | None
    referral_site_set_by_name: str | None
    companion_name: str | None
    transport_arrangement: str | None
    landmarks: str | None
    primary_contact: HelpContactOut | None
    alternate_contact: HelpContactOut | None
    family_report: FamilyReport | None
    family_reported_at: datetime | None
    staff_verified_by_name: str | None
    staff_verified_at: datetime | None
    updated_at: datetime
    version: int
