import { describe, expect, it } from "vitest";
import { attentionBucketsFor } from "./attention";

describe("attention buckets by role", () => {
  it("gives a doctor the review work", () => {
    expect(attentionBucketsFor(new Set(["DOCTOR"]))).toEqual([
      "reports_to_review",
      "prescriptions_to_review",
      "dating_not_confirmed",
      "no_care_plan",
    ]);
  });

  it("gives field roles contact and referral follow-up only", () => {
    expect(attentionBucketsFor(new Set(["ASHA"]))).toEqual(["contact_not_confirmed", "referrals_in_progress"]);
    expect(attentionBucketsFor(new Set(["NURSE"]))).toEqual(["contact_not_confirmed", "referrals_in_progress"]);
  });

  it("merges several roles, clinician items first, without repeats", () => {
    expect(attentionBucketsFor(new Set(["COORDINATOR", "DOCTOR"]))).toEqual([
      "reports_to_review",
      "prescriptions_to_review",
      "dating_not_confirmed",
      "no_care_plan",
      "contact_not_confirmed",
      "referrals_in_progress",
    ]);
  });

  it("shows nothing without a role", () => {
    expect(attentionBucketsFor(new Set())).toEqual([]);
  });
});
