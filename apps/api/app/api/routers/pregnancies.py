import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import (
    get_current_staff,
    require_active_facility,
    require_csrf_header,
    require_facility_membership,
)
from app.models.audit import AuditOutcome
from app.models.identity import Person
from app.models.pregnancy import ONE_ACTIVE_EPISODE_INDEX, PregnancyEpisode, PregnancyEpisodeStatus
from app.models.staff import StaffUser
from app.schemas.pregnancy import PregnancyEpisodeCreate, PregnancyEpisodeOut
from app.services import audit_service, idempotency_service

router = APIRouter(prefix="/pregnancy-episodes", tags=["pregnancies"])
_ENDPOINT = "create_pregnancy_episode"

ACTIVE_EPISODE_EXISTS = "This mother already has an active pregnancy episode."


def to_out(episode: PregnancyEpisode, mother_name: str) -> PregnancyEpisodeOut:
    return PregnancyEpisodeOut(
        id=str(episode.id),
        mother_person_id=str(episode.mother_person_id),
        mother_full_name=mother_name,
        facility_id=str(episode.facility_id),
        dating_estimate=episode.dating_estimate,
        dating_source=episode.dating_source,
        status=episode.status,
        created_at=episode.created_at,
    )


def find_active_episode(db: Session, person_id: uuid.UUID) -> PregnancyEpisode | None:
    return (
        db.query(PregnancyEpisode)
        .filter(
            PregnancyEpisode.mother_person_id == person_id,
            PregnancyEpisode.status == PregnancyEpisodeStatus.ACTIVE,
        )
        .first()
    )


def _active_episode_conflict(staff: StaffUser, existing: PregnancyEpisode) -> HTTPException:
    """409 pointing at the existing episode. The caller already passed the
    facility check for this mother, so revealing her episode id leaks nothing."""
    audit_service.record_event(
        actor_staff_user_id=staff.id,
        action="create",
        entity_type="PregnancyEpisode",
        entity_id=str(existing.id),
        outcome=AuditOutcome.DENIED,
        metadata={"reason": "active_episode_exists"},
    )
    return HTTPException(
        status.HTTP_409_CONFLICT,
        detail={"message": ACTIVE_EPISODE_EXISTS, "existing_episode_id": str(existing.id)},
    )


def _is_one_active_violation(err: IntegrityError) -> bool:
    diag = getattr(err.orig, "diag", None)
    return getattr(diag, "constraint_name", None) == ONE_ACTIVE_EPISODE_INDEX


@router.post("", response_model=PregnancyEpisodeOut, status_code=status.HTTP_201_CREATED)
def create_pregnancy_episode(
    body: PregnancyEpisodeCreate,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
    _csrf: None = Depends(require_csrf_header),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> PregnancyEpisodeOut:
    claimed_row_id: uuid.UUID | None = None

    if idempotency_key:
        payload_hash = idempotency_service.hash_payload(body.model_dump(mode="json"))
        result = idempotency_service.claim(
            db, staff_user_id=staff.id, endpoint=_ENDPOINT, key=idempotency_key, payload_hash=payload_hash
        )
        if result.payload_mismatch:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail="Idempotency key already used with a different request"
            )
        if not result.won:
            existing_episode = db.get(PregnancyEpisode, result.response_entity_id)
            if existing_episode is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
            # Re-checked against current membership even on replay — a
            # cached result never bypasses live access control.
            require_facility_membership(db, staff, existing_episode.facility_id)
            mother = db.get(Person, existing_episode.mother_person_id)
            return to_out(existing_episode, mother.full_name if mother else "")
        claimed_row_id = result.idempotency_row_id

    person = db.get(Person, uuid.UUID(body.person_id))
    if person is None:
        audit_service.record_event(
            actor_staff_user_id=staff.id,
            action="create",
            entity_type="PregnancyEpisode",
            entity_id=None,
            outcome=AuditOutcome.DENIED,
            metadata={"reason": "person_not_found_or_inaccessible"},
        )
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")

    # Reject creating an episode against a person the caller cannot access —
    # access to a Person is the same facility-membership check used for
    # everything else, so this can't be bypassed by supplying a bare id.
    try:
        require_facility_membership(db, staff, person.registering_facility_id)
        require_active_facility(db, person.registering_facility_id)
    except HTTPException:
        audit_service.record_event(
            actor_staff_user_id=staff.id,
            action="create",
            entity_type="PregnancyEpisode",
            entity_id=None,
            outcome=AuditOutcome.DENIED,
            metadata={"reason": "person_not_found_or_inaccessible"},
        )
        raise

    # D13: one ACTIVE episode per mother. Checked here for a clear answer;
    # the partial unique index below is what actually guarantees it under
    # concurrency.
    existing_active = find_active_episode(db, person.id)
    if existing_active is not None:
        raise _active_episode_conflict(staff, existing_active)

    # facility_id is derived from the person's registering facility, never
    # accepted from the client — the episode cannot be created under an
    # arbitrary facility the caller merely names in the request body.
    episode = PregnancyEpisode(
        mother_person_id=person.id,
        facility_id=person.registering_facility_id,
        dating_estimate=body.dating_estimate,
        dating_source=body.dating_source,
        created_by_staff_user_id=staff.id,
    )
    db.add(episode)
    try:
        db.flush()
    except IntegrityError as err:
        if not _is_one_active_violation(err):
            raise
        # Lost a race: another request created her active episode between
        # our check and our insert. Answer exactly as if we had seen it.
        db.rollback()
        winner = find_active_episode(db, person.id)
        if winner is None:  # pragma: no cover - the index guarantees one exists
            raise
        raise _active_episode_conflict(staff, winner) from None

    if claimed_row_id is not None:
        idempotency_service.attach_result(db, idempotency_row_id=claimed_row_id, entity_id=episode.id)

    db.commit()

    audit_service.record_event(
        actor_staff_user_id=staff.id,
        action="create",
        entity_type="PregnancyEpisode",
        entity_id=str(episode.id),
        outcome=AuditOutcome.SUCCESS,
        metadata={"facility_id": str(episode.facility_id)},
    )
    return to_out(episode, person.full_name)


@router.get("/{episode_id}", response_model=PregnancyEpisodeOut)
def get_pregnancy_episode(
    episode_id: str,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
) -> PregnancyEpisodeOut:
    episode = db.get(PregnancyEpisode, uuid.UUID(episode_id))
    if episode is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")

    try:
        require_facility_membership(db, staff, episode.facility_id)
    except HTTPException:
        audit_service.record_event(
            actor_staff_user_id=staff.id,
            action="read",
            entity_type="PregnancyEpisode",
            entity_id=str(episode.id),
            outcome=AuditOutcome.DENIED,
            metadata={},
        )
        raise

    mother = db.get(Person, episode.mother_person_id)
    audit_service.record_event(
        actor_staff_user_id=staff.id,
        action="read",
        entity_type="PregnancyEpisode",
        entity_id=str(episode.id),
        outcome=AuditOutcome.SUCCESS,
        metadata={},
    )
    return to_out(episode, mother.full_name if mother else "")
