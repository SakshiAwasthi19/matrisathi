import uuid

import jwt
from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.security import decode_access_token
from app.models.facility import Facility
from app.models.organization import OrganizationAdmin
from app.models.staff import StaffMembership, StaffUser


def get_current_staff(
    db: Session = Depends(get_db),
    access_token: str | None = Cookie(default=None),
) -> StaffUser:
    """Resolves the caller from the access-token cookie and re-checks the
    StaffUser's `active` flag against the database on every call — a
    disabled user loses access immediately, not merely at token expiry.
    """
    if access_token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_access_token(access_token)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated") from None

    staff_user_id = payload.get("sub")
    staff = db.get(StaffUser, uuid.UUID(staff_user_id)) if staff_user_id else None
    if staff is None or not staff.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return staff


def require_csrf_header(request: Request) -> None:
    """Minimal CSRF mitigation for the cookie-based session.

    Auth rides on httpOnly cookies (see core/security.py + routers/auth.py),
    so a classic cross-site form submission would otherwise carry the
    cookie automatically. Requiring this custom header on every mutating
    request blocks that: a plain cross-site form post cannot set a custom
    header, and a cross-origin script attempting to via fetch() is blocked
    by CORS before the request is even sent (see main.py CORS config,
    which allows only the configured frontend origin with credentials).
    """
    value = request.headers.get(settings.csrf_header_name)
    if value != settings.csrf_header_value:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Missing or invalid CSRF header")


def find_active_membership(
    db: Session, staff_user_id: uuid.UUID, facility_id: uuid.UUID
) -> StaffMembership | None:
    return (
        db.query(StaffMembership)
        .filter(
            StaffMembership.staff_user_id == staff_user_id,
            StaffMembership.facility_id == facility_id,
            StaffMembership.active.is_(True),
            StaffMembership.revoked_at.is_(None),
        )
        .first()
    )


def require_facility_membership(db: Session, staff: StaffUser, facility_id: uuid.UUID) -> StaffMembership:
    """Facility-scoped access check, per request, against live membership
    state — never cached at login. Raises 404 (not 403) on denial: a 403
    would confirm the record/facility exists but is someone else's, which
    leaks cross-facility/cross-organization existence information.
    """
    membership = find_active_membership(db, staff.id, facility_id)
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    return membership


def require_active_facility(db: Session, facility_id: uuid.UUID) -> Facility:
    facility = db.get(Facility, facility_id)
    if facility is None or not facility.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    return facility


def require_org_admin(db: Session, staff: StaffUser, organization_id: uuid.UUID) -> OrganizationAdmin:
    """Organization-wide administrative authority is a distinct, explicit
    grant (OrganizationAdmin) — never inferred from a StaffMembership role
    at some facility the caller happens to belong to.
    """
    grant = (
        db.query(OrganizationAdmin)
        .filter(
            OrganizationAdmin.staff_user_id == staff.id,
            OrganizationAdmin.organization_id == organization_id,
            OrganizationAdmin.revoked_at.is_(None),
        )
        .first()
    )
    if grant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    return grant


def roles_at_facility(db: Session, staff: StaffUser, facility_id: uuid.UUID) -> list[str]:
    """The caller's live roles at one facility (empty if not a member)."""
    rows = (
        db.query(StaffMembership.role)
        .filter(
            StaffMembership.staff_user_id == staff.id,
            StaffMembership.facility_id == facility_id,
            StaffMembership.active.is_(True),
            StaffMembership.revoked_at.is_(None),
        )
        .all()
    )
    return [r[0].value for r in rows]
