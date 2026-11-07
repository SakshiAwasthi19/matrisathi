"""Birth preparation plan (F013) and family responses (F006), W2-A5.

What the family reports is stored apart from what staff verified, and
neither is inferred from the other. No dispatch, ETA, GPS, geofence or
guarantee of transport: places and phone numbers come from the
facility's verified local contacts; arrangements are plain notes.
"""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk


def _fk(target: str, nullable: bool = True) -> Any:
    return mapped_column(UUID(as_uuid=True), ForeignKey(target), nullable=nullable)


class FamilyReport(str, enum.Enum):
    """What the mother or family said, recorded by staff on their behalf
    until patient access exists (D07). Never a staff verification."""

    DONE = "DONE"
    NOT_DONE = "NOT_DONE"
    NEED_HELP = "NEED_HELP"


class AppointmentFamilyReport(str, enum.Enum):
    DONE = "DONE"
    COULD_NOT_GO = "COULD_NOT_GO"
    NEED_HELP = "NEED_HELP"


class BirthPlan(Base, TimestampMixin):
    __tablename__ = "birth_plan"
    __table_args__ = (
        CheckConstraint(
            "(staff_verified_at IS NULL) = (staff_verified_by_staff_user_id IS NULL)",
            name="ck_birth_plan_verification_attributed",
        ),
        CheckConstraint(
            "(referral_site_contact_id IS NULL) = (referral_site_set_by_staff_user_id IS NULL)",
            name="ck_birth_plan_referral_site_attributed",
        ),
        CheckConstraint(
            "(family_report IS NULL) = (family_reported_at IS NULL)", name="ck_birth_plan_family_report_dated"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    episode_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pregnancy_episode.id"), nullable=False, unique=True
    )
    facility_id: Mapped[uuid.UUID] = _fk("facility.id", nullable=False)
    # The family's choice of where to give birth.
    chosen_birth_place_contact_id: Mapped[uuid.UUID | None] = _fk("local_contact.id")
    chosen_birth_place_note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Chosen by a clinician only.
    referral_site_contact_id: Mapped[uuid.UUID | None] = _fk("local_contact.id")
    referral_site_set_by_staff_user_id: Mapped[uuid.UUID | None] = _fk("staff_user.id")
    companion_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    transport_arrangement: Mapped[str | None] = mapped_column(String(300), nullable=True)
    landmarks: Mapped[str | None] = mapped_column(String(300), nullable=True)
    primary_contact_id: Mapped[uuid.UUID | None] = _fk("local_contact.id")
    alternate_contact_id: Mapped[uuid.UUID | None] = _fk("local_contact.id")
    family_report: Mapped[FamilyReport | None] = mapped_column(Enum(FamilyReport, name="family_report"), nullable=True)
    family_reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    staff_verified_by_staff_user_id: Mapped[uuid.UUID | None] = _fk("staff_user.id")
    staff_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    __mapper_args__ = {"version_id_col": version}
