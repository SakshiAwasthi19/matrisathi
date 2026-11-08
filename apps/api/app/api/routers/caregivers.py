"""Family access grants, managed by staff (F015, T010; D07 option 3).

There is no patient or caregiver sign-in. A grant records that a mother, in
front of staff, allowed one adult to receive specific things (her next step,
her birth plan, reminders). Staff use it to decide what they may tell or
send to whom; the check is `caregiver_may_receive`.

Rules enforced here:
- the mother and the caregiver are separate person records, both registered
  at a facility the caller works at (a phone number is never an identity);
- consent and in-person verification are recorded, with who and how;
- one active grant per mother and caregiver; changes revoke and re-grant;
- grants are never deleted: revocation keeps the history.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routers.care import _local_tz, _start_of_local_day, _today
from app.core.db import get_db
from app.core.deps import get_current_staff, require_csrf_header, require_facility_membership
from app.domain.permissions import DENIED_MESSAGE, Capability, has_capability
from app.models.audit import AuditOutcome
from app.models.caregiver import CaregiverGrant, CaregiverScope
from app.models.identity import Person
from app.models.staff import StaffMembership, StaffUser
from app.schemas.caregiver import CaregiverGrantIn, CaregiverGrantOut, CaregiverRevokeIn
from app.services import audit_service
from app.services.caregiver_access import grant_state

router = APIRouter(tags=["caregivers"])

DEFAULT_GRANT_DAYS = 90  # D07 proposal; the manager may change it
MAX_GRANT_DAYS = 366


def _id(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found") from None


def _audit(staff: StaffUser, action: str, entity_id: object, outcome: AuditOutcome = AuditOutcome.SUCCESS, **meta: object) -> None:
    audit_service.record_event(
        actor_staff_user_id=staff.id,
        action=action,
        entity_type="CaregiverGrant",
        entity_id=str(entity_id) if entity_id is not None else None,
        outcome=outcome,
        metadata=meta,
    )


def _accessible_person(db: Session, staff: StaffUser, person_id: str, action: str) -> tuple[Person, StaffMembership]:
    """The person, if the caller works at her registering facility; else 404."""
    person = db.get(Person, _id(person_id))
    if person is None:
        _audit(staff, action, None, AuditOutcome.DENIED, reason="not_found")
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    try:
        membership = require_facility_membership(db, staff, person.registering_facility_id)
    except HTTPException:
        _audit(staff, action, None, AuditOutcome.DENIED, reason="not_authorized", person_id=str(person.id))
        raise
    return person, membership


def _require_manage(staff: StaffUser, membership: StaffMembership, action: str) -> None:
    if not has_capability([membership.role.value], Capability.MANAGE_CAREGIVER_GRANTS):
        _audit(staff, action, None, AuditOutcome.DENIED, reason="role_not_permitted")
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=DENIED_MESSAGE[Capability.MANAGE_CAREGIVER_GRANTS])


def _name(db: Session, staff_id: uuid.UUID | None) -> str | None:
    if staff_id is None:
        return None
    s = db.get(StaffUser, staff_id)
    return s.full_name if s else None


def _last_local_day(expires_at: datetime) -> date:
    """The last local calendar day on which the grant is valid."""
    return (expires_at - timedelta(microseconds=1)).astimezone(_local_tz()).date()


def _out(db: Session, g: CaregiverGrant, now: datetime) -> CaregiverGrantOut:
    grantee = db.get(Person, g.grantee_person_id)
    return CaregiverGrantOut(
        id=str(g.id),
        subject_person_id=str(g.subject_person_id),
        grantee_person_id=str(g.grantee_person_id),
        grantee_full_name=grantee.full_name if grantee else "",
        scopes=[CaregiverScope(s) for s in g.scopes],
        verification_method=g.verification_method,
        recorded_by_name=_name(db, g.recorded_by_staff_user_id),
        verified_by_name=_name(db, g.verified_by_staff_user_id),
        created_at=g.created_at,
        expires_at=g.expires_at,
        expires_on=_last_local_day(g.expires_at),
        revoked_at=g.revoked_at,
        revoked_by_name=_name(db, g.revoked_by_staff_user_id),
        revoke_reason=g.revoke_reason,
        state=grant_state(g, now),
        version=g.version,
    )


@router.get("/people/{person_id}/caregiver-grants", response_model=list[CaregiverGrantOut])
def list_grants(person_id: str, db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)) -> list[CaregiverGrantOut]:
    """Every grant the mother has given, active first, with its history."""
    subject, _ = _accessible_person(db, staff, person_id, "list_caregiver_grants")
    now = datetime.now(timezone.utc)
    rows = db.execute(
        select(CaregiverGrant).where(CaregiverGrant.subject_person_id == subject.id).order_by(CaregiverGrant.created_at.desc())
    ).scalars().all()
    out = sorted((_out(db, g, now) for g in rows), key=lambda g: g.state != "ACTIVE")
    _audit(staff, "list_caregiver_grants", None, person_id=str(subject.id), count=len(out))
    return out


@router.post("/people/{person_id}/caregiver-grants", response_model=CaregiverGrantOut, status_code=status.HTTP_201_CREATED)
def create_grant(
    person_id: str,
    body: CaregiverGrantIn,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
    _csrf: None = Depends(require_csrf_header),
) -> CaregiverGrantOut:
    subject, membership = _accessible_person(db, staff, person_id, "grant_caregiver")
    _require_manage(staff, membership, "grant_caregiver")
    # The caregiver is a person in her own right, and must be reachable by
    # the caller too: an id the caller cannot see cannot be linked in.
    grantee, _ = _accessible_person(db, staff, body.grantee_person_id, "grant_caregiver")
    if grantee.id == subject.id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A mother cannot be her own caregiver.")
    if not body.consent_confirmed:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Record that the mother gave this consent herself, in front of you."
        )

    now = datetime.now(timezone.utc)
    today = _today()  # the facility's local calendar day, not UTC
    expires_on = body.expires_on or (today + timedelta(days=DEFAULT_GRANT_DAYS))
    if expires_on < today:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The end date has already passed.")
    if expires_on > today + timedelta(days=MAX_GRANT_DAYS):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A grant can last at most one year; renew it after that.")

    existing = db.execute(
        select(CaregiverGrant).where(
            CaregiverGrant.subject_person_id == subject.id,
            CaregiverGrant.grantee_person_id == grantee.id,
            CaregiverGrant.revoked_at.is_(None),
            CaregiverGrant.expires_at > now,
        )
    ).first()
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="This person already has access. End it first to change what they receive."
        )

    grant = CaregiverGrant(
        subject_person_id=subject.id,
        grantee_person_id=grantee.id,
        scopes=sorted({s.value for s in body.scopes}),
        recorded_by_staff_user_id=staff.id,
        verified_by_staff_user_id=staff.id,
        verification_method=body.verification_method,
        # Valid through the whole of the last local day: it ends at the
        # start of the next local day.
        expires_at=_start_of_local_day(expires_on + timedelta(days=1)),
    )
    db.add(grant)
    db.commit()
    _audit(
        staff, "grant_caregiver", grant.id,
        person_id=str(subject.id), grantee_person_id=str(grantee.id), scopes=grant.scopes,
        verification=body.verification_method.value,
    )
    return _out(db, grant, now)


@router.post("/caregiver-grants/{grant_id}/revoke", response_model=CaregiverGrantOut)
def revoke_grant(
    grant_id: str,
    body: CaregiverRevokeIn,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
    _csrf: None = Depends(require_csrf_header),
) -> CaregiverGrantOut:
    grant = db.get(CaregiverGrant, _id(grant_id))
    if grant is None:
        _audit(staff, "revoke_caregiver", grant_id, AuditOutcome.DENIED, reason="not_found")
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    _, membership = _accessible_person(db, staff, str(grant.subject_person_id), "revoke_caregiver")
    _require_manage(staff, membership, "revoke_caregiver")
    if grant.version != body.expected_version:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="This record was changed by someone else. Reload it and try again.")
    if grant.revoked_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="This access has already been ended.")

    now = datetime.now(timezone.utc)
    grant.revoked_at = now
    grant.revoked_by_staff_user_id = staff.id
    grant.revoke_reason = body.reason
    grant.version += 1
    db.commit()
    _audit(staff, "revoke_caregiver", grant.id, person_id=str(grant.subject_person_id), reason=body.reason.value)
    return _out(db, grant, now)
