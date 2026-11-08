from datetime import datetime

from pydantic import BaseModel, Field

from app.models.audit import AuditOutcome
from app.models.staff import StaffRole


class FacilityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class FacilityOut(BaseModel):
    id: str
    organization_id: str
    name: str
    active: bool


class StaffCreate(BaseModel):
    organization_id: str
    username: str = Field(min_length=3, max_length=100)
    full_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=12, max_length=200)
    # Optional first membership, created in the same transaction as the account.
    facility_id: str | None = None
    role: StaffRole | None = None


class StaffCreateOut(BaseModel):
    id: str
    username: str
    full_name: str


class MembershipGrant(BaseModel):
    staff_user_id: str
    role: StaffRole


class MembershipOut(BaseModel):
    id: str
    staff_user_id: str
    facility_id: str
    role: StaffRole
    active: bool


class RoleChange(BaseModel):
    role: StaffRole


class OrgMembershipOut(BaseModel):
    id: str
    facility_id: str
    facility_name: str
    role: StaffRole
    active: bool
    granted_at: datetime
    revoked_at: datetime | None


class OrgStaffOut(BaseModel):
    id: str
    username: str
    full_name: str
    active: bool
    memberships: list[OrgMembershipOut]


class AuditEventOut(BaseModel):
    id: str
    occurred_at: datetime
    actor_id: str
    actor_name: str
    actor_username: str
    action: str
    entity_type: str
    entity_id: str | None
    outcome: AuditOutcome
    # Only allow-listed metadata (e.g. the denial reason); never clinical content.
    details: dict[str, str]


class AuditPage(BaseModel):
    events: list[AuditEventOut]
    has_more: bool
