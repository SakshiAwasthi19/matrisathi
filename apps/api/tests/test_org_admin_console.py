"""F004 admin console API and F037 organisation audit view."""

import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.models.staff import StaffMembership, StaffRole, StaffUser
from tests.conftest import CSRF_HEADERS
from tests.factories import make_facility, make_membership, make_org, make_org_admin, make_staff, make_world

PASSWORD = "synthetic-password-123"


def _client(username: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD}, headers=CSRF_HEADERS)
    assert r.status_code == 200, r.text
    return c


def _setup(db):
    w = make_world(db, f"adm{uuid.uuid4().hex[:4]}")
    admin = make_staff(db, f"orgadmin_{uuid.uuid4().hex[:5]}", full_name="Synthetic Admin")
    make_org_admin(db, admin, w.org)
    return w, admin, _client(admin.username)


# --- staff and facilities --------------------------------------------------------------


def test_lists_need_an_org_admin_grant(db_session):
    w, _, admin = _setup(db_session)
    coord = _client(w.coordinator.username)
    for path in ("facilities", "staff", "audit"):
        assert coord.get(f"/api/v1/organizations/{w.org.id}/{path}").status_code == 404
        assert admin.get(f"/api/v1/organizations/{w.org.id}/{path}").status_code == 200
    assert admin.get("/api/v1/organizations/not-a-uuid/staff").status_code == 404


def test_staff_list_shows_only_this_organisations_memberships(db_session):
    w, _, admin = _setup(db_session)
    other_org = make_org(db_session, "Other Org")
    other_fac = make_facility(db_session, other_org, "Other Facility")
    make_membership(db_session, w.nurse, other_fac, StaffRole.ASHA)

    staff = admin.get(f"/api/v1/organizations/{w.org.id}/staff").json()
    names = {s["full_name"] for s in staff}
    assert {"Synthetic Coordinator", "Synthetic Doctor", "Synthetic Nurse"} <= names
    nurse = next(s for s in staff if s["id"] == str(w.nurse.id))
    assert [m["facility_name"] for m in nurse["memberships"]] == [w.facility.name]


def test_create_staff_with_first_membership_in_one_step(db_session):
    w, _, admin = _setup(db_session)
    r = admin.post(
        "/api/v1/staff",
        json={"organization_id": str(w.org.id), "username": "new_asha_1", "full_name": "Synthetic New ASHA",
              "password": "synthetic-password-456", "facility_id": str(w.facility.id), "role": "ASHA"},
        headers=CSRF_HEADERS,
    )
    assert r.status_code == 201, r.text
    c = TestClient(app)
    assert c.post("/api/v1/auth/login", json={"username": "new_asha_1", "password": "synthetic-password-456"}, headers=CSRF_HEADERS).status_code == 200
    assert c.get("/api/v1/auth/me").json()["memberships"][0]["role"] == "ASHA"


def test_create_staff_at_another_organisations_facility_creates_nothing(db_session):
    w, _, admin = _setup(db_session)
    other_fac = make_facility(db_session, make_org(db_session, "Other Org"), "Other Facility")
    r = admin.post(
        "/api/v1/staff",
        json={"organization_id": str(w.org.id), "username": "sneaky_1", "full_name": "Synthetic Sneaky",
              "password": "synthetic-password-456", "facility_id": str(other_fac.id), "role": "NURSE"},
        headers=CSRF_HEADERS,
    )
    assert r.status_code == 404
    assert db_session.query(StaffUser).filter(StaffUser.username == "sneaky_1").count() == 0


def test_short_password_is_refused(db_session):
    w, _, admin = _setup(db_session)
    r = admin.post(
        "/api/v1/staff",
        json={"organization_id": str(w.org.id), "username": "shortpw", "full_name": "Synthetic", "password": "short"},
        headers=CSRF_HEADERS,
    )
    assert r.status_code == 422


def test_duplicate_active_membership_is_refused(db_session):
    w, _, admin = _setup(db_session)
    r = admin.post(
        f"/api/v1/facilities/{w.facility.id}/memberships",
        json={"staff_user_id": str(w.nurse.id), "role": "NURSE"},
        headers=CSRF_HEADERS,
    )
    assert r.status_code == 409


def test_role_change_keeps_history_and_access(db_session):
    w, _, admin = _setup(db_session)
    old = db_session.query(StaffMembership).filter(StaffMembership.staff_user_id == w.nurse.id).one()
    r = admin.post(
        f"/api/v1/facilities/{w.facility.id}/memberships/{old.id}/role", json={"role": "ANM"}, headers=CSRF_HEADERS
    )
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "ANM" and r.json()["id"] != str(old.id)

    db_session.expire_all()
    rows = db_session.query(StaffMembership).filter(StaffMembership.staff_user_id == w.nurse.id).all()
    assert sorted((m.role.value, m.revoked_at is None) for m in rows) == [("ANM", True), ("NURSE", False)]
    # Still works at the facility, now as ANM.
    assert _client(w.nurse.username).get("/api/v1/auth/me").json()["memberships"][0]["role"] == "ANM"

    history = admin.get(f"/api/v1/organizations/{w.org.id}/staff", params={"include_revoked": True}).json()
    nurse = next(s for s in history if s["id"] == str(w.nurse.id))
    assert len(nurse["memberships"]) == 2

    # Same role again, or an ended membership, is refused.
    new_id = r.json()["id"]
    assert admin.post(f"/api/v1/facilities/{w.facility.id}/memberships/{new_id}/role", json={"role": "ANM"}, headers=CSRF_HEADERS).status_code == 409
    assert admin.post(f"/api/v1/facilities/{w.facility.id}/memberships/{old.id}/role", json={"role": "ASHA"}, headers=CSRF_HEADERS).status_code == 409


# --- audit view ------------------------------------------------------------------------


def test_audit_view_scoped_to_organisation_without_clinical_content(db_session):
    w, _, admin = _setup(db_session)
    other = make_world(db_session, f"oth{uuid.uuid4().hex[:4]}")

    coord = _client(w.coordinator.username)
    r = coord.post(
        "/api/v1/people",
        json={"full_name": "Synthetic Zebracorn", "facility_id": str(w.facility.id), "phone": "+919000000201"},
        headers=CSRF_HEADERS,
    )
    assert r.status_code == 201
    # A denied action in this org, and activity in another org.
    coord.post("/api/v1/people", json={"full_name": "x", "facility_id": str(other.facility.id), "phone": "1"}, headers=CSRF_HEADERS)
    _client(other.coordinator.username).get("/api/v1/auth/me")

    page = admin.get(f"/api/v1/organizations/{w.org.id}/audit", params={"limit": 100})
    assert page.status_code == 200
    events = page.json()["events"]
    actors = {e["actor_id"] for e in events}
    assert str(w.coordinator.id) in actors
    assert str(other.coordinator.id) not in actors
    assert any(e["action"] == "create" and e["entity_type"] == "Person" and e["outcome"] == "SUCCESS" for e in events)
    assert any(e["outcome"] == "DENIED" for e in events)
    # Names of mothers and phone numbers never appear.
    assert "Zebracorn" not in page.text and "+919000000201" not in page.text
    for e in events:
        assert set(e["details"]) <= {"reason"}


def test_audit_view_filters_pages_and_is_itself_audited(db_session):
    w, admin_user, admin = _setup(db_session)
    coord = _client(w.coordinator.username)
    for i in range(3):
        coord.get("/api/v1/auth/me")
        coord.post("/api/v1/people", json={"full_name": f"Synthetic P{i}", "facility_id": str(w.facility.id), "phone": f"+91900000030{i}"}, headers=CSRF_HEADERS)

    first = admin.get(f"/api/v1/organizations/{w.org.id}/audit", params={"limit": 2, "action": "create"}).json()
    assert len(first["events"]) == 2 and first["has_more"] is True
    assert all(e["action"] == "create" for e in first["events"])
    nxt = admin.get(
        f"/api/v1/organizations/{w.org.id}/audit",
        params={"limit": 2, "action": "create", "before": first["events"][-1]["occurred_at"]},
    ).json()
    assert nxt["events"] and nxt["events"][0]["occurred_at"] < first["events"][-1]["occurred_at"]

    viewed = admin.get(f"/api/v1/organizations/{w.org.id}/audit", params={"action": "view_audit"}).json()["events"]
    assert viewed and viewed[0]["actor_id"] == str(admin_user.id)
