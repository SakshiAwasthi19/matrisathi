from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.deps import get_current_staff, require_csrf_header
from app.core.security import (
    create_access_token,
    hash_refresh_token,
    new_refresh_token,
    verify_password,
)
from app.domain.permissions import capabilities_of
from app.models.audit import AuditOutcome
from app.models.facility import Facility
from app.models.organization import Organization, OrganizationAdmin
from app.models.staff import LoginAttempt, RefreshToken, StaffMembership, StaffUser
from app.schemas.auth import AdminOrganizationOut, LoginRequest, MembershipOut, StaffOut
from app.services import audit_service

router = APIRouter(prefix="/auth", tags=["auth"])

GENERIC_LOGIN_ERROR = "Invalid username or password"


def _staff_out(db: Session, staff: StaffUser) -> StaffOut:
    rows = (
        db.query(StaffMembership, Facility)
        .join(Facility, Facility.id == StaffMembership.facility_id)
        .filter(
            StaffMembership.staff_user_id == staff.id,
            StaffMembership.active.is_(True),
            StaffMembership.revoked_at.is_(None),
        )
        .all()
    )
    memberships = [
        MembershipOut(
            facility_id=str(f.id),
            facility_name=f.name,
            role=m.role.value,
            capabilities=sorted(c.value for c in capabilities_of([m.role.value])),
        )
        for m, f in rows
    ]
    admin_orgs = (
        db.query(Organization)
        .join(OrganizationAdmin, OrganizationAdmin.organization_id == Organization.id)
        .filter(OrganizationAdmin.staff_user_id == staff.id, OrganizationAdmin.revoked_at.is_(None))
        .order_by(Organization.name)
        .all()
    )
    return StaffOut(
        id=str(staff.id),
        username=staff.username,
        full_name=staff.full_name,
        memberships=memberships,
        admin_organizations=[AdminOrganizationOut(id=str(o.id), name=o.name) for o in admin_orgs],
    )


def _set_session_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        "access_token",
        access_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,  # type: ignore[arg-type]
        domain=settings.cookie_domain,
        max_age=settings.access_token_ttl_minutes * 60,
        path="/",
    )
    response.set_cookie(
        "refresh_token",
        refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,  # type: ignore[arg-type]
        domain=settings.cookie_domain,
        max_age=settings.refresh_token_ttl_days * 24 * 3600,
        # Scoped to the refresh/logout endpoints only, limiting exposure of
        # this longer-lived credential to the rest of the API surface.
        path="/api/v1/auth",
    )


def _clear_session_cookies(response: Response) -> None:
    response.delete_cookie("access_token", path="/", domain=settings.cookie_domain)
    response.delete_cookie("refresh_token", path="/api/v1/auth", domain=settings.cookie_domain)


def _recent_failed_attempts(db: Session, username: str) -> int:
    window_start = datetime.now(timezone.utc) - timedelta(
        minutes=settings.login_throttle_window_minutes
    )
    return (
        db.query(LoginAttempt)
        .filter(
            LoginAttempt.username == username,
            LoginAttempt.succeeded.is_(False),
            LoginAttempt.created_at >= window_start,
        )
        .count()
    )


@router.post("/login", response_model=StaffOut)
def login(
    body: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
    # CSRF header on login too: with SameSite=None cookies (cross-domain
    # staging), another site could otherwise submit a login form and sign
    # the victim's browser into an attacker-controlled account.
    _csrf: None = Depends(require_csrf_header),
) -> StaffOut:
    throttled = _recent_failed_attempts(db, body.username) >= settings.login_throttle_max_attempts

    staff = db.query(StaffUser).filter(StaffUser.username == body.username).first()
    valid = (
        not throttled
        and staff is not None
        and staff.active
        and verify_password(body.password, staff.password_hash)
    )

    if not valid:
        db.add(LoginAttempt(username=body.username, succeeded=False))
        db.commit()
        audit_service.record_event(
            actor_staff_user_id=staff.id if staff else None,
            action="login",
            entity_type="StaffUser",
            entity_id=str(staff.id) if staff else None,
            outcome=AuditOutcome.DENIED,
            metadata={"username": body.username, "throttled": throttled},
        )
        # Same status and message whether the username doesn't exist, the
        # password is wrong, the account is disabled, or throttling kicked
        # in — none of that is distinguishable from the response.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=GENERIC_LOGIN_ERROR)

    assert staff is not None  # `valid` is only True when staff was found above

    db.add(LoginAttempt(username=body.username, succeeded=True))
    db.commit()

    access_token = create_access_token(staff_user_id=str(staff.id))
    refresh_plain, refresh_hash = new_refresh_token()
    db.add(
        RefreshToken(
            staff_user_id=staff.id,
            token_hash=refresh_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_ttl_days),
        )
    )
    db.commit()

    _set_session_cookies(response, access_token, refresh_plain)
    audit_service.record_event(
        actor_staff_user_id=staff.id,
        action="login",
        entity_type="StaffUser",
        entity_id=str(staff.id),
        outcome=AuditOutcome.SUCCESS,
        metadata={},
    )
    return _staff_out(db, staff)


@router.post("/refresh", response_model=StaffOut)
def refresh(
    response: Response,
    db: Session = Depends(get_db),
    refresh_token: str | None = Cookie(default=None),
    # Without this, a cross-site POST could force a token rotation.
    _csrf: None = Depends(require_csrf_header),
) -> StaffOut:
    if refresh_token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    token_hash = hash_refresh_token(refresh_token)
    row = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()

    if row is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    if row.revoked_at is not None:
        # Reuse of an already-rotated-out refresh token: treat as a signal
        # of possible token theft and revoke every live session for this
        # user, not just this one token.
        db.query(RefreshToken).filter(
            RefreshToken.staff_user_id == row.staff_user_id,
            RefreshToken.revoked_at.is_(None),
        ).update({"revoked_at": datetime.now(timezone.utc)})
        db.commit()
        audit_service.record_event(
            actor_staff_user_id=row.staff_user_id,
            action="refresh_token_reuse_detected",
            entity_type="StaffUser",
            entity_id=str(row.staff_user_id),
            outcome=AuditOutcome.DENIED,
            metadata={},
        )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    if row.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    staff = db.get(StaffUser, row.staff_user_id)
    if staff is None or not staff.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    new_plain, new_hash = new_refresh_token()
    new_row = RefreshToken(
        staff_user_id=staff.id,
        token_hash=new_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_ttl_days),
    )
    db.add(new_row)
    db.flush()
    row.revoked_at = datetime.now(timezone.utc)
    row.replaced_by_id = new_row.id
    db.commit()

    access_token = create_access_token(staff_user_id=str(staff.id))
    _set_session_cookies(response, access_token, new_plain)
    return _staff_out(db, staff)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    db: Session = Depends(get_db),
    refresh_token: str | None = Cookie(default=None),
    _csrf: None = Depends(require_csrf_header),
    staff: StaffUser = Depends(get_current_staff),
) -> None:
    if refresh_token is not None:
        token_hash = hash_refresh_token(refresh_token)
        row = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
        if row is not None and row.revoked_at is None:
            row.revoked_at = datetime.now(timezone.utc)
            db.commit()
    _clear_session_cookies(response)
    audit_service.record_event(
        actor_staff_user_id=staff.id,
        action="logout",
        entity_type="StaffUser",
        entity_id=str(staff.id),
        outcome=AuditOutcome.SUCCESS,
        metadata={},
    )


@router.get("/me", response_model=StaffOut)
def me(db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)) -> StaffOut:
    return _staff_out(db, staff)
