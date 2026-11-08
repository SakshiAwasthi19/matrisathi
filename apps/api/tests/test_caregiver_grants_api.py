"""F015 under D07 option 3: staff record, show and revoke family access grants."""

import uuid
from datetime import timedelta

from fastapi.testclient import TestClient

from app.api.routers.care import _today
from app.domain.permissions import EVERYDAY, ROLE_CAPABILITIES, Capability
from app.main import app
from app.models.caregiver import CaregiverScope
from app.models.identity import Person
from app.services.caregiver_access import caregiver_access_allowed, caregiver_may_receive
from tests.conftest import CSRF_HEADERS
from tests.factories import make_mother, make_world

PASSWORD = "synthetic-password-123"


def _client(username: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD}, headers=CSRF_HEADERS)
    assert r.status_code == 200, r.text
    return c


def _setup(db):
    w = make_world(db, f"cg{uuid.uuid4().hex[:4]}")
    mother, _ = make_mother(db, w, "Synthetic Grant Mother", "+919000000401")
    # Same phone on purpose: a shared handset never links anyone.
    caregiver, _ = make_mother(db, w, "Synthetic Grant Sister", "+919000000401")
    return w, mother, caregiver, _client(w.coordinator.username)


def _body(caregiver: Person, **over):
    return {
        "grantee_person_id": str(caregiver.id),
        "scopes": ["NEXT_ACTION", "BIRTH_PLAN"],
        "verification_method": "IN_PERSON_DOCUMENT",
        "consent_confirmed": True,
        **over,
    }


def test_grant_list_and_revoke_take_effect_on_the_next_check(db_session):
    w, mother, caregiver, c = _setup(db_session)
    r = c.post(f"/api/v1/people/{mother.id}/caregiver-grants", json=_body(caregiver), headers=CSRF_HEADERS)
    assert r.status_code == 201, r.text
    g = r.json()
    assert g["state"] == "ACTIVE" and g["grantee_full_name"] == "Synthetic Grant Sister"
    assert g["verified_by_name"] == "Synthetic Coordinator"
    assert g["expires_on"] == (_today() + timedelta(days=90)).isoformat()

    def may(scope):
        db_session.expire_all()
        return caregiver_may_receive(db_session, subject_person_id=mother.id, grantee_person_id=caregiver.id, scope=scope)

    assert may(CaregiverScope.NEXT_ACTION) and may(CaregiverScope.BIRTH_PLAN)
    assert not may(CaregiverScope.REMINDERS)  # not granted
    # Not symmetric: the sister gave the mother nothing.
    assert not caregiver_may_receive(db_session, subject_person_id=caregiver.id, grantee_person_id=mother.id, scope=CaregiverScope.NEXT_ACTION)
    # Option 3: no patient sign-in, so the patient-facing check stays off.
    assert not caregiver_access_allowed(db_session, subject_person_id=mother.id, grantee_person_id=caregiver.id, scope=CaregiverScope.NEXT_ACTION)

    r = c.post(f"/api/v1/caregiver-grants/{g['id']}/revoke", json={"expected_version": g["version"], "reason": "REQUESTED_BY_SUBJECT"}, headers=CSRF_HEADERS)
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "REVOKED" and r.json()["revoked_by_name"] == "Synthetic Coordinator"
    assert not may(CaregiverScope.NEXT_ACTION)

    listed = c.get(f"/api/v1/people/{mother.id}/caregiver-grants").json()
    assert [x["state"] for x in listed] == ["REVOKED"]  # history kept, nothing deleted
    # Revoking twice, or with a stale version, is refused.
    assert c.post(f"/api/v1/caregiver-grants/{g['id']}/revoke", json={"expected_version": r.json()["version"], "reason": "REPLACED"}, headers=CSRF_HEADERS).status_code == 409


def test_invalid_grants_are_refused(db_session):
    w, mother, caregiver, c = _setup(db_session)
    url = f"/api/v1/people/{mother.id}/caregiver-grants"
    assert c.post(url, json=_body(caregiver, consent_confirmed=False), headers=CSRF_HEADERS).status_code == 422
    assert c.post(url, json=_body(mother), headers=CSRF_HEADERS).status_code == 422  # herself
    assert c.post(url, json=_body(caregiver, scopes=[]), headers=CSRF_HEADERS).status_code == 422
    assert c.post(url, json=_body(caregiver, expires_on=(_today() - timedelta(days=1)).isoformat()), headers=CSRF_HEADERS).status_code == 422
    assert c.post(url, json=_body(caregiver, expires_on=(_today() + timedelta(days=400)).isoformat()), headers=CSRF_HEADERS).status_code == 422
    assert c.post(url, json=_body(caregiver, grantee_person_id="not-a-uuid"), headers=CSRF_HEADERS).status_code == 404
    assert c.post(url, json=_body(caregiver), headers=CSRF_HEADERS).status_code == 201
    assert c.post(url, json=_body(caregiver), headers=CSRF_HEADERS).status_code == 409  # one active grant per pair


def test_other_facility_cannot_see_or_link(db_session):
    w, mother, caregiver, _ = _setup(db_session)
    other = make_world(db_session, f"cgo{uuid.uuid4().hex[:4]}")
    outsider, _ = make_mother(db_session, other, "Synthetic Outsider", "+919000000402")
    oc = _client(other.coordinator.username)
    assert oc.get(f"/api/v1/people/{mother.id}/caregiver-grants").status_code == 404
    assert oc.post(f"/api/v1/people/{mother.id}/caregiver-grants", json=_body(caregiver), headers=CSRF_HEADERS).status_code == 404
    # Linking a person the caller cannot see (reference injection) is refused.
    c = _client(w.coordinator.username)
    assert c.post(f"/api/v1/people/{mother.id}/caregiver-grants", json=_body(outsider), headers=CSRF_HEADERS).status_code == 404


def test_role_without_the_capability_is_refused(db_session, monkeypatch):
    w, mother, caregiver, c = _setup(db_session)
    monkeypatch.setitem(ROLE_CAPABILITIES, "COORDINATOR", EVERYDAY - {Capability.MANAGE_CAREGIVER_GRANTS})
    r = c.post(f"/api/v1/people/{mother.id}/caregiver-grants", json=_body(caregiver), headers=CSRF_HEADERS)
    assert r.status_code == 403
    # Viewing is still allowed: it is part of the mother's record.
    assert c.get(f"/api/v1/people/{mother.id}/caregiver-grants").status_code == 200
