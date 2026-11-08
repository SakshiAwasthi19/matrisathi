"""Who may do what: the single role-capability table (F004, T005).

Every role-dependent check in the API asks `has_capability`; nothing else
compares role names. The table below reproduces the rules in force before it
existed (only DOCTOR records clinical decisions; every facility member does
the rest), so introducing it changed no behaviour.

The doctor's M008 answers (ANM as its own role, what an ASHA may do and see)
and the tech lead's D04 review change this table, not the routers.

Capabilities are checked against the caller's role *at the record's
facility*, live on every request. A capability never grants access to a
facility the caller is not a member of: facility membership is checked first,
separately (deps.require_facility_membership).
"""

import enum
from collections.abc import Iterable, Mapping


class Capability(str, enum.Enum):
    # --- clinical decisions (recorded by a person, never computed) ---
    CONFIRM_DATING = "CONFIRM_DATING"  # confirm or correct pregnancy dating (F005)
    PUBLISH_CARE_PLAN = "PUBLISH_CARE_PLAN"  # publish, replace or cancel a care plan (F005)
    REVIEW_REPORT = "REVIEW_REPORT"  # mark a received report reviewed (F009)
    REVIEW_PRESCRIPTION = "REVIEW_PRESCRIPTION"  # transcribe or flag an instruction (F010)
    RECORD_CLINICAL_FINDING = "RECORD_CLINICAL_FINDING"  # clinician-entered finding (F012)
    CREATE_REFERRAL = "CREATE_REFERRAL"  # destination and urgency (F011)
    CHOOSE_REFERRAL_SITE = "CHOOSE_REFERRAL_SITE"  # referral site on the birth plan (F013)
    # --- everyday work ---
    REGISTER_MOTHER = "REGISTER_MOTHER"  # register a person, open an episode (F002)
    VIEW_REPORTED_HISTORY = "VIEW_REPORTED_HISTORY"  # reported history and allergies (M008 Q12)
    MANAGE_CAREGIVER_GRANTS = "MANAGE_CAREGIVER_GRANTS"  # record and revoke family access (F015)
    HAND_OVER_WORK = "HAND_OVER_WORK"  # move an unavailable person's open work (F008, F038)
    # --- messaging (SG3) ---
    SEND_MESSAGES = "SEND_MESSAGES"  # queue reminders, reply to linked inbox items (F017, F018)
    MANAGE_CONTACT_PREFERENCES = "MANAGE_CONTACT_PREFERENCES"  # consent, opt-out, language, hours (F016, F020)
    # The unlinked queue shows messages from numbers nobody has confirmed yet,
    # so only coordinators see it and link items after an identity check (M018).
    TRIAGE_UNLINKED_INBOX = "TRIAGE_UNLINKED_INBOX"


CLINICAL: frozenset[Capability] = frozenset(
    {
        Capability.CONFIRM_DATING,
        Capability.PUBLISH_CARE_PLAN,
        Capability.REVIEW_REPORT,
        Capability.REVIEW_PRESCRIPTION,
        Capability.RECORD_CLINICAL_FINDING,
        Capability.CREATE_REFERRAL,
        Capability.CHOOSE_REFERRAL_SITE,
    }
)
COORDINATION: frozenset[Capability] = frozenset({Capability.TRIAGE_UNLINKED_INBOX})
EVERYDAY: frozenset[Capability] = frozenset(Capability) - CLINICAL - COORDINATION

# Role -> capabilities. ANM starts identical to NURSE until the doctor answers
# M008 question 9; ASHA keeps every everyday capability until questions 11-12.
ROLE_CAPABILITIES: Mapping[str, frozenset[Capability]] = {
    "DOCTOR": CLINICAL | EVERYDAY,
    "NURSE": EVERYDAY,
    "ANM": EVERYDAY,
    "COORDINATOR": EVERYDAY | COORDINATION,
    "ASHA": EVERYDAY,
}

# Shown to the user when a capability is missing. Clinical ones keep the
# wording staff already see.
DENIED_MESSAGE: Mapping[Capability, str] = {
    **{c: "Only a clinician can do this." for c in CLINICAL},
    Capability.CHOOSE_REFERRAL_SITE: "Only a clinician can choose the referral site.",
    Capability.REGISTER_MOTHER: "Your role cannot register mothers or open pregnancy records.",
    Capability.VIEW_REPORTED_HISTORY: "Your role cannot see reported history.",
    Capability.MANAGE_CAREGIVER_GRANTS: "Your role cannot change family access.",
    Capability.HAND_OVER_WORK: "Your role cannot hand over other people's work.",
    Capability.SEND_MESSAGES: "Your role cannot send messages.",
    Capability.MANAGE_CONTACT_PREFERENCES: "Your role cannot change contact preferences.",
    Capability.TRIAGE_UNLINKED_INBOX: "Only a coordinator can see and link messages from unconfirmed numbers.",
}


def capabilities_of(roles: Iterable[str]) -> frozenset[Capability]:
    out: frozenset[Capability] = frozenset()
    for role in roles:
        out |= ROLE_CAPABILITIES.get(role, frozenset())
    return out


def has_capability(roles: Iterable[str], capability: Capability) -> bool:
    return capability in capabilities_of(roles)
