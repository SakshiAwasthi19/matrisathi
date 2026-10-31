import { afterEach, describe, expect, it, vi } from "vitest";
import { attemptKey, clearAttempt, createAttemptStore } from "./attempts";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("attemptKey", () => {
  it("reuses the key while the payload is unchanged", () => {
    const store = createAttemptStore();
    const first = attemptKey(store, "person", { full_name: "Synthetic A", phone: "1" });
    expect(attemptKey(store, "person", { full_name: "Synthetic A", phone: "1" })).toBe(first);
  });

  it("issues a new key when the payload changes", () => {
    const store = createAttemptStore();
    const first = attemptKey(store, "person", { full_name: "Synthetic A", phone: "1" });
    expect(attemptKey(store, "person", { full_name: "Synthetic A", phone: "2" })).not.toBe(first);
  });

  it("keeps scopes independent", () => {
    const store = createAttemptStore();
    const person = attemptKey(store, "person", { id: 1 });
    const episode = attemptKey(store, "episode", { id: 1 });
    expect(episode).not.toBe(person);
    expect(attemptKey(store, "person", { id: 1 })).toBe(person);
  });

  it("issues a new key after the attempt is cleared", () => {
    const store = createAttemptStore();
    const first = attemptKey(store, "person", { id: 1 });
    clearAttempt(store, "person");
    expect(attemptKey(store, "person", { id: 1 })).not.toBe(first);
  });

  it("falls back to getRandomValues outside a secure context", () => {
    vi.stubGlobal("crypto", { getRandomValues: (a: Uint8Array) => a.fill(171) });
    const key = attemptKey(createAttemptStore(), "person", {});
    expect(key).toBe("ab".repeat(16));
  });
});
