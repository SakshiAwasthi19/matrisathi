"""Turning provider webhooks into inbox items and delivery updates
(W3-A2, W3-A4; F018, F019; AT12, AT13).

- One provider event makes at most one record: the event ID is inserted
  with ON CONFLICT DO NOTHING, so a repeated or concurrent webhook is a no-op.
- An item is never linked to a person automatically. A phone number is not
  an identity; two people may share one handset. Staff link it after an
  identity check. If everyone on that number is registered at a single
  facility, the item is routed to that facility's inbox (still unlinked).
- "STOP" opts out every person on that number at once. Opting out is the
  safe direction, so it does not wait for an identity check. Opting back in
  needs staff to record consent again.
- Voice notes and photos are downloaded into private storage by the worker;
  the provider's media URL is used once and never stored.
"""

import hashlib
import logging
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.models.facility import Facility
from app.models.identity import ContactMethod, Person
from app.models.messaging import (
    ContactPreference,
    DetailLevel,
    InboundEvent,
    InboundMedia,
    InboxItem,
    InboxKind,
    InboxStatus,
    MediaState,
    MessagingChannel,
    OptOutSource,
)
from app.services.file_store import FileStore
from app.services.messaging import outbox
from app.services.messaging.provider import (
    MessagingProvider,
    ProviderError,
    ProviderPermanentError,
)
from app.services.messaging.util import (
    MAX_INBOUND_MEDIA_BYTES,
    MediaRejected,
    check_inbound_media,
    same_number,
    to_provider_number,
)

log = logging.getLogger("matrisathi.inbound")

PROVIDER = "meta"
OPT_OUT_WORDS = {"STOP", "UNSUBSCRIBE"}
_KIND = {"text": InboxKind.TEXT, "audio": InboxKind.VOICE, "image": InboxKind.IMAGE}


def _record_event(db: Session, event_id: str, kind: str) -> bool:
    """True if this event is new; False if it was already processed."""
    inserted = db.execute(
        pg_insert(InboundEvent)
        .values(id=uuid.uuid4(), provider=PROVIDER, provider_event_id=event_id[:200], kind=kind)
        .on_conflict_do_nothing(constraint="uq_inbound_event_provider_id")
        .returning(InboundEvent.id)
    ).scalar_one_or_none()
    return inserted is not None


def _event_id(db: Session, event_id: str) -> uuid.UUID:
    return db.execute(
        select(InboundEvent.id).where(InboundEvent.provider == PROVIDER, InboundEvent.provider_event_id == event_id[:200])
    ).scalar_one()


def people_on_number(db: Session, organization_id: uuid.UUID, provider_number: str) -> list[Person]:
    """Everyone in this organization with this number. Used to route and to
    honour STOP, never to decide who wrote."""
    tail = provider_number[-10:]
    rows = db.execute(
        select(ContactMethod, Person)
        .join(Person, Person.id == ContactMethod.person_id)
        .join(Facility, Facility.id == Person.registering_facility_id)
        .where(
            Facility.organization_id == organization_id,
            func.regexp_replace(ContactMethod.value, r"\D", "", "g").like(f"%{tail}"),
        )
    ).all()
    seen: dict[uuid.UUID, Person] = {}
    for contact, person in rows:
        if same_number(contact.value, provider_number):
            seen[person.id] = person
    return list(seen.values())


def _opt_out(db: Session, people: list[Person], at: datetime) -> int:
    count = 0
    for person in people:
        pref = outbox.preference_for(db, person.id)
        if pref is None:
            pref = ContactPreference(
                person_id=person.id, detail_level=DetailLevel.MINIMAL, messaging_consent=False, prefers_call=False
            )
            db.add(pref)
        if not pref.opted_out:
            pref.opted_out = True
            pref.opted_out_at = at
            pref.opt_out_source = OptOutSource.INBOUND_KEYWORD
            count += 1
    return count


def _timestamp(value: Any) -> datetime:
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return datetime.now(timezone.utc)


def _handle_message(db: Session, channel: MessagingChannel, message: dict[str, Any]) -> InboxItem | None:
    event_id = str(message.get("id") or "")
    sender = to_provider_number(str(message.get("from") or ""))
    if not event_id or sender is None:
        return None
    if not _record_event(db, event_id, "MESSAGE"):
        return None  # already processed
    received = _timestamp(message.get("timestamp"))
    mtype = str(message.get("type") or "")
    kind = _KIND.get(mtype, InboxKind.OTHER)
    text_body: str | None = None
    media_id: str | None = None
    media_state = MediaState.NONE
    media_note: str | None = None
    if kind is InboxKind.TEXT:
        text_body = str((message.get("text") or {}).get("body") or "")[:4000]
    elif kind in (InboxKind.VOICE, InboxKind.IMAGE):
        part = message.get(mtype) or {}
        media_id = str(part.get("id") or "") or None
        caption = part.get("caption")
        text_body = str(caption)[:4000] if caption else None
        media_state = MediaState.PENDING if media_id else MediaState.FAILED
        media_note = None if media_id else "The provider sent no file."
    else:
        media_state = MediaState.REJECTED
        media_note = f"A {mtype or 'message'} was sent; only text, voice notes and photos are accepted."

    people = people_on_number(db, channel.organization_id, sender)
    facilities = {p.registering_facility_id for p in people}
    item = InboxItem(
        organization_id=channel.organization_id,
        facility_id=next(iter(facilities)) if len(facilities) == 1 else None,
        channel_id=channel.id,
        inbound_event_id=_event_id(db, event_id),
        from_number=sender,
        kind=kind,
        text_body=text_body,
        provider_media_id=media_id,
        media_state=media_state,
        media_note=media_note,
        received_at=received,
        status=InboxStatus.OPEN,
        due_at=received + timedelta(hours=settings.inbox_response_hours),
    )
    db.add(item)
    if kind is InboxKind.TEXT and text_body and text_body.strip().upper() in OPT_OUT_WORDS:
        changed = _opt_out(db, people, received)
        item.media_note = f"Opt-out received: messages stopped for {changed} person(s) on this number."
    return item


def handle_webhook(db: Session, payload: dict[str, Any]) -> dict[str, int]:
    """Processes one verified webhook body. The caller commits."""
    counts = {"messages": 0, "duplicates": 0, "statuses": 0, "unknown_channel": 0}
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            value = change.get("value") or {}
            phone_number_id = str((value.get("metadata") or {}).get("phone_number_id") or "")
            channel = db.execute(
                select(MessagingChannel).where(
                    MessagingChannel.phone_number_id == phone_number_id, MessagingChannel.active.is_(True)
                )
            ).scalar_one_or_none()
            if channel is None:
                counts["unknown_channel"] += 1
                continue
            for message in value.get("messages") or []:
                if _handle_message(db, channel, message) is None:
                    counts["duplicates"] += 1
                else:
                    counts["messages"] += 1
            for st in value.get("statuses") or []:
                pid, status = str(st.get("id") or ""), str(st.get("status") or "")
                if not pid or not status or not _record_event(db, f"status:{pid}:{status}", "STATUS"):
                    continue
                outbox.apply_status(db, pid, status, _timestamp(st.get("timestamp")))
                counts["statuses"] += 1
    return counts


def fetch_pending_media(
    session_factory: sessionmaker,
    provider_factory: Callable[[str], MessagingProvider],
    store: FileStore,
    limit: int = 10,
) -> int:
    """Downloads waiting voice notes and photos into private storage."""
    done = 0
    with session_factory() as db:
        items = db.execute(
            select(InboxItem)
            .where(InboxItem.media_state == MediaState.PENDING)
            .order_by(InboxItem.received_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).scalars().all()
        for item in items:
            channel = db.get(MessagingChannel, item.channel_id)
            assert channel is not None
            try:
                download = provider_factory(channel.phone_number_id).download_media(
                    item.provider_media_id or "", MAX_INBOUND_MEDIA_BYTES
                )
                content_type = check_inbound_media(download.data)
                key = uuid.uuid4().hex
                store.put(key, download.data, content_type)
            except MediaRejected as err:
                item.media_state, item.media_note = MediaState.REJECTED, str(err)
            except ProviderPermanentError as err:
                item.media_state, item.media_note = MediaState.FAILED, f"Could not fetch the file: {err}."[:200]
            except ProviderError:
                continue  # try again on the next run
            except Exception:  # storage failure: keep it pending, never lose the item
                log.exception("storing inbound media failed")
                continue
            else:
                db.add(
                    InboundMedia(
                        inbox_item_id=item.id,
                        storage_key=key,
                        content_type=content_type,
                        size_bytes=len(download.data),
                        sha256=hashlib.sha256(download.data).hexdigest(),
                    )
                )
                item.media_state = MediaState.STORED
                done += 1
        db.commit()
    return done
