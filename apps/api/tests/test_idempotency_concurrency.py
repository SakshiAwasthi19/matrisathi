"""Idempotency must be enforced by the database, not a check-then-insert
window or a process-local lock. These tests exercise real concurrent
requests against the real Postgres instance (via SQLAlchemy's connection
pool, each thread getting its own connection) — not a mocked race.
"""

import threading
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.conftest import CSRF_HEADERS
from tests.factories import make_facility, make_membership, make_org, make_staff


def _login(client, username, password="synthetic-password-123"):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password}, headers=CSRF_HEADERS)
    assert resp.status_code == 200


def test_truly_concurrent_identical_requests_create_exactly_one_person(db_session):
    from app.main import app

    org = make_org(db_session)
    facility = make_facility(db_session, org)
    staff = make_staff(db_session, "concurrent_staff")
    make_membership(db_session, staff, facility)

    body = {"full_name": "Concurrent Mother", "facility_id": str(facility.id), "phone": "+915555500001"}
    headers = {**CSRF_HEADERS, "Idempotency-Key": "concurrent-key-1"}

    # Two independent clients (independent cookie jars, independent
    # underlying connections), each logged in as the same staff user, firing
    # at the same instant via a barrier.
    client_a, client_b = TestClient(app), TestClient(app)
    _login(client_a, "concurrent_staff")
    _login(client_b, "concurrent_staff")

    barrier = threading.Barrier(2)
    results = {}

    def _fire(name, client):
        barrier.wait(timeout=5)
        results[name] = client.post("/api/v1/people", json=body, headers=headers)

    t1 = threading.Thread(target=_fire, args=("a", client_a))
    t2 = threading.Thread(target=_fire, args=("b", client_b))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert results["a"].status_code == 201
    assert results["b"].status_code == 201
    # Both requests observe the SAME record — the database's unique
    # constraint (not application logic) decided exactly one winner, and
    # the loser was handed the winner's committed result, not left to
    # create its own duplicate.
    assert results["a"].json()["id"] == results["b"].json()["id"]

    rows = db_session.execute(
        text("SELECT count(*) FROM person WHERE full_name = :n"), {"n": "Concurrent Mother"}
    ).scalar()
    assert rows == 1


def test_sequential_retry_returns_same_record(client, db_session):
    org = make_org(db_session)
    facility = make_facility(db_session, org)
    staff = make_staff(db_session, "seq_retry_staff")
    make_membership(db_session, staff, facility)
    _login(client, "seq_retry_staff")

    headers = {**CSRF_HEADERS, "Idempotency-Key": "seq-key-1"}
    body = {"full_name": "Sequential Mother", "facility_id": str(facility.id), "phone": "+915555500002"}

    first = client.post("/api/v1/people", json=body, headers=headers)
    second = client.post("/api/v1/people", json=body, headers=headers)
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]


def test_same_key_different_payload_is_rejected(client, db_session):
    org = make_org(db_session)
    facility = make_facility(db_session, org)
    staff = make_staff(db_session, "conflict_staff")
    make_membership(db_session, staff, facility)
    _login(client, "conflict_staff")

    headers = {**CSRF_HEADERS, "Idempotency-Key": "reused-key"}
    first = client.post(
        "/api/v1/people",
        json={"full_name": "First Body", "facility_id": str(facility.id), "phone": "+915555500003"},
        headers=headers,
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/people",
        json={"full_name": "Different Body", "facility_id": str(facility.id), "phone": "+915555500004"},
        headers=headers,
    )
    assert second.status_code == 409


def test_identical_key_string_is_isolated_across_staff_users(client, db_session):
    org = make_org(db_session)
    facility = make_facility(db_session, org)
    staff_1 = make_staff(db_session, "iso_staff_1")
    make_membership(db_session, staff_1, facility)
    staff_2 = make_staff(db_session, "iso_staff_2")
    make_membership(db_session, staff_2, facility)

    headers = {**CSRF_HEADERS, "Idempotency-Key": "shared-literal-key"}

    _login(client, "iso_staff_1")
    r1 = client.post(
        "/api/v1/people",
        json={"full_name": "Staff One's Mother", "facility_id": str(facility.id), "phone": "+915555500005"},
        headers=headers,
    )
    assert r1.status_code == 201
    client.post("/api/v1/auth/logout", headers=CSRF_HEADERS)

    _login(client, "iso_staff_2")
    r2 = client.post(
        "/api/v1/people",
        json={"full_name": "Staff Two's Mother", "facility_id": str(facility.id), "phone": "+915555500006"},
        headers=headers,
    )
    assert r2.status_code == 201
    assert r2.json()["id"] != r1.json()["id"]
    assert r2.json()["full_name"] == "Staff Two's Mother"


def test_replay_re_enforces_current_authorization(client, db_session):
    org = make_org(db_session)
    facility = make_facility(db_session, org)
    staff = make_staff(db_session, "revoke_replay_staff")
    membership = make_membership(db_session, staff, facility)
    _login(client, "revoke_replay_staff")

    headers = {**CSRF_HEADERS, "Idempotency-Key": "revoke-replay-key"}
    body = {"full_name": "Revoke Replay Mother", "facility_id": str(facility.id), "phone": "+915555500007"}

    first = client.post("/api/v1/people", json=body, headers=headers)
    assert first.status_code == 201

    membership.active = False
    membership.revoked_at = datetime.now(timezone.utc)
    db_session.add(membership)
    db_session.commit()

    # Same key, same body — but the caller is no longer authorized at this
    # facility. The cached result must not be handed back regardless.
    replay = client.post("/api/v1/people", json=body, headers=headers)
    assert replay.status_code == 404
