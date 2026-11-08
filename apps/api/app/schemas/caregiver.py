from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.caregiver import CaregiverScope, RevokeReason, VerificationMethod


class CaregiverGrantIn(BaseModel):
    grantee_person_id: str
    scopes: list[CaregiverScope] = Field(min_length=1)
    verification_method: VerificationMethod
    # Last day the grant is valid (inclusive). Default: 90 days (D07 proposal).
    expires_on: date | None = None
    # Staff confirm the mother gave this consent herself, in front of them.
    consent_confirmed: bool


class CaregiverRevokeIn(BaseModel):
    expected_version: int
    reason: RevokeReason


class CaregiverGrantOut(BaseModel):
    id: str
    subject_person_id: str
    grantee_person_id: str
    grantee_full_name: str
    scopes: list[CaregiverScope]
    verification_method: VerificationMethod
    recorded_by_name: str | None
    verified_by_name: str | None
    created_at: datetime
    expires_at: datetime
    # Last local calendar day the grant is valid (what screens should show).
    expires_on: date
    revoked_at: datetime | None
    revoked_by_name: str | None
    revoke_reason: RevokeReason | None
    # ACTIVE, EXPIRED or REVOKED, computed at the time of the request.
    state: str
    version: int
