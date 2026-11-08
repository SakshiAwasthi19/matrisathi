"""Doctor-approved wording shown to the public (D05, M015, F014).

The app never writes this content: it is loaded from the doctor's filled-in
D05 packet by `app/scripts/load_approved_content.py`, through the migrator
role. The app role can only read it. Until an approved version exists, the
public Urgent help page shows verified numbers only and says the wording is
awaiting approval.
"""

import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk
from app.models.care import TemplateStatus


class UrgentHelpContent(Base, TimestampMixin):
    __tablename__ = "urgent_help_content"
    __table_args__ = (
        UniqueConstraint("organization_id", "version_label", name="uq_urgent_help_content_version"),
        CheckConstraint(
            "status <> 'APPROVED' OR (approved_by_name IS NOT NULL AND approved_on IS NOT NULL"
            " AND effective_from IS NOT NULL)",
            name="ck_urgent_help_approval_recorded",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organization.id"), nullable=False)
    version_label: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[TemplateStatus] = mapped_column(
        Enum(TemplateStatus, name="template_status", create_type=False), nullable=False
    )
    heading: Mapped[str] = mapped_column(String(200), nullable=False)
    instruction_text: Mapped[str] = mapped_column(Text, nullable=False)
    when_to_call_text: Mapped[str] = mapped_column(Text, nullable=False)
    # Must state that messages are not monitored for emergencies.
    not_monitored_text: Mapped[str] = mapped_column(Text, nullable=False)
    support_hours_text: Mapped[str | None] = mapped_column(String(300), nullable=True)
    outside_hours_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    approved_by_role: Mapped[str | None] = mapped_column(String(100), nullable=True)
    approved_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
