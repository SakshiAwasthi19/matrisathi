import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk


class StaffRole(str, enum.Enum):
    ASHA = "ASHA"
    # ANM (auxiliary nurse midwife): its own role from F004/M008 Q9. Starts with
    # the same capabilities as NURSE (app/domain/permissions.py).
    ANM = "ANM"
    NURSE = "NURSE"
    COORDINATOR = "COORDINATOR"
    DOCTOR = "DOCTOR"


class StaffUser(Base, TimestampMixin):
    __tablename__ = "staff_user"

    id: Mapped[uuid.UUID] = uuid_pk()
    # Unique login identifier, independent of contact phone (a phone number
    # is never a person's identity in this system — see Person/ContactMethod).
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class StaffMembership(Base, TimestampMixin):
    __tablename__ = "staff_membership"

    id: Mapped[uuid.UUID] = uuid_pk()
    staff_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_user.id"), nullable=False
    )
    facility_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("facility.id"), nullable=False
    )
    role: Mapped[StaffRole] = mapped_column(Enum(StaffRole, name="staff_role"), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RefreshToken(Base, TimestampMixin):
    """Opaque refresh tokens; only the hash is stored. Rotated on every use."""

    __tablename__ = "refresh_token"

    id: Mapped[uuid.UUID] = uuid_pk()
    staff_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_user.id"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("refresh_token.id"), nullable=True
    )


class LoginAttempt(Base, TimestampMixin):
    """Backs login throttling. Records both failed and successful attempts."""

    __tablename__ = "login_attempt"

    id: Mapped[uuid.UUID] = uuid_pk()
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    succeeded: Mapped[bool] = mapped_column(Boolean, nullable=False)
