from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class MembershipOut(BaseModel):
    facility_id: str
    facility_name: str
    role: str
    # What this role may do at this facility (app/domain/permissions.py).
    # For hiding buttons only: the server checks every action itself.
    capabilities: list[str] = []


class AdminOrganizationOut(BaseModel):
    id: str
    name: str


class StaffOut(BaseModel):
    id: str
    username: str
    full_name: str
    memberships: list[MembershipOut] = []
    # Organisations this user administers (explicit grant; gives no record access).
    admin_organizations: list[AdminOrganizationOut] = []
