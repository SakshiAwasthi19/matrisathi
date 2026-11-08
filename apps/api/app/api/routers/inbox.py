"""The staff inbox for inbound text, voice notes and photos
(W3-A2, W3-A4, W3-B1; F018, F019; M018, M020; AT13).

Who sees what:
- An item linked to a person: everyone working at her facility.
- An unlinked item (nobody has confirmed who wrote): coordinators only, at
  the facility it was routed to, or at any facility of the organization if
  the number matched no single facility.
Anything else is a 404, audited, like every other record.

Linking needs an identity check, recorded with who did it and how. The
person must be registered at a facility the coordinator works at.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.routers.care import STALE, _commit
from app.api.routers.messaging import message_out, primary_contact
from app.core.db import get_db
from app.core.deps import (
    find_active_membership,
    get_current_staff,
    require_csrf_header,
    require_facility_membership,
)
from app.domain.permissions import DENIED_MESSAGE, Capability, has_capability
from app.models.audit import AuditOutcome
from app.models.facility import Facility
from app.models.identity import ContactMethod, Person
from app.models.messaging import (
    InboundMedia,
    InboxItem,
    InboxStatus,
    OutboxMessage,
)
from app.models.staff import StaffMembership, StaffUser
from app.schemas.messaging import AssignIn, CloseIn, InboxItemOut, InboxSummary, LinkIn, ReplyIn
from app.services import audit_service
from app.services.file_store import FileStore, FileStoreError, get_file_store
from app.services.messaging import inbound, outbox
from app.services.messaging.util import same_number

router = APIRouter(tags=["inbox"])

VIEWS = ("open", "unlinked", "mine", "overdue", "closed")


def _id(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found") from None


def _audit(staff: StaffUser, action: str, entity_id: object, outcome: AuditOutcome = AuditOutcome.SUCCESS, **meta: object) -> None:
    audit_service.record_event(
        actor_staff_user_id=staff.id,
        action=action,
        entity_type="InboxItem",
        entity_id=str(entity_id) if entity_id is not None else None,
        outcome=outcome,
        metadata=meta,
    )


def _name(db: Session, staff_id: uuid.UUID | None) -> str | None:
    if staff_id is None:
        return None
    user = db.get(StaffUser, staff_id)
    return user.full_name if user else None


def _memberships(db: Session, staff: StaffUser) -> list[StaffMembership]:
    return list(
        db.execute(
            select(StaffMembership).where(
                StaffMembership.staff_user_id == staff.id,
                StaffMembership.active.is_(True),
                StaffMembership.revoked_at.is_(None),
            )
        ).scalars()
    )


def _can_triage(memberships: list[StaffMembership]) -> bool:
    return has_capability([m.role.value for m in memberships], Capability.TRIAGE_UNLINKED_INBOX)


def visible_membership(db: Session, staff: StaffUser, item: InboxItem) -> StaffMembership | None:
    """The membership through which the caller may see this item, or None."""
    if item.person_id is not None and item.facility_id is not None:
        return find_active_membership(db, staff.id, item.facility_id)
    mine = _memberships(db, staff)
    triage = [m for m in mine if has_capability([m.role.value], Capability.TRIAGE_UNLINKED_INBOX)]
    if item.facility_id is not None:
        return next((m for m in triage if m.facility_id == item.facility_id), None)
    for m in triage:
        facility = db.get(Facility, m.facility_id)
        if facility is not None and facility.organization_id == item.organization_id:
            return m
    return None


def _item_for(db: Session, staff: StaffUser, item_id: str, action: str) -> tuple[InboxItem, StaffMembership]:
    item = db.get(InboxItem, _id(item_id))
    membership = visible_membership(db, staff, item) if item is not None else None
    if item is None or membership is None:
        _audit(staff, action, item.id if item else None, AuditOutcome.DENIED, reason="not_visible")
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    return item, membership


def _out(db: Session, item: InboxItem, with_replies: bool = False) -> InboxItemOut:
    now = datetime.now(timezone.utc)
    person = db.get(Person, item.person_id) if item.person_id else None
    media = db.execute(select(InboundMedia).where(InboundMedia.inbox_item_id == item.id)).scalar_one_or_none()
    out = InboxItemOut(
        id=str(item.id),
        facility_id=str(item.facility_id) if item.facility_id else None,
        kind=item.kind,
        text_body=item.text_body,
        media_state=item.media_state,
        media_note=item.media_note,
        media_content_type=media.content_type if media else None,
        received_at=item.received_at,
        from_number=item.from_number,
        people_on_number=len(inbound.people_on_number(db, item.organization_id, item.from_number)),
        person_id=str(item.person_id) if item.person_id else None,
        person_name=person.full_name if person else None,
        linked_by_name=_name(db, item.linked_by_staff_user_id),
        linked_at=item.linked_at,
        identity_check=item.identity_check,
        status=item.status,
        owner_staff_user_id=str(item.owner_staff_user_id) if item.owner_staff_user_id else None,
        owner_name=_name(db, item.owner_staff_user_id),
        backup_staff_user_id=str(item.backup_staff_user_id) if item.backup_staff_user_id else None,
        backup_name=_name(db, item.backup_staff_user_id),
        due_at=item.due_at,
        overdue=item.status is InboxStatus.OPEN and item.due_at < now,
        outcome=item.outcome,
        closure_note=item.closure_note,
        closed_at=item.closed_at,
        version=item.version,
    )
    if with_replies:
        replies = db.execute(
            select(OutboxMessage).where(OutboxMessage.inbox_item_id == item.id).order_by(OutboxMessage.created_at)
        ).scalars().all()
        out.replies = [message_out(db, r) for r in replies]
        last = outbox.last_inbound_at(db, item.organization_id, item.from_number)
        out.can_reply_free_text = (
            item.person_id is not None and last is not None and now - last <= outbox.SERVICE_WINDOW
        )
    return out


def _visible_items_query(db: Session, staff: StaffUser, facility_id: uuid.UUID):  # type: ignore[no-untyped-def]
    membership = require_facility_membership(db, staff, facility_id)
    facility = db.get(Facility, facility_id)
    assert facility is not None
    linked_here = (InboxItem.facility_id == facility_id) & InboxItem.person_id.is_not(None)
    if not has_capability([membership.role.value], Capability.TRIAGE_UNLINKED_INBOX):
        return select(InboxItem).where(linked_here), membership
    unlinked = InboxItem.person_id.is_(None) & (
        (InboxItem.facility_id == facility_id)
        | (InboxItem.facility_id.is_(None) & (InboxItem.organization_id == facility.organization_id))
    )
    return select(InboxItem).where(or_(linked_here, unlinked)), membership


@router.get("/facilities/{facility_id}/inbox", response_model=list[InboxItemOut])
def list_inbox(
    facility_id: str,
    view: str = Query("open"),
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
) -> list[InboxItemOut]:
    if view not in VIEWS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"view must be one of {', '.join(VIEWS)}")
    fid = _id(facility_id)
    q, membership = _visible_items_query(db, staff, fid)
    now = datetime.now(timezone.utc)
    if view == "closed":
        q = q.where(InboxItem.status == InboxStatus.CLOSED)
    else:
        q = q.where(InboxItem.status == InboxStatus.OPEN)
    if view == "unlinked":
        if not has_capability([membership.role.value], Capability.TRIAGE_UNLINKED_INBOX):
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail=DENIED_MESSAGE[Capability.TRIAGE_UNLINKED_INBOX])
        q = q.where(InboxItem.person_id.is_(None))
    elif view == "mine":
        q = q.where(or_(InboxItem.owner_staff_user_id == staff.id, InboxItem.backup_staff_user_id == staff.id))
    elif view == "overdue":
        q = q.where(InboxItem.due_at < now)
    order = InboxItem.received_at.desc() if view == "closed" else InboxItem.due_at
    items = db.execute(q.order_by(order).limit(200)).scalars().all()
    return [_out(db, i) for i in items]


@router.get("/facilities/{facility_id}/inbox-summary", response_model=InboxSummary)
def inbox_summary(facility_id: str, db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)) -> InboxSummary:
    fid = _id(facility_id)
    q, _ = _visible_items_query(db, staff, fid)
    items = db.execute(q.where(InboxItem.status == InboxStatus.OPEN)).scalars().all()
    now = datetime.now(timezone.utc)
    failures = db.execute(outbox.open_failures_query([fid])).scalars().all()
    return InboxSummary(
        open=len(items),
        unlinked=sum(1 for i in items if i.person_id is None),
        mine=sum(1 for i in items if staff.id in (i.owner_staff_user_id, i.backup_staff_user_id)),
        overdue=sum(1 for i in items if i.due_at < now),
        failed_messages=len(failures),
    )


@router.get("/inbox/{item_id}", response_model=InboxItemOut)
def get_item(item_id: str, db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)) -> InboxItemOut:
    item, _ = _item_for(db, staff, item_id, "inbox.read")
    _audit(staff, "inbox.read", item.id)
    return _out(db, item, with_replies=True)


@router.get("/inbox/{item_id}/media")
def get_media(
    item_id: str,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
    store: FileStore = Depends(get_file_store),
) -> Response:
    item, _ = _item_for(db, staff, item_id, "inbox.media")
    media = db.execute(select(InboundMedia).where(InboundMedia.inbox_item_id == item.id)).scalar_one_or_none()
    if media is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    try:
        data = store.get(media.storage_key)
    except FileStoreError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="The file could not be loaded. Try again.") from None
    _audit(staff, "inbox.media", item.id)
    return Response(
        content=data,
        media_type=media.content_type,
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": "inline",
            "X-Content-Type-Options": "nosniff",
        },
    )


def _check_version(item: InboxItem, expected: int) -> None:
    if item.version != expected:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=STALE)


def _require_open(item: InboxItem) -> None:
    if item.status is not InboxStatus.OPEN:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="This message is already closed.")


@router.post("/inbox/{item_id}/link", response_model=InboxItemOut, dependencies=[Depends(require_csrf_header)])
def link_item(item_id: str, body: LinkIn, db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)) -> InboxItemOut:
    action = "inbox.link"
    item, membership = _item_for(db, staff, item_id, action)
    if not has_capability([membership.role.value], Capability.TRIAGE_UNLINKED_INBOX):
        _audit(staff, action, item.id, AuditOutcome.DENIED, reason="role_not_permitted")
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=DENIED_MESSAGE[Capability.TRIAGE_UNLINKED_INBOX])
    _check_version(item, body.expected_version)
    _require_open(item)
    if item.person_id is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="This message is already linked.")
    person = db.get(Person, _id(body.person_id))
    if person is None or find_active_membership(db, staff.id, person.registering_facility_id) is None:
        _audit(staff, action, item.id, AuditOutcome.DENIED, reason="person_not_accessible")
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    facility = db.get(Facility, person.registering_facility_id)
    if facility is None or facility.organization_id != item.organization_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    number_matches = any(
        same_number(c.value, item.from_number)
        for c in db.execute(select(ContactMethod).where(ContactMethod.person_id == person.id)).scalars()
    )
    item.person_id = person.id
    item.facility_id = person.registering_facility_id
    item.identity_check = body.identity_check
    item.linked_by_staff_user_id = staff.id
    item.linked_at = datetime.now(timezone.utc)
    if item.owner_staff_user_id is None:
        item.owner_staff_user_id = staff.id
    _commit(db)
    _audit(
        staff,
        action,
        item.id,
        person_id=str(person.id),
        identity_check=body.identity_check.value,
        number_on_record=number_matches,
    )
    return _out(db, item, with_replies=True)


@router.post("/inbox/{item_id}/assign", response_model=InboxItemOut, dependencies=[Depends(require_csrf_header)])
def assign_item(item_id: str, body: AssignIn, db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)) -> InboxItemOut:
    action = "inbox.assign"
    item, membership = _item_for(db, staff, item_id, action)
    _check_version(item, body.expected_version)
    _require_open(item)
    facility_id = item.facility_id or membership.facility_id
    owner = _id(body.owner_staff_user_id)
    backup = _id(body.backup_staff_user_id) if body.backup_staff_user_id else None
    if backup is not None and backup == owner:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The backup must be a different person.")
    for person_id in (owner, backup):
        if person_id is None:
            continue
        m = find_active_membership(db, person_id, facility_id)
        if m is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Choose someone who works at this facility.")
        if item.person_id is None and not has_capability([m.role.value], Capability.TRIAGE_UNLINKED_INBOX):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Until it is linked, only a coordinator can own this message.",
            )
    item.owner_staff_user_id, item.backup_staff_user_id = owner, backup
    _commit(db)
    _audit(staff, action, item.id, owner=str(owner), backup=str(backup) if backup else None)
    return _out(db, item, with_replies=True)


@router.post("/inbox/{item_id}/reply", response_model=InboxItemOut, dependencies=[Depends(require_csrf_header)])
def reply_item(item_id: str, body: ReplyIn, db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)) -> InboxItemOut:
    action = "inbox.reply"
    item, membership = _item_for(db, staff, item_id, action)
    if not has_capability([membership.role.value], Capability.SEND_MESSAGES):
        _audit(staff, action, item.id, AuditOutcome.DENIED, reason="role_not_permitted")
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=DENIED_MESSAGE[Capability.SEND_MESSAGES])
    _check_version(item, body.expected_version)
    _require_open(item)
    if item.person_id is None or item.facility_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Link this message to a person before replying.")
    if (body.text is None) == (body.template_purpose is None):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Reply with either your own text or a template.")
    person = db.get(Person, item.person_id)
    assert person is not None
    contact = next(
        (
            c
            for c in db.execute(select(ContactMethod).where(ContactMethod.person_id == person.id)).scalars()
            if same_number(c.value, item.from_number)
        ),
        None,
    ) or primary_contact(db, person.id)
    if contact is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="She has no phone number that can receive messages.")
    try:
        if body.text is not None:
            msg = outbox.enqueue_text(db, staff=staff, item=item, person=person, contact=contact, body=body.text.strip())
        else:
            facility = db.get(Facility, item.facility_id)
            assert body.template_purpose is not None
            msg = outbox.enqueue_template(
                db,
                staff=staff,
                facility_id=item.facility_id,
                organization_id=item.organization_id,
                person=person,
                contact=contact,
                purpose=body.template_purpose,
                variables={"facility_name": facility.name if facility else "", "place": facility.name if facility else ""},
            )
            msg.inbox_item_id = item.id
    except outbox.EnqueueRefused as err:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(err)) from None
    _commit(db)
    _audit(staff, action, item.id, message_id=str(msg.id), kind=msg.kind.value)
    db.refresh(item)
    return _out(db, item, with_replies=True)


@router.post("/inbox/{item_id}/close", response_model=InboxItemOut, dependencies=[Depends(require_csrf_header)])
def close_item(item_id: str, body: CloseIn, db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)) -> InboxItemOut:
    action = "inbox.close"
    item, _ = _item_for(db, staff, item_id, action)
    _check_version(item, body.expected_version)
    _require_open(item)
    item.status = InboxStatus.CLOSED
    item.outcome = body.outcome
    item.closure_note = body.note
    item.closed_at = datetime.now(timezone.utc)
    item.closed_by_staff_user_id = staff.id
    if item.owner_staff_user_id is None:
        item.owner_staff_user_id = staff.id
    _commit(db)
    _audit(staff, action, item.id, closed_as=body.outcome.value)
    return _out(db, item, with_replies=True)
