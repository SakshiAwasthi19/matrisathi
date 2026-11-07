"""T008 state rules as pure functions: every allowed and rejected move."""

import itertools

import pytest

from app.domain.transitions import (
    APPOINTMENT_TRANSITIONS,
    CARE_PLAN_TRANSITIONS,
    CLINICIAN_ONLY,
    INVESTIGATION_TRANSITIONS,
    TASK_TRANSITIONS,
    ClinicianOnlyError,
    StaleVersionError,
    TransitionError,
    check_transition,
    check_version,
    is_clinician,
)
from app.models.care import AppointmentStatus as A
from app.models.care import CarePlanStatus as P
from app.models.care import InvestigationStatus as I
from app.models.care import TaskStatus as T

DOCTOR = ["DOCTOR"]
NON_CLINICIANS = [["ASHA"], ["NURSE"], ["COORDINATOR"], []]

MACHINES = {
    "appointment": (APPOINTMENT_TRANSITIONS, list(A)),
    "task": (TASK_TRANSITIONS, list(T)),
    "investigation": (INVESTIGATION_TRANSITIONS, list(I)),
    "care_plan": (CARE_PLAN_TRANSITIONS, list(P)),
}


def _all_pairs():
    for name, (table, states) in MACHINES.items():
        for current, target in itertools.product(states, states):
            yield name, table, current, target


@pytest.mark.parametrize(("name", "table", "current", "target"), list(_all_pairs()))
def test_every_pair_is_allowed_or_rejected_exactly_as_listed(name, table, current, target):
    allowed = target in table[current]
    if not allowed:
        with pytest.raises(TransitionError):
            check_transition(table, current, target, DOCTOR)
    else:
        check_transition(table, current, target, DOCTOR)  # a clinician may make every listed move


def test_every_state_is_covered():
    for table, states in MACHINES.values():
        assert set(table) == set(states)


@pytest.mark.parametrize("roles", NON_CLINICIANS)
@pytest.mark.parametrize(("current", "target"), sorted(CLINICIAN_ONLY, key=lambda p: (p[0].value, p[1].value)))
def test_clinician_only_moves_are_refused_for_non_clinicians(roles, current, target):
    table = INVESTIGATION_TRANSITIONS if isinstance(current, I) else CARE_PLAN_TRANSITIONS
    with pytest.raises(ClinicianOnlyError):
        check_transition(table, current, target, roles)


def test_marking_a_report_reviewed_needs_a_clinician():
    with pytest.raises(ClinicianOnlyError):
        check_transition(INVESTIGATION_TRANSITIONS, I.RECEIVED, I.REVIEWED, ["COORDINATOR"])
    check_transition(INVESTIGATION_TRANSITIONS, I.RECEIVED, I.REVIEWED, ["COORDINATOR", "DOCTOR"])


def test_an_upload_is_never_reviewed_without_being_received_first():
    for start in (I.REQUESTED, I.PERFORMED):
        with pytest.raises(TransitionError):
            check_transition(INVESTIGATION_TRANSITIONS, start, I.REVIEWED, DOCTOR)


def test_outside_report_can_be_received_without_known_earlier_steps():
    check_transition(INVESTIGATION_TRANSITIONS, I.REQUESTED, I.RECEIVED, ["COORDINATOR"])


def test_final_states_cannot_move():
    for table, states in MACHINES.values():
        for state in states:
            if not table[state]:
                for target in states:
                    with pytest.raises(TransitionError):
                        check_transition(table, state, target, DOCTOR)


def test_reschedule_keeps_the_old_appointment_final():
    check_transition(APPOINTMENT_TRANSITIONS, A.CONFIRMED, A.RESCHEDULED, ["COORDINATOR"])
    with pytest.raises(TransitionError):
        check_transition(APPOINTMENT_TRANSITIONS, A.RESCHEDULED, A.CONFIRMED, ["COORDINATOR"])


def test_clinician_role_list_is_doctor_only():
    assert is_clinician(["DOCTOR"])
    assert not any(is_clinician(r) for r in NON_CLINICIANS)


def test_stale_version_is_rejected():
    check_version(3, 3)
    with pytest.raises(StaleVersionError):
        check_version(4, 3)
