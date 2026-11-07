import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk


class DatingSource(str, enum.Enum):
    SELF_REPORTED = "SELF_REPORTED"
    CLINICIAN_CONFIRMED = "CLINICIAN_CONFIRMED"
    UNKNOWN = "UNKNOWN"


class PregnancyEpisodeStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


ONE_ACTIVE_EPISODE_INDEX = "uq_pregnancy_episode_one_active"


class PregnancyEpisode(Base, TimestampMixin):
    __tablename__ = "pregnancy_episode"
    # D13 (option A): at most one ACTIVE episode per mother, enforced by the
    # database so concurrent requests cannot both create one.
    __table_args__ = (
        Index(
            ONE_ACTIVE_EPISODE_INDEX,
            "mother_person_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    mother_person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("person.id"), nullable=False
    )
    # Always derived server-side from the mother Person's registering
    # facility at creation time — never accepted from the client. A change
    # of facility is a transfer action (later work), not a field edit.
    facility_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("facility.id"), nullable=False
    )
    dating_estimate: Mapped[date | None] = mapped_column(Date, nullable=True)
    dating_source: Mapped[DatingSource] = mapped_column(
        Enum(DatingSource, name="dating_source"), nullable=False, default=DatingSource.UNKNOWN
    )
    status: Mapped[PregnancyEpisodeStatus] = mapped_column(
        Enum(PregnancyEpisodeStatus, name="pregnancy_episode_status"),
        nullable=False,
        default=PregnancyEpisodeStatus.ACTIVE,
    )
    created_by_staff_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_user.id"), nullable=False
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
