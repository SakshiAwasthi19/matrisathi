import { describe, expect, it } from "vitest";
import en from "./en.json";
import second from "./second.json";

function flatten(obj: Record<string, unknown>, prefix = ""): Record<string, unknown> {
  return Object.entries(obj).reduce<Record<string, unknown>>((acc, [key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    if (value && typeof value === "object") Object.assign(acc, flatten(value as Record<string, unknown>, path));
    else acc[path] = value;
    return acc;
  }, {});
}

describe("translation files", () => {
  const enKeys = flatten(en);

  it("has no empty English strings", () => {
    const empty = Object.entries(enKeys).filter(([, v]) => typeof v !== "string" || v.trim() === "");
    expect(empty).toEqual([]);
  });

  it("second locale only contains keys that exist in English", () => {
    const extra = Object.keys(flatten(second as Record<string, unknown>)).filter((k) => !(k in enKeys));
    expect(extra).toEqual([]);
  });
});
