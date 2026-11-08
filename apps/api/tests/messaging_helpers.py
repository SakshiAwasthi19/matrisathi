"""Test helpers for SG3 messaging. The fake provider here exists only in tests:
it never counts towards the SG3 gate, which needs the real provider."""

import os
import threading
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.care import Appointment, AppointmentStatus, TemplateStatus
from app.models.messaging import (
    ContactPreference,
    DetailLevel,
    MessagePurpose,
    MessageTemplate,
    MessagingChannel,
)
from app.services.messaging.provider import (
    MediaDownload,
    ProviderPermanentError,
    ProviderTransientError,
    ProviderUnknownOutcome,
    SendResult,
)

PHONE_NUMBER_ID = "SANDBOX-PHONE-ID"


@contextmanager
def migrator_session():
    engine = create_engine(os.environ["DATABASE_URL_MIGRATOR"])
    try:
        with Session(engine) as s:
            yield s
    finally:
        engine.dispose()


def setup_channel(org_id: uuid.UUID, phone_number_id: str = PHONE_NUMBER_ID, placeholder: bool = False) -> None:
    """A channel plus approved templates (English and Hindi, both detail levels)."""
    with migrator_session() as s:
        s.add(
            MessagingChannel(
                organization_id=org_id, provider="meta", phone_number_id=phone_number_id, display_label="Test", active=True
            )
        )
        for lang in ("en", "hi"):
            for detail, name, body, variables in (
                (DetailLevel.MINIMAL, f"rem_min_{lang}", "Reminder from {{1}} for {{2}}.", ["facility_name", "appointment_date"]),
                (DetailLevel.STANDARD, f"rem_std_{lang}", "Your visit at {{1}} is on {{2}}.", ["place", "appointment_date"]),
            ):
                s.add(
                    MessageTemplate(
                        organization_id=org_id,
                        purpose=MessagePurpose.APPOINTMENT_REMINDER,
                        language=lang,
                        detail_level=detail,
                        version_label="v1",
                        provider_template_name=name,
                        body_text=body,
                        variable_names=variables,
                        status=TemplateStatus.APPROVED,
                        is_placeholder=placeholder,
                        approved_by_name=None if placeholder else "Synthetic Reviewer (Doctor)",
                        approved_on=None if placeholder else date(2026, 11, 1),
                    )
                )
            s.add(
                MessageTemplate(
                    organization_id=org_id,
                    purpose=MessagePurpose.FOLLOW_UP,
                    language=lang,
                    detail_level=DetailLevel.MINIMAL,
                    version_label="v1",
                    provider_template_name=f"fu_min_{lang}",
                    body_text="{{1}} tried to reach you.",
                    variable_names=["facility_name"],
                    status=TemplateStatus.APPROVED,
                    is_placeholder=placeholder,
                    approved_by_name=None if placeholder else "Synthetic Reviewer (Doctor)",
                    approved_on=None if placeholder else date(2026, 11, 1),
                )
            )
        s.commit()


def consent(db, person_id, staff_id, **kw) -> ContactPreference:  # type: ignore[no-untyped-def]
    pref = ContactPreference(
        person_id=person_id,
        messaging_consent=True,
        consent_recorded_at=datetime.now(timezone.utc),
        consent_recorded_by_staff_user_id=staff_id,
        opted_out=False,
        prefers_call=False,
        detail_level=kw.pop("detail_level", DetailLevel.MINIMAL),
        **kw,
    )
    db.add(pref)
    db.commit()
    return pref


def appointment(db, world, episode, days: int = 3) -> Appointment:  # type: ignore[no-untyped-def]
    a = Appointment(
        episode_id=episode.id,
        facility_id=world.facility.id,
        status=AppointmentStatus.CONFIRMED,
        confirmed_for=datetime.now(timezone.utc) + timedelta(days=days),
        owner_staff_user_id=world.coordinator.id,
    )
    db.add(a)
    db.commit()
    return a


class FakeProvider:
    """Records every call. `mode` decides the outcome of sends."""

    name = "fake"

    def __init__(self, mode: str = "ok", media: bytes = b"", media_type: str | None = None) -> None:
        self.mode = mode
        self.sent: list[tuple] = []
        self.lock = threading.Lock()
        self.media = media
        self.media_type = media_type

    def _send(self, record: tuple) -> SendResult:
        with self.lock:
            self.sent.append(record)
            n = len(self.sent)
        if self.mode == "transient":
            raise ProviderTransientError("could not reach the provider")
        if self.mode == "permanent":
            raise ProviderPermanentError("provider refused (400)")
        if self.mode == "unknown":
            raise ProviderUnknownOutcome("no answer from the provider")
        return SendResult(provider_message_id=f"wamid.TEST{n}.{uuid.uuid4().hex[:8]}")

    def send_template(self, to, template_name, language, parameters):  # type: ignore[no-untyped-def]
        return self._send(("template", to, template_name, language, tuple(parameters)))

    def send_text(self, to, body):  # type: ignore[no-untyped-def]
        return self._send(("text", to, body))

    def download_media(self, media_id, max_bytes):  # type: ignore[no-untyped-def]
        if self.mode == "media_permanent":
            raise ProviderPermanentError("media larger than the limit")
        return MediaDownload(data=self.media, declared_type=self.media_type)


def app_sessions() -> sessionmaker:
    from app.core.db import SessionLocal

    return SessionLocal


def local_time(hour: int) -> datetime:
    """Today at `hour` local time (UTC+05:30), as an aware UTC datetime."""
    ist = timezone(timedelta(minutes=330))
    now = datetime.now(ist)
    return now.replace(hour=hour, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
