"""F002 (authorized existing-person search/select) and F003 (contact
verification, intake precision) coverage."""

from tests.conftest import CSRF_HEADERS
from tests.factories import make_facility, make_membership, make_org, make_staff


def _login(client, username, password="synthetic-password-123"):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password}, headers=CSRF_HEADERS)
    assert resp.status_code == 200


def test_search_finds_only_records_at_callers_own_facility(client, db_session):
    org = make_org(db_session)
    facility_a = make_facility(db_session, org, "Facility A")
    facility_b = make_facility(db_session, org, "Facility B")
    staff_a = make_staff(db_session, "search_staff_a")
    make_membership(db_session, staff_a, facility_a)
    staff_b = make_staff(db_session, "search_staff_b")
    make_membership(db_session, staff_b, facility_b)

    _login(client, "search_staff_a")
    client.post(
        "/api/v1/people",
        json={"full_name": "Findable Mother", "facility_id": str(facility_a.id), "phone": "+916666600001"},
        headers=CSRF_HEADERS,
    )
    client.post("/api/v1/auth/logout", headers=CSRF_HEADERS)

    # staff_a finds it.
    _login(client, "search_staff_a")
    resp = client.get("/api/v1/people", params={"phone": "+916666600001"})
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["full_name"] == "Findable Mother"
    client.post("/api/v1/auth/logout", headers=CSRF_HEADERS)

    # staff_b, a different facility, finds nothing for the same phone number
    # — the record is simply excluded, not surfaced-then-denied.
    _login(client, "search_staff_b")
    resp = client.get("/api/v1/people", params={"phone": "+916666600001"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_search_on_shared_phone_returns_distinct_people_not_merged(client, db_session):
    org = make_org(db_session)
    facility = make_facility(db_session, org)
    staff = make_staff(db_session, "search_shared_staff")
    make_membership(db_session, staff, facility)
    _login(client, "search_shared_staff")

    shared_phone = "+916666600002"
    client.post(
        "/api/v1/people",
        json={"full_name": "Household A", "facility_id": str(facility.id), "phone": shared_phone},
        headers=CSRF_HEADERS,
    )
    client.post(
        "/api/v1/people",
        json={"full_name": "Household B", "facility_id": str(facility.id), "phone": shared_phone},
        headers=CSRF_HEADERS,
    )

    resp = client.get("/api/v1/people", params={"phone": shared_phone})
    assert resp.status_code == 200
    names = sorted(p["full_name"] for p in resp.json())
    assert names == ["Household A", "Household B"]
    ids = {p["id"] for p in resp.json()}
    assert len(ids) == 2  # distinct people, never merged into one result


def test_search_result_cannot_be_linked_into_episode_without_access(client, db_session):
    org = make_org(db_session)
    facility_a = make_facility(db_session, org, "Facility A")
    facility_b = make_facility(db_session, org, "Facility B")
    staff_a = make_staff(db_session, "link_staff_a")
    make_membership(db_session, staff_a, facility_a)
    staff_b = make_staff(db_session, "link_staff_b")
    make_membership(db_session, staff_b, facility_b)

    _login(client, "link_staff_a")
    person = client.post(
        "/api/v1/people",
        json={"full_name": "Facility A Mother", "facility_id": str(facility_a.id), "phone": "+916666600003"},
        headers=CSRF_HEADERS,
    ).json()
    client.post("/api/v1/auth/logout", headers=CSRF_HEADERS)

    # staff_b never sees this person via search (facility-scoped)...
    _login(client, "link_staff_b")
    resp = client.get("/api/v1/people", params={"phone": "+916666600003"})
    assert resp.json() == []
    # ...and even with the id in hand (e.g. guessed), cannot link it into a
    # new episode.
    resp = client.post("/api/v1/pregnancy-episodes", json={"person_id": person["id"]}, headers=CSRF_HEADERS)
    assert resp.status_code == 404


def test_contact_verification_records_attribution(client, db_session):
    org = make_org(db_session)
    facility = make_facility(db_session, org)
    staff = make_staff(db_session, "verify_staff")
    make_membership(db_session, staff, facility)
    _login(client, "verify_staff")

    person = client.post(
        "/api/v1/people",
        json={"full_name": "Verify Mother", "facility_id": str(facility.id), "phone": "+916666600004"},
        headers=CSRF_HEADERS,
    ).json()
    assert person["contact_verified_at"] is None

    resp = client.post(f"/api/v1/people/{person['id']}/contact/verify", headers=CSRF_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["contact_verified_at"] is not None


def test_contact_verification_is_facility_scoped(client, db_session):
    org = make_org(db_session)
    facility_a = make_facility(db_session, org, "Facility A")
    facility_b = make_facility(db_session, org, "Facility B")
    staff_a = make_staff(db_session, "verify_staff_a")
    make_membership(db_session, staff_a, facility_a)
    staff_b = make_staff(db_session, "verify_staff_b")
    make_membership(db_session, staff_b, facility_b)

    _login(client, "verify_staff_a")
    person = client.post(
        "/api/v1/people",
        json={"full_name": "Cross Facility Mother", "facility_id": str(facility_a.id), "phone": "+916666600005"},
        headers=CSRF_HEADERS,
    ).json()
    client.post("/api/v1/auth/logout", headers=CSRF_HEADERS)

    _login(client, "verify_staff_b")
    resp = client.post(f"/api/v1/people/{person['id']}/contact/verify", headers=CSRF_HEADERS)
    assert resp.status_code == 404


def test_age_precision_rejects_mismatched_fields(client, db_session):
    org = make_org(db_session)
    facility = make_facility(db_session, org)
    staff = make_staff(db_session, "intake_staff")
    make_membership(db_session, staff, facility)
    _login(client, "intake_staff")

    # Claiming EXACT_DOB but supplying a birth_year instead is rejected —
    # never silently accepted or coerced.
    resp = client.post(
        "/api/v1/people",
        json={
            "full_name": "Bad Intake",
            "facility_id": str(facility.id),
            "phone": "+916666600006",
            "age_precision": "EXACT_DOB",
            "birth_year": 1990,
        },
        headers=CSRF_HEADERS,
    )
    assert resp.status_code == 422


def test_unknown_age_precision_stores_no_invented_values(client, db_session):
    org = make_org(db_session)
    facility = make_facility(db_session, org)
    staff = make_staff(db_session, "unknown_age_staff")
    make_membership(db_session, staff, facility)
    _login(client, "unknown_age_staff")

    resp = client.post(
        "/api/v1/people",
        json={"full_name": "Unknown Age Mother", "facility_id": str(facility.id), "phone": "+916666600007"},
        headers=CSRF_HEADERS,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["age_precision"] == "UNKNOWN"
    assert body["date_of_birth"] is None
    assert body["birth_year"] is None
    assert body["reported_age_years"] is None


def test_pregnancy_episode_dating_estimate_stays_null_when_not_supplied(client, db_session):
    """T003/CLAUDE.md: never substitute today's date or any invented value
    for an unknown dating estimate."""
    org = make_org(db_session)
    facility = make_facility(db_session, org)
    staff = make_staff(db_session, "dating_staff")
    make_membership(db_session, staff, facility)
    _login(client, "dating_staff")

    person = client.post(
        "/api/v1/people",
        json={"full_name": "Unknown Dating Mother", "facility_id": str(facility.id), "phone": "+916666600008"},
        headers=CSRF_HEADERS,
    ).json()
    episode = client.post(
        "/api/v1/pregnancy-episodes", json={"person_id": person["id"]}, headers=CSRF_HEADERS
    ).json()
    assert episode["dating_estimate"] is None
    assert episode["dating_source"] == "UNKNOWN"


def test_search_by_partial_name_scoped_to_facility(client, db_session):
    org = make_org(db_session)
    facility_a = make_facility(db_session, org, "Facility A")
    facility_b = make_facility(db_session, org, "Facility B")
    staff_a = make_staff(db_session, "name_search_a")
    make_membership(db_session, staff_a, facility_a)
    staff_b = make_staff(db_session, "name_search_b")
    make_membership(db_session, staff_b, facility_b)

    _login(client, "name_search_a")
    client.post(
        "/api/v1/people",
        json={"full_name": "Priya Sharma", "facility_id": str(facility_a.id), "phone": "+916666600009"},
        headers=CSRF_HEADERS,
    )

    resp = client.get("/api/v1/people", params={"full_name": "priya"})  # case-insensitive, partial
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["full_name"] == "Priya Sharma"
    client.post("/api/v1/auth/logout", headers=CSRF_HEADERS)

    # A different facility's staff searching the same name finds nothing.
    _login(client, "name_search_b")
    resp = client.get("/api/v1/people", params={"full_name": "priya"})
    assert resp.json() == []


def test_search_requires_at_least_one_field(client, db_session):
    org = make_org(db_session)
    facility = make_facility(db_session, org)
    staff = make_staff(db_session, "empty_search_staff")
    make_membership(db_session, staff, facility)
    _login(client, "empty_search_staff")

    resp = client.get("/api/v1/people")
    assert resp.status_code == 422


def test_verifier_name_is_exposed_after_verification(client, db_session):
    org = make_org(db_session)
    facility = make_facility(db_session, org)
    staff = make_staff(db_session, "verifier_name_staff", full_name="Nurse Kavita")
    make_membership(db_session, staff, facility)
    _login(client, "verifier_name_staff")

    person = client.post(
        "/api/v1/people",
        json={"full_name": "Verifier Name Mother", "facility_id": str(facility.id), "phone": "+916666600010"},
        headers=CSRF_HEADERS,
    ).json()
    assert person["contact_verified_by_name"] is None

    resp = client.post(f"/api/v1/people/{person['id']}/contact/verify", headers=CSRF_HEADERS)
    assert resp.json()["contact_verified_by_name"] == "Nurse Kavita"

    # And it's visible via search too, not just the direct read.
    search_resp = client.get("/api/v1/people", params={"phone": "+916666600010"})
    assert search_resp.json()[0]["contact_verified_by_name"] == "Nurse Kavita"
