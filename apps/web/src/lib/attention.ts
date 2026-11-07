import type { AttentionBucket } from "../api/client";

/** What each role acts on first. Order matters: it is the panel order.
 * Administrative only: who is waiting for what, never a clinical priority. */
const BY_ROLE: Record<string, readonly AttentionBucket[]> = {
  DOCTOR: ["reports_to_review", "prescriptions_to_review", "dating_not_confirmed", "no_care_plan"],
  COORDINATOR: ["contact_not_confirmed", "no_care_plan", "referrals_in_progress"],
  NURSE: ["contact_not_confirmed", "referrals_in_progress"],
  ASHA: ["contact_not_confirmed", "referrals_in_progress"],
};

const ROLE_ORDER = ["DOCTOR", "COORDINATOR", "NURSE", "ASHA"];

/** Buckets for someone holding these roles (at any facility), clinician items first, no repeats. */
export function attentionBucketsFor(roles: Set<string>): AttentionBucket[] {
  const out: AttentionBucket[] = [];
  for (const role of ROLE_ORDER) {
    if (!roles.has(role)) continue;
    for (const b of BY_ROLE[role]) if (!out.includes(b)) out.push(b);
  }
  return out;
}

/** The record tab where each item is dealt with. */
export const BUCKET_TAB: Record<AttentionBucket, string> = {
  reports_to_review: "records",
  prescriptions_to_review: "records",
  referrals_in_progress: "records",
  dating_not_confirmed: "overview",
  no_care_plan: "overview",
  contact_not_confirmed: "overview",
};
