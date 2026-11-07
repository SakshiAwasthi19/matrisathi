"""SG2 acceptance cases (AT06-AT10, AT28) on the named synthetic scenarios
in tests/factories.py. Each test follows the tracker's steps; its name
starts with the AT id so the evidence table can point at it.

AT28 is covered at the model and access-check level only: patient sign-in
waits for D07, so the gate reports AT28 as Blocked: D07, not passed.
"""

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.core.config import Settings
from app.main import app
from app.models.care import CareTask, TaskKind
from app.models.caregiver import CaregiverScope
from app.scripts import seed_placeholder_template
from app.services.caregiver_access import caregiver_access_allowed
from app.services.file_store import LocalDiskFileStore, get_file_store
from tests.conftest import CSRF_HEADERS
from tests.factories import (
    scenario_late_presenter,
    scenario_outside_report,
    scenario_revoked_caregiver,
    scenario_shared_phone,
    scenario_unknown_lmp,
)

PASSWORD = "synthetic-password-123"
LOCAL_TODAY = (datetime.now(timezone.utc) + timedelta(minutes=330)).date()


@pytest.fixture(autouse=True)
def _store(tmp_path):
    app.dependency_overrides[get_file_store] = lambda: LocalDiskFileStore(tmp_path)
    yield
    app.dependency_overrides.pop(get_file_store, None)


@pytest.fixture
def login():
    opened: list[TestClient] = []

    def _login(user) -> TestClient:  # type: ignore[no-untyped-def]
        c = TestClient(app)
        c.__enter__()
        r = c.post("/api/v1/auth/login", json={"username": user.username, "password": PASSWORD}, headers=CSRF_HEADERS)
        assert r.status_code == 200
        opened.append(c)
        return c

    yield _login
    for c in opened:
        c.__exit__(None, None, None)


def post(c, url, body):
    return c.post(url, json=body, headers=CSRF_HEADERS)


def put(c, url, body):
    return c.put(url, json=body, headers=CSRF_HEADERS)


def _template_id(doc: TestClient) -> str:
    seed_placeholder_template.main()
    return doc.get("/api/v1/care-plan-templates").json()[0]["id"]


def _migrator(sql: str, **params) -> None:
    engine = create_engine(os.environ["DATABASE_URL_MIGRATOR"])
    with engine.begin() as conn:
        conn.execute(text(sql), params)
    engine.dispose()


# --- AT06: late / unknown dating and schedules ------------------------------------


def test_AT06_late_and_unknown_dating_and_schedules(db_session, login):
    # Unknown LMP: nothing recorded, nothing assumed.
    world, _, episode = scenario_unknown_lmp(db_session)
    coord, doc = login(world.coordinator), login(world.doctor)
    ep = str(episode.id)
    assert doc.get(f"/api/v1/pregnancy-episodes/{ep}/dating").json()["current"] is None

    # Only an APPROVED template version can be published (a draft cannot).
    template = _template_id(doc)
    draft = str(uuid.uuid4())
    _migrator(
        "INSERT INTO care_plan_template (id, organization_id, name, version_label, status, is_placeholder, created_at, updated_at)"
        " VALUES (:id, :o, 'Synthetic draft', 'draft-1', 'DRAFT', true, now(), now())",
        id=draft,
        o=world.org.id,
    )
    assert post(doc, f"/api/v1/pregnancy-episodes/{ep}/care-plan", {"template_id": draft}).status_code == 404
    assert post(coord, f"/api/v1/pregnancy-episodes/{ep}/care-plan", {"template_id": template}).status_code == 403
    assert post(doc, f"/api/v1/pregnancy-episodes/{ep}/care-plan", {"template_id": template}).status_code == 201

    # Late presenter: provisional date; only a clinician confirms or corrects it.
    world2, _, late = scenario_late_presenter(db_session)
    coord2, doc2 = login(world2.coordinator), login(world2.doctor)
    url = f"/api/v1/pregnancy-episodes/{late.id}/dating"
    current = coord2.get(url).json()["current"]
    assert current["state"] == "PROVISIONAL"
    assert post(coord2, url + "/confirm", {"dating_id": current["id"], "expected_version": current["version"]}).status_code == 403
    confirmed = post(doc2, url + "/confirm", {"dating_id": current["id"], "expected_version": current["version"]}).json()
    assert confirmed["state"] == "CONFIRMED"

    # Publish, attend the first visit (past retained), then correct the date.
    tid = _template_id(doc2)
    post(doc2, f"/api/v1/pregnancy-episodes/{late.id}/care-plan", {"template_id": tid})
    a = coord2.get(f"/api/v1/pregnancy-episodes/{late.id}/appointments").json()[0]
    a = post(coord2, f"/api/v1/appointments/{a['id']}/transition", {"to": "CONFIRMED", "expected_version": a["version"], "confirmed_for": datetime.now(timezone.utc).isoformat()}).json()
    post(coord2, f"/api/v1/appointments/{a['id']}/transition", {"to": "ATTENDED", "expected_version": a["version"]})
    corrected = post(doc2, url + "/correct", {"edd": str(LOCAL_TODAY + timedelta(days=20)), "precision": "EXACT", "evidence": "SCAN_REPORT", "expected_version": confirmed["version"]})
    assert corrected.status_code == 201
    history = doc2.get(url).json()["history"]
    assert len(history) == 2 and sum(1 for h in history if h["superseded_at"]) == 1
    statuses = {x["id"]: x["status"] for x in coord2.get(f"/api/v1/pregnancy-episodes/{late.id}/appointments").json()}
    assert statuses[a["id"]] == "ATTENDED"


# --- AT07: appointments and overdue work ---------------------------------------------


def test_AT07_appointments_missed_visit_backup_owner(db_session, login):
    world, _, episode = scenario_unknown_lmp(db_session, tag="at07")
    coord, doc = login(world.coordinator), login(world.doctor)
    ep = str(episode.id)
    post(doc, f"/api/v1/pregnancy-episodes/{ep}/care-plan", {"template_id": _template_id(doc)})
    appts = coord.get(f"/api/v1/pregnancy-episodes/{ep}/appointments").json()
    assert all(x["status"] == "REQUESTED" for x in appts)  # a request until a person confirms

    a = appts[0]
    a = post(coord, f"/api/v1/appointments/{a['id']}/transition", {"to": "CONFIRMED", "expected_version": a["version"], "confirmed_for": datetime.now(timezone.utc).isoformat()}).json()
    missed = post(coord, f"/api/v1/appointments/{a['id']}/transition", {"to": "MISSED", "expected_version": a["version"]}).json()
    follow_ups = db_session.query(CareTask).filter(CareTask.source_appointment_id == uuid.UUID(a["id"]), CareTask.kind == TaskKind.FOLLOW_UP_MISSED_VISIT).all()
    assert len(follow_ups) == 1

    # Reschedule once: only the newest is current.
    r = post(coord, f"/api/v1/appointments/{missed['id']}/reschedule", {"expected_version": missed["version"], "requested_for": str(LOCAL_TODAY + timedelta(days=3))}).json()
    assert r["new"]["previous_appointment_id"] == a["id"]
    assert post(coord, f"/api/v1/appointments/{missed['id']}/reschedule", {"expected_version": r["previous"]["version"], "requested_for": str(LOCAL_TODAY + timedelta(days=4))}).status_code == 409

    # Cancel another visit.
    other = next(x for x in coord.get(f"/api/v1/pregnancy-episodes/{ep}/appointments").json() if x["status"] == "REQUESTED" and x["id"] != r["new"]["id"])
    assert post(coord, f"/api/v1/appointments/{other['id']}/transition", {"to": "CANCELLED", "expected_version": other["version"], "reason": "FAMILY_REQUEST"}).json()["status"] == "CANCELLED"

    # Owner unavailable: the follow-up moves to the backup, still owned.
    task = coord.get(f"/api/v1/pregnancy-episodes/{ep}/tasks").json()
    fu = next(t for t in task if t["kind"] == "FOLLOW_UP_MISSED_VISIT")
    moved = post(coord, f"/api/v1/tasks/{fu['id']}/assign", {"expected_version": fu["version"], "owner_staff_user_id": str(world.nurse.id), "backup_staff_user_id": str(world.coordinator.id)}).json()
    assert moved["owner_staff_user_id"] == str(world.nurse.id) and moved["status"] == "ASSIGNED"

    # No inferred non-adherence: the next step stays an honest "none".
    assert coord.get(f"/api/v1/pregnancy-episodes/{ep}/next-action").json()["state"] == "NONE"


# --- AT08: reports and medicine records ---------------------------------------------------


def test_AT08_outside_report_and_prescriptions(db_session, login):
    world, person, episode, report = scenario_outside_report(db_session)
    coord, doc = login(world.coordinator), login(world.doctor)
    reports = coord.get(f"/api/v1/pregnancy-episodes/{episode.id}/investigations").json()
    r = next(x for x in reports if x["id"] == str(report.id))
    assert r["status"] == "RECEIVED" and r["reviewed_at"] is None and r["requested_on"] is None

    # Uploading a private report through the API gives a received record too.
    pdf = b"%PDF-1.4\n% synthetic\n"
    f = coord.post(f"/api/v1/files?subject_person_id={person.id}&filename=r.pdf", content=pdf, headers={**CSRF_HEADERS, "Content-Type": "application/pdf"}).json()
    up = post(coord, f"/api/v1/pregnancy-episodes/{episode.id}/investigations", {"name": "Synthetic uploaded report", "received_file_id": f["id"], "source": "OUTSIDE_REPORT"}).json()
    assert up["status"] == "RECEIVED"

    assert post(coord, f"/api/v1/investigations/{r['id']}/reviewed", {"expected_version": r["version"]}).status_code == 403
    reviewed = post(doc, f"/api/v1/investigations/{r['id']}/reviewed", {"expected_version": r["version"]}).json()
    assert reviewed["status"] == "REVIEWED" and reviewed["reviewed_by_name"] == "Synthetic Doctor"

    rx = post(coord, f"/api/v1/pregnancy-episodes/{episode.id}/prescriptions", {"source": "PAPER_PRESCRIPTION", "source_file_id": f["id"]}).json()
    assert rx["source_file_id"] == f["id"] and rx["reminder_enabled"] is False  # original retained
    unclear = post(doc, f"/api/v1/prescriptions/{rx['id']}/review", {"expected_version": rx["version"], "decision": "UNCLEAR"}).json()
    assert unclear["instruction_status"] == "UNCLEAR" and unclear["reminder_enabled"] is False  # ambiguous: queued, no reminder


# --- AT09: referral closure -------------------------------------------------------------


def test_AT09_referral_closes_only_by_state_or_reason(db_session, login):
    world, _, episode = scenario_unknown_lmp(db_session, tag="at09")
    coord, doc = login(world.coordinator), login(world.doctor)
    ref = post(doc, f"/api/v1/pregnancy-episodes/{episode.id}/referrals", {"destination_name": "Synthetic district hospital", "urgency": "SOON"}).json()

    def step(r, **body):
        return post(coord, f"/api/v1/referrals/{r['id']}/step", {"expected_version": r["version"], **body})

    # "A message was sent" is not an outcome: nothing jumps to completion.
    assert step(ref, to="FOLLOW_UP_COMPLETED").status_code == 409
    assert step(ref, to="CLOSED").status_code == 422  # closing needs a reason
    for to in ("CONTACTED", "ATTENDED", "ADVICE_RECEIVED", "FOLLOW_UP_COMPLETED"):
        ref = step(ref, to=to).json()
        assert ref["status"] == to
    advice_tasks = db_session.query(CareTask).filter(CareTask.source_record_id == uuid.UUID(ref["id"])).all()
    assert len(advice_tasks) == 1 and advice_tasks[0].owner_staff_user_id is not None  # owner visible


# --- AT10: birth plan and urgent help ---------------------------------------------------


def test_AT10_birth_plan_and_signed_out_urgent_help(db_session, login):
    world, _, episode = scenario_unknown_lmp(db_session, tag="at10")
    coord = login(world.coordinator)
    phc = post(coord, "/api/v1/local-contacts", {"facility_id": str(world.facility.id), "service_type": "PHC", "name": "Synthetic PHC", "phone": "+910000010101"}).json()
    hosp = post(coord, "/api/v1/local-contacts", {"facility_id": str(world.facility.id), "service_type": "REFERRAL_HOSPITAL", "name": "Synthetic hospital", "phone": "+910000010102"}).json()
    plan = put(coord, f"/api/v1/pregnancy-episodes/{episode.id}/birth-plan", {"expected_version": 0, "primary_contact_id": phc["id"], "alternate_contact_id": hosp["id"], "transport_arrangement": "Synthetic neighbour's vehicle"}).json()
    assert plan["primary_contact"]["verified_on"] and plan["alternate_contact"]["verified_on"]  # dated contacts
    assert not any(k in plan for k in ("eta", "dispatch", "location", "gps"))

    with TestClient(app) as anonymous:  # signed out, no location
        public = anonymous.get(f"/api/v1/public/urgent-help/{world.facility.id}").json()
    assert {c["phone"] for c in public["contacts"]} == {"+910000010101", "+910000010102"}
    assert public["wording_approved"] is False  # no unapproved instructions shown


# --- AT28: patient/caregiver access (model level; Blocked: D07) --------------------------


def test_AT28_model_level_revoked_caregiver_and_same_handset(db_session):
    world, mother, _, caregiver, sister, _ = scenario_revoked_caregiver(db_session)
    on = Settings(_env_file=None, patient_access_enabled=True)  # type: ignore[call-arg]
    for who in (caregiver, sister):
        assert caregiver_access_allowed(db_session, subject_person_id=mother.id, grantee_person_id=who.id, scope=CaregiverScope.NEXT_ACTION, config=on) is False
    # Two women on one phone stay separate people.
    _, (first, _), (second, _) = scenario_shared_phone(db_session)
    assert first.id != second.id
