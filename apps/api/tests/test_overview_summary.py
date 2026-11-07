"""Overview summary: what is waiting, per bucket, scoped to the caller's
facilities, with no names in the audit trail."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models.audit import AuditEvent
from app.models.staff import StaffRole
from app.services.file_store import LocalDiskFileStore, get_file_store
from tests.conftest import CSRF_HEADERS
from tests.factories import make_facility, make_membership, make_org, make_staff

PASSWORD = "synthetic-password-123"
PDF = b"%PDF-1.4\n% synthetic outside report\n"
URL = "/api/v1/overview/summary"
BUCKETS = {
    "reports_to_review",
    "prescriptions_to_review",
    "dating_not_confirmed",
    "no_care_plan",
    "contact_not_confirmed",
    "referrals_in_progress",
}


@pytest.fixture(autouse=True)
def _store(tmp_path):
    app.dependency_overrides[get_file_store] = lambda: LocalDiskFileStore(tmp_path)
    yield
    app.dependency_overrides.pop(get_file_store, None)


def _client(username: str) -> TestClient:
    c = TestClient(app)
    c.__enter__()
    r = c.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD}, headers=CSRF_HEADERS)
    assert r.status_code == 200
    return c


def _post(c, url, body):
    return c.post(url, json=body, headers=CSRF_HEADERS)


@pytest.fixture
def w(db_session):
    org = make_org(db_session)
    fa, fb = make_facility(db_session, org, "Facility A"), make_facility(db_session, org, "Facility B")
    coord, doc, other = make_staff(db_session, "o_coord"), make_staff(db_session, "o_doc"), make_staff(db_session, "o_other")
    make_membership(db_session, coord, fa, StaffRole.COORDINATOR)
    make_membership(db_session, doc, fa, StaffRole.DOCTOR)
    make_membership(db_session, other, fb, StaffRole.DOCTOR)
    clients = {n: _client(n) for n in ("o_coord", "o_doc", "o_other")}
    c = clients["o_coord"]
    mothers = []
    for i in range(2):
        p = _post(c, "/api/v1/people", {"full_name": f"Synthetic Overview Mother {i}", "facility_id": str(fa.id), "phone": f"+91777770000{i}"}).json()
        e = _post(c, "/api/v1/pregnancy-episodes", {"person_id": p["id"]}).json()
        mothers.append((p, e))
    yield {"coord": c, "doc": clients["o_doc"], "other": clients["o_other"], "mothers": mothers}
    for cl in clients.values():
        cl.__exit__(None, None, None)


def _summary(c):
    r = c.get(URL)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == BUCKETS
    return body


def _ids(bucket):
    return [r["episode_id"] for r in bucket["records"]]


def test_new_records_wait_for_dating_plan_and_contact(w):
    s = _summary(w["coord"])
    episodes = [e["id"] for _, e in w["mothers"]]
    for name in ("dating_not_confirmed", "no_care_plan", "contact_not_confirmed"):
        assert s[name]["count"] == 2, name
        assert _ids(s[name]) == episodes, name  # oldest first
    for name in ("reports_to_review", "prescriptions_to_review", "referrals_in_progress"):
        assert s[name] == {"count": 0, "records": []}, name
    assert s["no_care_plan"]["records"][0]["mother_full_name"] == "Synthetic Overview Mother 0"


def test_report_waits_until_a_clinician_reviews_it(w):
    (person, ep), _ = w["mothers"]
    up = w["coord"].post(
        f"/api/v1/files?subject_person_id={person['id']}&filename=report.pdf",
        content=PDF,
        headers={**CSRF_HEADERS, "Content-Type": "application/pdf"},
    )
    inv = _post(w["coord"], f"/api/v1/pregnancy-episodes/{ep['id']}/investigations", {"name": "Outside report", "received_file_id": up.json()["id"]}).json()
    assert inv["status"] == "RECEIVED"
    s = _summary(w["doc"])
    assert s["reports_to_review"]["count"] == 1 and _ids(s["reports_to_review"]) == [ep["id"]]

    assert _post(w["doc"], f"/api/v1/investigations/{inv['id']}/reviewed", {"expected_version": inv["version"]}).status_code == 200
    assert _summary(w["doc"])["reports_to_review"]["count"] == 0


def test_unreviewed_prescription_and_confirmed_contact(w):
    (p0, ep0), (_, ep1) = w["mothers"]
    assert _post(w["coord"], f"/api/v1/pregnancy-episodes/{ep0['id']}/prescriptions", {"source": "MCP_CARD"}).status_code == 201
    assert _post(w["coord"], f"/api/v1/people/{p0['id']}/contact/verify", {}).status_code == 200
    s = _summary(w["coord"])
    assert _ids(s["prescriptions_to_review"]) == [ep0["id"]]
    assert s["contact_not_confirmed"]["count"] == 1 and _ids(s["contact_not_confirmed"]) == [ep1["id"]]


def test_other_facility_sees_none_of_it(w):
    s = _summary(w["other"])
    assert all(s[name] == {"count": 0, "records": []} for name in BUCKETS)


def test_audit_holds_counts_not_names(w, db_session):
    _summary(w["coord"])
    event = db_session.execute(
        select(AuditEvent).where(AuditEvent.action == "overview_summary").order_by(AuditEvent.id.desc())
    ).scalars().first()
    assert event is not None
    assert set(event.metadata_json) == BUCKETS
    assert all(isinstance(v, int) for v in event.metadata_json.values())
    assert "Synthetic" not in str(event.metadata_json)


def test_requires_sign_in():
    with TestClient(app) as anon:
        assert anon.get(URL).status_code == 401
