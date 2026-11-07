import type { Membership } from "../api/client";

// Mirrors the server's CLINICIAN_ROLES (app/domain/transitions.py). Used only
// to hide buttons; the server refuses clinician-only actions regardless.
export const CLINICIAN_ROLES: ReadonlySet<string> = new Set(["DOCTOR"]);

export function rolesAt(memberships: readonly Membership[], facilityId: string): string[] {
  return memberships.filter((m) => m.facility_id === facilityId).map((m) => m.role);
}

export function isClinicianAt(memberships: readonly Membership[], facilityId: string): boolean {
  return rolesAt(memberships, facilityId).some((r) => CLINICIAN_ROLES.has(r));
}
