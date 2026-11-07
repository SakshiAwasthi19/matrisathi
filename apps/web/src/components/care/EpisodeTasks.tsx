import { useQuery } from "@tanstack/react-query";
import { ListChecks } from "lucide-react";
import { useTranslation } from "react-i18next";
import { careApi } from "../../api/client";
import { errorStateKind, PageState } from "../PageState";
import { Card, Section } from "../ui/card";
import { Alert } from "../ui/status";
import { TaskList } from "./TaskList";

export function EpisodeTasks({ episodeId }: { episodeId: string }) {
  const { t } = useTranslation();
  const tasks = useQuery({ queryKey: ["episodeTasks", episodeId], queryFn: () => careApi.listEpisodeTasks(episodeId) });
  const open = tasks.data?.filter((x) => x.status === "NEW" || x.status === "ASSIGNED" || x.status === "AWAITING_PATIENT") ?? [];
  return (
    <Card>
      <Section icon={ListChecks} title={t("care.task.title")}>
        {tasks.isPending && <PageState kind="loading" />}
        {tasks.isError && <PageState kind={errorStateKind(tasks.error)} />}
        {tasks.data && open.length === 0 && <Alert kind="info">{t("care.task.empty")}</Alert>}
        {open.length > 0 && <TaskList tasks={open} invalidate={[["episodeTasks", episodeId], ["tasks"]]} />}
      </Section>
    </Card>
  );
}
