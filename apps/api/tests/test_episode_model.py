"""D13 / W1-A5: list a mother's episodes, continue her ACTIVE one, and never
let her have two ACTIVE episodes (409 + partial unique index)."""

import importlib.util
import os
import threading
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app.models.audit import AuditEvent, AuditOutcome
from app.models.pregnancy import PregnancyEpisode, PregnancyEpisodeStatus
from tests.conftest import CSRF_HEADERS
from tests.factories import make_facility, make_membership, make_org, make_staff

PASSWORD = "synthetic-password-123"


def _login(client, username):
    resp = client.post(
        "/api/v1/auth/login", json={"username": username, "password": PASSWORD}, headers=CSRF_HEADERS
    )
    assert resp.status_code == 200


def _setup(db_session):
    org = make_org(db_session)
    facility_a = make_facility(db_session, org, "Facility A")
    facility_b = make_facility(db_session, org, "Facility B")
    staff_a = make_staff(db_session, "ep_staff_a")
    make_membership(db_session, staff_a, facility_a)
    staff_b = make_staff(db_session, "ep_staff_b")
    make_membership(db_session, staff_b, facility_b)
    return facility_a, facility_b


def _register(client, facility, name="Synthetic Mother", phone="+915555500001"):
    resp = client.post(
        "/api/v1/people",
        json={"full_name": name, "facility_id": str(facility.id), "phone": phone},
        headers=CSRF_HEADERS,
    )
    assert resp.status_code == 201
    return resp.json()


def _create_episode(client, person_id, key=None):
    headers = dict(CSRF_HEADERS)
    if key:
        headers["Idempotency-Key"] = key
    return client.post("/api/v1/pregnancy-episodes", json={"person_id": person_id}, headers=headers)


# --- Listing --------------------------------------------------------------


def test_list_episodes_returns_the_mothers_episodes(client, db_session):
    facility_a, _ = _setup(db_session)
    _login(client, "ep_staff_a")
    person = _register(client, facility_a)

    assert client.get(f"/api/v1/people/{person['id']}/episodes").json() == []

    episode = _create_episode(client, person["id"]).json()
    listed = client.get(f"/api/v1/people/{person['id']}/episodes")
    assert listed.status_code == 200
    assert [e["id"] for e in listed.json()] == [episode["id"]]
    assert listed.json()[0]["status"] == "ACTIVE"


def test_list_episodes_is_facility_scoped_and_denial_is_audited(client, db_session):
    facility_a, _ = _setup(db_session)
    _login(client, "ep_staff_a")
    person = _register(client, facility_a)
    _create_episode(client, person["id"])
    client.post("/api/v1/auth/logout", headers=CSRF_HEADERS)

    _login(client, "ep_staff_b")
    resp = client.get(f"/api/v1/people/{person['id']}/episodes")
    assert resp.status_code == 404  # not 403: never reveal another facility's records

    denied = (
        db_session.query(AuditEvent)
        .filter(
            AuditEvent.action == "list_episodes",
            AuditEvent.entity_id == person["id"],
            AuditEvent.outcome == AuditOutcome.DENIED,
        )
        .count()
    )
    assert denied == 1


def test_list_episodes_for_unknown_person_is_404(client, db_session):
    _setup(db_session)
    _login(client, "ep_staff_a")
    assert client.get(f"/api/v1/people/{uuid.uuid4()}/episodes").status_code == 404


# --- One ACTIVE episode per mother ------------------------------------------


def test_second_active_episode_is_409_pointing_at_the_existing_one(client, db_session):
    facility_a, _ = _setup(db_session)
    _login(client, "ep_staff_a")
    person = _register(client, facility_a)
    first = _create_episode(client, person["id"], key="key-1").json()

    second = _create_episode(client, person["id"], key="key-2")
    assert second.status_code == 409
    assert second.json()["detail"]["existing_episode_id"] == first["id"]

    # Continuing never duplicates: still exactly one episode for her.
    episodes = client.get(f"/api/v1/people/{person['id']}/episodes").json()
    assert [e["id"] for e in episodes] == [first["id"]]


def test_retry_with_same_idempotency_key_still_returns_the_original(client, db_session):
    facility_a, _ = _setup(db_session)
    _login(client, "ep_staff_a")
    person = _register(client, facility_a)
    first = _create_episode(client, person["id"], key="same-key")
    retry = _create_episode(client, person["id"], key="same-key")
    assert first.status_code == 201
    assert retry.status_code == 201
    assert retry.json()["id"] == first.json()["id"]


def test_new_episode_allowed_once_the_previous_one_is_closed(client, db_session):
    facility_a, _ = _setup(db_session)
    _login(client, "ep_staff_a")
    person = _register(client, facility_a)
    first = _create_episode(client, person["id"]).json()

    # There is no close endpoint yet (Phase 3); close it directly as the
    # migrator would, to prove the rule only counts ACTIVE episodes.
    _as_migrator(
        "UPDATE pregnancy_episode SET status = 'CLOSED', closed_at = now() WHERE id = :id", id=first["id"]
    )
    second = _create_episode(client, person["id"])
    assert second.status_code == 201
    assert second.json()["id"] != first["id"]


def test_mothers_are_independent(client, db_session):
    facility_a, _ = _setup(db_session)
    _login(client, "ep_staff_a")
    # Two women on one shared phone: each gets her own active episode.
    mother_1 = _register(client, facility_a, "Synthetic Mother One", "+915555500009")
    mother_2 = _register(client, facility_a, "Synthetic Mother Two", "+915555500009")
    assert _create_episode(client, mother_1["id"]).status_code == 201
    assert _create_episode(client, mother_2["id"]).status_code == 201


def test_concurrent_creates_leave_exactly_one_active_episode(client, db_session):
    """Two simultaneous creates for the same mother (different keys): the
    partial unique index lets one win; the other gets a clean 409, not 500."""
    from fastapi.testclient import TestClient

    from app.main import app

    facility_a, _ = _setup(db_session)
    _login(client, "ep_staff_a")
    person = _register(client, facility_a)
    cookies = dict(client.cookies)

    statuses: list[int] = []
    barrier = threading.Barrier(4)

    def worker(n: int) -> None:
        with TestClient(app) as c:
            c.cookies.update(cookies)
            barrier.wait()
            resp = _create_episode(c, person["id"], key=f"race-{n}")
            statuses.append(resp.status_code)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(statuses) == [201, 409, 409, 409]
    active = (
        db_session.query(PregnancyEpisode)
        .filter(
            PregnancyEpisode.mother_person_id == uuid.UUID(person["id"]),
            PregnancyEpisode.status == PregnancyEpisodeStatus.ACTIVE,
        )
        .count()
    )
    assert active == 1


def test_database_rejects_a_second_active_episode_directly():
    """The rule holds even for code that bypasses the API."""
    from sqlalchemy.exc import IntegrityError

    engine = create_engine(os.environ["DATABASE_URL_APP"])
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            ids = _insert_person_with_staff(conn)
            insert = text(
                "INSERT INTO pregnancy_episode (id, mother_person_id, facility_id, dating_source, status, "
                "created_by_staff_user_id, created_at, updated_at) VALUES (:id, :p, :f, 'UNKNOWN', 'ACTIVE', "
                ":s, now(), now())"
            )
            conn.execute(insert, {"id": uuid.uuid4(), **ids})
            with pytest.raises(IntegrityError, match="uq_pregnancy_episode_one_active"):
                conn.execute(insert, {"id": uuid.uuid4(), **ids})
        finally:
            trans.rollback()
    engine.dispose()


# --- Migration duplicate check ---------------------------------------------


def _migration():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "a13d5e0c7f01_one_active_episode_per_mother.py"
    )
    spec = importlib.util.spec_from_file_location("migration_a13d5e0c7f01", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_refuses_when_duplicates_exist_and_changes_nothing():
    m = _migration()
    engine = create_engine(os.environ["DATABASE_URL_MIGRATOR"])
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            m.assert_no_duplicate_active_episodes(conn)  # clean database: passes

            # Simulate a database from before the rule existed.
            conn.execute(text(f"DROP INDEX {m.INDEX_NAME}"))
            ids = _insert_person_with_staff(conn)
            for _ in range(2):
                conn.execute(
                    text(
                        "INSERT INTO pregnancy_episode (id, mother_person_id, facility_id, dating_source, "
                        "status, created_by_staff_user_id, created_at, updated_at) VALUES (:id, :p, :f, "
                        "'UNKNOWN', 'ACTIVE', :s, now(), now())"
                    ),
                    {"id": uuid.uuid4(), **ids},
                )
            with pytest.raises(RuntimeError, match="1 mother\\(s\\) have more than one ACTIVE") as exc:
                m.assert_no_duplicate_active_episodes(conn)
            assert ids["p"].hex not in str(exc.value)  # no identifiers in the message
        finally:
            trans.rollback()  # restores the index and removes the rows
    engine.dispose()


# --- helpers ---------------------------------------------------------------


def _as_migrator(sql: str, **params) -> None:
    engine = create_engine(os.environ["DATABASE_URL_MIGRATOR"])
    with engine.begin() as conn:
        conn.execute(text(sql), params)
    engine.dispose()


def _insert_person_with_staff(conn) -> dict:
    org_id, facility_id, staff_id, person_id = (uuid.uuid4() for _ in range(4))
    conn.execute(
        text("INSERT INTO organization (id, name, created_at, updated_at) VALUES (:id, 'Org', now(), now())"),
        {"id": org_id},
    )
    conn.execute(
        text(
            "INSERT INTO facility (id, organization_id, name, active, created_at, updated_at) "
            "VALUES (:id, :o, 'Fac', true, now(), now())"
        ),
        {"id": facility_id, "o": org_id},
    )
    conn.execute(
        text(
            "INSERT INTO staff_user (id, username, full_name, password_hash, active, created_at, updated_at) "
            "VALUES (:id, :u, 'Staff', 'x', true, now(), now())"
        ),
        {"id": staff_id, "u": f"raw_{staff_id.hex[:8]}"},
    )
    conn.execute(
        text(
            "INSERT INTO person (id, full_name, age_precision, registering_facility_id, created_at, updated_at) "
            "VALUES (:id, 'Synthetic', 'UNKNOWN', :f, now(), now())"
        ),
        {"id": person_id, "f": facility_id},
    )
    return {"p": person_id, "f": facility_id, "s": staff_id}
