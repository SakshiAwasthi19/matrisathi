"""T009 through the API: private upload and download, facility-scoped."""

import uuid

import pytest

from app.main import app
from app.models.audit import AuditEvent
from app.services.file_store import LocalDiskFileStore, get_file_store
from tests.conftest import CSRF_HEADERS
from tests.factories import make_facility, make_membership, make_org, make_staff

PDF = b"%PDF-1.4\n% synthetic test report\n"
PASSWORD = "synthetic-password-123"


@pytest.fixture(autouse=True)
def _local_store(tmp_path):
    app.dependency_overrides[get_file_store] = lambda: LocalDiskFileStore(tmp_path)
    yield
    app.dependency_overrides.pop(get_file_store, None)


def _login(client, username):
    assert (
        client.post(
            "/api/v1/auth/login", json={"username": username, "password": PASSWORD}, headers=CSRF_HEADERS
        ).status_code
        == 200
    )


def _setup(client, db_session):
    org = make_org(db_session)
    fa, fb = make_facility(db_session, org, "Facility A"), make_facility(db_session, org, "Facility B")
    a, b = make_staff(db_session, "file_a"), make_staff(db_session, "file_b")
    make_membership(db_session, a, fa)
    make_membership(db_session, b, fb)
    _login(client, "file_a")
    person = client.post(
        "/api/v1/people",
        json={"full_name": "Synthetic Mother", "facility_id": str(fa.id), "phone": "+916666600001"},
        headers=CSRF_HEADERS,
    ).json()
    return person


def _upload(client, person_id, data=PDF, content_type="application/pdf", filename="report.pdf"):
    return client.post(
        f"/api/v1/files?subject_person_id={person_id}&filename={filename}",
        content=data,
        headers={**CSRF_HEADERS, "Content-Type": content_type},
    )


def test_upload_then_download_by_the_same_facility(client, db_session):
    person = _setup(client, db_session)
    resp = _upload(client, person["id"])
    assert resp.status_code == 201
    body = resp.json()
    assert body["content_type"] == "application/pdf"
    assert body["size_bytes"] == len(PDF)
    assert "storage_key" not in body  # never exposed

    dl = client.get(f"/api/v1/files/{body['id']}")
    assert dl.status_code == 200
    assert dl.content == PDF
    assert dl.headers["cache-control"] == "no-store"
    assert dl.headers["content-disposition"].startswith("attachment;")


def test_download_requires_sign_in(client, db_session):
    person = _setup(client, db_session)
    file_id = _upload(client, person["id"]).json()["id"]
    client.post("/api/v1/auth/logout", headers=CSRF_HEADERS)
    assert client.get(f"/api/v1/files/{file_id}").status_code == 401


def test_other_facility_cannot_download_and_it_is_audited(client, db_session):
    person = _setup(client, db_session)
    file_id = _upload(client, person["id"]).json()["id"]
    client.post("/api/v1/auth/logout", headers=CSRF_HEADERS)
    _login(client, "file_b")
    assert client.get(f"/api/v1/files/{file_id}").status_code == 404
    denied = db_session.query(AuditEvent).filter(
        AuditEvent.action == "download", AuditEvent.entity_id == file_id
    ).one()
    assert denied.outcome.value == "DENIED"


def test_other_facility_cannot_upload_for_the_person(client, db_session):
    person = _setup(client, db_session)
    client.post("/api/v1/auth/logout", headers=CSRF_HEADERS)
    _login(client, "file_b")
    assert _upload(client, person["id"]).status_code == 404


def test_guessed_file_id_is_not_found(client, db_session):
    _setup(client, db_session)
    assert client.get(f"/api/v1/files/{uuid.uuid4()}").status_code == 404


def test_unsupported_and_mismatched_files_are_refused(client, db_session):
    person = _setup(client, db_session)
    assert _upload(client, person["id"], b"<html>hi</html>", "text/html").status_code == 415
    assert _upload(client, person["id"], b"not really a pdf", "application/pdf").status_code == 415
    assert _upload(client, person["id"], b"", "application/pdf").status_code == 415


def test_oversized_file_is_refused(client, db_session):
    person = _setup(client, db_session)
    big = PDF + b"0" * (10 * 1024 * 1024)
    assert _upload(client, person["id"], big).status_code == 413


def test_upload_requires_csrf_header(client, db_session):
    person = _setup(client, db_session)
    resp = client.post(
        f"/api/v1/files?subject_person_id={person['id']}", content=PDF, headers={"Content-Type": "application/pdf"}
    )
    assert resp.status_code == 403


def test_audit_never_records_the_filename(client, db_session):
    person = _setup(client, db_session)
    file_id = _upload(client, person["id"], filename="Synthetic-Mother-name-report.pdf").json()["id"]
    row = db_session.query(AuditEvent).filter(AuditEvent.action == "upload", AuditEvent.entity_id == file_id).one()
    assert "Synthetic-Mother" not in str(row.metadata_json)
    assert row.metadata_json == {"content_type": "application/pdf", "size_bytes": len(PDF)}
