import { describe, expect, it } from "vitest";
import { envLabel, shouldShowEnvBanner } from "./env";

describe("environment banner", () => {
  it("treats an unset label as development", () => {
    expect(envLabel(undefined)).toBe("development");
    expect(envLabel("  ")).toBe("development");
  });

  it("normalises case and whitespace", () => {
    expect(envLabel(" Staging ")).toBe("staging");
  });

  it("shows the banner everywhere except production", () => {
    expect(shouldShowEnvBanner("development")).toBe(true);
    expect(shouldShowEnvBanner("staging")).toBe(true);
    expect(shouldShowEnvBanner(envLabel("PRODUCTION"))).toBe(false);
  });
});
