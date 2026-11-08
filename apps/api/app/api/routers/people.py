import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import (
    get_current_staff,
    require_active_facility,
    require_csrf_header,
    require_facility_membership,
    roles_at_facility,
)
from app.api.routers.pregnancies import to_out as episode_to_out
from app.domain.permissions import DENIED_MESSAGE, Capability, has_capability
from app.models.audit import AuditOutcome
from app.models.identity import ContactMethod, ContactType, Person
from app.models.pregnancy import PregnancyEpisode
from app.models.staff import StaffMembership, StaffUser
from app.schemas.person import PersonCreate, PersonOut
from app.schemas.pregnancy import PregnancyEpisodeOut
from app.services import audit_service, idempotency_service

router = APIRouter(prefix="/people", tags=["people"])
_ENDPOINT = "create_person"

# A search is bounded, not paginated — F002's "find an authorized record" is
# an exact-phone lookup scoped to the caller's own facilities, so the
# realistic result set is small (a shared handset has a handful of
# registrants, not thousands). If that assumption stops holding, add real
# pagination then rather than building it unused now.
_SEARCH_RESULT_CAP = 50


def _primary_contact(db: Session, person_id: uuid.UUID) -> ContactMethod | None:
    return (
        db.query(ContactMethod)
        .filter(ContactMethod.person_id == person_id, ContactMethod.type == ContactType.PHONE)
        .first()
    )


def _verifier_name(db: Session, contact: ContactMethod | None) -> str | None:
    if contact is None or contact.verified_by_staff_user_id is None:
        return None
    verifier = db.get(StaffUser, contact.verified_by_staff_user_id)
    return verifier.full_name if verifier else None


def _to_out(db: Session, staff: StaffUser, person: Person, contact: ContactMethod | None) -> PersonOut:
    # Reported history and allergies follow the role-capability table (M008 Q12).
    show_history = has_capability(
        roles_at_facility(db, staff, person.registering_facility_id), Capability.VIEW_REPORTED_HISTORY
    )
    return PersonOut(
        id=str(person.id),
        full_name=person.full_name,
        age_precision=person.age_precision,
        date_of_birth=person.date_of_birth,
        birth_year=person.birth_year,
        reported_age_years=person.reported_age_years,
        preferred_language=person.preferred_language,
        reported_medical_history=person.reported_medical_history if show_history else None,
        known_allergies_medicines=person.known_allergies_medicines if show_history else None,
        reported_history_withheld=not show_history,
        registering_facility_id=str(person.registering_facility_id),
        phone=contact.value if contact else "",
        contact_verified_at=contact.verified_at if contact else None,
        contact_verified_by_name=_verifier_name(db, contact),
    )


def _caller_facility_ids(db: Session, staff: StaffUser) -> list[uuid.UUID]:
    rows = (
        db.query(StaffMembership.facility_id)
        .filter(StaffMembership.staff_user_id == staff.id, StaffMembership.active.is_(True))
        .all()
    )
    return [r[0] for r in rows]


@router.get("", response_model=list[PersonOut])
def search_people(
    phone: str | None = Query(default=None, min_length=1),
    full_name: str | None = Query(default=None, min_length=1),
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
) -> list[PersonOut]:
    """F002 "find an authorized record": phone (exact) and/or name (partial,
    case-insensitive) search, scoped to the caller's own facilities only. A
    phone number is not an identity, so this deliberately returns every
    distinct Person it matches within scope (never merges them) — the
    caller picks the right one, or registers a new person if none is right.
    A match outside the caller's facilities is never returned; it isn't
    404'd per-row because there's no per-row reference to deny, it's simply
    excluded from the result set.
    """
    if not phone and not full_name:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Supply phone and/or full_name")

    facility_ids = _caller_facility_ids(db, staff)
    if not facility_ids:
        return []

    query = (
        db.query(Person, ContactMethod)
        .join(ContactMethod, ContactMethod.person_id == Person.id)
        .filter(ContactMethod.type == ContactType.PHONE)
        .filter(Person.registering_facility_id.in_(facility_ids))
    )
    if phone:
        query = query.filter(ContactMethod.value == phone)
    if full_name:
        query = query.filter(Person.full_name.ilike(f"%{full_name}%"))

    rows = query.limit(_SEARCH_RESULT_CAP).all()
    audit_service.record_event(
        actor_staff_user_id=staff.id,
        action="search",
        entity_type="Person",
        entity_id=None,
        outcome=AuditOutcome.SUCCESS,
        metadata={"result_count": len(rows)},
    )
    return [_to_out(db, staff, person, contact) for person, contact in rows]


@router.post("", response_model=PersonOut, status_code=status.HTTP_201_CREATED)
def create_person(
    body: PersonCreate,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
    _csrf: None = Depends(require_csrf_header),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> PersonOut:
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
            # A completed prior attempt (sequential retry, or the loser of a
            # concurrent race that blocked until the winner committed).
            # Authorization is re-checked against *current* facility
            # membership before returning it — a cached result never
            # bypasses live access control, even on replay.
            existing_person = db.get(Person, result.response_entity_id)
            if existing_person is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
            require_facility_membership(db, staff, existing_person.registering_facility_id)
            return _to_out(db, staff, existing_person, _primary_contact(db, existing_person.id))
        claimed_row_id = result.idempotency_row_id

    facility_id = uuid.UUID(body.facility_id)
    # Server-side ownership: the caller must hold an active membership at the
    # facility they're registering this person under, and that facility must
    # be active. facility_id is never trusted beyond that validation.
    try:
        require_facility_membership(db, staff, facility_id)
        require_active_facility(db, facility_id)
    except HTTPException:
        audit_service.record_event(
            actor_staff_user_id=staff.id,
            action="create",
            entity_type="Person",
            entity_id=None,
            outcome=AuditOutcome.DENIED,
            metadata={"facility_id": str(facility_id)},
        )
        raise
    if not has_capability(roles_at_facility(db, staff, facility_id), Capability.REGISTER_MOTHER):
        audit_service.record_event(
            actor_staff_user_id=staff.id,
            action="create",
            entity_type="Person",
            entity_id=None,
            outcome=AuditOutcome.DENIED,
            metadata={"facility_id": str(facility_id), "reason": "role_not_permitted"},
        )
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=DENIED_MESSAGE[Capability.REGISTER_MOTHER])

    person = Person(
        full_name=body.full_name,
        age_precision=body.age_precision,
        date_of_birth=body.date_of_birth,
        birth_year=body.birth_year,
        reported_age_years=body.reported_age_years,
        preferred_language=body.preferred_language,
        reported_medical_history=body.reported_medical_history,
        known_allergies_medicines=body.known_allergies_medicines,
        registering_facility_id=facility_id,
        created_by_staff_user_id=staff.id,
    )
    db.add(person)
    db.flush()
    contact = ContactMethod(person_id=person.id, type=ContactType.PHONE, value=body.phone)
    db.add(contact)

    if claimed_row_id is not None:
        idempotency_service.attach_result(db, idempotency_row_id=claimed_row_id, entity_id=person.id)

    # One commit for the claim, the person, the contact, and the attached
    # idempotency result together — see idempotency_service.claim's docstring.
    db.commit()

    audit_service.record_event(
        actor_staff_user_id=staff.id,
        action="create",
        entity_type="Person",
        entity_id=str(person.id),
        outcome=AuditOutcome.SUCCESS,
        metadata={"facility_id": str(facility_id)},
    )
    return _to_out(db, staff, person, contact)


@router.get("/{person_id}", response_model=PersonOut)
def get_person(
    person_id: str,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
) -> PersonOut:
    person = db.get(Person, uuid.UUID(person_id))
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")

    try:
        require_facility_membership(db, staff, person.registering_facility_id)
    except HTTPException:
        audit_service.record_event(
            actor_staff_user_id=staff.id,
            action="read",
            entity_type="Person",
            entity_id=str(person.id),
            outcome=AuditOutcome.DENIED,
            metadata={},
        )
        raise

    contact = _primary_contact(db, person.id)
    audit_service.record_event(
        actor_staff_user_id=staff.id,
        action="read",
        entity_type="Person",
        entity_id=str(person.id),
        outcome=AuditOutcome.SUCCESS,
        metadata={},
    )
    return _to_out(db, staff, person, contact)


@router.get("/{person_id}/episodes", response_model=list[PregnancyEpisodeOut])
def list_person_episodes(
    person_id: str,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
) -> list[PregnancyEpisodeOut]:
    """A mother's pregnancy episodes, newest first, so staff can continue her
    active one instead of opening another (D13). Same facility scoping as
    reading the person: a mother outside the caller's facilities is a 404."""
    person = db.get(Person, uuid.UUID(person_id))
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")

    try:
        require_facility_membership(db, staff, person.registering_facility_id)
    except HTTPException:
        audit_service.record_event(
            actor_staff_user_id=staff.id,
            action="list_episodes",
            entity_type="Person",
            entity_id=str(person.id),
            outcome=AuditOutcome.DENIED,
            metadata={},
        )
        raise

    episodes = (
        db.query(PregnancyEpisode)
        .filter(PregnancyEpisode.mother_person_id == person.id)
        .order_by(PregnancyEpisode.created_at.desc())
        .all()
    )
    audit_service.record_event(
        actor_staff_user_id=staff.id,
        action="list_episodes",
        entity_type="Person",
        entity_id=str(person.id),
        outcome=AuditOutcome.SUCCESS,
        metadata={"count": len(episodes)},
    )
    return [episode_to_out(e, person.full_name) for e in episodes]


@router.post("/{person_id}/contact/verify", response_model=PersonOut)
def verify_contact(
    person_id: str,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
    _csrf: None = Depends(require_csrf_header),
) -> PersonOut:
    """F003 "confirm which person a contact relates to": a staff-assisted
    attestation, not a technical verification (no OTP in this slice) — who
    confirmed it and when is recorded as the evidence.
    """
    person = db.get(Person, uuid.UUID(person_id))
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    require_facility_membership(db, staff, person.registering_facility_id)

    contact = _primary_contact(db, person.id)
    if contact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")

    contact.verified_at = datetime.now(timezone.utc)
    contact.verified_by_staff_user_id = staff.id
    db.commit()

    audit_service.record_event(
        actor_staff_user_id=staff.id,
        action="verify_contact",
        entity_type="ContactMethod",
        entity_id=str(contact.id),
        outcome=AuditOutcome.SUCCESS,
        metadata={"person_id": str(person.id)},
    )
    return _to_out(db, staff, person, contact)
