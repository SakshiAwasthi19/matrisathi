import { useQuery } from "@tanstack/react-query";
import {
  AlarmClock,
  ArrowRight,
  BookUser,
  CalendarClock,
  ClipboardList,
  Inbox,
  ListChecks,
  Search,
  Siren,
  UserPlus,
  UserRound,
  type LucideIcon,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { careApi, type CareTask } from "../api/client";
import { AreaChart, BarList, StackedColumns } from "../components/charts";
import { PageHeader } from "../components/PageHeader";
import { errorStateKind, PageState } from "../components/PageState";
import { Card, CardHeader } from "../components/ui/card";
import { SampleBadge, Skeleton, StatTile } from "../components/ui/kit";
import { StatusBadge } from "../components/ui/status";
import { registrationsByWeek, visitsByWeek } from "../demo/sample";
import { formatDate } from "../lib/format";
import { countByKind, groupTasks } from "../lib/worklist";
import { useSession } from "../state/session";

function greetingKey(hour: number): string {
  if (hour < 12) return "overview.greetMorning";
  if (hour < 17) return "overview.greetAfternoon";
  return "overview.greetEvening";
}

function QuickAction({ to, icon: Icon, title, body, external }: { to: string; icon: LucideIcon; title: string; body: string; external?: boolean }) {
  const inner = (
    <>
      <span className="inline-flex size-10 shrink-0 items-center justify-center rounded-xl bg-brand-tint text-brand ring-1 ring-brand-soft transition-colors group-hover:bg-brand group-hover:text-brand-ink">
        <Icon aria-hidden className="size-5" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block font-semibold text-ink">{title}</span>
        <span className="block truncate text-sm text-muted">{body}</span>
      </span>
      <ArrowRight aria-hidden className="size-4 text-faint transition-transform group-hover:translate-x-0.5 group-hover:text-brand" />
    </>
  );
  const cls =
    "group flex min-h-16 items-center gap-3 rounded-xl border border-line bg-surface px-4 py-3 shadow-card transition-[box-shadow,border-color] hover:border-line-strong hover:shadow-raised";
  return external ? (
    <a href={to} target="_blank" rel="noopener noreferrer" className={cls}>
      {inner}
    </a>
  ) : (
    <Link to={to} className={cls}>
      {inner}
    </Link>
  );
}

function UpNext({ tasks }: { tasks: CareTask[] }) {
  const { t } = useTranslation();
  if (tasks.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 py-8 text-center">
        <span className="inline-flex size-12 items-center justify-center rounded-full bg-brand-tint text-brand">
          <Inbox aria-hidden className="size-6" />
        </span>
        <p className="font-semibold">{t("overview.upNextEmpty")}</p>
        <p className="text-sm text-muted">{t("overview.upNextEmptyBody")}</p>
      </div>
    );
  }
  return (
    <ul className="-mx-2 divide-y divide-line/70">
      {tasks.map((task) => (
        <li key={task.id}>
          <Link
            to={`/episodes/${task.episode_id}?tab=care`}
            className="flex items-center gap-3 rounded-lg px-2 py-3 transition-colors hover:bg-subtle/70"
          >
            <span className="min-w-0 flex-1">
              <span className="block truncate font-semibold text-ink">{task.mother_full_name}</span>
              <span className="block truncate text-sm text-muted">{task.name ?? t(`care.task.kind${task.kind}`, { defaultValue: task.kind })}</span>
            </span>
            {task.overdue ? (
              <StatusBadge kind="attention">{t("care.task.overdue")}</StatusBadge>
            ) : task.due_at ? (
              <span className="inline-flex shrink-0 items-center gap-1 text-sm text-muted">
                <CalendarClock aria-hidden className="size-4" />
                {formatDate(task.due_at.slice(0, 10))}
              </span>
            ) : null}
          </Link>
        </li>
      ))}
    </ul>
  );
}

/** Signed-in home: real open-work figures from the task API, plus clearly
 * labelled sample charts for reporting that has no backend yet. */
export function Overview() {
  const { t } = useTranslation();
  const { staff } = useSession();
  const all = useQuery({ queryKey: ["tasks", "all"], queryFn: () => careApi.listTasks(false) });
  const tasks = all.data ?? [];
  const groups = groupTasks(tasks);
  const mine = tasks.filter((x) => x.owner_staff_user_id === staff?.id || x.backup_staff_user_id === staff?.id);
  const unassigned = tasks.filter((x) => x.status === "NEW").length;
  const byKind = countByKind(tasks).map((k) => ({ label: t(`care.task.kind${k.kind}`, { defaultValue: k.kind }), value: k.count }));
  const firstName = staff?.full_name.split(/\s+/)[0] ?? "";
  const facilityId = staff?.memberships[0]?.facility_id;

  const value = (n: number) => (all.isPending ? <Skeleton className="h-8 w-12" /> : all.isError ? "—" : n);

  return (
    <div className="space-y-8">
      <PageHeader
        title={t(greetingKey(new Date().getHours()), { name: firstName })}
        description={t("overview.description")}
        actions={
          <>
            <Link
              to="/mothers"
              className="inline-flex min-h-12 items-center gap-2 rounded-[var(--radius-control)] bg-brand px-4 font-semibold text-brand-ink hover:bg-brand-strong md:min-h-10"
            >
              <UserPlus aria-hidden className="size-4" />
              {t("overview.findOrRegister")}
            </Link>
          </>
        }
      />

      {/* Real figures from the open-task list. */}
      <section aria-label={t("overview.kpiLabel")} className="grid grid-cols-2 gap-3 md:gap-4 xl:grid-cols-4">
        <StatTile
          label={t("overview.kpiOpen")}
          value={value(tasks.length)}
          icon={ClipboardList}
          hint={unassigned > 0 ? t("overview.kpiUnassigned", { count: unassigned }) : t("overview.kpiOpenHint")}
        />
        <StatTile label={t("overview.kpiMine")} value={value(mine.length)} icon={UserRound} hint={t("overview.kpiMineHint")} />
        <StatTile label={t("overview.kpiDueToday")} value={value(groups.today.length)} icon={CalendarClock} hint={t("overview.kpiDueTodayHint")} />
        <StatTile
          label={t("overview.kpiOverdue")}
          value={value(groups.overdue.length)}
          icon={AlarmClock}
          tone="accent"
          hint={t("overview.kpiOverdueHint")}
        />
      </section>

      {all.isError && <PageState kind={errorStateKind(all.error)} />}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)] lg:items-start">
        <Card>
          <CardHeader
            icon={ListChecks}
            title={t("overview.upNext")}
            description={t("overview.upNextBody")}
            actions={
              <Link to="/today" className="inline-flex min-h-10 items-center gap-1 text-sm font-semibold text-brand hover:text-brand-strong">
                {t("overview.viewAll")}
                <ArrowRight aria-hidden className="size-4" />
              </Link>
            }
          />
          {all.isPending ? (
            <div className="space-y-4 py-2">
              {[0, 1, 2].map((i) => (
                <div key={i} className="space-y-2">
                  <Skeleton className="w-40" />
                  <Skeleton className="w-24" />
                </div>
              ))}
            </div>
          ) : (
            <UpNext tasks={[...groups.overdue, ...groups.today, ...groups.later, ...groups.undated].slice(0, 5)} />
          )}
        </Card>

        <div className="space-y-3">
          <h2 className="px-1 text-sm font-semibold text-muted">{t("overview.quickActions")}</h2>
          <QuickAction to="/mothers" icon={Search} title={t("overview.qaFind")} body={t("overview.qaFindBody")} />
          <QuickAction to="/today" icon={ListChecks} title={t("overview.qaToday")} body={t("overview.qaTodayBody")} />
          <QuickAction to="/contacts" icon={BookUser} title={t("overview.qaContacts")} body={t("overview.qaContactsBody")} />
          {facilityId && (
            <QuickAction to={`/urgent-help/${facilityId}`} icon={Siren} title={t("overview.qaUrgent")} body={t("overview.qaUrgentBody")} external />
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 lg:items-start">
        <Card>
          <CardHeader icon={ClipboardList} title={t("overview.byKind")} description={t("overview.byKindBody")} />
          {all.isPending ? (
            <Skeleton className="h-24 w-full" />
          ) : byKind.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted">{t("overview.byKindEmpty")}</p>
          ) : (
            <BarList data={byKind} caption={t("overview.byKind")} />
          )}
        </Card>
        <Card>
          <CardHeader title={t("overview.registrations")} description={t("overview.registrationsBody")} actions={<SampleBadge />} />
          <AreaChart data={registrationsByWeek} caption={t("overview.registrations")} />
        </Card>
      </div>

      <Card>
        <CardHeader title={t("overview.visits")} description={t("overview.visitsBody")} actions={<SampleBadge />} />
        <StackedColumns rows={visitsByWeek} series={[t("overview.attended"), t("overview.missed")]} caption={t("overview.visits")} />
      </Card>
    </div>
  );
}
