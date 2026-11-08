import { useMutation, useQuery } from "@tanstack/react-query";
import { CalendarClock, HeartHandshake, Search, ShieldCheck, UserPlus } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  api,
  caregiverApi,
  type CaregiverGrant,
  type CaregiverScope,
  type Person,
  type RevokeReason,
  type VerificationMethod,
} from "../../api/client";
import { formatDate, todayIso } from "../../lib/format";
import { Avatar } from "../Avatar";
import { Button } from "../ui/button";
import { Card, CardHeader } from "../ui/card";
import { Field, Input, Select } from "../ui/field";
import { Badge, CardSkeleton } from "../ui/kit";
import { Alert, StatusBadge, type StatusKind } from "../ui/status";
import { ActionError, InlineForm, useActionError } from "./shared";

const SCOPES: CaregiverScope[] = ["NEXT_ACTION", "BIRTH_PLAN", "REMINDERS"];
const METHODS: VerificationMethod[] = ["IN_PERSON_DOCUMENT", "IN_PERSON_KNOWN_TO_STAFF", "IN_PERSON_OTHER"];
const REASONS: RevokeReason[] = ["REQUESTED_BY_SUBJECT", "SAFETY_CONCERN", "REPLACED", "RECORDED_IN_ERROR"];
const STATE_KIND: Record<CaregiverGrant["state"], StatusKind> = { ACTIVE: "confirmed", EXPIRED: "not-recorded", REVOKED: "neutral" };

function in90Days(): string {
  const d = new Date();
  d.setDate(d.getDate() + 90);
  return todayIso(d);
}

function GrantRow({ grant, canManage, invalidate }: { grant: CaregiverGrant; canManage: boolean; invalidate: string[][] }) {
  const { t } = useTranslation();
  const errors = useActionError(invalidate);
  const [revoking, setRevoking] = useState(false);
  const [reason, setReason] = useState<RevokeReason>("REQUESTED_BY_SUBJECT");
  const revoke = useMutation({
    mutationFn: () => caregiverApi.revoke(grant.id, grant.version, reason),
    meta: { toast: t("family.revoked", { name: grant.grantee_full_name }) },
    onSuccess: () => {
      setRevoking(false);
      errors.clear();
      errors.reload();
    },
    onError: errors.onError,
  });

  return (
    <li className="space-y-3 rounded-xl border border-line bg-surface p-4 transition-shadow hover:shadow-card">
      <div className="flex flex-wrap items-start gap-3">
        <Avatar name={grant.grantee_full_name} size="sm" />
        <div className="min-w-0 flex-1 space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-semibold text-ink">{grant.grantee_full_name}</p>
            <StatusBadge kind={STATE_KIND[grant.state]}>{t(`family.state.${grant.state}`)}</StatusBadge>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {grant.scopes.map((s) => (
              <Badge key={s} tone="brand">
                {t(`family.scope.${s}`)}
              </Badge>
            ))}
          </div>
          <p className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted">
            <span className="inline-flex items-center gap-1">
              <ShieldCheck aria-hidden className="size-4" />
              {t("family.verifiedBy", { name: grant.verified_by_name ?? "—", method: t(`family.method.${grant.verification_method}`) })}
            </span>
            <span className="inline-flex items-center gap-1">
              <CalendarClock aria-hidden className="size-4" />
              {grant.state === "REVOKED"
                ? t("family.endedOn", {
                    date: formatDate(grant.revoked_at),
                    name: grant.revoked_by_name ?? "—",
                    reason: t(`family.reason.${grant.revoke_reason}`),
                  })
                : t(grant.state === "EXPIRED" ? "family.expiredOn" : "family.validUntil", { date: formatDate(grant.expires_on) })}
            </span>
          </p>
        </div>
        {canManage && grant.state === "ACTIVE" && !revoking && (
          <Button variant="secondary" size="sm" onClick={() => setRevoking(true)}>
            {t("family.end")}
          </Button>
        )}
      </div>
      {revoking && (
        <InlineForm onSubmit={() => revoke.mutate()} onCancel={() => setRevoking(false)} submitLabel={t("family.endConfirm")} busy={revoke.isPending}>
          <p className="text-sm text-ink-2">{t("family.endExplain", { name: grant.grantee_full_name })}</p>
          <Field label={t("family.reasonLabel")} htmlFor={`reason-${grant.id}`}>
            <Select id={`reason-${grant.id}`} value={reason} onChange={(e) => setReason(e.target.value as RevokeReason)}>
              {REASONS.map((r) => (
                <option key={r} value={r}>
                  {t(`family.reason.${r}`)}
                </option>
              ))}
            </Select>
          </Field>
        </InlineForm>
      )}
      <ActionError message={errors.message} />
    </li>
  );
}

function AddGrant({ subject, invalidate, onDone }: { subject: Person; invalidate: string[][]; onDone: () => void }) {
  const { t } = useTranslation();
  const errors = useActionError(invalidate);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Person[] | null>(null);
  const [grantee, setGrantee] = useState<Person | null>(null);
  const [scopes, setScopes] = useState<CaregiverScope[]>(["NEXT_ACTION"]);
  const [method, setMethod] = useState<VerificationMethod>("IN_PERSON_DOCUMENT");
  const [until, setUntil] = useState(in90Days());
  const [consent, setConsent] = useState(false);

  const search = useMutation({
    mutationFn: () => {
      const q = query.trim();
      return api.searchPeople(/^[+\d\s-]+$/.test(q) ? { phone: q } : { full_name: q });
    },
    meta: { silent: true },
    onSuccess: (people) => setResults(people.filter((p) => p.id !== subject.id)),
    onError: errors.onError,
  });
  const save = useMutation({
    mutationFn: () =>
      caregiverApi.grant(subject.id, {
        grantee_person_id: grantee!.id,
        scopes,
        verification_method: method,
        expires_on: until || null,
        consent_confirmed: consent,
      }),
    meta: { toast: t("family.granted", { name: grantee?.full_name ?? "" }) },
    onSuccess: () => {
      errors.reload();
      onDone();
    },
    onError: errors.onError,
  });

  return (
    <div className="space-y-4 rounded-xl border border-brand-soft bg-brand-tint/40 p-4">
      {!grantee ? (
        <>
          <form
            className="flex flex-col gap-2 sm:flex-row sm:items-end"
            onSubmit={(e) => {
              e.preventDefault();
              if (query.trim()) search.mutate();
            }}
          >
            <div className="flex-1">
              <Field label={t("family.findLabel")} htmlFor="fa-search" hint={t("family.findHint")}>
                <Input id="fa-search" value={query} onChange={(e) => setQuery(e.target.value)} />
              </Field>
            </div>
            <Button type="submit" disabled={search.isPending || !query.trim()}>
              <Search aria-hidden className="size-4" />
              {t("find.submit")}
            </Button>
          </form>
          {results && results.length === 0 && <Alert kind="info">{t("family.noMatch")}</Alert>}
          {results && results.length > 0 && (
            <ul className="divide-y divide-line rounded-lg border border-line bg-surface">
              {results.map((p) => (
                <li key={p.id} className="flex items-center gap-3 px-3 py-2.5">
                  <Avatar name={p.full_name} size="sm" />
                  <span className="min-w-0 flex-1 truncate font-medium">{p.full_name}</span>
                  <Button size="sm" variant="soft" onClick={() => setGrantee(p)}>
                    {t("family.choose")}
                  </Button>
                </li>
              ))}
            </ul>
          )}
          <div className="flex justify-end">
            <Button variant="ghost" size="sm" onClick={onDone}>
              {t("care.cancel")}
            </Button>
          </div>
        </>
      ) : (
        <InlineForm onSubmit={() => save.mutate()} onCancel={onDone} submitLabel={t("family.save")} busy={save.isPending}>
          <div className="flex items-center gap-3">
            <Avatar name={grantee.full_name} size="sm" />
            <p className="font-semibold">{grantee.full_name}</p>
            <button type="button" className="text-sm font-semibold text-brand" onClick={() => setGrantee(null)}>
              {t("family.change")}
            </button>
          </div>
          <fieldset className="space-y-2">
            <legend className="text-sm font-semibold">{t("family.scopesLabel")}</legend>
            {SCOPES.map((s) => (
              <label key={s} className="flex min-h-10 items-start gap-2.5">
                <input
                  type="checkbox"
                  className="mt-1 size-4 accent-[var(--color-brand)]"
                  checked={scopes.includes(s)}
                  onChange={(e) => setScopes((cur) => (e.target.checked ? [...cur, s] : cur.filter((x) => x !== s)))}
                />
                <span>
                  <span className="font-medium">{t(`family.scope.${s}`)}</span>
                  <span className="block text-sm text-muted">{t(`family.scopeHint.${s}`)}</span>
                </span>
              </label>
            ))}
            <p className="text-sm text-muted">{t("family.neverShared")}</p>
          </fieldset>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t("family.methodLabel")} htmlFor="fa-method">
              <Select id="fa-method" value={method} onChange={(e) => setMethod(e.target.value as VerificationMethod)}>
                {METHODS.map((m) => (
                  <option key={m} value={m}>
                    {t(`family.method.${m}`)}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("family.untilLabel")} htmlFor="fa-until" hint={t("family.untilHint")}>
              <Input id="fa-until" type="date" min={todayIso()} value={until} onChange={(e) => setUntil(e.target.value)} />
            </Field>
          </div>
          <label className="flex items-start gap-2.5 rounded-lg border border-line bg-surface p-3">
            <input type="checkbox" className="mt-1 size-4 accent-[var(--color-brand)]" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
            <span className="text-sm">{t("family.consent", { name: subject.full_name, grantee: grantee.full_name })}</span>
          </label>
          {(!consent || scopes.length === 0) && <p className="text-sm text-muted">{t("family.needConsent")}</p>}
        </InlineForm>
      )}
      <ActionError message={errors.message} />
    </div>
  );
}

/** Who the mother has allowed to receive her information (F015, D07 option 3).
 * Families do not sign in: staff use this list before sharing anything. */
export function FamilyAccessPanel({ mother, canManage }: { mother: Person | undefined; canManage: boolean }) {
  const { t } = useTranslation();
  const [adding, setAdding] = useState(false);
  const key = ["caregiver-grants", mother?.id ?? ""];
  const grants = useQuery({ queryKey: key, queryFn: () => caregiverApi.list(mother!.id), enabled: !!mother });
  const active = (grants.data ?? []).filter((g) => g.state === "ACTIVE");
  const past = (grants.data ?? []).filter((g) => g.state !== "ACTIVE");

  return (
    <Card>
      <CardHeader
        icon={HeartHandshake}
        title={t("family.title")}
        description={t("family.description")}
        actions={
          canManage && mother && !adding ? (
            <Button size="sm" onClick={() => setAdding(true)}>
              <UserPlus aria-hidden className="size-4" />
              {t("family.add")}
            </Button>
          ) : undefined
        }
      />
      <div className="space-y-4">
        <Alert kind="info">{t("family.howItWorks")}</Alert>
        {adding && mother && <AddGrant subject={mother} invalidate={[key]} onDone={() => setAdding(false)} />}
        {(!mother || grants.isPending) && <CardSkeleton lines={2} />}
        {grants.isError && <Alert kind="problem">{t("states.errorBody")}</Alert>}
        {grants.data && grants.data.length === 0 && !adding && (
          <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-line-strong px-4 py-8 text-center">
            <span className="inline-flex size-11 items-center justify-center rounded-full bg-brand-tint text-brand">
              <HeartHandshake aria-hidden className="size-5" />
            </span>
            <p className="font-semibold">{t("family.emptyTitle")}</p>
            <p className="max-w-md text-sm text-muted">{t("family.emptyBody")}</p>
          </div>
        )}
        {active.length > 0 && (
          <ul className="space-y-3">
            {active.map((g) => (
              <GrantRow key={g.id} grant={g} canManage={canManage} invalidate={[key]} />
            ))}
          </ul>
        )}
        {past.length > 0 && (
          <details className="group rounded-xl border border-line bg-page/50 p-3">
            <summary className="cursor-pointer text-sm font-semibold text-ink-2">{t("family.history", { count: past.length })}</summary>
            <ul className="mt-3 space-y-3">
              {past.map((g) => (
                <GrantRow key={g.id} grant={g} canManage={false} invalidate={[key]} />
              ))}
            </ul>
          </details>
        )}
      </div>
    </Card>
  );
}
