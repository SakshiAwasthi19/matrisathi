"""T009: upload validation and both storage backends (no network)."""

import uuid

import httpx
import pytest

from app.services.file_store import (
    MAX_FILE_BYTES,
    FileRejected,
    FileStoreError,
    LocalDiskFileStore,
    SupabaseFileStore,
    safe_original_filename,
    sniff_content_type,
    validate_upload,
)

PDF = b"%PDF-1.4\n% synthetic test document\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16


@pytest.mark.parametrize(("data", "kind"), [(PDF, "application/pdf"), (PNG, "image/png"), (JPEG, "image/jpeg")])
def test_type_comes_from_content(data, kind):
    assert sniff_content_type(data) == kind
    assert validate_upload(data, None) == kind
    assert validate_upload(data, kind) == kind


@pytest.mark.parametrize(
    "data",
    [b"MZ\x90\x00 an executable", b"<html><script>alert(1)</script>", b"GIF89a....", b"plain text"],
)
def test_unsupported_content_is_rejected(data):
    with pytest.raises(FileRejected, match="Only PDF, JPEG and PNG"):
        validate_upload(data, "application/pdf")


def test_fake_pdf_is_rejected_even_with_a_pdf_header():
    with pytest.raises(FileRejected):
        validate_upload(b"this is not a pdf", "application/pdf")


def test_declared_type_must_match_content():
    with pytest.raises(FileRejected, match="does not match"):
        validate_upload(PNG, "application/pdf")


def test_empty_and_oversized_are_rejected():
    with pytest.raises(FileRejected, match="empty"):
        validate_upload(b"", "application/pdf")
    with pytest.raises(FileRejected, match="10 MB"):
        validate_upload(PDF + b"0" * MAX_FILE_BYTES, "application/pdf")


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        ("../../etc/passwd", "passwd"),
        ("C:\\Users\\x\\report.pdf", "report.pdf"),
        ('a"b<c>.pdf', "abc.pdf"),
        ("", "upload"),
        (None, "upload"),
        ("x" * 400 + ".pdf", ("x" * 400 + ".pdf")[:255]),
    ],
)
def test_original_filename_is_display_only(raw, clean):
    assert safe_original_filename(raw) == clean


def test_local_store_round_trip_and_key_rules(tmp_path):
    store = LocalDiskFileStore(tmp_path)
    key = uuid.uuid4().hex
    store.put(key, PDF, "application/pdf")
    assert store.get(key) == PDF
    with pytest.raises(FileStoreError):
        store.put(key, PDF, "application/pdf")  # never overwrite
    for bad in ("../evil", "ABC", key + "x", ""):
        with pytest.raises(FileStoreError):
            store.get(bad)
    with pytest.raises(FileStoreError):
        store.get(uuid.uuid4().hex)  # missing


def test_supabase_store_uses_private_authenticated_endpoints():
    seen: list[httpx.Request] = []
    stored: dict[str, bytes] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        key = request.url.path.rsplit("/", 1)[-1]
        if request.method == "POST":
            stored[key] = request.content
            return httpx.Response(200, json={"Key": key})
        return httpx.Response(200, content=stored[key])

    client = httpx.Client(transport=httpx.MockTransport(handler))
    store = SupabaseFileStore("https://proj.supabase.invalid/", "svc-key", "matrisathi-files", client=client)
    key = uuid.uuid4().hex
    store.put(key, PNG, "image/png")
    assert store.get(key) == PNG

    upload, download = seen
    assert upload.url.path == f"/storage/v1/object/matrisathi-files/{key}"
    assert upload.headers["x-upsert"] == "false"
    assert download.url.path == f"/storage/v1/object/authenticated/matrisathi-files/{key}"
    assert all(r.headers["authorization"] == "Bearer svc-key" for r in seen)
    assert not any("public" in r.url.path or "sign" in r.url.path for r in seen)


def test_supabase_failures_become_store_errors_without_details():
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500, text="internal secret detail")))
    store = SupabaseFileStore("https://proj.supabase.invalid", "svc-key", "b", client=client)
    with pytest.raises(FileStoreError) as exc:
        store.put(uuid.uuid4().hex, PDF, "application/pdf")
    assert "secret" not in str(exc.value)
    with pytest.raises(FileStoreError):
        store.get(uuid.uuid4().hex)
