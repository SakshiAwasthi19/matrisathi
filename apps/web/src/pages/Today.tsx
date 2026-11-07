import { useQuery } from "@tanstack/react-query";
import { ListChecks, UserRound, Users } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { careApi } from "../api/client";
import { TaskList } from "../components/care/TaskList";
import { PageHeader } from "../components/PageHeader";
import { errorStateKind, PageState } from "../components/PageState";
import { StatusBadge } from "../components/ui/status";
import { cn } from "../lib/utils";

type Scope = "mine" | "all";

/** The staff console's home: open, owned work. Never a clinical worklist. */
export function Today() {
  const { t } = useTranslation();
  const [scope, setScope] = useState<Scope>("mine");
  const tasks = useQuery({ queryKey: ["tasks", scope], queryFn: () => careApi.listTasks(scope === "mine") });
  const overdue = tasks.data?.filter((x) => x.overdue).length ?? 0;

  const tab = (value: Scope, label: string, Icon: typeof Users) => (
    <button
      type="button"
      role="tab"
      aria-selected={scope === value}
      onClick={() => setScope(value)}
      className={cn(
        "inline-flex min-h-12 flex-1 items-center justify-center gap-2 rounded-md px-4 font-semibold md:min-h-10 md:flex-none",
        scope === value ? "bg-surface text-brand shadow-sm" : "text-muted hover:text-ink",
      )}
    >
      <Icon aria-hidden className="size-4" />
      {label}
    </button>
  );

  return (
    <div className="space-y-6">
      <PageHeader title={t("care.today.title")} />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div role="tablist" className="flex w-full gap-1 rounded-lg bg-subtle p-1 md:inline-flex md:w-auto">
          {tab("mine", t("care.today.mine"), UserRound)}
          {tab("all", t("care.today.all"), Users)}
        </div>
        {overdue > 0 && <StatusBadge kind="attention">{t("care.today.overdueCount", { count: overdue })}</StatusBadge>}
      </div>
      <p className="text-sm text-muted">{t("care.today.note")}</p>

      {tasks.isPending && <PageState kind="loading" />}
      {tasks.isError && <PageState kind={errorStateKind(tasks.error)} />}
      {tasks.data?.length === 0 && (
        <PageState kind="empty" title={scope === "mine" ? t("care.today.emptyMine") : t("care.today.emptyAll")} />
      )}
      {tasks.data && tasks.data.length > 0 && (
        <section aria-label={t("care.task.title")} className="space-y-3">
          <h2 className="flex items-center gap-2 text-lg font-semibold">
            <ListChecks aria-hidden className="size-5 text-brand" />
            {t("care.task.title")} ({tasks.data.length})
          </h2>
          <TaskList tasks={tasks.data} showMother invalidate={[["tasks"]]} />
        </section>
      )}
    </div>
  );
}
