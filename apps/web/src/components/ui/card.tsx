import type { LucideIcon } from "lucide-react";
import * as React from "react";
import { cn } from "../../lib/utils";

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("rounded-xl border border-line/70 bg-surface p-4 shadow-card md:p-6", className)}
      {...props}
    />
  );
}

export function CardTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h2 className={cn("text-lg font-semibold text-ink", className)} {...props} />;
}

/** A titled group inside a form or record, with an icon chip. */
export function Section({
  icon: Icon,
  title,
  children,
  className,
}: {
  icon: LucideIcon;
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("space-y-4", className)}>
      <h3 className="flex items-center gap-2 text-base font-semibold text-ink">
        <span className="inline-flex size-8 items-center justify-center rounded-lg bg-brand-soft text-brand">
          <Icon aria-hidden className="size-4" />
        </span>
        {title}
      </h3>
      {children}
    </section>
  );
}
