import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from app.core.db import SessionLocal, engine
from app.models.audit import AuditEvent, AuditOutcome
from app.services import audit_service
from tests.conftest import CSRF_HEADERS
from tests.factories import make_facility, make_membership, make_org, make_staff


def _login(client, username, password="synthetic-password-123"):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password}, headers=CSRF_HEADERS)
    assert resp.status_code == 200


def test_create_and_read_each_produce_one_audit_row(client, db_session):
    org = make_org(db_session)
    facility = make_facility(db_session, org)
    staff = make_staff(db_session, "audit_staff")
    make_membership(db_session, staff, facility)

    _login(client, "audit_staff")
    person = client.post(
        "/api/v1/people",
        json={"full_name": "Audited Mother", "facility_id": str(facility.id), "phone": "+913333333331"},
        headers=CSRF_HEADERS,
    ).json()
    client.get(f"/api/v1/people/{person['id']}")

    rows = db_session.query(AuditEvent).filter(AuditEvent.entity_id == person["id"]).all()
    actions = sorted((r.action, r.outcome) for r in rows)
    assert actions == [("create", AuditOutcome.SUCCESS), ("read", AuditOutcome.SUCCESS)]


def test_denied_access_writes_a_denied_audit_row(client, db_session):
    org = make_org(db_session)
    facility_a = make_facility(db_session, org, "Facility A")
    facility_b = make_facility(db_session, org, "Facility B")
    staff_a = make_staff(db_session, "audit_a")
    make_membership(db_session, staff_a, facility_a)
    staff_b = make_staff(db_session, "audit_b")
    make_membership(db_session, staff_b, facility_b)

    _login(client, "audit_a")
    person = client.post(
        "/api/v1/people",
        json={"full_name": "Audited Mother B", "facility_id": str(facility_a.id), "phone": "+913333333332"},
        headers=CSRF_HEADERS,
    ).json()
    client.post("/api/v1/auth/logout", headers=CSRF_HEADERS)

    _login(client, "audit_b")
    resp = client.get(f"/api/v1/people/{person['id']}")
    assert resp.status_code == 404

    denied = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.entity_id == person["id"], AuditEvent.outcome == AuditOutcome.DENIED)
        .all()
    )
    assert len(denied) == 1
    # No clinical content — just structural facts.
    assert denied[0].metadata_json == {}


def test_audit_row_survives_rollback_of_the_caller_session():
    """The audit write uses its own session/transaction (AuditSessionLocal),
    independent of whatever session the calling request used. Simulates a
    request whose own transaction is rolled back after the audit call, and
    confirms the audit row is unaffected."""
    caller_session = SessionLocal()
    try:
        audit_service.record_event(
            actor_staff_user_id=None,
            action="simulated_denial",
            entity_type="Test",
            entity_id="durability-check",
            outcome=AuditOutcome.DENIED,
            metadata={},
        )

        # Now roll back the caller's own session, as if the request failed.
        caller_session.rollback()
    finally:
        caller_session.close()

    verify_session = SessionLocal()
    try:
        row = (
            verify_session.query(AuditEvent)
            .filter(AuditEvent.entity_id == "durability-check")
            .first()
        )
        assert row is not None
        assert row.outcome == AuditOutcome.DENIED
    finally:
        verify_session.close()


def test_app_db_role_cannot_update_or_delete_audit_rows():
    with engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO audit_event (id, action, entity_type, outcome, occurred_at, metadata_json) "
                "VALUES (gen_random_uuid(), 'perm_check', 'Test', 'SUCCESS', now(), '{}'::jsonb)"
            )
        )
        conn.commit()

        with pytest.raises(ProgrammingError, match="permission denied"):
            conn.execute(text("UPDATE audit_event SET action = 'tampered'"))
        conn.rollback()

        with pytest.raises(ProgrammingError, match="permission denied"):
            conn.execute(text("DELETE FROM audit_event"))
        conn.rollback()
