"""Loads the doctor-approved content from the filled-in D05 packet (D05, M015,
M023): the ANC care-plan template, the urgent-help wording, and the
WhatsApp message templates.

The doctor approves the content on paper or by email (docs/review/D05-...).
Someone on the team transcribes it, word for word, into a JSON file shaped
like docs/review/D05-approved-content.example.json, and runs this script.
The app itself can never create or edit this content: the app role only
reads these tables. This script writes through the migrator role.

Safety:
- Dry run by default: it validates and prints a summary. Add --apply to write.
- The approver's name, role and approval date are required.
- A version that already exists is refused (versions are never overwritten).
- --synthetic-demo loads the file as a labelled placeholder (for demos and
  tests). It is refused when ENV=production.
- Older approved versions stay in place (plans published from them keep
  them); the newest approved version is offered first.

Usage:
  uv run python -m app.scripts.load_approved_content path/to/content.json
  uv run python -m app.scripts.load_approved_content path/to/content.json --apply
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, model_validator
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.care import CareItemKind, CarePlanTemplate, CarePlanTemplateItem, TemplateStatus, TimingBasis
from app.models.content import UrgentHelpContent
from app.models.messaging import DetailLevel, MessagePurpose, MessageTemplate
from app.models.organization import Organization

ROLES = {"DOCTOR", "NURSE", "ANM", "COORDINATOR", "ASHA"}
_SLOT = re.compile(r"\{\{(\d+)\}\}")


class Approval(BaseModel):
    approved_by_name: str = Field(min_length=2, max_length=200)
    approved_by_role: str = Field(min_length=2, max_length=100)
    approved_on: date


class Item(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    kind: CareItemKind
    timing_basis: TimingBasis
    offset_days: int | None = Field(default=None, ge=0, le=400)
    week_from: int | None = Field(default=None, ge=1, le=45)
    week_to: int | None = Field(default=None, ge=1, le=45)
    performer_role: str | None = None
    preparation_text: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _timing(self) -> "Item":
        b = self.timing_basis
        if b is TimingBasis.AT_PUBLISH and (self.offset_days, self.week_from, self.week_to) != (None, None, None):
            raise ValueError(f"'{self.name}': 'at first contact' items take no days or weeks")
        if b is TimingBasis.DAYS_AFTER_PUBLISH and (self.offset_days is None or self.week_from or self.week_to):
            raise ValueError(f"'{self.name}': give offset_days only")
        if b is TimingBasis.GESTATIONAL_WEEKS and (
            self.offset_days is not None or self.week_from is None or self.week_to is None or self.week_from > self.week_to
        ):
            raise ValueError(f"'{self.name}': give week_from <= week_to only")
        if self.performer_role and self.performer_role not in ROLES:
            raise ValueError(f"'{self.name}': performer_role must be one of {sorted(ROLES)}")
        return self


class CareTemplate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    version: str = Field(min_length=1, max_length=50)
    source_reference: str = Field(min_length=2, max_length=300)
    effective_from: date
    items: list[Item] = Field(min_length=1)


class UrgentHelp(BaseModel):
    version: str = Field(min_length=1, max_length=50)
    heading: str = Field(min_length=2, max_length=200)
    instruction_text: str = Field(min_length=2)
    when_to_call_text: str = Field(min_length=2)
    not_monitored_text: str = Field(min_length=2)
    support_hours_text: str | None = Field(default=None, max_length=300)
    outside_hours_text: str | None = None
    effective_from: date


class Template(BaseModel):
    purpose: MessagePurpose
    language: str = Field(min_length=2, max_length=16)
    detail_level: DetailLevel
    version: str = Field(min_length=1, max_length=50)
    provider_template_name: str = Field(pattern=r"^[a-z0-9_]{1,100}$")
    body_text: str = Field(min_length=2, max_length=1024)
    variable_names: list[Literal["appointment_date", "appointment_time", "facility_name", "place"]] = []

    @model_validator(mode="after")
    def _slots(self) -> "Template":
        slots = sorted({int(n) for n in _SLOT.findall(self.body_text)})
        if slots != list(range(1, len(self.variable_names) + 1)):
            raise ValueError(
                f"'{self.provider_template_name}': the text has slots {slots} but "
                f"{len(self.variable_names)} variable name(s); they must match {{{{1}}}}..{{{{n}}}}"
            )
        return self


class Content(BaseModel):
    organization_name: str
    approval: Approval
    care_plan_template: CareTemplate | None = None
    urgent_help: UrgentHelp | None = None
    message_templates: list[Template] = []

    @model_validator(mode="after")
    def _something(self) -> "Content":
        if not (self.care_plan_template or self.urgent_help or self.message_templates):
            raise ValueError("the file contains no content to load")
        return self


def load(content: Content, db: Session, synthetic: bool) -> list[str]:
    """Adds the content to `db` (not committed). Returns a summary."""
    org = db.execute(select(Organization).where(Organization.name == content.organization_name)).scalar_one_or_none()
    if org is None:
        raise SystemExit(f"No organization is named {content.organization_name!r}.")
    a = content.approval
    out: list[str] = []
    if (t := content.care_plan_template) is not None:
        if db.execute(
            select(CarePlanTemplate).where(
                CarePlanTemplate.organization_id == org.id,
                CarePlanTemplate.name == t.name,
                CarePlanTemplate.version_label == t.version,
            )
        ).first():
            raise SystemExit(f"Care-plan template {t.name!r} version {t.version!r} already exists.")
        tpl = CarePlanTemplate(
            organization_id=org.id,
            name=t.name,
            version_label=t.version,
            status=TemplateStatus.APPROVED,
            is_placeholder=synthetic,
            source_reference=t.source_reference,
            approved_by_name=f"{a.approved_by_name} ({a.approved_by_role})",
            approved_on=a.approved_on,
            effective_from=t.effective_from,
        )
        db.add(tpl)
        db.flush()
        for pos, item in enumerate(t.items, start=1):
            db.add(
                CarePlanTemplateItem(
                    template_id=tpl.id,
                    position=pos,
                    name=item.name,
                    kind=item.kind,
                    timing_basis=item.timing_basis,
                    offset_days=item.offset_days,
                    week_from=item.week_from,
                    week_to=item.week_to,
                    performer_role=item.performer_role,
                    preparation_text=item.preparation_text,
                )
            )
        out.append(f"care-plan template {t.name!r} v{t.version}: {len(t.items)} item(s)")
    if (u := content.urgent_help) is not None:
        if db.execute(
            select(UrgentHelpContent).where(
                UrgentHelpContent.organization_id == org.id, UrgentHelpContent.version_label == u.version
            )
        ).first():
            raise SystemExit(f"Urgent-help wording version {u.version!r} already exists.")
        db.add(
            UrgentHelpContent(
                organization_id=org.id,
                version_label=u.version,
                status=TemplateStatus.APPROVED,
                heading=u.heading,
                instruction_text=u.instruction_text,
                when_to_call_text=u.when_to_call_text,
                not_monitored_text=u.not_monitored_text,
                support_hours_text=u.support_hours_text,
                outside_hours_text=u.outside_hours_text,
                approved_by_name=a.approved_by_name,
                approved_by_role=a.approved_by_role,
                approved_on=a.approved_on,
                effective_from=u.effective_from,
            )
        )
        out.append(f"urgent-help wording v{u.version}")
    for m in content.message_templates:
        if db.execute(
            select(MessageTemplate).where(
                MessageTemplate.organization_id == org.id,
                MessageTemplate.purpose == m.purpose,
                MessageTemplate.language == m.language,
                MessageTemplate.detail_level == m.detail_level,
                MessageTemplate.version_label == m.version,
            )
        ).first():
            raise SystemExit(f"Message template {m.provider_template_name!r} version {m.version!r} already exists.")
        db.add(
            MessageTemplate(
                organization_id=org.id,
                purpose=m.purpose,
                language=m.language,
                detail_level=m.detail_level,
                version_label=m.version,
                provider_template_name=m.provider_template_name,
                body_text=m.body_text,
                variable_names=list(m.variable_names),
                status=TemplateStatus.APPROVED,
                is_placeholder=synthetic,
                approved_by_name=f"{a.approved_by_name} ({a.approved_by_role})",
                approved_on=a.approved_on,
            )
        )
        out.append(f"message template {m.provider_template_name} ({m.purpose.value}, {m.language}, {m.detail_level.value})")
    return out


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("file", type=Path)
    parser.add_argument("--apply", action="store_true", help="write to the database (default: dry run)")
    parser.add_argument("--synthetic-demo", action="store_true", help="load as a labelled placeholder")
    args = parser.parse_args(argv)
    if args.synthetic_demo and settings.env.strip().lower() == "production":
        raise SystemExit("Refusing to load synthetic demo content in production.")
    try:
        content = Content.model_validate(json.loads(args.file.read_text(encoding="utf-8")))
    except (OSError, ValueError, ValidationError) as err:
        raise SystemExit(f"The file is not valid: {err}") from None
    engine = create_engine(settings.database_url_migrator)
    with Session(engine) as db:
        summary = load(content, db, synthetic=args.synthetic_demo)
        label = "SYNTHETIC DEMO (placeholder)" if args.synthetic_demo else "APPROVED"
        print(f"Approved by {content.approval.approved_by_name} ({content.approval.approved_by_role}) "
              f"on {content.approval.approved_on}. Loading as {label}:")
        for line in summary:
            print(f"  - {line}")
        if args.apply:
            db.commit()
            print("Written.")
        else:
            db.rollback()
            print("Dry run: nothing written. Add --apply to write.")
    engine.dispose()


if __name__ == "__main__":
    main(sys.argv[1:])
