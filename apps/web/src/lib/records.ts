import type { ReferralStatus } from "../api/client";

/** Mirrors REFERRAL_TRANSITIONS on the server: the forward steps offered as
 * buttons. Closing (with a reason) is offered separately whenever allowed. */
export const REFERRAL_NEXT: Record<ReferralStatus, Exclude<ReferralStatus, "SENT" | "CLOSED">[]> = {
  SENT: ["CONTACTED", "ATTENDED"],
  CONTACTED: ["ATTENDED"],
  ATTENDED: ["ADVICE_RECEIVED"],
  ADVICE_RECEIVED: ["FOLLOW_UP_COMPLETED"],
  FOLLOW_UP_COMPLETED: [],
  CLOSED: [],
};

export function referralCanClose(status: ReferralStatus): boolean {
  return status !== "CLOSED" && status !== "FOLLOW_UP_COMPLETED";
}

/** The order steps are shown in the timeline. */
export const REFERRAL_TIMELINE: ReferralStatus[] = ["SENT", "CONTACTED", "ATTENDED", "ADVICE_RECEIVED", "FOLLOW_UP_COMPLETED"];

export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
export const ACCEPTED_TYPES = ["application/pdf", "image/jpeg", "image/png"] as const;
export const ACCEPT_ATTRIBUTE = ".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png";

/** Same limits the server enforces (it also checks the file's content).
 * Returns an i18n key for the problem, or null if the file may be sent. */
export function uploadProblem(file: { size: number; type: string }): string | null {
  if (file.size === 0) return "records.file.empty";
  if (file.size > MAX_UPLOAD_BYTES) return "records.file.tooLarge";
  if (!(ACCEPTED_TYPES as readonly string[]).includes(file.type)) return "records.file.wrongType";
  return null;
}
