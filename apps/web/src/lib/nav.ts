import { BarChart3, Baby, BookUser, LayoutDashboard, ListChecks, MessageCircle, ShieldCheck, Users, UsersRound, type LucideIcon } from "lucide-react";
import type { Membership } from "../api/client";

export type StaffRole = "ASHA" | "ANM" | "NURSE" | "COORDINATOR" | "DOCTOR";

export const ALL_ROLES: readonly StaffRole[] = ["ASHA", "ANM", "NURSE", "COORDINATOR", "DOCTOR"];

export type NavGroup = "work" | "network" | "preview" | "manage";

export interface NavItem {
  /** i18n key for the link text. */
  labelKey: string;
  to: string;
  icon: LucideIcon;
  group: NavGroup;
  /** Roles that see this link. The server still enforces access on every request. */
  roles: readonly StaffRole[];
  /** A preview screen built on sample data; labelled as such everywhere. */
  preview?: boolean;
}

// Every role currently sees the same pages: role capabilities start in SG2
// (D04 section 9). New screens add their own role lists here.
export const NAV_ITEMS: readonly NavItem[] = [
  { labelKey: "nav.overview", to: "/", icon: LayoutDashboard, group: "work", roles: ALL_ROLES },
  { labelKey: "nav.today", to: "/today", icon: ListChecks, group: "work", roles: ALL_ROLES },
  { labelKey: "nav.mothersShort", to: "/mothers", icon: Users, group: "work", roles: ALL_ROLES },
  { labelKey: "nav.workload", to: "/workload", icon: UsersRound, group: "work", roles: ALL_ROLES },
  { labelKey: "nav.contacts", to: "/contacts", icon: BookUser, group: "network", roles: ALL_ROLES },
  { labelKey: "nav.messages", to: "/messages", icon: MessageCircle, group: "preview", roles: ALL_ROLES, preview: true },
  { labelKey: "nav.children", to: "/children", icon: Baby, group: "preview", roles: ALL_ROLES, preview: true },
  { labelKey: "nav.insights", to: "/insights", icon: BarChart3, group: "preview", roles: ALL_ROLES, preview: true },
];

export function rolesOf(memberships: readonly Membership[]): Set<string> {
  return new Set(memberships.map((m) => m.role));
}

/** Links shown to a user holding any of `roles` (at any of their facilities). */
export function navItemsFor(roles: Set<string>, items: readonly NavItem[] = NAV_ITEMS): NavItem[] {
  return items.filter((item) => item.roles.some((role) => roles.has(role)));
}

/** Shown only to organisation admins (an explicit grant, not a facility role). */
export const ADMIN_NAV_ITEM: NavItem = {
  labelKey: "nav.admin",
  to: "/admin",
  icon: ShieldCheck,
  group: "manage",
  roles: [],
};
