"""W2-A3 API: dating, plan publishing, appointments and owned tasks.

Covers the build plan's list: late presentation, unknown LMP, a correction
that keeps the past intact, a missed visit producing exactly one task, a
non-clinician trying to confirm (403), and isolation across facilities.
"""

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app
from app.models.care import Appointment, AppointmentStatus, CareTask, TaskKind
from app.models.staff import StaffRole
from app.scripts import seed_placeholder_template
from tests.conftest import CSRF_HEADERS
from tests.factories import make_facility, make_membership, make_org, make_staff

PASSWORD = "synthetic-password-123"
TODAY = (datetime.now(timezone.utc) + timedelta(minutes=330)).date()


def _login(c: TestClient, username: str) -> None:
    r = c.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD}, headers=CSRF_HEADERS)
    assert r.status_code == 200


@pytest.fixture
def w(db_session):
    org = make_org(db_session)
    fa, fb = make_facility(db_session, org, "Facility A"), make_facility(db_session, org, "Facility B")
    coord, doctor, other = make_staff(db_session, "c_coord"), make_staff(db_session, "c_doc"), make_staff(db_session, "c_other")
    backup = make_staff(db_session, "c_backup")
    make_membership(db_session, coord, fa, StaffRole.COORDINATOR)
    make_membership(db_session, doctor, fa, StaffRole.DOCTOR)
    make_membership(db_session, backup, fa, StaffRole.NURSE)
    make_membership(db_session, other, fb, StaffRole.DOCTOR)
    seed_placeholder_template.main()  # through the migrator role, as in real use

    clients = {}
    for name in ("c_coord", "c_doc", "c_other"):
        c = TestClient(app)
        c.__enter__()
        _login(c, name)
        clients[name] = c
    person = clients["c_coord"].post(
        "/api/v1/people",
        json={"full_name": "Synthetic Late Presenter", "facility_id": str(fa.id), "phone": "+917777700001"},
        headers=CSRF_HEADERS,
    ).json()
    episode = clients["c_coord"].post(
        "/api/v1/pregnancy-episodes", json={"person_id": person["id"]}, headers=CSRF_HEADERS
    ).json()
    templates = clients["c_doc"].get("/api/v1/care-plan-templates").json()
    yield {
        "coord": clients["c_coord"],
        "doc": clients["c_doc"],
        "other": clients["c_other"],
        "episode": episode["id"],
        "template": templates[0],
        "ids": {"coord": str(coord.id), "doc": str(doctor.id), "backup": str(backup.id), "other": str(other.id)},
    }
    for c in clients.values():
        c.__exit__(None, None, None)


def _post(c: TestClient, url: str, body: dict):
    return c.post(url, json=body, headers=CSRF_HEADERS)


def _publish(w, client="doc", template_id=None):
    return _post(w[client], f"/api/v1/pregnancy-episodes/{w['episode']}/care-plan", {"template_id": template_id or w["template"]["id"]})


# --- Templates and the placeholder ----------------------------------------------


def test_placeholder_template_is_labelled_and_has_no_week_timing(w):
    t = w["template"]
    assert t["is_placeholder"] is True
    assert "PLACEHOLDER" in t["name"] and "NOT CLINICALLY APPROVED" in t["name"]
    assert all(i["timing_basis"] in ("AT_PUBLISH", "DAYS_AFTER_PUBLISH") for i in t["items"])


def test_seed_script_is_idempotent(w):
    seed_placeholder_template.main()
    assert len(w["doc"].get("/api/v1/care-plan-templates").json()) == 1


# --- Dating ------------------------------------------------------------------------


def test_unknown_dating_stays_unknown(w):
    r = w["coord"].get(f"/api/v1/pregnancy-episodes/{w['episode']}/dating")
    assert r.status_code == 200 and r.json() == {"current": None, "history": []}
    # Recording "nothing known" is not an entry: it is refused, not defaulted.
    bad = _post(w["coord"], f"/api/v1/pregnancy-episodes/{w['episode']}/dating", {"precision": "EXACT", "evidence": "SELF_REPORTED"})
    assert bad.status_code == 422
    episode = w["coord"].get(f"/api/v1/pregnancy-episodes/{w['episode']}").json()
    assert episode["dating_estimate"] is None and episode["dating_source"] == "UNKNOWN"


def test_provisional_then_clinician_confirms(w):
    url = f"/api/v1/pregnancy-episodes/{w['episode']}/dating"
    rec = _post(w["coord"], url, {"edd": str(TODAY + timedelta(days=60)), "precision": "APPROXIMATE", "evidence": "SELF_REPORTED"})
    assert rec.status_code == 201 and rec.json()["state"] == "PROVISIONAL"
    d = rec.json()

    # A coordinator cannot confirm (clinician-only): 403.
    denied = _post(w["coord"], url + "/confirm", {"dating_id": d["id"], "expected_version": d["version"]})
    assert denied.status_code == 403

    ok = _post(w["doc"], url + "/confirm", {"dating_id": d["id"], "expected_version": d["version"]})
    assert ok.status_code == 200
    assert ok.json()["state"] == "CONFIRMED" and ok.json()["confirmed_by_name"]
    episode = w["coord"].get(f"/api/v1/pregnancy-episodes/{w['episode']}").json()
    assert episode["dating_source"] == "CLINICIAN_CONFIRMED"

    # Once confirmed, a non-clinician cannot replace it with a provisional entry.
    again = _post(w["coord"], url, {"edd": str(TODAY), "precision": "EXACT", "evidence": "SELF_REPORTED"})
    assert again.status_code == 409


def test_stale_version_is_refused(w):
    url = f"/api/v1/pregnancy-episodes/{w['episode']}/dating"
    d = _post(w["coord"], url, {"lmp_date": str(TODAY - timedelta(days=100)), "precision": "EXACT", "evidence": "CARD_OR_DOCUMENT"}).json()
    assert _post(w["doc"], url + "/confirm", {"dating_id": d["id"], "expected_version": d["version"] + 1}).status_code == 409


def test_correction_keeps_history_and_past_intact(w, db_session):
    url = f"/api/v1/pregnancy-episodes/{w['episode']}/dating"
    first = _post(w["doc"], url + "/correct", {"edd": str(TODAY + timedelta(days=90)), "precision": "EXACT", "evidence": "SCAN_REPORT", "expected_version": 0})
    assert first.status_code == 201

    plan = _publish(w).json()
    appts = w["coord"].get(f"/api/v1/pregnancy-episodes/{w['episode']}/appointments").json()
    attended = appts[0]
    _post(w["coord"], f"/api/v1/appointments/{attended['id']}/transition", {"to": "CONFIRMED", "expected_version": attended["version"], "confirmed_for": datetime.now(timezone.utc).isoformat()})
    attended = next(a for a in w["coord"].get(f"/api/v1/pregnancy-episodes/{w['episode']}/appointments").json() if a["id"] == attended["id"])
    assert _post(w["coord"], f"/api/v1/appointments/{attended['id']}/transition", {"to": "ATTENDED", "expected_version": attended["version"]}).status_code == 200

    # A future, week-timed appointment (as the approved template will create).
    week_item_id = _insert_week_timed_item(w["template"]["id"])
    future = Appointment(
        episode_id=uuid.UUID(w["episode"]),
        facility_id=_facility_of(db_session, w["episode"]),
        care_plan_id=uuid.UUID(plan["id"]),
        template_item_id=week_item_id,
        status=AppointmentStatus.REQUESTED,
        requested_for=TODAY + timedelta(days=20),
    )
    db_session.add(future)
    db_session.commit()

    current = w["doc"].get(url).json()["current"]
    corrected = _post(w["doc"], url + "/correct", {"edd": str(TODAY + timedelta(days=75)), "precision": "EXACT", "evidence": "SCAN_REPORT", "expected_version": current["version"]})
    assert corrected.status_code == 201

    history = w["doc"].get(url).json()
    assert len(history["history"]) == 2
    assert history["current"]["id"] == corrected.json()["id"]
    assert sum(1 for h in history["history"] if h["superseded_at"]) == 1

    after = {a["id"]: a for a in w["coord"].get(f"/api/v1/pregnancy-episodes/{w['episode']}/appointments").json()}
    assert after[attended["id"]]["status"] == "ATTENDED"  # the past is untouched
    assert after[str(future.id)]["status"] == "CANCELLED"
    assert after[str(future.id)]["status_reason"] == "DATING_CORRECTED"
    # Items not timed by week are unaffected.
    assert all(a["status"] == "REQUESTED" for i, a in after.items() if i not in (attended["id"], str(future.id)))
    tasks = w["doc"].get(f"/api/v1/pregnancy-episodes/{w['episode']}/tasks").json()
    review = [t for t in tasks if t["kind"] == "REVIEW_WORK"]
    assert len(review) == 1 and review[0]["owner_staff_user_id"] == w["ids"]["doc"]


# --- Plans ----------------------------------------------------------------------------


def test_late_presentation_publish_schedules_from_today(w):
    # No dating at all (late, unknown LMP): the plan still publishes; nothing is backdated.
    r = _publish(w)
    assert r.status_code == 201
    body = r.json()
    assert body["template"]["is_placeholder"] is True and body["unscheduled_item_names"] == []
    appts = w["coord"].get(f"/api/v1/pregnancy-episodes/{w['episode']}/appointments").json()
    assert sorted(a["requested_for"] for a in appts) == [str(TODAY), str(TODAY + timedelta(days=28))]
    assert all(a["status"] == "REQUESTED" for a in appts)  # a request until a person confirms
    tasks = w["coord"].get(f"/api/v1/pregnancy-episodes/{w['episode']}/tasks").json()
    assert sorted(t["name"] for t in tasks) == ["Placeholder follow-up call", "Placeholder test request"]
    assert all(t["status"] == "NEW" and not t["overdue"] for t in tasks)


def test_only_a_clinician_publishes_and_not_twice(w):
    assert _publish(w, client="coord").status_code == 403
    assert _publish(w).status_code == 201
    assert _publish(w).status_code == 409


def test_week_timed_items_wait_for_an_approved_rule(w):
    _insert_week_timed_item(w["template"]["id"])
    body = _publish(w).json()
    assert body["unscheduled_item_names"] == ["Week-timed item (test)"]


# --- Appointments -----------------------------------------------------------------------


def _first_appointment(w):
    appts = w["coord"].get(f"/api/v1/pregnancy-episodes/{w['episode']}/appointments").json()
    return next(a for a in appts if a["requested_for"] == str(TODAY))


def _confirm(w, a):
    r = _post(w["coord"], f"/api/v1/appointments/{a['id']}/transition", {"to": "CONFIRMED", "expected_version": a["version"], "confirmed_for": datetime.now(timezone.utc).isoformat(), "location_note": "Synthetic sub-centre"})
    assert r.status_code == 200
    return r.json()


def test_missed_visit_creates_exactly_one_owned_follow_up(w, db_session):
    _publish(w)
    a = _confirm(w, _first_appointment(w))
    missed = _post(w["coord"], f"/api/v1/appointments/{a['id']}/transition", {"to": "MISSED", "expected_version": a["version"]})
    assert missed.status_code == 200
    # MISSED is final: pressing it again is refused, never a second task.
    again = _post(w["coord"], f"/api/v1/appointments/{a['id']}/transition", {"to": "MISSED", "expected_version": missed.json()["version"]})
    assert again.status_code == 409
    follow_ups = db_session.query(CareTask).filter(CareTask.source_appointment_id == uuid.UUID(a["id"]), CareTask.kind == TaskKind.FOLLOW_UP_MISSED_VISIT).all()
    assert len(follow_ups) == 1
    assert follow_ups[0].owner_staff_user_id is not None and follow_ups[0].status.value == "ASSIGNED"


def test_illegal_appointment_move_is_refused(w):
    _publish(w)
    a = _first_appointment(w)
    r = _post(w["coord"], f"/api/v1/appointments/{a['id']}/transition", {"to": "ATTENDED", "expected_version": a["version"]})
    assert r.status_code == 409  # REQUESTED -> ATTENDED skips confirmation


def test_reschedule_once_and_only_newest_is_current(w):
    _publish(w)
    a = _confirm(w, _first_appointment(w))
    r = _post(w["coord"], f"/api/v1/appointments/{a['id']}/reschedule", {"expected_version": a["version"], "requested_for": str(TODAY + timedelta(days=3)), "reason": "FAMILY_REQUEST"})
    assert r.status_code == 201
    assert r.json()["previous"]["status"] == "RESCHEDULED"
    assert r.json()["new"]["previous_appointment_id"] == a["id"]
    # The old appointment cannot be rescheduled a second time.
    old = r.json()["previous"]
    assert _post(w["coord"], f"/api/v1/appointments/{old['id']}/reschedule", {"expected_version": old["version"], "requested_for": str(TODAY + timedelta(days=5))}).status_code == 409


def test_missed_visit_can_be_rescheduled_and_stays_missed(w):
    _publish(w)
    a = _confirm(w, _first_appointment(w))
    m = _post(w["coord"], f"/api/v1/appointments/{a['id']}/transition", {"to": "MISSED", "expected_version": a["version"]}).json()
    r = _post(w["coord"], f"/api/v1/appointments/{m['id']}/reschedule", {"expected_version": m["version"], "requested_for": str(TODAY + timedelta(days=2))})
    assert r.status_code == 201 and r.json()["previous"]["status"] == "MISSED"
    assert _post(w["coord"], f"/api/v1/appointments/{m['id']}/reschedule", {"expected_version": r.json()["previous"]["version"], "requested_for": str(TODAY + timedelta(days=4))}).status_code == 409


def test_republishing_a_new_template_keeps_attended_and_cancels_future(w):
    _publish(w)
    a = _confirm(w, _first_appointment(w))
    _post(w["coord"], f"/api/v1/appointments/{a['id']}/transition", {"to": "ATTENDED", "expected_version": a["version"]})
    second = _second_placeholder_template()
    assert _publish(w, template_id=second).status_code == 201
    appts = w["coord"].get(f"/api/v1/pregnancy-episodes/{w['episode']}/appointments").json()
    by_status = {}
    for x in appts:
        by_status.setdefault(x["status"], []).append(x)
    assert len(by_status["ATTENDED"]) == 1
    assert all(x["status_reason"] == "PLAN_SUPERSEDED" for x in by_status["CANCELLED"])
    assert w["coord"].get(f"/api/v1/pregnancy-episodes/{w['episode']}/care-plan").json()["template"]["id"] == second


# --- Tasks -------------------------------------------------------------------------------


def test_task_assign_attempt_close(w):
    _publish(w)
    t = next(t for t in w["coord"].get(f"/api/v1/pregnancy-episodes/{w['episode']}/tasks").json() if t["status"] == "NEW")
    # Owner must work at the facility.
    bad = _post(w["coord"], f"/api/v1/tasks/{t['id']}/assign", {"expected_version": t["version"], "owner_staff_user_id": w["ids"]["other"]})
    assert bad.status_code == 422
    same = _post(w["coord"], f"/api/v1/tasks/{t['id']}/assign", {"expected_version": t["version"], "owner_staff_user_id": w["ids"]["coord"], "backup_staff_user_id": w["ids"]["coord"]})
    assert same.status_code == 422
    t = _post(w["coord"], f"/api/v1/tasks/{t['id']}/assign", {"expected_version": t["version"], "owner_staff_user_id": w["ids"]["coord"], "backup_staff_user_id": w["ids"]["backup"]}).json()
    assert t["status"] == "ASSIGNED" and t["owner_name"]

    mine = w["coord"].get("/api/v1/tasks?mine=true").json()
    assert [x["id"] for x in mine] == [t["id"]]

    t = _post(w["coord"], f"/api/v1/tasks/{t['id']}/attempt", {"expected_version": t["version"], "awaiting_patient": True, "barrier": "TRAVEL"}).json()
    assert t["status"] == "AWAITING_PATIENT" and t["barrier"] == "TRAVEL" and t["last_attempt_at"]

    closed = _post(w["coord"], f"/api/v1/tasks/{t['id']}/close", {"expected_version": t["version"], "outcome": "UNREACHABLE", "closure_reason": "COULD_NOT_REACH"})
    assert closed.status_code == 200
    assert closed.json()["status"] == "COMPLETED" and closed.json()["outcome"] == "UNREACHABLE"
    assert w["coord"].get("/api/v1/tasks?mine=true").json() == []  # closed tasks leave the worklist


def test_free_text_is_not_accepted_for_barriers_or_reasons(w):
    _publish(w)
    t = next(t for t in w["coord"].get(f"/api/v1/pregnancy-episodes/{w['episode']}/tasks").json() if t["status"] == "NEW")
    r = _post(w["coord"], f"/api/v1/tasks/{t['id']}/close", {"expected_version": t["version"], "outcome": "DONE", "closure_reason": "she told me about her husband"})
    assert r.status_code == 422


def test_overdue_is_administrative_and_only_for_open_tasks(w, db_session):
    _publish(w)
    task = db_session.query(CareTask).filter(CareTask.episode_id == uuid.UUID(w["episode"])).first()
    task.due_at = datetime.now(timezone.utc) - timedelta(days=1)
    db_session.commit()
    t = next(x for x in w["coord"].get(f"/api/v1/pregnancy-episodes/{w['episode']}/tasks").json() if x["id"] == str(task.id))
    assert t["overdue"] is True


# --- Isolation ----------------------------------------------------------------------------


def test_other_facility_sees_and_changes_nothing(w):
    _publish(w)
    a = _first_appointment(w)
    t = w["coord"].get(f"/api/v1/pregnancy-episodes/{w['episode']}/tasks").json()[0]
    o = w["other"]  # a DOCTOR, but at facility B
    ep = w["episode"]
    for url in (f"/api/v1/pregnancy-episodes/{ep}/dating", f"/api/v1/pregnancy-episodes/{ep}/care-plan", f"/api/v1/pregnancy-episodes/{ep}/appointments", f"/api/v1/pregnancy-episodes/{ep}/tasks"):
        assert o.get(url).status_code == 404, url
    assert _post(o, f"/api/v1/pregnancy-episodes/{ep}/dating/correct", {"edd": str(TODAY), "precision": "EXACT", "evidence": "SCAN_REPORT", "expected_version": 0}).status_code == 404
    assert _publish(w, client="other").status_code == 404
    assert _post(o, f"/api/v1/appointments/{a['id']}/transition", {"to": "CANCELLED", "expected_version": a["version"]}).status_code == 404
    assert _post(o, f"/api/v1/tasks/{t['id']}/close", {"expected_version": t["version"], "outcome": "DONE", "closure_reason": "DONE_AS_PLANNED"}).status_code == 404
    assert o.get("/api/v1/tasks").json() == []


# --- helpers ------------------------------------------------------------------------------


def _migrator_engine():
    return create_engine(os.environ["DATABASE_URL_MIGRATOR"])


def _insert_week_timed_item(template_id: str) -> uuid.UUID:
    item_id = uuid.uuid4()
    with _migrator_engine().begin() as conn:
        conn.execute(
            text(
                "INSERT INTO care_plan_template_item (id, template_id, position, name, kind, timing_basis, week_from,"
                " week_to, created_at, updated_at) VALUES (:id, :t, 99, 'Week-timed item (test)', 'VISIT',"
                " 'GESTATIONAL_WEEKS', 10, 12, now(), now())"
            ),
            {"id": item_id, "t": template_id},
        )
    return item_id


def _second_placeholder_template() -> str:
    template_id = uuid.uuid4()
    with _migrator_engine().begin() as conn:
        org = conn.execute(text("SELECT organization_id FROM care_plan_template LIMIT 1")).scalar_one()
        conn.execute(
            text(
                "INSERT INTO care_plan_template (id, organization_id, name, version_label, status, is_placeholder,"
                " created_at, updated_at) VALUES (:id, :o, 'SYNTHETIC PLACEHOLDER – NOT CLINICALLY APPROVED',"
                " 'placeholder-2', 'APPROVED', true, now(), now())"
            ),
            {"id": template_id, "o": org},
        )
        conn.execute(
            text(
                "INSERT INTO care_plan_template_item (id, template_id, position, name, kind, timing_basis, offset_days,"
                " created_at, updated_at) VALUES (gen_random_uuid(), :t, 1, 'Placeholder contact C', 'VISIT',"
                " 'DAYS_AFTER_PUBLISH', 10, now(), now())"
            ),
            {"t": template_id},
        )
    return str(template_id)


def _facility_of(db_session, episode_id: str) -> uuid.UUID:
    from app.models.pregnancy import PregnancyEpisode

    return db_session.get(PregnancyEpisode, uuid.UUID(episode_id)).facility_id

