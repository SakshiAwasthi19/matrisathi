"""SG3 outbound messaging: queueing, send-time checks, the worker and delivery
states (W3-A1, W3-A3, W3-B2; AT11, AT12, AT14; T011, T012)."""

import threading
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.main import app
from app.models.care import CareTask, TaskKind
from app.models.messaging import ContactPreference, DetailLevel, OutboxMessage, OutboxStatus
from app.services.messaging import outbox
from tests.conftest import CSRF_HEADERS
from tests.factories import make_mother, make_world
from tests.messaging_helpers import FakeProvider, app_sessions, appointment, consent, local_time, setup_channel

PASSWORD = "synthetic-password-123"
TOMORROW_11 = local_time(11) + timedelta(days=1)  # inside default safe hours, after "now"


def _client(username: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD}, headers=CSRF_HEADERS)
    assert r.status_code == 200, r.text
    return c


def _setup(db, consented: bool = True, **pref):  # type: ignore[no-untyped-def]
    w = make_world(db, f"ob{uuid.uuid4().hex[:4]}")
    person, ep = make_mother(db, w, "Synthetic Messaging Mother", "+919000000701")
    setup_channel(w.org.id)
    if consented:
        consent(db, person.id, w.coordinator.id, **pref)
    appt = appointment(db, w, ep)
    return w, person, ep, appt, _client(w.coordinator.username)


def _queue(c, appt) -> dict:  # type: ignore[no-untyped-def]
    r = c.post(f"/api/v1/appointments/{appt.id}/reminders", json={}, headers=CSRF_HEADERS)
    assert r.status_code == 201, r.text
    return r.json()


def _row(db, msg_id) -> OutboxMessage:  # type: ignore[no-untyped-def]
    db.expire_all()
    return db.get(OutboxMessage, uuid.UUID(msg_id))


def test_reminder_is_sent_once_with_the_approved_template_and_her_details(db_session):
    w, person, ep, appt, c = _setup(db_session)
    queued = _queue(c, appt)
    assert queued["status"] == "QUEUED"
    assert queued["text"].startswith(f"Reminder from {w.facility.name} for ")

    provider = FakeProvider()
    counts = outbox.run_once(app_sessions(), lambda _: provider, "w1", now=TOMORROW_11)
    assert counts == {"SUBMITTED": 1}
    assert len(provider.sent) == 1
    kind, to, name, lang, params = provider.sent[0]
    assert (kind, to, name, lang) == ("template", "919000000701", "rem_min_en", "en")
    assert params[0] == w.facility.name

    # A second pass sends nothing more.
    assert outbox.run_once(app_sessions(), lambda _: provider, "w1", now=TOMORROW_11) == {}
    assert len(provider.sent) == 1
    assert _row(db_session, queued["id"]).status is OutboxStatus.SUBMITTED


def test_no_consent_means_nothing_is_queued(db_session):
    w, person, ep, appt, c = _setup(db_session, consented=False)
    r = c.post(f"/api/v1/appointments/{appt.id}/reminders", json={}, headers=CSRF_HEADERS)
    assert r.status_code == 409
    assert "consent" in r.json()["detail"].lower()


def test_AT14_opt_out_between_queueing_and_sending_blocks_the_send(db_session):
    w, person, ep, appt, c = _setup(db_session)
    queued = _queue(c, appt)
    pref = c.get(f"/api/v1/people/{person.id}/contact-preferences").json()
    r = c.put(
        f"/api/v1/people/{person.id}/contact-preferences",
        json={"expected_version": pref["version"], "messaging_consent": True, "opted_out": True, "detail_level": "MINIMAL"},
        headers=CSRF_HEADERS,
    )
    assert r.status_code == 200, r.text
    provider = FakeProvider()
    outbox.run_once(app_sessions(), lambda _: provider, "w1", now=TOMORROW_11)
    row = _row(db_session, queued["id"])
    assert (row.status, row.status_reason) == (OutboxStatus.BLOCKED, "OPTED_OUT")
    assert provider.sent == []
    # And it shows on the facility's follow-up list.
    failures = c.get(f"/api/v1/facilities/{w.facility.id}/message-failures").json()
    assert [f["id"] for f in failures] == [queued["id"]]


def test_a_changed_appointment_drops_the_stale_reminder(db_session):
    w, person, ep, appt, c = _setup(db_session)
    queued = _queue(c, appt)
    appt.confirmed_for = appt.confirmed_for + timedelta(days=2)
    db_session.commit()  # version moves on
    provider = FakeProvider()
    outbox.run_once(app_sessions(), lambda _: provider, "w1", now=TOMORROW_11)
    row = _row(db_session, queued["id"])
    assert (row.status, row.status_reason) == (OutboxStatus.BLOCKED, "APPOINTMENT_CHANGED")
    assert provider.sent == []


def test_outside_safe_hours_the_send_waits_for_the_next_window(db_session):
    w, person, ep, appt, c = _setup(db_session)
    queued = _queue(c, appt)
    late_night = local_time(22) + timedelta(days=1)
    provider = FakeProvider()
    outbox.run_once(app_sessions(), lambda _: provider, "w1", now=late_night)
    row = _row(db_session, queued["id"])
    assert row.status is OutboxStatus.QUEUED and row.status_reason == "OUTSIDE_SAFE_HOURS"
    assert row.next_attempt_at == local_time(8) + timedelta(days=2)
    assert provider.sent == []


def test_her_preferences_change_what_is_sent(db_session):
    w, person, ep, appt, c = _setup(db_session, language="hi", detail_level=DetailLevel.STANDARD)
    queued = _queue(c, appt)
    assert queued["text"].startswith("Your visit at ")
    provider = FakeProvider()
    outbox.run_once(app_sessions(), lambda _: provider, "w1", now=TOMORROW_11)
    assert provider.sent[0][2:4] == ("rem_std_hi", "hi")


def test_transient_errors_retry_with_backoff_then_fail_with_a_call_task(db_session, monkeypatch):
    monkeypatch.setattr(settings, "messaging_max_attempts", 2)
    w, person, ep, appt, c = _setup(db_session)
    queued = _queue(c, appt)
    provider = FakeProvider(mode="transient")
    outbox.run_once(app_sessions(), lambda _: provider, "w1", now=TOMORROW_11)
    row = _row(db_session, queued["id"])
    assert (row.status, row.attempts, row.status_reason) == (OutboxStatus.QUEUED, 1, "RETRYING")
    assert row.next_attempt_at > datetime.now(timezone.utc)

    outbox.run_once(app_sessions(), lambda _: provider, "w1", now=TOMORROW_11 + timedelta(hours=2))
    row = _row(db_session, queued["id"])
    assert (row.status, row.status_reason) == (OutboxStatus.FAILED, "RETRIES_USED_UP")
    task = db_session.execute(select(CareTask).where(CareTask.source_record_id == row.id)).scalar_one()
    assert task.kind is TaskKind.CONTACT and task.owner_staff_user_id == w.coordinator.id


def test_a_provider_timeout_is_unknown_never_delivered_and_never_resent(db_session):
    w, person, ep, appt, c = _setup(db_session)
    queued = _queue(c, appt)
    provider = FakeProvider(mode="unknown")
    outbox.run_once(app_sessions(), lambda _: provider, "w1", now=TOMORROW_11)
    outbox.run_once(app_sessions(), lambda _: provider, "w1", now=TOMORROW_11 + timedelta(hours=3))
    row = _row(db_session, queued["id"])
    assert row.status is OutboxStatus.UNKNOWN and row.delivered_at is None
    assert len(provider.sent) == 1
    history = c.get(f"/api/v1/people/{person.id}/messages").json()
    assert history[0]["status"] == "UNKNOWN"


def test_a_permanent_refusal_fails_at_once(db_session):
    w, person, ep, appt, c = _setup(db_session)
    queued = _queue(c, appt)
    provider = FakeProvider(mode="permanent")
    outbox.run_once(app_sessions(), lambda _: provider, "w1", now=TOMORROW_11)
    row = _row(db_session, queued["id"])
    assert (row.status, row.status_reason, row.attempts) == (OutboxStatus.FAILED, "PROVIDER_REFUSED", 1)


def test_two_workers_never_send_the_same_message_twice(db_session):
    w, person, ep, appt, c = _setup(db_session)
    ids = [_queue(c, appt)["id"] for _ in range(6)]
    provider = FakeProvider()
    barrier = threading.Barrier(2)

    def work(name: str) -> None:
        barrier.wait()
        outbox.run_once(app_sessions(), lambda _: provider, name, now=TOMORROW_11)

    threads = [threading.Thread(target=work, args=(f"w{i}",)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(provider.sent) == 6
    assert {_row(db_session, i).status for i in ids} == {OutboxStatus.SUBMITTED}


def test_a_worker_that_stops_mid_send_leaves_unknown_not_a_resend(db_session):
    w, person, ep, appt, c = _setup(db_session)
    queued = _queue(c, appt)
    # Simulate: claimed and marked SENDING, then the process died.
    row = _row(db_session, queued["id"])
    row.status, row.leased_by = OutboxStatus.SENDING, "dead-worker"
    row.lease_until = TOMORROW_11 - timedelta(minutes=5)
    row.attempts = 1
    db_session.commit()
    provider = FakeProvider()
    outbox.run_once(app_sessions(), lambda _: provider, "w2", now=TOMORROW_11)
    row = _row(db_session, queued["id"])
    assert (row.status, row.status_reason) == (OutboxStatus.UNKNOWN, "WORKER_STOPPED_MID_SEND")
    assert provider.sent == []


def test_a_worker_that_stops_after_claiming_but_before_sending_is_recovered_once(db_session):
    w, person, ep, appt, c = _setup(db_session)
    queued = _queue(c, appt)
    assert outbox.claim(app_sessions(), "dead-worker", TOMORROW_11) == [uuid.UUID(queued["id"])]
    provider = FakeProvider()
    # Lease still valid: nobody else takes it.
    assert outbox.run_once(app_sessions(), lambda _: provider, "w2", now=TOMORROW_11) == {}
    # Lease expired: taken over and sent once.
    outbox.run_once(app_sessions(), lambda _: provider, "w2", now=TOMORROW_11 + timedelta(minutes=5))
    assert len(provider.sent) == 1
    assert _row(db_session, queued["id"]).status is OutboxStatus.SUBMITTED


def test_delivery_callbacks_only_move_forward_and_failed_wins(db_session):
    w, person, ep, appt, c = _setup(db_session)
    queued = _queue(c, appt)
    outbox.run_once(app_sessions(), lambda _: FakeProvider(), "w1", now=TOMORROW_11)
    pid = _row(db_session, queued["id"]).provider_message_id
    at = datetime.now(timezone.utc)
    with app_sessions()() as s:
        outbox.apply_status(s, pid, "delivered", at)
        outbox.apply_status(s, pid, "sent", at)  # late, out of order
        s.commit()
    assert _row(db_session, queued["id"]).status is OutboxStatus.DELIVERED
    with app_sessions()() as s:
        outbox.apply_status(s, pid, "read", at)
        s.commit()
    assert _row(db_session, queued["id"]).status is OutboxStatus.READ
    with app_sessions()() as s:
        outbox.apply_status(s, pid, "failed", at)
        s.commit()
    assert _row(db_session, queued["id"]).status is OutboxStatus.FAILED


def test_placeholder_templates_are_not_sendable_unless_allowed_for_staff_tests(db_session, monkeypatch):
    w = make_world(db_session, f"ph{uuid.uuid4().hex[:4]}")
    person, ep = make_mother(db_session, w, "Synthetic Placeholder Mother", "+919000000702")
    setup_channel(w.org.id, phone_number_id=f"PH-{uuid.uuid4().hex[:6]}", placeholder=True)
    consent(db_session, person.id, w.coordinator.id)
    appt = appointment(db_session, w, ep)
    c = _client(w.coordinator.username)
    r = c.post(f"/api/v1/appointments/{appt.id}/reminders", json={}, headers=CSRF_HEADERS)
    assert r.status_code == 409 and "template" in r.json()["detail"]
    monkeypatch.setattr(settings, "messaging_allow_placeholder_templates", True)
    assert c.post(f"/api/v1/appointments/{appt.id}/reminders", json={}, headers=CSRF_HEADERS).status_code == 201


def test_preferences_require_both_safe_hours_and_record_who_consented(db_session):
    w, person, ep, appt, c = _setup(db_session, consented=False)
    r = c.put(
        f"/api/v1/people/{person.id}/contact-preferences",
        json={"expected_version": 0, "messaging_consent": True, "safe_from_hour": 9},
        headers=CSRF_HEADERS,
    )
    assert r.status_code == 422
    r = c.put(
        f"/api/v1/people/{person.id}/contact-preferences",
        json={"expected_version": 0, "messaging_consent": True, "safe_from_hour": 9, "safe_to_hour": 18},
        headers=CSRF_HEADERS,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["consent_recorded_by_name"] == "Synthetic Coordinator" and body["version"] == 1
    # A stale version is refused.
    stale = c.put(
        f"/api/v1/people/{person.id}/contact-preferences",
        json={"expected_version": 0, "messaging_consent": False},
        headers=CSRF_HEADERS,
    )
    assert stale.status_code == 409
    pref = db_session.execute(select(ContactPreference).where(ContactPreference.person_id == person.id)).scalar_one()
    assert (pref.safe_from_hour, pref.safe_to_hour) == (9, 18)


def test_other_facilities_cannot_message_or_read_her_messages(db_session):
    w, person, ep, appt, c = _setup(db_session)
    other = make_world(db_session, f"ox{uuid.uuid4().hex[:4]}")
    o = _client(other.coordinator.username)
    assert o.post(f"/api/v1/appointments/{appt.id}/reminders", json={}, headers=CSRF_HEADERS).status_code == 404
    assert o.get(f"/api/v1/people/{person.id}/messages").status_code == 404
    assert o.get(f"/api/v1/people/{person.id}/contact-preferences").status_code == 404


@pytest.mark.parametrize("value,expected", [("+91 90000 00701", "919000000701"), ("9000000701", "919000000701"), ("12", None)])
def test_phone_numbers_are_put_in_the_provider_format(value, expected):
    from app.services.messaging.util import to_provider_number

    assert to_provider_number(value) == expected
