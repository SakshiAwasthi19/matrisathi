"""Public, signed-out endpoints (W2-B3; F014).

GET /api/v1/public/urgent-help/{facility_id} returns only what the public
Urgent help page needs: the facility's name and its active, verified
service numbers. No patient data, no session, no location.

Wording comes only from a doctor-approved `urgent_help_content` version
that has taken effect (D05, loaded by app/scripts/load_approved_content.py).
Until one exists, `wording_approved` is false and the page shows the
verified numbers only, saying the wording is awaiting approval. Nothing is
ever invented here.
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routers.next_step import HELP_SERVICE_TYPES, _contact_out
from app.core.db import get_db
from app.api.routers.care import _today
from app.models.care import TemplateStatus
from app.models.content import UrgentHelpContent
from app.models.facility import Facility
from app.models.records import LocalContact
from app.schemas.next_step import HelpContactOut

router = APIRouter(prefix="/public", tags=["public"])


class ApprovedWording(BaseModel):
    heading: str
    instruction_text: str
    when_to_call_text: str
    not_monitored_text: str
    outside_hours_text: str | None
    version_label: str
    approved_by_name: str
    approved_by_role: str | None
    approved_on: date


class UrgentHelpOut(BaseModel):
    facility_name: str
    contacts: list[HelpContactOut]
    # From the approved wording; None until approved (F014).
    support_hours: str | None
    # False until the doctor approves the urgent-help wording (D05).
    wording_approved: bool
    wording: ApprovedWording | None = None


def approved_wording(db: Session, organization_id: uuid.UUID) -> UrgentHelpContent | None:
    return db.execute(
        select(UrgentHelpContent)
        .where(
            UrgentHelpContent.organization_id == organization_id,
            UrgentHelpContent.status == TemplateStatus.APPROVED,
            UrgentHelpContent.effective_from <= _today(),
        )
        .order_by(UrgentHelpContent.effective_from.desc(), UrgentHelpContent.approved_on.desc())
        .limit(1)
    ).scalar_one_or_none()


@router.get("/urgent-help/{facility_id}", response_model=UrgentHelpOut)
def urgent_help(facility_id: str, db: Session = Depends(get_db)) -> UrgentHelpOut:
    try:
        fid = uuid.UUID(facility_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found") from None
    facility = db.get(Facility, fid)
    if facility is None or not facility.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    contacts = db.execute(
        select(LocalContact)
        .where(
            LocalContact.facility_id == fid,
            LocalContact.active.is_(True),
            LocalContact.service_type.in_(HELP_SERVICE_TYPES),
        )
        .order_by(LocalContact.service_type, LocalContact.name)
    ).scalars().all()
    content = approved_wording(db, facility.organization_id)
    wording = (
        ApprovedWording(
            heading=content.heading,
            instruction_text=content.instruction_text,
            when_to_call_text=content.when_to_call_text,
            not_monitored_text=content.not_monitored_text,
            outside_hours_text=content.outside_hours_text,
            version_label=content.version_label,
            approved_by_name=content.approved_by_name or "",
            approved_by_role=content.approved_by_role,
            approved_on=content.approved_on or _today(),
        )
        if content is not None
        else None
    )
    return UrgentHelpOut(
        facility_name=facility.name,
        contacts=[c for c in (_contact_out(x) for x in contacts) if c is not None],
        support_hours=content.support_hours_text if content else None,
        wording_approved=content is not None,
        wording=wording,
    )
