"""Private file upload and download (T009, W2-A1).

Upload: the raw file is the request body (no multipart, so no extra
dependency). Download: streamed by the API after a live facility check;
there is no public or long-lived URL. Missing and not-yours are both 404.
Audit records sizes and types only, never the filename (it can contain a
person's name).
"""

import hashlib
import uuid
from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_staff, require_csrf_header, require_facility_membership
from app.models.audit import AuditOutcome
from app.models.files import FileObject
from app.models.identity import Person
from app.models.staff import StaffUser
from app.services import audit_service
from app.services.file_store import (
    MAX_FILE_BYTES,
    FileRejected,
    FileStore,
    FileStoreError,
    get_file_store,
    safe_original_filename,
    validate_upload,
)

router = APIRouter(prefix="/files", tags=["files"])


class FileObjectOut(BaseModel):
    id: str
    subject_person_id: str
    original_filename: str
    content_type: str
    size_bytes: int
    created_at: datetime


def _out(f: FileObject) -> FileObjectOut:
    return FileObjectOut(
        id=str(f.id),
        subject_person_id=str(f.subject_person_id),
        original_filename=f.original_filename,
        content_type=f.content_type,
        size_bytes=f.size_bytes,
        created_at=f.created_at,
    )


def _deny(staff: StaffUser, action: str, entity_id: str | None, reason: str) -> HTTPException:
    audit_service.record_event(
        actor_staff_user_id=staff.id,
        action=action,
        entity_type="FileObject",
        entity_id=entity_id,
        outcome=AuditOutcome.DENIED,
        metadata={"reason": reason},
    )
    return HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")


@router.post("", response_model=FileObjectOut, status_code=status.HTTP_201_CREATED)
async def upload_file(
    request: Request,
    subject_person_id: uuid.UUID = Query(...),
    filename: str | None = Query(default=None, max_length=255),
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
    _csrf: None = Depends(require_csrf_header),
    store: FileStore = Depends(get_file_store),
) -> FileObjectOut:
    declared_length = request.headers.get("content-length")
    if declared_length and declared_length.isdigit() and int(declared_length) > MAX_FILE_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="The file is larger than 10 MB.")

    person = db.get(Person, subject_person_id)
    if person is None:
        raise _deny(staff, "upload", None, "person_not_found_or_inaccessible")
    try:
        require_facility_membership(db, staff, person.registering_facility_id)
    except HTTPException:
        raise _deny(staff, "upload", None, "person_not_found_or_inaccessible") from None

    data = await request.body()
    try:
        content_type = validate_upload(data, request.headers.get("content-type"))
    except FileRejected as err:
        code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE if len(data) > MAX_FILE_BYTES else status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
        raise HTTPException(code, detail=str(err)) from None

    key = uuid.uuid4().hex
    try:
        store.put(key, data, content_type)
    except FileStoreError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="The file could not be stored. Try again.") from None

    record = FileObject(
        facility_id=person.registering_facility_id,  # derived on the server, never from the client
        subject_person_id=person.id,
        storage_key=key,
        original_filename=safe_original_filename(filename),
        content_type=content_type,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        uploaded_by_staff_user_id=staff.id,
    )
    db.add(record)
    db.commit()
    audit_service.record_event(
        actor_staff_user_id=staff.id,
        action="upload",
        entity_type="FileObject",
        entity_id=str(record.id),
        outcome=AuditOutcome.SUCCESS,
        metadata={"content_type": content_type, "size_bytes": len(data)},
    )
    return _out(record)


@router.get("/{file_id}")
def download_file(
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
    store: FileStore = Depends(get_file_store),
) -> Response:
    record = db.get(FileObject, file_id)
    if record is None:
        raise _deny(staff, "download", str(file_id), "not_found")
    try:
        require_facility_membership(db, staff, record.facility_id)
    except HTTPException:
        raise _deny(staff, "download", str(file_id), "not_authorized") from None

    try:
        data = store.get(record.storage_key)
    except FileStoreError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="The file could not be read. Try again.") from None

    audit_service.record_event(
        actor_staff_user_id=staff.id,
        action="download",
        entity_type="FileObject",
        entity_id=str(record.id),
        outcome=AuditOutcome.SUCCESS,
        metadata={},
    )
    return Response(
        content=data,
        media_type=record.content_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(record.original_filename)}",
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
