import { describe, expect, it } from "vitest";
import type { CareTask } from "../api/client";
import { countByKind, filterTasks, groupByMother, groupTasks, localISODate, parseQuickFind } from "./worklist";

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

describe("overview helpers", () => {
  it("groups by mother in first-seen order", () => {
    const g = groupByMother([task("a", { episode_id: "e1" }), task("b", { episode_id: "e2" }), task("c", { episode_id: "e1" })]);
    expect(g.map((x) => [x.episodeId, x.tasks.map((t) => t.id)])).toEqual([
      ["e1", ["a", "c"]],
      ["e2", ["b"]],
    ]);
  });

  it("filters by overdue, today, unassigned and kind", () => {
    const tasks = [
      task("a", { overdue: true, status: "NEW" }),
      task("b", { due_at: "2026-11-07T10:00:00Z", kind: "HELP_REQUEST" }),
      task("c", { status: "NEW", kind: "HELP_REQUEST" }),
    ];
    expect(filterTasks(tasks, "overdue", null, "2026-11-07").map((t) => t.id)).toEqual(["a"]);
    expect(filterTasks(tasks, "today", null, "2026-11-07").map((t) => t.id)).toEqual(["b"]);
    expect(filterTasks(tasks, "unassigned", null, "2026-11-07").map((t) => t.id)).toEqual(["a", "c"]);
    expect(filterTasks(tasks, null, "HELP_REQUEST", "2026-11-07").map((t) => t.id)).toEqual(["b", "c"]);
  });

  it("reads quick-find text as a phone number or a name", () => {
    expect(parseQuickFind("  ")).toBeNull();
    expect(parseQuickFind("+91 98765-43210")).toEqual({ phone: "+919876543210" });
    expect(parseQuickFind("Sunita Devi")).toEqual({ full_name: "Sunita Devi" });
    expect(parseQuickFind("123")).toEqual({ full_name: "123" });
  });
});
