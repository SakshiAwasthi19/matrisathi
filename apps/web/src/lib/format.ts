import { ApiError } from "../api/client";

/** "2026-11-07" shown as a local calendar date, never shifted by time zone. */
export function formatDate(isoDate: string | null | undefined, locale?: string): string {
  if (!isoDate) return "";
  const [y, m, d] = isoDate.slice(0, 10).split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(locale, { day: "numeric", month: "short", year: "numeric" });
}

export function formatDateTime(iso: string | null | undefined, locale?: string): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString(locale, { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
}

/** Today's date in the browser, as YYYY-MM-DD (for date inputs). */
export function todayIso(now: Date = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/** True when the server refused an update because someone else changed it first. */
export function isStaleConflict(err: unknown): boolean {
  return err instanceof ApiError && err.status === 409 && /changed by someone else/i.test(err.message);
}
