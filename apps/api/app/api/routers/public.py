"""Public, signed-out endpoints (W2-B3; F014).

GET /api/v1/public/urgent-help/{facility_id} returns only what the public
Urgent help page needs: the facility's name and its active, verified
service numbers. No patient data, no session, no location.

It deliberately carries no instructions or wording: urgent-help text
must be approved by the doctor first (D05). Support hours are not
configured yet, and the page says so rather than inventing them.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routers.next_step import HELP_SERVICE_TYPES, _contact_out
from app.core.db import get_db
from app.models.facility import Facility
from app.models.records import LocalContact
from app.schemas.next_step import HelpContactOut

router = APIRouter(prefix="/public", tags=["public"])


class UrgentHelpOut(BaseModel):
    facility_name: str
    contacts: list[HelpContactOut]
    # Not configured yet; set once the facility confirms its hours (F014).
    support_hours: str | None
    # False until the doctor approves the urgent-help wording (D05).
    wording_approved: bool


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
    return UrgentHelpOut(
        facility_name=facility.name,
        contacts=[c for c in (_contact_out(x) for x in contacts) if c is not None],
        support_hours=None,
        wording_approved=False,
    )
