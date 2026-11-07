from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.facility import Facility
from app.models.organization import Organization, OrganizationAdmin
from app.models.staff import StaffMembership, StaffRole, StaffUser


def make_org(db: Session, name: str = "Test Org") -> Organization:
    org = Organization(name=name)
    db.add(org)
    db.commit()
    return org


def make_facility(db: Session, org: Organization, name: str = "Test Facility", active: bool = True) -> Facility:
    facility = Facility(organization_id=org.id, name=name, active=active)
    db.add(facility)
    db.commit()
    return facility


def make_staff(
    db: Session,
    username: str,
    password: str = "synthetic-password-123",
    active: bool = True,
    full_name: str = "Test Staff",
) -> StaffUser:
    staff = StaffUser(
        username=username,
        full_name=full_name,
        phone=None,
        password_hash=hash_password(password),
        active=active,
    )
    db.add(staff)
    db.commit()
    return staff


def make_membership(
    db: Session,
    staff: StaffUser,
    facility: Facility,
    role: StaffRole = StaffRole.COORDINATOR,
    active: bool = True,
) -> StaffMembership:
    from datetime import datetime, timezone

    membership = StaffMembership(
        staff_user_id=staff.id,
        facility_id=facility.id,
        role=role,
        active=active,
        revoked_at=None if active else datetime.now(timezone.utc),
    )
    db.add(membership)
    db.commit()
    return membership


def make_org_admin(db: Session, staff: StaffUser, org: Organization) -> OrganizationAdmin:
    grant = OrganizationAdmin(organization_id=org.id, staff_user_id=staff.id)
    db.add(grant)
    db.commit()
    return grant


# --- Named synthetic scenarios (W2-B4; AT06-AT10, AT28) ------------------------
#
# Every value is invented. Names start with "Synthetic"; phone numbers use
# the reserved +91 00000 range. Each scenario builds its own organization,
# facility and staff, so scenarios never depend on one another.

import uuid as _uuid  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from datetime import date as _date, datetime as _datetime, timedelta as _timedelta, timezone as _tz  # noqa: E402


@dataclass
class World:
    """One facility with a coordinator, a doctor and a nurse (backup)."""

    org: Organization
    facility: Facility
    coordinator: StaffUser
    doctor: StaffUser
    nurse: StaffUser


def make_world(db: Session, tag: str) -> World:
    org = make_org(db, f"Synthetic Org {tag}")
    facility = make_facility(db, org, f"Synthetic Facility {tag}")
    coordinator = make_staff(db, f"{tag}_coord", full_name="Synthetic Coordinator")
    doctor = make_staff(db, f"{tag}_doc", full_name="Synthetic Doctor")
    nurse = make_staff(db, f"{tag}_nurse", full_name="Synthetic Nurse")
    make_membership(db, coordinator, facility, StaffRole.COORDINATOR)
    make_membership(db, doctor, facility, StaffRole.DOCTOR)
    make_membership(db, nurse, facility, StaffRole.NURSE)
    return World(org, facility, coordinator, doctor, nurse)


def make_mother(db: Session, world: World, name: str, phone: str):  # type: ignore[no-untyped-def]
    """A registered mother with one ACTIVE pregnancy episode and no dating."""
    from app.models.identity import ContactMethod, ContactType, Person
    from app.models.pregnancy import PregnancyEpisode

    person = Person(full_name=name, registering_facility_id=world.facility.id, created_by_staff_user_id=world.coordinator.id)
    db.add(person)
    db.flush()
    db.add(ContactMethod(person_id=person.id, type=ContactType.PHONE, value=phone))
    episode = PregnancyEpisode(
        mother_person_id=person.id, facility_id=world.facility.id, created_by_staff_user_id=world.coordinator.id
    )
    db.add(episode)
    db.commit()
    return person, episode


def scenario_unknown_lmp(db: Session, tag: str = "unknown"):  # type: ignore[no-untyped-def]
    """First contact; she does not know her last period. Nothing is recorded."""
    world = make_world(db, tag)
    person, episode = make_mother(db, world, "Synthetic Unknown-Date Mother", "+910000010001")
    return world, person, episode


def scenario_late_presenter(db: Session, tag: str = "late"):  # type: ignore[no-untyped-def]
    """First contact late in pregnancy: only an approximate expected date,
    as told by the family, recorded as PROVISIONAL (not confirmed)."""
    from app.models.dating import DatingEvidence, DatingPrecision, DatingState, EpisodeDating

    world = make_world(db, tag)
    person, episode = make_mother(db, world, "Synthetic Late Presenter", "+910000010002")
    db.add(
        EpisodeDating(
            episode_id=episode.id,
            facility_id=world.facility.id,
            edd=_date.today() + _timedelta(days=30),
            precision=DatingPrecision.APPROXIMATE,
            evidence=DatingEvidence.SELF_REPORTED,
            state=DatingState.PROVISIONAL,
            recorded_by_staff_user_id=world.coordinator.id,
        )
    )
    db.commit()
    return world, person, episode


def scenario_shared_phone(db: Session, tag: str = "shared"):  # type: ignore[no-untyped-def]
    """Two women registered on one household handset."""
    world = make_world(db, tag)
    first = make_mother(db, world, "Synthetic Sister One", "+910000010003")
    second = make_mother(db, world, "Synthetic Sister Two", "+910000010003")
    return world, first, second


def scenario_revoked_caregiver(db: Session, tag: str = "caregiver"):  # type: ignore[no-untyped-def]
    """A mother granted her husband access, then revoked it. Her sister uses
    the same phone and has no grant."""
    from app.models.caregiver import CaregiverGrant, CaregiverScope, RevokeReason, VerificationMethod
    from app.models.identity import Person

    world = make_world(db, tag)
    mother, episode = make_mother(db, world, "Synthetic Mother With Caregiver", "+910000010004")
    caregiver = Person(full_name="Synthetic Caregiver", registering_facility_id=world.facility.id)
    sister = Person(full_name="Synthetic Sister On Same Phone", registering_facility_id=world.facility.id)
    db.add_all([caregiver, sister])
    db.flush()
    now = _datetime.now(_tz.utc)
    grant = CaregiverGrant(
        subject_person_id=mother.id,
        grantee_person_id=caregiver.id,
        scopes=[CaregiverScope.NEXT_ACTION.value, CaregiverScope.BIRTH_PLAN.value],
        recorded_by_staff_user_id=world.coordinator.id,
        verified_by_staff_user_id=world.coordinator.id,
        verification_method=VerificationMethod.IN_PERSON_DOCUMENT,
        expires_at=now + _timedelta(days=90),
        revoked_at=now,
        revoked_by_staff_user_id=world.coordinator.id,
        revoke_reason=RevokeReason.REQUESTED_BY_SUBJECT,
    )
    db.add(grant)
    db.commit()
    return world, mother, episode, caregiver, sister, grant


def scenario_outside_report(db: Session, tag: str = "outside"):  # type: ignore[no-untyped-def]
    """A report done elsewhere, brought in as a photo/PDF: received, with
    unknown request and performed dates, never reviewed by the app."""
    from app.models.care import Investigation, InvestigationStatus
    from app.models.files import FileObject

    world = make_world(db, tag)
    person, episode = make_mother(db, world, "Synthetic Outside-Report Mother", "+910000010005")
    file = FileObject(
        facility_id=world.facility.id,
        subject_person_id=person.id,
        storage_key=_uuid.uuid4().hex,
        original_filename="synthetic-outside-report.pdf",
        content_type="application/pdf",
        size_bytes=128,
        sha256="0" * 64,
        uploaded_by_staff_user_id=world.coordinator.id,
    )
    db.add(file)
    db.flush()
    report = Investigation(
        episode_id=episode.id,
        facility_id=world.facility.id,
        name="Synthetic outside report",
        status=InvestigationStatus.RECEIVED,
        received_at=_datetime.now(_tz.utc),
        source="OUTSIDE_REPORT",
        file_object_id=file.id,
    )
    db.add(report)
    db.commit()
    return world, person, episode, report
