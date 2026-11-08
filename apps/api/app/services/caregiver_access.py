"""The single server-side check for caregiver access (F015, T010, D07).

Every future patient/caregiver endpoint must call `caregiver_access_allowed`
on every request and every download, never cache its answer, and treat
False as "not found" for the caller.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.models.caregiver import CaregiverGrant, CaregiverScope


def caregiver_access_allowed(
    db: Session,
    *,
    subject_person_id: uuid.UUID,
    grantee_person_id: uuid.UUID,
    scope: CaregiverScope,
    now: datetime | None = None,
    config: Settings = settings,
) -> bool:
    """True only if patient access is switched on and a grant exists from
    the subject to this grantee that covers `scope`, has not expired and has
    not been revoked. Phone numbers play no part: identities are person ids."""
    if not config.patient_access_enabled:
        return False
    if subject_person_id == grantee_person_id:
        return False
    moment = now or datetime.now(timezone.utc)
    grant = db.execute(
        select(CaregiverGrant.id)
        .where(
            CaregiverGrant.subject_person_id == subject_person_id,
            CaregiverGrant.grantee_person_id == grantee_person_id,
            CaregiverGrant.scopes.contains([scope.value]),
            CaregiverGrant.revoked_at.is_(None),
            CaregiverGrant.expires_at > moment,
        )
        .limit(1)
    ).first()
    return grant is not None


def grant_state(grant: CaregiverGrant, now: datetime) -> str:
    """REVOKED, EXPIRED or ACTIVE at `now`."""
    if grant.revoked_at is not None:
        return "REVOKED"
    if grant.expires_at <= now:
        return "EXPIRED"
    return "ACTIVE"


def caregiver_may_receive(
    db: Session,
    *,
    subject_person_id: uuid.UUID,
    grantee_person_id: uuid.UUID,
    scope: CaregiverScope,
    now: datetime | None = None,
) -> bool:
    """Staff-side check (D07 option 3): may staff share `scope` with this
    adult on the mother's behalf? Same grant rules as caregiver_access_allowed,
    but not tied to PATIENT_ACCESS_ENABLED, which gates patient sign-in only
    (none exists under option 3). Ask again before every share; never cache."""
    if subject_person_id == grantee_person_id:
        return False
    moment = now or datetime.now(timezone.utc)
    grant = db.execute(
        select(CaregiverGrant.id)
        .where(
            CaregiverGrant.subject_person_id == subject_person_id,
            CaregiverGrant.grantee_person_id == grantee_person_id,
            CaregiverGrant.scopes.contains([scope.value]),
            CaregiverGrant.revoked_at.is_(None),
            CaregiverGrant.expires_at > moment,
        )
        .limit(1)
    ).first()
    return grant is not None
