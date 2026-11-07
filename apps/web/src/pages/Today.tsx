import { useQuery } from "@tanstack/react-query";
import { AlarmClock, CalendarClock, CalendarDays, CalendarOff, Filter, UserRound, Users, X, type LucideIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router";
import { careApi, type CareTask } from "../api/client";
import { TaskList } from "../components/care/TaskList";
import { PageHeader } from "../components/PageHeader";
import { errorStateKind, PageState } from "../components/PageState";
import { CardSkeleton, Tabs } from "../components/ui/kit";
import { filterTasks, groupTasks, TASK_FILTERS, type TaskFilter } from "../lib/worklist";

type Scope = "mine" | "all";

function Group({ icon: Icon, title, tasks, tone = "default" }: { icon: LucideIcon; title: string; tasks: CareTask[]; tone?: "default" | "attention" }) {
  if (tasks.length === 0) return null;
  return (
    <section aria-label={title} className="space-y-3">
      <h2 className="flex items-center gap-2.5 text-base font-semibold">
        <span
          className={
            tone === "attention"
              ? "inline-flex size-8 items-center justify-center rounded-lg bg-pending-bg text-pending"
              : "inline-flex size-8 items-center justify-center rounded-lg bg-brand-tint text-brand"
          }
        >
          <Icon aria-hidden className="size-4" />
        </span>
        {title}
        <span className="tabular rounded-full bg-subtle px-2 text-sm text-muted">{tasks.length}</span>
      </h2>
      <TaskList tasks={tasks} showMother invalidate={[["tasks"]]} />
    </section>
  );
}

/** Open, owned work. Never a clinical worklist: "overdue" is administrative.
 * The Overview links here with ?scope=all, ?filter= and ?kind=. */
export function Today() {
  const { t } = useTranslation();
  const [params, setParams] = useSearchParams();
  const scope: Scope = params.get("scope") === "all" ? "all" : "mine";
  const rawFilter = params.get("filter") as TaskFilter | null;
  const filter = rawFilter && TASK_FILTERS.includes(rawFilter) ? rawFilter : null;
  const kind = params.get("kind");

  const tasks = useQuery({ queryKey: ["tasks", scope], queryFn: () => careApi.listTasks(scope === "mine") });
  const shown = tasks.data ? filterTasks(tasks.data, filter, kind) : undefined;
  const groups = groupTasks(shown ?? []);
  const filtered = filter !== null || kind !== null;

  const setScope = (next: Scope) =>
    setParams(
      (p) => {
        if (next === "all") p.set("scope", "all");
        else p.delete("scope");
        return p;
      },
      { replace: true },
    );
  const clearFilter = () =>
    setParams(
      (p) => {
        p.delete("filter");
        p.delete("kind");
        return p;
      },
      { replace: true },
    );

  const filterLabel = [
    filter ? t(`care.today.filter.${filter}`) : null,
    kind ? t(`care.task.kind${kind}`, { defaultValue: kind }) : null,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="space-y-6">
      <PageHeader title={t("care.today.title")} description={t("care.today.note")} />
      <Tabs<Scope>
        label={t("care.today.title")}
        value={scope}
        onChange={setScope}
        items={[
          { value: "mine", label: t("care.today.mine"), icon: UserRound, count: scope === "mine" ? shown?.length : undefined },
          { value: "all", label: t("care.today.all"), icon: Users, count: scope === "all" ? shown?.length : undefined },
        ]}
      />

      {filtered && (
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="inline-flex items-center gap-1.5 text-muted">
            <Filter aria-hidden className="size-4" />
            {t("care.today.filteredBy")}
          </span>
          <button
            type="button"
            onClick={clearFilter}
            className="inline-flex min-h-10 items-center gap-1.5 rounded-full bg-brand-tint px-3 font-semibold text-brand-strong ring-1 ring-brand-soft hover:bg-brand-soft"
            aria-label={t("care.today.clearFilter", { label: filterLabel })}
          >
            {filterLabel}
            <X aria-hidden className="size-4" />
          </button>
        </div>
      )}

      {tasks.isPending && (
        <div className="space-y-3">
          <CardSkeleton lines={2} />
          <CardSkeleton lines={2} />
        </div>
      )}
      {tasks.isError && <PageState kind={errorStateKind(tasks.error)} />}
      {shown?.length === 0 &&
        (filtered ? (
          <PageState kind="empty" title={t("care.today.emptyFiltered")} />
        ) : (
          <PageState
            kind="empty"
            title={scope === "mine" ? t("care.today.emptyMine") : t("care.today.emptyAll")}
            body={t("care.today.emptyBody")}
          />
        ))}
      {shown && shown.length > 0 && (
        <div className="space-y-8">
          <Group icon={AlarmClock} title={t("care.today.groupOverdue")} tasks={groups.overdue} tone="attention" />
          <Group icon={CalendarClock} title={t("care.today.groupToday")} tasks={groups.today} />
          <Group icon={CalendarDays} title={t("care.today.groupLater")} tasks={groups.later} />
          <Group icon={CalendarOff} title={t("care.today.groupUndated")} tasks={groups.undated} />
        </div>
      )}
    </div>
  );
}
