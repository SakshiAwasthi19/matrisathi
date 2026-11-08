"""Phase 1 records API (W2-A4): reports, prescriptions, observations,
referrals and verified local contacts.

Same rules as the care API (app/api/routers/care.py, whose helpers this
reuses): facility scoping with audited 404s, clinician-only actions with
audited 403s, expected_version on every update, audit metadata without
names, dates or clinical text. Nothing here interprets a value.
"""

import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routers.care import (
    _audit,
    _commit,
    _episode,
    _membership_for,
    _name,
    _now,
    _require_capability,
    _today,
    _transition,
    _uuid,
    _version,
)
from app.core.db import get_db
from app.core.deps import find_active_membership, get_current_staff, require_csrf_header
from app.domain.permissions import Capability
from app.domain.transitions import INVESTIGATION_TRANSITIONS, REFERRAL_TRANSITIONS
from app.models.audit import AuditOutcome
from app.models.care import CareTask, Investigation, InvestigationStatus, TaskKind, TaskOutcome, TaskStatus
from app.models.files import FileObject
from app.models.pregnancy import PregnancyEpisode
from app.models.records import (
    InstructionStatus,
    LocalContact,
    Observation,
    ObservationKind,
    Prescription,
    Referral,
    ReferralStatus,
)
from app.models.staff import StaffMembership, StaffUser
from app.schemas.records import (
    InvestigationIn,
    InvestigationOut,
    InvestigationStepIn,
    LocalContactIn,
    LocalContactOut,
    LocalContactVerifyIn,
    ObservationCorrectionIn,
    ObservationIn,
    ObservationOut,
    PrescriptionIn,
    PrescriptionOut,
    PrescriptionReviewIn,
    ReferralIn,
    ReferralOut,
    ReferralStepIn,
)

router = APIRouter(tags=["records"])

# A contact not re-verified for this long is shown as stale (administrative).
CONTACT_STALE_AFTER = timedelta(days=90)


def _file_for_episode(db: Session, file_id: str | None, episode: PregnancyEpisode) -> uuid.UUID | None:
    """A linked file must belong to this mother at this facility."""
    if not file_id:
        return None
    f = db.get(FileObject, _uuid(file_id))
    if f is None or f.facility_id != episode.facility_id or f.subject_person_id != episode.mother_person_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="That file does not belong to this record.")
    return f.id


def _review_task(episode: PregnancyEpisode, record_type: str, record_id: uuid.UUID, owner: uuid.UUID | None) -> CareTask:
    return CareTask(
        episode_id=episode.id,
        facility_id=episode.facility_id,
        kind=TaskKind.REVIEW_WORK,
        status=TaskStatus.ASSIGNED if owner else TaskStatus.NEW,
        owner_staff_user_id=owner,
        source_record_type=record_type,
        source_record_id=record_id,
    )


# --- Investigations / reports (F009) ------------------------------------------------


def _investigation_out(db: Session, i: Investigation) -> InvestigationOut:
    return InvestigationOut(
        id=str(i.id),
        episode_id=str(i.episode_id),
        name=i.name,
        status=i.status.value,
        requested_on=i.requested_on,
        performed_on=i.performed_on,
        received_at=i.received_at,
        source=i.source,
        file_id=str(i.file_object_id) if i.file_object_id else None,
        reviewed_at=i.reviewed_at,
        reviewed_by_name=_name(db, i.reviewed_by_staff_user_id),
        version=i.version,
    )


@router.get("/pregnancy-episodes/{episode_id}/investigations", response_model=list[InvestigationOut])
def list_investigations(episode_id: str, db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)) -> list[InvestigationOut]:
    episode, _ = _episode(db, staff, episode_id, "list_investigations")
    rows = db.execute(select(Investigation).where(Investigation.episode_id == episode.id).order_by(Investigation.created_at.desc())).scalars().all()
    _audit(staff, "list_investigations", "PregnancyEpisode", episode.id, count=len(rows))
    return [_investigation_out(db, i) for i in rows]


@router.post("/pregnancy-episodes/{episode_id}/investigations", response_model=InvestigationOut, status_code=status.HTTP_201_CREATED)
def create_investigation(
    episode_id: str,
    body: InvestigationIn,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
    _csrf: None = Depends(require_csrf_header),
) -> InvestigationOut:
    """A requested test, or an outside report received with a file. A report
    is RECEIVED, never REVIEWED, until a clinician reviews it."""
    episode, _ = _episode(db, staff, episode_id, "create_investigation")
    file_id = _file_for_episode(db, body.received_file_id, episode)
    received = file_id is not None
    inv = Investigation(
        episode_id=episode.id,
        facility_id=episode.facility_id,
        name=body.name.strip(),
        status=InvestigationStatus.RECEIVED if received else InvestigationStatus.REQUESTED,
        requested_on=body.requested_on,
        received_at=_now() if received else None,
        source=body.source,
        file_object_id=file_id,
    )
    db.add(inv)
    _commit(db)
    _audit(staff, "create_investigation", "Investigation", inv.id, state=inv.status, with_file=received)
    return _investigation_out(db, inv)


def _investigation(
    db: Session, staff: StaffUser, inv_id: str, action: str
) -> tuple[Investigation, PregnancyEpisode, StaffMembership]:
    inv = db.get(Investigation, _uuid(inv_id))
    if inv is None:
        _audit(staff, action, "Investigation", inv_id, AuditOutcome.DENIED, reason="not_found")
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    membership = _membership_for(db, staff, inv.facility_id, action, "Investigation", inv.id)
    episode = db.get(PregnancyEpisode, inv.episode_id)
    assert episode is not None
    return inv, episode, membership


@router.post("/investigations/{inv_id}/{step}", response_model=InvestigationOut)
def investigation_step(
    inv_id: str,
    step: str,
    body: InvestigationStepIn,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
    _csrf: None = Depends(require_csrf_header),
) -> InvestigationOut:
    """step = performed | received | reviewed. Reviewed is clinician-only and
    records who and when; the app never reads or interprets the report."""
    targets = {
        "performed": InvestigationStatus.PERFORMED,
        "received": InvestigationStatus.RECEIVED,
        "reviewed": InvestigationStatus.REVIEWED,
    }
    if step not in targets:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    action = f"investigation_{step}"
    inv, episode, membership = _investigation(db, staff, inv_id, action)
    _version(inv.version, body.expected_version)
    target = targets[step]
    _transition(INVESTIGATION_TRANSITIONS, inv.status, target, membership, staff, action, "Investigation", inv.id)
    if target is InvestigationStatus.PERFORMED:
        inv.performed_on = body.performed_on
    elif target is InvestigationStatus.RECEIVED:
        inv.received_at = _now()
        new_file = _file_for_episode(db, body.file_id, episode)
        if new_file is not None:
            inv.file_object_id = new_file
    else:
        inv.reviewed_at = _now()
        inv.reviewed_by_staff_user_id = staff.id
    inv.status = target
    _commit(db)
    _audit(staff, action, "Investigation", inv.id, state=target)
    return _investigation_out(db, inv)


# --- Prescriptions (F010) ----------------------------------------------------------


def _prescription_out(db: Session, p: Prescription) -> PrescriptionOut:
    return PrescriptionOut(
        id=str(p.id),
        episode_id=str(p.episode_id),
        source=p.source.value,
        source_file_id=str(p.source_file_id) if p.source_file_id else None,
        issued_on=p.issued_on,
        recorded_by_name=_name(db, p.recorded_by_staff_user_id),
        instruction_status=p.instruction_status.value,
        confirmed_instruction=p.confirmed_instruction,
        reviewed_by_name=_name(db, p.reviewed_by_staff_user_id),
        reviewed_at=p.reviewed_at,
        reminder_enabled=p.reminder_enabled,
        reminder_start=p.reminder_start,
        reminder_end=p.reminder_end,
        created_at=p.created_at,
        version=p.version,
    )


@router.get("/pregnancy-episodes/{episode_id}/prescriptions", response_model=list[PrescriptionOut])
def list_prescriptions(episode_id: str, db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)) -> list[PrescriptionOut]:
    episode, _ = _episode(db, staff, episode_id, "list_prescriptions")
    rows = db.execute(select(Prescription).where(Prescription.episode_id == episode.id).order_by(Prescription.created_at.desc())).scalars().all()
    _audit(staff, "list_prescriptions", "PregnancyEpisode", episode.id, count=len(rows))
    return [_prescription_out(db, p) for p in rows]


@router.post("/pregnancy-episodes/{episode_id}/prescriptions", response_model=PrescriptionOut, status_code=status.HTTP_201_CREATED)
def record_prescription(
    episode_id: str,
    body: PrescriptionIn,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
    _csrf: None = Depends(require_csrf_header),
) -> PrescriptionOut:
    """Records an already-issued prescription from its original document.
    No reminder is possible until a clinician confirms the instruction."""
    episode, _ = _episode(db, staff, episode_id, "record_prescription")
    p = Prescription(
        episode_id=episode.id,
        facility_id=episode.facility_id,
        source=body.source,
        source_file_id=_file_for_episode(db, body.source_file_id, episode),
        issued_on=body.issued_on,
        recorded_by_staff_user_id=staff.id,
        instruction_status=InstructionStatus.UNREVIEWED,
    )
    db.add(p)
    db.flush()
    db.add(_review_task(episode, "PRESCRIPTION", p.id, owner=None))  # a clinician must review it
    _commit(db)
    _audit(staff, "record_prescription", "Prescription", p.id, source=body.source)
    return _prescription_out(db, p)


@router.post("/prescriptions/{prescription_id}/review", response_model=PrescriptionOut)
def review_prescription(
    prescription_id: str,
    body: PrescriptionReviewIn,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
    _csrf: None = Depends(require_csrf_header),
) -> PrescriptionOut:
    """Clinician-only. CONFIRMED: the instruction transcribed as written, and
    optionally a reminder. UNCLEAR: no text, no reminder; the review work
    stays open, owned by the reviewing clinician."""
    p = db.get(Prescription, _uuid(prescription_id))
    if p is None:
        _audit(staff, "review_prescription", "Prescription", prescription_id, AuditOutcome.DENIED, reason="not_found")
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    membership = _membership_for(db, staff, p.facility_id, "review_prescription", "Prescription", p.id)
    _require_capability(staff, membership, Capability.REVIEW_PRESCRIPTION, "review_prescription", "Prescription", p.id)
    _version(p.version, body.expected_version)

    p.reviewed_by_staff_user_id = staff.id
    p.reviewed_at = _now()
    review = db.execute(
        select(CareTask).where(
            CareTask.source_record_type == "PRESCRIPTION",
            CareTask.source_record_id == p.id,
            CareTask.status.in_((TaskStatus.NEW, TaskStatus.ASSIGNED, TaskStatus.AWAITING_PATIENT)),
        )
    ).scalars().first()
    if body.decision == "CONFIRMED":
        p.instruction_status = InstructionStatus.CONFIRMED
        p.confirmed_instruction = (body.confirmed_instruction or "").strip()
        p.reminder_enabled = body.reminder_enabled
        p.reminder_start = body.reminder_start
        p.reminder_end = body.reminder_end
        if review is not None:
            review.status = TaskStatus.COMPLETED
            review.owner_staff_user_id = review.owner_staff_user_id or staff.id
            review.outcome = TaskOutcome.DONE
            review.closure_reason = "DONE_AS_PLANNED"
            review.closed_at = _now()
    else:
        p.instruction_status = InstructionStatus.UNCLEAR
        p.confirmed_instruction = None
        p.reminder_enabled = False
        p.reminder_start = None
        p.reminder_end = None
        if review is not None and review.status is TaskStatus.NEW:
            review.status = TaskStatus.ASSIGNED
            review.owner_staff_user_id = staff.id
    _commit(db)
    _audit(staff, "review_prescription", "Prescription", p.id, decision=body.decision, reminder=p.reminder_enabled)
    return _prescription_out(db, p)


# --- Observations (F012) ----------------------------------------------------------


def _observation_out(db: Session, o: Observation) -> ObservationOut:
    return ObservationOut(
        id=str(o.id),
        episode_id=str(o.episode_id),
        kind=o.kind.value,
        name=o.name,
        value_text=o.value_text,
        unit=o.unit,
        observed_on=o.observed_on,
        source=o.source.value,
        recorded_by_name=_name(db, o.recorded_by_staff_user_id),
        corrects_id=str(o.corrects_id) if o.corrects_id else None,
        correction_reason=o.correction_reason.value if o.correction_reason else None,
        superseded_at=o.superseded_at,
        created_at=o.created_at,
        version=o.version,
    )


@router.get("/pregnancy-episodes/{episode_id}/observations", response_model=list[ObservationOut])
def list_observations(
    episode_id: str,
    include_superseded: bool = False,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
) -> list[ObservationOut]:
    episode, _ = _episode(db, staff, episode_id, "list_observations")
    query = select(Observation).where(Observation.episode_id == episode.id)
    if not include_superseded:
        query = query.where(Observation.superseded_at.is_(None))
    rows = db.execute(query.order_by(Observation.observed_on.desc().nulls_last(), Observation.created_at.desc())).scalars().all()
    _audit(staff, "list_observations", "PregnancyEpisode", episode.id, count=len(rows))
    return [_observation_out(db, o) for o in rows]


@router.post("/pregnancy-episodes/{episode_id}/observations", response_model=ObservationOut, status_code=status.HTTP_201_CREATED)
def record_observation(
    episode_id: str,
    body: ObservationIn,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
    _csrf: None = Depends(require_csrf_header),
) -> ObservationOut:
    """Stores what was entered, as entered. Clinician findings are
    clinician-only. No value is compared with anything."""
    episode, membership = _episode(db, staff, episode_id, "record_observation")
    if body.kind is ObservationKind.CLINICIAN_FINDING:
        _require_capability(staff, membership, Capability.RECORD_CLINICAL_FINDING, "record_observation", "PregnancyEpisode", episode.id)
    o = Observation(
        episode_id=episode.id,
        facility_id=episode.facility_id,
        kind=body.kind,
        name=body.name.strip(),
        value_text=body.value_text.strip(),
        unit=(body.unit or "").strip() or None,
        observed_on=body.observed_on,
        source=body.source,
        recorded_by_staff_user_id=staff.id,
    )
    db.add(o)
    _commit(db)
    _audit(staff, "record_observation", "Observation", o.id, kind=body.kind)
    return _observation_out(db, o)


@router.post("/observations/{observation_id}/correct", response_model=ObservationOut, status_code=status.HTTP_201_CREATED)
def correct_observation(
    observation_id: str,
    body: ObservationCorrectionIn,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
    _csrf: None = Depends(require_csrf_header),
) -> ObservationOut:
    """A correction is a new entry with a reason; the earlier value is kept."""
    old = db.get(Observation, _uuid(observation_id))
    if old is None:
        _audit(staff, "correct_observation", "Observation", observation_id, AuditOutcome.DENIED, reason="not_found")
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    membership = _membership_for(db, staff, old.facility_id, "correct_observation", "Observation", old.id)
    if old.kind is ObservationKind.CLINICIAN_FINDING or body.kind is ObservationKind.CLINICIAN_FINDING:
        _require_capability(staff, membership, Capability.RECORD_CLINICAL_FINDING, "correct_observation", "Observation", old.id)
    if old.superseded_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="This entry was already corrected.")
    _version(old.version, body.expected_version)
    new = Observation(
        id=uuid.uuid4(),
        episode_id=old.episode_id,
        facility_id=old.facility_id,
        kind=body.kind,
        name=body.name.strip(),
        value_text=body.value_text.strip(),
        unit=(body.unit or "").strip() or None,
        observed_on=body.observed_on,
        source=body.source,
        recorded_by_staff_user_id=staff.id,
        corrects_id=old.id,
        correction_reason=body.correction_reason,
    )
    old.superseded_at = _now()
    old.superseded_by_id = new.id
    db.flush()
    db.add(new)
    _commit(db)
    _audit(staff, "correct_observation", "Observation", new.id, corrects=str(old.id), reason=body.correction_reason)
    return _observation_out(db, new)


# --- Verified local contacts (F044) --------------------------------------------------


def _contact_out(db: Session, c: LocalContact) -> LocalContactOut:
    return LocalContactOut(
        id=str(c.id),
        facility_id=str(c.facility_id),
        service_type=c.service_type.value,
        name=c.name,
        phone=c.phone,
        alternate_phone=c.alternate_phone,
        landmarks=c.landmarks,
        availability_note=c.availability_note,
        verified_by_name=_name(db, c.verified_by_staff_user_id),
        verified_on=c.verified_on,
        stale=c.verified_on < _today() - CONTACT_STALE_AFTER,
        version=c.version,
    )


@router.get("/local-contacts", response_model=list[LocalContactOut])
def list_local_contacts(facility_id: str, db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)) -> list[LocalContactOut]:
    fid = _uuid(facility_id)
    _membership_for(db, staff, fid, "list_local_contacts", "Facility", fid)
    rows = db.execute(
        select(LocalContact).where(LocalContact.facility_id == fid, LocalContact.active.is_(True)).order_by(LocalContact.service_type, LocalContact.name)
    ).scalars().all()
    return [_contact_out(db, c) for c in rows]


@router.post("/local-contacts", response_model=LocalContactOut, status_code=status.HTTP_201_CREATED)
def create_local_contact(
    body: LocalContactIn,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
    _csrf: None = Depends(require_csrf_header),
) -> LocalContactOut:
    """The creator vouches that they verified the number today."""
    fid = _uuid(body.facility_id)
    _membership_for(db, staff, fid, "create_local_contact", "Facility", fid)
    c = LocalContact(
        facility_id=fid,
        service_type=body.service_type,
        name=body.name.strip(),
        phone=body.phone.strip(),
        alternate_phone=(body.alternate_phone or "").strip() or None,
        landmarks=(body.landmarks or "").strip() or None,
        availability_note=(body.availability_note or "").strip() or None,
        verified_by_staff_user_id=staff.id,
        verified_on=_today(),
    )
    db.add(c)
    _commit(db)
    _audit(staff, "create_local_contact", "LocalContact", c.id, service_type=body.service_type)
    return _contact_out(db, c)


@router.post("/local-contacts/{contact_id}/verify", response_model=LocalContactOut)
def verify_local_contact(
    contact_id: str,
    body: LocalContactVerifyIn,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
    _csrf: None = Depends(require_csrf_header),
) -> LocalContactOut:
    c = db.get(LocalContact, _uuid(contact_id))
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    _membership_for(db, staff, c.facility_id, "verify_local_contact", "LocalContact", c.id)
    _version(c.version, body.expected_version)
    c.verified_by_staff_user_id = staff.id
    c.verified_on = _today()
    _commit(db)
    _audit(staff, "verify_local_contact", "LocalContact", c.id)
    return _contact_out(db, c)


# --- Referrals (F011) -----------------------------------------------------------------


def _referral_out(db: Session, r: Referral) -> ReferralOut:
    return ReferralOut(
        id=str(r.id),
        episode_id=str(r.episode_id),
        destination_contact_id=str(r.destination_contact_id) if r.destination_contact_id else None,
        destination_name=r.destination_name,
        urgency=r.urgency.value,
        clinician_instruction=r.clinician_instruction,
        referred_by_name=_name(db, r.referred_by_staff_user_id),
        owner_staff_user_id=str(r.owner_staff_user_id),
        owner_name=_name(db, r.owner_staff_user_id),
        status=r.status.value,
        contacted_at=r.contacted_at,
        attended_on=r.attended_on,
        advice_received_at=r.advice_received_at,
        advice_file_id=str(r.advice_file_id) if r.advice_file_id else None,
        follow_up_completed_at=r.follow_up_completed_at,
        closure_reason=r.closure_reason.value if r.closure_reason else None,
        closed_at=r.closed_at,
        created_at=r.created_at,
        version=r.version,
    )


@router.get("/pregnancy-episodes/{episode_id}/referrals", response_model=list[ReferralOut])
def list_referrals(episode_id: str, db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)) -> list[ReferralOut]:
    episode, _ = _episode(db, staff, episode_id, "list_referrals")
    rows = db.execute(select(Referral).where(Referral.episode_id == episode.id).order_by(Referral.created_at.desc())).scalars().all()
    _audit(staff, "list_referrals", "PregnancyEpisode", episode.id, count=len(rows))
    return [_referral_out(db, r) for r in rows]


@router.post("/pregnancy-episodes/{episode_id}/referrals", response_model=ReferralOut, status_code=status.HTTP_201_CREATED)
def create_referral(
    episode_id: str,
    body: ReferralIn,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
    _csrf: None = Depends(require_csrf_header),
) -> ReferralOut:
    """Clinician-only: the clinician chooses destination and urgency."""
    episode, membership = _episode(db, staff, episode_id, "create_referral")
    _require_capability(staff, membership, Capability.CREATE_REFERRAL, "create_referral", "PregnancyEpisode", episode.id)
    contact_id = None
    if body.destination_contact_id:
        contact = db.get(LocalContact, _uuid(body.destination_contact_id))
        if contact is None or contact.facility_id != episode.facility_id:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Choose a contact from this facility.")
        contact_id = contact.id
    owner = _uuid(body.owner_staff_user_id) if body.owner_staff_user_id else staff.id
    if find_active_membership(db, owner, episode.facility_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The owner must work at this facility.")
    r = Referral(
        episode_id=episode.id,
        facility_id=episode.facility_id,
        destination_contact_id=contact_id,
        destination_name=(body.destination_name or "").strip() or None,
        urgency=body.urgency,
        clinician_instruction=(body.clinician_instruction or "").strip() or None,
        referred_by_staff_user_id=staff.id,
        owner_staff_user_id=owner,
        status=ReferralStatus.SENT,
    )
    db.add(r)
    _commit(db)
    _audit(staff, "create_referral", "Referral", r.id, urgency=body.urgency)
    return _referral_out(db, r)


@router.post("/referrals/{referral_id}/step", response_model=ReferralOut)
def referral_step(
    referral_id: str,
    body: ReferralStepIn,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
    _csrf: None = Depends(require_csrf_header),
) -> ReferralOut:
    """Records what happened. Advice received opens one owned follow-up
    task. Closing needs a reason from the fixed list."""
    r = db.get(Referral, _uuid(referral_id))
    if r is None:
        _audit(staff, "referral_step", "Referral", referral_id, AuditOutcome.DENIED, reason="not_found")
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    membership = _membership_for(db, staff, r.facility_id, "referral_step", "Referral", r.id)
    _version(r.version, body.expected_version)
    target = ReferralStatus(body.to)
    previous = r.status
    _transition(REFERRAL_TRANSITIONS, previous, target, membership, staff, "referral_step", "Referral", r.id)
    episode = db.get(PregnancyEpisode, r.episode_id)
    assert episode is not None
    now = _now()
    if target is ReferralStatus.CONTACTED:
        r.contacted_at = now
    elif target is ReferralStatus.ATTENDED:
        r.attended_on = body.attended_on  # may be unknown
    elif target is ReferralStatus.ADVICE_RECEIVED:
        r.advice_received_at = now
        r.advice_file_id = _file_for_episode(db, body.advice_file_id, episode)
        db.add(_review_task(episode, "REFERRAL", r.id, owner=r.owner_staff_user_id))
    elif target is ReferralStatus.FOLLOW_UP_COMPLETED:
        r.follow_up_completed_at = now
    else:
        r.closure_reason = body.closure_reason
        r.closed_at = now
    r.status = target
    _commit(db)
    _audit(staff, "referral_step", "Referral", r.id, from_state=previous, to_state=target, reason=body.closure_reason)
    return _referral_out(db, r)

