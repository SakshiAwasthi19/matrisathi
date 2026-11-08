import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { History, Lock, MessageSquareOff, Settings2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { messagingApi, type ContactPreference, type DetailLevel } from "../../api/client";
import { formatDateTime } from "../../lib/format";
import { ActionError } from "../care/shared";
import { errorStateKind, PageState } from "../PageState";
import { Button } from "../ui/button";
import { Card, CardHeader } from "../ui/card";
import { Field, Select } from "../ui/field";
import { CardSkeleton } from "../ui/kit";
import { Alert, StatusBadge } from "../ui/status";
import { MessageRow, useMessagingError } from "./shared";

const LANGUAGES = ["en", "hi"];
const DETAIL_LEVELS: DetailLevel[] = ["MINIMAL", "STANDARD"];
const FROM_HOURS = Array.from({ length: 24 }, (_, h) => h);
const TO_HOURS = Array.from({ length: 24 }, (_, h) => h + 1);

function hourLabel(h: number): string {
  return `${String(h).padStart(2, "0")}:00`;
}

type Errors = ReturnType<typeof useMessagingError>;

function PreferencesForm({ pref, canManage, errors }: { pref: ContactPreference; canManage: boolean; errors: Errors }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const key = ["contactPrefs", pref.person_id];
  const [consent, setConsent] = useState(pref.messaging_consent);
  const [optedOut, setOptedOut] = useState(pref.opted_out);
  const [language, setLanguage] = useState(pref.language ?? "");
  const [from, setFrom] = useState(pref.safe_from_hour === null ? "" : String(pref.safe_from_hour));
  const [to, setTo] = useState(pref.safe_to_hour === null ? "" : String(pref.safe_to_hour));
  const [detail, setDetail] = useState<DetailLevel>(pref.detail_level);
  const [prefersCall, setPrefersCall] = useState(pref.prefers_call);
  const [localError, setLocalError] = useState<string | null>(null);
  const languages = pref.language && !LANGUAGES.includes(pref.language) ? [...LANGUAGES, pref.language] : LANGUAGES;
  const disabled = !canManage;

  const save = useMutation({
    mutationFn: () =>
      messagingApi.savePreferences(pref.person_id, {
        expected_version: pref.exists ? pref.version : 0,
        language: language || null,
        safe_from_hour: from === "" ? null : Number(from),
        safe_to_hour: to === "" ? null : Number(to),
        detail_level: detail,
        messaging_consent: consent,
        opted_out: optedOut,
        prefers_call: prefersCall,
      }),
    meta: { toast: t("prefs.saved") },
    onSuccess: (updated) => {
      errors.clear();
      queryClient.setQueryData(key, updated);
    },
    onError: errors.onError,
  });

  const submit = () => {
    setLocalError(null);
    errors.clear();
    if ((from === "") !== (to === "") || (from !== "" && Number(from) >= Number(to))) {
      setLocalError(t("prefs.hoursInvalid"));
      return;
    }
    save.mutate();
  };

  const checkbox = "mt-1 size-5 shrink-0 accent-[var(--color-brand)]";
  return (
    <form
      className="space-y-5"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <fieldset disabled={disabled} className="space-y-5">
        <div className="space-y-2 rounded-lg border border-line p-3">
          <label className="flex min-h-12 items-start gap-3">
            <input type="checkbox" className={checkbox} checked={consent} onChange={(e) => setConsent(e.target.checked)} />
            <span>
              <span className="font-semibold">{t("prefs.consentLabel")}</span>
              <span className="block text-sm text-muted">{t("prefs.consentHint")}</span>
            </span>
          </label>
          {pref.consent_recorded_at ? (
            <p className="text-sm text-muted">
              {t("prefs.consentRecorded", { name: pref.consent_recorded_by_name ?? t("find.aStaffMember"), time: formatDateTime(pref.consent_recorded_at) })}
            </p>
          ) : (
            <StatusBadge kind="not-recorded">{t("prefs.consentNotRecorded")}</StatusBadge>
          )}
        </div>

        <div className="space-y-2 rounded-lg border border-line p-3">
          <label className="flex min-h-12 items-start gap-3">
            <input type="checkbox" className={checkbox} checked={optedOut} onChange={(e) => setOptedOut(e.target.checked)} />
            <span>
              <span className="font-semibold">{t("prefs.optOutLabel")}</span>
              <span className="block text-sm text-muted">{t("prefs.optOutHint")}</span>
            </span>
          </label>
          {pref.opted_out && pref.opted_out_at && (
            <StatusBadge kind="neutral">
              {t(pref.opt_out_source === "INBOUND_KEYWORD" ? "prefs.optOutByStop" : "prefs.optOutByStaff", { time: formatDateTime(pref.opted_out_at) })}
            </StatusBadge>
          )}
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <Field label={t("prefs.languageLabel")} htmlFor={`lang-${pref.person_id}`}>
            <Select id={`lang-${pref.person_id}`} value={language} onChange={(e) => setLanguage(e.target.value)}>
              <option value="">{t("prefs.languageNotSet")}</option>
              {languages.map((l) => (
                <option key={l} value={l}>
                  {t(`prefs.language.${l}`, { defaultValue: l })}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("prefs.fromLabel")} htmlFor={`from-${pref.person_id}`}>
            <Select id={`from-${pref.person_id}`} value={from} onChange={(e) => setFrom(e.target.value)}>
              <option value="">{t("prefs.defaultHour", { time: hourLabel(pref.default_safe_from_hour) })}</option>
              {FROM_HOURS.map((h) => (
                <option key={h} value={h}>
                  {hourLabel(h)}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("prefs.toLabel")} htmlFor={`to-${pref.person_id}`}>
            <Select id={`to-${pref.person_id}`} value={to} onChange={(e) => setTo(e.target.value)}>
              <option value="">{t("prefs.defaultHour", { time: hourLabel(pref.default_safe_to_hour) })}</option>
              {TO_HOURS.map((h) => (
                <option key={h} value={h}>
                  {hourLabel(h)}
                </option>
              ))}
            </Select>
          </Field>
        </div>
        <p className="-mt-3 text-sm text-muted">{t("prefs.hoursHint")}</p>

        <fieldset className="space-y-2">
          <legend className="mb-1 text-sm font-semibold">{t("prefs.detailLabel")}</legend>
          {DETAIL_LEVELS.map((d) => (
            <label key={d} className="flex min-h-12 items-start gap-3 rounded-lg border border-line p-3">
              <input type="radio" name={`detail-${pref.person_id}`} className={checkbox} checked={detail === d} onChange={() => setDetail(d)} />
              <span>
                <span className="font-semibold">{t(`prefs.detail.${d}`)}</span>
                <span className="block text-sm text-muted">{t(`prefs.detailHint.${d}`)}</span>
              </span>
            </label>
          ))}
        </fieldset>

        <label className="flex min-h-12 items-start gap-3">
          <input type="checkbox" className={checkbox} checked={prefersCall} onChange={(e) => setPrefersCall(e.target.checked)} />
          <span>
            <span className="font-semibold">{t("prefs.prefersCallLabel")}</span>
            <span className="block text-sm text-muted">{t("prefs.prefersCallHint")}</span>
          </span>
        </label>
      </fieldset>

      <ActionError message={localError} />
      {canManage && (
        <Button type="submit" disabled={save.isPending}>
          {save.isPending ? t("prefs.saving") : t("prefs.save")}
        </Button>
      )}
    </form>
  );
}

/** Her messaging choices (F016, F020). Staff record consent only after asking her. */
export function ContactPreferencesPanel({ personId, canManage }: { personId: string; canManage: boolean }) {
  const { t } = useTranslation();
  const prefs = useQuery({ queryKey: ["contactPrefs", personId], queryFn: () => messagingApi.getPreferences(personId) });
  const p = prefs.data;
  // Kept outside the form: a conflict reloads her preferences and remounts the form.
  const errors = useMessagingError([["contactPrefs", personId]]);
  return (
    <Card>
      <CardHeader icon={Settings2} title={t("prefs.title")} description={t("prefs.description")} />
      <div className="space-y-4">
        {prefs.isPending && <CardSkeleton lines={4} />}
        {prefs.isError && <PageState kind={errorStateKind(prefs.error)} />}
        {p && (
          <>
            {!p.messaging_available && (
              <Alert kind="pending" title={t("prefs.notSetUpTitle")}>
                {t("prefs.notSetUpBody")}
              </Alert>
            )}
            {!canManage && (
              <Alert kind="info" title={t("prefs.readOnlyTitle")}>
                <span className="inline-flex items-center gap-1.5">
                  <Lock aria-hidden className="size-4" />
                  {t("prefs.readOnlyBody")}
                </span>
              </Alert>
            )}
            <p className="text-sm text-muted">
              {p.phone_numbers.length > 0 ? t("prefs.numbers", { numbers: p.phone_numbers.join(", ") }) : t("prefs.noNumbers")}
            </p>
            <PreferencesForm key={`${p.exists}-${p.version}`} pref={p} canManage={canManage} errors={errors} />
            <ActionError message={errors.message} />
          </>
        )}
      </div>
    </Card>
  );
}

/** Every message queued for her, newest first, with an honest status. */
export function MessageHistory({ personId }: { personId: string }) {
  const { t } = useTranslation();
  const messages = useQuery({ queryKey: ["personMessages", personId], queryFn: () => messagingApi.personMessages(personId) });
  return (
    <Card>
      <CardHeader icon={History} title={t("msg.historyTitle")} description={t("msg.historyDescription")} />
      {messages.isPending && <CardSkeleton lines={3} />}
      {messages.isError && <PageState kind={errorStateKind(messages.error)} />}
      {messages.data && messages.data.length === 0 && (
        <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-line-strong px-4 py-8 text-center">
          <MessageSquareOff aria-hidden className="size-6 text-muted" />
          <p className="font-semibold">{t("msg.historyEmpty")}</p>
        </div>
      )}
      {messages.data && messages.data.length > 0 && (
        <ul className="space-y-3">
          {messages.data.map((m) => (
            <li key={m.id} className="rounded-lg border border-line p-3 md:p-4">
              <MessageRow message={m} />
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
