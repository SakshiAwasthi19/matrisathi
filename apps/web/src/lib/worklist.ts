import type { CareTask } from "../api/client";

export interface WorklistGroups {
  overdue: CareTask[];
  today: CareTask[];
  later: CareTask[];
  undated: CareTask[];
}

/** Local calendar date (YYYY-MM-DD) for "today". */
export function localISODate(now: Date = new Date()): string {
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

/** Splits open tasks into the Today page's sections. "Overdue" is the
 * server's administrative flag (past the due time), never a clinical risk. */
export function groupTasks(tasks: readonly CareTask[], today: string = localISODate()): WorklistGroups {
  const groups: WorklistGroups = { overdue: [], today: [], later: [], undated: [] };
  for (const task of tasks) {
    if (task.overdue) groups.overdue.push(task);
    else if (!task.due_at) groups.undated.push(task);
    else if (task.due_at.slice(0, 10) <= today) groups.today.push(task);
    else groups.later.push(task);
  }
  return groups;
}

/** Open task counts by kind, largest first (ties keep first-seen order). */
export function countByKind(tasks: readonly CareTask[]): { kind: string; count: number }[] {
  const counts = new Map<string, number>();
  for (const task of tasks) counts.set(task.kind, (counts.get(task.kind) ?? 0) + 1);
  return [...counts.entries()].map(([kind, count]) => ({ kind, count })).sort((a, b) => b.count - a.count);
}

/** Open tasks for one pregnancy record, in worklist order. */
export interface MotherGroup {
  episodeId: string;
  mother: string;
  tasks: CareTask[];
}

/** Groups tasks by record, keeping the order in which each record first appears. */
export function groupByMother(tasks: readonly CareTask[]): MotherGroup[] {
  const groups = new Map<string, MotherGroup>();
  for (const task of tasks) {
    const g = groups.get(task.episode_id) ?? { episodeId: task.episode_id, mother: task.mother_full_name, tasks: [] };
    g.tasks.push(task);
    groups.set(task.episode_id, g);
  }
  return [...groups.values()];
}

/** Worklist order: overdue, due today, later, then undated. */
export function worklistOrder(tasks: readonly CareTask[], today: string = localISODate()): CareTask[] {
  const g = groupTasks(tasks, today);
  return [...g.overdue, ...g.today, ...g.later, ...g.undated];
}

export type TaskFilter = "overdue" | "today" | "unassigned";
export const TASK_FILTERS: readonly TaskFilter[] = ["overdue", "today", "unassigned"];

/** Narrows the worklist for links from the Overview (filter and/or task kind). */
export function filterTasks(
  tasks: readonly CareTask[],
  filter: TaskFilter | null,
  kind: string | null,
  today: string = localISODate(),
): CareTask[] {
  const groups = groupTasks(tasks, today);
  let out: readonly CareTask[] = tasks;
  if (filter === "overdue") out = groups.overdue;
  else if (filter === "today") out = groups.today;
  else if (filter === "unassigned") out = tasks.filter((t) => t.status === "NEW");
  return kind ? out.filter((t) => t.kind === kind) : [...out];
}

/** Top-bar search text: digits (with spaces, dashes or a leading +) search by phone, anything else by name. */
export function parseQuickFind(raw: string): { phone?: string; full_name?: string } | null {
  const q = raw.trim();
  if (!q) return null;
  if (/^\+?[\d\s-]+$/.test(q) && q.replace(/\D/g, "").length >= 4) return { phone: q.replace(/[\s-]/g, "") };
  return { full_name: q };
}
