import { useMutation, useQuery } from "@tanstack/react-query";
import { CalendarDays, MapPin } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { careApi, type Appointment, type AppointmentStatus } from "../../api/client";
import { formatDate, formatDateTime, todayIso } from "../../lib/format";
import { errorStateKind, PageState } from "../PageState";
import { Button } from "../ui/button";
import { Card, Section } from "../ui/card";
import { Field, Input } from "../ui/field";
import { Alert, StatusBadge, type StatusKind } from "../ui/status";
import { ActionError, InlineForm, useActionError } from "./shared";

const STATUS_KIND: Record<AppointmentStatus, StatusKind> = {
  REQUESTED: "pending",
  CONFIRMED: "confirmed",
  ATTENDED: "confirmed",
  MISSED: "attention",
  RESCHEDULED: "neutral",
  CANCELLED: "neutral",
};

type Mode = "none" | "confirm" | "reschedule";

function AppointmentRow({ a, episodeId }: { a: Appointment; episodeId: string }) {
  const { t } = useTranslation();
  const errors = useActionError([["appointments", episodeId], ["episodeTasks", episodeId], ["tasks"]]);
  const [mode, setMode] = useState<Mode>("none");
  const [when, setWhen] = useState("");
  const [place, setPlace] = useState("");
  const [newDate, setNewDate] = useState(todayIso());

  const finish = () => {
    setMode("none");
    errors.clear();
    errors.reload();
  };
  const move = useMutation({
    mutationFn: (body: Parameters<typeof careApi.transitionAppointment>[1]) => careApi.transitionAppointment(a.id, body),
    onSuccess: finish,
    onError: errors.onError,
  });
  const reschedule = useMutation({
    mutationFn: () => careApi.rescheduleAppointment(a.id, a.version, newDate),
    onSuccess: finish,
    onError: errors.onError,
  });
  const busy = move.isPending || reschedule.isPending;
  const to = (target: "ATTENDED" | "MISSED" | "CANCELLED") => move.mutate({ to: target, expected_version: a.version });

  return (
    <li className="space-y-3 rounded-lg border border-line p-3 md:p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-semibold">{a.name ?? t("care.appt.unnamed")}</p>
          <p className="text-sm text-muted">
            {a.confirmed_for
              ? t("care.appt.confirmedFor", { date: formatDateTime(a.confirmed_for) })
              : a.requested_for
                ? t("care.appt.requestedFor", { date: formatDate(a.requested_for) })
                : null}
          </p>
          {a.location_note && (
            <p className="mt-1 inline-flex items-center gap-1 text-sm text-muted">
              <MapPin aria-hidden className="size-4" />
              {a.location_note}
            </p>
          )}
          {a.previous_appointment_id && <p className="text-sm text-muted">{t("care.appt.rescheduledFrom")}</p>}
        </div>
        <StatusBadge kind={STATUS_KIND[a.status]}>{t(`care.appt.status${a.status}`)}</StatusBadge>
      </div>

      <ActionError message={errors.message} />

      {mode === "none" && (
        <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
          {a.status === "REQUESTED" && (
            <>
              <Button onClick={() => setMode("confirm")}>{t("care.appt.confirm")}</Button>
              <Button variant="secondary" disabled={busy} onClick={() => to("CANCELLED")}>
                {t("care.appt.cancelAppt")}
              </Button>
            </>
          )}
          {a.status === "CONFIRMED" && (
            <>
              <Button disabled={busy} onClick={() => to("ATTENDED")}>
                {t("care.appt.attended")}
              </Button>
              <Button variant="secondary" disabled={busy} onClick={() => to("MISSED")}>
                {t("care.appt.missed")}
              </Button>
              <Button variant="secondary" onClick={() => setMode("reschedule")}>
                {t("care.appt.reschedule")}
              </Button>
              <Button variant="ghost" disabled={busy} onClick={() => to("CANCELLED")}>
                {t("care.appt.cancelAppt")}
              </Button>
            </>
          )}
          {a.status === "MISSED" && (
            <Button variant="secondary" onClick={() => setMode("reschedule")}>
              {t("care.appt.reschedule")}
            </Button>
          )}
        </div>
      )}
      {a.status === "CONFIRMED" && mode === "none" && <p className="text-sm text-muted">{t("care.appt.missedNote")}</p>}

      {mode === "confirm" && (
        <InlineForm
          submitLabel={t("care.appt.confirm")}
          busy={busy}
          onCancel={() => setMode("none")}
          onSubmit={() => {
            if (!when) return;
            move.mutate({
              to: "CONFIRMED",
              expected_version: a.version,
              confirmed_for: new Date(when).toISOString(),
              location_note: place.trim() || null,
            });
          }}
        >
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t("care.appt.confirmWhen")} htmlFor={`when_${a.id}`}>
              <Input id={`when_${a.id}`} type="datetime-local" required value={when} onChange={(e) => setWhen(e.target.value)} />
            </Field>
            <Field label={t("care.appt.location")} htmlFor={`place_${a.id}`}>
              <Input id={`place_${a.id}`} maxLength={300} value={place} onChange={(e) => setPlace(e.target.value)} />
            </Field>
          </div>
        </InlineForm>
      )}
      {mode === "reschedule" && (
        <InlineForm submitLabel={t("care.appt.reschedule")} busy={busy} onCancel={() => setMode("none")} onSubmit={() => reschedule.mutate()}>
          <Field label={t("care.appt.newDate")} htmlFor={`newdate_${a.id}`}>
            <Input id={`newdate_${a.id}`} type="date" required value={newDate} onChange={(e) => setNewDate(e.target.value)} className="sm:w-56" />
          </Field>
        </InlineForm>
      )}
    </li>
  );
}

export function AppointmentList({ episodeId }: { episodeId: string }) {
  const { t } = useTranslation();
  const appts = useQuery({ queryKey: ["appointments", episodeId], queryFn: () => careApi.listAppointments(episodeId) });
  return (
    <Card>
      <Section icon={CalendarDays} title={t("care.appt.title")}>
        {appts.isPending && <PageState kind="loading" />}
        {appts.isError && <PageState kind={errorStateKind(appts.error)} />}
        {appts.data?.length === 0 && <Alert kind="info">{t("care.appt.empty")}</Alert>}
        {appts.data && appts.data.length > 0 && (
          <ul className="space-y-3">
            {appts.data.map((a) => (
              <AppointmentRow key={a.id} a={a} episodeId={episodeId} />
            ))}
          </ul>
        )}
      </Section>
    </Card>
  );
}
