import type { Membership } from "../api/client";

// Clinical capabilities from the server's role-capability table
// (apps/api/app/domain/permissions.py). Used only to hide buttons; the server
// refuses anything the caller's role may not do, whatever the screen shows.
export const CLINICAL_CAPABILITIES: ReadonlySet<string> = new Set([
  "CONFIRM_DATING",
  "PUBLISH_CARE_PLAN",
  "REVIEW_REPORT",
  "REVIEW_PRESCRIPTION",
  "RECORD_CLINICAL_FINDING",
  "CREATE_REFERRAL",
  "CHOOSE_REFERRAL_SITE",
]);

// Fallback for a /me response without capabilities (older server).
const CLINICIAN_ROLES: ReadonlySet<string> = new Set(["DOCTOR"]);

export function rolesAt(memberships: readonly Membership[], facilityId: string): string[] {
  return memberships.filter((m) => m.facility_id === facilityId).map((m) => m.role);
}

function holds(m: Membership, capability: string): boolean {
  if (m.capabilities) return m.capabilities.includes(capability);
  return CLINICAL_CAPABILITIES.has(capability) ? CLINICIAN_ROLES.has(m.role) : true;
}

/** True if the caller's role at this facility holds `capability`. */
export function canAt(memberships: readonly Membership[], facilityId: string, capability: string): boolean {
  return memberships.some((m) => m.facility_id === facilityId && holds(m, capability));
}

/** True if the caller holds any clinical capability at this facility. */
export function isClinicianAt(memberships: readonly Membership[], facilityId: string): boolean {
  return memberships.some(
    (m) => m.facility_id === facilityId && [...CLINICAL_CAPABILITIES].some((c) => holds(m, c)),
  );
}
