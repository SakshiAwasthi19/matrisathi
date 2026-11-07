import uuid

from tests.conftest import CSRF_HEADERS
from tests.factories import make_facility, make_membership, make_org, make_staff


def _login(client, username, password="synthetic-password-123"):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password}, headers=CSRF_HEADERS)
    assert resp.status_code == 200


def test_episode_creation_rejected_for_inaccessible_person(client, db_session):
    org = make_org(db_session)
    facility_a = make_facility(db_session, org, "Facility A")
    facility_b = make_facility(db_session, org, "Facility B")

    staff_a = make_staff(db_session, "staff_a2")
    make_membership(db_session, staff_a, facility_a)
    staff_b = make_staff(db_session, "staff_b2")
    make_membership(db_session, staff_b, facility_b)

    _login(client, "staff_a2")
    person = client.post(
        "/api/v1/people",
        json={"full_name": "Mother X", "facility_id": str(facility_a.id), "phone": "+912222222221"},
        headers=CSRF_HEADERS,
    ).json()
    client.post("/api/v1/auth/logout", headers=CSRF_HEADERS)

    _login(client, "staff_b2")
    # staff_b has no access to a Facility-A person — creating an episode
    # against that person's id must be rejected, not silently allowed
    # because the id itself was valid.
    resp = client.post("/api/v1/pregnancy-episodes", json={"person_id": person["id"]}, headers=CSRF_HEADERS)
    assert resp.status_code == 404


def test_episode_creation_rejected_for_nonexistent_person(client, db_session):
    org = make_org(db_session)
    facility = make_facility(db_session, org)
    staff = make_staff(db_session, "staff_e")
    make_membership(db_session, staff, facility)

    _login(client, "staff_e")
    resp = client.post(
        "/api/v1/pregnancy-episodes", json={"person_id": str(uuid.uuid4())}, headers=CSRF_HEADERS
    )
    assert resp.status_code == 404


def test_episode_facility_is_derived_server_side_not_from_request_body(client, db_session):
    org = make_org(db_session)
    facility_a = make_facility(db_session, org, "Facility A")
    facility_b = make_facility(db_session, org, "Facility B")
    staff_a = make_staff(db_session, "staff_a3")
    make_membership(db_session, staff_a, facility_a)

    _login(client, "staff_a3")
    person = client.post(
        "/api/v1/people",
        json={"full_name": "Mother Y", "facility_id": str(facility_a.id), "phone": "+912222222222"},
        headers=CSRF_HEADERS,
    ).json()

    # Even if a client tried to smuggle a different facility_id into the
    # episode-create body, the schema doesn't accept one — the episode's
    # facility is always the person's registering facility.
    resp = client.post(
        "/api/v1/pregnancy-episodes",
        json={"person_id": person["id"], "facility_id": str(facility_b.id)},
        headers=CSRF_HEADERS,
    )
    assert resp.status_code == 201
    assert resp.json()["facility_id"] == str(facility_a.id)


def test_person_creation_rejected_for_facility_caller_is_not_a_member_of(client, db_session):
    org = make_org(db_session)
    facility_a = make_facility(db_session, org, "Facility A")
    facility_b = make_facility(db_session, org, "Facility B")
    staff_a = make_staff(db_session, "staff_a4")
    make_membership(db_session, staff_a, facility_a)

    _login(client, "staff_a4")
    # staff_a is not a member of facility_b — cannot register a person there
    # merely by naming that facility_id in the request.
    resp = client.post(
        "/api/v1/people",
        json={"full_name": "Mother Z", "facility_id": str(facility_b.id), "phone": "+912222222223"},
        headers=CSRF_HEADERS,
    )
    assert resp.status_code == 404


def test_retried_person_creation_with_same_idempotency_key_does_not_duplicate(client, db_session):
    org = make_org(db_session)
    facility = make_facility(db_session, org)
    staff = make_staff(db_session, "staff_idem")
    make_membership(db_session, staff, facility)

    _login(client, "staff_idem")
    headers = {**CSRF_HEADERS, "Idempotency-Key": "retry-key-1"}
    body = {"full_name": "Mother Idem", "facility_id": str(facility.id), "phone": "+912222222224"}

    first = client.post("/api/v1/people", json=body, headers=headers)
    assert first.status_code == 201
    # A retried submission (same key) returns the SAME record, not a new one.
    second = client.post("/api/v1/people", json=body, headers=headers)
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]


def test_retried_pregnancy_episode_creation_with_same_idempotency_key_does_not_duplicate(client, db_session):
    org = make_org(db_session)
    facility = make_facility(db_session, org)
    staff = make_staff(db_session, "staff_idem2")
    make_membership(db_session, staff, facility)

    _login(client, "staff_idem2")
    person = client.post(
        "/api/v1/people",
        json={"full_name": "Mother Idem 2", "facility_id": str(facility.id), "phone": "+912222222225"},
        headers=CSRF_HEADERS,
    ).json()

    headers = {**CSRF_HEADERS, "Idempotency-Key": "retry-key-2"}
    first = client.post("/api/v1/pregnancy-episodes", json={"person_id": person["id"]}, headers=headers)
    assert first.status_code == 201
    second = client.post("/api/v1/pregnancy-episodes", json={"person_id": person["id"]}, headers=headers)
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]
