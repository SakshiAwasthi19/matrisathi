import { useMutation, useQuery } from "@tanstack/react-query";
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
import { AttentionPanel } from "../components/AttentionPanel";
import { ActionError, useActionError } from "../components/care/shared";
import { BarList } from "../components/charts";
import { PageHeader } from "../components/PageHeader";
import { errorStateKind, PageState } from "../components/PageState";
import { Button } from "../components/ui/button";
import { Card, CardHeader } from "../components/ui/card";
import { Skeleton, StatTile } from "../components/ui/kit";
import { StatusBadge } from "../components/ui/status";
import i18n from "../i18n";
import { formatDate } from "../lib/format";
import { countByKind, groupByMother, groupTasks, worklistOrder, type MotherGroup } from "../lib/worklist";
import { useSession } from "../state/session";

const UP_NEXT_MOTHERS = 5;
const TASKS_PER_MOTHER = 3;

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

function AssignToMe({ task }: { task: CareTask }) {
  const { t } = useTranslation();
  const { staff } = useSession();
  const errors = useActionError([["tasks"]]);
  const assign = useMutation({
    mutationFn: () => careApi.assignTask(task.id, task.version, staff!.id),
    meta: { toast: i18n.t("toast.assigned") },
    onSuccess: () => {
      errors.clear();
      errors.reload();
    },
    onError: errors.onError,
  });
  if (!staff) return null;
  return (
    <>
      <Button size="sm" variant="soft" disabled={assign.isPending} onClick={() => assign.mutate()}>
        <UserPlus aria-hidden className="size-3.5" />
        {t("care.task.assignToMe")}
      </Button>
      {errors.message && (
        <div className="basis-full">
          <ActionError message={errors.message} />
        </div>
      )}
    </>
  );
}

function TaskLine({ task }: { task: CareTask }) {
  const { t } = useTranslation();
  return (
    <li className="flex flex-wrap items-center gap-x-3 gap-y-2 py-2">
      <span className="min-w-0 flex-1 basis-40 text-[0.95rem] text-ink-2">
        {task.name ?? t(`care.task.kind${task.kind}`, { defaultValue: task.kind })}
      </span>
      <span className="flex flex-wrap items-center gap-2 text-sm">
        {task.overdue ? (
          <StatusBadge kind="attention">{t("care.task.overdue")}</StatusBadge>
        ) : task.due_at ? (
          <span className="tabular inline-flex items-center gap-1 text-muted">
            <CalendarClock aria-hidden className="size-4" />
            {formatDate(task.due_at.slice(0, 10))}
          </span>
        ) : null}
        {task.owner_name ? (
          <span className="inline-flex items-center gap-1 text-muted">
            <UserRound aria-hidden className="size-4" />
            {task.owner_name}
          </span>
        ) : (
          <StatusBadge kind="pending">{t("care.task.statusNEW")}</StatusBadge>
        )}
        {task.status === "NEW" && <AssignToMe task={task} />}
      </span>
    </li>
  );
}

function UpNext({ groups }: { groups: MotherGroup[] }) {
  const { t } = useTranslation();
  if (groups.length === 0) {
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
    <ul className="divide-y divide-line/70">
      {groups.map((g) => {
        const extra = g.tasks.length - TASKS_PER_MOTHER;
        return (
          <li key={g.episodeId} className="py-3 first:pt-0 last:pb-0">
            <Link
              to={`/episodes/${g.episodeId}?tab=care`}
              className="group inline-flex items-center gap-1.5 font-semibold text-ink hover:text-brand"
            >
              {g.mother}
              <span className="tabular rounded-full bg-subtle px-1.5 text-xs font-semibold text-muted">{g.tasks.length}</span>
              <ArrowRight aria-hidden className="size-4 text-faint transition-transform group-hover:translate-x-0.5 group-hover:text-brand" />
            </Link>
            <ul className="mt-1 border-l-2 border-line pl-3">
              {g.tasks.slice(0, TASKS_PER_MOTHER).map((task) => (
                <TaskLine key={task.id} task={task} />
              ))}
            </ul>
            {extra > 0 && (
              <Link
                to={`/episodes/${g.episodeId}?tab=care`}
                className="mt-1 inline-block pl-3.5 text-sm font-semibold text-brand hover:text-brand-strong"
              >
                {t("overview.moreTasks", { count: extra })}
              </Link>
            )}
          </li>
        );
      })}
    </ul>
  );
}

/** Signed-in home. Everything on it comes from the live task list. */
export function Overview() {
  const { t } = useTranslation();
  const { staff } = useSession();
  const all = useQuery({ queryKey: ["tasks", "all"], queryFn: () => careApi.listTasks(false) });
  const tasks = all.data ?? [];
  const groups = groupTasks(tasks);
  const mine = tasks.filter((x) => x.owner_staff_user_id === staff?.id || x.backup_staff_user_id === staff?.id);
  const unassigned = tasks.filter((x) => x.status === "NEW").length;
  const byKind = countByKind(tasks).map((k) => ({
    label: t(`care.task.kind${k.kind}`, { defaultValue: k.kind }),
    value: k.count,
    to: `/today?scope=all&kind=${encodeURIComponent(k.kind)}`,
  }));
  const upNext = groupByMother(worklistOrder(tasks)).slice(0, UP_NEXT_MOTHERS);
  const firstName = staff?.full_name.split(/\s+/)[0] ?? "";
  const facilityId = staff?.memberships[0]?.facility_id;

  const value = (n: number) => (all.isPending ? <Skeleton className="h-8 w-12" /> : all.isError ? "—" : n);

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title={t(greetingKey(new Date().getHours()), { name: firstName })}
        description={t("overview.description")}
        actions={
          <Button asChild>
            <Link to="/mothers">
              <UserPlus aria-hidden className="size-4" />
              {t("overview.findOrRegister")}
            </Link>
          </Button>
        }
      />

      {all.isError && <PageState kind={errorStateKind(all.error)} />}

      {/* Phones: the work list comes first; the figures follow. */}
      <section aria-label={t("overview.kpiLabel")} className="order-2 grid grid-cols-2 gap-3 md:gap-4 lg:order-1 xl:grid-cols-4">
        <StatTile
          label={t("overview.kpiOpen")}
          value={value(tasks.length)}
          icon={ClipboardList}
          to="/today?scope=all"
          hint={unassigned > 0 ? t("overview.kpiUnassigned", { count: unassigned }) : t("overview.kpiOpenHint")}
        />
        <StatTile label={t("overview.kpiMine")} value={value(mine.length)} icon={UserRound} to="/today" hint={t("overview.kpiMineHint")} />
        <StatTile
          label={t("overview.kpiDueToday")}
          value={value(groups.today.length)}
          icon={CalendarClock}
          to="/today?scope=all&filter=today"
          hint={t("overview.kpiDueTodayHint")}
        />
        <StatTile
          label={t("overview.kpiOverdue")}
          value={value(groups.overdue.length)}
          icon={AlarmClock}
          tone="accent"
          to="/today?scope=all&filter=overdue"
          hint={t("overview.kpiOverdueHint")}
        />
      </section>

      <div className="order-1 grid grid-cols-1 gap-6 lg:order-2 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)] lg:items-start">
        <div className="space-y-6">
          <Card>
            <CardHeader
              icon={ListChecks}
              title={t("overview.upNext")}
              description={t("overview.upNextBody")}
              actions={
                <Link to="/today?scope=all" className="inline-flex min-h-10 items-center gap-1 text-sm font-semibold text-brand hover:text-brand-strong">
                  {t("overview.viewAll")}
                  <ArrowRight aria-hidden className="size-4" />
                </Link>
              }
            />
            {all.isPending ? (
              <div className="space-y-5 py-2">
                {[0, 1, 2].map((i) => (
                  <div key={i} className="space-y-2">
                    <Skeleton className="w-40" />
                    <Skeleton className="w-64 max-w-full" />
                  </div>
                ))}
              </div>
            ) : (
              <UpNext groups={upNext} />
            )}
          </Card>
          <AttentionPanel />
        </div>

        <div className="space-y-6">
          <div className="space-y-3">
            <h2 className="px-1 text-sm font-semibold text-muted">{t("overview.quickActions")}</h2>
            <QuickAction to="/mothers" icon={Search} title={t("overview.qaFind")} body={t("overview.qaFindBody")} />
            <QuickAction to="/contacts" icon={BookUser} title={t("overview.qaContacts")} body={t("overview.qaContactsBody")} />
            {facilityId && (
              <QuickAction to={`/urgent-help/${facilityId}`} icon={Siren} title={t("overview.qaUrgent")} body={t("overview.qaUrgentBody")} external />
            )}
          </div>
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
        </div>
      </div>
    </div>
  );
}
