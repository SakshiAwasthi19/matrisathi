"""Outbound messaging for staff (W3-A3, W3-B2; F016, F017, F020; AT11, AT14).

- Contact preferences: consent (recorded by staff), opt-out, language, safe
  hours, detail level and "prefers a call". Opt-out always wins.
- Appointment reminders are queued from an approved template chosen by her
  language and detail level, and re-checked when the worker sends them.
- Every message shows one of: queued, submitted, delivered, read (only if
  the provider reports it), failed, unknown or blocked, with the reason.
- Failed, unknown and blocked messages stay on a facility list until a person
  resolves them; failed and unknown ones also create a "call instead" task.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routers.care import STALE, _commit
from app.core.config import settings
from app.core.db import get_db
from app.core.deps import get_current_staff, require_csrf_header, require_facility_membership
from app.domain.permissions import DENIED_MESSAGE, Capability, has_capability
from app.models.audit import AuditOutcome
from app.models.care import Appointment
from app.models.facility import Facility
from app.models.identity import ContactMethod, Person
from app.models.messaging import (
    ContactPreference,
    MessagePurpose,
    MessageTemplate,
    OptOutSource,
    OutboxKind,
    OutboxMessage,
)
from app.models.staff import StaffMembership, StaffUser
from app.schemas.messaging import (
    ContactPreferenceIn,
    ContactPreferenceOut,
    MessageOut,
    ReminderIn,
    ResolveIn,
    TemplateOut,
)
from app.services import audit_service
from app.services.messaging import outbox
from app.services.messaging.util import to_provider_number

router = APIRouter(tags=["messaging"])


def _id(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found") from None


def _audit(staff: StaffUser, action: str, entity_type: str, entity_id: object, outcome: AuditOutcome = AuditOutcome.SUCCESS, **meta: object) -> None:
    audit_service.record_event(
        actor_staff_user_id=staff.id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        outcome=outcome,
        metadata=meta,
    )


def _name(db: Session, staff_id: uuid.UUID | None) -> str | None:
    if staff_id is None:
        return None
    user = db.get(StaffUser, staff_id)
    return user.full_name if user else None


def _require(staff: StaffUser, membership: StaffMembership, capability: Capability, action: str) -> None:
    if not has_capability([membership.role.value], capability):
        _audit(staff, action, "Messaging", None, AuditOutcome.DENIED, reason="role_not_permitted")
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=DENIED_MESSAGE[capability])


def accessible_person(db: Session, staff: StaffUser, person_id: str, action: str) -> tuple[Person, StaffMembership]:
    person = db.get(Person, _id(person_id))
    if person is None:
        _audit(staff, action, "Person", None, AuditOutcome.DENIED, reason="not_found")
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    try:
        membership = require_facility_membership(db, staff, person.registering_facility_id)
    except HTTPException:
        _audit(staff, action, "Person", person.id, AuditOutcome.DENIED, reason="not_authorized")
        raise
    return person, membership


def primary_contact(db: Session, person_id: uuid.UUID) -> ContactMethod | None:
    """Her verified phone number, else her first one."""
    rows = db.execute(
        select(ContactMethod).where(ContactMethod.person_id == person_id).order_by(ContactMethod.created_at)
    ).scalars().all()
    usable = [c for c in rows if to_provider_number(c.value)]
    verified = [c for c in usable if c.verified_at is not None]
    candidates = verified or usable
    return candidates[0] if candidates else None


def message_text(db: Session, msg: OutboxMessage) -> tuple[str, bool, bool]:
    """(text as sent, audio available, template is a placeholder)."""
    if msg.kind is OutboxKind.TEXT:
        return msg.free_text or "", False, False
    template = db.get(MessageTemplate, msg.template_id)
    if template is None:
        return "", False, False
    text = template.body_text
    for i, name in enumerate(template.variable_names, start=1):
        text = text.replace("{{" + str(i) + "}}", msg.variables.get(name, ""))
    return text, template.audio_storage_key is not None, template.is_placeholder


def message_out(db: Session, msg: OutboxMessage, with_person: bool = False) -> MessageOut:
    text, audio, placeholder = message_text(db, msg)
    person_name = None
    if with_person:
        person = db.get(Person, msg.person_id)
        person_name = person.full_name if person else None
    return MessageOut(
        id=str(msg.id),
        person_id=str(msg.person_id),
        kind=msg.kind,
        purpose=msg.purpose,
        status=msg.status,
        status_reason=msg.status_reason,
        text=text,
        audio_available=audio,
        template_placeholder=placeholder,
        appointment_id=str(msg.appointment_id) if msg.appointment_id else None,
        inbox_item_id=str(msg.inbox_item_id) if msg.inbox_item_id else None,
        attempts=msg.attempts,
        next_attempt_at=msg.next_attempt_at,
        submitted_at=msg.submitted_at,
        delivered_at=msg.delivered_at,
        read_at=msg.read_at,
        failed_at=msg.failed_at,
        created_at=msg.created_at,
        created_by_name=_name(db, msg.created_by_staff_user_id),
        owner_name=_name(db, msg.owner_staff_user_id),
        resolved_at=msg.resolved_at,
        person_name=person_name,
    )


def _org_of(db: Session, facility_id: uuid.UUID) -> uuid.UUID:
    facility = db.get(Facility, facility_id)
    assert facility is not None
    return facility.organization_id


# --- contact preferences ---------------------------------------------------------


def _pref_out(db: Session, person: Person, pref: ContactPreference | None) -> ContactPreferenceOut:
    numbers = [
        c.value for c in db.execute(select(ContactMethod).where(ContactMethod.person_id == person.id)).scalars()
    ]
    available = outbox.channel_for(db, _org_of(db, person.registering_facility_id)) is not None
    return ContactPreferenceOut(
        person_id=str(person.id),
        exists=pref is not None,
        language=pref.language if pref else None,
        safe_from_hour=pref.safe_from_hour if pref else None,
        safe_to_hour=pref.safe_to_hour if pref else None,
        default_safe_from_hour=settings.messaging_default_safe_from_hour,
        default_safe_to_hour=settings.messaging_default_safe_to_hour,
        detail_level=pref.detail_level if pref else outbox.DetailLevel.MINIMAL,
        messaging_consent=pref.messaging_consent if pref else False,
        consent_recorded_at=pref.consent_recorded_at if pref else None,
        consent_recorded_by_name=_name(db, pref.consent_recorded_by_staff_user_id) if pref else None,
        opted_out=pref.opted_out if pref else False,
        opted_out_at=pref.opted_out_at if pref else None,
        opt_out_source=pref.opt_out_source if pref else None,
        prefers_call=pref.prefers_call if pref else False,
        version=pref.version if pref else 0,
        phone_numbers=numbers,
        messaging_available=available,
    )


@router.get("/people/{person_id}/contact-preferences", response_model=ContactPreferenceOut)
def get_preferences(person_id: str, db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)) -> ContactPreferenceOut:
    person, _ = accessible_person(db, staff, person_id, "contact_preference.read")
    return _pref_out(db, person, outbox.preference_for(db, person.id))


@router.put(
    "/people/{person_id}/contact-preferences",
    response_model=ContactPreferenceOut,
    dependencies=[Depends(require_csrf_header)],
)
def put_preferences(
    person_id: str, body: ContactPreferenceIn, db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)
) -> ContactPreferenceOut:
    action = "contact_preference.update"
    person, membership = accessible_person(db, staff, person_id, action)
    _require(staff, membership, Capability.MANAGE_CONTACT_PREFERENCES, action)
    if (body.safe_from_hour is None) != (body.safe_to_hour is None) or (
        body.safe_from_hour is not None and body.safe_to_hour is not None and body.safe_from_hour >= body.safe_to_hour
    ):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Give both safe hours, start before end.")
    pref = outbox.preference_for(db, person.id)
    now = datetime.now(timezone.utc)
    if pref is None:
        if body.expected_version not in (None, 0):
            raise HTTPException(status.HTTP_409_CONFLICT, detail=STALE)
        pref = ContactPreference(person_id=person.id, opted_out=False, messaging_consent=False, prefers_call=False)
        db.add(pref)
    elif body.expected_version != pref.version:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=STALE)
    changes: dict[str, object] = {}
    if body.messaging_consent != pref.messaging_consent:
        changes["consent"] = body.messaging_consent
        pref.messaging_consent = body.messaging_consent
        pref.consent_recorded_at = now if body.messaging_consent else pref.consent_recorded_at
        pref.consent_recorded_by_staff_user_id = staff.id if body.messaging_consent else pref.consent_recorded_by_staff_user_id
    if body.opted_out != pref.opted_out:
        changes["opted_out"] = body.opted_out
        pref.opted_out = body.opted_out
        pref.opted_out_at = now if body.opted_out else None
        pref.opt_out_source = OptOutSource.STAFF if body.opted_out else None
    pref.language = body.language or None
    pref.safe_from_hour, pref.safe_to_hour = body.safe_from_hour, body.safe_to_hour
    pref.detail_level = body.detail_level
    pref.prefers_call = body.prefers_call
    pref.updated_by_staff_user_id = staff.id
    _commit(db)
    _audit(staff, action, "ContactPreference", pref.id, person_id=str(person.id), changes=changes)
    db.refresh(pref)
    return _pref_out(db, person, pref)


# --- templates, reminders, history ----------------------------------------------


@router.get("/message-templates", response_model=list[TemplateOut])
def list_templates(
    facility_id: str = Query(...), db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)
) -> list[TemplateOut]:
    fid = _id(facility_id)
    require_facility_membership(db, staff, fid)
    return [
        TemplateOut(
            id=str(t.id),
            purpose=t.purpose,
            language=t.language,
            detail_level=t.detail_level,
            version_label=t.version_label,
            body_text=t.body_text,
            variable_names=list(t.variable_names),
            is_placeholder=t.is_placeholder,
            approved_by_name=t.approved_by_name,
            audio_available=t.audio_storage_key is not None,
        )
        for t in outbox.sendable_templates(db, _org_of(db, fid))
    ]


def reminder_variables(db: Session, appt: Appointment) -> dict[str, str]:
    facility = db.get(Facility, appt.facility_id)
    local = appt.confirmed_for.astimezone(outbox.local_tz()) if appt.confirmed_for else None
    day = local.date() if local else appt.requested_for
    return {
        "appointment_date": day.strftime("%d %b %Y") if day else "",
        "appointment_time": local.strftime("%I:%M %p").lstrip("0") if local else "",
        "facility_name": facility.name if facility else "",
        "place": appt.location_note or (facility.name if facility else ""),
    }


@router.post(
    "/appointments/{appointment_id}/reminders",
    response_model=MessageOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_header)],
)
def queue_reminder(
    appointment_id: str, body: ReminderIn, db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)
) -> MessageOut:
    from app.models.pregnancy import PregnancyEpisode

    action = "message.queue_reminder"
    appt = db.get(Appointment, _id(appointment_id))
    if appt is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    try:
        membership = require_facility_membership(db, staff, appt.facility_id)
    except HTTPException:
        _audit(staff, action, "Appointment", appt.id, AuditOutcome.DENIED, reason="not_authorized")
        raise
    _require(staff, membership, Capability.SEND_MESSAGES, action)
    if appt.status not in outbox.SENDABLE_APPOINTMENT_STATES:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Only a requested or confirmed appointment can have a reminder.")
    episode = db.get(PregnancyEpisode, appt.episode_id)
    assert episode is not None
    person = db.get(Person, episode.mother_person_id)
    assert person is not None
    contact = primary_contact(db, person.id)
    if contact is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="She has no phone number that can receive messages.")
    try:
        msg = outbox.enqueue_template(
            db,
            staff=staff,
            facility_id=appt.facility_id,
            organization_id=_org_of(db, appt.facility_id),
            person=person,
            contact=contact,
            purpose=MessagePurpose.APPOINTMENT_REMINDER,
            variables=reminder_variables(db, appt),
            appointment=appt,
            send_after=body.send_at,
        )
    except outbox.EnqueueRefused as err:
        _audit(staff, action, "Appointment", appt.id, AuditOutcome.DENIED, reason="refused")
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(err)) from None
    _commit(db)
    _audit(staff, action, "OutboxMessage", msg.id, appointment_id=str(appt.id))
    return message_out(db, msg)


@router.get("/people/{person_id}/messages", response_model=list[MessageOut])
def person_messages(person_id: str, db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)) -> list[MessageOut]:
    person, _ = accessible_person(db, staff, person_id, "message.list")
    rows = db.execute(
        select(OutboxMessage).where(OutboxMessage.person_id == person.id).order_by(OutboxMessage.created_at.desc()).limit(100)
    ).scalars().all()
    return [message_out(db, m) for m in rows]


@router.get("/facilities/{facility_id}/message-failures", response_model=list[MessageOut])
def message_failures(facility_id: str, db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)) -> list[MessageOut]:
    fid = _id(facility_id)
    require_facility_membership(db, staff, fid)
    rows = db.execute(outbox.open_failures_query([fid]).order_by(OutboxMessage.created_at.desc()).limit(200)).scalars().all()
    return [message_out(db, m, with_person=True) for m in rows]


def _message_for_action(db: Session, staff: StaffUser, message_id: str, action: str) -> tuple[OutboxMessage, StaffMembership]:
    msg = db.get(OutboxMessage, _id(message_id))
    if msg is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    try:
        membership = require_facility_membership(db, staff, msg.facility_id)
    except HTTPException:
        _audit(staff, action, "OutboxMessage", msg.id, AuditOutcome.DENIED, reason="not_authorized")
        raise
    return msg, membership


@router.post("/messages/{message_id}/resolve", response_model=MessageOut, dependencies=[Depends(require_csrf_header)])
def resolve_message(message_id: str, body: ResolveIn, db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)) -> MessageOut:
    action = "message.resolve"
    msg, membership = _message_for_action(db, staff, message_id, action)
    _require(staff, membership, Capability.SEND_MESSAGES, action)
    if msg.status not in outbox.NEEDS_FOLLOW_UP:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Only failed, unknown or blocked messages need resolving.")
    if msg.resolved_at is None:
        msg.resolved_at = datetime.now(timezone.utc)
        msg.resolved_by_staff_user_id = staff.id
        _commit(db)
        _audit(staff, action, "OutboxMessage", msg.id, note_given=bool(body.note))
    return message_out(db, msg)


@router.post("/messages/{message_id}/call-instead", response_model=MessageOut, dependencies=[Depends(require_csrf_header)])
def call_instead(message_id: str, db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)) -> MessageOut:
    """Creates (once) a task to phone her about this message."""
    action = "message.call_instead"
    msg, membership = _message_for_action(db, staff, message_id, action)
    _require(staff, membership, Capability.SEND_MESSAGES, action)
    if msg.owner_staff_user_id is None:
        msg.owner_staff_user_id = staff.id
    task = outbox.ensure_call_task(db, msg, datetime.now(timezone.utc))
    if task is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="She has no active pregnancy record to attach a call task to.")
    _commit(db)
    _audit(staff, action, "OutboxMessage", msg.id, task_id=str(task.id))
    return message_out(db, msg)
