import { cn } from "../lib/utils";

/** Initials in a circle. Purely visual: helps staff tell records apart at a
 * glance (e.g. two women on one phone). Never used to identify anyone. */
export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  const first = parts[0][0] ?? "";
  const last = parts.length > 1 ? (parts[parts.length - 1][0] ?? "") : "";
  return (first + last).toUpperCase();
}

export function Avatar({ name, size = "md" }: { name: string; size?: "sm" | "md" | "lg" }) {
  return (
    <span
      aria-hidden
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-full bg-accent-soft font-semibold text-accent",
        size === "lg" ? "size-14 text-xl" : size === "sm" ? "size-8 text-xs" : "size-11 text-base",
      )}
    >
      {initials(name)}
    </span>
  );
}
