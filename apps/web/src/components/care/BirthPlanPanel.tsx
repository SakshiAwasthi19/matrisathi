import { useMutation, useQuery } from "@tanstack/react-query";
import { Baby, Printer } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import {
  nextStepApi,
  recordsApi,
  type Barrier,
  type BirthPlan,
  type BirthPlanInput,
  type FamilyReport,
  type HelpContact,
} from "../../api/client";
import { formatDate, formatDateTime } from "../../lib/format";
import { errorStateKind, PageState } from "../PageState";
import { Button } from "../ui/button";
import { Card, Section } from "../ui/card";
import { Field, Input, Select } from "../ui/field";
import { Alert, StatusBadge } from "../ui/status";
import { ActionError, InlineForm, useActionError } from "./shared";

const BARRIERS: Barrier[] = ["TRAVEL", "COST", "MEDICINE_ACCESS", "CHILDCARE", "WORK", "FAMILY", "OTHER"];

function ContactLine({ c }: { c: HelpContact | null }) {
  const { t } = useTranslation();
  if (!c) return <StatusBadge kind="not-recorded">{t("birth.notRecorded")}</StatusBadge>;
  return (
    <span>
      {c.name} · {c.phone}{" "}
      <span className="text-sm text-muted">
        ({c.stale ? t("birth.staleContact") : t("birth.verifiedOn", { date: formatDate(c.verified_on) })})
      </span>
    </span>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1 border-b border-line/70 py-2 last:border-b-0 sm:grid-cols-[13rem_1fr] sm:gap-4">
      <dt className="text-sm font-semibold text-muted">{label}</dt>
      <dd className="text-base">{children}</dd>
    </div>
  );
}

function PlanForm({
  plan,
  facilityId,
  isClinician,
  busy,
  onSubmit,
  onCancel,
}: {
  plan: BirthPlan | null;
  facilityId: string;
  isClinician: boolean;
  busy: boolean;
  onSubmit: (body: BirthPlanInput) => void;
  onCancel: () => void;
}) {
  const { t } = useTranslation();
  const contacts = useQuery({ queryKey: ["contacts", facilityId], queryFn: () => recordsApi.listContacts(facilityId) });
  const [f, setF] = useState({
    chosen: plan?.chosen_birth_place?.id ?? "",
    chosenNote: plan?.chosen_birth_place_note ?? "",
    referral: plan?.referral_site?.id ?? "",
    companion: plan?.companion_name ?? "",
    transport: plan?.transport_arrangement ?? "",
    landmarks: plan?.landmarks ?? "",
    primary: plan?.primary_contact?.id ?? "",
    alternate: plan?.alternate_contact?.id ?? "",
  });
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF((x) => ({ ...x, [k]: e.target.value }));
  const options = (contacts.data ?? []).map((c) => (
    <option key={c.id} value={c.id}>
      {c.name} ({c.phone})
    </option>
  ));
  const picker = (id: string, label: string, k: keyof typeof f, disabled = false) => (
    <Field label={label} htmlFor={id}>
      <Select id={id} value={f[k]} onChange={set(k)} disabled={disabled}>
        <option value="">{t("birth.none_option")}</option>
        {options}
      </Select>
    </Field>
  );
  return (
    <InlineForm
      submitLabel={t("care.save")}
      busy={busy}
      onCancel={onCancel}
      onSubmit={() =>
        onSubmit({
          expected_version: plan?.version ?? 0,
          chosen_birth_place_contact_id: f.chosen || null,
          chosen_birth_place_note: f.chosenNote.trim() || null,
          referral_site_contact_id: f.referral || null,
          companion_name: f.companion.trim() || null,
          transport_arrangement: f.transport.trim() || null,
          landmarks: f.landmarks.trim() || null,
          primary_contact_id: f.primary || null,
          alternate_contact_id: f.alternate || null,
        })
      }
    >
      {contacts.data?.length === 0 && <Alert kind="pending">{t("birth.noContacts")}</Alert>}
      <div className="grid gap-3 sm:grid-cols-2">
        {picker("bp_chosen", t("birth.birthPlace"), "chosen")}
        <Field label={t("birth.birthPlaceNote")} htmlFor="bp_chosen_note">
          <Input id="bp_chosen_note" maxLength={200} value={f.chosenNote} onChange={set("chosenNote")} />
        </Field>
        {picker("bp_referral", t("birth.referralSite"), "referral", !isClinician)}
        <Field label={t("birth.companion")} htmlFor="bp_companion">
          <Input id="bp_companion" maxLength={200} value={f.companion} onChange={set("companion")} />
        </Field>
        <Field label={t("birth.transport")} htmlFor="bp_transport">
          <Input id="bp_transport" maxLength={300} value={f.transport} onChange={set("transport")} />
        </Field>
        <Field label={t("birth.landmarks")} htmlFor="bp_landmarks">
          <Input id="bp_landmarks" maxLength={300} value={f.landmarks} onChange={set("landmarks")} />
        </Field>
        {picker("bp_primary", t("birth.primary"), "primary")}
        {picker("bp_alternate", t("birth.alternate"), "alternate")}
      </div>
      {!isClinician && <p className="text-sm text-muted">{t("birth.referralClinicianOnly")}</p>}
      <p className="text-sm text-muted">{t("birth.changeClearsVerification")}</p>
    </InlineForm>
  );
}

export function BirthPlanPanel({ episodeId, facilityId, isClinician }: { episodeId: string; facilityId: string; isClinician: boolean }) {
  const { t } = useTranslation();
  const key = ["birthPlan", episodeId];
  const errors = useActionError([key, ["episodeTasks", episodeId], ["tasks"]]);
  const plan = useQuery({ queryKey: key, queryFn: () => nextStepApi.getBirthPlan(episodeId) });
  const [editing, setEditing] = useState(false);
  const [family, setFamily] = useState<FamilyReport | null>(null);
  const [barrier, setBarrier] = useState<Barrier | "">("");
  const finish = () => {
    setEditing(false);
    setFamily(null);
    setBarrier("");
    errors.clear();
    errors.reload();
  };
  const save = useMutation({ mutationFn: (body: BirthPlanInput) => nextStepApi.saveBirthPlan(episodeId, body), onSuccess: finish, onError: errors.onError });
  const verify = useMutation({ mutationFn: (v: number) => nextStepApi.verifyBirthPlan(episodeId, v), onSuccess: finish, onError: errors.onError });
  const report = useMutation({
    mutationFn: ({ v, r }: { v: number; r: FamilyReport }) => nextStepApi.birthPlanFamilyReport(episodeId, v, r, barrier || null),
    onSuccess: finish,
    onError: errors.onError,
  });
  const p = plan.data ?? null;

  return (
    <Card>
      <Section icon={Baby} title={t("birth.title")}>
        <p className="text-sm text-muted">{t("birth.noDispatch")}</p>
        {plan.isPending && <PageState kind="loading" />}
        {plan.isError && <PageState kind={errorStateKind(plan.error)} />}
        {plan.isSuccess && !p && !editing && <p className="text-base text-muted">{t("birth.none")}</p>}
        {p && !editing && (
          <>
            <dl>
              <Row label={t("birth.birthPlace")}>
                <ContactLine c={p.chosen_birth_place} />
                {p.chosen_birth_place_note && <span className="block text-sm text-muted">{p.chosen_birth_place_note}</span>}
              </Row>
              <Row label={t("birth.referralSite")}>
                <ContactLine c={p.referral_site} />
                {p.referral_site_set_by_name && <span className="block text-sm text-muted">{t("birth.referralSiteBy", { name: p.referral_site_set_by_name })}</span>}
              </Row>
              <Row label={t("birth.companion")}>{p.companion_name ?? <StatusBadge kind="not-recorded">{t("birth.notRecorded")}</StatusBadge>}</Row>
              <Row label={t("birth.transport")}>{p.transport_arrangement ?? <StatusBadge kind="not-recorded">{t("birth.notRecorded")}</StatusBadge>}</Row>
              <Row label={t("birth.landmarks")}>{p.landmarks ?? <StatusBadge kind="not-recorded">{t("birth.notRecorded")}</StatusBadge>}</Row>
              <Row label={t("birth.primary")}>
                <ContactLine c={p.primary_contact} />
              </Row>
              <Row label={t("birth.alternate")}>
                <ContactLine c={p.alternate_contact} />
              </Row>
            </dl>
            <div className="flex flex-wrap gap-2">
              {p.staff_verified_at ? (
                <StatusBadge kind="confirmed">{t("birth.verified", { name: p.staff_verified_by_name ?? "", date: formatDateTime(p.staff_verified_at) })}</StatusBadge>
              ) : (
                <StatusBadge kind="pending">{t("birth.notVerified")}</StatusBadge>
              )}
              {p.family_report && p.family_reported_at && (
                <StatusBadge kind="neutral">
                  {t("birth.familyReported", { answer: t(`birth.family${p.family_report}`), date: formatDateTime(p.family_reported_at) })}
                </StatusBadge>
              )}
            </div>
          </>
        )}
        <ActionError message={errors.message} />
        {editing ? (
          <PlanForm plan={p} facilityId={facilityId} isClinician={isClinician} busy={save.isPending} onSubmit={(b) => save.mutate(b)} onCancel={() => setEditing(false)} />
        ) : (
          <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
            <Button variant="secondary" onClick={() => setEditing(true)}>
              {p ? t("birth.edit") : t("birth.create")}
            </Button>
            {p && !p.staff_verified_at && (
              <Button disabled={verify.isPending} onClick={() => verify.mutate(p.version)}>
                {t("birth.verify")}
              </Button>
            )}
            {p && (
              <Button asChild variant="ghost">
                <Link to={`/episodes/${episodeId}/birth-plan/print`}>
                  <Printer aria-hidden className="size-4" />
                  {t("birth.print")}
                </Link>
              </Button>
            )}
          </div>
        )}
        {p && !editing && (
          <div className="space-y-2">
            <p className="text-sm font-semibold text-muted">{t("birth.familySays")}</p>
            {family === null ? (
              <div className="flex flex-col gap-2 sm:flex-row">
                {(["DONE", "NOT_DONE", "NEED_HELP"] as const).map((r) => (
                  <Button
                    key={r}
                    variant="secondary"
                    disabled={report.isPending}
                    onClick={() => (r === "NEED_HELP" ? setFamily(r) : report.mutate({ v: p.version, r }))}
                  >
                    {t(`birth.family${r}`)}
                  </Button>
                ))}
              </div>
            ) : (
              <InlineForm submitLabel={t("next.send")} busy={report.isPending} onCancel={() => setFamily(null)} onSubmit={() => report.mutate({ v: p.version, r: family })}>
                <Field label={t("next.barrierQuestion")} htmlFor="bp_barrier">
                  <Select id="bp_barrier" value={barrier} onChange={(e) => setBarrier(e.target.value as Barrier | "")}>
                    <option value="">{t("care.task.noBarrier")}</option>
                    {BARRIERS.map((b) => (
                      <option key={b} value={b}>
                        {t(`care.task.barrier${b}`)}
                      </option>
                    ))}
                  </Select>
                </Field>
              </InlineForm>
            )}
          </div>
        )}
      </Section>
    </Card>
  );
}
