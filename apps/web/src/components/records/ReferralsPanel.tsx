import { useMutation, useQuery } from "@tanstack/react-query";
import { CheckCircle2, Circle, FileText, Send } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  fileUrl,
  recordsApi,
  type Referral,
  type ReferralClosureReason,
  type ReferralStatus,
  type ReferralUrgency,
} from "../../api/client";
import { formatDate, formatDateTime, todayIso } from "../../lib/format";
import { REFERRAL_NEXT, REFERRAL_TIMELINE, referralCanClose } from "../../lib/records";
import { ActionError, InlineForm, useActionError } from "../care/shared";
import { errorStateKind, PageState } from "../PageState";
import { Button } from "../ui/button";
import { Card, Section } from "../ui/card";
import { Field, Input, Select, Textarea } from "../ui/field";
import { Alert, StatusBadge } from "../ui/status";
import { FilePicker } from "./FilePicker";

const URGENCIES: ReferralUrgency[] = ["ROUTINE", "SOON", "URGENT"];
const CLOSURE: ReferralClosureReason[] = [
  "FAMILY_DECLINED",
  "NOT_ATTENDED_AFTER_FOLLOW_UP",
  "CARE_TRANSFERRED_ELSEWHERE",
  "NO_LONGER_NEEDED_PER_CLINICIAN",
  "RECORDED_IN_ERROR",
];

function stepTime(r: Referral, s: ReferralStatus): string | null {
  switch (s) {
    case "SENT":
      return formatDateTime(r.created_at);
    case "CONTACTED":
      return r.contacted_at ? formatDateTime(r.contacted_at) : null;
    case "ATTENDED":
      return r.attended_on ? formatDate(r.attended_on) : null;
    case "ADVICE_RECEIVED":
      return r.advice_received_at ? formatDateTime(r.advice_received_at) : null;
    case "FOLLOW_UP_COMPLETED":
      return r.follow_up_completed_at ? formatDateTime(r.follow_up_completed_at) : null;
    default:
      return null;
  }
}

function ReferralRow({ r, episodeId, personId, destinationLabel }: { r: Referral; episodeId: string; personId: string; destinationLabel: string }) {
  const { t } = useTranslation();
  const errors = useActionError([["referrals", episodeId], ["episodeTasks", episodeId], ["tasks"]]);
  const [mode, setMode] = useState<"none" | Exclude<ReferralStatus, "SENT">>("none");
  const [attendedOn, setAttendedOn] = useState("");
  const [adviceFile, setAdviceFile] = useState<File | null>(null);
  const [reason, setReason] = useState<ReferralClosureReason>("FAMILY_DECLINED");
  const step = useMutation({
    mutationFn: async (to: Exclude<ReferralStatus, "SENT">) => {
      const file = to === "ADVICE_RECEIVED" && adviceFile ? await recordsApi.uploadFile(personId, adviceFile) : null;
      return recordsApi.referralStep(r.id, {
        expected_version: r.version,
        to,
        attended_on: to === "ATTENDED" ? attendedOn || null : null,
        advice_file_id: file?.id ?? null,
        closure_reason: to === "CLOSED" ? reason : null,
      });
    },
    onSuccess: () => {
      setMode("none");
      errors.clear();
      errors.reload();
    },
    onError: errors.onError,
  });
  const reached = (s: ReferralStatus) => REFERRAL_TIMELINE.indexOf(s) <= REFERRAL_TIMELINE.indexOf(r.status === "CLOSED" ? "SENT" : r.status) || stepTime(r, s) !== null;

  return (
    <li className="space-y-3 rounded-lg border border-line p-3 md:p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-semibold">{destinationLabel}</p>
          <p className="text-sm text-muted">{t("records.ref.referredBy", { name: r.referred_by_name ?? "", owner: r.owner_name ?? "" })}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <StatusBadge kind="neutral">{t(`records.ref.urgency${r.urgency}`)}</StatusBadge>
          {r.status === "CLOSED" ? (
            <StatusBadge kind="neutral">{t("records.ref.closedBecause", { reason: t(`records.ref.reason${r.closure_reason}`) })}</StatusBadge>
          ) : r.status === "FOLLOW_UP_COMPLETED" ? (
            <StatusBadge kind="confirmed">{t("records.ref.statusFOLLOW_UP_COMPLETED")}</StatusBadge>
          ) : (
            <StatusBadge kind="pending">{t(`records.ref.status${r.status}`)}</StatusBadge>
          )}
        </div>
      </div>
      {r.clinician_instruction && <p className="rounded-md bg-subtle px-3 py-2 text-base whitespace-pre-wrap">{r.clinician_instruction}</p>}

      <ol className="space-y-1" aria-label={t("records.ref.title")}>
        {REFERRAL_TIMELINE.map((s) => {
          const done = reached(s);
          const Icon = done ? CheckCircle2 : Circle;
          return (
            <li key={s} className={done ? "flex items-center gap-2 text-base" : "flex items-center gap-2 text-base text-muted"}>
              <Icon aria-hidden className={done ? "size-4 text-ok" : "size-4"} />
              <span>{t(`records.ref.status${s}`)}</span>
              {stepTime(r, s) && <span className="text-sm text-muted">· {stepTime(r, s)}</span>}
            </li>
          );
        })}
      </ol>
      {r.advice_file_id && (
        <a href={fileUrl(r.advice_file_id)} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-10 items-center gap-1 font-semibold text-brand">
          <FileText aria-hidden className="size-4" />
          {t("records.file.open")}
        </a>
      )}

      <ActionError message={errors.message} />
      {mode === "none" && (
        <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
          {REFERRAL_NEXT[r.status].map((next) => (
            <Button
              key={next}
              variant="secondary"
              disabled={step.isPending}
              onClick={() => (next === "CONTACTED" || next === "FOLLOW_UP_COMPLETED" ? step.mutate(next) : setMode(next))}
            >
              {t(`records.ref.step${next}`)}
            </Button>
          ))}
          {referralCanClose(r.status) && (
            <Button variant="ghost" onClick={() => setMode("CLOSED")}>
              {t("records.ref.close")}
            </Button>
          )}
        </div>
      )}
      {mode === "ATTENDED" && (
        <InlineForm submitLabel={t("records.ref.stepATTENDED")} busy={step.isPending} onCancel={() => setMode("none")} onSubmit={() => step.mutate("ATTENDED")}>
          <Field label={t("records.ref.attendedOn")} htmlFor={`att_${r.id}`}>
            <Input id={`att_${r.id}`} type="date" max={todayIso()} value={attendedOn} onChange={(e) => setAttendedOn(e.target.value)} className="sm:w-56" />
          </Field>
        </InlineForm>
      )}
      {mode === "ADVICE_RECEIVED" && (
        <InlineForm submitLabel={t("records.ref.stepADVICE_RECEIVED")} busy={step.isPending} onCancel={() => setMode("none")} onSubmit={() => step.mutate("ADVICE_RECEIVED")}>
          <FilePicker id={`advice_${r.id}`} onChange={setAdviceFile} />
          <p className="text-sm text-muted">{t("records.ref.adviceNote")}</p>
        </InlineForm>
      )}
      {mode === "CLOSED" && (
        <InlineForm submitLabel={t("records.ref.close")} busy={step.isPending} onCancel={() => setMode("none")} onSubmit={() => step.mutate("CLOSED")}>
          <Field label={t("records.ref.closureReason")} htmlFor={`close_${r.id}`}>
            <Select id={`close_${r.id}`} value={reason} onChange={(e) => setReason(e.target.value as ReferralClosureReason)}>
              {CLOSURE.map((c) => (
                <option key={c} value={c}>
                  {t(`records.ref.reason${c}`)}
                </option>
              ))}
            </Select>
          </Field>
        </InlineForm>
      )}
    </li>
  );
}

export function ReferralsPanel({
  episodeId,
  personId,
  facilityId,
  isClinician,
}: {
  episodeId: string;
  personId: string;
  facilityId: string;
  isClinician: boolean;
}) {
  const { t } = useTranslation();
  const key = ["referrals", episodeId];
  const errors = useActionError([key]);
  const list = useQuery({ queryKey: key, queryFn: () => recordsApi.listReferrals(episodeId) });
  const contacts = useQuery({ queryKey: ["contacts", facilityId], queryFn: () => recordsApi.listContacts(facilityId) });
  const [creating, setCreating] = useState(false);
  const [contactId, setContactId] = useState("");
  const [name, setName] = useState("");
  const [urgency, setUrgency] = useState<ReferralUrgency>("ROUTINE");
  const [instruction, setInstruction] = useState("");
  const create = useMutation({
    mutationFn: () =>
      recordsApi.createReferral(episodeId, {
        destination_contact_id: contactId || null,
        destination_name: contactId ? null : name.trim() || null,
        urgency,
        clinician_instruction: instruction.trim() || null,
      }),
    onSuccess: () => {
      setCreating(false);
      setContactId("");
      setName("");
      setInstruction("");
      errors.clear();
      errors.reload();
    },
    onError: errors.onError,
  });
  const label = (r: Referral) =>
    r.destination_name ?? contacts.data?.find((c) => c.id === r.destination_contact_id)?.name ?? t("records.ref.destination");

  return (
    <Card>
      <Section icon={Send} title={t("records.ref.title")}>
        <p className="text-sm text-muted">{t("records.ref.messageNote")}</p>
        {list.isPending && <PageState kind="loading" />}
        {list.isError && <PageState kind={errorStateKind(list.error)} />}
        {list.data?.length === 0 && <Alert kind="info">{t("records.ref.empty")}</Alert>}
        {list.data && list.data.length > 0 && (
          <ul className="space-y-3">
            {list.data.map((r) => (
              <ReferralRow key={r.id} r={r} episodeId={episodeId} personId={personId} destinationLabel={label(r)} />
            ))}
          </ul>
        )}
        <ActionError message={errors.message} />
        {isClinician && !creating && <Button onClick={() => setCreating(true)}>{t("records.ref.create")}</Button>}
        {isClinician && creating && (
          <InlineForm
            submitLabel={t("records.ref.create")}
            busy={create.isPending}
            onCancel={() => setCreating(false)}
            onSubmit={() => {
              if (contactId || name.trim()) create.mutate();
            }}
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label={t("records.ref.chooseContact")} htmlFor="ref_contact">
                <Select id="ref_contact" value={contactId} onChange={(e) => setContactId(e.target.value)}>
                  <option value="">—</option>
                  {(contacts.data ?? []).map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} ({c.phone})
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label={t("records.ref.orName")} htmlFor="ref_name">
                <Input id="ref_name" maxLength={200} disabled={!!contactId} value={name} onChange={(e) => setName(e.target.value)} />
              </Field>
              <Field label={t("records.ref.urgency")} htmlFor="ref_urgency">
                <Select id="ref_urgency" value={urgency} onChange={(e) => setUrgency(e.target.value as ReferralUrgency)}>
                  {URGENCIES.map((u) => (
                    <option key={u} value={u}>
                      {t(`records.ref.urgency${u}`)}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>
            <Field label={t("records.ref.instruction")} htmlFor="ref_instruction">
              <Textarea id="ref_instruction" maxLength={2000} value={instruction} onChange={(e) => setInstruction(e.target.value)} />
            </Field>
          </InlineForm>
        )}
      </Section>
    </Card>
  );
}
