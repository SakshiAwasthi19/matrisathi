"""Organization-admin authority is an explicit grant (OrganizationAdmin),
never inferred from a facility-level StaffMembership role. There is no
"ADMIN" StaffRole at all — see app/models/staff.py StaffRole and
app/models/organization.py OrganizationAdmin.

This slice has no HTTP surface for org administration yet (no admin CRUD
API — out of scope for the demonstrable flow), so these tests exercise the
`require_org_admin` dependency directly, the same way a future admin router
would use it.
"""

from fastapi import HTTPException
import pytest

from app.core.deps import require_org_admin
from tests.conftest import CSRF_HEADERS
from tests.factories import make_facility, make_org, make_org_admin, make_staff, make_membership


def test_org_admin_grant_is_required_not_inferred_from_membership_role(db_session):
    org = make_org(db_session)
    facility = make_facility(db_session, org)
    staff = make_staff(db_session, "coord_only")
    # This staff member has an ordinary facility membership, but NO
    # OrganizationAdmin grant. There is no facility-level "ADMIN" role to
    # accidentally satisfy this check with.
    make_membership(db_session, staff, facility)

    with pytest.raises(HTTPException) as exc_info:
        require_org_admin(db_session, staff, org.id)
    assert exc_info.value.status_code == 404


def test_org_admin_of_org_a_cannot_administer_org_b(db_session):
    org_a = make_org(db_session, "Org A")
    org_b = make_org(db_session, "Org B")
    admin = make_staff(db_session, "admin_a")
    make_org_admin(db_session, admin, org_a)

    # Works for their own org.
    assert require_org_admin(db_session, admin, org_a.id) is not None

    # Does not carry over to a different organization.
    with pytest.raises(HTTPException) as exc_info:
        require_org_admin(db_session, admin, org_b.id)
    assert exc_info.value.status_code == 404


def test_revoked_org_admin_grant_loses_authority(db_session):
    from datetime import datetime, timezone

    org = make_org(db_session)
    admin = make_staff(db_session, "admin_revoked")
    grant = make_org_admin(db_session, admin, org)

    assert require_org_admin(db_session, admin, org.id) is not None

    grant.revoked_at = datetime.now(timezone.utc)
    db_session.add(grant)
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        require_org_admin(db_session, admin, org.id)
    assert exc_info.value.status_code == 404


def test_org_admin_authority_alone_grants_no_clinical_record_access(client, db_session):
    """T005: "No automatic clinical access from admin title." Being an
    OrganizationAdmin is a distinct grant from a facility StaffMembership
    (see app/models/organization.py) — an org admin with no membership of
    their own still cannot register a person or read records, because that
    requires the ordinary facility-membership check, which org-admin status
    does not satisfy."""
    org = make_org(db_session)
    facility = make_facility(db_session, org)
    admin = make_staff(db_session, "admin_no_membership")
    make_org_admin(db_session, admin, org)  # org admin, but NO StaffMembership anywhere

    resp = client.post("/api/v1/auth/login", json={"username": "admin_no_membership", "password": "synthetic-password-123"}, headers=CSRF_HEADERS)
    assert resp.status_code == 200

    resp = client.post(
        "/api/v1/people",
        json={"full_name": "Should be denied", "facility_id": str(facility.id), "phone": "+917777700001"},
        headers=CSRF_HEADERS,
    )
    assert resp.status_code == 404
