"""Seeds one synthetic organization, facility and coordinator for manual
demonstration. Safe to run repeatedly (skips if already seeded).

Usage: uv run python -m app.scripts.seed_dev

Outside development (ENV is not "development"), the committed password is
refused: SEED_PASSWORD must come from the environment, and the password is
never printed.
"""

import os
from collections.abc import Mapping

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.core.startup_checks import is_development
from app.models.facility import Facility
from app.models.organization import Organization
from app.models.staff import StaffMembership, StaffRole, StaffUser

DEV_USERNAME = "coordinator1"
DEV_DOCTOR_USERNAME = "doctor1"
DEV_PASSWORD = "synthetic-dev-password-123"  # noqa: S105 — synthetic, local dev only
MIN_SEED_PASSWORD_LENGTH = 12


class UnsafeSeedError(RuntimeError):
    pass


def resolve_seed_password(env: str, environ: Mapping[str, str]) -> str:
    """Development: the committed synthetic password. Anywhere else:
    SEED_PASSWORD from the environment, which must not be the committed one."""
    if is_development(env):
        return DEV_PASSWORD
    password = environ.get("SEED_PASSWORD", "")
    if password == DEV_PASSWORD or len(password) < MIN_SEED_PASSWORD_LENGTH:
        raise UnsafeSeedError(
            f"Refusing to seed with ENV={env.strip()!r}: set SEED_PASSWORD in the environment "
            f"(at least {MIN_SEED_PASSWORD_LENGTH} characters, not the committed dev password)"
        )
    return password


def _ensure_staff(db, username: str, full_name: str, role: StaffRole, facility_id, password: str) -> bool:  # type: ignore[no-untyped-def]
    """Creates the user with a membership at the facility unless the
    username already exists. Returns True if created."""
    if db.query(StaffUser).filter(StaffUser.username == username).first():
        return False
    user = StaffUser(username=username, full_name=full_name, phone=None, password_hash=hash_password(password), active=True)
    db.add(user)
    db.flush()
    db.add(StaffMembership(staff_user_id=user.id, facility_id=facility_id, role=role, active=True))
    return True


def main() -> None:
    password = resolve_seed_password(settings.env, os.environ)
    show_password = is_development(settings.env)

    def login_line(username: str) -> str:
        return (
            f"username={username!r}, password={password!r}"
            if show_password
            else f"username={username!r} (password from SEED_PASSWORD, not shown)"
        )

    db = SessionLocal()
    try:
        coordinator = db.query(StaffUser).filter(StaffUser.username == DEV_USERNAME).first()
        if coordinator is None:
            org = Organization(name="Synthetic Pilot NGO")
            db.add(org)
            db.flush()
            facility = Facility(organization_id=org.id, name="Synthetic Rural Facility", active=True)
            db.add(facility)
            db.flush()
            _ensure_staff(db, DEV_USERNAME, "Synthetic Coordinator", StaffRole.COORDINATOR, facility.id, password)
            facility_id = facility.id
        else:
            membership = db.query(StaffMembership).filter(StaffMembership.staff_user_id == coordinator.id).first()
            assert membership is not None, "coordinator1 exists without a facility membership"
            facility_id = membership.facility_id

        # A synthetic clinician, so plan publishing and dating confirmation
        # (DOCTOR-only) can be built and demonstrated.
        created_doctor = _ensure_staff(db, DEV_DOCTOR_USERNAME, "Synthetic Doctor", StaffRole.DOCTOR, facility_id, password)
        db.commit()

        print("Synthetic data ready:")
        print(f"  coordinator  = {login_line(DEV_USERNAME)}")
        print(f"  doctor       = {login_line(DEV_DOCTOR_USERNAME)}" + (" (created)" if created_doctor else ""))
    finally:
        db.close()


if __name__ == "__main__":
    main()
