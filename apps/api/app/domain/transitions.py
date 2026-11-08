"""State-transition rules for Phase 1 records (T008), as plain functions.

Routers call `check_transition` before changing a status. It rejects any
move not listed here, and any clinician-only move by a non-clinician.
Clinician-only moves record clinical decisions; they never compute one.
"""

from collections.abc import Iterable, Mapping
from enum import Enum

from app.domain.permissions import CLINICAL, ROLE_CAPABILITIES, Capability, has_capability
from app.models.care import AppointmentStatus, CarePlanStatus, InvestigationStatus, TaskStatus
from app.models.records import ReferralStatus

# Roles that hold any clinical capability. Derived from the single
# role-capability table (app/domain/permissions.py); change it there.
CLINICIAN_ROLES: frozenset[str] = frozenset(r for r, caps in ROLE_CAPABILITIES.items() if caps & CLINICAL)

A = AppointmentStatus
APPOINTMENT_TRANSITIONS: Mapping[Enum, frozenset[Enum]] = {
    A.REQUESTED: frozenset({A.CONFIRMED, A.CANCELLED}),
    A.CONFIRMED: frozenset({A.ATTENDED, A.MISSED, A.RESCHEDULED, A.CANCELLED}),
    # Final states: a reschedule creates a new appointment linked by
    # previous_appointment_id; the old one is kept as it was.
    A.ATTENDED: frozenset(),
    A.MISSED: frozenset(),
    A.RESCHEDULED: frozenset(),
    A.CANCELLED: frozenset(),
}

T = TaskStatus
TASK_TRANSITIONS: Mapping[Enum, frozenset[Enum]] = {
    T.NEW: frozenset({T.ASSIGNED, T.CANCELLED}),
    T.ASSIGNED: frozenset({T.AWAITING_PATIENT, T.COMPLETED, T.CANCELLED, T.ASSIGNED}),  # reassignment
    T.AWAITING_PATIENT: frozenset({T.ASSIGNED, T.COMPLETED, T.CANCELLED}),
    T.COMPLETED: frozenset(),
    T.CANCELLED: frozenset(),
}

Inv = InvestigationStatus
INVESTIGATION_TRANSITIONS: Mapping[Enum, frozenset[Enum]] = {
    # An outside report can arrive without a known request or performed
    # date, so REQUESTED -> RECEIVED is allowed directly.
    Inv.REQUESTED: frozenset({Inv.PERFORMED, Inv.RECEIVED}),
    Inv.PERFORMED: frozenset({Inv.RECEIVED}),
    Inv.RECEIVED: frozenset({Inv.REVIEWED}),
    Inv.REVIEWED: frozenset(),
}

P = CarePlanStatus
CARE_PLAN_TRANSITIONS: Mapping[Enum, frozenset[Enum]] = {
    P.ACTIVE: frozenset({P.SUPERSEDED, P.CANCELLED}),
    P.SUPERSEDED: frozenset(),
    P.CANCELLED: frozenset(),
}

R = ReferralStatus
REFERRAL_TRANSITIONS: Mapping[Enum, frozenset[Enum]] = {
    # Each step records something that happened; CLOSED always needs a reason.
    # Nothing (e.g. a message being sent) closes a referral by itself.
    R.SENT: frozenset({R.CONTACTED, R.ATTENDED, R.CLOSED}),
    R.CONTACTED: frozenset({R.ATTENDED, R.CLOSED}),
    R.ATTENDED: frozenset({R.ADVICE_RECEIVED, R.CLOSED}),
    R.ADVICE_RECEIVED: frozenset({R.FOLLOW_UP_COMPLETED, R.CLOSED}),
    R.FOLLOW_UP_COMPLETED: frozenset(),
    R.CLOSED: frozenset(),
}

# (from, to) moves that need a clinical capability, and which one.
CLINICIAN_ONLY: Mapping[tuple[Enum, Enum], Capability] = {
    (Inv.RECEIVED, Inv.REVIEWED): Capability.REVIEW_REPORT,  # marking a report reviewed (F009)
    (P.ACTIVE, P.SUPERSEDED): Capability.PUBLISH_CARE_PLAN,  # replacing a published plan (F005)
    (P.ACTIVE, P.CANCELLED): Capability.PUBLISH_CARE_PLAN,
}


class TransitionError(ValueError):
    """The move is not allowed from the current state."""


class ClinicianOnlyError(PermissionError):
    """The move is allowed, but only for a clinician."""


class StaleVersionError(Exception):
    """The record changed since the caller read it (optimistic concurrency)."""


def is_clinician(roles: Iterable[str]) -> bool:
    return any(role in CLINICIAN_ROLES for role in roles)


def check_transition(
    transitions: Mapping[Enum, frozenset[Enum]], current: Enum, target: Enum, roles: Iterable[str]
) -> None:
    """Raises TransitionError or ClinicianOnlyError; returns None if allowed."""
    if target not in transitions.get(current, frozenset()):
        raise TransitionError(f"{current.value} -> {target.value} is not allowed")
    needed = CLINICIAN_ONLY.get((current, target))
    if needed is not None and not has_capability(roles, needed):
        raise ClinicianOnlyError(f"{current.value} -> {target.value} is a clinician-only action")


def check_version(current_version: int, expected_version: int) -> None:
    """Raises StaleVersionError unless the caller saw the current version."""
    if current_version != expected_version:
        raise StaleVersionError(f"expected version {expected_version}, record is at {current_version}")
