import { Building2, CalendarDays } from "lucide-react";
import type * as React from "react";
import { useTranslation } from "react-i18next";
import { useSession } from "../state/session";

/** Page title on a brand band, with where the user is working and today's
 * date, so staff on a shared device can see the context at a glance. */
export function PageHeader({ title, children }: { title: string; children?: React.ReactNode }) {
  const { t, i18n } = useTranslation();
  const { staff } = useSession();
  const facilities = [...new Set((staff?.memberships ?? []).map((m) => m.facility_name))];
  const today = new Date().toLocaleDateString(i18n.language, {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  return (
    <div className="relative overflow-hidden rounded-xl bg-linear-to-br from-brand-deep via-brand to-brand-strong px-5 py-6 text-brand-ink shadow-raised md:px-8 md:py-7">
      {/* Decorative rings; purely visual. */}
      <span aria-hidden className="pointer-events-none absolute -top-16 -right-10 size-48 rounded-full border-[24px] border-white/5" />
      <span aria-hidden className="pointer-events-none absolute -bottom-20 right-24 size-40 rounded-full border-[20px] border-white/5" />
      <h1 className="relative text-2xl font-semibold md:text-3xl">{title}</h1>
      <div className="relative mt-3 flex flex-col gap-2 text-sm text-white/85 sm:flex-row sm:flex-wrap sm:gap-x-3">
        {facilities.length > 0 && (
          <span className="inline-flex w-fit items-center gap-1.5 rounded-full bg-white/12 px-3 py-1">
            <Building2 aria-hidden className="size-4 shrink-0" />
            {t("header.workingAt", { facilities: facilities.join(", ") })}
          </span>
        )}
        <span className="inline-flex w-fit items-center gap-1.5 rounded-full bg-white/12 px-3 py-1">
          <CalendarDays aria-hidden className="size-4 shrink-0" />
          {today}
        </span>
      </div>
      {children && <div className="relative mt-4">{children}</div>}
    </div>
  );
}
