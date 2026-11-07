import { describe, expect, it } from "vitest";
import { ApiError, type Membership } from "../api/client";
import { formatDate, isStaleConflict, todayIso } from "./format";
import { isClinicianAt, rolesAt } from "./roles";

const m = (facility_id: string, role: string): Membership => ({ facility_id, facility_name: facility_id, role });

describe("clinician check is per facility", () => {
  const memberships = [m("A", "DOCTOR"), m("B", "COORDINATOR")];

  it("lists roles at one facility only", () => {
    expect(rolesAt(memberships, "A")).toEqual(["DOCTOR"]);
    expect(rolesAt(memberships, "C")).toEqual([]);
  });

  it("a doctor at A is not a clinician at B", () => {
    expect(isClinicianAt(memberships, "A")).toBe(true);
    expect(isClinicianAt(memberships, "B")).toBe(false);
  });

  it("nurses, ASHAs and coordinators are not clinicians", () => {
    for (const role of ["NURSE", "ASHA", "COORDINATOR"]) {
      expect(isClinicianAt([m("A", role)], "A")).toBe(false);
    }
  });
});

describe("dates", () => {
  it("formats a calendar date without shifting it", () => {
    expect(formatDate("2026-11-07", "en-GB")).toBe("7 Nov 2026");
    expect(formatDate(null)).toBe("");
  });

  it("gives today's date for date inputs", () => {
    expect(todayIso(new Date(2026, 0, 5))).toBe("2026-01-05");
  });
});

describe("stale update detection", () => {
  it("recognises the server's stale-version conflict", () => {
    expect(isStaleConflict(new ApiError(409, "This record was changed by someone else. Reload it and try again."))).toBe(true);
  });

  it("ignores other conflicts and errors", () => {
    expect(isStaleConflict(new ApiError(409, "Cannot change from REQUESTED to ATTENDED."))).toBe(false);
    expect(isStaleConflict(new ApiError(403, "Only a clinician can do this."))).toBe(false);
  });
});
