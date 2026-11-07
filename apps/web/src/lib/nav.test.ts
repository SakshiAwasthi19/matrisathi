import { Users } from "lucide-react";
import { describe, expect, it } from "vitest";
import type { Membership } from "../api/client";
import { NAV_ITEMS, navItemsFor, rolesOf, type NavItem } from "./nav";

const membership = (role: string): Membership => ({ facility_id: "f", facility_name: "F", role });

describe("role-aware navigation", () => {
  it("collects roles across all of a user's facilities", () => {
    expect(rolesOf([membership("ASHA"), membership("DOCTOR"), membership("ASHA")])).toEqual(
      new Set(["ASHA", "DOCTOR"]),
    );
  });

  it("shows every current page to every role", () => {
    for (const role of ["ASHA", "NURSE", "COORDINATOR", "DOCTOR"]) {
      expect(navItemsFor(new Set([role]))).toEqual([...NAV_ITEMS]);
      expect(navItemsFor(new Set([role])).map((i) => i.to)).toEqual(["/", "/today", "/mothers", "/contacts", "/messages", "/children", "/insights"]);
    }
  });

  it("shows nothing to a user with no facility membership", () => {
    expect(navItemsFor(new Set())).toEqual([]);
  });

  it("hides a link from roles not listed on it", () => {
    const items: NavItem[] = [
      { labelKey: "a", to: "/a", icon: Users, group: "work", roles: ["DOCTOR"] },
      { labelKey: "b", to: "/b", icon: Users, group: "work", roles: ["ASHA", "DOCTOR"] },
    ];
    expect(navItemsFor(new Set(["ASHA"]), items).map((i) => i.to)).toEqual(["/b"]);
    expect(navItemsFor(new Set(["DOCTOR"]), items).map((i) => i.to)).toEqual(["/a", "/b"]);
  });
});

describe("preview screens", () => {
  it("every preview item is marked, and only preview group items are", () => {
    for (const item of NAV_ITEMS) {
      expect(Boolean(item.preview)).toBe(item.group === "preview");
    }
  });
});
