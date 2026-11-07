"""at most one ACTIVE pregnancy episode per mother (D13, option A)

Revision ID: a13d5e0c7f01
Revises: 67ca239c7fe7
Create Date: 2026-11-07 00:00:00.000000

Adds a partial unique index so a mother can have at most one ACTIVE
pregnancy episode. Before creating it, the migration checks for mothers who
already have more than one ACTIVE episode and stops with a clear message if
any exist. It never closes or deletes episodes itself: resolving duplicates
is a deliberate, human step (see docs/delivery/staging.md, "Duplicate
active episodes").
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a13d5e0c7f01"
down_revision: str | None = "67ca239c7fe7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_NAME = "uq_pregnancy_episode_one_active"

_COUNT_DUPLICATES = sa.text(
    """
    SELECT count(*) FROM (
        SELECT mother_person_id
        FROM pregnancy_episode
        WHERE status = 'ACTIVE'
        GROUP BY mother_person_id
        HAVING count(*) > 1
    ) AS duplicates
    """
)


def assert_no_duplicate_active_episodes(conn: sa.engine.Connection) -> None:
    """Raises if any mother has more than one ACTIVE episode. Reports only a
    count, never names or IDs, so nothing identifying reaches a log."""
    duplicates = conn.execute(_COUNT_DUPLICATES).scalar_one()
    if duplicates:
        raise RuntimeError(
            f"{duplicates} mother(s) have more than one ACTIVE pregnancy episode, so the "
            "one-active-episode rule cannot be added. No data was changed. Resolve them first: "
            "see docs/delivery/staging.md, 'Duplicate active episodes'."
        )


def upgrade() -> None:
    assert_no_duplicate_active_episodes(op.get_bind())
    op.create_index(
        INDEX_NAME,
        "pregnancy_episode",
        ["mother_person_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="pregnancy_episode")
