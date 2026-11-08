import { useMutation, useQuery } from "@tanstack/react-query";
import { AlarmClock, ArrowRightLeft, ClipboardList, MessageCircleOff, UserX, Users } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { workApi, type HandoverReason, type PersonLoad, type Workload as WorkloadData } from "../api/client";
import { Avatar } from "../components/Avatar";
import { ActionError, InlineForm, useActionError } from "../components/care/shared";
import { PageHeader } from "../components/PageHeader";
import { errorStateKind, PageState } from "../components/PageState";
import { Button } from "../components/ui/button";
import { Card, CardHeader } from "../components/ui/card";
import { Field, Select } from "../components/ui/field";
import { Badge, CardSkeleton, StatTile } from "../components/ui/kit";
import { Alert, StatusBadge } from "../components/ui/status";
import { useToast } from "../components/ui/toast";
import { formatDateTime } from "../lib/format";
import { canAt } from "../lib/roles";
import { useSession } from "../state/session";

const REASONS: HandoverReason[] = ["UNAVAILABLE_TODAY", "ON_LEAVE", "LEFT_FACILITY", "BALANCING_WORKLOAD"];

function Handover({
  person,
  data,
  facilityId,
  onDone,
}: {
  person: PersonLoad;
  data: WorkloadData;
  facilityId: string;
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const toast = useToast();
  const key = ["workload", facilityId];
  const errors = useActionError([key, ["tasks"]]);
  const candidates = data.people.filter((p) => p.works_here && p.staff_user_id !== person.staff_user_id);
  const [to, setTo] = useState(candidates[0]?.staff_user_id ?? "");
  const [reason, setReason] = useState<HandoverReason>(person.works_here ? "UNAVAILABLE_TODAY" : "LEFT_FACILITY");
  const [includeBackup, setIncludeBackup] = useState(true);
  const move = useMutation({
    mutationFn: () => workApi.handover(facilityId, { from_staff_user_id: person.staff_user_id, to_staff_user_id: to, reason, include_backup: includeBackup }),
    // The message needs the count from the response, so it is raised below.
    meta: { silent: true },
    onSuccess: (r) => {
      errors.reload();
      toast(t("workload.moved", { count: r.owner_moved + r.backup_moved, name: candidates.find((c) => c.staff_user_id === to)?.full_name ?? "" }));
      onDone();
    },
    onError: errors.onError,
  });

  if (candidates.length === 0) return <Alert kind="info">{t("workload.noOneElse")}</Alert>;
  return (
    <>
      <InlineForm onSubmit={() => move.mutate()} onCancel={onDone} submitLabel={t("workload.moveSubmit")} busy={move.isPending || !to}>
        <p className="text-sm text-ink-2">
          {t("workload.moveExplain", { name: person.full_name, owned: person.owned_open, backup: person.backup_open })}
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label={t("workload.toLabel")} htmlFor={`to-${person.staff_user_id}`}>
            <Select id={`to-${person.staff_user_id}`} value={to} onChange={(e) => setTo(e.target.value)}>
              {candidates.map((c) => (
                <option key={c.staff_user_id} value={c.staff_user_id}>
                  {c.full_name} · {t(`nav.role.${c.role}`, { defaultValue: c.role ?? "" })} · {t("workload.openCount", { count: c.owned_open })}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("workload.reasonLabel")} htmlFor={`reason-${person.staff_user_id}`}>
            <Select id={`reason-${person.staff_user_id}`} value={reason} onChange={(e) => setReason(e.target.value as HandoverReason)}>
              {REASONS.map((r) => (
                <option key={r} value={r}>
                  {t(`workload.reason.${r}`)}
                </option>
              ))}
            </Select>
          </Field>
        </div>
        {person.backup_open > 0 && (
          <label className="flex items-center gap-2.5 text-sm">
            <input type="checkbox" className="size-4 accent-[var(--color-brand)]" checked={includeBackup} onChange={(e) => setIncludeBackup(e.target.checked)} />
            {t("workload.includeBackup", { count: person.backup_open })}
          </label>
        )}
      </InlineForm>
      <ActionError message={errors.message} />
    </>
  );
}

function PersonRow({ person, data, max, facilityId, canHandOver }: { person: PersonLoad; data: WorkloadData; max: number; facilityId: string; canHandOver: boolean }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const holdsWork = person.owned_open + person.backup_open > 0;
  return (
    <li className="space-y-3 px-4 py-3.5 md:px-5">
      <div className="flex flex-wrap items-center gap-3">
        <Avatar name={person.full_name} size="sm" />
        <div className="min-w-[10rem] flex-1 leading-tight">
          <p className="font-semibold text-ink">{person.full_name}</p>
          <p className="text-sm text-muted">
            {person.works_here ? t(`nav.role.${person.role}`, { defaultValue: person.role ?? "" }) : t("workload.leftFacility")}
          </p>
        </div>
        <div className="flex w-full items-center gap-3 sm:w-56">
          <div className="h-2 flex-1 rounded-full bg-subtle">
            <div className="h-2 rounded-full bg-[var(--color-series-1)] transition-[width] duration-500" style={{ width: `${max ? (person.owned_open / max) * 100 : 0}%` }} />
          </div>
          <span className="tabular w-16 text-right text-sm font-semibold text-ink">{t("workload.openCount", { count: person.owned_open })}</span>
        </div>
        <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
          {person.owned_overdue > 0 && <StatusBadge kind="attention">{t("workload.overdueCount", { count: person.owned_overdue })}</StatusBadge>}
          {person.backup_open > 0 && <Badge>{t("workload.backupCount", { count: person.backup_open })}</Badge>}
          {!person.works_here && <StatusBadge kind="pending">{t("workload.needsNewOwner")}</StatusBadge>}
        </div>
        {canHandOver && holdsWork && !open && (
          <Button variant={person.works_here ? "secondary" : "primary"} size="sm" onClick={() => setOpen(true)} className="sm:ml-auto">
            <ArrowRightLeft aria-hidden className="size-4" />
            {t("workload.handOver")}
          </Button>
        )}
      </div>
      {open && <Handover person={person} data={data} facilityId={facilityId} onDone={() => setOpen(false)} />}
    </li>
  );
}

/** Who holds how much open work, and handing work over when someone is
 * unavailable (F038, F008). Administrative figures, never clinical priority. */
export function Workload() {
  const { t } = useTranslation();
  const { staff } = useSession();
  const memberships = staff?.memberships ?? [];
  const [facilityId, setFacilityId] = useState(memberships[0]?.facility_id ?? "");
  const query = useQuery({ queryKey: ["workload", facilityId], queryFn: () => workApi.workload(facilityId), enabled: !!facilityId });
  const data = query.data;
  const canHandOver = canAt(memberships, facilityId, "HAND_OVER_WORK");
  const open = data ? data.people.reduce((a, p) => a + p.owned_open, 0) + data.unowned_open : 0;
  const overdue = data ? data.people.reduce((a, p) => a + p.owned_overdue, 0) : 0;
  const max = data ? Math.max(1, ...data.people.map((p) => p.owned_open)) : 1;
  const gone = data?.people.filter((p) => !p.works_here) ?? [];

  if (memberships.length === 0) return <PageState kind="no-access" />;

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("workload.title")}
        description={t("workload.description")}
        actions={
          memberships.length > 1 ? (
            <Select aria-label={t("nav.facility")} value={facilityId} onChange={(e) => setFacilityId(e.target.value)} className="w-auto">
              {memberships.map((m) => (
                <option key={m.facility_id} value={m.facility_id}>
                  {m.facility_name}
                </option>
              ))}
            </Select>
          ) : undefined
        }
      />

      <section className="grid grid-cols-2 gap-3 md:gap-4 xl:grid-cols-4">
        <StatTile label={t("workload.tileOpen")} value={data ? open : "—"} icon={ClipboardList} to="/today" />
        <StatTile label={t("workload.tileUnowned")} value={data ? data.unowned_open : "—"} icon={UserX} tone={data?.unowned_open ? "accent" : "brand"} to="/today" />
        <StatTile label={t("workload.tileOverdue")} value={data ? overdue : "—"} icon={AlarmClock} tone={overdue ? "accent" : "brand"} hint={t("overview.kpiOverdueHint")} />
        <StatTile label={t("workload.tileTeam")} value={data ? data.people.filter((p) => p.works_here).length : "—"} icon={Users} />
      </section>

      {gone.length > 0 && (
        <Alert kind="pending" title={t("workload.goneTitle", { count: gone.length })}>
          {t("workload.goneBody")}
        </Alert>
      )}

      <Card className="overflow-hidden p-0 md:p-0">
        <div className="p-4 pb-0 md:p-5 md:pb-0">
          <CardHeader
            icon={Users}
            title={t("workload.teamTitle")}
            description={data ? t("workload.asOf", { time: formatDateTime(data.as_of) }) : t("workload.teamBody")}
          />
        </div>
        {query.isPending && (
          <div className="p-4 md:p-5">
            <CardSkeleton lines={4} />
          </div>
        )}
        {query.isError && (
          <div className="p-4 md:p-5">
            <PageState kind={errorStateKind(query.error)} />
          </div>
        )}
        {data && data.people.length === 0 && <p className="px-5 py-8 text-center text-muted">{t("workload.emptyTeam")}</p>}
        {data && data.people.length > 0 && (
          <ul className="divide-y divide-line/70 border-t border-line">
            {data.people.map((p) => (
              <PersonRow key={p.staff_user_id} person={p} data={data} max={max} facilityId={facilityId} canHandOver={canHandOver} />
            ))}
          </ul>
        )}
        {data && data.unowned_open > 0 && (
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line bg-page/60 px-4 py-3 text-sm md:px-5">
            <span className="text-ink-2">{t("workload.unownedLine", { count: data.unowned_open })}</span>
            <Link to="/today" className="font-semibold text-brand hover:text-brand-strong">
              {t("workload.assignOnToday")}
            </Link>
          </div>
        )}
      </Card>

      <Card>
        <CardHeader icon={MessageCircleOff} title={t("workload.messagingTitle")} description={t("workload.messagingBody")} />
        <Badge>{t("workload.messagingTag")}</Badge>
      </Card>
    </div>
  );
}
