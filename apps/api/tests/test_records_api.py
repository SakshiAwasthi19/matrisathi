"""W2-A4: reports (AT08), prescriptions, observations, referrals (AT09) and
verified local contacts, through the API."""

import re
import tokenize
import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.main import app
from app.models.care import CareTask, TaskKind
from app.models.records import InstructionStatus, LocalContact, Prescription, PrescriptionSource
from app.models.staff import StaffRole
from app.services.file_store import LocalDiskFileStore, get_file_store
from tests.conftest import CSRF_HEADERS
from tests.factories import make_facility, make_membership, make_org, make_staff

PASSWORD = "synthetic-password-123"
PDF = b"%PDF-1.4\n% synthetic outside report\n"


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


@pytest.fixture
def w(db_session):
    org = make_org(db_session)
    fa, fb = make_facility(db_session, org, "Facility A"), make_facility(db_session, org, "Facility B")
    coord, doc, other = make_staff(db_session, "r_coord"), make_staff(db_session, "r_doc"), make_staff(db_session, "r_other")
    make_membership(db_session, coord, fa, StaffRole.COORDINATOR)
    make_membership(db_session, doc, fa, StaffRole.DOCTOR)
    make_membership(db_session, other, fb, StaffRole.DOCTOR)
    clients = {n: _client(n) for n in ("r_coord", "r_doc", "r_other")}
    c = clients["r_coord"]
    mothers = []
    for i in range(2):
        p = c.post("/api/v1/people", json={"full_name": f"Synthetic Mother {i}", "facility_id": str(fa.id), "phone": f"+91888880000{i}"}, headers=CSRF_HEADERS).json()
        e = c.post("/api/v1/pregnancy-episodes", json={"person_id": p["id"]}, headers=CSRF_HEADERS).json()
        mothers.append((p, e))
    yield {"coord": c, "doc": clients["r_doc"], "other": clients["r_other"], "fa": str(fa.id), "mothers": mothers, "doc_id": str(doc.id)}
    for cl in clients.values():
        cl.__exit__(None, None, None)


def _post(c, url, body):
    return c.post(url, json=body, headers=CSRF_HEADERS)


def _upload(c, person_id):
    r = c.post(f"/api/v1/files?subject_person_id={person_id}&filename=report.pdf", content=PDF, headers={**CSRF_HEADERS, "Content-Type": "application/pdf"})
    assert r.status_code == 201
    return r.json()["id"]


# --- AT08: reports are never shown as reviewed until a clinician reviews them ------


def test_uploaded_outside_report_is_received_not_reviewed(w):
    (person, ep), _ = w["mothers"]
    file_id = _upload(w["coord"], person["id"])
    inv = _post(w["coord"], f"/api/v1/pregnancy-episodes/{ep['id']}/investigations", {"name": "Outside report", "received_file_id": file_id, "source": "OUTSIDE_REPORT"})
    assert inv.status_code == 201
    body = inv.json()
    assert body["status"] == "RECEIVED"
    assert body["reviewed_at"] is None and body["reviewed_by_name"] is None
    assert body["requested_on"] is None and body["performed_on"] is None  # unknown stays unknown

    # A non-clinician cannot mark it reviewed: 403.
    denied = _post(w["coord"], f"/api/v1/investigations/{body['id']}/reviewed", {"expected_version": body["version"]})
    assert denied.status_code == 403

    ok = _post(w["doc"], f"/api/v1/investigations/{body['id']}/reviewed", {"expected_version": body["version"]})
    assert ok.status_code == 200
    assert ok.json()["status"] == "REVIEWED" and ok.json()["reviewed_by_name"] and ok.json()["reviewed_at"]


def test_requested_test_moves_step_by_step(w):
    (_, ep), _ = w["mothers"]
    inv = _post(w["coord"], f"/api/v1/pregnancy-episodes/{ep['id']}/investigations", {"name": "Placeholder test", "requested_on": str(date.today())}).json()
    assert inv["status"] == "REQUESTED"
    # Cannot jump to reviewed.
    assert _post(w["doc"], f"/api/v1/investigations/{inv['id']}/reviewed", {"expected_version": inv["version"]}).status_code == 409
    inv = _post(w["coord"], f"/api/v1/investigations/{inv['id']}/performed", {"expected_version": inv["version"]}).json()
    assert inv["status"] == "PERFORMED" and inv["performed_on"] is None
    inv = _post(w["coord"], f"/api/v1/investigations/{inv['id']}/received", {"expected_version": inv["version"]}).json()
    assert inv["status"] == "RECEIVED"


def test_file_of_another_mother_cannot_be_attached(w):
    (p0, ep0), (p1, _) = w["mothers"]
    other_file = _upload(w["coord"], p1["id"])
    r = _post(w["coord"], f"/api/v1/pregnancy-episodes/{ep0['id']}/investigations", {"name": "Wrong file", "received_file_id": other_file})
    assert r.status_code == 422


# --- Prescriptions -------------------------------------------------------------------


def test_prescription_needs_clinician_confirmation_before_any_reminder(w, db_session):
    (person, ep), _ = w["mothers"]
    file_id = _upload(w["coord"], person["id"])
    rx = _post(w["coord"], f"/api/v1/pregnancy-episodes/{ep['id']}/prescriptions", {"source": "PAPER_PRESCRIPTION", "source_file_id": file_id}).json()
    assert rx["instruction_status"] == "UNREVIEWED" and rx["reminder_enabled"] is False
    assert rx["source_file_id"] == file_id and rx["issued_on"] is None  # original kept; date unknown
    review = db_session.query(CareTask).filter(CareTask.source_record_id == uuid.UUID(rx["id"])).one()
    assert review.kind is TaskKind.REVIEW_WORK

    assert _post(w["coord"], f"/api/v1/prescriptions/{rx['id']}/review", {"expected_version": rx["version"], "decision": "CONFIRMED", "confirmed_instruction": "as written"}).status_code == 403

    # Unclear: no text, no reminder; the review work stays open with the clinician.
    unclear = _post(w["doc"], f"/api/v1/prescriptions/{rx['id']}/review", {"expected_version": rx["version"], "decision": "UNCLEAR"})
    assert unclear.status_code == 200
    assert unclear.json()["instruction_status"] == "UNCLEAR" and unclear.json()["reminder_enabled"] is False
    db_session.expire_all()
    review = db_session.get(CareTask, review.id)
    assert review.status.value == "ASSIGNED" and str(review.owner_staff_user_id) == w["doc_id"]

    # Confirming needs the instruction transcribed as written.
    rx = unclear.json()
    assert _post(w["doc"], f"/api/v1/prescriptions/{rx['id']}/review", {"expected_version": rx["version"], "decision": "CONFIRMED"}).status_code == 422
    ok = _post(w["doc"], f"/api/v1/prescriptions/{rx['id']}/review", {"expected_version": rx["version"], "decision": "CONFIRMED", "confirmed_instruction": "Synthetic instruction as written on the original", "reminder_enabled": True, "reminder_start": str(date.today())})
    assert ok.status_code == 200
    assert ok.json()["reminder_enabled"] is True and ok.json()["reviewed_by_name"]
    db_session.expire_all()
    assert db_session.get(CareTask, review.id).status.value == "COMPLETED"


def test_database_refuses_a_reminder_without_confirmation(w, db_session):
    (_, ep), _ = w["mothers"]
    rx = Prescription(
        episode_id=uuid.UUID(ep["id"]),
        facility_id=uuid.UUID(w["fa"]),
        source=PrescriptionSource.MCP_CARD,
        recorded_by_staff_user_id=uuid.UUID(w["doc_id"]),
        instruction_status=InstructionStatus.UNREVIEWED,
        reminder_enabled=True,
    )
    db_session.add(rx)
    with pytest.raises(IntegrityError, match="ck_prescription_reminder_only_when_confirmed"):
        db_session.commit()
    db_session.rollback()


# --- Observations (F012) ------------------------------------------------------------


def test_observation_is_stored_exactly_as_entered_and_corrections_keep_the_old_value(w):
    (_, ep), _ = w["mothers"]
    url = f"/api/v1/pregnancy-episodes/{ep['id']}/observations"
    o = _post(w["coord"], url, {"name": "Placeholder measurement", "value_text": "120/80", "unit": "mmHg", "source": "MEASURED_HERE"}).json()
    assert o["value_text"] == "120/80" and o["unit"] == "mmHg" and o["observed_on"] is None
    assert set(o) >= {"recorded_by_name", "source", "created_at"}
    assert not any(k in o for k in ("flag", "alert", "risk", "normal", "abnormal", "high", "low"))

    assert _post(w["coord"], f"/api/v1/observations/{o['id']}/correct", {"name": o["name"], "value_text": "110/80", "unit": "mmHg", "source": "MEASURED_HERE", "expected_version": o["version"]}).status_code == 422  # reason required
    fixed = _post(w["coord"], f"/api/v1/observations/{o['id']}/correct", {"name": o["name"], "value_text": "110/80", "unit": "mmHg", "source": "MEASURED_HERE", "expected_version": o["version"], "correction_reason": "TYPING_ERROR"})
    assert fixed.status_code == 201 and fixed.json()["corrects_id"] == o["id"]
    current = w["coord"].get(url).json()
    assert [x["value_text"] for x in current] == ["110/80"]
    everything = w["coord"].get(url + "?include_superseded=true").json()
    assert sorted(x["value_text"] for x in everything) == ["110/80", "120/80"]
    # The earlier entry cannot be corrected twice.
    assert _post(w["coord"], f"/api/v1/observations/{o['id']}/correct", {"name": o["name"], "value_text": "1", "source": "MEASURED_HERE", "expected_version": 2, "correction_reason": "OTHER"}).status_code == 409


def test_clinician_findings_are_clinician_only(w):
    (_, ep), _ = w["mothers"]
    body = {"kind": "CLINICIAN_FINDING", "name": "Finding", "value_text": "as written by the clinician", "source": "MEASURED_HERE"}
    assert _post(w["coord"], f"/api/v1/pregnancy-episodes/{ep['id']}/observations", body).status_code == 403
    assert _post(w["doc"], f"/api/v1/pregnancy-episodes/{ep['id']}/observations", body).status_code == 201


def test_no_code_compares_or_converts_observation_values():
    """F012 / G01 / G07: no thresholds, alerts or interpretation anywhere."""
    app_dir = Path(__file__).resolve().parents[1] / "app"
    pattern = re.compile(r"value_text\s*(<|>|<=|>=)|(float|int|Decimal)\(\s*[\w.]*value_text|threshold|is_abnormal|risk_score", re.I)
    offenders = []
    for path in app_dir.rglob("*.py"):
        # Code only: comments and string literals (docstrings explaining the
        # rule) are dropped, so only real expressions are checked.
        code_by_line: dict[int, list[str]] = {}
        with path.open("rb") as f:
            for tok in tokenize.tokenize(f.readline):
                if tok.type in (tokenize.COMMENT, tokenize.STRING, tokenize.ENCODING):
                    continue
                code_by_line.setdefault(tok.start[0], []).append(tok.string)
        for n, parts in code_by_line.items():
            line = " ".join(parts)
            if pattern.search(line):
                offenders.append(f"{path.name}:{n}: {line}")
    assert offenders == []


def test_the_scan_would_catch_a_threshold(tmp_path):
    """The scan above is only useful if it fires on real code."""
    pattern = re.compile(r"value_text\s*(<|>|<=|>=)|(float|int|Decimal)\(\s*[\w.]*value_text|threshold|is_abnormal|risk_score", re.I)
    for code in ("if o.value_text > 140:", "x = float(o.value_text)", "HIGH_THRESHOLD = 140"):
        assert pattern.search(code), code


# --- Local contacts (F044) -------------------------------------------------------------


def test_contact_shows_who_verified_and_becomes_stale(w, db_session):
    c = _post(w["coord"], "/api/v1/local-contacts", {"facility_id": w["fa"], "service_type": "TRANSPORT", "name": "Synthetic transport", "phone": "+910000000555", "landmarks": "Near the synthetic well"}).json()
    assert c["verified_by_name"] and c["stale"] is False
    row = db_session.get(LocalContact, uuid.UUID(c["id"]))
    row.verified_on = date.today() - timedelta(days=120)
    db_session.commit()
    listed = w["coord"].get(f"/api/v1/local-contacts?facility_id={w['fa']}").json()
    stale = next(x for x in listed if x["id"] == c["id"])
    assert stale["stale"] is True
    again = _post(w["coord"], f"/api/v1/local-contacts/{c['id']}/verify", {"expected_version": stale["version"]}).json()
    assert again["stale"] is False


# --- AT09: referrals close only through a defined state or reason ---------------------


def test_referral_lifecycle_and_closure_rules(w, db_session):
    (_, ep), _ = w["mothers"]
    contact = _post(w["coord"], "/api/v1/local-contacts", {"facility_id": w["fa"], "service_type": "REFERRAL_HOSPITAL", "name": "Synthetic district hospital", "phone": "+910000000777"}).json()
    url = f"/api/v1/pregnancy-episodes/{ep['id']}/referrals"
    assert _post(w["coord"], url, {"destination_contact_id": contact["id"], "urgency": "SOON"}).status_code == 403
    r = _post(w["doc"], url, {"destination_contact_id": contact["id"], "urgency": "SOON", "clinician_instruction": "Synthetic instruction"}).json()
    assert r["status"] == "SENT" and r["owner_name"]

    step = lambda ref, body: _post(w["coord"], f"/api/v1/referrals/{ref['id']}/step", {"expected_version": ref["version"], **body})  # noqa: E731
    # Nothing jumps to completion (e.g. "message sent" is not an outcome).
    assert step(r, {"to": "FOLLOW_UP_COMPLETED"}).status_code == 409
    # Closing needs a reason; a reason is only for closing.
    assert step(r, {"to": "CLOSED"}).status_code == 422
    assert step(r, {"to": "CONTACTED", "closure_reason": "FAMILY_DECLINED"}).status_code == 422

    r = step(r, {"to": "CONTACTED"}).json()
    r = step(r, {"to": "ATTENDED"}).json()
    assert r["attended_on"] is None  # unknown stays unknown
    r = step(r, {"to": "ADVICE_RECEIVED"}).json()
    follow_up = db_session.query(CareTask).filter(CareTask.source_record_id == uuid.UUID(r["id"])).one()
    assert follow_up.owner_staff_user_id is not None and follow_up.status.value == "ASSIGNED"
    r = step(r, {"to": "FOLLOW_UP_COMPLETED"}).json()
    assert r["status"] == "FOLLOW_UP_COMPLETED" and r["follow_up_completed_at"]

    second = _post(w["doc"], url, {"destination_name": "Synthetic clinic", "urgency": "ROUTINE"}).json()
    closed = step(second, {"to": "CLOSED", "closure_reason": "FAMILY_DECLINED"}).json()
    assert closed["status"] == "CLOSED" and closed["closure_reason"] == "FAMILY_DECLINED"


# --- Isolation ------------------------------------------------------------------------


def test_other_facility_sees_and_changes_nothing(w):
    (person, ep), _ = w["mothers"]
    inv = _post(w["coord"], f"/api/v1/pregnancy-episodes/{ep['id']}/investigations", {"name": "x"}).json()
    rx = _post(w["coord"], f"/api/v1/pregnancy-episodes/{ep['id']}/prescriptions", {"source": "MCP_CARD"}).json()
    o = w["other"]
    for kind in ("investigations", "prescriptions", "observations", "referrals"):
        assert o.get(f"/api/v1/pregnancy-episodes/{ep['id']}/{kind}").status_code == 404, kind
    assert _post(o, f"/api/v1/investigations/{inv['id']}/performed", {"expected_version": inv["version"]}).status_code == 404
    assert _post(o, f"/api/v1/prescriptions/{rx['id']}/review", {"expected_version": rx["version"], "decision": "UNCLEAR"}).status_code == 404
    assert o.get(f"/api/v1/local-contacts?facility_id={w['fa']}").status_code == 404
