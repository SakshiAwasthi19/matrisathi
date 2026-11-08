"""Organisation administration (F004) and the organisation audit view (F037).

Every route needs an explicit OrganizationAdmin grant for the organisation
concerned. That grant never gives access to mothers' records, and nothing here
returns clinical content: the audit view lists who did what, when, and the
outcome, with record ids rather than names.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import find_active_membership, get_current_staff, require_csrf_header, require_org_admin
from app.core.security import hash_password
from app.models.audit import AuditEvent, AuditOutcome
from app.models.facility import Facility
from app.models.organization import OrganizationAdmin
from app.models.staff import StaffMembership, StaffUser
from app.schemas.admin import (
    AuditEventOut,
    AuditPage,
    FacilityCreate,
    FacilityOut,
    MembershipGrant,
    MembershipOut,
    OrgMembershipOut,
    OrgStaffOut,
    RoleChange,
    StaffCreate,
    StaffCreateOut,
)
from app.services import audit_service

router = APIRouter(tags=["admin"])

AUDIT_PAGE_MAX = 100
# Audit metadata keys safe to show an administrator. Everything else (counts,
# ids of other records, typed usernames) stays in the database only.
_SAFE_AUDIT_DETAIL_KEYS = ("reason",)


def _id(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found") from None


def _audit(actor: StaffUser, action: str, entity_type: str, entity_id: object, **metadata: object) -> None:
    audit_service.record_event(
        actor_staff_user_id=actor.id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        outcome=AuditOutcome.SUCCESS,
        metadata=metadata,
    )


def _facility_out(f: Facility) -> FacilityOut:
    return FacilityOut(id=str(f.id), organization_id=str(f.organization_id), name=f.name, active=f.active)


def _membership_out(m: StaffMembership) -> MembershipOut:
    return MembershipOut(
        id=str(m.id), staff_user_id=str(m.staff_user_id), facility_id=str(m.facility_id), role=m.role, active=m.active
    )


def _facility_in_org(db: Session, staff: StaffUser, facility_id: str) -> Facility:
    facility = db.get(Facility, _id(facility_id))
    if facility is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    require_org_admin(db, staff, facility.organization_id)
    return facility


def _grant(db: Session, staff_user_id: uuid.UUID, facility: Facility, role: object) -> StaffMembership:
    """New active membership; one active membership per person per facility."""
    if find_active_membership(db, staff_user_id, facility.id) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="This person already works at this facility. Change their role instead.",
        )
    membership = StaffMembership(staff_user_id=staff_user_id, facility_id=facility.id, role=role, active=True)
    db.add(membership)
    return membership


# --- Facilities -------------------------------------------------------------------------


@router.get("/organizations/{organization_id}/facilities", response_model=list[FacilityOut])
def list_facilities(
    organization_id: str, db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)
) -> list[FacilityOut]:
    org_id = _id(organization_id)
    require_org_admin(db, staff, org_id)
    rows = db.execute(select(Facility).where(Facility.organization_id == org_id).order_by(Facility.name)).scalars()
    return [_facility_out(f) for f in rows]


@router.post(
    "/organizations/{organization_id}/facilities", response_model=FacilityOut, status_code=status.HTTP_201_CREATED
)
def create_facility(
    organization_id: str,
    body: FacilityCreate,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
    _csrf: None = Depends(require_csrf_header),
) -> FacilityOut:
    org_id = _id(organization_id)
    # Organization-admin authority is required and is never inferred from a
    # facility-level StaffMembership role (see app/models/organization.py).
    require_org_admin(db, staff, org_id)

    facility = Facility(organization_id=org_id, name=body.name, active=True)
    db.add(facility)
    db.commit()
    _audit(staff, "create", "Facility", facility.id, organization_id=str(org_id))
    return _facility_out(facility)


# --- Staff ------------------------------------------------------------------------------


@router.get("/organizations/{organization_id}/staff", response_model=list[OrgStaffOut])
def list_staff(
    organization_id: str,
    include_revoked: bool = Query(default=False),
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
) -> list[OrgStaffOut]:
    """Everyone who works (or worked, with include_revoked) at a facility of
    this organisation, with their memberships here. Memberships elsewhere are
    not shown."""
    org_id = _id(organization_id)
    require_org_admin(db, staff, org_id)
    query = (
        select(StaffMembership, Facility, StaffUser)
        .join(Facility, Facility.id == StaffMembership.facility_id)
        .join(StaffUser, StaffUser.id == StaffMembership.staff_user_id)
        .where(Facility.organization_id == org_id)
        .order_by(StaffUser.full_name, Facility.name, StaffMembership.created_at)
    )
    if not include_revoked:
        query = query.where(StaffMembership.active.is_(True), StaffMembership.revoked_at.is_(None))
    people: dict[uuid.UUID, OrgStaffOut] = {}
    for m, f, u in db.execute(query).all():
        entry = people.setdefault(
            u.id, OrgStaffOut(id=str(u.id), username=u.username, full_name=u.full_name, active=u.active, memberships=[])
        )
        entry.memberships.append(
            OrgMembershipOut(
                id=str(m.id),
                facility_id=str(f.id),
                facility_name=f.name,
                role=m.role,
                active=m.active and m.revoked_at is None,
                granted_at=m.created_at,
                revoked_at=m.revoked_at,
            )
        )
    _audit(staff, "list_staff", "Organization", org_id, count=len(people))
    return list(people.values())


@router.post("/staff", response_model=StaffCreateOut, status_code=status.HTTP_201_CREATED)
def create_staff(
    body: StaffCreate,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
    _csrf: None = Depends(require_csrf_header),
) -> StaffCreateOut:
    org_id = _id(body.organization_id)
    # Creating staff accounts is an organization-administrative action, gated
    # the same way facility creation is — not by any facility-level role.
    require_org_admin(db, staff, org_id)

    facility: Facility | None = None
    if body.facility_id is not None:
        facility = db.get(Facility, _id(body.facility_id))
        if facility is None or facility.organization_id != org_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
        if body.role is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Choose a role for the facility.")

    if db.query(StaffUser).filter(StaffUser.username == body.username).first() is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Username already in use")

    new_staff = StaffUser(
        username=body.username,
        full_name=body.full_name,
        phone=None,
        password_hash=hash_password(body.password),
        active=True,
    )
    db.add(new_staff)
    db.flush()
    membership = _grant(db, new_staff.id, facility, body.role) if facility is not None else None
    # Account and first membership commit together, so a failure never leaves
    # an account nobody can see in the staff list.
    db.commit()

    _audit(staff, "create", "StaffUser", new_staff.id, organization_id=str(org_id))
    if membership is not None and facility is not None:
        _audit(staff, "grant", "StaffMembership", membership.id, facility_id=str(facility.id), staff_user_id=str(new_staff.id))
    return StaffCreateOut(id=str(new_staff.id), username=new_staff.username, full_name=new_staff.full_name)


# --- Memberships ------------------------------------------------------------------------


@router.post(
    "/facilities/{facility_id}/memberships", response_model=MembershipOut, status_code=status.HTTP_201_CREATED
)
def grant_membership(
    facility_id: str,
    body: MembershipGrant,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
    _csrf: None = Depends(require_csrf_header),
) -> MembershipOut:
    facility = _facility_in_org(db, staff, facility_id)
    target = db.get(StaffUser, _id(body.staff_user_id))
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")

    membership = _grant(db, target.id, facility, body.role)
    db.commit()
    _audit(staff, "grant", "StaffMembership", membership.id, facility_id=str(facility.id), staff_user_id=str(target.id))
    return _membership_out(membership)


@router.post("/facilities/{facility_id}/memberships/{membership_id}/role", response_model=MembershipOut)
def change_role(
    facility_id: str,
    membership_id: str,
    body: RoleChange,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
    _csrf: None = Depends(require_csrf_header),
) -> MembershipOut:
    """A role change ends the old membership and starts a new one in one
    transaction, so the history shows which role someone held, and when."""
    facility = _facility_in_org(db, staff, facility_id)
    old = db.get(StaffMembership, _id(membership_id))
    if old is None or old.facility_id != facility.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    if not old.active or old.revoked_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="This membership has already ended.")
    if old.role == body.role:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="They already have this role.")

    old.active = False
    old.revoked_at = datetime.now(timezone.utc)
    db.flush()
    new = _grant(db, old.staff_user_id, facility, body.role)
    db.commit()
    _audit(
        staff, "change_role", "StaffMembership", new.id,
        facility_id=str(facility.id), previous_membership=str(old.id), role=body.role.value,
    )
    return _membership_out(new)


@router.delete("/facilities/{facility_id}/memberships/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_membership(
    facility_id: str,
    membership_id: str,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
    _csrf: None = Depends(require_csrf_header),
) -> None:
    facility = _facility_in_org(db, staff, facility_id)
    membership = db.get(StaffMembership, _id(membership_id))
    if membership is None or membership.facility_id != facility.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")

    membership.active = False
    membership.revoked_at = datetime.now(timezone.utc)
    db.commit()
    _audit(staff, "revoke", "StaffMembership", membership.id, facility_id=str(facility.id))


# --- Audit view (F037) ------------------------------------------------------------------


@router.get("/organizations/{organization_id}/audit", response_model=AuditPage)
def organization_audit(
    organization_id: str,
    limit: int = Query(default=50, ge=1, le=AUDIT_PAGE_MAX),
    before: datetime | None = Query(default=None, description="Return events older than this time"),
    outcome: AuditOutcome | None = Query(default=None),
    action: str | None = Query(default=None, max_length=100),
    actor_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
) -> AuditPage:
    """Who did what, when, and whether it was allowed, for actions taken by
    people who work (or worked) in this organisation or administer it.
    Newest first; page with `before` = the last event's time."""
    org_id = _id(organization_id)
    require_org_admin(db, staff, org_id)

    members = select(StaffMembership.staff_user_id).join(Facility, Facility.id == StaffMembership.facility_id).where(
        Facility.organization_id == org_id
    )
    admins = select(OrganizationAdmin.staff_user_id).where(OrganizationAdmin.organization_id == org_id)
    query = (
        select(AuditEvent, StaffUser)
        .join(StaffUser, StaffUser.id == AuditEvent.actor_staff_user_id)
        .where(or_(AuditEvent.actor_staff_user_id.in_(members), AuditEvent.actor_staff_user_id.in_(admins)))
    )
    if before is not None:
        query = query.where(AuditEvent.occurred_at < before)
    if outcome is not None:
        query = query.where(AuditEvent.outcome == outcome)
    if action:
        query = query.where(AuditEvent.action == action)
    if actor_id:
        query = query.where(and_(AuditEvent.actor_staff_user_id == _id(actor_id)))
    rows = db.execute(query.order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc()).limit(limit + 1)).all()

    events = [
        AuditEventOut(
            id=str(e.id),
            occurred_at=e.occurred_at,
            actor_id=str(u.id),
            actor_name=u.full_name,
            actor_username=u.username,
            action=e.action,
            entity_type=e.entity_type,
            entity_id=e.entity_id,
            outcome=e.outcome,
            details={k: str(e.metadata_json[k]) for k in _SAFE_AUDIT_DETAIL_KEYS if k in (e.metadata_json or {})},
        )
        for e, u in rows[:limit]
    ]
    # Looking at the audit trail is itself recorded (filters only, no results).
    _audit(
        staff, "view_audit", "Organization", org_id,
        outcome_filter=outcome.value if outcome else None, action_filter=action, count=len(events),
    )
    return AuditPage(events=events, has_more=len(rows) > limit)
