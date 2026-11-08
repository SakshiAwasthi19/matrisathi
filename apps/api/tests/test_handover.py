"""F038 (with F008): team workload and handover of an unavailable person's open work."""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.domain.permissions import EVERYDAY, ROLE_CAPABILITIES, Capability
from app.main import app
from app.models.care import CareTask, TaskKind, TaskOutcome, TaskStatus
from app.models.staff import StaffMembership
from tests.conftest import CSRF_HEADERS
from tests.factories import make_mother, make_world

PASSWORD = "synthetic-password-123"
NOW = datetime.now(timezone.utc)


def _client(username: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD}, headers=CSRF_HEADERS)
    assert r.status_code == 200, r.text
    return c


def _task(db, w, episode, owner=None, backup=None, status=TaskStatus.ASSIGNED, due=NOW + timedelta(days=2)):
    t = CareTask(
        episode_id=episode.id, facility_id=w.facility.id, kind=TaskKind.CONTACT, status=status,
        owner_staff_user_id=owner.id if owner else None, backup_staff_user_id=backup.id if backup else None, due_at=due,
    )
    if status is TaskStatus.COMPLETED:
        t.outcome, t.closure_reason, t.closed_at = TaskOutcome.DONE, "CONTACTED", NOW
    db.add(t)
    db.commit()
    return t


def _setup(db):
    w = make_world(db, f"ho{uuid.uuid4().hex[:4]}")
    _, ep = make_mother(db, w, "Synthetic Handover Mother", "+919000000501")
    return w, ep, _client(w.coordinator.username)


def test_workload_counts_owned_overdue_backup_and_unowned(db_session):
    w, ep, c = _setup(db_session)
    _task(db_session, w, ep, owner=w.nurse, backup=w.doctor)
    _task(db_session, w, ep, owner=w.nurse, due=NOW - timedelta(days=1))
    _task(db_session, w, ep, status=TaskStatus.NEW)
    _task(db_session, w, ep, owner=w.nurse, status=TaskStatus.COMPLETED)  # closed: not counted

    load = c.get(f"/api/v1/facilities/{w.facility.id}/workload").json()
    assert load["unowned_open"] == 1
    nurse = next(p for p in load["people"] if p["staff_user_id"] == str(w.nurse.id))
    assert (nurse["owned_open"], nurse["owned_overdue"], nurse["backup_open"], nurse["works_here"]) == (2, 1, 0, True)
    doctor = next(p for p in load["people"] if p["staff_user_id"] == str(w.doctor.id))
    assert doctor["backup_open"] == 1


def test_handover_moves_open_work_only_and_keeps_owner_and_backup_distinct(db_session):
    w, ep, c = _setup(db_session)
    a = _task(db_session, w, ep, owner=w.nurse, backup=w.doctor)
    b = _task(db_session, w, ep, owner=w.nurse, backup=w.coordinator)  # new owner is already the backup
    d = _task(db_session, w, ep, owner=w.doctor, backup=w.nurse)  # nurse is backup here
    closed = _task(db_session, w, ep, owner=w.nurse, status=TaskStatus.COMPLETED)

    r = c.post(
        f"/api/v1/facilities/{w.facility.id}/handover",
        json={"from_staff_user_id": str(w.nurse.id), "to_staff_user_id": str(w.coordinator.id), "reason": "ON_LEAVE"},
        headers=CSRF_HEADERS,
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"owner_moved": 2, "backup_moved": 1}

    db_session.expire_all()
    assert (a.owner_staff_user_id, a.backup_staff_user_id) == (w.coordinator.id, w.doctor.id)
    assert (b.owner_staff_user_id, b.backup_staff_user_id) == (w.coordinator.id, None)
    assert (d.owner_staff_user_id, d.backup_staff_user_id) == (w.doctor.id, w.coordinator.id)
    assert closed.owner_staff_user_id == w.nurse.id  # history untouched
    assert a.version == 2  # optimistic-concurrency version advanced


def test_handover_from_someone_who_left(db_session):
    w, ep, c = _setup(db_session)
    t = _task(db_session, w, ep, owner=w.nurse)
    m = db_session.query(StaffMembership).filter(StaffMembership.staff_user_id == w.nurse.id).one()
    m.active, m.revoked_at = False, NOW
    db_session.commit()

    gone = next(p for p in c.get(f"/api/v1/facilities/{w.facility.id}/workload").json()["people"] if p["staff_user_id"] == str(w.nurse.id))
    assert gone["works_here"] is False and gone["role"] is None and gone["owned_open"] == 1

    r = c.post(
        f"/api/v1/facilities/{w.facility.id}/handover",
        json={"from_staff_user_id": str(w.nurse.id), "to_staff_user_id": str(w.doctor.id), "reason": "LEFT_FACILITY"},
        headers=CSRF_HEADERS,
    )
    assert r.status_code == 200
    db_session.expire_all()
    assert t.owner_staff_user_id == w.doctor.id


def test_handover_refusals(db_session, monkeypatch):
    w, ep, c = _setup(db_session)
    _task(db_session, w, ep, owner=w.nurse)
    url = f"/api/v1/facilities/{w.facility.id}/handover"
    other = make_world(db_session, f"hoo{uuid.uuid4().hex[:4]}")

    def post(client, frm, to, reason="UNAVAILABLE_TODAY"):
        return client.post(url, json={"from_staff_user_id": str(frm.id), "to_staff_user_id": str(to.id), "reason": reason}, headers=CSRF_HEADERS)

    assert post(c, w.nurse, w.nurse).status_code == 422  # same person
    assert post(c, w.nurse, other.nurse).status_code == 422  # new owner must work here
    assert post(c, w.doctor, w.nurse).status_code == 409  # no open work to move
    assert post(_client(other.coordinator.username), w.nurse, w.doctor).status_code == 404  # other facility
    assert c.post(url, json={"from_staff_user_id": str(w.nurse.id), "to_staff_user_id": str(w.doctor.id), "reason": "FREE TEXT"}, headers=CSRF_HEADERS).status_code == 422

    monkeypatch.setitem(ROLE_CAPABILITIES, "COORDINATOR", EVERYDAY - {Capability.HAND_OVER_WORK})
    assert post(c, w.nurse, w.doctor).status_code == 403
