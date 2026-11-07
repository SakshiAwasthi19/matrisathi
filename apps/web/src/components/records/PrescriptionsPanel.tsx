import { useMutation, useQuery } from "@tanstack/react-query";
import { FileText, Pill } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { fileUrl, recordsApi, type Prescription, type PrescriptionSource } from "../../api/client";
import { formatDate, todayIso } from "../../lib/format";
import { ActionError, InlineForm, useActionError } from "../care/shared";
import { errorStateKind, PageState } from "../PageState";
import { Button } from "../ui/button";
import { Card, Section } from "../ui/card";
import { Field, Hint, Input, Select, Textarea } from "../ui/field";
import { Alert, StatusBadge } from "../ui/status";
import { FilePicker } from "./FilePicker";

const SOURCES: PrescriptionSource[] = ["PAPER_PRESCRIPTION", "MCP_CARD", "DISCHARGE_SUMMARY", "OTHER_DOCUMENT"];

function ReviewForm({ rx, onDone, onCancel, onError }: { rx: Prescription; onDone: () => void; onCancel: () => void; onError: (e: unknown) => void }) {
  const { t } = useTranslation();
  const [decision, setDecision] = useState<"CONFIRMED" | "UNCLEAR">("CONFIRMED");
  const [text, setText] = useState("");
  const [reminder, setReminder] = useState(false);
  const [start, setStart] = useState(todayIso());
  const [end, setEnd] = useState("");
  const review = useMutation({
    mutationFn: () =>
      recordsApi.reviewPrescription(rx.id, {
        expected_version: rx.version,
        decision,
        confirmed_instruction: decision === "CONFIRMED" ? text.trim() : null,
        reminder_enabled: decision === "CONFIRMED" && reminder,
        reminder_start: decision === "CONFIRMED" && reminder ? start : null,
        reminder_end: decision === "CONFIRMED" && reminder && end ? end : null,
      }),
    onSuccess: onDone,
    onError,
  });
  return (
    <InlineForm submitLabel={t("care.save")} busy={review.isPending} onCancel={onCancel} onSubmit={() => review.mutate()}>
      <fieldset className="space-y-1">
        <legend className="text-sm font-semibold">{t("records.rx.decision")}</legend>
        {(["CONFIRMED", "UNCLEAR"] as const).map((d) => (
          <label key={d} className="flex min-h-12 items-center gap-3 md:min-h-10">
            <input type="radio" name={`decision_${rx.id}`} className="size-5 accent-brand" checked={decision === d} onChange={() => setDecision(d)} />
            {d === "CONFIRMED" ? t("records.rx.confirm") : t("records.rx.unclear")}
          </label>
        ))}
      </fieldset>
      {decision === "CONFIRMED" ? (
        <>
          <Field label={t("records.rx.transcription")} htmlFor={`rx_text_${rx.id}`}>
            <Textarea id={`rx_text_${rx.id}`} required maxLength={2000} value={text} onChange={(e) => setText(e.target.value)} />
            <Hint>{t("records.rx.transcriptionNote")}</Hint>
          </Field>
          <label className="flex min-h-12 items-center gap-3 md:min-h-10">
            <input type="checkbox" className="size-5 accent-brand" checked={reminder} onChange={(e) => setReminder(e.target.checked)} />
            {t("records.rx.reminder")}
          </label>
          {reminder && (
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label={t("records.rx.reminderStart")} htmlFor={`rx_start_${rx.id}`}>
                <Input id={`rx_start_${rx.id}`} type="date" required value={start} onChange={(e) => setStart(e.target.value)} />
              </Field>
              <Field label={t("records.rx.reminderEnd")} htmlFor={`rx_end_${rx.id}`}>
                <Input id={`rx_end_${rx.id}`} type="date" min={start} value={end} onChange={(e) => setEnd(e.target.value)} />
              </Field>
            </div>
          )}
        </>
      ) : (
        <Alert kind="info">{t("records.rx.unclearNote")}</Alert>
      )}
    </InlineForm>
  );
}

function PrescriptionRow({ rx, episodeId, isClinician }: { rx: Prescription; episodeId: string; isClinician: boolean }) {
  const { t } = useTranslation();
  const errors = useActionError([["prescriptions", episodeId], ["episodeTasks", episodeId], ["tasks"]]);
  const [reviewing, setReviewing] = useState(false);
  return (
    <li className="space-y-3 rounded-lg border border-line p-3 md:p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-semibold">{t(`records.rx.source${rx.source}`)}</p>
          {rx.issued_on && <p className="text-sm text-muted">{t("records.rx.issued", { date: formatDate(rx.issued_on) })}</p>}
          {rx.source_file_id && (
            <a href={fileUrl(rx.source_file_id)} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-10 items-center gap-1 font-semibold text-brand">
              <FileText aria-hidden className="size-4" />
              {t("records.file.open")}
            </a>
          )}
        </div>
        {rx.instruction_status === "UNREVIEWED" && <StatusBadge kind="pending">{t("records.rx.statusUNREVIEWED")}</StatusBadge>}
        {rx.instruction_status === "UNCLEAR" && <StatusBadge kind="attention">{t("records.rx.statusUNCLEAR")}</StatusBadge>}
        {rx.instruction_status === "CONFIRMED" && (
          <StatusBadge kind="confirmed">{t("records.rx.statusCONFIRMED", { name: rx.reviewed_by_name ?? "" })}</StatusBadge>
        )}
      </div>
      {rx.confirmed_instruction && (
        <blockquote className="rounded-md border-l-4 border-brand bg-brand-soft px-3 py-2 text-base whitespace-pre-wrap">{rx.confirmed_instruction}</blockquote>
      )}
      <p className="text-sm text-muted">
        {rx.instruction_status !== "CONFIRMED"
          ? t("records.rx.noReminder")
          : rx.reminder_enabled
            ? t("records.rx.reminderOn", { start: formatDate(rx.reminder_start) })
            : t("records.rx.reminderOff")}
      </p>
      <ActionError message={errors.message} />
      {isClinician && rx.instruction_status !== "CONFIRMED" && !reviewing && (
        <Button onClick={() => setReviewing(true)}>{t("records.rx.review")}</Button>
      )}
      {reviewing && (
        <ReviewForm
          rx={rx}
          onCancel={() => setReviewing(false)}
          onError={errors.onError}
          onDone={() => {
            setReviewing(false);
            errors.clear();
            errors.reload();
          }}
        />
      )}
    </li>
  );
}

export function PrescriptionsPanel({ episodeId, personId, isClinician }: { episodeId: string; personId: string; isClinician: boolean }) {
  const { t } = useTranslation();
  const key = ["prescriptions", episodeId];
  const errors = useActionError([key, ["episodeTasks", episodeId], ["tasks"]]);
  const list = useQuery({ queryKey: key, queryFn: () => recordsApi.listPrescriptions(episodeId) });
  const [adding, setAdding] = useState(false);
  const [source, setSource] = useState<PrescriptionSource>("PAPER_PRESCRIPTION");
  const [issued, setIssued] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const record = useMutation({
    mutationFn: async () => {
      const stored = file ? await recordsApi.uploadFile(personId, file) : null;
      return recordsApi.recordPrescription(episodeId, { source, source_file_id: stored?.id ?? null, issued_on: issued || null });
    },
    onSuccess: () => {
      setAdding(false);
      setIssued("");
      setFile(null);
      errors.clear();
      errors.reload();
    },
    onError: errors.onError,
  });

  return (
    <Card>
      <Section icon={Pill} title={t("records.rx.title")}>
        {list.isPending && <PageState kind="loading" />}
        {list.isError && <PageState kind={errorStateKind(list.error)} />}
        {list.data?.length === 0 && <Alert kind="info">{t("records.rx.empty")}</Alert>}
        {list.data && list.data.length > 0 && (
          <ul className="space-y-3">
            {list.data.map((rx) => (
              <PrescriptionRow key={rx.id} rx={rx} episodeId={episodeId} isClinician={isClinician} />
            ))}
          </ul>
        )}
        <ActionError message={errors.message} />
        {!adding ? (
          <Button variant="secondary" onClick={() => setAdding(true)}>
            {t("records.rx.record")}
          </Button>
        ) : (
          <InlineForm
            submitLabel={record.isPending ? t("records.file.uploading") : t("care.save")}
            busy={record.isPending}
            onCancel={() => setAdding(false)}
            onSubmit={() => record.mutate()}
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label={t("records.rx.source")} htmlFor="rx_source">
                <Select id="rx_source" value={source} onChange={(e) => setSource(e.target.value as PrescriptionSource)}>
                  {SOURCES.map((s) => (
                    <option key={s} value={s}>
                      {t(`records.rx.source${s}`)}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label={t("records.rx.issuedOn")} htmlFor="rx_issued">
                <Input id="rx_issued" type="date" max={todayIso()} value={issued} onChange={(e) => setIssued(e.target.value)} />
              </Field>
            </div>
            <FilePicker id="rx_file" onChange={setFile} />
            <Alert kind="info">{t("records.rx.noReminder")}</Alert>
          </InlineForm>
        )}
      </Section>
    </Card>
  );
}
