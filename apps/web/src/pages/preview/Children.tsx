import { Baby, CalendarClock } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Avatar } from "../../components/Avatar";
import { PageHeader } from "../../components/PageHeader";
import { PreviewNotice } from "../../components/PreviewNotice";
import { Card, CardHeader } from "../../components/ui/card";
import { SampleBadge } from "../../components/ui/kit";
import { StatusBadge, type StatusKind } from "../../components/ui/status";
import { sampleChildren, type SampleChild } from "../../demo/sample";

const STATUS: Record<SampleChild["status"], StatusKind> = { due: "pending", given: "confirmed", unknown: "unknown" };

/** PREVIEW: child follow-up after birth (later phase). Placeholder schedule, sample data. */
export function Children() {
  const { t } = useTranslation();
  return (
    <div className="space-y-6">
      <PageHeader title={t("children.title")} description={t("children.description")} badge={<SampleBadge />} showContext={false} />
      <PreviewNotice body={t("children.notice")} />

      <Card className="p-0 md:p-0">
        <div className="p-4 pb-0 md:p-5 md:pb-0">
          <CardHeader icon={Baby} title={t("children.listTitle")} description={t("children.listBody")} actions={<SampleBadge />} />
        </div>
        {/* Table on wide screens, cards on phones. */}
        <table className="hidden w-full text-left md:table">
          <thead className="border-y border-line bg-page/70 text-xs font-semibold tracking-wide text-faint uppercase">
            <tr>
              <th className="px-5 py-2.5">{t("children.col.child")}</th>
              <th className="px-5 py-2.5">{t("children.col.mother")}</th>
              <th className="px-5 py-2.5">{t("children.col.age")}</th>
              <th className="px-5 py-2.5">{t("children.col.next")}</th>
              <th className="px-5 py-2.5">{t("children.col.status")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line/70">
            {sampleChildren.map((c) => (
              <tr key={c.id} className="transition-colors hover:bg-subtle/50">
                <td className="px-5 py-3.5">
                  <span className="flex items-center gap-3 font-semibold">
                    <Avatar name={c.name} size="sm" />
                    {c.name}
                  </span>
                </td>
                <td className="px-5 py-3.5 text-ink-2">{c.mother}</td>
                <td className="tabular px-5 py-3.5 text-ink-2">{c.ageLabel}</td>
                <td className="px-5 py-3.5 text-ink-2">{c.nextStep}</td>
                <td className="px-5 py-3.5">
                  <StatusBadge kind={STATUS[c.status]}>{t(`children.status.${c.status}`)}</StatusBadge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <ul className="divide-y divide-line/70 border-t border-line md:hidden">
          {sampleChildren.map((c) => (
            <li key={c.id} className="flex items-start gap-3 px-4 py-4">
              <Avatar name={c.name} size="sm" />
              <div className="min-w-0 flex-1 space-y-1">
                <p className="font-semibold">{c.name}</p>
                <p className="text-sm text-muted">
                  {c.mother} · {c.ageLabel}
                </p>
                <p className="inline-flex items-center gap-1.5 text-sm text-ink-2">
                  <CalendarClock aria-hidden className="size-4 text-faint" />
                  {c.nextStep}
                </p>
                <div>
                  <StatusBadge kind={STATUS[c.status]}>{t(`children.status.${c.status}`)}</StatusBadge>
                </div>
              </div>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
