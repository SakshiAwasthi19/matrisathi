"""Phase 1 care API (W2-A3): dating, plan publishing, appointments, owned tasks.

Rules every endpoint follows:
- Facility scoping on every request (404 for missing or not yours, audited).
- Clinician-only actions check the caller's role at the record's facility
  (403, audited): confirming/correcting dating, publishing a plan.
- Updates carry `expected_version`; a stale version is a 409.
- Nothing computes clinical meaning. Unknown stays unknown; "overdue" is an
  administrative delay; pregnancy-week items wait for an approved rule (D05).
- Audit metadata holds ids, states and counts only: never names or dates.
"""

import uuid
from collections.abc import Mapping
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core.config import settings
from app.core.db import get_db
from app.core.deps import find_active_membership, get_current_staff, require_csrf_header, require_facility_membership
from app.domain.permissions import CLINICAL, DENIED_MESSAGE, Capability, has_capability
from app.domain.transitions import (
    APPOINTMENT_TRANSITIONS,
    CARE_PLAN_TRANSITIONS,
    TASK_TRANSITIONS,
    ClinicianOnlyError,
    StaleVersionError,
    TransitionError,
    check_transition,
    check_version,
)
from app.models.audit import AuditOutcome
from app.models.care import (
    Appointment,
    AppointmentStatus,
    CareItemKind,
    CarePlan,
    CarePlanStatus,
    CarePlanTemplate,
    CarePlanTemplateItem,
    CareTask,
    TaskKind,
    TaskOutcome,
    TaskStatus,
    TemplateStatus,
    TimingBasis,
)
from app.models.dating import DatingState, EpisodeDating
from app.models.facility import Facility
from app.models.identity import Person
from app.models.pregnancy import DatingSource, PregnancyEpisode, PregnancyEpisodeStatus
from app.models.staff import StaffMembership, StaffUser
from app.schemas.care import (
    AppointmentOut,
    AppointmentTransitionIn,
    CarePlanOut,
    DatingConfirmIn,
    DatingCorrectionIn,
    DatingHistoryOut,
    DatingIn,
    DatingOut,
    PublishPlanIn,
    RescheduleIn,
    RescheduleOut,
    TaskAssignIn,
    TaskAttemptIn,
    TaskCloseIn,
    TaskOut,
    TemplateItemOut,
    TemplateOut,
)
from app.services import audit_service

router = APIRouter(tags=["care"])

STALE = "This record was changed by someone else. Reload it and try again."
OPEN_TASK_STATES = (TaskStatus.NEW, TaskStatus.ASSIGNED, TaskStatus.AWAITING_PATIENT)
OPEN_APPOINTMENT_STATES = (AppointmentStatus.REQUESTED, AppointmentStatus.CONFIRMED)


# --- shared helpers --------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _local_tz() -> timezone:
    return timezone(timedelta(minutes=settings.local_utc_offset_minutes))


def _today() -> date:
    return _now().astimezone(_local_tz()).date()


def _start_of_local_day(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=_local_tz())


def _uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found") from None


def _audit(
    staff: StaffUser,
    action: str,
    entity_type: str,
    entity_id: object,
    result: AuditOutcome = AuditOutcome.SUCCESS,
    **metadata: object,
) -> None:
    audit_service.record_event(
        actor_staff_user_id=staff.id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        outcome=result,
        metadata={k: (v.value if isinstance(v, Enum) else v) for k, v in metadata.items()},
    )


def _membership_for(
    db: Session, staff: StaffUser, facility_id: uuid.UUID, action: str, entity_type: str, entity_id: object
) -> StaffMembership:
    try:
        return require_facility_membership(db, staff, facility_id)
    except HTTPException:
        _audit(staff, action, entity_type, entity_id, AuditOutcome.DENIED, reason="not_authorized")
        raise


def _episode(db: Session, staff: StaffUser, episode_id: str, action: str) -> tuple[PregnancyEpisode, StaffMembership]:
    episode = db.get(PregnancyEpisode, _uuid(episode_id))
    if episode is None:
        _audit(staff, action, "PregnancyEpisode", episode_id, AuditOutcome.DENIED, reason="not_found")
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    return episode, _membership_for(db, staff, episode.facility_id, action, "PregnancyEpisode", episode.id)


def _require_capability(
    staff: StaffUser, membership: StaffMembership, capability: Capability, action: str, entity_type: str, entity_id: object
) -> None:
    """Role check at the record's facility, from the role-capability table."""
    if not has_capability([membership.role.value], capability):
        reason = "clinician_only" if capability in CLINICAL else "role_not_permitted"
        _audit(staff, action, entity_type, entity_id, AuditOutcome.DENIED, reason=reason, capability=capability)
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=DENIED_MESSAGE[capability])


def _transition(
    table: Mapping[Enum, frozenset[Enum]],
    current: Enum,
    target: Enum,
    membership: StaffMembership,
    staff: StaffUser,
    action: str,
    entity_type: str,
    entity_id: object,
) -> None:
    try:
        check_transition(table, current, target, [membership.role.value])
    except ClinicianOnlyError:
        _audit(staff, action, entity_type, entity_id, AuditOutcome.DENIED, reason="clinician_only")
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Only a clinician can do this.") from None
    except TransitionError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail=f"Cannot change from {current.value} to {target.value}."
        ) from None


def _version(current: int, expected: int) -> None:
    try:
        check_version(current, expected)
    except StaleVersionError:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=STALE) from None


def _commit(db: Session) -> None:
    """Commit, turning a concurrent-update or uniqueness race into a 409."""
    try:
        db.commit()
    except (StaleDataError, IntegrityError):
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail=STALE) from None


def _name(db: Session, staff_user_id: uuid.UUID | None) -> str | None:
    if staff_user_id is None:
        return None
    user = db.get(StaffUser, staff_user_id)
    return user.full_name if user else None


# --- Dating -------------------------------------------------------------------------


def _current_dating(db: Session, episode_id: uuid.UUID) -> EpisodeDating | None:
    return db.execute(
        select(EpisodeDating).where(EpisodeDating.episode_id == episode_id, EpisodeDating.superseded_at.is_(None))
    ).scalar_one_or_none()


def _dating_out(db: Session, d: EpisodeDating) -> DatingOut:
    return DatingOut(
        id=str(d.id),
        lmp_date=d.lmp_date,
        edd=d.edd,
        precision=d.precision,
        evidence=d.evidence,
        state=d.state.value,
        recorded_by_name=_name(db, d.recorded_by_staff_user_id),
        confirmed_by_name=_name(db, d.confirmed_by_staff_user_id),
        confirmed_at=d.confirmed_at,
        superseded_at=d.superseded_at,
        created_at=d.created_at,
        version=d.version,
    )


def _sync_episode_summary(episode: PregnancyEpisode, dating: EpisodeDating | None) -> None:
    """Keeps the episode's summary fields in step with the current entry.
    PROVISIONAL maps to the older SELF_REPORTED value, meaning "not yet
    confirmed by a clinician", whatever the evidence was."""
    if dating is None:
        episode.dating_estimate = None
        episode.dating_source = DatingSource.UNKNOWN
        return
    episode.dating_estimate = dating.edd
    episode.dating_source = (
        DatingSource.CLINICIAN_CONFIRMED if dating.state is DatingState.CONFIRMED else DatingSource.SELF_REPORTED
    )


def _supersede_and_add(db: Session, old: EpisodeDating | None, new: EpisodeDating) -> None:
    if old is not None:
        old.superseded_at = _now()
        old.superseded_by_id = new.id
        db.flush()  # free the "one current entry" slot before inserting the new one
    db.add(new)
    db.flush()


@router.get("/pregnancy-episodes/{episode_id}/dating", response_model=DatingHistoryOut)
def get_dating(episode_id: str, db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)) -> DatingHistoryOut:
    episode, _ = _episode(db, staff, episode_id, "read_dating")
    rows = db.execute(
        select(EpisodeDating).where(EpisodeDating.episode_id == episode.id).order_by(EpisodeDating.created_at.desc())
    ).scalars().all()
    _audit(staff, "read_dating", "PregnancyEpisode", episode.id, count=len(rows))
    current = next((r for r in rows if r.superseded_at is None), None)
    return DatingHistoryOut(
        current=_dating_out(db, current) if current else None, history=[_dating_out(db, r) for r in rows]
    )


@router.post("/pregnancy-episodes/{episode_id}/dating", response_model=DatingOut, status_code=status.HTTP_201_CREATED)
def record_provisional_dating(
    episode_id: str,
    body: DatingIn,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
    _csrf: None = Depends(require_csrf_header),
) -> DatingOut:
    """Any member of the facility may record a provisional date."""
    episode, _ = _episode(db, staff, episode_id, "record_dating")
    current = _current_dating(db, episode.id)
    if current is not None and current.state is DatingState.CONFIRMED:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="A clinician has confirmed the dating. Only a clinician can correct it.",
        )
    new = EpisodeDating(
        id=uuid.uuid4(),
        episode_id=episode.id,
        facility_id=episode.facility_id,
        lmp_date=body.lmp_date,
        edd=body.edd,
        precision=body.precision,
        evidence=body.evidence,
        state=DatingState.PROVISIONAL,
        recorded_by_staff_user_id=staff.id,
    )
    _supersede_and_add(db, current, new)
    _sync_episode_summary(episode, new)
    _commit(db)
    _audit(staff, "record_dating", "EpisodeDating", new.id, state=DatingState.PROVISIONAL, evidence=body.evidence)
    return _dating_out(db, new)


@router.post("/pregnancy-episodes/{episode_id}/dating/confirm", response_model=DatingOut)
def confirm_dating(
    episode_id: str,
    body: DatingConfirmIn,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
    _csrf: None = Depends(require_csrf_header),
) -> DatingOut:
    """Clinician-only: confirm the current provisional entry as it stands."""
    episode, membership = _episode(db, staff, episode_id, "confirm_dating")
    _require_capability(staff, membership, Capability.CONFIRM_DATING, "confirm_dating", "PregnancyEpisode", episode.id)
    current = _current_dating(db, episode.id)
    if current is None or str(current.id) != body.dating_id:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=STALE)
    if current.state is DatingState.CONFIRMED:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="This dating is already confirmed.")
    _version(current.version, body.expected_version)
    current.state = DatingState.CONFIRMED
    current.confirmed_by_staff_user_id = staff.id
    current.confirmed_at = _now()
    _sync_episode_summary(episode, current)
    _commit(db)
    _audit(staff, "confirm_dating", "EpisodeDating", current.id)
    return _dating_out(db, current)


@router.post("/pregnancy-episodes/{episode_id}/dating/correct", response_model=DatingOut, status_code=status.HTTP_201_CREATED)
def correct_dating(
    episode_id: str,
    body: DatingCorrectionIn,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
    _csrf: None = Depends(require_csrf_header),
) -> DatingOut:
    """Clinician-only: record a confirmed date that replaces the current one.
    Past and attended items are never touched. Future, not-yet-attended items
    that were timed by pregnancy week are cancelled, and one review task asks
    the clinician to rebook them (no week rule is approved yet, D05)."""
    episode, membership = _episode(db, staff, episode_id, "correct_dating")
    _require_capability(staff, membership, Capability.CONFIRM_DATING, "correct_dating", "PregnancyEpisode", episode.id)
    current = _current_dating(db, episode.id)
    _version(current.version if current else 0, body.expected_version)
    new = EpisodeDating(
        id=uuid.uuid4(),
        episode_id=episode.id,
        facility_id=episode.facility_id,
        lmp_date=body.lmp_date,
        edd=body.edd,
        precision=body.precision,
        evidence=body.evidence,
        state=DatingState.CONFIRMED,
        recorded_by_staff_user_id=staff.id,
        confirmed_by_staff_user_id=staff.id,
        confirmed_at=_now(),
    )
    _supersede_and_add(db, current, new)
    _sync_episode_summary(episode, new)
    cancelled = _cancel_week_timed_future_items(db, episode, reason="DATING_CORRECTED")
    if cancelled:
        db.add(
            CareTask(
                episode_id=episode.id,
                facility_id=episode.facility_id,
                kind=TaskKind.REVIEW_WORK,
                status=TaskStatus.ASSIGNED,
                owner_staff_user_id=staff.id,
            )
        )
    _commit(db)
    _audit(staff, "correct_dating", "EpisodeDating", new.id, cancelled_items=cancelled)
    return _dating_out(db, new)


def _week_timed_item_ids(db: Session) -> Any:
    return select(CarePlanTemplateItem.id).where(CarePlanTemplateItem.timing_basis == TimingBasis.GESTATIONAL_WEEKS)


def _cancel_week_timed_future_items(db: Session, episode: PregnancyEpisode, reason: str) -> int:
    now, today = _now(), _today()
    week_items = _week_timed_item_ids(db)
    appointments = db.execute(
        select(Appointment).where(
            Appointment.episode_id == episode.id,
            Appointment.status.in_(OPEN_APPOINTMENT_STATES),
            Appointment.template_item_id.in_(week_items),
            or_(Appointment.confirmed_for >= now, Appointment.requested_for >= today, Appointment.requested_for.is_(None)),
        )
    ).scalars().all()
    for a in appointments:
        a.status = AppointmentStatus.CANCELLED
        a.status_reason = reason
    tasks = db.execute(
        select(CareTask).where(
            CareTask.episode_id == episode.id,
            CareTask.status.in_(OPEN_TASK_STATES),
            CareTask.template_item_id.in_(week_items),
        )
    ).scalars().all()
    for t in tasks:
        _close_task(t, TaskOutcome.NOT_NEEDED, "NO_LONGER_NEEDED")
    return len(appointments) + len(tasks)


# --- Templates and plans ----------------------------------------------------------


def _template_out(db: Session, t: CarePlanTemplate) -> TemplateOut:
    items = db.execute(
        select(CarePlanTemplateItem).where(CarePlanTemplateItem.template_id == t.id).order_by(CarePlanTemplateItem.position)
    ).scalars().all()
    return TemplateOut(
        id=str(t.id),
        name=t.name,
        version_label=t.version_label,
        is_placeholder=t.is_placeholder,
        approved_by_name=t.approved_by_name,
        approved_on=t.approved_on,
        items=[
            TemplateItemOut(
                id=str(i.id),
                position=i.position,
                name=i.name,
                kind=i.kind.value,
                timing_basis=i.timing_basis.value,
                offset_days=i.offset_days,
                week_from=i.week_from,
                week_to=i.week_to,
                performer_role=i.performer_role,
                preparation_text=i.preparation_text,
            )
            for i in items
        ],
    )


def _plan_out(db: Session, plan: CarePlan, unscheduled: list[str] | None = None) -> CarePlanOut:
    template = db.get(CarePlanTemplate, plan.template_id)
    assert template is not None
    return CarePlanOut(
        id=str(plan.id),
        episode_id=str(plan.episode_id),
        template=_template_out(db, template),
        status=plan.status.value,
        published_by_name=_name(db, plan.published_by_staff_user_id),
        published_at=plan.published_at,
        version=plan.version,
        unscheduled_item_names=unscheduled or [],
    )


def _organization_ids(db: Session, staff: StaffUser) -> list[uuid.UUID]:
    rows = db.execute(
        select(Facility.organization_id)
        .join(StaffMembership, StaffMembership.facility_id == Facility.id)
        .where(
            StaffMembership.staff_user_id == staff.id,
            StaffMembership.active.is_(True),
            StaffMembership.revoked_at.is_(None),
        )
    ).scalars().all()
    return list(set(rows))


@router.get("/care-plan-templates", response_model=list[TemplateOut])
def list_templates(db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)) -> list[TemplateOut]:
    org_ids = _organization_ids(db, staff)
    templates = db.execute(
        select(CarePlanTemplate)
        .where(CarePlanTemplate.organization_id.in_(org_ids), CarePlanTemplate.status == TemplateStatus.APPROVED)
        .order_by(CarePlanTemplate.is_placeholder, CarePlanTemplate.name)
    ).scalars().all()
    return [_template_out(db, t) for t in templates]


def _active_plan(db: Session, episode_id: uuid.UUID) -> CarePlan | None:
    return db.execute(
        select(CarePlan).where(CarePlan.episode_id == episode_id, CarePlan.status == CarePlanStatus.ACTIVE)
    ).scalar_one_or_none()


@router.get("/pregnancy-episodes/{episode_id}/care-plan", response_model=CarePlanOut | None)
def get_care_plan(episode_id: str, db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)) -> CarePlanOut | None:
    episode, _ = _episode(db, staff, episode_id, "read_care_plan")
    plan = _active_plan(db, episode.id)
    _audit(staff, "read_care_plan", "PregnancyEpisode", episode.id, has_plan=plan is not None)
    return _plan_out(db, plan) if plan else None


@router.post("/pregnancy-episodes/{episode_id}/care-plan", response_model=CarePlanOut, status_code=status.HTTP_201_CREATED)
def publish_care_plan(
    episode_id: str,
    body: PublishPlanIn,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
    _csrf: None = Depends(require_csrf_header),
) -> CarePlanOut:
    """Clinician-only. Creates the plan's future appointments (as requests)
    and tasks from an approved template version. Publishing a different
    template supersedes the active plan: its future, not-yet-attended items
    are cancelled; past and attended items are kept."""
    episode, membership = _episode(db, staff, episode_id, "publish_care_plan")
    _require_capability(staff, membership, Capability.PUBLISH_CARE_PLAN, "publish_care_plan", "PregnancyEpisode", episode.id)
    if episode.status is not PregnancyEpisodeStatus.ACTIVE:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="This pregnancy episode is not active.")

    template = db.get(CarePlanTemplate, _uuid(body.template_id))
    facility = db.get(Facility, episode.facility_id)
    if (
        template is None
        or facility is None
        or template.organization_id != facility.organization_id
        or template.status is not TemplateStatus.APPROVED
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")

    old = _active_plan(db, episode.id)
    if old is not None:
        if old.template_id == template.id:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="This plan is already published for her.")
        _transition(CARE_PLAN_TRANSITIONS, old.status, CarePlanStatus.SUPERSEDED, membership, staff, "publish_care_plan", "CarePlan", old.id)
        old.status = CarePlanStatus.SUPERSEDED
        _cancel_future_plan_items(db, old, reason="PLAN_SUPERSEDED")
        db.flush()

    now, today = _now(), _today()
    plan = CarePlan(
        episode_id=episode.id,
        facility_id=episode.facility_id,
        template_id=template.id,
        status=CarePlanStatus.ACTIVE,
        published_by_staff_user_id=staff.id,
        published_at=now,
    )
    db.add(plan)
    db.flush()

    unscheduled: list[str] = []
    items = db.execute(
        select(CarePlanTemplateItem).where(CarePlanTemplateItem.template_id == template.id).order_by(CarePlanTemplateItem.position)
    ).scalars().all()
    for item in items:
        if item.timing_basis is TimingBasis.GESTATIONAL_WEEKS:
            unscheduled.append(item.name)  # waits for an approved week rule (D05)
            continue
        due = today + timedelta(days=item.offset_days or 0)
        if item.kind is CareItemKind.VISIT:
            db.add(
                Appointment(
                    episode_id=episode.id,
                    facility_id=episode.facility_id,
                    care_plan_id=plan.id,
                    template_item_id=item.id,
                    status=AppointmentStatus.REQUESTED,
                    requested_for=due,
                )
            )
        else:
            db.add(
                CareTask(
                    episode_id=episode.id,
                    facility_id=episode.facility_id,
                    care_plan_id=plan.id,
                    template_item_id=item.id,
                    kind=TaskKind.PLAN_ITEM,
                    status=TaskStatus.NEW,
                    due_at=_start_of_local_day(due),
                )
            )
    _commit(db)
    _audit(
        staff,
        "publish_care_plan",
        "CarePlan",
        plan.id,
        template_id=str(template.id),
        placeholder=template.is_placeholder,
        superseded=str(old.id) if old else None,
        unscheduled=len(unscheduled),
    )
    return _plan_out(db, plan, unscheduled)


def _cancel_future_plan_items(db: Session, plan: CarePlan, reason: str) -> None:
    now, today = _now(), _today()
    for a in db.execute(
        select(Appointment).where(
            Appointment.care_plan_id == plan.id,
            Appointment.status.in_(OPEN_APPOINTMENT_STATES),
            or_(Appointment.confirmed_for >= now, Appointment.requested_for >= today, Appointment.requested_for.is_(None)),
        )
    ).scalars():
        a.status = AppointmentStatus.CANCELLED
        a.status_reason = reason
    for t in db.execute(
        select(CareTask).where(CareTask.care_plan_id == plan.id, CareTask.status.in_(OPEN_TASK_STATES))
    ).scalars():
        _close_task(t, TaskOutcome.NOT_NEEDED, "NO_LONGER_NEEDED")


# --- Appointments ---------------------------------------------------------------------


def _item_name(db: Session, item_id: uuid.UUID | None) -> str | None:
    if item_id is None:
        return None
    item = db.get(CarePlanTemplateItem, item_id)
    return item.name if item else None


def _appointment_out(db: Session, a: Appointment) -> AppointmentOut:
    return AppointmentOut(
        id=str(a.id),
        episode_id=str(a.episode_id),
        care_plan_id=str(a.care_plan_id) if a.care_plan_id else None,
        name=_item_name(db, a.template_item_id),
        status=a.status,
        requested_for=a.requested_for,
        confirmed_for=a.confirmed_for,
        location_note=a.location_note,
        owner_staff_user_id=str(a.owner_staff_user_id) if a.owner_staff_user_id else None,
        previous_appointment_id=str(a.previous_appointment_id) if a.previous_appointment_id else None,
        status_reason=a.status_reason,
        version=a.version,
    )


@router.get("/pregnancy-episodes/{episode_id}/appointments", response_model=list[AppointmentOut])
def list_appointments(episode_id: str, db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)) -> list[AppointmentOut]:
    episode, _ = _episode(db, staff, episode_id, "list_appointments")
    rows = db.execute(
        select(Appointment)
        .where(Appointment.episode_id == episode.id)
        .order_by(Appointment.requested_for.asc().nulls_last(), Appointment.created_at)
    ).scalars().all()
    _audit(staff, "list_appointments", "PregnancyEpisode", episode.id, count=len(rows))
    return [_appointment_out(db, a) for a in rows]


def _appointment(db: Session, staff: StaffUser, appointment_id: str, action: str) -> tuple[Appointment, StaffMembership]:
    a = db.get(Appointment, _uuid(appointment_id))
    if a is None:
        _audit(staff, action, "Appointment", appointment_id, AuditOutcome.DENIED, reason="not_found")
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    return a, _membership_for(db, staff, a.facility_id, action, "Appointment", a.id)


@router.post("/appointments/{appointment_id}/transition", response_model=AppointmentOut)
def transition_appointment(
    appointment_id: str,
    body: AppointmentTransitionIn,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
    _csrf: None = Depends(require_csrf_header),
) -> AppointmentOut:
    a, membership = _appointment(db, staff, appointment_id, "transition_appointment")
    _version(a.version, body.expected_version)
    target = AppointmentStatus(body.to)
    previous = a.status
    _transition(APPOINTMENT_TRANSITIONS, previous, target, membership, staff, "transition_appointment", "Appointment", a.id)
    a.status = target
    a.status_reason = body.reason
    if target is AppointmentStatus.CONFIRMED:
        a.confirmed_for = body.confirmed_for
        a.location_note = body.location_note
    follow_up = None
    if target is AppointmentStatus.MISSED:
        # Exactly one owned follow-up (also enforced by a unique index).
        follow_up = CareTask(
            episode_id=a.episode_id,
            facility_id=a.facility_id,
            care_plan_id=a.care_plan_id,
            kind=TaskKind.FOLLOW_UP_MISSED_VISIT,
            status=TaskStatus.ASSIGNED,
            owner_staff_user_id=a.owner_staff_user_id or staff.id,
            source_appointment_id=a.id,
        )
        db.add(follow_up)
    _commit(db)
    _audit(
        staff,
        "transition_appointment",
        "Appointment",
        a.id,
        from_state=previous,
        to_state=target,
        follow_up_task=str(follow_up.id) if follow_up else None,
    )
    return _appointment_out(db, a)


@router.post("/appointments/{appointment_id}/reschedule", response_model=RescheduleOut, status_code=status.HTTP_201_CREATED)
def reschedule_appointment(
    appointment_id: str,
    body: RescheduleIn,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
    _csrf: None = Depends(require_csrf_header),
) -> RescheduleOut:
    """Makes a new requested appointment linked to the old one. A confirmed
    appointment becomes RESCHEDULED; a missed one stays MISSED. Each
    appointment can be rescheduled once (unique link), so only the newest
    one is ever current."""
    a, membership = _appointment(db, staff, appointment_id, "reschedule_appointment")
    _version(a.version, body.expected_version)
    if a.status is AppointmentStatus.CONFIRMED:
        _transition(APPOINTMENT_TRANSITIONS, a.status, AppointmentStatus.RESCHEDULED, membership, staff, "reschedule_appointment", "Appointment", a.id)
        a.status = AppointmentStatus.RESCHEDULED
        a.status_reason = body.reason
    elif a.status is not AppointmentStatus.MISSED:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail=f"A {a.status.value} appointment cannot be rescheduled."
        )
    db.flush()
    new = Appointment(
        episode_id=a.episode_id,
        facility_id=a.facility_id,
        care_plan_id=a.care_plan_id,
        template_item_id=a.template_item_id,
        status=AppointmentStatus.REQUESTED,
        requested_for=body.requested_for,
        owner_staff_user_id=a.owner_staff_user_id,
        previous_appointment_id=a.id,
    )
    db.add(new)
    _commit(db)
    _audit(staff, "reschedule_appointment", "Appointment", a.id, new_appointment=str(new.id))
    return RescheduleOut(previous=_appointment_out(db, a), new=_appointment_out(db, new))


# --- Tasks ------------------------------------------------------------------------------


def _close_task(t: CareTask, outcome: TaskOutcome, reason: str) -> None:
    t.status = TaskStatus.CANCELLED if outcome is TaskOutcome.NOT_NEEDED else TaskStatus.COMPLETED
    t.outcome = outcome
    t.closure_reason = reason
    t.closed_at = _now()


def _task_out(db: Session, t: CareTask) -> TaskOut:
    episode = db.get(PregnancyEpisode, t.episode_id)
    mother = db.get(Person, episode.mother_person_id) if episode else None
    open_ = t.status in OPEN_TASK_STATES
    return TaskOut(
        id=str(t.id),
        episode_id=str(t.episode_id),
        mother_full_name=mother.full_name if mother else "",
        name=_item_name(db, t.template_item_id),
        kind=t.kind.value,
        status=t.status.value,
        owner_staff_user_id=str(t.owner_staff_user_id) if t.owner_staff_user_id else None,
        owner_name=_name(db, t.owner_staff_user_id),
        backup_staff_user_id=str(t.backup_staff_user_id) if t.backup_staff_user_id else None,
        due_at=t.due_at,
        overdue=bool(open_ and t.due_at is not None and t.due_at < _now()),
        source_appointment_id=str(t.source_appointment_id) if t.source_appointment_id else None,
        last_attempt_at=t.last_attempt_at,
        barrier=t.barrier,
        outcome=t.outcome.value if t.outcome else None,
        closure_reason=t.closure_reason,
        closed_at=t.closed_at,
        version=t.version,
    )


def _caller_facility_ids(db: Session, staff: StaffUser) -> list[uuid.UUID]:
    return list(
        db.execute(
            select(StaffMembership.facility_id).where(
                StaffMembership.staff_user_id == staff.id,
                StaffMembership.active.is_(True),
                StaffMembership.revoked_at.is_(None),
            )
        ).scalars()
    )


@router.get("/tasks", response_model=list[TaskOut])
def list_tasks(
    mine: bool = Query(default=False, description="Only tasks I own or back up"),
    include_closed: bool = Query(default=False),
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
) -> list[TaskOut]:
    """The facility worklist (Today view). Scoped to the caller's facilities."""
    query = select(CareTask).where(CareTask.facility_id.in_(_caller_facility_ids(db, staff)))
    if mine:
        query = query.where(or_(CareTask.owner_staff_user_id == staff.id, CareTask.backup_staff_user_id == staff.id))
    if not include_closed:
        query = query.where(CareTask.status.in_(OPEN_TASK_STATES))
    rows = db.execute(query.order_by(CareTask.due_at.asc().nulls_last(), CareTask.created_at).limit(200)).scalars().all()
    _audit(staff, "list_tasks", "CareTask", None, count=len(rows), mine=mine)
    return [_task_out(db, t) for t in rows]


@router.get("/pregnancy-episodes/{episode_id}/tasks", response_model=list[TaskOut])
def list_episode_tasks(episode_id: str, db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)) -> list[TaskOut]:
    episode, _ = _episode(db, staff, episode_id, "list_tasks")
    rows = db.execute(
        select(CareTask).where(CareTask.episode_id == episode.id).order_by(CareTask.due_at.asc().nulls_last(), CareTask.created_at)
    ).scalars().all()
    _audit(staff, "list_tasks", "PregnancyEpisode", episode.id, count=len(rows))
    return [_task_out(db, t) for t in rows]


def _task(db: Session, staff: StaffUser, task_id: str, action: str) -> tuple[CareTask, StaffMembership]:
    t = db.get(CareTask, _uuid(task_id))
    if t is None:
        _audit(staff, action, "CareTask", task_id, AuditOutcome.DENIED, reason="not_found")
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    return t, _membership_for(db, staff, t.facility_id, action, "CareTask", t.id)


@router.post("/tasks/{task_id}/assign", response_model=TaskOut)
def assign_task(
    task_id: str,
    body: TaskAssignIn,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
    _csrf: None = Depends(require_csrf_header),
) -> TaskOut:
    t, membership = _task(db, staff, task_id, "assign_task")
    _version(t.version, body.expected_version)
    owner_id = _uuid(body.owner_staff_user_id)
    backup_id = _uuid(body.backup_staff_user_id) if body.backup_staff_user_id else None
    for person_id in filter(None, (owner_id, backup_id)):
        if find_active_membership(db, person_id, t.facility_id) is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Owner and backup must work at this facility.")
    if backup_id is not None and backup_id == owner_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The backup must be a different person.")
    _transition(TASK_TRANSITIONS, t.status, TaskStatus.ASSIGNED, membership, staff, "assign_task", "CareTask", t.id)
    t.status = TaskStatus.ASSIGNED
    t.owner_staff_user_id = owner_id
    t.backup_staff_user_id = backup_id
    _commit(db)
    _audit(staff, "assign_task", "CareTask", t.id, owner=str(owner_id), backup=str(backup_id) if backup_id else None)
    return _task_out(db, t)


@router.post("/tasks/{task_id}/attempt", response_model=TaskOut)
def record_task_attempt(
    task_id: str,
    body: TaskAttemptIn,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
    _csrf: None = Depends(require_csrf_header),
) -> TaskOut:
    t, membership = _task(db, staff, task_id, "task_attempt")
    _version(t.version, body.expected_version)
    if t.status not in (TaskStatus.ASSIGNED, TaskStatus.AWAITING_PATIENT):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Assign the task before recording an attempt.")
    target = TaskStatus.AWAITING_PATIENT if body.awaiting_patient else TaskStatus.ASSIGNED
    if target is not t.status:
        _transition(TASK_TRANSITIONS, t.status, target, membership, staff, "task_attempt", "CareTask", t.id)
        t.status = target
    t.last_attempt_at = _now()
    t.barrier = body.barrier
    _commit(db)
    _audit(staff, "task_attempt", "CareTask", t.id, barrier=body.barrier, awaiting_patient=body.awaiting_patient)
    return _task_out(db, t)


@router.post("/tasks/{task_id}/close", response_model=TaskOut)
def close_task(
    task_id: str,
    body: TaskCloseIn,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
    _csrf: None = Depends(require_csrf_header),
) -> TaskOut:
    t, membership = _task(db, staff, task_id, "close_task")
    _version(t.version, body.expected_version)
    target = TaskStatus.CANCELLED if body.outcome is TaskOutcome.NOT_NEEDED else TaskStatus.COMPLETED
    _transition(TASK_TRANSITIONS, t.status, target, membership, staff, "close_task", "CareTask", t.id)
    _close_task(t, body.outcome, body.closure_reason)
    _commit(db)
    _audit(staff, "close_task", "CareTask", t.id, outcome=body.outcome, reason=body.closure_reason)
    return _task_out(db, t)
