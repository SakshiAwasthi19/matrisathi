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
