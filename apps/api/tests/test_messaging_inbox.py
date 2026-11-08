"""SG3 inbound messaging: signed webhooks, dedupe, the unlinked queue, linking
after an identity check, media privacy, opt-out and replies
(W3-A1, W3-A2, W3-A4, W3-B1; AT12, AT13, AT14; M018)."""

import hashlib
import hmac
import json
import threading
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import settings
from app.main import app
from app.models.pregnancy import PregnancyEpisode
from app.models.messaging import ContactPreference, InboxItem, MediaState, OutboxKind, OutboxMessage
from app.services.file_store import LocalDiskFileStore, get_file_store
from app.services.messaging import inbound, outbox
from tests.conftest import CSRF_HEADERS
from tests.factories import make_mother, make_world
from tests.messaging_helpers import (
    PHONE_NUMBER_ID,
    FakeProvider,
    app_sessions,
    appointment,
    consent,
    local_time,
    setup_channel,
)

PASSWORD = "synthetic-password-123"
SECRET = "test-app-secret"
SHARED = "+919000000801"
OGG = b"OggS" + b"\x00" * 200


@pytest.fixture(autouse=True)
def _messaging_on(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "messaging_provider", "meta")
    monkeypatch.setattr(settings, "whatsapp_app_secret", SECRET)
    monkeypatch.setattr(settings, "whatsapp_verify_token", "verify-me")
    app.dependency_overrides[get_file_store] = lambda: LocalDiskFileStore(tmp_path)
    yield
    app.dependency_overrides.pop(get_file_store, None)


def _client(username: str | None = None) -> TestClient:
    c = TestClient(app)
    if username:
        r = c.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD}, headers=CSRF_HEADERS)
        assert r.status_code == 200, r.text
    return c


def _payload(messages=(), statuses=(), phone_number_id=PHONE_NUMBER_ID) -> bytes:  # type: ignore[no-untyped-def]
    return json.dumps(
        {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "WABA",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {"phone_number_id": phone_number_id},
                                "messages": list(messages),
                                "statuses": list(statuses),
                            },
                        }
                    ],
                }
            ],
        }
    ).encode()


def _text(body: str, sender: str = SHARED, mid: str | None = None, at: datetime | None = None) -> dict:
    ts = int((at or datetime.now(timezone.utc)).timestamp())
    return {"from": sender.lstrip("+"), "id": mid or f"wamid.{uuid.uuid4().hex}", "timestamp": str(ts), "type": "text", "text": {"body": body}}


def _voice(sender: str = SHARED) -> dict:
    return {
        "from": sender.lstrip("+"),
        "id": f"wamid.{uuid.uuid4().hex}",
        "timestamp": str(int(datetime.now(timezone.utc).timestamp())),
        "type": "audio",
        "audio": {"id": "MEDIA-1", "mime_type": "audio/ogg; codecs=opus", "voice": True},
    }


def _post(body: bytes, secret: str | None = SECRET):  # type: ignore[no-untyped-def]
    headers = {"Content-Type": "application/json"}
    if secret is not None:
        headers["X-Hub-Signature-256"] = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return _client().post("/api/v1/webhooks/whatsapp", content=body, headers=headers)


def _items(db) -> list[InboxItem]:  # type: ignore[no-untyped-def]
    db.expire_all()
    return list(db.execute(select(InboxItem).order_by(InboxItem.received_at)).scalars())


def _world(db):  # type: ignore[no-untyped-def]
    w = make_world(db, f"ib{uuid.uuid4().hex[:4]}")
    first, _ = make_mother(db, w, "Synthetic Sister One", SHARED)
    second, _ = make_mother(db, w, "Synthetic Sister Two", SHARED)
    setup_channel(w.org.id)
    return w, first, second


# --- webhook security ------------------------------------------------------------------


def test_subscription_check_needs_the_verify_token():
    c = _client()
    ok = c.get("/api/v1/webhooks/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": "verify-me", "hub.challenge": "42"})
    assert ok.status_code == 200 and ok.text == "42"
    bad = c.get("/api/v1/webhooks/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": "nope", "hub.challenge": "42"})
    assert bad.status_code == 403


def test_unsigned_or_wrongly_signed_webhooks_are_rejected_and_store_nothing(db_session):
    _world(db_session)
    body = _payload([_text("hello")])
    assert _post(body, secret=None).status_code == 401
    assert _post(body, secret="wrong-secret").status_code == 401
    assert _items(db_session) == []


def test_webhook_is_refused_while_messaging_is_disabled(db_session, monkeypatch):
    monkeypatch.setattr(settings, "messaging_provider", "disabled")
    assert _post(_payload([_text("hello")])).status_code == 503


# --- AT12 / AT13: one event, one item; never auto-linked ------------------------------


def test_AT13_the_same_webhook_twice_makes_one_unlinked_item(db_session):
    w, first, second = _world(db_session)
    body = _payload([_text("I cannot come tomorrow", mid="wamid.SAME")])
    assert _post(body).status_code == 200
    assert _post(body).status_code == 200
    items = _items(db_session)
    assert len(items) == 1
    item = items[0]
    assert item.person_id is None  # shared number: never linked automatically
    assert item.facility_id == w.facility.id  # both people are registered here
    assert item.text_body == "I cannot come tomorrow"


def test_concurrent_deliveries_of_one_event_still_make_one_item(db_session):
    _world(db_session)
    body = _payload([_text("same event", mid="wamid.RACE")])
    barrier = threading.Barrier(3)
    codes: list[int] = []

    def deliver() -> None:
        barrier.wait()
        codes.append(_post(body).status_code)

    threads = [threading.Thread(target=deliver) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert codes.count(200) >= 1
    assert db_session.execute(select(func.count()).select_from(InboxItem)).scalar_one() == 1


def test_unknown_channels_are_ignored(db_session):
    _world(db_session)
    assert _post(_payload([_text("hi")], phone_number_id="SOMEONE-ELSE")).status_code == 200
    assert _items(db_session) == []


# --- unlinked queue: coordinators only ------------------------------------------------


def test_unlinked_messages_are_visible_only_to_coordinators(db_session):
    w, first, second = _world(db_session)
    _post(_payload([_text("who am I?")]))
    item = _items(db_session)[0]
    coord, nurse = _client(w.coordinator.username), _client(w.nurse.username)
    assert [i["id"] for i in coord.get(f"/api/v1/facilities/{w.facility.id}/inbox", params={"view": "unlinked"}).json()] == [str(item.id)]
    assert coord.get(f"/api/v1/inbox/{item.id}").json()["people_on_number"] == 2
    assert nurse.get(f"/api/v1/facilities/{w.facility.id}/inbox").json() == []
    assert nurse.get(f"/api/v1/facilities/{w.facility.id}/inbox", params={"view": "unlinked"}).status_code == 403
    assert nurse.get(f"/api/v1/inbox/{item.id}").status_code == 404


def test_linking_needs_a_coordinator_and_an_identity_check_then_the_team_sees_it(db_session):
    w, first, second = _world(db_session)
    _post(_payload([_text("this is Sister Two")]))
    item = _items(db_session)[0]
    coord, nurse = _client(w.coordinator.username), _client(w.nurse.username)
    missing_check = coord.post(
        f"/api/v1/inbox/{item.id}/link", json={"expected_version": item.version, "person_id": str(second.id)}, headers=CSRF_HEADERS
    )
    assert missing_check.status_code == 422
    r = coord.post(
        f"/api/v1/inbox/{item.id}/link",
        json={"expected_version": item.version, "person_id": str(second.id), "identity_check": "CALLED_BACK"},
        headers=CSRF_HEADERS,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["person_name"], body["identity_check"], body["linked_by_name"]) == (
        "Synthetic Sister Two",
        "CALLED_BACK",
        "Synthetic Coordinator",
    )
    assert body["owner_name"] == "Synthetic Coordinator"
    assert nurse.get(f"/api/v1/inbox/{item.id}").status_code == 200
    again = coord.post(
        f"/api/v1/inbox/{item.id}/link",
        json={"expected_version": body["version"], "person_id": str(first.id), "identity_check": "IN_PERSON"},
        headers=CSRF_HEADERS,
    )
    assert again.status_code == 409


def test_a_person_from_another_organization_cannot_be_linked(db_session):
    w, first, second = _world(db_session)
    other = make_world(db_session, f"io{uuid.uuid4().hex[:4]}")
    stranger, _ = make_mother(db_session, other, "Synthetic Stranger", SHARED)
    _post(_payload([_text("hello")]))
    item = _items(db_session)[0]
    r = _client(w.coordinator.username).post(
        f"/api/v1/inbox/{item.id}/link",
        json={"expected_version": item.version, "person_id": str(stranger.id), "identity_check": "CALLED_BACK"},
        headers=CSRF_HEADERS,
    )
    assert r.status_code == 404
    # And the other organization's coordinator never sees this item.
    assert _client(other.coordinator.username).get(f"/api/v1/inbox/{item.id}").status_code == 404


def test_assign_owner_and_backup_and_close_with_an_outcome(db_session):
    w, first, second = _world(db_session)
    _post(_payload([_text("please call")]))
    item = _items(db_session)[0]
    coord = _client(w.coordinator.username)
    nurse_owner = coord.post(
        f"/api/v1/inbox/{item.id}/assign",
        json={"expected_version": item.version, "owner_staff_user_id": str(w.nurse.id)},
        headers=CSRF_HEADERS,
    )
    assert nurse_owner.status_code == 422  # unlinked: only a coordinator may own it
    linked = coord.post(
        f"/api/v1/inbox/{item.id}/link",
        json={"expected_version": item.version, "person_id": str(first.id), "identity_check": "ASKED_IDENTIFYING_DETAILS"},
        headers=CSRF_HEADERS,
    ).json()
    assigned = coord.post(
        f"/api/v1/inbox/{item.id}/assign",
        json={"expected_version": linked["version"], "owner_staff_user_id": str(w.nurse.id), "backup_staff_user_id": str(w.doctor.id)},
        headers=CSRF_HEADERS,
    )
    assert assigned.status_code == 200, assigned.text
    assert (assigned.json()["owner_name"], assigned.json()["backup_name"]) == ("Synthetic Nurse", "Synthetic Doctor")
    nurse = _client(w.nurse.username)
    assert [i["id"] for i in nurse.get(f"/api/v1/facilities/{w.facility.id}/inbox", params={"view": "mine"}).json()] == [str(item.id)]
    closed = nurse.post(
        f"/api/v1/inbox/{item.id}/close",
        json={"expected_version": assigned.json()["version"], "outcome": "CALLED", "note": "Spoke to her"},
        headers=CSRF_HEADERS,
    )
    assert closed.status_code == 200 and closed.json()["status"] == "CLOSED"
    assert nurse.get(f"/api/v1/facilities/{w.facility.id}/inbox").json() == []


# --- replies and the service window ------------------------------------------------------


def _linked_item(db, w, person, at=None):  # type: ignore[no-untyped-def]
    _post(_payload([_text("hello", at=at)]))
    item = _items(db)[-1]
    linked = _client(w.coordinator.username).post(
        f"/api/v1/inbox/{item.id}/link",
        json={"expected_version": item.version, "person_id": str(person.id), "identity_check": "CALLED_BACK"},
        headers=CSRF_HEADERS,
    )
    assert linked.status_code == 200, linked.text
    return item, linked.json()


def test_free_text_reply_inside_the_window_is_queued_once(db_session):
    w, first, second = _world(db_session)
    consent(db_session, first.id, w.coordinator.id)
    item, linked = _linked_item(db_session, w, first)
    coord = _client(w.coordinator.username)
    assert linked["can_reply_free_text"] is True
    r = coord.post(
        f"/api/v1/inbox/{item.id}/reply", json={"expected_version": linked["version"], "text": "We will call you today."}, headers=CSRF_HEADERS
    )
    assert r.status_code == 200, r.text
    assert [m["text"] for m in r.json()["replies"]] == ["We will call you today."]
    msg = db_session.execute(select(OutboxMessage).where(OutboxMessage.inbox_item_id == item.id)).scalar_one()
    assert msg.kind is OutboxKind.TEXT


def test_free_text_after_24_hours_is_refused(db_session):
    w, first, second = _world(db_session)
    consent(db_session, first.id, w.coordinator.id)
    item, linked = _linked_item(db_session, w, first, at=datetime.now(timezone.utc) - timedelta(hours=30))
    assert linked["can_reply_free_text"] is False
    r = _client(w.coordinator.username).post(
        f"/api/v1/inbox/{item.id}/reply", json={"expected_version": linked["version"], "text": "Hello"}, headers=CSRF_HEADERS
    )
    assert r.status_code == 409 and "24 hours" in r.json()["detail"]


def test_replying_to_an_unlinked_message_is_refused(db_session):
    w, first, second = _world(db_session)
    _post(_payload([_text("hello")]))
    item = _items(db_session)[0]
    r = _client(w.coordinator.username).post(
        f"/api/v1/inbox/{item.id}/reply", json={"expected_version": item.version, "text": "Hi"}, headers=CSRF_HEADERS
    )
    assert r.status_code == 409


# --- AT14: STOP --------------------------------------------------------------------------


def test_stop_opts_out_everyone_on_that_number_at_once(db_session):
    w, first, second = _world(db_session)
    consent(db_session, first.id, w.coordinator.id)
    _post(_payload([_text("STOP")]))
    db_session.expire_all()
    prefs = {p.person_id: p for p in db_session.execute(select(ContactPreference)).scalars()}
    assert prefs[first.id].opted_out and prefs[second.id].opted_out
    assert prefs[first.id].opt_out_source.value == "INBOUND_KEYWORD"
    assert prefs[second.id].messaging_consent is False  # STOP never grants consent
    assert "Opt-out received" in (_items(db_session)[0].media_note or "")


# --- media: private storage, size and type rules ----------------------------------------


def test_voice_notes_are_stored_privately_and_served_only_to_those_who_may_see_them(db_session, tmp_path):
    w, first, second = _world(db_session)
    _post(_payload([_voice()]))
    store = LocalDiskFileStore(tmp_path)
    assert inbound.fetch_pending_media(app_sessions(), lambda _: FakeProvider(media=OGG), store) == 1
    item = _items(db_session)[0]
    assert item.media_state is MediaState.STORED
    coord = _client(w.coordinator.username)
    r = coord.get(f"/api/v1/inbox/{item.id}/media")
    assert r.status_code == 200 and r.headers["content-type"] == "audio/ogg" and r.content == OGG
    assert r.headers["cache-control"] == "no-store"
    assert _client(w.nurse.username).get(f"/api/v1/inbox/{item.id}/media").status_code == 404
    assert _client().get(f"/api/v1/inbox/{item.id}/media").status_code == 401


def test_unsupported_or_oversized_files_are_not_kept(db_session, tmp_path):
    w, first, second = _world(db_session)
    _post(_payload([_voice(), _voice()]))
    store = LocalDiskFileStore(tmp_path)
    inbound.fetch_pending_media(app_sessions(), lambda _: FakeProvider(media=b"MZ\x90\x00not-audio"), store, limit=1)
    inbound.fetch_pending_media(app_sessions(), lambda _: FakeProvider(mode="media_permanent"), store, limit=1)
    states = sorted(i.media_state.value for i in _items(db_session))
    assert states == ["FAILED", "REJECTED"]
    assert list(tmp_path.rglob("*")) == [] or all(p.is_dir() for p in tmp_path.rglob("*"))


def test_other_message_types_are_recorded_as_not_accepted(db_session):
    _world(db_session)
    sticker = {"from": SHARED.lstrip("+"), "id": "wamid.STICKER", "timestamp": "1700000000", "type": "sticker", "sticker": {"id": "S"}}
    _post(_payload([sticker]))
    item = _items(db_session)[0]
    assert item.media_state is MediaState.REJECTED and "only text, voice notes and photos" in (item.media_note or "")


# --- delivery statuses through the webhook ---------------------------------------------


def test_status_callbacks_update_the_message_once(db_session):
    w, first, second = _world(db_session)
    consent(db_session, first.id, w.coordinator.id)
    episode = db_session.execute(
        select(PregnancyEpisode).where(PregnancyEpisode.mother_person_id == first.id)
    ).scalar_one()
    appt = appointment(db_session, w, episode)
    coord = _client(w.coordinator.username)
    msg_id = coord.post(f"/api/v1/appointments/{appt.id}/reminders", json={}, headers=CSRF_HEADERS).json()["id"]
    outbox.run_once(app_sessions(), lambda _: FakeProvider(), "w1", now=local_time(11) + timedelta(days=1))
    db_session.expire_all()
    pid = db_session.get(OutboxMessage, uuid.UUID(msg_id)).provider_message_id
    status = {"id": pid, "status": "delivered", "timestamp": str(int(datetime.now(timezone.utc).timestamp())), "recipient_id": "x"}
    _post(_payload(statuses=[status]))
    _post(_payload(statuses=[status]))
    history = coord.get(f"/api/v1/people/{first.id}/messages").json()
    assert history[0]["status"] == "DELIVERED" and history[0]["delivered_at"] is not None
