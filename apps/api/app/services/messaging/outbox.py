"""The durable outbox and its worker (W3-A1, W3-A3; T011, T012; AT11, AT12).

Queueing: `enqueue_template` / `enqueue_text` add an `outbox_message` row to
the caller's session, so it commits in the same transaction as the business
change that caused it (or not at all).

Sending: `run_once` claims due rows with `FOR UPDATE SKIP LOCKED` and a
lease, so two workers never take the same row. Each row is re-checked at
send time (consent, opt-out, safe hours, the appointment still current, the
service window, the template still approved). Before the provider is
called the row is marked SENDING and committed; if the worker dies after
that, the row becomes UNKNOWN for a person to reconcile, never resent.

Nothing here decides anything clinical. Every message is an approved
template or a staff member's own reply.
"""

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.models.care import Appointment, AppointmentStatus, CareTask, TaskKind, TaskStatus, TemplateStatus
from app.models.identity import ContactMethod, Person
from app.models.messaging import (
    ContactPreference,
    DetailLevel,
    InboxItem,
    MessagePurpose,
    MessageTemplate,
    MessagingChannel,
    OutboxKind,
    OutboxMessage,
    OutboxStatus,
)
from app.models.pregnancy import PregnancyEpisode, PregnancyEpisodeStatus
from app.models.staff import StaffUser
from app.services.messaging.provider import (
    MessagingProvider,
    ProviderError,
    ProviderPermanentError,
    ProviderTransientError,
    ProviderUnknownOutcome,
)
from app.services.messaging.util import to_provider_number

log = logging.getLogger("matrisathi.outbox")

LEASE = timedelta(minutes=2)
SERVICE_WINDOW = timedelta(hours=24)  # the provider's free-text window after the person last wrote
DEFAULT_LANGUAGE = "en"
SENDABLE_APPOINTMENT_STATES = (AppointmentStatus.REQUESTED, AppointmentStatus.CONFIRMED)


class EnqueueRefused(ValueError):
    """The message cannot be queued. The text is safe to show to staff."""


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def local_tz() -> timezone:
    return timezone(timedelta(minutes=settings.local_utc_offset_minutes))


# --- lookups ---------------------------------------------------------------------


def preference_for(db: Session, person_id: uuid.UUID) -> ContactPreference | None:
    return db.execute(select(ContactPreference).where(ContactPreference.person_id == person_id)).scalar_one_or_none()


def channel_for(db: Session, organization_id: uuid.UUID) -> MessagingChannel | None:
    return db.execute(
        select(MessagingChannel)
        .where(MessagingChannel.organization_id == organization_id, MessagingChannel.active.is_(True))
        .order_by(MessagingChannel.created_at)
    ).scalars().first()


def sendable_templates(db: Session, organization_id: uuid.UUID) -> list[MessageTemplate]:
    q = select(MessageTemplate).where(
        MessageTemplate.organization_id == organization_id, MessageTemplate.status == TemplateStatus.APPROVED
    )
    if not settings.messaging_allow_placeholder_templates:
        q = q.where(MessageTemplate.is_placeholder.is_(False))
    return list(db.execute(q.order_by(MessageTemplate.purpose, MessageTemplate.language)).scalars())


def pick_template(
    db: Session, organization_id: uuid.UUID, purpose: MessagePurpose, language: str, detail: DetailLevel
) -> MessageTemplate | None:
    """The approved template for exactly this language and detail level.
    Real templates win over placeholders; the newest approved version wins."""
    candidates = [
        t
        for t in sendable_templates(db, organization_id)
        if t.purpose == purpose and t.language == language and t.detail_level == detail
    ]
    candidates.sort(key=lambda t: (t.is_placeholder, -(t.approved_on.toordinal() if t.approved_on else 0)))
    return candidates[0] if candidates else None


def last_inbound_at(db: Session, organization_id: uuid.UUID, provider_number: str) -> datetime | None:
    return db.execute(
        select(InboxItem.received_at)
        .where(InboxItem.organization_id == organization_id, InboxItem.from_number == provider_number)
        .order_by(InboxItem.received_at.desc())
        .limit(1)
    ).scalar_one_or_none()


# --- queueing ----------------------------------------------------------------------


def _check_can_message(db: Session, person: Person) -> ContactPreference:
    pref = preference_for(db, person.id)
    if pref is None or not pref.messaging_consent:
        raise EnqueueRefused("Record her consent to WhatsApp messages first (Contact preferences).")
    if pref.opted_out:
        raise EnqueueRefused("She has opted out of messages. Call her instead.")
    return pref


def enqueue_template(
    db: Session,
    *,
    staff: StaffUser,
    facility_id: uuid.UUID,
    organization_id: uuid.UUID,
    person: Person,
    contact: ContactMethod,
    purpose: MessagePurpose,
    variables: dict[str, str],
    appointment: Appointment | None = None,
    send_after: datetime | None = None,
) -> OutboxMessage:
    pref = _check_can_message(db, person)
    channel = channel_for(db, organization_id)
    if channel is None:
        raise EnqueueRefused("WhatsApp is not set up for this organization yet.")
    if to_provider_number(contact.value) is None:
        raise EnqueueRefused("This phone number cannot receive WhatsApp messages. Check it first.")
    language = pref.language or DEFAULT_LANGUAGE
    template = pick_template(db, organization_id, purpose, language, pref.detail_level)
    if template is None:
        raise EnqueueRefused(
            "There is no approved message template for this purpose, language and detail level yet."
        )
    missing = [name for name in template.variable_names if not variables.get(name)]
    if missing:
        raise EnqueueRefused("Some details the template needs are missing: " + ", ".join(missing) + ".")
    msg = OutboxMessage(
        facility_id=facility_id,
        person_id=person.id,
        contact_method_id=contact.id,
        channel_id=channel.id,
        kind=OutboxKind.TEMPLATE,
        purpose=purpose,
        template_id=template.id,
        variables={name: variables[name] for name in template.variable_names},
        appointment_id=appointment.id if appointment else None,
        appointment_version=appointment.version if appointment else None,
        status=OutboxStatus.QUEUED,
        attempts=0,
        next_attempt_at=send_after or now_utc(),
        created_by_staff_user_id=staff.id,
        owner_staff_user_id=staff.id,
    )
    db.add(msg)
    return msg


def enqueue_text(
    db: Session, *, staff: StaffUser, item: InboxItem, person: Person, contact: ContactMethod, body: str
) -> OutboxMessage:
    """A staff member's own reply to an inbox item, inside the service window."""
    _check_can_message(db, person)
    last = last_inbound_at(db, item.organization_id, item.from_number)
    if last is None or now_utc() - last > SERVICE_WINDOW:
        raise EnqueueRefused("More than 24 hours since she last wrote: reply with an approved template or call.")
    if item.facility_id is None:
        raise EnqueueRefused("Link this message to a person first.")
    msg = OutboxMessage(
        facility_id=item.facility_id,
        person_id=person.id,
        contact_method_id=contact.id,
        channel_id=item.channel_id,
        kind=OutboxKind.TEXT,
        purpose=MessagePurpose.GENERAL,
        free_text=body,
        variables={},
        inbox_item_id=item.id,
        status=OutboxStatus.QUEUED,
        attempts=0,
        next_attempt_at=now_utc(),
        created_by_staff_user_id=staff.id,
        owner_staff_user_id=staff.id,
    )
    db.add(msg)
    return msg


# --- send-time checks -------------------------------------------------------------


@dataclass(frozen=True)
class Decision:
    action: str  # "send", "block" or "defer"
    reason: str | None = None
    until: datetime | None = None


def _next_window_start(now: datetime, start_hour: int, end_hour: int) -> datetime | None:
    """None if `now` is inside [start, end) local time; else the next start."""
    local = now.astimezone(local_tz())
    if start_hour <= local.hour < end_hour:
        return None
    day = local.date() if local.hour < start_hour else local.date() + timedelta(days=1)
    return datetime.combine(day, time(hour=start_hour), tzinfo=local_tz())


def check_at_send_time(db: Session, msg: OutboxMessage, now: datetime) -> Decision:
    pref = preference_for(db, msg.person_id)
    if pref is None or not pref.messaging_consent:
        return Decision("block", "NO_CONSENT")
    if pref.opted_out:
        return Decision("block", "OPTED_OUT")
    contact = db.get(ContactMethod, msg.contact_method_id)
    if contact is None or contact.person_id != msg.person_id or to_provider_number(contact.value) is None:
        return Decision("block", "NUMBER_NOT_USABLE")
    channel = db.get(MessagingChannel, msg.channel_id)
    if channel is None or not channel.active:
        return Decision("block", "CHANNEL_INACTIVE")
    if msg.kind is OutboxKind.TEMPLATE:
        template = db.get(MessageTemplate, msg.template_id)
        if (
            template is None
            or template.status is not TemplateStatus.APPROVED
            or (template.is_placeholder and not settings.messaging_allow_placeholder_templates)
        ):
            return Decision("block", "TEMPLATE_NOT_APPROVED")
    else:
        number = to_provider_number(contact.value)
        last = last_inbound_at(db, channel.organization_id, number or "")
        if last is None or now - last > SERVICE_WINDOW:
            return Decision("block", "OUTSIDE_SERVICE_WINDOW")
    if msg.appointment_id is not None:
        appt = db.get(Appointment, msg.appointment_id)
        if appt is None or appt.version != msg.appointment_version or appt.status not in SENDABLE_APPOINTMENT_STATES:
            return Decision("block", "APPOINTMENT_CHANGED")
    start = pref.safe_from_hour if pref.safe_from_hour is not None else settings.messaging_default_safe_from_hour
    end = pref.safe_to_hour if pref.safe_to_hour is not None else settings.messaging_default_safe_to_hour
    later = _next_window_start(now, start, end)
    if later is not None:
        return Decision("defer", "OUTSIDE_SAFE_HOURS", later)
    return Decision("send")


# --- failure follow-up -----------------------------------------------------------


def ensure_call_task(db: Session, msg: OutboxMessage, now: datetime) -> CareTask | None:
    """One 'call instead' task per failed or unknown message, owned by the
    person who sent it, on the mother's active pregnancy record (if any)."""
    existing = db.execute(
        select(CareTask).where(CareTask.source_record_type == "outbox_message", CareTask.source_record_id == msg.id)
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    episode = db.execute(
        select(PregnancyEpisode).where(
            PregnancyEpisode.mother_person_id == msg.person_id,
            PregnancyEpisode.status == PregnancyEpisodeStatus.ACTIVE,
        )
    ).scalars().first()
    if episode is None:
        return None
    owner = msg.owner_staff_user_id or msg.created_by_staff_user_id
    task = CareTask(
        episode_id=episode.id,
        facility_id=msg.facility_id,
        kind=TaskKind.CONTACT,
        status=TaskStatus.ASSIGNED,
        owner_staff_user_id=owner,
        due_at=now + timedelta(days=1),
        source_record_type="outbox_message",
        source_record_id=msg.id,
    )
    db.add(task)
    return task


# --- worker ------------------------------------------------------------------------

ProviderFactory = Callable[[str], MessagingProvider]


def _backoff(attempts: int) -> timedelta:
    return min(timedelta(seconds=30 * (2 ** max(attempts - 1, 0))), timedelta(hours=1))


def claim(session_factory: sessionmaker, worker_id: str, now: datetime, limit: int = 20) -> list[uuid.UUID]:
    """Takes up to `limit` due messages for this worker. Also turns rows left
    in SENDING by a worker that stopped into UNKNOWN (never resent)."""
    with session_factory() as db:
        stuck = db.execute(
            select(OutboxMessage)
            .where(OutboxMessage.status == OutboxStatus.SENDING, OutboxMessage.lease_until < now)
            .with_for_update(skip_locked=True)
        ).scalars().all()
        for msg in stuck:
            msg.status = OutboxStatus.UNKNOWN
            msg.status_reason = "WORKER_STOPPED_MID_SEND"
            msg.lease_until = None
            ensure_call_task(db, msg, now)
        rows = db.execute(
            select(OutboxMessage)
            .where(
                OutboxMessage.status == OutboxStatus.QUEUED,
                OutboxMessage.next_attempt_at <= now,
                or_(OutboxMessage.lease_until.is_(None), OutboxMessage.lease_until < now),
            )
            .order_by(OutboxMessage.next_attempt_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).scalars().all()
        for msg in rows:
            msg.lease_until = now + LEASE
            msg.leased_by = worker_id
        ids = [m.id for m in rows]
        db.commit()
    return ids


def _locked(db: Session, msg_id: uuid.UUID, worker_id: str) -> OutboxMessage | None:
    msg = db.execute(select(OutboxMessage).where(OutboxMessage.id == msg_id).with_for_update()).scalar_one_or_none()
    if msg is None or msg.leased_by != worker_id:
        return None
    return msg


def process(
    session_factory: sessionmaker, provider_factory: ProviderFactory, msg_id: uuid.UUID, worker_id: str, now: datetime
) -> OutboxStatus | None:
    # 1. Re-check everything, then mark SENDING (committed) before the call.
    with session_factory() as db:
        msg = _locked(db, msg_id, worker_id)
        if msg is None or msg.status is not OutboxStatus.QUEUED:
            return None
        decision = check_at_send_time(db, msg, now)
        if decision.action == "block":
            msg.status = OutboxStatus.BLOCKED
            msg.status_reason = decision.reason
            msg.lease_until = None
            db.commit()
            return OutboxStatus.BLOCKED
        if decision.action == "defer":
            msg.next_attempt_at = decision.until or now + timedelta(hours=1)
            msg.status_reason = decision.reason
            msg.lease_until = None
            db.commit()
            return OutboxStatus.QUEUED
        contact = db.get(ContactMethod, msg.contact_method_id)
        channel = db.get(MessagingChannel, msg.channel_id)
        template = db.get(MessageTemplate, msg.template_id) if msg.template_id else None
        assert contact is not None and channel is not None
        to = to_provider_number(contact.value) or ""
        phone_number_id = channel.phone_number_id
        kind, free_text = msg.kind, msg.free_text
        template_args = (
            (template.provider_template_name, template.language, [msg.variables[n] for n in template.variable_names])
            if template
            else None
        )
        msg.status = OutboxStatus.SENDING
        msg.status_reason = None
        msg.attempts += 1
        msg.lease_until = now + LEASE
        attempts = msg.attempts
        db.commit()

    # 2. Call the provider outside any transaction.
    outcome: OutboxStatus
    reason: str | None = None
    provider_id: str | None = None
    try:
        provider = provider_factory(phone_number_id)
        if kind is OutboxKind.TEMPLATE and template_args is not None:
            result = provider.send_template(to, *template_args)
        else:
            result = provider.send_text(to, free_text or "")
        outcome, provider_id = OutboxStatus.SUBMITTED, result.provider_message_id
    except ProviderTransientError as err:
        outcome, reason = OutboxStatus.QUEUED, str(err)[:200]
    except ProviderPermanentError as err:
        outcome, reason = OutboxStatus.FAILED, str(err)[:200]
    except ProviderUnknownOutcome as err:
        outcome, reason = OutboxStatus.UNKNOWN, str(err)[:200]
    except ProviderError as err:  # not configured, etc.: it was never sent
        outcome, reason = OutboxStatus.QUEUED, str(err)[:200]

    # 3. Record what happened.
    with session_factory() as db:
        row: OutboxMessage = db.execute(
            select(OutboxMessage).where(OutboxMessage.id == msg_id).with_for_update()
        ).scalar_one()
        row.lease_until = None
        row.last_error = reason
        if outcome is OutboxStatus.SUBMITTED:
            row.status = OutboxStatus.SUBMITTED
            row.provider_message_id = provider_id
            row.submitted_at = now_utc()
        elif outcome is OutboxStatus.QUEUED and attempts < settings.messaging_max_attempts:
            row.status = OutboxStatus.QUEUED
            row.status_reason = "RETRYING"
            row.next_attempt_at = now_utc() + _backoff(attempts)
        elif outcome is OutboxStatus.UNKNOWN:
            row.status = OutboxStatus.UNKNOWN
            row.status_reason = "NO_ANSWER_FROM_PROVIDER"
            ensure_call_task(db, row, now_utc())
        else:
            row.status = OutboxStatus.FAILED
            row.status_reason = "RETRIES_USED_UP" if outcome is OutboxStatus.QUEUED else "PROVIDER_REFUSED"
            row.failed_at = now_utc()
            ensure_call_task(db, row, now_utc())
        final = row.status
        db.commit()
    log.info("outbox message %s -> %s", msg_id, final.value)
    return final


def run_once(
    session_factory: sessionmaker,
    provider_factory: ProviderFactory,
    worker_id: str,
    now: datetime | None = None,
    limit: int = 20,
) -> dict[str, int]:
    when = now or now_utc()
    counts: dict[str, int] = {}
    for msg_id in claim(session_factory, worker_id, when, limit):
        status = process(session_factory, provider_factory, msg_id, worker_id, when)
        if status is not None:
            counts[status.value] = counts.get(status.value, 0) + 1
    return counts


# --- delivery callbacks -------------------------------------------------------------

_RANK = {
    OutboxStatus.SUBMITTED: 1,
    OutboxStatus.DELIVERED: 2,
    OutboxStatus.READ: 3,
}


def apply_status(db: Session, provider_message_id: str, status: str, at: datetime) -> OutboxMessage | None:
    """Applies a provider status callback. States only move forward; a
    'failed' report always wins and creates the call-instead task."""
    msg = db.execute(
        select(OutboxMessage).where(OutboxMessage.provider_message_id == provider_message_id).with_for_update()
    ).scalar_one_or_none()
    if msg is None:
        return None
    if status == "failed":
        msg.status = OutboxStatus.FAILED
        msg.status_reason = "PROVIDER_REPORTED_FAILED"
        msg.failed_at = at
        ensure_call_task(db, msg, at)
        return msg
    target = {"sent": OutboxStatus.SUBMITTED, "delivered": OutboxStatus.DELIVERED, "read": OutboxStatus.READ}.get(status)
    if target is None or msg.status not in _RANK:
        return msg
    if _RANK[target] > _RANK[msg.status]:
        msg.status = target
    if target is OutboxStatus.DELIVERED and msg.delivered_at is None:
        msg.delivered_at = at
    if target is OutboxStatus.READ:
        msg.read_at = msg.read_at or at
        msg.delivered_at = msg.delivered_at or at
    return msg


NEEDS_FOLLOW_UP = (OutboxStatus.FAILED, OutboxStatus.UNKNOWN, OutboxStatus.BLOCKED)


def open_failures_query(facility_ids: list[uuid.UUID]) -> Select[tuple[OutboxMessage]]:
    """Failed, unknown or blocked messages nobody has resolved yet."""
    return select(OutboxMessage).where(
        OutboxMessage.facility_id.in_(facility_ids),
        OutboxMessage.status.in_(NEEDS_FOLLOW_UP),
        OutboxMessage.resolved_at.is_(None),
    )
