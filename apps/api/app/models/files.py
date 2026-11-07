import uuid

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk


class FileObject(Base, TimestampMixin):
    """A privately stored file (T009). Never reachable by a public URL: it is
    served only through GET /api/v1/files/{id}, which checks the caller's
    facility on every download. The storage key is random; the original
    filename is kept only as metadata and never used as a path."""

    __tablename__ = "file_object"
    __table_args__ = (
        CheckConstraint("size_bytes > 0", name="ck_file_object_size_positive"),
        CheckConstraint(
            "content_type IN ('application/pdf', 'image/jpeg', 'image/png')", name="ck_file_object_type"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    facility_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("facility.id"), nullable=False)
    subject_person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("person.id"), nullable=False
    )
    storage_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    uploaded_by_staff_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_user.id"), nullable=False
    )
