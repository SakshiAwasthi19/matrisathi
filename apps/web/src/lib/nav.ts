import type { Membership } from "../api/client";

export type StaffRole = "ASHA" | "NURSE" | "COORDINATOR" | "DOCTOR";

export const ALL_ROLES: readonly StaffRole[] = ["ASHA", "NURSE", "COORDINATOR", "DOCTOR"];

export interface NavItem {
  /** i18n key for the link text. */
  labelKey: string;
  to: string;
  /** Roles that see this link. The server still enforces access on every request. */
  roles: readonly StaffRole[];
}

// Every role currently sees the same pages: role capabilities start in SG2
// (D04 section 9). New screens add their own role lists here.
export const NAV_ITEMS: readonly NavItem[] = [{ labelKey: "nav.mothers", to: "/", roles: ALL_ROLES }];

export function rolesOf(memberships: readonly Membership[]): Set<string> {
  return new Set(memberships.map((m) => m.role));
}

/** Links shown to a user holding any of `roles` (at any of their facilities). */
export function navItemsFor(roles: Set<string>, items: readonly NavItem[] = NAV_ITEMS): NavItem[] {
  return items.filter((item) => item.roles.some((role) => roles.has(role)));
}
