import { useInfiniteQuery, useMutation, useQuery } from "@tanstack/react-query";
import { Building2, History, KeyRound, Plus, ShieldCheck, UserMinus, UserPlus, UsersRound } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { adminApi, type AuditFilter, type Facility, type OrgMembership, type OrgStaff, type StaffRole } from "../../api/client";
import { Avatar } from "../../components/Avatar";
import { ActionError, InlineForm, useActionError } from "../../components/care/shared";
import { PageHeader } from "../../components/PageHeader";
import { errorStateKind, PageState } from "../../components/PageState";
import { Button } from "../../components/ui/button";
import { Card, CardHeader } from "../../components/ui/card";
import { Field, Input, Select } from "../../components/ui/field";
import { Badge, CardSkeleton, Tabs } from "../../components/ui/kit";
import { Alert, StatusBadge } from "../../components/ui/status";
import { formatDate, formatDateTime } from "../../lib/format";
import { useSession } from "../../state/session";

const ROLES: StaffRole[] = ["ASHA", "ANM", "NURSE", "COORDINATOR", "DOCTOR"];
type AdminTab = "staff" | "facilities" | "audit";

// --- Staff ----------------------------------------------------------------------------

function MembershipLine({ m, invalidate }: { m: OrgMembership; invalidate: string[][] }) {
  const { t } = useTranslation();
  const errors = useActionError(invalidate);
  const [mode, setMode] = useState<"none" | "role" | "end">("none");
  const [role, setRole] = useState<StaffRole>(m.role);
  const done = () => {
    setMode("none");
    errors.clear();
    errors.reload();
  };
  const change = useMutation({
    mutationFn: () => adminApi.changeRole(m.facility_id, m.id, role),
    meta: { toast: t("admin.roleChanged") },
    onSuccess: done,
    onError: errors.onError,
  });
  const end = useMutation({
    mutationFn: () => adminApi.revoke(m.facility_id, m.id),
    meta: { toast: t("admin.accessEnded") },
    onSuccess: done,
    onError: errors.onError,
  });

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Building2 aria-hidden className="size-4 text-faint" />
        <span className="font-medium text-ink-2">{m.facility_name}</span>
        <Badge tone={m.role === "DOCTOR" ? "brand" : "neutral"}>{t(`nav.role.${m.role}`)}</Badge>
        {m.active ? (
          <span className="text-muted">{t("admin.since", { date: formatDate(m.granted_at) })}</span>
        ) : (
          <StatusBadge kind="neutral">{t("admin.endedOn", { date: formatDate(m.revoked_at) })}</StatusBadge>
        )}
        {m.active && mode === "none" && (
          <span className="ml-auto flex gap-1">
            <Button variant="ghost" size="sm" onClick={() => setMode("role")}>
              <KeyRound aria-hidden className="size-4" />
              {t("admin.changeRole")}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setMode("end")}>
              <UserMinus aria-hidden className="size-4" />
              {t("admin.endAccess")}
            </Button>
          </span>
        )}
      </div>
      {mode === "role" && (
        <InlineForm onSubmit={() => change.mutate()} onCancel={() => setMode("none")} submitLabel={t("admin.saveRole")} busy={change.isPending || role === m.role}>
          <Field label={t("admin.newRole")} htmlFor={`role-${m.id}`} hint={t("admin.roleHint")}>
            <Select id={`role-${m.id}`} value={role} onChange={(e) => setRole(e.target.value as StaffRole)}>
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {t(`nav.role.${r}`)}
                </option>
              ))}
            </Select>
          </Field>
        </InlineForm>
      )}
      {mode === "end" && (
        <InlineForm onSubmit={() => end.mutate()} onCancel={() => setMode("none")} submitLabel={t("admin.endConfirm")} busy={end.isPending}>
          <p className="text-sm text-ink-2">{t("admin.endExplain", { facility: m.facility_name })}</p>
        </InlineForm>
      )}
      <ActionError message={errors.message} />
    </div>
  );
}

function AddStaff({ orgId, facilities, invalidate, onDone }: { orgId: string; facilities: Facility[]; invalidate: string[][]; onDone: () => void }) {
  const { t } = useTranslation();
  const errors = useActionError(invalidate);
  const active = facilities.filter((f) => f.active);
  const [form, setForm] = useState({ full_name: "", username: "", password: "", facility_id: active[0]?.id ?? "", role: "ASHA" as StaffRole });
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const create = useMutation({
    mutationFn: () => adminApi.createStaff({ organization_id: orgId, ...form }),
    meta: { toast: t("admin.staffAdded", { name: form.full_name }) },
    onSuccess: () => {
      errors.reload();
      onDone();
    },
    onError: errors.onError,
  });
  return (
    <div className="space-y-3">
      <InlineForm onSubmit={() => create.mutate()} onCancel={onDone} submitLabel={t("admin.createStaff")} busy={create.isPending}>
        <div className="grid gap-3 md:grid-cols-2">
          <Field label={t("admin.fullName")} htmlFor="s-name">
            <Input id="s-name" required maxLength={200} value={form.full_name} onChange={set("full_name")} />
          </Field>
          <Field label={t("admin.username")} htmlFor="s-user" hint={t("admin.usernameHint")}>
            <Input id="s-user" required minLength={3} maxLength={100} autoComplete="off" value={form.username} onChange={set("username")} />
          </Field>
          <Field label={t("admin.tempPassword")} htmlFor="s-pw" hint={t("admin.tempPasswordHint")}>
            <Input id="s-pw" type="password" required minLength={12} autoComplete="new-password" value={form.password} onChange={set("password")} />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label={t("nav.facility")} htmlFor="s-fac">
              <Select id="s-fac" required value={form.facility_id} onChange={set("facility_id")}>
                {active.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("admin.role")} htmlFor="s-role">
              <Select id="s-role" value={form.role} onChange={set("role")}>
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {t(`nav.role.${r}`)}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
        </div>
      </InlineForm>
      <ActionError message={errors.message} />
    </div>
  );
}

function StaffTab({ orgId }: { orgId: string }) {
  const { t } = useTranslation();
  const [showEnded, setShowEnded] = useState(false);
  const [adding, setAdding] = useState(false);
  const staffKey = ["admin-staff", orgId, String(showEnded)];
  const staff = useQuery({ queryKey: staffKey, queryFn: () => adminApi.staff(orgId, showEnded) });
  const facilities = useQuery({ queryKey: ["admin-facilities", orgId], queryFn: () => adminApi.facilities(orgId) });
  const invalidate = [["admin-staff", orgId]];

  return (
    <Card>
      <CardHeader
        icon={UsersRound}
        title={t("admin.staffTitle")}
        description={t("admin.staffBody")}
        actions={
          <>
            <label className="inline-flex items-center gap-2 text-sm text-muted">
              <input type="checkbox" className="size-4 accent-[var(--color-brand)]" checked={showEnded} onChange={(e) => setShowEnded(e.target.checked)} />
              {t("admin.showEnded")}
            </label>
            {!adding && (
              <Button size="sm" onClick={() => setAdding(true)} disabled={!facilities.data?.length}>
                <UserPlus aria-hidden className="size-4" />
                {t("admin.addStaff")}
              </Button>
            )}
          </>
        }
      />
      <div className="space-y-4">
        {adding && facilities.data && (
          <AddStaff orgId={orgId} facilities={facilities.data} invalidate={invalidate} onDone={() => setAdding(false)} />
        )}
        {staff.isPending && <CardSkeleton lines={4} />}
        {staff.isError && <PageState kind={errorStateKind(staff.error)} />}
        {staff.data && staff.data.length === 0 && <p className="py-6 text-center text-muted">{t("admin.noStaff")}</p>}
        {staff.data && staff.data.length > 0 && (
          <ul className="divide-y divide-line/70 rounded-xl border border-line">
            {staff.data.map((s: OrgStaff) => (
              <li key={s.id} className="space-y-3 p-4">
                <div className="flex items-center gap-3">
                  <Avatar name={s.full_name} size="sm" />
                  <div className="min-w-0 flex-1 leading-tight">
                    <p className="font-semibold text-ink">{s.full_name}</p>
                    <p className="font-mono text-xs text-muted">{s.username}</p>
                  </div>
                  {!s.active && <StatusBadge kind="neutral">{t("admin.accountDisabled")}</StatusBadge>}
                </div>
                <div className="space-y-2 pl-11">
                  {s.memberships.map((m) => (
                    <MembershipLine key={m.id} m={m} invalidate={invalidate} />
                  ))}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}

// --- Facilities -------------------------------------------------------------------------

function FacilitiesTab({ orgId }: { orgId: string }) {
  const { t } = useTranslation();
  const key = ["admin-facilities", orgId];
  const errors = useActionError([key]);
  const facilities = useQuery({ queryKey: key, queryFn: () => adminApi.facilities(orgId) });
  const staff = useQuery({ queryKey: ["admin-staff", orgId, "false"], queryFn: () => adminApi.staff(orgId, false) });
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const create = useMutation({
    mutationFn: () => adminApi.createFacility(orgId, name.trim()),
    meta: { toast: t("admin.facilityAdded", { name: name.trim() }) },
    onSuccess: () => {
      setAdding(false);
      setName("");
      errors.reload();
    },
    onError: errors.onError,
  });
  const count = (fid: string) =>
    staff.data?.filter((s) => s.memberships.some((m) => m.facility_id === fid && m.active)).length ?? 0;

  return (
    <Card>
      <CardHeader
        icon={Building2}
        title={t("admin.facilitiesTitle")}
        description={t("admin.facilitiesBody")}
        actions={
          !adding && (
            <Button size="sm" onClick={() => setAdding(true)}>
              <Plus aria-hidden className="size-4" />
              {t("admin.addFacility")}
            </Button>
          )
        }
      />
      <div className="space-y-4">
        {adding && (
          <InlineForm onSubmit={() => create.mutate()} onCancel={() => setAdding(false)} submitLabel={t("admin.createFacility")} busy={create.isPending || !name.trim()}>
            <Field label={t("admin.facilityName")} htmlFor="f-name">
              <Input id="f-name" required maxLength={200} value={name} onChange={(e) => setName(e.target.value)} />
            </Field>
          </InlineForm>
        )}
        <ActionError message={errors.message} />
        {facilities.isPending && <CardSkeleton lines={3} />}
        {facilities.isError && <PageState kind={errorStateKind(facilities.error)} />}
        {facilities.data && (
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {facilities.data.map((f) => (
              <li key={f.id} className="rounded-xl border border-line bg-surface p-4 shadow-card">
                <div className="flex items-start justify-between gap-2">
                  <span className="inline-flex size-9 items-center justify-center rounded-lg bg-brand-tint text-brand ring-1 ring-brand-soft">
                    <Building2 aria-hidden className="size-4" />
                  </span>
                  <StatusBadge kind={f.active ? "confirmed" : "neutral"}>{f.active ? t("admin.active") : t("admin.inactive")}</StatusBadge>
                </div>
                <p className="mt-3 font-semibold text-ink">{f.name}</p>
                <p className="text-sm text-muted">{t("admin.staffCount", { count: count(f.id) })}</p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}

// --- Audit trail (F037) ----------------------------------------------------------------

function AuditTab({ orgId }: { orgId: string }) {
  const { t } = useTranslation();
  const [outcome, setOutcome] = useState<AuditFilter["outcome"] | "">("");
  const [action, setAction] = useState("");
  const filter: AuditFilter = { outcome: outcome || undefined, action: action.trim() || undefined, limit: 50 };
  const pages = useInfiniteQuery({
    queryKey: ["admin-audit", orgId, filter.outcome ?? "", filter.action ?? ""],
    queryFn: ({ pageParam }) => adminApi.audit(orgId, { ...filter, before: pageParam || undefined }),
    initialPageParam: "",
    getNextPageParam: (last) => (last.has_more ? last.events[last.events.length - 1]?.occurred_at : undefined),
  });
  const events = pages.data?.pages.flatMap((p) => p.events) ?? [];

  return (
    <Card className="overflow-hidden p-0 md:p-0">
      <div className="space-y-4 p-4 md:p-5">
        <CardHeader icon={History} title={t("admin.auditTitle")} description={t("admin.auditBody")} className="mb-0" />
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <Field label={t("admin.outcome")} htmlFor="a-outcome">
            <Select id="a-outcome" value={outcome} onChange={(e) => setOutcome(e.target.value as AuditFilter["outcome"] | "")}>
              <option value="">{t("admin.allOutcomes")}</option>
              <option value="SUCCESS">{t("admin.outcomeSUCCESS")}</option>
              <option value="DENIED">{t("admin.outcomeDENIED")}</option>
            </Select>
          </Field>
          <div className="flex-1">
            <Field label={t("admin.action")} htmlFor="a-action" hint={t("admin.actionHint")}>
              <Input id="a-action" value={action} onChange={(e) => setAction(e.target.value)} placeholder="login, create, grant_caregiver…" />
            </Field>
          </div>
        </div>
      </div>
      {pages.isPending && (
        <div className="px-5 pb-5">
          <CardSkeleton lines={5} />
        </div>
      )}
      {pages.isError && (
        <div className="px-5 pb-5">
          <PageState kind={errorStateKind(pages.error)} />
        </div>
      )}
      {pages.data && events.length === 0 && <p className="px-5 pb-8 text-center text-muted">{t("admin.noEvents")}</p>}
      {events.length > 0 && (
        <div className="overflow-x-auto border-t border-line">
          <table className="w-full min-w-[46rem] text-left text-sm">
            <thead>
              <tr className="bg-page/60 text-xs font-semibold tracking-wide text-muted uppercase">
                <th scope="col" className="px-5 py-3">{t("admin.col.when")}</th>
                <th scope="col" className="px-3 py-3">{t("admin.col.who")}</th>
                <th scope="col" className="px-3 py-3">{t("admin.col.action")}</th>
                <th scope="col" className="px-3 py-3">{t("admin.col.record")}</th>
                <th scope="col" className="px-5 py-3">{t("admin.col.outcome")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line/70">
              {events.map((e) => (
                <tr key={e.id} className="align-top transition-colors hover:bg-subtle/50">
                  <td className="tabular px-5 py-2.5 whitespace-nowrap text-muted">{formatDateTime(e.occurred_at)}</td>
                  <td className="px-3 py-2.5">
                    <span className="font-medium text-ink">{e.actor_name}</span>
                    <span className="block font-mono text-xs text-faint">{e.actor_username}</span>
                  </td>
                  <td className="px-3 py-2.5 font-mono text-xs text-ink-2">{e.action}</td>
                  <td className="px-3 py-2.5 text-ink-2">
                    {e.entity_type}
                    {e.entity_id && <span className="block font-mono text-xs text-faint">{e.entity_id.slice(0, 8)}…</span>}
                  </td>
                  <td className="px-5 py-2.5">
                    <StatusBadge kind={e.outcome === "DENIED" ? "attention" : "confirmed"}>{t(`admin.outcome${e.outcome}`)}</StatusBadge>
                    {e.details.reason && <span className="mt-1 block text-xs text-muted">{e.details.reason}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {pages.hasNextPage && (
        <div className="border-t border-line p-4 text-center">
          <Button variant="secondary" onClick={() => void pages.fetchNextPage()} disabled={pages.isFetchingNextPage}>
            {pages.isFetchingNextPage ? t("admin.loading") : t("admin.loadOlder")}
          </Button>
        </div>
      )}
    </Card>
  );
}

/** Organisation administration: staff, facilities and the audit trail.
 * Needs an organisation-admin grant, which gives no access to records (F004). */
export function Admin() {
  const { t } = useTranslation();
  const { staff } = useSession();
  const orgs = staff?.admin_organizations ?? [];
  const [orgId, setOrgId] = useState(orgs[0]?.id ?? "");
  const [tab, setTab] = useState<AdminTab>("staff");

  if (orgs.length === 0) return <PageState kind="no-access" />;

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("admin.title")}
        description={t("admin.description")}
        showContext={false}
        badge={
          <Badge tone="brand" icon={ShieldCheck}>
            {orgs.find((o) => o.id === orgId)?.name}
          </Badge>
        }
        actions={
          orgs.length > 1 ? (
            <Select aria-label={t("admin.organisation")} value={orgId} onChange={(e) => setOrgId(e.target.value)} className="w-auto">
              {orgs.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.name}
                </option>
              ))}
            </Select>
          ) : undefined
        }
      />
      <Alert kind="info">{t("admin.noRecordAccess")}</Alert>
      <Tabs
        label={t("admin.title")}
        value={tab}
        onChange={setTab}
        items={[
          { value: "staff", label: t("admin.tabStaff"), icon: UsersRound },
          { value: "facilities", label: t("admin.tabFacilities"), icon: Building2 },
          { value: "audit", label: t("admin.tabAudit"), icon: History },
        ]}
      />
      <div key={tab} className="animate-fade-in">
        {tab === "staff" && <StaffTab orgId={orgId} />}
        {tab === "facilities" && <FacilitiesTab orgId={orgId} />}
        {tab === "audit" && <AuditTab orgId={orgId} />}
      </div>
    </div>
  );
}
