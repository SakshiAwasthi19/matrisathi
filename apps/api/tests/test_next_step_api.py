"""W2-A5: next action, birth plan, family reports and help requests."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.care import CareTask, TaskKind
from app.models.staff import StaffRole
from app.scripts import seed_placeholder_template
from tests.conftest import CSRF_HEADERS
from tests.factories import make_facility, make_membership, make_org, make_staff

PASSWORD = "synthetic-password-123"


def _client(username: str) -> TestClient:
    c = TestClient(app)
    c.__enter__()
    assert c.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD}, headers=CSRF_HEADERS).status_code == 200
    return c


def _post(c, url, body):
    return c.post(url, json=body, headers=CSRF_HEADERS)


def _put(c, url, body):
    return c.put(url, json=body, headers=CSRF_HEADERS)


@pytest.fixture
def w(db_session):
    org = make_org(db_session)
    fa, fb = make_facility(db_session, org, "Facility A"), make_facility(db_session, org, "Facility B")
    coord, doc, other = make_staff(db_session, "n_coord"), make_staff(db_session, "n_doc"), make_staff(db_session, "n_other")
    make_membership(db_session, coord, fa, StaffRole.COORDINATOR)
    make_membership(db_session, doc, fa, StaffRole.DOCTOR)
    make_membership(db_session, other, fb, StaffRole.DOCTOR)
    seed_placeholder_template.main()
    cl = {n: _client(n) for n in ("n_coord", "n_doc", "n_other")}
    c = cl["n_coord"]
    p = c.post("/api/v1/people", json={"full_name": "Synthetic Mother", "facility_id": str(fa.id), "phone": "+919999900001"}, headers=CSRF_HEADERS).json()
    ep = c.post("/api/v1/pregnancy-episodes", json={"person_id": p["id"]}, headers=CSRF_HEADERS).json()
    phc = _post(c, "/api/v1/local-contacts", {"facility_id": str(fa.id), "service_type": "PHC", "name": "Synthetic PHC", "phone": "+910000000101"}).json()
    hosp = _post(c, "/api/v1/local-contacts", {"facility_id": str(fa.id), "service_type": "REFERRAL_HOSPITAL", "name": "Synthetic hospital", "phone": "+910000000102"}).json()
    other_contact = _post(cl["n_other"], "/api/v1/local-contacts", {"facility_id": str(fb.id), "service_type": "PHC", "name": "Other PHC", "phone": "+910000000199"}).json()
    yield {"coord": c, "doc": cl["n_doc"], "other": cl["n_other"], "ep": ep["id"], "phc": phc, "hosp": hosp, "other_contact": other_contact}
    for x in cl.values():
        x.__exit__(None, None, None)


# --- Next action ------------------------------------------------------------------


def test_no_confirmed_step_is_said_honestly(w):
    r = w["coord"].get(f"/api/v1/pregnancy-episodes/{w['ep']}/next-action")
    assert r.status_code == 200
    body = r.json()
    assert body["state"] == "NONE" and body["appointment_id"] is None and body["confirmed_for"] is None
    assert body["unconfirmed_requests"] == 0
    assert {c["name"] for c in body["help_contacts"]} == {"Synthetic PHC", "Synthetic hospital"}


def test_requested_appointments_are_not_shown_as_the_next_step(w):
    templates = w["doc"].get("/api/v1/care-plan-templates").json()
    _post(w["doc"], f"/api/v1/pregnancy-episodes/{w['ep']}/care-plan", {"template_id": templates[0]["id"]})
    body = w["coord"].get(f"/api/v1/pregnancy-episodes/{w['ep']}/next-action").json()
    assert body["state"] == "NONE"  # requests are not confirmed actions
    assert body["unconfirmed_requests"] == 2


def _confirmed_next(w):
    templates = w["doc"].get("/api/v1/care-plan-templates").json()
    _post(w["doc"], f"/api/v1/pregnancy-episodes/{w['ep']}/care-plan", {"template_id": templates[0]["id"]})
    appts = w["coord"].get(f"/api/v1/pregnancy-episodes/{w['ep']}/appointments").json()
    a = appts[0]
    when = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    _post(w["coord"], f"/api/v1/appointments/{a['id']}/transition", {"to": "CONFIRMED", "expected_version": a["version"], "confirmed_for": when, "location_note": "Synthetic sub-centre"})
    return w["coord"].get(f"/api/v1/pregnancy-episodes/{w['ep']}/next-action").json()


def test_next_confirmed_action_with_preparation_and_placeholder_flag(w):
    body = _confirmed_next(w)
    assert body["state"] == "CONFIRMED"
    assert body["location_note"] == "Synthetic sub-centre"
    assert body["is_placeholder"] is True and "Placeholder" in body["preparation_text"]
    assert body["family_report"] is None  # nothing reported yet: unknown, not "missed"


def test_family_report_is_separate_from_staff_status_and_help_opens_one_task(w, db_session):
    body = _confirmed_next(w)
    r = _post(w["coord"], f"/api/v1/appointments/{body['appointment_id']}/family-report", {"expected_version": body["version"], "report": "NEED_HELP", "barrier": "TRAVEL"})
    assert r.status_code == 200 and r.json()["family_report"] == "NEED_HELP"
    appts = {a["id"]: a for a in w["coord"].get(f"/api/v1/pregnancy-episodes/{w['ep']}/appointments").json()}
    assert appts[body["appointment_id"]]["status"] == "CONFIRMED"  # staff status unchanged
    tasks = db_session.query(CareTask).filter(CareTask.kind == TaskKind.HELP_REQUEST, CareTask.source_record_id == uuid.UUID(body["appointment_id"])).all()
    assert len(tasks) == 1 and tasks[0].owner_staff_user_id is not None and tasks[0].barrier == "TRAVEL"

    # "Done" as reported by the family does not mark the visit attended.
    done = _post(w["coord"], f"/api/v1/appointments/{body['appointment_id']}/family-report", {"expected_version": r.json()["version"], "report": "DONE"})
    assert done.status_code == 200
    appts = {a["id"]: a for a in w["coord"].get(f"/api/v1/pregnancy-episodes/{w['ep']}/appointments").json()}
    assert appts[body["appointment_id"]]["status"] == "CONFIRMED"


# --- Birth plan ------------------------------------------------------------------------


def _plan(w, client="coord", **fields):
    current = w[client].get(f"/api/v1/pregnancy-episodes/{w['ep']}/birth-plan").json()
    body = {"expected_version": current["version"] if current else 0, **fields}
    return _put(w[client], f"/api/v1/pregnancy-episodes/{w['ep']}/birth-plan", body)


def test_birth_plan_starts_unknown_and_saves_with_verified_contacts(w):
    assert w["coord"].get(f"/api/v1/pregnancy-episodes/{w['ep']}/birth-plan").json() is None
    r = _plan(w, chosen_birth_place_contact_id=w["phc"]["id"], companion_name="Synthetic companion", transport_arrangement="Neighbour's vehicle (synthetic)", landmarks="Near the synthetic temple", primary_contact_id=w["phc"]["id"], alternate_contact_id=w["hosp"]["id"])
    assert r.status_code == 200
    p = r.json()
    assert p["chosen_birth_place"]["name"] == "Synthetic PHC"
    assert p["primary_contact"]["phone"] == "+910000000101" and p["alternate_contact"]["verified_on"]
    assert p["staff_verified_at"] is None and p["family_report"] is None


def test_contacts_must_come_from_this_facility(w):
    assert _plan(w, primary_contact_id=w["other_contact"]["id"]).status_code == 422


def test_referral_site_is_clinician_only(w):
    assert _plan(w, referral_site_contact_id=w["hosp"]["id"]).status_code == 403
    ok = _plan(w, client="doc", referral_site_contact_id=w["hosp"]["id"])
    assert ok.status_code == 200 and ok.json()["referral_site_set_by_name"]
    # A non-clinician may still edit other fields while keeping the site.
    kept = _plan(w, referral_site_contact_id=w["hosp"]["id"], companion_name="Changed")
    assert kept.status_code == 200 and kept.json()["referral_site"]["name"] == "Synthetic hospital"


def test_verification_is_cleared_by_any_change(w):
    p = _plan(w, landmarks="Old landmark").json()
    v = _post(w["coord"], f"/api/v1/pregnancy-episodes/{w['ep']}/birth-plan/verify", {"expected_version": p["version"]}).json()
    assert v["staff_verified_by_name"] and v["staff_verified_at"]
    changed = _plan(w, landmarks="New landmark").json()
    assert changed["staff_verified_at"] is None


def test_family_report_is_kept_apart_from_staff_verification(w, db_session):
    p = _plan(w, landmarks="Landmark").json()
    r = _post(w["coord"], f"/api/v1/pregnancy-episodes/{w['ep']}/birth-plan/family-report", {"expected_version": p["version"], "report": "DONE"}).json()
    assert r["family_report"] == "DONE" and r["staff_verified_at"] is None
    need = _post(w["coord"], f"/api/v1/pregnancy-episodes/{w['ep']}/birth-plan/family-report", {"expected_version": r["version"], "report": "NEED_HELP", "barrier": "COST"})
    assert need.status_code == 200
    tasks = db_session.query(CareTask).filter(CareTask.kind == TaskKind.HELP_REQUEST, CareTask.source_record_type == "BIRTH_PLAN").all()
    assert len(tasks) == 1


def test_stale_version_is_refused(w):
    _plan(w, landmarks="A")
    assert _put(w["coord"], f"/api/v1/pregnancy-episodes/{w['ep']}/birth-plan", {"expected_version": 0, "landmarks": "B"}).status_code == 409


# --- Isolation --------------------------------------------------------------------------


def test_other_facility_sees_and_changes_nothing(w):
    body = _confirmed_next(w)
    _plan(w, landmarks="x")
    o = w["other"]
    assert o.get(f"/api/v1/pregnancy-episodes/{w['ep']}/next-action").status_code == 404
    assert o.get(f"/api/v1/pregnancy-episodes/{w['ep']}/birth-plan").status_code == 404
    assert _put(o, f"/api/v1/pregnancy-episodes/{w['ep']}/birth-plan", {"expected_version": 1, "landmarks": "y"}).status_code == 404
    assert _post(o, f"/api/v1/appointments/{body['appointment_id']}/family-report", {"expected_version": body["version"], "report": "DONE"}).status_code == 404
