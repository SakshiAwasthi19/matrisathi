from datetime import datetime, timezone

from tests.conftest import CSRF_HEADERS
from tests.factories import make_facility, make_membership, make_org, make_staff


def _login(client, username, password="synthetic-password-123"):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password}, headers=CSRF_HEADERS)
    assert resp.status_code == 200
    return resp


def test_staff_at_facility_b_cannot_read_facility_a_episode(client, db_session):
    org = make_org(db_session)
    facility_a = make_facility(db_session, org, "Facility A")
    facility_b = make_facility(db_session, org, "Facility B")

    staff_a = make_staff(db_session, "staff_a")
    make_membership(db_session, staff_a, facility_a)
    staff_b = make_staff(db_session, "staff_b")
    make_membership(db_session, staff_b, facility_b)

    _login(client, "staff_a")
    person = client.post(
        "/api/v1/people",
        json={"full_name": "Mother A", "facility_id": str(facility_a.id), "phone": "+911111111111"},
        headers=CSRF_HEADERS,
    ).json()
    episode = client.post(
        "/api/v1/pregnancy-episodes", json={"person_id": person["id"]}, headers=CSRF_HEADERS
    ).json()
    client.post("/api/v1/auth/logout", headers=CSRF_HEADERS)

    _login(client, "staff_b")
    # 404, never 403: a 403 would confirm the record exists at another
    # facility, which leaks cross-facility existence information.
    resp = client.get(f"/api/v1/pregnancy-episodes/{episode['id']}")
    assert resp.status_code == 404

    resp = client.get(f"/api/v1/people/{person['id']}")
    assert resp.status_code == 404


def test_revoked_membership_loses_access_immediately(client, db_session):
    org = make_org(db_session)
    facility = make_facility(db_session, org)
    staff = make_staff(db_session, "staff_c")
    membership = make_membership(db_session, staff, facility)

    _login(client, "staff_c")
    person = client.post(
        "/api/v1/people",
        json={"full_name": "Mother C", "facility_id": str(facility.id), "phone": "+911111111112"},
        headers=CSRF_HEADERS,
    ).json()

    # Revoke mid-session — the still-valid access token must not matter.
    membership.active = False
    membership.revoked_at = datetime.now(timezone.utc)
    db_session.add(membership)
    db_session.commit()

    resp = client.get(f"/api/v1/people/{person['id']}")
    assert resp.status_code == 404


def test_disabled_facility_blocks_new_person_registration(client, db_session):
    org = make_org(db_session)
    facility = make_facility(db_session, org, active=False)
    staff = make_staff(db_session, "staff_d")
    make_membership(db_session, staff, facility)

    _login(client, "staff_d")
    resp = client.post(
        "/api/v1/people",
        json={"full_name": "Mother D", "facility_id": str(facility.id), "phone": "+911111111113"},
        headers=CSRF_HEADERS,
    )
    assert resp.status_code == 404


def test_two_organizations_are_isolated(client, db_session):
    org_1 = make_org(db_session, "Org 1")
    org_2 = make_org(db_session, "Org 2")
    facility_1 = make_facility(db_session, org_1, "Org 1 Facility")
    facility_2 = make_facility(db_session, org_2, "Org 2 Facility")

    staff_1 = make_staff(db_session, "org1_staff")
    make_membership(db_session, staff_1, facility_1)
    staff_2 = make_staff(db_session, "org2_staff")
    make_membership(db_session, staff_2, facility_2)

    _login(client, "org1_staff")
    person = client.post(
        "/api/v1/people",
        json={"full_name": "Org 1 Mother", "facility_id": str(facility_1.id), "phone": "+911111111114"},
        headers=CSRF_HEADERS,
    ).json()
    client.post("/api/v1/auth/logout", headers=CSRF_HEADERS)

    _login(client, "org2_staff")
    resp = client.get(f"/api/v1/people/{person['id']}")
    assert resp.status_code == 404
