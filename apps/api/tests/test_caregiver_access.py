"""W2-A2: caregiver_grant model and the single server-side access check.
Patient access stays switched off until D07 is decided."""

import os
import uuid
from datetime import datetime, timedelta, timezone

import psycopg
import pytest
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.models.caregiver import CaregiverGrant, CaregiverScope, RevokeReason, VerificationMethod
from app.models.identity import Person
from app.services.caregiver_access import caregiver_access_allowed
from tests.factories import make_facility, make_org, make_staff

ON = Settings(_env_file=None, patient_access_enabled=True)  # type: ignore[call-arg]
NOW = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)


def _people(db, *names):
    org = make_org(db)
    facility = make_facility(db, org)
    staff = make_staff(db, f"cg_staff_{uuid.uuid4().hex[:6]}")
    people = [Person(full_name=n, registering_facility_id=facility.id) for n in names]
    db.add_all(people)
    db.commit()
    return staff, people


def _grant(db, staff, subject, grantee, scopes=(CaregiverScope.NEXT_ACTION,), expires=NOW + timedelta(days=90)):
    grant = CaregiverGrant(
        subject_person_id=subject.id,
        grantee_person_id=grantee.id,
        scopes=[s.value for s in scopes],
        recorded_by_staff_user_id=staff.id,
        verified_by_staff_user_id=staff.id,
        verification_method=VerificationMethod.IN_PERSON_DOCUMENT,
        expires_at=expires,
    )
    db.add(grant)
    db.commit()
    return grant


def _allowed(db, subject, grantee, scope=CaregiverScope.NEXT_ACTION, config=ON, now=NOW):
    return caregiver_access_allowed(
        db, subject_person_id=subject.id, grantee_person_id=grantee.id, scope=scope, now=now, config=config
    )


def test_switched_off_by_default_denies_even_with_a_valid_grant(db_session):
    staff, (mother, caregiver) = _people(db_session, "Synthetic Mother", "Synthetic Caregiver")
    _grant(db_session, staff, mother, caregiver)
    assert Settings(_env_file=None).patient_access_enabled is False  # type: ignore[call-arg]
    assert _allowed(db_session, mother, caregiver, config=Settings(_env_file=None)) is False  # type: ignore[call-arg]


def test_valid_grant_allows_only_its_scopes(db_session):
    staff, (mother, caregiver) = _people(db_session, "Synthetic Mother", "Synthetic Caregiver")
    _grant(db_session, staff, mother, caregiver, scopes=(CaregiverScope.NEXT_ACTION,))
    assert _allowed(db_session, mother, caregiver, CaregiverScope.NEXT_ACTION) is True
    assert _allowed(db_session, mother, caregiver, CaregiverScope.BIRTH_PLAN) is False


def test_grant_is_one_way(db_session):
    staff, (mother, caregiver) = _people(db_session, "Synthetic Mother", "Synthetic Caregiver")
    _grant(db_session, staff, mother, caregiver)
    assert _allowed(db_session, caregiver, mother) is False


def test_expired_grant_denies(db_session):
    staff, (mother, caregiver) = _people(db_session, "Synthetic Mother", "Synthetic Caregiver")
    _grant(db_session, staff, mother, caregiver, expires=NOW - timedelta(seconds=1))
    assert _allowed(db_session, mother, caregiver) is False


def test_revocation_denies_on_the_next_check(db_session):
    staff, (mother, caregiver) = _people(db_session, "Synthetic Mother", "Synthetic Caregiver")
    grant = _grant(db_session, staff, mother, caregiver)
    assert _allowed(db_session, mother, caregiver) is True

    grant.revoked_at = NOW
    grant.revoked_by_staff_user_id = staff.id
    grant.revoke_reason = RevokeReason.REQUESTED_BY_SUBJECT
    db_session.commit()
    assert _allowed(db_session, mother, caregiver) is False


def test_another_person_on_the_same_phone_is_denied(db_session):
    """Two women on one handset: a grant to one caregiver gives nothing to
    anyone else, whatever phone they use (identity is the person id)."""
    staff, (mother, caregiver, sister) = _people(
        db_session, "Synthetic Mother", "Synthetic Caregiver", "Synthetic Sister"
    )
    _grant(db_session, staff, mother, caregiver)
    assert _allowed(db_session, mother, sister) is False
    assert _allowed(db_session, sister, caregiver) is False


def test_self_grant_is_rejected_by_the_database(db_session):
    staff, (mother,) = _people(db_session, "Synthetic Mother")
    with pytest.raises(IntegrityError, match="ck_caregiver_grant_not_self"):
        _grant(db_session, staff, mother, mother)
    db_session.rollback()


def test_unknown_scope_is_rejected_by_the_database(db_session):
    staff, (mother, caregiver) = _people(db_session, "Synthetic Mother", "Synthetic Caregiver")
    grant = CaregiverGrant(
        subject_person_id=mother.id,
        grantee_person_id=caregiver.id,
        scopes=["REPORTS"],
        recorded_by_staff_user_id=staff.id,
        verified_by_staff_user_id=staff.id,
        verification_method=VerificationMethod.IN_PERSON_DOCUMENT,
        expires_at=NOW + timedelta(days=1),
    )
    db_session.add(grant)
    with pytest.raises(IntegrityError, match="ck_caregiver_grant_known_scopes"):
        db_session.commit()
    db_session.rollback()


def test_half_recorded_revocation_is_rejected(db_session):
    staff, (mother, caregiver) = _people(db_session, "Synthetic Mother", "Synthetic Caregiver")
    grant = _grant(db_session, staff, mother, caregiver)
    grant.revoked_at = NOW  # no who / why
    with pytest.raises(IntegrityError, match="ck_caregiver_grant_revocation_complete"):
        db_session.commit()
    db_session.rollback()


def test_app_role_cannot_delete_grants(db_session):
    staff, (mother, caregiver) = _people(db_session, "Synthetic Mother", "Synthetic Caregiver")
    grant = _grant(db_session, staff, mother, caregiver)
    app_url = os.environ["DATABASE_URL_APP"].replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(app_url, autocommit=True) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("DELETE FROM caregiver_grant WHERE id = %s", (grant.id,))
