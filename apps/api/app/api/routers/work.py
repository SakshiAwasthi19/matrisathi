"""Team workload and handover of open work (F038, with F008's backup rule).

When someone is unavailable, their open tasks move to a named colleague in
one step, so no follow-up is left without an owner. Figures are
administrative (who holds how much work), never clinical priority.
"""

import enum
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import find_active_membership, get_current_staff, require_csrf_header, require_facility_membership
from app.domain.permissions import DENIED_MESSAGE, Capability, has_capability
from app.models.audit import AuditOutcome
from app.models.care import CareTask, TaskStatus
from app.models.staff import StaffMembership, StaffUser
from app.services import audit_service

router = APIRouter(tags=["work"])

OPEN = (TaskStatus.NEW, TaskStatus.ASSIGNED, TaskStatus.AWAITING_PATIENT)


class HandoverReason(str, enum.Enum):
    # A fixed list: no free text, so nothing private lands in the record.
    ON_LEAVE = "ON_LEAVE"
    UNAVAILABLE_TODAY = "UNAVAILABLE_TODAY"
    LEFT_FACILITY = "LEFT_FACILITY"
    BALANCING_WORKLOAD = "BALANCING_WORKLOAD"


class PersonLoad(BaseModel):
    staff_user_id: str
    full_name: str
    role: str | None  # None: no longer works here but still holds open work
    works_here: bool
    owned_open: int
    owned_overdue: int
    backup_open: int


class Workload(BaseModel):
    facility_id: str
    unowned_open: int
    people: list[PersonLoad]
    as_of: datetime


class HandoverIn(BaseModel):
    from_staff_user_id: str
    to_staff_user_id: str
    reason: HandoverReason
    # Also move tasks where the person is the backup (default: yes).
    include_backup: bool = True


class HandoverOut(BaseModel):
    owner_moved: int
    backup_moved: int


def _id(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found") from None


def _audit(staff: StaffUser, action: str, entity_type: str, entity_id: object, outcome: AuditOutcome = AuditOutcome.SUCCESS, **meta: object) -> None:
    audit_service.record_event(
        actor_staff_user_id=staff.id, action=action, entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None, outcome=outcome, metadata=meta,
    )


def _member(db: Session, staff: StaffUser, facility_id: uuid.UUID, action: str) -> StaffMembership:
    try:
        return require_facility_membership(db, staff, facility_id)
    except HTTPException:
        _audit(staff, action, "Facility", facility_id, AuditOutcome.DENIED, reason="not_authorized")
        raise


@router.get("/facilities/{facility_id}/workload", response_model=Workload)
def facility_workload(facility_id: str, db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)) -> Workload:
    fid = _id(facility_id)
    _member(db, staff, fid, "view_workload")
    now = datetime.now(timezone.utc)
    tasks = db.execute(select(CareTask).where(CareTask.facility_id == fid, CareTask.status.in_(OPEN))).scalars().all()

    current = {
        m.staff_user_id: m.role.value
        for m in db.execute(
            select(StaffMembership).where(
                StaffMembership.facility_id == fid, StaffMembership.active.is_(True), StaffMembership.revoked_at.is_(None)
            )
        ).scalars()
    }
    holders = {t.owner_staff_user_id for t in tasks} | {t.backup_staff_user_id for t in tasks}
    ids: set[uuid.UUID] = {i for i in (set(current) | holders) if i is not None}
    names = {u.id: u.full_name for u in db.execute(select(StaffUser).where(StaffUser.id.in_(ids))).scalars()} if ids else {}

    people = []
    for sid in ids:
        owned = [t for t in tasks if t.owner_staff_user_id == sid]
        people.append(
            PersonLoad(
                staff_user_id=str(sid),
                full_name=names.get(sid, ""),
                role=current.get(sid),
                works_here=sid in current,
                owned_open=len(owned),
                owned_overdue=sum(1 for t in owned if t.due_at is not None and t.due_at < now),
                backup_open=sum(1 for t in tasks if t.backup_staff_user_id == sid),
            )
        )
    # People who left but still hold work first, then the busiest.
    people.sort(key=lambda p: (p.works_here, -p.owned_open, p.full_name))
    _audit(staff, "view_workload", "Facility", fid, open=len(tasks))
    return Workload(
        facility_id=str(fid),
        unowned_open=sum(1 for t in tasks if t.owner_staff_user_id is None),
        people=people,
        as_of=now,
    )


@router.post("/facilities/{facility_id}/handover", response_model=HandoverOut)
def hand_over(
    facility_id: str,
    body: HandoverIn,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
    _csrf: None = Depends(require_csrf_header),
) -> HandoverOut:
    """Moves every open task at this facility from one person to another, in
    one transaction. Closed tasks keep their original owner (history)."""
    fid = _id(facility_id)
    membership = _member(db, staff, fid, "hand_over_work")
    if not has_capability([membership.role.value], Capability.HAND_OVER_WORK):
        _audit(staff, "hand_over_work", "Facility", fid, AuditOutcome.DENIED, reason="role_not_permitted")
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=DENIED_MESSAGE[Capability.HAND_OVER_WORK])

    from_id, to_id = _id(body.from_staff_user_id), _id(body.to_staff_user_id)
    if from_id == to_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Choose two different people.")
    if find_active_membership(db, to_id, fid) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The new owner must work at this facility.")

    # Lock the affected rows so a concurrent assign/close waits for us.
    tasks = db.execute(
        select(CareTask)
        .where(
            CareTask.facility_id == fid,
            CareTask.status.in_(OPEN),
            or_(CareTask.owner_staff_user_id == from_id, CareTask.backup_staff_user_id == from_id),
        )
        .with_for_update()
    ).scalars().all()
    if not tasks:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="This person has no open work here to hand over.")

    owner_moved = backup_moved = 0
    for t in tasks:
        if t.owner_staff_user_id == from_id:
            t.owner_staff_user_id = to_id
            if t.backup_staff_user_id == to_id:
                t.backup_staff_user_id = None  # owner and backup must differ
            if t.status is TaskStatus.NEW:
                t.status = TaskStatus.ASSIGNED
            owner_moved += 1
        elif body.include_backup and t.backup_staff_user_id == from_id:
            t.backup_staff_user_id = None if t.owner_staff_user_id == to_id else to_id
            backup_moved += 1
    db.commit()

    for t in tasks:
        _audit(staff, "hand_over_task", "CareTask", t.id, reason=body.reason.value, from_staff=str(from_id), to_staff=str(to_id))
    _audit(
        staff, "hand_over_work", "Facility", fid,
        reason=body.reason.value, from_staff=str(from_id), to_staff=str(to_id), owner_moved=owner_moved, backup_moved=backup_moved,
    )
    return HandoverOut(owner_moved=owner_moved, backup_moved=backup_moved)
