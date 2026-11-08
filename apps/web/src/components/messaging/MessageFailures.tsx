import { useMutation, useQuery } from "@tanstack/react-query";
import { CheckCheck, MessageSquareWarning, PhoneForwarded } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { messagingApi, type OutboxMessage } from "../../api/client";
import { ActionError, InlineForm } from "../care/shared";
import { errorStateKind, PageState } from "../PageState";
import { Button } from "../ui/button";
import { Card, CardHeader } from "../ui/card";
import { Field, Input } from "../ui/field";
import { CardSkeleton } from "../ui/kit";
import { MessageRow, useMessagingError } from "./shared";

function FailureRow({ message, facilityId, canSend }: { message: OutboxMessage; facilityId: string; canSend: boolean }) {
  const { t } = useTranslation();
  const errors = useMessagingError([["messageFailures", facilityId], ["inboxSummary"], ["tasks"]]);
  const [resolving, setResolving] = useState(false);
  const [note, setNote] = useState("");
  const call = useMutation({
    mutationFn: () => messagingApi.callInstead(message.id),
    meta: { toast: t("msg.callTaskCreated") },
    onSuccess: () => {
      errors.clear();
      errors.reload();
    },
    onError: errors.onError,
  });
  const resolve = useMutation({
    mutationFn: () => messagingApi.resolve(message.id, note.trim() || null),
    meta: { toast: t("msg.resolvedToast") },
    onSuccess: () => {
      setResolving(false);
      errors.clear();
      errors.reload();
    },
    onError: errors.onError,
  });
  return (
    <li className="space-y-3 px-4 py-3.5 md:px-5">
      <MessageRow message={message} showPerson />
      {canSend && !resolving && (
        <div className="flex flex-col gap-2 sm:flex-row">
          <Button size="sm" variant="secondary" disabled={call.isPending} onClick={() => call.mutate()}>
            <PhoneForwarded aria-hidden className="size-4" />
            {t("msg.callInstead")}
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setResolving(true)}>
            <CheckCheck aria-hidden className="size-4" />
            {t("msg.markResolved")}
          </Button>
        </div>
      )}
      {resolving && (
        <InlineForm onSubmit={() => resolve.mutate()} onCancel={() => setResolving(false)} submitLabel={t("msg.markResolved")} busy={resolve.isPending}>
          <Field label={t("msg.resolveNoteLabel")} htmlFor={`note-${message.id}`} hint={t("msg.resolveNoteHint")}>
            <Input id={`note-${message.id}`} maxLength={300} value={note} onChange={(e) => setNote(e.target.value)} />
          </Field>
        </InlineForm>
      )}
      <ActionError message={errors.message} />
    </li>
  );
}

/** Failed, unconfirmed and blocked messages stay here until a person deals with them (F017). */
export function MessageFailures({ facilityId, canSend }: { facilityId: string; canSend: boolean }) {
  const { t } = useTranslation();
  const failures = useQuery({
    queryKey: ["messageFailures", facilityId],
    queryFn: () => messagingApi.failures(facilityId),
    enabled: !!facilityId,
  });
  return (
    <Card id="failures" className="overflow-hidden p-0 md:p-0">
      <div className="p-4 pb-0 md:p-5 md:pb-0">
        <CardHeader icon={MessageSquareWarning} title={t("msg.failuresTitle")} description={t("msg.failuresDescription")} />
      </div>
      {failures.isPending && (
        <div className="p-4 md:p-5">
          <CardSkeleton lines={2} />
        </div>
      )}
      {failures.isError && (
        <div className="p-4 md:p-5">
          <PageState kind={errorStateKind(failures.error)} />
        </div>
      )}
      {failures.data && failures.data.length === 0 && <p className="px-5 pt-2 pb-6 text-center text-muted">{t("msg.failuresEmpty")}</p>}
      {failures.data && failures.data.length > 0 && (
        <ul className="divide-y divide-line/70 border-t border-line">
          {failures.data.map((m) => (
            <FailureRow key={m.id} message={m} facilityId={facilityId} canSend={canSend} />
          ))}
        </ul>
      )}
    </Card>
  );
}
