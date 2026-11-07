from tests.conftest import CSRF_HEADERS
from tests.factories import make_facility, make_membership, make_org, make_staff

SHARED_PHONE = "+919999999999"


def _login(client, username, password="synthetic-password-123"):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password}, headers=CSRF_HEADERS)
    assert resp.status_code == 200


def test_two_people_can_share_a_phone_without_being_merged(client, db_session):
    org = make_org(db_session)
    facility = make_facility(db_session, org)
    staff = make_staff(db_session, "staff_shared")
    make_membership(db_session, staff, facility)

    _login(client, "staff_shared")
    person_1 = client.post(
        "/api/v1/people",
        json={"full_name": "Household Member One", "facility_id": str(facility.id), "phone": SHARED_PHONE},
        headers=CSRF_HEADERS,
    )
    assert person_1.status_code == 201
    person_2 = client.post(
        "/api/v1/people",
        json={"full_name": "Household Member Two", "facility_id": str(facility.id), "phone": SHARED_PHONE},
        headers=CSRF_HEADERS,
    )
    assert person_2.status_code == 201

    p1, p2 = person_1.json(), person_2.json()
    assert p1["id"] != p2["id"]

    episode_1 = client.post("/api/v1/pregnancy-episodes", json={"person_id": p1["id"]}, headers=CSRF_HEADERS)
    episode_2 = client.post("/api/v1/pregnancy-episodes", json={"person_id": p2["id"]}, headers=CSRF_HEADERS)
    assert episode_1.status_code == 201
    assert episode_2.status_code == 201
    assert episode_1.json()["id"] != episode_2.json()["id"]

    # Each is independently readable, and reading one never surfaces the
    # other sharing its phone number.
    read_1 = client.get(f"/api/v1/people/{p1['id']}").json()
    read_2 = client.get(f"/api/v1/people/{p2['id']}").json()
    assert read_1["full_name"] == "Household Member One"
    assert read_2["full_name"] == "Household Member Two"
    assert read_1["id"] != read_2["id"]


def test_shared_phone_does_not_leak_across_organizations(client, db_session):
    org_1 = make_org(db_session, "Org 1")
    org_2 = make_org(db_session, "Org 2")
    facility_1 = make_facility(db_session, org_1, "Org 1 Facility")
    facility_2 = make_facility(db_session, org_2, "Org 2 Facility")
    staff_1 = make_staff(db_session, "phone_staff_1")
    make_membership(db_session, staff_1, facility_1)
    staff_2 = make_staff(db_session, "phone_staff_2")
    make_membership(db_session, staff_2, facility_2)

    _login(client, "phone_staff_1")
    person_1 = client.post(
        "/api/v1/people",
        json={"full_name": "Org 1 Mother", "facility_id": str(facility_1.id), "phone": SHARED_PHONE},
        headers=CSRF_HEADERS,
    ).json()
    client.post("/api/v1/auth/logout", headers=CSRF_HEADERS)

    _login(client, "phone_staff_2")
    person_2 = client.post(
        "/api/v1/people",
        json={"full_name": "Org 2 Mother", "facility_id": str(facility_2.id), "phone": SHARED_PHONE},
        headers=CSRF_HEADERS,
    ).json()

    # staff_2 (currently logged in) cannot read org 1's person, even though
    # it shares the exact phone number they just used themselves.
    resp = client.get(f"/api/v1/people/{person_1['id']}")
    assert resp.status_code == 404
    # Their own read never mentions or exposes the other org's record.
    own = client.get(f"/api/v1/people/{person_2['id']}").json()
    assert "org 1" not in str(own).lower()
