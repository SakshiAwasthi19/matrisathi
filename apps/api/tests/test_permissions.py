"""F004: the single role-capability table and the checks that use it."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.domain import permissions
from app.domain.permissions import CLINICAL, EVERYDAY, ROLE_CAPABILITIES, Capability, capabilities_of, has_capability
from app.domain.transitions import CLINICIAN_ROLES, INVESTIGATION_TRANSITIONS, ClinicianOnlyError, check_transition
from app.main import app
from app.models.care import InvestigationStatus
from app.models.staff import StaffRole
from tests.conftest import CSRF_HEADERS
from tests.factories import make_membership, make_mother, make_org_admin, make_staff, make_world

PASSWORD = "synthetic-password-123"


def _client(username: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD}, headers=CSRF_HEADERS)
    assert r.status_code == 200, r.text
    return c


# --- the table itself ------------------------------------------------------------------


def test_table_reproduces_the_rules_in_force_before_it():
    """Only DOCTOR holds clinical capabilities; every role does everyday work."""
    assert ROLE_CAPABILITIES["DOCTOR"] == CLINICAL | EVERYDAY
    for role in ("NURSE", "ANM", "COORDINATOR", "ASHA"):
        assert ROLE_CAPABILITIES[role] == EVERYDAY
    assert CLINICIAN_ROLES == {"DOCTOR"}


def test_every_staff_role_is_in_the_table_and_unknown_roles_get_nothing():
    assert {r.value for r in StaffRole} == set(ROLE_CAPABILITIES)
    assert capabilities_of(["NOT_A_ROLE"]) == frozenset()
    assert not has_capability([], Capability.REGISTER_MOTHER)


def test_anm_starts_identical_to_nurse():
    assert ROLE_CAPABILITIES["ANM"] == ROLE_CAPABILITIES["NURSE"]


def test_every_capability_has_a_denial_message():
    assert set(permissions.DENIED_MESSAGE) == set(Capability)


def test_transitions_follow_the_table_not_role_names(monkeypatch):
    """Changing the table changes who may mark a report reviewed, with no code change."""
    received, reviewed = InvestigationStatus.RECEIVED, InvestigationStatus.REVIEWED
    check_transition(INVESTIGATION_TRANSITIONS, received, reviewed, ["DOCTOR"])
    with pytest.raises(ClinicianOnlyError):
        check_transition(INVESTIGATION_TRANSITIONS, received, reviewed, ["NURSE"])

    monkeypatch.setitem(ROLE_CAPABILITIES, "NURSE", EVERYDAY | {Capability.REVIEW_REPORT})
    check_transition(INVESTIGATION_TRANSITIONS, received, reviewed, ["NURSE"])


# --- /auth/me --------------------------------------------------------------------------


def test_me_reports_capabilities_per_membership_and_admin_organisations(db_session):
    w = make_world(db_session, f"perm{uuid.uuid4().hex[:4]}")
    make_org_admin(db_session, w.coordinator, w.org)

    me = _client(w.coordinator.username).get("/api/v1/auth/me").json()
    assert me["memberships"][0]["capabilities"] == sorted(c.value for c in EVERYDAY)
    assert me["admin_organizations"] == [{"id": str(w.org.id), "name": w.org.name}]

    doc = _client(w.doctor.username).get("/api/v1/auth/me").json()
    assert set(doc["memberships"][0]["capabilities"]) == {c.value for c in CLINICAL | EVERYDAY}
    assert doc["admin_organizations"] == []


# --- enforcement points driven by the table --------------------------------------------


def test_register_mother_follows_the_table(db_session, monkeypatch):
    w = make_world(db_session, f"reg{uuid.uuid4().hex[:4]}")
    asha = make_staff(db_session, f"asha_{uuid.uuid4().hex[:5]}")
    make_membership(db_session, asha, w.facility, StaffRole.ASHA)
    c = _client(asha.username)
    body = {"full_name": "Synthetic Reg Mother", "facility_id": str(w.facility.id), "phone": "+919000000101"}

    # Today's rule: ASHAs may register.
    assert c.post("/api/v1/people", json=body, headers=CSRF_HEADERS).status_code == 201

    # If the doctor's answer removes it, the same request is refused and audited.
    monkeypatch.setitem(ROLE_CAPABILITIES, "ASHA", EVERYDAY - {Capability.REGISTER_MOTHER})
    r = c.post("/api/v1/people", json={**body, "full_name": "Synthetic Reg Mother 2"}, headers=CSRF_HEADERS)
    assert r.status_code == 403
    assert "cannot register" in r.json()["detail"]

    person, _ = make_mother(db_session, w, "Synthetic Episode Mother", "+919000000102")
    r = c.post("/api/v1/pregnancy-episodes", json={"person_id": str(person.id)}, headers=CSRF_HEADERS)
    assert r.status_code == 403


def test_reported_history_visibility_follows_the_table(db_session, monkeypatch):
    w = make_world(db_session, f"hist{uuid.uuid4().hex[:4]}")
    person, _ = make_mother(db_session, w, "Synthetic History Mother", "+919000000103")
    person.reported_medical_history = "Synthetic history text"
    person.known_allergies_medicines = "Synthetic allergy text"
    db_session.commit()
    c = _client(w.nurse.username)

    shown = c.get(f"/api/v1/people/{person.id}").json()
    assert shown["reported_medical_history"] == "Synthetic history text"
    assert shown["reported_history_withheld"] is False

    monkeypatch.setitem(ROLE_CAPABILITIES, "NURSE", EVERYDAY - {Capability.VIEW_REPORTED_HISTORY})
    hidden = c.get(f"/api/v1/people/{person.id}").json()
    assert hidden["reported_medical_history"] is None
    assert hidden["known_allergies_medicines"] is None
    assert hidden["reported_history_withheld"] is True
    # Search results follow the same rule.
    found = c.get("/api/v1/people", params={"full_name": "History Mother"}).json()
    assert found[0]["reported_medical_history"] is None


def test_anm_role_can_be_granted_and_works_like_nurse(db_session):
    w = make_world(db_session, f"anm{uuid.uuid4().hex[:4]}")
    admin_user = w.coordinator
    make_org_admin(db_session, admin_user, w.org)
    anm = make_staff(db_session, f"anm_{uuid.uuid4().hex[:5]}")
    r = _client(admin_user.username).post(
        f"/api/v1/facilities/{w.facility.id}/memberships",
        json={"staff_user_id": str(anm.id), "role": "ANM"},
        headers=CSRF_HEADERS,
    )
    assert r.status_code == 201, r.text
    me = _client(anm.username).get("/api/v1/auth/me").json()
    assert me["memberships"][0]["role"] == "ANM"
    assert set(me["memberships"][0]["capabilities"]) == {c.value for c in EVERYDAY}
