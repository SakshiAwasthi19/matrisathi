import { useMutation, useQuery } from "@tanstack/react-query";
import { CalendarHeart, ChevronDown } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { careApi, type Dating, type DatingEvidence, type DatingInput, type DatingPrecision } from "../../api/client";
import { formatDate, formatDateTime } from "../../lib/format";
import { errorStateKind, PageState } from "../PageState";
import { Button } from "../ui/button";
import { Card, Section } from "../ui/card";
import { Field, Input, Select } from "../ui/field";
import { Alert, StatusBadge } from "../ui/status";
import { ActionError, InlineForm, useActionError } from "./shared";

const PRECISIONS: DatingPrecision[] = ["EXACT", "APPROXIMATE"];
const EVIDENCE: DatingEvidence[] = ["SELF_REPORTED", "CARD_OR_DOCUMENT", "SCAN_REPORT", "CLINICIAN_ASSESSMENT"];

function DatingForm({
  submitLabel,
  note,
  busy,
  onSubmit,
  onCancel,
}: {
  submitLabel: string;
  note?: string;
  busy: boolean;
  onSubmit: (input: DatingInput) => void;
  onCancel: () => void;
}) {
  const { t } = useTranslation();
  const [lmp, setLmp] = useState("");
  const [edd, setEdd] = useState("");
  const [precision, setPrecision] = useState<DatingPrecision>("EXACT");
  const [evidence, setEvidence] = useState<DatingEvidence>("SELF_REPORTED");
  const [error, setError] = useState<string | null>(null);
  return (
    <InlineForm
      submitLabel={submitLabel}
      busy={busy}
      onCancel={onCancel}
      onSubmit={() => {
        if (!lmp && !edd) {
          setError(t("care.dating.needOneDate"));
          return;
        }
        setError(null);
        onSubmit({ lmp_date: lmp || null, edd: edd || null, precision, evidence });
      }}
    >
      {note && <Alert kind="info">{note}</Alert>}
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t("care.dating.lmp")} htmlFor="dating_lmp">
          <Input id="dating_lmp" type="date" value={lmp} onChange={(e) => setLmp(e.target.value)} />
        </Field>
        <Field label={t("care.dating.edd")} htmlFor="dating_edd">
          <Input id="dating_edd" type="date" value={edd} onChange={(e) => setEdd(e.target.value)} />
        </Field>
        <Field label={t("care.dating.precision")} htmlFor="dating_precision">
          <Select id="dating_precision" value={precision} onChange={(e) => setPrecision(e.target.value as DatingPrecision)}>
            {PRECISIONS.map((p) => (
              <option key={p} value={p}>
                {t(`care.dating.precision${p}`)}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t("care.dating.evidence")} htmlFor="dating_evidence">
          <Select id="dating_evidence" value={evidence} onChange={(e) => setEvidence(e.target.value as DatingEvidence)}>
            {EVIDENCE.map((v) => (
              <option key={v} value={v}>
                {t(`care.dating.evidence${v}`)}
              </option>
            ))}
          </Select>
        </Field>
      </div>
      {error && <Alert kind="problem">{error}</Alert>}
    </InlineForm>
  );
}

function DatingFacts({ d }: { d: Dating }) {
  const { t } = useTranslation();
  return (
    <dl className="grid gap-x-6 gap-y-2 text-base sm:grid-cols-2">
      <div>
        <dt className="text-sm font-semibold text-muted">{t("care.dating.lmp")}</dt>
        <dd>{d.lmp_date ? formatDate(d.lmp_date) : <StatusBadge kind="not-recorded">{t("status.notRecorded")}</StatusBadge>}</dd>
      </div>
      <div>
        <dt className="text-sm font-semibold text-muted">{t("care.dating.edd")}</dt>
        <dd>{d.edd ? formatDate(d.edd) : <StatusBadge kind="not-recorded">{t("status.notRecorded")}</StatusBadge>}</dd>
      </div>
      <div>
        <dt className="text-sm font-semibold text-muted">{t("care.dating.precision")}</dt>
        <dd>{t(`care.dating.precision${d.precision}`)}</dd>
      </div>
      <div>
        <dt className="text-sm font-semibold text-muted">{t("care.dating.evidence")}</dt>
        <dd>{t(`care.dating.evidence${d.evidence}`)}</dd>
      </div>
    </dl>
  );
}

export function DatingCard({ episodeId, isClinician }: { episodeId: string; isClinician: boolean }) {
  const { t } = useTranslation();
  const key = ["dating", episodeId];
  const errors = useActionError([key, ["episode", episodeId], ["appointments", episodeId], ["episodeTasks", episodeId], ["tasks"]]);
  const [mode, setMode] = useState<"none" | "record" | "correct">("none");
  const [showHistory, setShowHistory] = useState(false);
  const dating = useQuery({ queryKey: key, queryFn: () => careApi.getDating(episodeId) });

  const done = () => {
    setMode("none");
    errors.clear();
    errors.reload();
  };
  const record = useMutation({ mutationFn: (input: DatingInput) => careApi.recordDating(episodeId, input), onSuccess: done, onError: errors.onError });
  const confirm = useMutation({
    mutationFn: (d: Dating) => careApi.confirmDating(episodeId, d.id, d.version),
    onSuccess: done,
    onError: errors.onError,
  });
  const correct = useMutation({
    mutationFn: (input: DatingInput) => careApi.correctDating(episodeId, input, dating.data?.current?.version ?? 0),
    onSuccess: done,
    onError: errors.onError,
  });

  const current = dating.data?.current ?? null;
  const confirmed = current?.state === "CONFIRMED";

  return (
    <Card>
      <Section icon={CalendarHeart} title={t("care.dating.title")}>
        {dating.isPending && <PageState kind="loading" />}
        {dating.isError && <PageState kind={errorStateKind(dating.error)} />}
        {dating.data && (
          <div className="space-y-4">
            {current === null ? (
              <div className="space-y-2">
                <StatusBadge kind="unknown">{t("care.dating.unknown")}</StatusBadge>
                <p className="text-base text-muted">{t("care.dating.unknownBody")}</p>
              </div>
            ) : (
              <div className="space-y-3">
                {confirmed ? (
                  <StatusBadge kind="confirmed">{t("care.dating.confirmedBy", { name: current.confirmed_by_name ?? "" })}</StatusBadge>
                ) : (
                  <StatusBadge kind="pending">{t("care.dating.provisional")}</StatusBadge>
                )}
                <DatingFacts d={current} />
                <p className="text-sm text-muted">
                  {t("care.dating.recordedBy", { name: current.recorded_by_name ?? "", date: formatDateTime(current.created_at) })}
                </p>
              </div>
            )}

            <ActionError message={errors.message} />

            {mode === "none" && (
              <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
                {!confirmed && (
                  <Button variant="secondary" onClick={() => setMode("record")}>
                    {t("care.dating.record")}
                  </Button>
                )}
                {isClinician && current && !confirmed && (
                  <Button onClick={() => confirm.mutate(current)} disabled={confirm.isPending}>
                    {t("care.dating.confirm")}
                  </Button>
                )}
                {isClinician && (
                  <Button variant="secondary" onClick={() => setMode("correct")}>
                    {t("care.dating.correct")}
                  </Button>
                )}
              </div>
            )}
            {confirmed && !isClinician && <p className="text-sm text-muted">{t("care.dating.lockedForNonClinician")}</p>}

            {mode === "record" && (
              <DatingForm submitLabel={t("care.save")} busy={record.isPending} onSubmit={(i) => record.mutate(i)} onCancel={() => setMode("none")} />
            )}
            {mode === "correct" && (
              <DatingForm
                submitLabel={t("care.dating.correct")}
                note={t("care.dating.correctNote")}
                busy={correct.isPending}
                onSubmit={(i) => correct.mutate(i)}
                onCancel={() => setMode("none")}
              />
            )}

            {dating.data.history.length > 1 && (
              <div>
                <button
                  type="button"
                  onClick={() => setShowHistory((v) => !v)}
                  className="inline-flex min-h-12 items-center gap-1 font-semibold text-brand md:min-h-10"
                  aria-expanded={showHistory}
                >
                  <ChevronDown aria-hidden className={showHistory ? "size-4 rotate-180" : "size-4"} />
                  {t("care.dating.history", { count: dating.data.history.length })}
                </button>
                {showHistory && (
                  <ul className="mt-2 space-y-3">
                    {dating.data.history.map((h) => (
                      <li key={h.id} className="rounded-lg border border-line p-3">
                        <div className="mb-2 flex flex-wrap gap-2">
                          {h.state === "CONFIRMED" ? (
                            <StatusBadge kind="confirmed">{t("care.dating.confirmedBy", { name: h.confirmed_by_name ?? "" })}</StatusBadge>
                          ) : (
                            <StatusBadge kind="pending">{t("care.dating.provisional")}</StatusBadge>
                          )}
                          {h.superseded_at && <StatusBadge kind="neutral">{t("care.dating.superseded")}</StatusBadge>}
                        </div>
                        <DatingFacts d={h} />
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        )}
      </Section>
    </Card>
  );
}
