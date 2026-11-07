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


def main() -> None:
    password = resolve_seed_password(settings.env, os.environ)
    show_password = is_development(settings.env)
    login_line = (
        f"username={DEV_USERNAME!r}, password={password!r}"
        if show_password
        else f"username={DEV_USERNAME!r} (password from SEED_PASSWORD, not shown)"
    )

    db = SessionLocal()
    try:
        existing = db.query(StaffUser).filter(StaffUser.username == DEV_USERNAME).first()
        if existing:
            print(f"Already seeded. Login with {login_line}")
            return

        org = Organization(name="Synthetic Pilot NGO")
        db.add(org)
        db.flush()

        facility = Facility(organization_id=org.id, name="Synthetic Rural Facility", active=True)
        db.add(facility)
        db.flush()

        staff = StaffUser(
            username=DEV_USERNAME,
            full_name="Synthetic Coordinator",
            phone="+910000000001",
            password_hash=hash_password(password),
            active=True,
        )
        db.add(staff)
        db.flush()

        db.add(
            StaffMembership(
                staff_user_id=staff.id,
                facility_id=facility.id,
                role=StaffRole.COORDINATOR,
                active=True,
            )
        )
        db.commit()

        print("Seeded synthetic data:")
        print(f"  organization = {org.name} ({org.id})")
        print(f"  facility     = {facility.name} ({facility.id})")
        print(f"  login        = {login_line}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
