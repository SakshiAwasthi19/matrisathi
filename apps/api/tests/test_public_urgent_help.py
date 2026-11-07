"""F014 / W2-B3: the public Urgent help endpoint works signed out and
returns only facility contact details, never patient data or wording."""

from fastapi.testclient import TestClient

from app.main import app
from app.models.records import LocalContact, ServiceType
from tests.factories import make_facility, make_org, make_staff

FORBIDDEN_KEYS = {"person", "mother", "patient", "full_name", "episode", "phone_of", "instructions"}


def _contact(db, facility, staff, service_type, name, phone, active=True):
    from datetime import date

    c = LocalContact(
        facility_id=facility.id,
        service_type=service_type,
        name=name,
        phone=phone,
        verified_by_staff_user_id=staff.id,
        verified_on=date.today(),
        active=active,
    )
    db.add(c)
    db.commit()
    return c


def test_signed_out_user_gets_verified_service_numbers_only(db_session):
    org = make_org(db_session)
    facility = make_facility(db_session, org, "Synthetic Facility")
    staff = make_staff(db_session, "pub_staff")
    _contact(db_session, facility, staff, ServiceType.PHC, "Synthetic PHC", "+910000000301")
    _contact(db_session, facility, staff, ServiceType.TRANSPORT, "Synthetic transport", "+910000000302")
    _contact(db_session, facility, staff, ServiceType.NUTRITION, "Synthetic nutrition", "+910000000303")
    _contact(db_session, facility, staff, ServiceType.PHC, "Retired number", "+910000000304", active=False)

    with TestClient(app) as anonymous:  # no login, no cookies
        r = anonymous.get(f"/api/v1/public/urgent-help/{facility.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["facility_name"] == "Synthetic Facility"
    assert {c["name"] for c in body["contacts"]} == {"Synthetic PHC", "Synthetic transport"}
    assert body["support_hours"] is None and body["wording_approved"] is False
    flat = str(body).lower()
    assert not any(k in flat for k in FORBIDDEN_KEYS)


def test_unknown_or_inactive_facility_is_not_found(db_session):
    org = make_org(db_session)
    closed = make_facility(db_session, org, "Closed", active=False)
    with TestClient(app) as anonymous:
        assert anonymous.get("/api/v1/public/urgent-help/00000000-0000-0000-0000-000000000000").status_code == 404
        assert anonymous.get("/api/v1/public/urgent-help/not-a-uuid").status_code == 404
        assert anonymous.get(f"/api/v1/public/urgent-help/{closed.id}").status_code == 404
