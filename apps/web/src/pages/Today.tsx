import { useQuery } from "@tanstack/react-query";
import { AlarmClock, CalendarClock, CalendarDays, CalendarOff, UserRound, Users, type LucideIcon } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { careApi, type CareTask } from "../api/client";
import { TaskList } from "../components/care/TaskList";
import { PageHeader } from "../components/PageHeader";
import { errorStateKind, PageState } from "../components/PageState";
import { CardSkeleton, Tabs } from "../components/ui/kit";
import { groupTasks } from "../lib/worklist";

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

/** Open, owned work. Never a clinical worklist: "overdue" is administrative. */
export function Today() {
  const { t } = useTranslation();
  const [scope, setScope] = useState<Scope>("mine");
  const tasks = useQuery({ queryKey: ["tasks", scope], queryFn: () => careApi.listTasks(scope === "mine") });
  const groups = groupTasks(tasks.data ?? []);

  return (
    <div className="space-y-6">
      <PageHeader title={t("care.today.title")} description={t("care.today.note")} />
      <Tabs<Scope>
        label={t("care.today.title")}
        value={scope}
        onChange={setScope}
        items={[
          { value: "mine", label: t("care.today.mine"), icon: UserRound, count: scope === "mine" ? tasks.data?.length : undefined },
          { value: "all", label: t("care.today.all"), icon: Users, count: scope === "all" ? tasks.data?.length : undefined },
        ]}
      />

      {tasks.isPending && (
        <div className="space-y-3">
          <CardSkeleton lines={2} />
          <CardSkeleton lines={2} />
        </div>
      )}
      {tasks.isError && <PageState kind={errorStateKind(tasks.error)} />}
      {tasks.data?.length === 0 && (
        <PageState kind="empty" title={scope === "mine" ? t("care.today.emptyMine") : t("care.today.emptyAll")} body={t("care.today.emptyBody")} />
      )}
      {tasks.data && tasks.data.length > 0 && (
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
