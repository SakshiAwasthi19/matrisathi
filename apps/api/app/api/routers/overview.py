"""Overview summary: which active pregnancy records need attention, across the
caller's facilities. Feeds the role-specific panels on the staff home page.

Counts are administrative (what is waiting for whom), never clinical risk:
nothing here interprets a result, a value or a date. Each bucket counts
distinct ACTIVE pregnancy records and lists a few of them, oldest first,
so a panel can link straight to the record.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import ColumnElement, and_, exists, func, select
from sqlalchemy.orm import Session

from app.api.routers.care import _caller_facility_ids
from app.core.db import get_db
from app.core.deps import get_current_staff
from app.models.audit import AuditOutcome
from app.models.care import CarePlan, CarePlanStatus, Investigation, InvestigationStatus
from app.models.identity import ContactMethod, Person
from app.models.pregnancy import DatingSource, PregnancyEpisode, PregnancyEpisodeStatus
from app.models.records import InstructionStatus, Prescription, Referral, ReferralStatus
from app.models.staff import StaffUser
from app.services import audit_service

router = APIRouter(prefix="/overview", tags=["overview"])

RECORDS_PER_BUCKET = 5

# Referral steps after which nothing is waiting on staff.
_REFERRAL_DONE = (ReferralStatus.FOLLOW_UP_COMPLETED, ReferralStatus.CLOSED)


class RecordRef(BaseModel):
    episode_id: str
    mother_full_name: str


class Bucket(BaseModel):
    count: int
    records: list[RecordRef]


class OverviewSummary(BaseModel):
    reports_to_review: Bucket
    prescriptions_to_review: Bucket
    dating_not_confirmed: Bucket
    no_care_plan: Bucket
    contact_not_confirmed: Bucket
    referrals_in_progress: Bucket


def _conditions() -> dict[str, ColumnElement[bool]]:
    episode = PregnancyEpisode.id
    return {
        # A report has arrived and no clinician has reviewed it yet (AT08).
        "reports_to_review": exists().where(
            Investigation.episode_id == episode, Investigation.status == InvestigationStatus.RECEIVED
        ),
        # A prescription document is recorded but its instruction is not yet transcribed.
        "prescriptions_to_review": exists().where(
            Prescription.episode_id == episode, Prescription.instruction_status == InstructionStatus.UNREVIEWED
        ),
        # Unknown or provisional dating; a clinician has not confirmed it.
        "dating_not_confirmed": PregnancyEpisode.dating_source != DatingSource.CLINICIAN_CONFIRMED,
        "no_care_plan": ~exists().where(CarePlan.episode_id == episode, CarePlan.status == CarePlanStatus.ACTIVE),
        # No contact number for the mother has been confirmed with the family.
        "contact_not_confirmed": ~exists().where(
            ContactMethod.person_id == PregnancyEpisode.mother_person_id, ContactMethod.verified_at.is_not(None)
        ),
        "referrals_in_progress": exists().where(
            and_(Referral.episode_id == episode, Referral.status.not_in(_REFERRAL_DONE))
        ),
    }


@router.get("/summary", response_model=OverviewSummary)
def overview_summary(db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)) -> OverviewSummary:
    facility_ids = _caller_facility_ids(db, staff)
    base = (
        select(PregnancyEpisode.id, Person.full_name)
        .join(Person, Person.id == PregnancyEpisode.mother_person_id)
        .where(PregnancyEpisode.facility_id.in_(facility_ids), PregnancyEpisode.status == PregnancyEpisodeStatus.ACTIVE)
    )
    buckets: dict[str, Bucket] = {}
    for name, condition in _conditions().items():
        query = base.where(condition)
        count = db.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = db.execute(query.order_by(PregnancyEpisode.created_at, PregnancyEpisode.id).limit(RECORDS_PER_BUCKET)).all()
        buckets[name] = Bucket(count=count, records=[RecordRef(episode_id=str(r[0]), mother_full_name=r[1]) for r in rows])
    # Counts only in the audit metadata: no names.
    audit_service.record_event(
        actor_staff_user_id=staff.id,
        action="overview_summary",
        entity_type="Facility",
        entity_id=None,
        outcome=AuditOutcome.SUCCESS,
        metadata={k: b.count for k, b in buckets.items()},
    )
    return OverviewSummary(**buckets)
