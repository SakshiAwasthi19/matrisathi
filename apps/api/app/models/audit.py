import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow, uuid_pk


class AuditOutcome(str, enum.Enum):
    SUCCESS = "SUCCESS"
    DENIED = "DENIED"


class AuditEvent(Base):
    """Append-only. The application DB role has INSERT/SELECT only on this
    table (no UPDATE/DELETE) — enforced by a database grant, not just
    convention. See alembic revision 0002 and tests/test_audit_durability.py.

    `metadata_json` must never contain clinical content, passwords, or
    tokens — only structural facts (ids, actions, outcomes) needed to
    reconstruct who did what to which record and whether it was allowed.
    """

    __tablename__ = "audit_event"
    # The audit view (F037) lists one organisation's events newest first, by actor.
    __table_args__ = (Index("ix_audit_event_actor_occurred", "actor_staff_user_id", "occurred_at"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    actor_staff_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    outcome: Mapped[AuditOutcome] = mapped_column(Enum(AuditOutcome, name="audit_outcome"), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
