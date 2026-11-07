"""Private file storage (T009): validation and two storage backends.

Files are only ever served by the API (GET /api/v1/files/{id}) after a
facility check. Nothing here creates a public or long-lived URL.
"""

import os
import re
import tempfile
from pathlib import Path
from typing import Protocol

import httpx

from app.core.config import Settings, settings

MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB (Phase 1 plan section 5)
ALLOWED_TYPES = ("application/pdf", "image/jpeg", "image/png")
_KEY = re.compile(r"^[0-9a-f]{32}$")


class FileRejected(ValueError):
    """The upload breaks a rule (type, size, empty, mismatch). Safe to show."""


class FileStoreError(RuntimeError):
    """The storage backend failed. Never shown with backend details."""


def sniff_content_type(data: bytes) -> str | None:
    """The type from the file's first bytes, ignoring its name or header."""
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    return None


def validate_upload(data: bytes, declared_type: str | None) -> str:
    """Returns the verified content type, or raises FileRejected."""
    if not data:
        raise FileRejected("The file is empty.")
    if len(data) > MAX_FILE_BYTES:
        raise FileRejected("The file is larger than 10 MB.")
    actual = sniff_content_type(data)
    if actual is None:
        raise FileRejected("Only PDF, JPEG and PNG files are accepted.")
    declared = (declared_type or "").split(";")[0].strip().lower()
    if declared and declared != actual:
        raise FileRejected("The file's content does not match its stated type.")
    return actual


def safe_original_filename(name: str | None) -> str:
    """Display-only name: no path parts, no control characters, bounded length."""
    base = os.path.basename((name or "").replace("\\", "/"))
    cleaned = "".join(ch for ch in base if ch.isprintable() and ch not in '"<>|:*?').strip()
    return cleaned[:255] or "upload"


def _check_key(key: str) -> None:
    if not _KEY.match(key):
        raise FileStoreError("invalid storage key")


class FileStore(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...

    def get(self, key: str) -> bytes: ...


class LocalDiskFileStore:
    """For development and tests only. Keys are random hex, never user input."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        _check_key(key)
        return self.root / key[:2] / key

    def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise FileStoreError("storage key already used")
        fd, tmp = tempfile.mkstemp(dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            os.replace(tmp, path)
        except Exception:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise

    def get(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise FileStoreError("file missing from storage")
        return path.read_bytes()


class SupabaseFileStore:
    """Supabase Storage over HTTP with the service-role key (server side only).
    The bucket must be private; objects are fetched through the authenticated
    endpoint, never a public or signed link."""

    def __init__(self, base_url: str, service_key: str, bucket: str, client: httpx.Client | None = None) -> None:
        self.base = base_url.rstrip("/") + "/storage/v1/object"
        self.bucket = bucket
        self.headers = {"Authorization": f"Bearer {service_key}", "apikey": service_key}
        self.client = client or httpx.Client(timeout=30.0)

    def put(self, key: str, data: bytes, content_type: str) -> None:
        _check_key(key)
        try:
            resp = self.client.post(
                f"{self.base}/{self.bucket}/{key}",
                content=data,
                headers={**self.headers, "Content-Type": content_type, "x-upsert": "false"},
            )
        except httpx.HTTPError as err:
            raise FileStoreError("storage unavailable") from err
        if resp.status_code >= 300:
            raise FileStoreError(f"storage rejected upload ({resp.status_code})")

    def get(self, key: str) -> bytes:
        _check_key(key)
        try:
            resp = self.client.get(f"{self.base}/authenticated/{self.bucket}/{key}", headers=self.headers)
        except httpx.HTTPError as err:
            raise FileStoreError("storage unavailable") from err
        if resp.status_code != 200:
            raise FileStoreError(f"storage read failed ({resp.status_code})")
        return resp.content


def build_file_store(config: Settings = settings) -> FileStore:
    if config.file_store_backend == "supabase":
        if not config.supabase_url or not config.supabase_service_role_key:
            raise FileStoreError("Supabase storage is selected but not configured")
        return SupabaseFileStore(config.supabase_url, config.supabase_service_role_key, config.supabase_storage_bucket)
    if config.file_store_backend == "local":
        return LocalDiskFileStore(config.file_store_local_root)
    raise FileStoreError("unknown FILE_STORE_BACKEND")


_store: FileStore | None = None


def get_file_store() -> FileStore:
    """FastAPI dependency (overridden in tests)."""
    global _store
    if _store is None:
        _store = build_file_store()
    return _store
