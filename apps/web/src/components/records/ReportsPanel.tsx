import { useMutation, useQuery } from "@tanstack/react-query";
import { FileText, FlaskConical } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { fileUrl, recordsApi, type Investigation } from "../../api/client";
import { formatDate, formatDateTime } from "../../lib/format";
import { ActionError, InlineForm, useActionError } from "../care/shared";
import { errorStateKind, PageState } from "../PageState";
import { Button } from "../ui/button";
import { Card, Section } from "../ui/card";
import { Field, Input } from "../ui/field";
import { Alert, StatusBadge } from "../ui/status";
import { FilePicker } from "./FilePicker";

function ReportRow({ inv, episodeId, isClinician }: { inv: Investigation; episodeId: string; isClinician: boolean }) {
  const { t } = useTranslation();
  const errors = useActionError([["investigations", episodeId]]);
  const step = useMutation({
    mutationFn: (s: "performed" | "received" | "reviewed") => recordsApi.investigationStep(inv.id, s, inv.version),
    onSuccess: () => {
      errors.clear();
      errors.reload();
    },
    onError: errors.onError,
  });
  const unknown = t("records.reports.dateUnknown");

  return (
    <li className="space-y-3 rounded-lg border border-line p-3 md:p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-semibold">{inv.name}</p>
          <div className="mt-1 flex flex-col text-sm text-muted">
            {inv.status !== "RECEIVED" && inv.status !== "REVIEWED" && inv.requested_on && (
              <span>{t("records.reports.requestedOn", { date: formatDate(inv.requested_on) })}</span>
            )}
            {inv.status === "PERFORMED" && (
              <span>{t("records.reports.performedOn", { date: inv.performed_on ? formatDate(inv.performed_on) : unknown })}</span>
            )}
            {inv.received_at && <span>{t("records.reports.receivedAt", { date: formatDateTime(inv.received_at) })}</span>}
            {inv.reviewed_at && (
              <span>{t("records.reports.reviewedBy", { name: inv.reviewed_by_name ?? "", date: formatDateTime(inv.reviewed_at) })}</span>
            )}
          </div>
          {inv.file_id && (
            <a href={fileUrl(inv.file_id)} className="mt-1 inline-flex min-h-10 items-center gap-1 font-semibold text-brand" target="_blank" rel="noopener noreferrer">
              <FileText aria-hidden className="size-4" />
              {t("records.file.open")}
            </a>
          )}
        </div>
        {inv.status === "RECEIVED" && <StatusBadge kind="pending">{t("records.reports.pendingReview")}</StatusBadge>}
        {inv.status === "REVIEWED" && <StatusBadge kind="confirmed">{t("records.reports.reviewed")}</StatusBadge>}
        {inv.status === "REQUESTED" && <StatusBadge kind="neutral">{t("records.reports.requested")}</StatusBadge>}
        {inv.status === "PERFORMED" && <StatusBadge kind="neutral">{t("records.reports.performed")}</StatusBadge>}
      </div>
      <ActionError message={errors.message} />
      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
        {inv.status === "REQUESTED" && (
          <Button variant="secondary" disabled={step.isPending} onClick={() => step.mutate("performed")}>
            {t("records.reports.markPerformed")}
          </Button>
        )}
        {(inv.status === "REQUESTED" || inv.status === "PERFORMED") && (
          <Button variant="secondary" disabled={step.isPending} onClick={() => step.mutate("received")}>
            {t("records.reports.markReceived")}
          </Button>
        )}
        {inv.status === "RECEIVED" && isClinician && (
          <Button disabled={step.isPending} onClick={() => step.mutate("reviewed")}>
            {t("records.reports.markReviewed")}
          </Button>
        )}
      </div>
      {inv.status === "RECEIVED" && isClinician && <p className="text-sm text-muted">{t("records.reports.reviewNote")}</p>}
    </li>
  );
}

export function ReportsPanel({ episodeId, personId, isClinician }: { episodeId: string; personId: string; isClinician: boolean }) {
  const { t } = useTranslation();
  const key = ["investigations", episodeId];
  const errors = useActionError([key]);
  const list = useQuery({ queryKey: key, queryFn: () => recordsApi.listInvestigations(episodeId) });
  const [mode, setMode] = useState<"none" | "outside" | "request">("none");
  const [name, setName] = useState("");
  const [file, setFile] = useState<File | null>(null);

  const done = () => {
    setMode("none");
    setName("");
    setFile(null);
    errors.clear();
    errors.reload();
  };
  const addOutside = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error(t("records.file.wrongType"));
      const stored = await recordsApi.uploadFile(personId, file);
      return recordsApi.createInvestigation(episodeId, { name: name.trim(), received_file_id: stored.id, source: "OUTSIDE_REPORT" });
    },
    onSuccess: done,
    onError: errors.onError,
  });
  const request = useMutation({
    mutationFn: () => recordsApi.createInvestigation(episodeId, { name: name.trim(), source: "ORDERED_HERE" }),
    onSuccess: done,
    onError: errors.onError,
  });

  return (
    <Card>
      <Section icon={FlaskConical} title={t("records.reports.title")}>
        {list.isPending && <PageState kind="loading" />}
        {list.isError && <PageState kind={errorStateKind(list.error)} />}
        {list.data?.length === 0 && <Alert kind="info">{t("records.reports.empty")}</Alert>}
        {list.data && list.data.length > 0 && (
          <ul className="space-y-3">
            {list.data.map((inv) => (
              <ReportRow key={inv.id} inv={inv} episodeId={episodeId} isClinician={isClinician} />
            ))}
          </ul>
        )}
        <ActionError message={errors.message} />
        {mode === "none" && (
          <div className="flex flex-col gap-2 sm:flex-row">
            <Button variant="secondary" onClick={() => setMode("outside")}>
              {t("records.reports.uploadOutside")}
            </Button>
            <Button variant="secondary" onClick={() => setMode("request")}>
              {t("records.reports.request")}
            </Button>
          </div>
        )}
        {mode !== "none" && (
          <InlineForm
            submitLabel={addOutside.isPending ? t("records.file.uploading") : t("care.save")}
            busy={addOutside.isPending || request.isPending}
            onCancel={() => setMode("none")}
            onSubmit={() => (mode === "outside" ? addOutside.mutate() : request.mutate())}
          >
            <Field label={t("records.reports.name")} htmlFor="report_name">
              <Input id="report_name" required maxLength={200} value={name} onChange={(e) => setName(e.target.value)} />
            </Field>
            {mode === "outside" && <FilePicker id="report_file" onChange={setFile} />}
          </InlineForm>
        )}
      </Section>
    </Card>
  );
}
