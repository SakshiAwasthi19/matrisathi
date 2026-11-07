import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeft, CalendarClock, CheckCircle2, HandHelping, MapPin, PhoneCall, Volume2, XCircle } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router";
import { nextStepApi, type AppointmentFamilyReport, type Barrier } from "../api/client";
import { ActionError, useActionError } from "../components/care/shared";
import { errorStateKind, PageState } from "../components/PageState";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { Field, Select } from "../components/ui/field";
import { Alert } from "../components/ui/status";
import { formatDateTime } from "../lib/format";
import { telHref } from "../lib/urgent";

const BARRIERS: Barrier[] = ["TRAVEL", "COST", "MEDICINE_ACCESS", "CHILDCARE", "WORK", "FAMILY", "OTHER"];

/** One large card: the next confirmed step and three answers (F006).
 * Used by staff together with the mother until patient access exists (D07). */
export function NextStep() {
  const { t } = useTranslation();
  const { episodeId = "" } = useParams();
  const key = ["nextAction", episodeId];
  const errors = useActionError([key, ["episodeTasks", episodeId], ["tasks"], ["appointments", episodeId]]);
  const next = useQuery({ queryKey: key, queryFn: () => nextStepApi.getNextAction(episodeId) });
  const [asking, setAsking] = useState<AppointmentFamilyReport | null>(null);
  const [barrier, setBarrier] = useState<Barrier | "">("");
  const [helpSent, setHelpSent] = useState(false);

  const report = useMutation({
    mutationFn: (answer: AppointmentFamilyReport) =>
      nextStepApi.familyReport(next.data!.appointment_id!, next.data!.version!, answer, barrier || null),
    onSuccess: (_data, answer) => {
      setAsking(null);
      setBarrier("");
      setHelpSent(answer !== "DONE");
      errors.clear();
      errors.reload();
    },
    onError: errors.onError,
  });

  const big = "min-h-16 w-full text-lg md:min-h-14";

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <Button asChild variant="ghost" className="-ml-2">
        <Link to={`/episodes/${episodeId}`}>
          <ArrowLeft aria-hidden className="size-4" />
          {t("episode.title")}
        </Link>
      </Button>
      <h1 className="text-3xl font-semibold">{t("next.title")}</h1>
      <Alert kind="info">{t("next.assistedNote")}</Alert>

      {next.isPending && <PageState kind="loading" />}
      {next.isError && <PageState kind={errorStateKind(next.error)} />}

      {next.data && next.data.state === "NONE" && (
        <Card className="space-y-2 text-center">
          <CalendarClock aria-hidden className="mx-auto size-10 text-muted" />
          <p className="text-2xl font-semibold">{t("next.none")}</p>
          <p className="text-lg text-muted">{t("next.noneBody")}</p>
          {next.data.unconfirmed_requests > 0 && (
            <p className="text-base">{t("next.requestsWaiting", { count: next.data.unconfirmed_requests })}</p>
          )}
        </Card>
      )}

      {next.data && next.data.state === "CONFIRMED" && (
        <Card className="space-y-5">
          <p className="text-2xl font-semibold md:text-3xl">{next.data.name}</p>
          <div className="space-y-3 text-lg">
            <p className="flex items-start gap-3">
              <CalendarClock aria-hidden className="mt-1 size-6 shrink-0 text-brand" />
              <span>
                <span className="block text-sm font-semibold text-muted">{t("next.when")}</span>
                {formatDateTime(next.data.confirmed_for)}
              </span>
            </p>
            <p className="flex items-start gap-3">
              <MapPin aria-hidden className="mt-1 size-6 shrink-0 text-brand" />
              <span>
                <span className="block text-sm font-semibold text-muted">{t("next.where")}</span>
                {next.data.location_note ?? t("next.placeNotSet")}
              </span>
            </p>
          </div>
          {next.data.preparation_text && (
            <div className="space-y-2 rounded-xl bg-brand-soft p-4">
              <p className="text-sm font-semibold text-brand">{t("next.prepare")}</p>
              <p className="text-lg">{next.data.preparation_text}</p>
              {next.data.is_placeholder && <p className="text-sm text-pending">{t("next.placeholder")}</p>}
            </div>
          )}
          {/* Audio slot: approved recordings arrive in Phase 2 (D08). */}
          <div className="flex items-center gap-3 rounded-xl border border-dashed border-line p-3 text-muted">
            <Volume2 aria-hidden className="size-6 shrink-0" />
            <span>{t("next.audioNotYet")}</span>
          </div>

          {next.data.family_report && next.data.family_reported_at && (
            <p className="text-base text-muted">
              {t("next.reported", { answer: t(`next.answer${next.data.family_report}`), date: formatDateTime(next.data.family_reported_at) })}
            </p>
          )}
          {helpSent && <Alert kind="info">{t("next.helpCreated")}</Alert>}
          <ActionError message={errors.message} />

          {asking === null ? (
            <div className="grid gap-3 sm:grid-cols-3">
              <Button className={big} disabled={report.isPending} onClick={() => report.mutate("DONE")}>
                <CheckCircle2 aria-hidden className="size-6" />
                {t("next.done")}
              </Button>
              <Button variant="secondary" className={big} onClick={() => setAsking("COULD_NOT_GO")}>
                <XCircle aria-hidden className="size-6" />
                {t("next.couldNotGo")}
              </Button>
              <Button variant="secondary" className={big} onClick={() => setAsking("NEED_HELP")}>
                <HandHelping aria-hidden className="size-6" />
                {t("next.needHelp")}
              </Button>
            </div>
          ) : (
            <div className="space-y-3 rounded-xl border border-line p-4">
              <Field label={t("next.barrierQuestion")} htmlFor="next_barrier">
                <Select id="next_barrier" value={barrier} onChange={(e) => setBarrier(e.target.value as Barrier | "")}>
                  <option value="">{t("care.task.noBarrier")}</option>
                  {BARRIERS.map((b) => (
                    <option key={b} value={b}>
                      {t(`care.task.barrier${b}`)}
                    </option>
                  ))}
                </Select>
              </Field>
              <div className="grid gap-3 sm:grid-cols-2">
                <Button className={big} disabled={report.isPending} onClick={() => report.mutate(asking)}>
                  {t("next.send")}
                </Button>
                <Button variant="secondary" className={big} onClick={() => setAsking(null)}>
                  {t("care.cancel")}
                </Button>
              </div>
            </div>
          )}
        </Card>
      )}

      {next.data && next.data.help_contacts.length > 0 && (
        <Card className="space-y-3">
          <p className="text-lg font-semibold">{t("next.callForHelp")}</p>
          {next.data.help_contacts.map((c) => (
            <a key={c.id} href={telHref(c.phone)} className="flex min-h-14 items-center gap-3 rounded-lg border border-line px-4 text-lg font-semibold text-brand">
              <PhoneCall aria-hidden className="size-5" />
              {c.name}: {c.phone}
            </a>
          ))}
        </Card>
      )}
    </div>
  );
}
