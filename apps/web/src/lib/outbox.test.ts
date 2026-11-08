import { describe, expect, it } from "vitest";
import en from "../locales/en.json";
import { KNOWN_REASONS, outboxLabel } from "./outbox";

function lookup(key: string): unknown {
  return key.split(".").reduce<unknown>((node, part) => (node as Record<string, unknown> | undefined)?.[part], en);
}

describe("outgoing message labels", () => {
  it("says 'sent to WhatsApp' for SUBMITTED, never 'delivered'", () => {
    const label = outboxLabel("SUBMITTED", null);
    expect(label.labelKey).toBe("msg.status.SUBMITTED");
    expect(lookup(label.labelKey)).toBe("Sent to WhatsApp");
    expect(label.kind).not.toBe("confirmed");
  });

  it("never shows UNKNOWN as sent", () => {
    const label = outboxLabel("UNKNOWN", "NO_ANSWER_FROM_PROVIDER");
    expect(label.kind).toBe("unknown");
    expect(String(lookup(label.labelKey))).toMatch(/not confirmed/i);
    expect(label.reasonKey).toBe("msg.reason.NO_ANSWER_FROM_PROVIDER");
  });

  it("shows BLOCKED as not sent, with the plain reason", () => {
    for (const reason of ["NO_CONSENT", "OPTED_OUT", "NUMBER_NOT_USABLE", "CHANNEL_INACTIVE", "TEMPLATE_NOT_APPROVED", "OUTSIDE_SERVICE_WINDOW", "APPOINTMENT_CHANGED"]) {
      const label = outboxLabel("BLOCKED", reason);
      expect(lookup(label.labelKey)).toBe("Not sent");
      expect(label.reasonKey).toBe(`msg.reason.${reason}`);
    }
  });

  it("falls back to a general reason for an unrecognised one", () => {
    expect(outboxLabel("BLOCKED", "SOMETHING_NEW").reasonKey).toBe("msg.reason.OTHER");
    expect(outboxLabel("FAILED", null).reasonKey).toBe("msg.reason.OTHER");
  });

  it("explains a queued message waiting for her safe hours or retrying", () => {
    expect(outboxLabel("QUEUED", "OUTSIDE_SAFE_HOURS").labelKey).toBe("msg.status.WAITING_SAFE_HOURS");
    expect(outboxLabel("QUEUED", "RETRYING").labelKey).toBe("msg.status.RETRYING");
    expect(outboxLabel("QUEUED", null)).toEqual({ kind: "pending", labelKey: "msg.status.QUEUED", reasonKey: null });
  });

  it("shows no reason line for messages on their way or delivered", () => {
    for (const status of ["QUEUED", "SENDING", "SUBMITTED", "DELIVERED", "READ"] as const) {
      expect(outboxLabel(status, null).reasonKey).toBeNull();
    }
  });

  it("has English text for every label and reason", () => {
    const keys = [
      ...(["QUEUED", "SENDING", "SUBMITTED", "DELIVERED", "READ", "FAILED", "UNKNOWN", "BLOCKED"] as const).map((s) => outboxLabel(s, null).labelKey),
      "msg.status.WAITING_SAFE_HOURS",
      "msg.status.RETRYING",
      "msg.reason.OTHER",
      ...[...KNOWN_REASONS].map((r) => `msg.reason.${r}`),
    ];
    for (const key of keys) expect(typeof lookup(key), key).toBe("string");
  });
});
