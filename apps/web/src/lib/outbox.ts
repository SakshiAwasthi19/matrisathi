import type { OutboxStatus } from "../api/client";
import type { StatusKind } from "../components/ui/status";

// Honest labels for an outgoing WhatsApp message (F017, AT14):
// - SUBMITTED means WhatsApp accepted it, not that it reached her phone.
// - UNKNOWN is never shown as sent.
// - READ appears only when the provider reported it.

/** Reasons the server records, each with a plain-English line in en.json (msg.reason.*). */
export const KNOWN_REASONS: ReadonlySet<string> = new Set([
  "NO_CONSENT",
  "OPTED_OUT",
  "NUMBER_NOT_USABLE",
  "CHANNEL_INACTIVE",
  "TEMPLATE_NOT_APPROVED",
  "OUTSIDE_SERVICE_WINDOW",
  "APPOINTMENT_CHANGED",
  "NO_ANSWER_FROM_PROVIDER",
  "RETRIES_USED_UP",
  "PROVIDER_REFUSED",
  "PROVIDER_REPORTED_FAILED",
  "WORKER_STOPPED_MID_SEND",
]);

export interface OutboxLabel {
  kind: StatusKind;
  /** i18n key for the status word. */
  labelKey: string;
  /** i18n key for the reason line, when one should be shown. */
  reasonKey: string | null;
}

const NEEDS_REASON: ReadonlySet<OutboxStatus> = new Set(["FAILED", "UNKNOWN", "BLOCKED"]);

export function outboxLabel(status: OutboxStatus, reason: string | null): OutboxLabel {
  let kind: StatusKind;
  let labelKey = `msg.status.${status}`;
  switch (status) {
    case "QUEUED":
      kind = "pending";
      if (reason === "OUTSIDE_SAFE_HOURS") labelKey = "msg.status.WAITING_SAFE_HOURS";
      else if (reason === "RETRYING") labelKey = "msg.status.RETRYING";
      break;
    case "SENDING":
      kind = "pending";
      break;
    case "SUBMITTED":
      kind = "neutral";
      break;
    case "DELIVERED":
    case "READ":
      kind = "confirmed";
      break;
    case "UNKNOWN":
      kind = "unknown";
      break;
    case "FAILED":
    case "BLOCKED":
      kind = "attention";
      break;
    default:
      kind = "unknown";
      labelKey = "msg.status.UNKNOWN";
  }
  let reasonKey: string | null = null;
  if (NEEDS_REASON.has(status)) {
    reasonKey = reason && KNOWN_REASONS.has(reason) ? `msg.reason.${reason}` : "msg.reason.OTHER";
  }
  return { kind, labelKey, reasonKey };
}
