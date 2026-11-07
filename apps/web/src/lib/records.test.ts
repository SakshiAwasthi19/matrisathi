import { describe, expect, it } from "vitest";
import type { ReferralStatus } from "../api/client";
import { MAX_UPLOAD_BYTES, REFERRAL_NEXT, referralCanClose, uploadProblem } from "./records";

describe("referral steps", () => {
  it("never offers a jump straight to completion", () => {
    expect(REFERRAL_NEXT.SENT).not.toContain("FOLLOW_UP_COMPLETED");
    expect(REFERRAL_NEXT.CONTACTED).not.toContain("FOLLOW_UP_COMPLETED");
  });

  it("final states offer nothing", () => {
    expect(REFERRAL_NEXT.CLOSED).toEqual([]);
    expect(REFERRAL_NEXT.FOLLOW_UP_COMPLETED).toEqual([]);
    expect(referralCanClose("CLOSED")).toBe(false);
    expect(referralCanClose("FOLLOW_UP_COMPLETED")).toBe(false);
  });

  it("every open state can be closed with a reason", () => {
    const open: ReferralStatus[] = ["SENT", "CONTACTED", "ATTENDED", "ADVICE_RECEIVED"];
    for (const s of open) expect(referralCanClose(s)).toBe(true);
  });
});

describe("upload checks match the server", () => {
  it("accepts PDF, JPEG and PNG up to 10 MB", () => {
    for (const type of ["application/pdf", "image/jpeg", "image/png"]) {
      expect(uploadProblem({ size: 1000, type })).toBeNull();
    }
    expect(uploadProblem({ size: MAX_UPLOAD_BYTES, type: "application/pdf" })).toBeNull();
  });

  it("refuses empty, oversized and other types", () => {
    expect(uploadProblem({ size: 0, type: "application/pdf" })).toBe("records.file.empty");
    expect(uploadProblem({ size: MAX_UPLOAD_BYTES + 1, type: "application/pdf" })).toBe("records.file.tooLarge");
    expect(uploadProblem({ size: 10, type: "text/html" })).toBe("records.file.wrongType");
    expect(uploadProblem({ size: 10, type: "" })).toBe("records.file.wrongType");
  });
});
