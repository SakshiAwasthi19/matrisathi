import { useMutation } from "@tanstack/react-query";
import { ArrowRight, Clock3, UserRound } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import {
  careApi,
  type Barrier,
  type CareTask,
  type ClosureReason,
  type TaskOutcome,
  type TaskStatus,
} from "../../api/client";
import { formatDate, formatDateTime } from "../../lib/format";
import { useSession } from "../../state/session";
import { Button } from "../ui/button";
import { Field, Select } from "../ui/field";
import { StatusBadge, type StatusKind } from "../ui/status";
import { ActionError, InlineForm, useActionError } from "./shared";

const STATUS_KIND: Record<TaskStatus, StatusKind> = {
  NEW: "pending",
  ASSIGNED: "neutral",
  AWAITING_PATIENT: "pending",
  COMPLETED: "confirmed",
  CANCELLED: "neutral",
};
const BARRIERS: Barrier[] = ["TRAVEL", "COST", "MEDICINE_ACCESS", "CHILDCARE", "WORK", "FAMILY", "OTHER"];
const OUTCOMES: TaskOutcome[] = ["DONE", "DECLINED", "UNREACHABLE", "UNKNOWN", "NOT_NEEDED"];
// Reasons offered for each outcome (the server accepts any listed reason).
const REASONS: Record<TaskOutcome, ClosureReason[]> = {
  DONE: ["DONE_AS_PLANNED"],
  DECLINED: ["FAMILY_DECLINED"],
  UNREACHABLE: ["COULD_NOT_REACH"],
  UNKNOWN: ["OUTCOME_UNKNOWN"],
  NOT_NEEDED: ["NO_LONGER_NEEDED", "DUPLICATE", "RECORDED_IN_ERROR"],
};

type Mode = "none" | "attempt" | "close";

function TaskRow({ task, showMother, invalidate }: { task: CareTask; showMother: boolean; invalidate: string[][] }) {
  const { t } = useTranslation();
  const { staff } = useSession();
  const errors = useActionError(invalidate);
  const [mode, setMode] = useState<Mode>("none");
  const [awaiting, setAwaiting] = useState(false);
  const [barrier, setBarrier] = useState<Barrier | "">("");
  const [outcome, setOutcome] = useState<TaskOutcome>("DONE");
  const [reason, setReason] = useState<ClosureReason>("DONE_AS_PLANNED");

  const finish = () => {
    setMode("none");
    errors.clear();
    errors.reload();
  };
  const assign = useMutation({ mutationFn: () => careApi.assignTask(task.id, task.version, staff!.id), onSuccess: finish, onError: errors.onError });
  const attempt = useMutation({
    mutationFn: () => careApi.recordAttempt(task.id, task.version, awaiting, barrier || null),
    onSuccess: finish,
    onError: errors.onError,
  });
  const close = useMutation({ mutationFn: () => careApi.closeTask(task.id, task.version, outcome, reason), onSuccess: finish, onError: errors.onError });
  const open = task.status === "NEW" || task.status === "ASSIGNED" || task.status === "AWAITING_PATIENT";
  const working = task.status === "ASSIGNED" || task.status === "AWAITING_PATIENT";

  return (
    <li className="space-y-3 rounded-lg border border-line bg-surface p-3 md:p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-semibold">{task.name ?? t(`care.task.kind${task.kind}`)}</p>
          {showMother && (
            <Link to={`/episodes/${task.episode_id}`} className="inline-flex min-h-10 items-center gap-1 font-semibold text-brand">
              {task.mother_full_name}
              <ArrowRight aria-hidden className="size-4" />
            </Link>
          )}
          <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted">
            <span className="inline-flex items-center gap-1">
              <UserRound aria-hidden className="size-4" />
              {task.owner_name ? t("care.task.owner", { name: task.owner_name }) : t("care.task.noOwner")}
            </span>
            {task.due_at && (
              <span className="inline-flex items-center gap-1">
                <Clock3 aria-hidden className="size-4" />
                {t("care.task.due", { date: formatDate(task.due_at.slice(0, 10)) })}
              </span>
            )}
            {task.last_attempt_at && <span>{t("care.task.lastAttempt", { date: formatDateTime(task.last_attempt_at) })}</span>}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {task.overdue && <StatusBadge kind="attention">{t("care.task.overdue")}</StatusBadge>}
          <StatusBadge kind={STATUS_KIND[task.status]}>
            {task.outcome ? t(`care.task.outcome${task.outcome}`) : t(`care.task.status${task.status}`)}
          </StatusBadge>
        </div>
      </div>

      <ActionError message={errors.message} />

      {open && mode === "none" && (
        <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
          {task.status === "NEW" && staff && (
            <Button disabled={assign.isPending} onClick={() => assign.mutate()}>
              {t("care.task.assignToMe")}
            </Button>
          )}
          {working && (
            <Button variant="secondary" onClick={() => setMode("attempt")}>
              {t("care.task.recordAttempt")}
            </Button>
          )}
          <Button variant={working ? "primary" : "secondary"} onClick={() => setMode("close")}>
            {t("care.task.close")}
          </Button>
        </div>
      )}

      {mode === "attempt" && (
        <InlineForm submitLabel={t("care.save")} busy={attempt.isPending} onCancel={() => setMode("none")} onSubmit={() => attempt.mutate()}>
          <Field label={t("care.task.barrier")} htmlFor={`barrier_${task.id}`}>
            <Select id={`barrier_${task.id}`} value={barrier} onChange={(e) => setBarrier(e.target.value as Barrier | "")}>
              <option value="">{t("care.task.noBarrier")}</option>
              {BARRIERS.map((b) => (
                <option key={b} value={b}>
                  {t(`care.task.barrier${b}`)}
                </option>
              ))}
            </Select>
          </Field>
          <label className="inline-flex min-h-12 items-center gap-3 md:min-h-10">
            <input type="checkbox" className="size-5 accent-brand" checked={awaiting} onChange={(e) => setAwaiting(e.target.checked)} />
            {t("care.task.awaiting")}
          </label>
        </InlineForm>
      )}
      {mode === "close" && (
        <InlineForm submitLabel={t("care.task.close")} busy={close.isPending} onCancel={() => setMode("none")} onSubmit={() => close.mutate()}>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t("care.task.outcome")} htmlFor={`outcome_${task.id}`}>
              <Select
                id={`outcome_${task.id}`}
                value={outcome}
                onChange={(e) => {
                  const next = e.target.value as TaskOutcome;
                  setOutcome(next);
                  setReason(REASONS[next][0]);
                }}
              >
                {OUTCOMES.map((o) => (
                  <option key={o} value={o}>
                    {t(`care.task.outcome${o}`)}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("care.task.reason")} htmlFor={`reason_${task.id}`}>
              <Select id={`reason_${task.id}`} value={reason} onChange={(e) => setReason(e.target.value as ClosureReason)}>
                {REASONS[outcome].map((r) => (
                  <option key={r} value={r}>
                    {t(`care.task.reason${r}`)}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
        </InlineForm>
      )}
    </li>
  );
}

export function TaskList({
  tasks,
  showMother = false,
  invalidate,
}: {
  tasks: CareTask[];
  showMother?: boolean;
  invalidate: string[][];
}) {
  return (
    <ul className="space-y-3">
      {tasks.map((task) => (
        <TaskRow key={task.id} task={task} showMother={showMother} invalidate={invalidate} />
      ))}
    </ul>
  );
}
