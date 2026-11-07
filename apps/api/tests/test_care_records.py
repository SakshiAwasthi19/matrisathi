"""W2-A1 database rules for plans, appointments, tasks and investigations."""

import os
from datetime import datetime, timezone

import psycopg
import pytest
from sqlalchemy.exc import IntegrityError

from app.models.care import (
    CarePlan,
    CarePlanStatus,
    CarePlanTemplate,
    CarePlanTemplateItem,
    CareTask,
    CareItemKind,
    Investigation,
    InvestigationStatus,
    TaskKind,
    TaskOutcome,
    TaskStatus,
    TemplateStatus,
    TimingBasis,
)
from app.models.identity import Person
from app.models.pregnancy import PregnancyEpisode
from tests.factories import make_facility, make_org, make_staff

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)


def _migrator():
    return psycopg.connect(os.environ["DATABASE_URL_MIGRATOR"].replace("postgresql+psycopg://", "postgresql://"))


def _app():
    return psycopg.connect(
        os.environ["DATABASE_URL_APP"].replace("postgresql+psycopg://", "postgresql://"), autocommit=True
    )


@pytest.fixture
def world(db_session):
    org = make_org(db_session)
    facility = make_facility(db_session, org)
    staff = make_staff(db_session, "care_staff")
    person = Person(full_name="Synthetic Mother", registering_facility_id=facility.id)
    db_session.add(person)
    db_session.commit()
    episode = PregnancyEpisode(mother_person_id=person.id, facility_id=facility.id, created_by_staff_user_id=staff.id)
    db_session.add(episode)
    db_session.commit()
    # Templates are read-only for the app role: insert as the migrator.
    with _migrator() as conn:
        template_id = conn.execute(
            "INSERT INTO care_plan_template (id, organization_id, name, version_label, status, is_placeholder,"
            " created_at, updated_at) VALUES (gen_random_uuid(), %s, 'SYNTHETIC PLACEHOLDER', 'p1', 'APPROVED',"
            " true, now(), now()) RETURNING id",
            (org.id,),
        ).fetchone()[0]
    return {"org": org, "facility": facility, "staff": staff, "episode": episode, "template_id": template_id}


def test_app_role_cannot_write_templates(world):
    with _app() as conn:
        for sql in (
            "UPDATE care_plan_template SET name = 'changed'",
            "DELETE FROM care_plan_template",
            "INSERT INTO care_plan_template_item (id, template_id, position, name, kind, timing_basis,"
            " created_at, updated_at) VALUES (gen_random_uuid(), gen_random_uuid(), 1, 'x', 'VISIT', 'AT_PUBLISH', now(), now())",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(sql)


def test_approved_real_template_needs_a_recorded_approver(world):
    with _migrator() as conn:
        with pytest.raises(psycopg.errors.CheckViolation, match="ck_template_approval_recorded"):
            conn.execute(
                "INSERT INTO care_plan_template (id, organization_id, name, version_label, status, is_placeholder,"
                " created_at, updated_at) VALUES (gen_random_uuid(), %s, 'Real', 'v1', 'APPROVED', false, now(), now())",
                (world["org"].id,),
            )


@pytest.mark.parametrize(
    ("basis", "offset", "wfrom", "wto", "ok"),
    [
        ("AT_PUBLISH", None, None, None, True),
        ("DAYS_AFTER_PUBLISH", 14, None, None, True),
        ("GESTATIONAL_WEEKS", None, 10, 12, True),
        ("AT_PUBLISH", 3, None, None, False),
        ("DAYS_AFTER_PUBLISH", -1, None, None, False),
        ("GESTATIONAL_WEEKS", None, 12, 10, False),
        ("GESTATIONAL_WEEKS", None, None, None, False),
    ],
)
def test_template_item_timing_is_consistent(world, basis, offset, wfrom, wto, ok):
    with _migrator() as conn:
        sql = (
            "INSERT INTO care_plan_template_item (id, template_id, position, name, kind, timing_basis, offset_days,"
            " week_from, week_to, created_at, updated_at) VALUES (gen_random_uuid(), %s, 1, 'Placeholder contact',"
            " 'VISIT', %s, %s, %s, %s, now(), now())"
        )
        if ok:
            conn.execute(sql, (world["template_id"], basis, offset, wfrom, wto))
        else:
            with pytest.raises(psycopg.errors.CheckViolation, match="ck_template_item_timing"):
                conn.execute(sql, (world["template_id"], basis, offset, wfrom, wto))


def _plan(db, w, status=CarePlanStatus.ACTIVE):
    plan = CarePlan(
        episode_id=w["episode"].id,
        facility_id=w["facility"].id,
        template_id=w["template_id"],
        status=status,
        published_by_staff_user_id=w["staff"].id,
        published_at=NOW,
    )
    db.add(plan)
    db.commit()
    return plan


def test_one_active_plan_per_episode(db_session, world):
    first = _plan(db_session, world)
    assert first.version == 1
    with pytest.raises(IntegrityError, match="uq_care_plan_one_active_per_episode"):
        _plan(db_session, world)
    db_session.rollback()
    first.status = CarePlanStatus.SUPERSEDED
    db_session.commit()
    _plan(db_session, world)  # a new active plan once the old one is superseded


def _task(db, w, **kw):
    task = CareTask(episode_id=w["episode"].id, facility_id=w["facility"].id, kind=TaskKind.CONTACT, **kw)
    db.add(task)
    db.commit()
    return task


def test_assigned_task_must_have_an_owner(db_session, world):
    _task(db_session, world, status=TaskStatus.NEW)
    with pytest.raises(IntegrityError, match="ck_task_owned_once_assigned"):
        _task(db_session, world, status=TaskStatus.ASSIGNED)
    db_session.rollback()


def test_closed_task_must_record_outcome_and_time(db_session, world):
    with pytest.raises(IntegrityError, match="ck_task_closure_recorded"):
        _task(db_session, world, status=TaskStatus.COMPLETED, owner_staff_user_id=world["staff"].id)
    db_session.rollback()
    done = _task(
        db_session,
        world,
        status=TaskStatus.COMPLETED,
        owner_staff_user_id=world["staff"].id,
        outcome=TaskOutcome.UNREACHABLE,
        closed_at=NOW,
    )
    assert done.outcome is TaskOutcome.UNREACHABLE  # distinct from DONE and DECLINED


def test_reviewed_investigation_must_be_attributed(db_session, world):
    inv = Investigation(
        episode_id=world["episode"].id,
        facility_id=world["facility"].id,
        name="Placeholder test",
        status=InvestigationStatus.RECEIVED,
        received_at=NOW,
    )
    db_session.add(inv)
    db_session.commit()
    assert inv.requested_on is None and inv.performed_on is None  # unknown stays unknown

    inv.status = InvestigationStatus.REVIEWED  # no reviewer recorded
    with pytest.raises(IntegrityError, match="ck_investigation_review_attributed"):
        db_session.commit()
    db_session.rollback()


def test_app_role_cannot_delete_care_history(world):
    with _app() as conn:
        for table in ("care_plan", "appointment", "care_task", "investigation", "file_object"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(f"DELETE FROM {table}")


def test_models_cover_template_enums():
    # Guard against the placeholder ever using pregnancy weeks.
    assert {b.value for b in TimingBasis} == {"AT_PUBLISH", "DAYS_AFTER_PUBLISH", "GESTATIONAL_WEEKS"}
    assert CareItemKind.VISIT.value == "VISIT"
    assert TemplateStatus.APPROVED.value == "APPROVED"
    assert CarePlanTemplate.__tablename__ == "care_plan_template"
    assert CarePlanTemplateItem.__tablename__ == "care_plan_template_item"
