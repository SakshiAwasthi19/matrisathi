import { Building2, CalendarDays } from "lucide-react";
import type * as React from "react";
import { useTranslation } from "react-i18next";
import { useSession } from "../state/session";

/** Page title with a one-line description, actions on the right, and where
 * the user is working plus today's date, so staff on a shared device can see
 * the context at a glance. */
export function PageHeader({
  title,
  description,
  actions,
  badge,
  children,
  showContext = true,
}: {
  title: string;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  /** Small label next to the title (e.g. "Preview · sample data"). */
  badge?: React.ReactNode;
  children?: React.ReactNode;
  showContext?: boolean;
}) {
  const { t, i18n } = useTranslation();
  const { staff } = useSession();
  const facilities = [...new Set((staff?.memberships ?? []).map((m) => m.facility_name))];
  const today = new Date().toLocaleDateString(i18n.language, { weekday: "long", day: "numeric", month: "long" });

  return (
    <header className="animate-fade-in space-y-4">
      {showContext && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted">
          {facilities.length > 0 && (
            <span className="inline-flex items-center gap-1.5">
              <Building2 aria-hidden className="size-4 shrink-0 text-faint" />
              {t("header.workingAt", { facilities: facilities.join(", ") })}
            </span>
          )}
          <span className="inline-flex items-center gap-1.5">
            <CalendarDays aria-hidden className="size-4 shrink-0 text-faint" />
            {today}
          </span>
        </div>
      )}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0 space-y-1.5">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight text-ink md:text-[1.75rem]">{title}</h1>
            {badge}
          </div>
          {description && <p className="max-w-2xl text-base text-muted">{description}</p>}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
      {children}
    </header>
  );
}
