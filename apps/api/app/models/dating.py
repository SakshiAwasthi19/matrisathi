"""Pregnancy dating history (F005, W2-A3).

Every entry is kept. A new entry supersedes the current one instead of
overwriting it, so "what did we believe, when, and who said so" is always
answerable. An unknown date is simply the absence of an entry: nothing is
defaulted or calculated here.
"""

import enum
import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import CheckConstraint, Date, DateTime, Enum, ForeignKey, Index, Integer, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk


class DatingState(str, enum.Enum):
    PROVISIONAL = "PROVISIONAL"
    CONFIRMED = "CONFIRMED"


class DatingPrecision(str, enum.Enum):
    EXACT = "EXACT"
    APPROXIMATE = "APPROXIMATE"  # e.g. only the month is known


class DatingEvidence(str, enum.Enum):
    """Where the date came from. Recorded, never weighed by the system."""

    SELF_REPORTED = "SELF_REPORTED"
    CARD_OR_DOCUMENT = "CARD_OR_DOCUMENT"
    SCAN_REPORT = "SCAN_REPORT"
    CLINICIAN_ASSESSMENT = "CLINICIAN_ASSESSMENT"


def _fk(target: str, nullable: bool = False) -> Any:
    return mapped_column(UUID(as_uuid=True), ForeignKey(target), nullable=nullable)


class EpisodeDating(Base, TimestampMixin):
    __tablename__ = "episode_dating"
    __table_args__ = (
        CheckConstraint("lmp_date IS NOT NULL OR edd IS NOT NULL", name="ck_dating_has_a_date"),
        CheckConstraint(
            "(state = 'CONFIRMED') = (confirmed_by_staff_user_id IS NOT NULL AND confirmed_at IS NOT NULL)",
            name="ck_dating_confirmation_attributed",
        ),
        CheckConstraint(
            "(superseded_at IS NULL) = (superseded_by_id IS NULL)", name="ck_dating_supersession_complete"
        ),
        Index(
            "uq_episode_dating_one_current",
            "episode_id",
            unique=True,
            postgresql_where=text("superseded_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    episode_id: Mapped[uuid.UUID] = _fk("pregnancy_episode.id")
    facility_id: Mapped[uuid.UUID] = _fk("facility.id")
    lmp_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    edd: Mapped[date | None] = mapped_column(Date, nullable=True)
    precision: Mapped[DatingPrecision] = mapped_column(Enum(DatingPrecision, name="dating_precision"), nullable=False)
    evidence: Mapped[DatingEvidence] = mapped_column(Enum(DatingEvidence, name="dating_evidence"), nullable=False)
    state: Mapped[DatingState] = mapped_column(Enum(DatingState, name="dating_state"), nullable=False)
    recorded_by_staff_user_id: Mapped[uuid.UUID] = _fk("staff_user.id")
    confirmed_by_staff_user_id: Mapped[uuid.UUID | None] = _fk("staff_user.id", nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Deferred so the old entry can point at its replacement within the same
    # transaction, before the replacement row is inserted.
    superseded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("episode_dating.id", deferrable=True, initially="DEFERRED"),
        nullable=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    __mapper_args__ = {"version_id_col": version}
