"""Seeds the SYNTHETIC PLACEHOLDER care-plan template for every organization.

It contains no clinical content: generic contacts timed relative to the
publish date, never pregnancy weeks, every label marked as a placeholder.
It exists so the plan, appointment and task flows can be built and
demonstrated before the doctor approves the real template (D05). The
approved template replaces it as data, without code changes.

Writes through the migrator role (the app role can only read templates).
Refused when ENV=production. Safe to run more than once.

Usage: uv run python -m app.scripts.seed_placeholder_template
"""

import uuid

from sqlalchemy import create_engine, text

from app.core.config import settings

NAME = "SYNTHETIC PLACEHOLDER – NOT CLINICALLY APPROVED"
VERSION = "placeholder-1"
NOTE = "Placeholder only. Not clinical guidance. Replace with the doctor-approved template (D05)."

# (position, name, kind, timing_basis, offset_days)
ITEMS = [
    (1, "Placeholder contact A", "VISIT", "AT_PUBLISH", None),
    (2, "Placeholder follow-up call", "FOLLOW_UP", "DAYS_AFTER_PUBLISH", 7),
    (3, "Placeholder test request", "TEST_REQUEST", "DAYS_AFTER_PUBLISH", 14),
    (4, "Placeholder contact B", "VISIT", "DAYS_AFTER_PUBLISH", 28),
]


def main() -> None:
    if settings.env.strip().lower() == "production":
        raise SystemExit("Refusing to seed a placeholder clinical template in production.")
    engine = create_engine(settings.database_url_migrator)
    created = 0
    with engine.begin() as conn:
        org_ids = conn.execute(text("SELECT id FROM organization ORDER BY created_at")).scalars().all()
        for org_id in org_ids:
            exists = conn.execute(
                text("SELECT 1 FROM care_plan_template WHERE organization_id = :o AND name = :n AND version_label = :v"),
                {"o": org_id, "n": NAME, "v": VERSION},
            ).first()
            if exists:
                continue
            template_id = uuid.uuid4()
            conn.execute(
                text(
                    "INSERT INTO care_plan_template (id, organization_id, name, version_label, status, is_placeholder,"
                    " source_reference, created_at, updated_at)"
                    " VALUES (:id, :o, :n, :v, 'APPROVED', true, :src, now(), now())"
                ),
                {"id": template_id, "o": org_id, "n": NAME, "v": VERSION, "src": NOTE},
            )
            for position, name, kind, basis, offset in ITEMS:
                conn.execute(
                    text(
                        "INSERT INTO care_plan_template_item (id, template_id, position, name, kind, timing_basis,"
                        " offset_days, preparation_text, created_at, updated_at)"
                        " VALUES (:id, :t, :p, :name, :kind, :basis, :off, :prep, now(), now())"
                    ),
                    {
                        "id": uuid.uuid4(),
                        "t": template_id,
                        "p": position,
                        "name": name,
                        "kind": kind,
                        "basis": basis,
                        "off": offset,
                        "prep": NOTE,
                    },
                )
            created += 1
    engine.dispose()
    print(f"Placeholder template ensured for {len(org_ids)} organization(s); created {created}.")


if __name__ == "__main__":
    main()
