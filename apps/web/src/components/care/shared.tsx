import { useQueryClient, type QueryKey } from "@tanstack/react-query";
import type * as React from "react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ApiError } from "../../api/client";
import { isStaleConflict } from "../../lib/format";
import { Alert } from "../ui/status";

/** Error text for a failed care action. On a stale-version conflict the
 * affected queries are reloaded and a plain explanation is shown. */
export function useActionError(keys: QueryKey[]) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [message, setMessage] = useState<string | null>(null);
  return {
    message,
    clear: () => setMessage(null),
    onError: (err: unknown) => {
      if (isStaleConflict(err)) {
        keys.forEach((key) => void queryClient.invalidateQueries({ queryKey: key }));
        setMessage(t("care.changedElsewhere"));
      } else {
        setMessage(err instanceof ApiError ? err.message : t("states.errorBody"));
      }
    },
    reload: () => keys.forEach((key) => void queryClient.invalidateQueries({ queryKey: key })),
  };
}

export function ActionError({ message }: { message: string | null }) {
  return message ? <Alert kind="problem">{message}</Alert> : null;
}

/** A small inline panel that opens under a button for one action's inputs. */
export function InlineForm({
  onSubmit,
  onCancel,
  submitLabel,
  busy,
  children,
}: {
  onSubmit: () => void;
  onCancel: () => void;
  submitLabel: string;
  busy?: boolean;
  children: React.ReactNode;
}) {
  const { t } = useTranslation();
  return (
    <form
      className="space-y-3 rounded-lg border border-line bg-page/60 p-3 md:p-4"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
    >
      {children}
      <div className="flex flex-col gap-2 sm:flex-row">
        <button
          type="submit"
          disabled={busy}
          className="inline-flex min-h-12 items-center justify-center rounded-md bg-brand px-4 font-semibold text-brand-ink hover:bg-brand-strong disabled:opacity-50 md:min-h-10"
        >
          {submitLabel}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="inline-flex min-h-12 items-center justify-center rounded-md border border-line bg-surface px-4 font-semibold hover:bg-subtle md:min-h-10"
        >
          {t("care.cancel")}
        </button>
      </div>
    </form>
  );
}
