import { useQuery } from "@tanstack/react-query";
import { BadgeCheck, Clock, Info, MapPin, MessageSquareOff, MoonStar, Navigation, Phone, PhoneCall, TriangleAlert } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router";
import { nextStepApi } from "../api/client";
import { formatDate } from "../lib/format";
import { telHref } from "../lib/urgent";

/** Public, signed-out page (F014). The only screen that uses red.
 * No location request, no login, no instructions until the doctor
 * approves the wording (D05): verified phone numbers only. Approved
 * wording is shown exactly as the server returns it, never rewritten. */
export function UrgentHelp() {
  const { t } = useTranslation();
  const { facilityId } = useParams();
  const help = useQuery({
    queryKey: ["urgentHelp", facilityId],
    queryFn: () => nextStepApi.urgentHelp(facilityId as string),
    enabled: !!facilityId,
    retry: 2,
  });
  const wording = help.data?.wording_approved ? (help.data.wording ?? null) : null;

  return (
    <main className="mx-auto max-w-xl px-4 py-6">
      <div className="rounded-2xl bg-urgent px-5 py-6 text-urgent-ink shadow-raised">
        <h1 className="flex items-center gap-3 text-3xl font-semibold">
          <PhoneCall aria-hidden className="size-8 shrink-0" />
          {wording ? wording.heading : t("urgent.callNow")}
        </h1>
        {help.data && <p className="mt-2 text-lg">{help.data.facility_name}</p>}
      </div>

      {wording && (
        <section className="mt-5 space-y-3 rounded-xl border border-line bg-surface p-4 text-lg shadow-card">
          <p className="whitespace-pre-line">{wording.instruction_text}</p>
          <p className="flex items-start gap-2 whitespace-pre-line">
            <Info aria-hidden className="mt-1 size-5 shrink-0" />
            <span>{wording.when_to_call_text}</span>
          </p>
        </section>
      )}

      <div className="mt-5 space-y-4">
        {!facilityId && <p className="rounded-xl border border-line bg-surface p-4 text-lg">{t("urgent.noFacility")}</p>}
        {help.isPending && facilityId && <p className="text-lg text-muted">…</p>}
        {help.isError && <p className="rounded-xl border border-line bg-surface p-4 text-lg">{t("urgent.loadFailed")}</p>}

        {help.data && help.data.contacts.length === 0 && (
          <p className="rounded-xl border border-line bg-surface p-4 text-lg">{t("urgent.noContacts")}</p>
        )}
        {help.data?.contacts.map((c) => (
          <section key={c.id} className="space-y-2 rounded-xl border border-line bg-surface p-4 shadow-card">
            <a
              href={telHref(c.phone)}
              className="flex min-h-16 items-center justify-center gap-3 rounded-xl bg-urgent px-4 text-xl font-semibold text-urgent-ink"
            >
              <Phone aria-hidden className="size-6" />
              {t("urgent.callFacility", { name: c.name })}
            </a>
            <p className="text-center text-2xl font-semibold tracking-wide">{c.phone}</p>
            {c.alternate_phone && (
              <a href={telHref(c.alternate_phone)} className="flex min-h-12 items-center justify-center gap-2 rounded-lg border-2 border-urgent font-semibold text-urgent">
                <Phone aria-hidden className="size-5" />
                {t("urgent.alternate")}: {c.alternate_phone}
              </a>
            )}
            {c.landmarks && (
              <p className="flex items-start gap-2 text-base text-muted">
                <MapPin aria-hidden className="mt-0.5 size-5 shrink-0" />
                {t("urgent.landmarks", { text: c.landmarks })}
              </p>
            )}
            <p className="text-sm text-muted">{t("urgent.verifiedOn", { date: formatDate(c.verified_on) })}</p>
          </section>
        ))}

        <div className="space-y-3 rounded-xl border border-line bg-surface p-4 text-base">
          <p className="flex items-start gap-2">
            <MessageSquareOff aria-hidden className="mt-0.5 size-5 shrink-0" />
            <strong>{wording ? wording.not_monitored_text : t("urgent.noMonitoring")}</strong>
          </p>
          <p className="flex items-start gap-2">
            <Clock aria-hidden className="mt-0.5 size-5 shrink-0" />
            <span>
              {t("urgent.hours")}: {help.data?.support_hours ?? t("urgent.hoursNotSet")}
            </span>
          </p>
          {wording?.outside_hours_text && (
            <p className="flex items-start gap-2">
              <MoonStar aria-hidden className="mt-0.5 size-5 shrink-0" />
              <span className="whitespace-pre-line">{wording.outside_hours_text}</span>
            </p>
          )}
          <p className="flex items-start gap-2 text-muted">
            <Navigation aria-hidden className="mt-0.5 size-5 shrink-0" />
            {t("urgent.noLocation")}
          </p>
        </div>

        {wording && (
          <p className="flex items-start gap-2 text-sm text-muted">
            <BadgeCheck aria-hidden className="mt-0.5 size-4 shrink-0" />
            {wording.approved_by_role
              ? t("urgent.approvedBy", { name: wording.approved_by_name, role: wording.approved_by_role, date: formatDate(wording.approved_on), version: wording.version_label })
              : t("urgent.approvedByNoRole", { name: wording.approved_by_name, date: formatDate(wording.approved_on), version: wording.version_label })}
          </p>
        )}

        {help.data && !wording && (
          <p className="flex items-start gap-2 rounded-xl border border-pending-line bg-pending-bg p-4 text-base text-pending">
            <TriangleAlert aria-hidden className="mt-0.5 size-5 shrink-0" />
            {t("urgent.wordingPending")}
          </p>
        )}
      </div>
    </main>
  );
}
