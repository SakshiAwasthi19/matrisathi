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
    }
  });

  it("shows nothing to a user with no facility membership", () => {
    expect(navItemsFor(new Set())).toEqual([]);
  });

  it("hides a link from roles not listed on it", () => {
    const items: NavItem[] = [
      { labelKey: "a", to: "/a", roles: ["DOCTOR"] },
      { labelKey: "b", to: "/b", roles: ["ASHA", "DOCTOR"] },
    ];
    expect(navItemsFor(new Set(["ASHA"]), items).map((i) => i.to)).toEqual(["/b"]);
    expect(navItemsFor(new Set(["DOCTOR"]), items).map((i) => i.to)).toEqual(["/a", "/b"]);
  });
});
