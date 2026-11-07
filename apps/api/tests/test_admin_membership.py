"""F004: an org admin manages facilities, staff accounts and memberships
through the application itself, not only via direct DB fixtures — and that
authority is never inferred from a facility-level role.
"""

from tests.conftest import CSRF_HEADERS
from tests.factories import make_facility, make_org, make_org_admin, make_staff, make_membership


def _login(client, username, password="synthetic-password-123"):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password}, headers=CSRF_HEADERS)
    assert resp.status_code == 200


def test_org_admin_can_create_facility_and_grant_membership(client, db_session):
    org = make_org(db_session)
    admin = make_staff(db_session, "org_admin_1")
    make_org_admin(db_session, admin, org)
    target = make_staff(db_session, "new_coordinator")

    _login(client, "org_admin_1")

    facility_resp = client.post(
        f"/api/v1/organizations/{org.id}/facilities", json={"name": "New Facility"}, headers=CSRF_HEADERS
    )
    assert facility_resp.status_code == 201
    facility_id = facility_resp.json()["id"]

    grant_resp = client.post(
        f"/api/v1/facilities/{facility_id}/memberships",
        json={"staff_user_id": str(target.id), "role": "COORDINATOR"},
        headers=CSRF_HEADERS,
    )
    assert grant_resp.status_code == 201
    membership_id = grant_resp.json()["id"]

    # The newly granted membership actually works — the target staff member
    # can now register a person at the new facility.
    client.post("/api/v1/auth/logout", headers=CSRF_HEADERS)
    _login(client, "new_coordinator")
    resp = client.post(
        "/api/v1/people",
        json={"full_name": "Mother via new grant", "facility_id": facility_id, "phone": "+914444444441"},
        headers=CSRF_HEADERS,
    )
    assert resp.status_code == 201
    assert membership_id  # sanity: grant response carried a real id


def test_revoking_a_membership_through_the_admin_api_removes_access(client, db_session):
    org = make_org(db_session)
    admin = make_staff(db_session, "org_admin_2")
    make_org_admin(db_session, admin, org)
    facility = make_facility(db_session, org)
    target = make_staff(db_session, "coordinator_to_revoke")
    membership = make_membership(db_session, target, facility)

    _login(client, "org_admin_2")
    resp = client.delete(
        f"/api/v1/facilities/{facility.id}/memberships/{membership.id}", headers=CSRF_HEADERS
    )
    assert resp.status_code == 204
    client.post("/api/v1/auth/logout", headers=CSRF_HEADERS)

    _login(client, "coordinator_to_revoke")
    resp = client.post(
        "/api/v1/people",
        json={"full_name": "Should be denied", "facility_id": str(facility.id), "phone": "+914444444442"},
        headers=CSRF_HEADERS,
    )
    assert resp.status_code == 404


def test_non_org_admin_cannot_create_facility_or_grant_membership(client, db_session):
    org = make_org(db_session)
    facility = make_facility(db_session, org)
    plain_staff = make_staff(db_session, "plain_coordinator")
    make_membership(db_session, plain_staff, facility)  # ordinary facility role, NOT org admin
    target = make_staff(db_session, "some_target")

    _login(client, "plain_coordinator")
    resp = client.post(
        f"/api/v1/organizations/{org.id}/facilities", json={"name": "Should not be created"}, headers=CSRF_HEADERS
    )
    assert resp.status_code == 404

    resp = client.post(
        f"/api/v1/facilities/{facility.id}/memberships",
        json={"staff_user_id": str(target.id), "role": "COORDINATOR"},
        headers=CSRF_HEADERS,
    )
    assert resp.status_code == 404


def test_org_admin_of_org_a_cannot_grant_membership_at_org_b_facility(client, db_session):
    org_a = make_org(db_session, "Org A")
    org_b = make_org(db_session, "Org B")
    facility_b = make_facility(db_session, org_b, "Org B Facility")
    admin_a = make_staff(db_session, "org_admin_a2")
    make_org_admin(db_session, admin_a, org_a)
    target = make_staff(db_session, "target_for_b")

    _login(client, "org_admin_a2")
    resp = client.post(
        f"/api/v1/facilities/{facility_b.id}/memberships",
        json={"staff_user_id": str(target.id), "role": "COORDINATOR"},
        headers=CSRF_HEADERS,
    )
    assert resp.status_code == 404
