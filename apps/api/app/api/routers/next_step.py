"""Next action, birth plan and help requests (W2-A5; F006, F013, F044).

Staff-facing for now: patient and caregiver access waits for D07, so the
family's answers are recorded by staff on their behalf and stored apart
from staff verification. Nothing here infers adherence, urgency or risk.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.routers.care import (
    _audit,
    _commit,
    _episode,
    _membership_for,
    _name,
    _now,
    _today,
    _uuid,
    _version,
)
from app.api.routers.records import CONTACT_STALE_AFTER
from app.core.db import get_db
from app.core.deps import get_current_staff, require_csrf_header
from app.domain.permissions import Capability, has_capability
from app.models.audit import AuditOutcome
from app.models.birth_plan import AppointmentFamilyReport, BirthPlan, FamilyReport
from app.models.care import (
    Appointment,
    AppointmentStatus,
    CarePlanTemplate,
    CarePlanTemplateItem,
    CareTask,
    TaskKind,
    TaskStatus,
)
from app.models.pregnancy import PregnancyEpisode
from app.models.records import LocalContact, ServiceType
from app.models.staff import StaffUser
from app.schemas.next_step import (
    AppointmentFamilyReportIn,
    BirthPlanFamilyReportIn,
    BirthPlanIn,
    BirthPlanOut,
    BirthPlanVerifyIn,
    HelpContactOut,
    NextActionOut,
)

router = APIRouter(tags=["next-step"])

# Verified local services offered as the help route.
HELP_SERVICE_TYPES = (ServiceType.PHC, ServiceType.REFERRAL_HOSPITAL, ServiceType.TRANSPORT)


def _contact_out(c: LocalContact | None) -> HelpContactOut | None:
    if c is None:
        return None
    return HelpContactOut(
        id=str(c.id),
        service_type=c.service_type.value,
        name=c.name,
        phone=c.phone,
        alternate_phone=c.alternate_phone,
        landmarks=c.landmarks,
        verified_on=c.verified_on.isoformat(),
        stale=c.verified_on < _today() - CONTACT_STALE_AFTER,
    )


def _help_task(episode: PregnancyEpisode, staff: StaffUser, record_type: str, record_id: uuid.UUID, barrier: str | None) -> CareTask:
    """One owned task for staff to act on the family's request for help."""
    return CareTask(
        episode_id=episode.id,
        facility_id=episode.facility_id,
        kind=TaskKind.HELP_REQUEST,
        status=TaskStatus.ASSIGNED,
        owner_staff_user_id=staff.id,
        source_record_type=record_type,
        source_record_id=record_id,
        barrier=barrier,
    )


# --- Next action (F006) ------------------------------------------------------------


@router.get("/pregnancy-episodes/{episode_id}/next-action", response_model=NextActionOut)
def next_action(episode_id: str, db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)) -> NextActionOut:
    episode, _ = _episode(db, staff, episode_id, "read_next_action")
    nxt = db.execute(
        select(Appointment)
        .where(
            Appointment.episode_id == episode.id,
            Appointment.status == AppointmentStatus.CONFIRMED,
            Appointment.confirmed_for >= _now(),
        )
        .order_by(Appointment.confirmed_for)
        .limit(1)
    ).scalar_one_or_none()
    unconfirmed = db.execute(
        select(func.count()).select_from(Appointment).where(
            Appointment.episode_id == episode.id, Appointment.status == AppointmentStatus.REQUESTED
        )
    ).scalar_one()
    contacts = db.execute(
        select(LocalContact)
        .where(
            LocalContact.facility_id == episode.facility_id,
            LocalContact.active.is_(True),
            LocalContact.service_type.in_(HELP_SERVICE_TYPES),
        )
        .order_by(LocalContact.service_type, LocalContact.name)
    ).scalars().all()

    item = db.get(CarePlanTemplateItem, nxt.template_item_id) if nxt and nxt.template_item_id else None
    template = db.get(CarePlanTemplate, item.template_id) if item else None
    _audit(staff, "read_next_action", "PregnancyEpisode", episode.id, has_next=nxt is not None)
    return NextActionOut(
        state="CONFIRMED" if nxt else "NONE",
        appointment_id=str(nxt.id) if nxt else None,
        name=item.name if item else None,
        confirmed_for=nxt.confirmed_for if nxt else None,
        location_note=nxt.location_note if nxt else None,
        preparation_text=item.preparation_text if item else None,
        is_placeholder=bool(template and template.is_placeholder),
        family_report=nxt.family_report if nxt else None,
        family_reported_at=nxt.family_reported_at if nxt else None,
        unconfirmed_requests=unconfirmed,
        help_contacts=[c for c in (_contact_out(x) for x in contacts) if c is not None],
        version=nxt.version if nxt else None,
    )


@router.post("/appointments/{appointment_id}/family-report", response_model=NextActionOut)
def appointment_family_report(
    appointment_id: str,
    body: AppointmentFamilyReportIn,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
    _csrf: None = Depends(require_csrf_header),
) -> NextActionOut:
    """Records "done", "couldn't go" or "need help" as the family said it.
    This never changes the appointment's staff-recorded status. "Couldn't
    go" and "need help" open one owned help task."""
    a = db.get(Appointment, _uuid(appointment_id))
    if a is None:
        _audit(staff, "family_report", "Appointment", appointment_id, AuditOutcome.DENIED, reason="not_found")
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    _membership_for(db, staff, a.facility_id, "family_report", "Appointment", a.id)
    _version(a.version, body.expected_version)
    episode = db.get(PregnancyEpisode, a.episode_id)
    assert episode is not None
    a.family_report = body.report
    a.family_reported_at = _now()
    if body.report in (AppointmentFamilyReport.COULD_NOT_GO, AppointmentFamilyReport.NEED_HELP):
        db.add(_help_task(episode, staff, "APPOINTMENT", a.id, body.barrier))
    _commit(db)
    _audit(staff, "family_report", "Appointment", a.id, report=body.report, barrier=body.barrier)
    return next_action(str(episode.id), db, staff)


# --- Birth plan (F013) -------------------------------------------------------------


def _plan_out(db: Session, p: BirthPlan) -> BirthPlanOut:
    def contact(cid: uuid.UUID | None) -> HelpContactOut | None:
        return _contact_out(db.get(LocalContact, cid)) if cid else None

    return BirthPlanOut(
        id=str(p.id),
        episode_id=str(p.episode_id),
        chosen_birth_place=contact(p.chosen_birth_place_contact_id),
        chosen_birth_place_note=p.chosen_birth_place_note,
        referral_site=contact(p.referral_site_contact_id),
        referral_site_set_by_name=_name(db, p.referral_site_set_by_staff_user_id),
        companion_name=p.companion_name,
        transport_arrangement=p.transport_arrangement,
        landmarks=p.landmarks,
        primary_contact=contact(p.primary_contact_id),
        alternate_contact=contact(p.alternate_contact_id),
        family_report=p.family_report,
        family_reported_at=p.family_reported_at,
        staff_verified_by_name=_name(db, p.staff_verified_by_staff_user_id),
        staff_verified_at=p.staff_verified_at,
        updated_at=p.updated_at,
        version=p.version,
    )


def _birth_plan(db: Session, episode_id: uuid.UUID) -> BirthPlan | None:
    return db.execute(select(BirthPlan).where(BirthPlan.episode_id == episode_id)).scalar_one_or_none()


@router.get("/pregnancy-episodes/{episode_id}/birth-plan", response_model=BirthPlanOut | None)
def get_birth_plan(episode_id: str, db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)) -> BirthPlanOut | None:
    episode, _ = _episode(db, staff, episode_id, "read_birth_plan")
    plan = _birth_plan(db, episode.id)
    _audit(staff, "read_birth_plan", "PregnancyEpisode", episode.id, has_plan=plan is not None)
    return _plan_out(db, plan) if plan else None


@router.put("/pregnancy-episodes/{episode_id}/birth-plan", response_model=BirthPlanOut)
def save_birth_plan(
    episode_id: str,
    body: BirthPlanIn,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
    _csrf: None = Depends(require_csrf_header),
) -> BirthPlanOut:
    """Creates or replaces the plan's details. The referral site is
    clinician-only. Any change clears the staff verification, so a changed
    plan is never shown as verified."""
    episode, membership = _episode(db, staff, episode_id, "save_birth_plan")
    plan = _birth_plan(db, episode.id)
    _version(plan.version if plan else 0, body.expected_version)

    def facility_contact(cid: str | None) -> uuid.UUID | None:
        if not cid:
            return None
        c = db.get(LocalContact, _uuid(cid))
        if c is None or c.facility_id != episode.facility_id or not c.active:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Choose a verified contact from this facility.")
        return c.id

    referral_site = facility_contact(body.referral_site_contact_id)
    current_referral = plan.referral_site_contact_id if plan else None
    if referral_site != current_referral and not has_capability([membership.role.value], Capability.CHOOSE_REFERRAL_SITE):
        _audit(staff, "save_birth_plan", "PregnancyEpisode", episode.id, AuditOutcome.DENIED, reason="clinician_only")
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Only a clinician can choose the referral site.")

    if plan is None:
        plan = BirthPlan(episode_id=episode.id, facility_id=episode.facility_id)
        db.add(plan)
    plan.chosen_birth_place_contact_id = facility_contact(body.chosen_birth_place_contact_id)
    plan.chosen_birth_place_note = (body.chosen_birth_place_note or "").strip() or None
    if referral_site != current_referral:
        plan.referral_site_contact_id = referral_site
        plan.referral_site_set_by_staff_user_id = staff.id if referral_site else None
    plan.companion_name = (body.companion_name or "").strip() or None
    plan.transport_arrangement = (body.transport_arrangement or "").strip() or None
    plan.landmarks = (body.landmarks or "").strip() or None
    plan.primary_contact_id = facility_contact(body.primary_contact_id)
    plan.alternate_contact_id = facility_contact(body.alternate_contact_id)
    plan.staff_verified_at = None
    plan.staff_verified_by_staff_user_id = None
    _commit(db)
    _audit(staff, "save_birth_plan", "BirthPlan", plan.id)
    return _plan_out(db, plan)


@router.post("/pregnancy-episodes/{episode_id}/birth-plan/verify", response_model=BirthPlanOut)
def verify_birth_plan(
    episode_id: str,
    body: BirthPlanVerifyIn,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
    _csrf: None = Depends(require_csrf_header),
) -> BirthPlanOut:
    """Staff confirm they went through the plan with the family."""
    episode, _ = _episode(db, staff, episode_id, "verify_birth_plan")
    plan = _birth_plan(db, episode.id)
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    _version(plan.version, body.expected_version)
    plan.staff_verified_at = _now()
    plan.staff_verified_by_staff_user_id = staff.id
    _commit(db)
    _audit(staff, "verify_birth_plan", "BirthPlan", plan.id)
    return _plan_out(db, plan)


@router.post("/pregnancy-episodes/{episode_id}/birth-plan/family-report", response_model=BirthPlanOut)
def birth_plan_family_report(
    episode_id: str,
    body: BirthPlanFamilyReportIn,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
    _csrf: None = Depends(require_csrf_header),
) -> BirthPlanOut:
    """What the family said about their preparations. Stored apart from
    staff verification. "Need help" opens one owned help task."""
    episode, _ = _episode(db, staff, episode_id, "birth_plan_family_report")
    plan = _birth_plan(db, episode.id)
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    _version(plan.version, body.expected_version)
    plan.family_report = body.report
    plan.family_reported_at = _now()
    if body.report is FamilyReport.NEED_HELP:
        db.add(_help_task(episode, staff, "BIRTH_PLAN", plan.id, body.barrier))
    _commit(db)
    _audit(staff, "birth_plan_family_report", "BirthPlan", plan.id, report=body.report, barrier=body.barrier)
    return _plan_out(db, plan)
