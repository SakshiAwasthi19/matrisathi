import { useQuery } from "@tanstack/react-query";
import {
  CalendarClock,
  CheckCircle2,
  ClipboardList,
  FileText,
  Phone,
  Pill,
  Send,
  TriangleAlert,
  type LucideIcon,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { overviewApi, type AttentionBucket } from "../api/client";
import { attentionBucketsFor, BUCKET_TAB } from "../lib/attention";
import { rolesOf } from "../lib/nav";
import { useSession } from "../state/session";
import { Card, CardHeader } from "./ui/card";
import { Skeleton } from "./ui/kit";

const ICON: Record<AttentionBucket, LucideIcon> = {
  reports_to_review: FileText,
  prescriptions_to_review: Pill,
  dating_not_confirmed: CalendarClock,
  no_care_plan: ClipboardList,
  contact_not_confirmed: Phone,
  referrals_in_progress: Send,
};

/** Role-specific list of records waiting on someone (live, from /overview/summary). */
export function AttentionPanel() {
  const { t } = useTranslation();
  const { staff } = useSession();
  const buckets = attentionBucketsFor(rolesOf(staff?.memberships ?? []));
  const summary = useQuery({ queryKey: ["overviewSummary"], queryFn: overviewApi.summary, enabled: buckets.length > 0 });
  if (buckets.length === 0) return null;

  return (
    <Card>
      <CardHeader icon={TriangleAlert} title={t("attention.title")} description={t("attention.body")} />
      {summary.isPending && (
        <div className="space-y-4">
          {buckets.map((b) => (
            <Skeleton key={b} className="h-10 w-full" />
          ))}
        </div>
      )}
      {summary.isError && <p className="text-sm text-muted">{t("attention.loadFailed")}</p>}
      {summary.data && (
        <ul className="divide-y divide-line/70">
          {buckets.map((b) => {
            const { count, records } = summary.data[b];
            const Icon = ICON[b];
            const more = count - records.length;
            return (
              <li key={b} className="py-3 first:pt-0 last:pb-0">
                <div className="flex items-center gap-3">
                  <span
                    className={
                      count
                        ? "inline-flex size-8 shrink-0 items-center justify-center rounded-lg bg-pending-bg text-pending"
                        : "inline-flex size-8 shrink-0 items-center justify-center rounded-lg bg-ok-bg text-ok"
                    }
                  >
                    {count ? <Icon aria-hidden className="size-4" /> : <CheckCircle2 aria-hidden className="size-4" />}
                  </span>
                  <span className="min-w-0 flex-1 text-[0.95rem] font-medium text-ink">{t(`attention.bucket.${b}`)}</span>
                  {count ? (
                    <span className="tabular rounded-full bg-pending-bg px-2 text-sm font-semibold text-pending">{count}</span>
                  ) : (
                    <span className="text-sm text-muted">{t("attention.none")}</span>
                  )}
                </div>
                {records.length > 0 && (
                  <ul className="mt-2 flex flex-wrap gap-1.5 pl-11">
                    {records.map((r) => (
                      <li key={r.episode_id}>
                        <Link
                          to={`/episodes/${r.episode_id}?tab=${BUCKET_TAB[b]}`}
                          className="inline-flex min-h-8 items-center rounded-full border border-line bg-surface px-2.5 text-sm text-ink-2 transition-colors hover:border-brand hover:text-brand"
                        >
                          {r.mother_full_name}
                        </Link>
                      </li>
                    ))}
                    {more > 0 && <li className="inline-flex min-h-8 items-center px-1 text-sm text-muted">{t("attention.more", { count: more })}</li>}
                  </ul>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
