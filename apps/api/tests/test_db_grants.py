"""The app role's rights on every table, exactly (Phase 1 plan section 5).

A new table fails this test until it is listed here with its intended
rights, so a forgotten or excessive grant cannot slip through (as F8 did).
"""

import os

import psycopg

RW = {"SELECT", "INSERT", "UPDATE", "DELETE"}
NO_DELETE = {"SELECT", "INSERT", "UPDATE"}
APPEND_ONLY = {"SELECT", "INSERT"}
NONE: set[str] = set()

READ_ONLY = {"SELECT"}
INSERT_ONLY = {"SELECT", "INSERT"}

EXPECTED: dict[str, set[str]] = {
    "alembic_version": NONE,  # F8: migrator only
    "appointment": NO_DELETE,
    "care_plan": NO_DELETE,
    "care_plan_template": READ_ONLY,  # clinical templates: never edited by the app
    "care_plan_template_item": READ_ONLY,
    "care_task": NO_DELETE,
    "file_object": INSERT_ONLY,  # a stored file record never changes
    "investigation": NO_DELETE,
    "local_contact": NO_DELETE,
    "observation": NO_DELETE,  # corrections supersede; the earlier value is kept
    "prescription": NO_DELETE,
    "referral": NO_DELETE,
    "audit_event": APPEND_ONLY,  # history cannot be changed
    "caregiver_grant": NO_DELETE,  # revoked, never deleted
    "contact_method": RW,
    "episode_dating": NO_DELETE,  # superseded, never deleted
    "facility": RW,
    "idempotency_key": RW,
    "login_attempt": RW,
    "organization": RW,
    "organization_admin": RW,
    "person": RW,
    "pregnancy_episode": RW,
    "refresh_token": RW,
    "staff_membership": RW,
    "staff_user": RW,
}


def test_app_role_has_exactly_the_intended_rights_on_every_table():
    url = os.environ["DATABASE_URL_MIGRATOR"].replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(url) as conn:
        tables = {r[0] for r in conn.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")}
        actual: dict[str, set[str]] = {t: set() for t in tables}
        for table, privilege in conn.execute(
            "SELECT table_name, privilege_type FROM information_schema.role_table_grants "
            "WHERE grantee = 'matrisathi_app' AND table_schema = 'public'"
        ):
            actual.setdefault(table, set()).add(privilege)

    unlisted = sorted(tables - EXPECTED.keys())
    assert not unlisted, f"new table(s) without an intended grant in this test: {unlisted}"
    wrong = {t: (sorted(actual.get(t, set())), sorted(EXPECTED[t])) for t in EXPECTED if actual.get(t, set()) != EXPECTED[t]}
    assert not wrong, f"app role rights differ (actual, expected): {wrong}"


def test_no_automatic_default_grants_to_the_app_role():
    """Migration b9d0e2a7c3f1: new tables get only explicitly granted rights."""
    url = os.environ["DATABASE_URL_MIGRATOR"].replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(url) as conn:
        rows = conn.execute(
            "SELECT defaclrole::regrole::text, defaclacl::text FROM pg_default_acl "
            "WHERE defaclacl::text LIKE '%matrisathi_app=%'"
        ).fetchall()
    assert rows == [], f"default privileges still grant to the app role: {rows}"
