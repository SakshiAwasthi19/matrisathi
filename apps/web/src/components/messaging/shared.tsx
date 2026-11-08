import type { QueryKey } from "@tanstack/react-query";
import { FlaskConical, VolumeX } from "lucide-react";
import { useTranslation } from "react-i18next";
import { ApiError, type OutboxMessage } from "../../api/client";
import { formatDateTime } from "../../lib/format";
import { outboxLabel } from "../../lib/outbox";
import { useActionError } from "../care/shared";
import { Badge } from "../ui/kit";
import { StatusBadge } from "../ui/status";

/** Like useActionError, but any 409 (stale version or a refusal such as
 * "no consent") also reloads, so the screen shows what is true now. */
export function useMessagingError(keys: QueryKey[]) {
  const errors = useActionError(keys);
  return {
    ...errors,
    onError: (err: unknown) => {
      errors.onError(err);
      if (err instanceof ApiError && err.status === 409) errors.reload();
    },
  };
}

/** Status word with an icon, plus the plain reason when it was not sent. */
export function MessageStatus({ message }: { message: Pick<OutboxMessage, "status" | "status_reason"> }) {
  const { t } = useTranslation();
  const label = outboxLabel(message.status, message.status_reason);
  return (
    <span className="inline-flex flex-col gap-1">
      <span>
        <StatusBadge kind={label.kind}>{t(label.labelKey)}</StatusBadge>
      </span>
      {label.reasonKey && <span className="text-sm text-ink-2">{t(label.reasonKey)}</span>}
    </span>
  );
}

/** Must appear wherever unapproved (synthetic) template text is shown. */
export function PlaceholderLabel() {
  const { t } = useTranslation();
  return (
    <Badge tone="accent" icon={FlaskConical}>
      {t("msg.placeholderLabel")}
    </Badge>
  );
}

/** One outgoing message: what was sent, its honest status, and who queued it. */
export function MessageRow({ message, showPerson = false }: { message: OutboxMessage; showPerson?: boolean }) {
  const { t } = useTranslation();
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 space-y-0.5">
          {showPerson && <p className="font-semibold text-ink">{message.person_name ?? t("msg.unknownPerson")}</p>}
          <p className="text-sm font-semibold text-ink-2">{t(`msg.purpose.${message.purpose}`)}</p>
          <p className="text-sm text-muted">
            {t("msg.queuedBy", { time: formatDateTime(message.created_at), name: message.created_by_name ?? t("msg.system") })}
          </p>
        </div>
        <MessageStatus message={message} />
      </div>
      {message.text && <p className="rounded-lg border border-line bg-page/60 p-3 text-sm whitespace-pre-wrap">{message.text}</p>}
      <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
        {message.template_placeholder && <PlaceholderLabel />}
        {message.kind === "TEMPLATE" && !message.audio_available && (
          <Badge icon={VolumeX}>{t("msg.audioNotApproved")}</Badge>
        )}
        {message.submitted_at && <span>{t("msg.submittedAt", { time: formatDateTime(message.submitted_at) })}</span>}
        {message.delivered_at && <span>{t("msg.deliveredAt", { time: formatDateTime(message.delivered_at) })}</span>}
        {message.read_at && <span>{t("msg.readAt", { time: formatDateTime(message.read_at) })}</span>}
        {message.attempts > 1 && <span>{t("msg.attempts", { count: message.attempts })}</span>}
        {message.resolved_at && <span>{t("msg.resolvedAt", { time: formatDateTime(message.resolved_at) })}</span>}
      </div>
    </div>
  );
}
