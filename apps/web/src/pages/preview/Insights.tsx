import { CalendarCheck, ClipboardCheck, FileClock, Users } from "lucide-react";
import { useTranslation } from "react-i18next";
import { AreaChart, BarList, StackedColumns } from "../../components/charts";
import { PageHeader } from "../../components/PageHeader";
import { PreviewNotice } from "../../components/PreviewNotice";
import { Card, CardHeader } from "../../components/ui/card";
import { SampleBadge, StatTile } from "../../components/ui/kit";
import { insightTiles, referralFunnel, registrationsByWeek, visitsByWeek } from "../../demo/sample";

/** PREVIEW: programme reporting (later phase). Every number here is sample data. */
export function Insights() {
  const { t } = useTranslation();
  return (
    <div className="space-y-6">
      <PageHeader title={t("insights.title")} description={t("insights.description")} badge={<SampleBadge />} showContext={false} />
      <PreviewNotice body={t("insights.notice")} />

      <section aria-label={t("insights.tilesLabel")} className="grid grid-cols-2 gap-3 md:gap-4 xl:grid-cols-4">
        <StatTile label={t("insights.active")} value={insightTiles.activePregnancies} icon={Users} sample />
        <StatTile label={t("insights.visits")} value={insightTiles.visitsThisMonth} icon={CalendarCheck} sample />
        <StatTile label={t("insights.closedOnTime")} value={insightTiles.followUpsClosedOnTime} icon={ClipboardCheck} sample />
        <StatTile label={t("insights.reports")} value={insightTiles.reportsAwaitingReview} icon={FileClock} tone="accent" sample />
      </section>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 lg:items-start">
        <Card>
          <CardHeader title={t("overview.registrations")} description={t("overview.registrationsBody")} actions={<SampleBadge />} />
          <AreaChart data={registrationsByWeek} caption={t("overview.registrations")} />
        </Card>
        <Card>
          <CardHeader title={t("overview.visits")} description={t("overview.visitsBody")} actions={<SampleBadge />} />
          <StackedColumns rows={visitsByWeek} series={[t("overview.attended"), t("overview.missed")]} caption={t("overview.visits")} />
        </Card>
      </div>

      <Card>
        <CardHeader title={t("insights.referrals")} description={t("insights.referralsBody")} actions={<SampleBadge />} />
        <BarList data={referralFunnel} caption={t("insights.referrals")} className="max-w-2xl" />
      </Card>
    </div>
  );
}
