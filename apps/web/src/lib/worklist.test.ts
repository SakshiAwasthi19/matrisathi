import { describe, expect, it } from "vitest";
import type { CareTask } from "../api/client";
import { countByKind, groupTasks, localISODate } from "./worklist";

const task = (id: string, over: Partial<CareTask> = {}): CareTask => ({
  id,
  episode_id: "e",
  mother_full_name: "Synthetic Mother",
  name: null,
  kind: "CONTACT",
  status: "ASSIGNED",
  owner_staff_user_id: null,
  owner_name: null,
  backup_staff_user_id: null,
  due_at: null,
  overdue: false,
  source_appointment_id: null,
  last_attempt_at: null,
  barrier: null,
  outcome: null,
  closure_reason: null,
  closed_at: null,
  version: 1,
  ...over,
});

describe("worklist grouping", () => {
  it("puts the server's overdue flag first, then due today, later and undated", () => {
    const g = groupTasks(
      [
        task("a", { overdue: true, due_at: "2026-11-01T10:00:00Z" }),
        task("b", { due_at: "2026-11-07T15:00:00Z" }),
        task("c", { due_at: "2026-11-09T09:00:00Z" }),
        task("d"),
      ],
      "2026-11-07",
    );
    expect(g.overdue.map((t) => t.id)).toEqual(["a"]);
    expect(g.today.map((t) => t.id)).toEqual(["b"]);
    expect(g.later.map((t) => t.id)).toEqual(["c"]);
    expect(g.undated.map((t) => t.id)).toEqual(["d"]);
  });

  it("never marks a task overdue on its own; past-due without the flag stays in today", () => {
    const g = groupTasks([task("a", { due_at: "2026-11-05T10:00:00Z" })], "2026-11-07");
    expect(g.overdue).toEqual([]);
    expect(g.today.map((t) => t.id)).toEqual(["a"]);
  });

  it("counts by kind, largest first", () => {
    expect(countByKind([task("a"), task("b", { kind: "HELP_REQUEST" }), task("c")])).toEqual([
      { kind: "CONTACT", count: 2 },
      { kind: "HELP_REQUEST", count: 1 },
    ]);
  });

  it("formats the local date", () => {
    expect(localISODate(new Date(2026, 0, 5))).toBe("2026-01-05");
  });
});
