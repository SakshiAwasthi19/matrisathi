import { CheckCircle2, CircleDashed, Clock, HelpCircle, Info, TriangleAlert, type LucideIcon } from "lucide-react";
import type * as React from "react";
import { cn } from "../../lib/utils";

// Every status shows an icon plus a word; colour is never the only signal.
// Red is reserved for Urgent help and is deliberately absent here.
export type StatusKind = "pending" | "unknown" | "not-recorded" | "confirmed";

const STATUS_STYLE: Record<StatusKind, { icon: LucideIcon; className: string }> = {
  pending: { icon: Clock, className: "border-pending-line bg-pending-bg text-pending" },
  unknown: { icon: HelpCircle, className: "border-pending-line bg-pending-bg text-pending" },
  "not-recorded": { icon: CircleDashed, className: "border-none-line bg-none-bg text-none" },
  confirmed: { icon: CheckCircle2, className: "border-ok-line bg-ok-bg text-ok" },
};

export function StatusBadge({ kind, children }: { kind: StatusKind; children: React.ReactNode }) {
  const { icon: Icon, className } = STATUS_STYLE[kind];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-sm font-semibold",
        className,
      )}
    >
      <Icon aria-hidden className="size-4 shrink-0" />
      {children}
    </span>
  );
}

export type AlertKind = "info" | "problem" | "pending";

const ALERT_STYLE: Record<AlertKind, { icon: LucideIcon; className: string }> = {
  info: { icon: Info, className: "border-line bg-subtle text-ink" },
  problem: { icon: TriangleAlert, className: "border-problem-line bg-problem-bg text-problem" },
  pending: { icon: Clock, className: "border-pending-line bg-pending-bg text-pending" },
};

export function Alert({
  kind = "info",
  title,
  children,
  className,
}: {
  kind?: AlertKind;
  title?: string;
  children?: React.ReactNode;
  className?: string;
}) {
  const { icon: Icon, className: tone } = ALERT_STYLE[kind];
  return (
    <div role={kind === "problem" ? "alert" : "status"} className={cn("flex gap-3 rounded-md border p-3", tone, className)}>
      <Icon aria-hidden className="mt-0.5 size-5 shrink-0" />
      <div className="space-y-1 text-base">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div>{children}</div>}
      </div>
    </div>
  );
}
