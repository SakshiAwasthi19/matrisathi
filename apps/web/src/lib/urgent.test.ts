import { describe, expect, it } from "vitest";
import { telHref, urgentHelpUrl } from "./urgent";

describe("urgent help links", () => {
  it("builds the public address printed on the birth plan", () => {
    expect(urgentHelpUrl("abc-123", "https://staging.example")).toBe("https://staging.example/urgent-help/abc-123");
  });

  it("makes dialler-friendly tel links", () => {
    expect(telHref("+91 00000-00101")).toBe("tel:+910000000101");
  });
});
