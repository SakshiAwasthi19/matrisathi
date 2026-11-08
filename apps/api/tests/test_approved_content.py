"""D05 / M015: doctor-approved content is loaded from the filled-in packet,
never written by the app, and the public Urgent help page shows the wording
only once an approved version has taken effect."""

import copy
import json
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select

from app.main import app
from app.models.care import CarePlanTemplate, CarePlanTemplateItem
from app.models.content import UrgentHelpContent
from app.models.messaging import MessageTemplate
from app.scripts import load_approved_content as loader
from tests.factories import make_facility, make_org
from tests.messaging_helpers import migrator_session

TODAY = date.today()

SYNTHETIC = {
    "organization_name": "Synthetic Content Org",
    "approval": {"approved_by_name": "Synthetic Reviewer", "approved_by_role": "Doctor", "approved_on": str(TODAY)},
    "care_plan_template": {
        "name": "Synthetic ANC template",
        "version": "1.0",
        "source_reference": "SYNTHETIC TEST SOURCE",
        "effective_from": str(TODAY),
        "items": [
            {"name": "Synthetic first contact", "kind": "VISIT", "timing_basis": "AT_PUBLISH", "performer_role": "NURSE"},
            {"name": "Synthetic week item", "kind": "VISIT", "timing_basis": "GESTATIONAL_WEEKS", "week_from": 10, "week_to": 12},
            {"name": "Synthetic call", "kind": "FOLLOW_UP", "timing_basis": "DAYS_AFTER_PUBLISH", "offset_days": 7},
        ],
    },
    "urgent_help": {
        "version": "1.0",
        "heading": "Synthetic heading",
        "instruction_text": "Synthetic instruction.",
        "when_to_call_text": "Synthetic when-to-call wording.",
        "not_monitored_text": "Synthetic: messages are not watched for emergencies.",
        "support_hours_text": "Synthetic hours",
        "effective_from": str(TODAY),
    },
    "message_templates": [
        {
            "purpose": "APPOINTMENT_REMINDER",
            "language": "en",
            "detail_level": "MINIMAL",
            "version": "1.0",
            "provider_template_name": "synthetic_reminder",
            "body_text": "Synthetic reminder from {{1}} on {{2}}.",
            "variable_names": ["facility_name", "appointment_date"],
        }
    ],
}


def _content(**changes) -> loader.Content:  # type: ignore[no-untyped-def]
    data = copy.deepcopy(SYNTHETIC)
    for path, value in changes.items():
        target = data
        *parents, leaf = path.split("__")
        for p in parents:
            target = target[p] if not p.isdigit() else target[int(p)]
        target[leaf] = value
    return loader.Content.model_validate(data)


def _org_and_facility(db):  # type: ignore[no-untyped-def]
    org = make_org(db, "Synthetic Content Org")
    return org, make_facility(db, org, "Synthetic Content Facility")


@pytest.mark.parametrize(
    "change,message",
    [
        ({"approval__approved_by_name": ""}, "approved_by_name"),
        ({"care_plan_template__items__1__week_to": None}, "week_from <= week_to"),
        ({"care_plan_template__items__0__offset_days": 3}, "first contact"),
        ({"care_plan_template__items__0__performer_role": "SURGEON"}, "performer_role"),
        ({"message_templates__0__body_text": "Only one slot {{1}}."}, "slots"),
    ],
)
def test_the_packet_is_validated_before_anything_is_loaded(change, message):
    with pytest.raises(ValidationError) as err:
        _content(**change)
    assert message in str(err.value)


def test_dry_run_writes_nothing(db_session, tmp_path, capsys):
    _org_and_facility(db_session)
    path = tmp_path / "content.json"
    path.write_text(json.dumps(SYNTHETIC), encoding="utf-8")
    loader.main([str(path)])
    assert "Dry run" in capsys.readouterr().out
    with migrator_session() as s:
        assert s.execute(select(CarePlanTemplate).where(CarePlanTemplate.name == "Synthetic ANC template")).first() is None


def test_apply_loads_approved_versions_with_the_approver_and_refuses_duplicates(db_session, tmp_path):
    org, facility = _org_and_facility(db_session)
    path = tmp_path / "content.json"
    path.write_text(json.dumps(SYNTHETIC), encoding="utf-8")
    loader.main([str(path), "--apply"])
    with migrator_session() as s:
        tpl = s.execute(select(CarePlanTemplate).where(CarePlanTemplate.name == "Synthetic ANC template")).scalar_one()
        assert tpl.is_placeholder is False and tpl.approved_by_name == "Synthetic Reviewer (Doctor)"
        items = s.execute(select(CarePlanTemplateItem).where(CarePlanTemplateItem.template_id == tpl.id)).scalars().all()
        assert [i.position for i in items] == [1, 2, 3]
        assert s.execute(select(MessageTemplate).where(MessageTemplate.provider_template_name == "synthetic_reminder")).scalar_one()
    with pytest.raises(SystemExit) as dup:
        loader.main([str(path), "--apply"])
    assert "already exists" in str(dup.value)


def test_synthetic_demo_loads_as_a_placeholder(db_session, tmp_path):
    _org_and_facility(db_session)
    path = tmp_path / "content.json"
    path.write_text(json.dumps(SYNTHETIC), encoding="utf-8")
    loader.main([str(path), "--apply", "--synthetic-demo"])
    with migrator_session() as s:
        assert s.execute(select(CarePlanTemplate.is_placeholder).where(CarePlanTemplate.name == "Synthetic ANC template")).scalar_one()


def test_urgent_help_shows_wording_only_once_approved_and_in_effect(db_session):
    org, facility = _org_and_facility(db_session)
    anonymous = TestClient(app)
    before = anonymous.get(f"/api/v1/public/urgent-help/{facility.id}").json()
    assert before["wording_approved"] is False and before["wording"] is None

    future = _content(urgent_help__effective_from=str(TODAY + timedelta(days=5)), care_plan_template=None, message_templates=[])
    with migrator_session() as s:
        loader.load(future, s, synthetic=False)
        s.commit()
    assert anonymous.get(f"/api/v1/public/urgent-help/{facility.id}").json()["wording_approved"] is False

    current = _content(urgent_help__version="0.9", care_plan_template=None, message_templates=[])
    with migrator_session() as s:
        loader.load(current, s, synthetic=False)
        s.commit()
    body = anonymous.get(f"/api/v1/public/urgent-help/{facility.id}").json()
    assert body["wording_approved"] is True
    assert body["wording"]["heading"] == "Synthetic heading"
    assert body["wording"]["approved_by_name"] == "Synthetic Reviewer"
    assert body["support_hours"] == "Synthetic hours"


def test_the_app_role_cannot_write_approved_content(db_session):
    org, _ = _org_and_facility(db_session)
    from sqlalchemy.exc import ProgrammingError

    db_session.add(
        UrgentHelpContent(
            organization_id=org.id,
            version_label="x",
            status="DRAFT",
            heading="h",
            instruction_text="i",
            when_to_call_text="w",
            not_monitored_text="n",
        )
    )
    with pytest.raises(ProgrammingError):
        db_session.commit()
    db_session.rollback()
