import { useMutation, useQuery } from "@tanstack/react-query";
import { NotebookText } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  recordsApi,
  type CorrectionReason,
  type Observation,
  type ObservationInput,
  type ObservationSource,
} from "../../api/client";
import { formatDate, formatDateTime, todayIso } from "../../lib/format";
import { ActionError, InlineForm, useActionError } from "../care/shared";
import { errorStateKind, PageState } from "../PageState";
import { Button } from "../ui/button";
import { Card, Section } from "../ui/card";
import { Field, Input, Select } from "../ui/field";
import { Alert, StatusBadge } from "../ui/status";

const SOURCES: ObservationSource[] = ["MEASURED_HERE", "OUTSIDE_RECORD", "REPORTED_BY_FAMILY"];
const REASONS: CorrectionReason[] = ["TYPING_ERROR", "WRONG_PERSON", "WRONG_DATE", "WRONG_UNIT", "OTHER"];

function ObservationForm({
  initial,
  isClinician,
  withReason,
  busy,
  onSubmit,
  onCancel,
}: {
  initial?: Observation;
  isClinician: boolean;
  withReason: boolean;
  busy: boolean;
  onSubmit: (input: ObservationInput, reason: CorrectionReason) => void;
  onCancel: () => void;
}) {
  const { t } = useTranslation();
  const prefix = initial ? `obs_${initial.id}` : "obs_new";
  const [kind, setKind] = useState<ObservationInput["kind"]>(initial?.kind ?? "MEASUREMENT");
  const [name, setName] = useState(initial?.name ?? "");
  const [value, setValue] = useState(initial?.value_text ?? "");
  const [unit, setUnit] = useState(initial?.unit ?? "");
  const [date, setDate] = useState(initial?.observed_on ?? "");
  const [source, setSource] = useState<ObservationSource>(initial?.source ?? "MEASURED_HERE");
  const [reason, setReason] = useState<CorrectionReason>("TYPING_ERROR");
  return (
    <InlineForm
      submitLabel={t("care.save")}
      busy={busy}
      onCancel={onCancel}
      onSubmit={() =>
        onSubmit({ kind, name: name.trim(), value_text: value.trim(), unit: unit.trim() || null, observed_on: date || null, source }, reason)
      }
    >
      <div className="grid gap-3 sm:grid-cols-2">
        {isClinician && (
          <Field label={t("records.obs.kind")} htmlFor={`${prefix}_kind`}>
            <Select id={`${prefix}_kind`} value={kind} onChange={(e) => setKind(e.target.value as ObservationInput["kind"])}>
              <option value="MEASUREMENT">{t("records.obs.kindMEASUREMENT")}</option>
              <option value="CLINICIAN_FINDING">{t("records.obs.kindCLINICIAN_FINDING")}</option>
            </Select>
          </Field>
        )}
        <Field label={t("records.obs.name")} htmlFor={`${prefix}_name`}>
          <Input id={`${prefix}_name`} required maxLength={100} value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field label={t("records.obs.value")} htmlFor={`${prefix}_value`}>
          <Input id={`${prefix}_value`} required maxLength={500} value={value} onChange={(e) => setValue(e.target.value)} />
        </Field>
        <Field label={t("records.obs.unit")} htmlFor={`${prefix}_unit`}>
          <Input id={`${prefix}_unit`} maxLength={30} value={unit} onChange={(e) => setUnit(e.target.value)} />
        </Field>
        <Field label={t("records.obs.observedOn")} htmlFor={`${prefix}_date`}>
          <Input id={`${prefix}_date`} type="date" max={todayIso()} value={date} onChange={(e) => setDate(e.target.value)} />
        </Field>
        <Field label={t("records.obs.source")} htmlFor={`${prefix}_source`}>
          <Select id={`${prefix}_source`} value={source} onChange={(e) => setSource(e.target.value as ObservationSource)}>
            {SOURCES.map((s) => (
              <option key={s} value={s}>
                {t(`records.obs.source${s}`)}
              </option>
            ))}
          </Select>
        </Field>
        {withReason && (
          <Field label={t("records.obs.reason")} htmlFor={`${prefix}_reason`}>
            <Select id={`${prefix}_reason`} value={reason} onChange={(e) => setReason(e.target.value as CorrectionReason)}>
              {REASONS.map((r) => (
                <option key={r} value={r}>
                  {t(`records.obs.reason${r}`)}
                </option>
              ))}
            </Select>
          </Field>
        )}
      </div>
    </InlineForm>
  );
}

function ObservationRow({ o, episodeId, isClinician }: { o: Observation; episodeId: string; isClinician: boolean }) {
  const { t } = useTranslation();
  const errors = useActionError([["observations", episodeId]]);
  const [correcting, setCorrecting] = useState(false);
  const correct = useMutation({
    mutationFn: ({ input, reason }: { input: ObservationInput; reason: CorrectionReason }) =>
      recordsApi.correctObservation(o.id, { ...input, expected_version: o.version, correction_reason: reason }),
    onSuccess: () => {
      setCorrecting(false);
      errors.clear();
      errors.reload();
    },
    onError: errors.onError,
  });
  const canCorrect = !o.superseded_at && (o.kind === "MEASUREMENT" || isClinician);
  return (
    <li className={o.superseded_at ? "space-y-2 rounded-lg border border-dashed border-line p-3 opacity-75" : "space-y-2 rounded-lg border border-line p-3"}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-muted">
            {o.name}
            {o.kind === "CLINICIAN_FINDING" && ` · ${t("records.obs.kindCLINICIAN_FINDING")}`}
          </p>
          {/* Exactly as entered: no colour, flag or "normal" label, ever. */}
          <p className="text-lg font-semibold break-words">
            {o.value_text}
            {o.unit && <span className="ml-1 text-base font-normal text-muted">{o.unit}</span>}
          </p>
          <p className="text-sm text-muted">
            {o.observed_on ? formatDate(o.observed_on) : t("records.reports.dateUnknown")} · {t(`records.obs.source${o.source}`)}
          </p>
          <p className="text-sm text-muted">{t("records.obs.recordedBy", { name: o.recorded_by_name ?? "", date: formatDateTime(o.created_at) })}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {o.superseded_at && <StatusBadge kind="neutral">{t("records.obs.corrected")}</StatusBadge>}
          {o.correction_reason && (
            <StatusBadge kind="neutral">{t("records.obs.correctionOf", { reason: t(`records.obs.reason${o.correction_reason}`) })}</StatusBadge>
          )}
        </div>
      </div>
      <ActionError message={errors.message} />
      {canCorrect && !correcting && (
        <Button variant="ghost" className="-ml-2" onClick={() => setCorrecting(true)}>
          {t("records.obs.correct")}
        </Button>
      )}
      {correcting && (
        <ObservationForm
          initial={o}
          isClinician={isClinician}
          withReason
          busy={correct.isPending}
          onCancel={() => setCorrecting(false)}
          onSubmit={(input, reason) => correct.mutate({ input, reason })}
        />
      )}
    </li>
  );
}

export function ObservationsPanel({ episodeId, isClinician }: { episodeId: string; isClinician: boolean }) {
  const { t } = useTranslation();
  const [showCorrected, setShowCorrected] = useState(false);
  const key = ["observations", episodeId];
  const errors = useActionError([key]);
  const list = useQuery({ queryKey: [...key, showCorrected], queryFn: () => recordsApi.listObservations(episodeId, showCorrected) });
  const [adding, setAdding] = useState(false);
  const add = useMutation({
    mutationFn: (input: ObservationInput) => recordsApi.recordObservation(episodeId, input),
    onSuccess: () => {
      setAdding(false);
      errors.clear();
      errors.reload();
    },
    onError: errors.onError,
  });
  return (
    <Card>
      <Section icon={NotebookText} title={t("records.obs.title")}>
        <Alert kind="info">{t("records.obs.unapprovedList")}</Alert>
        <label className="flex min-h-12 items-center gap-3 md:min-h-10">
          <input type="checkbox" className="size-5 accent-brand" checked={showCorrected} onChange={(e) => setShowCorrected(e.target.checked)} />
          {t("records.obs.showCorrected")}
        </label>
        {list.isPending && <PageState kind="loading" />}
        {list.isError && <PageState kind={errorStateKind(list.error)} />}
        {list.data?.length === 0 && <p className="text-base text-muted">{t("records.obs.empty")}</p>}
        {list.data && list.data.length > 0 && (
          <ul className="space-y-3">
            {list.data.map((o) => (
              <ObservationRow key={o.id} o={o} episodeId={episodeId} isClinician={isClinician} />
            ))}
          </ul>
        )}
        <ActionError message={errors.message} />
        {!adding ? (
          <Button variant="secondary" onClick={() => setAdding(true)}>
            {t("records.obs.add")}
          </Button>
        ) : (
          <ObservationForm isClinician={isClinician} withReason={false} busy={add.isPending} onCancel={() => setAdding(false)} onSubmit={(input) => add.mutate(input)} />
        )}
      </Section>
    </Card>
  );
}
