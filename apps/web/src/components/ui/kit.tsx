import { ArrowUpRight, Sparkles, type LucideIcon } from "lucide-react";
import * as React from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { cn } from "../../lib/utils";

/** Small label pill. Tones are decorative (identity), never a status. */
export function Badge({
  tone = "neutral",
  icon: Icon,
  children,
  className,
}: {
  tone?: "neutral" | "brand" | "accent";
  icon?: LucideIcon;
  children: React.ReactNode;
  className?: string;
}) {
  const tones = {
    neutral: "bg-subtle text-ink-2 ring-line",
    brand: "bg-brand-tint text-brand-strong ring-brand-soft",
    accent: "bg-accent-soft text-accent ring-[#f1d9b3]",
  };
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ring-inset", tones[tone], className)}>
      {Icon && <Icon aria-hidden className="size-3.5" />}
      {children}
    </span>
  );
}

/** Marks anything not connected to real data yet. Never omit it on sample content. */
export function SampleBadge({ label }: { label?: string }) {
  const { t } = useTranslation();
  return (
    <Badge tone="accent" icon={Sparkles} className="cursor-help">
      <span title={t("sample.tooltip")}>{label ?? t("sample.badge")}</span>
    </Badge>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn("skeleton h-4", className)} />;
}

/** Placeholder card while a section loads: avoids layout jumps on slow networks. */
export function CardSkeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div role="status" aria-busy="true" className="space-y-3 rounded-[var(--radius-card)] border border-line bg-surface p-5">
      <Skeleton className="h-5 w-40" />
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} className={cn("h-4", i % 2 ? "w-2/3" : "w-full")} />
      ))}
    </div>
  );
}

/** One headline number with a label. Use instead of a chart for a single value. */
export function StatTile({
  label,
  value,
  hint,
  icon: Icon,
  sample,
  tone = "brand",
  to,
}: {
  label: string;
  value: React.ReactNode;
  hint?: React.ReactNode;
  icon?: LucideIcon;
  sample?: boolean;
  tone?: "brand" | "accent" | "neutral";
  /** Makes the whole tile a link (e.g. to the filtered worklist). */
  to?: string;
}) {
  const chip = { brand: "bg-brand-tint text-brand", accent: "bg-accent-soft text-accent", neutral: "bg-subtle text-ink-2" }[tone];
  const body = (
    <>
      <div className="flex items-center justify-between gap-2">
        <span className="inline-flex items-center gap-1 text-sm font-medium text-muted">
          {label}
          {to && <ArrowUpRight aria-hidden className="size-3.5 text-faint opacity-0 transition-opacity group-hover:opacity-100" />}
        </span>
        {Icon && (
          <span className={cn("inline-flex size-8 items-center justify-center rounded-lg", chip)}>
            <Icon aria-hidden className="size-4" />
          </span>
        )}
      </div>
      <div className="tabular text-3xl font-semibold tracking-tight text-ink">{value}</div>
      <div className="flex min-h-5 flex-wrap items-center gap-2 text-sm text-muted">
        {hint}
        {sample && <SampleBadge />}
      </div>
    </>
  );
  const cls =
    "group flex flex-col gap-3 rounded-[var(--radius-card)] border border-line bg-surface p-4 shadow-card transition-[box-shadow,border-color] hover:shadow-raised md:p-5";
  return to ? (
    <Link to={to} className={cn(cls, "hover:border-line-strong")}>
      {body}
    </Link>
  ) : (
    <div className={cls}>{body}</div>
  );
}

export interface TabItem<T extends string> {
  value: T;
  label: string;
  icon?: LucideIcon;
  count?: number;
}

/** Underlined tabs (record sections, filters). Keyboard: arrows move focus. */
export function Tabs<T extends string>({
  items,
  value,
  onChange,
  label,
}: {
  items: TabItem<T>[];
  value: T;
  onChange: (v: T) => void;
  label: string;
}) {
  const refs = React.useRef<(HTMLButtonElement | null)[]>([]);
  return (
    <div role="tablist" aria-label={label} className="-mx-4 flex gap-1 overflow-x-auto border-b border-line px-4 md:mx-0 md:px-0">
      {items.map((item, i) => {
        const active = item.value === value;
        const Icon = item.icon;
        return (
          <button
            key={item.value}
            ref={(el) => {
              refs.current[i] = el;
            }}
            type="button"
            role="tab"
            aria-selected={active}
            tabIndex={active ? 0 : -1}
            onClick={() => onChange(item.value)}
            onKeyDown={(e) => {
              if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
              const next = (i + (e.key === "ArrowRight" ? 1 : -1) + items.length) % items.length;
              refs.current[next]?.focus();
              onChange(items[next].value);
            }}
            className={cn(
              "relative inline-flex min-h-12 shrink-0 items-center gap-2 px-3 text-[0.95rem] font-semibold transition-colors md:min-h-11",
              active ? "text-brand" : "text-muted hover:text-ink",
            )}
          >
            {Icon && <Icon aria-hidden className="size-4" />}
            {item.label}
            {item.count !== undefined && (
              <span className={cn("tabular rounded-full px-1.5 text-xs", active ? "bg-brand-soft text-brand-strong" : "bg-subtle text-muted")}>
                {item.count}
              </span>
            )}
            <span
              aria-hidden
              className={cn("absolute inset-x-2 -bottom-px h-0.5 rounded-full transition-colors", active ? "bg-brand" : "bg-transparent")}
            />
          </button>
        );
      })}
    </div>
  );
}
