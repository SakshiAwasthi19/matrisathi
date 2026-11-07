import { FileQuestion, Loader2, Lock, Search, SearchX, TriangleAlert, type LucideIcon } from "lucide-react";
import type * as React from "react";
import { useTranslation } from "react-i18next";
import { ApiError } from "../api/client";

// The four states every screen designs for (Part G): loading, empty, error,
// and "you don't have access". The API answers 404 for both "missing" and
// "not yours" (so it never reveals another facility's records); the
// no-access state therefore says both.
/** "start" is the state before the user has asked for anything (e.g. before a search). */
export type PageStateKind = "start" | "loading" | "empty" | "error" | "no-access" | "not-found";

const ICONS: Record<PageStateKind, LucideIcon> = {
  start: Search,
  loading: Loader2,
  empty: SearchX,
  error: TriangleAlert,
  "no-access": Lock,
  "not-found": FileQuestion,
};

export function PageState({
  kind,
  title,
  body,
  action,
}: {
  kind: PageStateKind;
  title?: string;
  body?: string;
  action?: React.ReactNode;
}) {
  const { t } = useTranslation();
  const Icon = ICONS[kind];
  const defaults: Record<PageStateKind, { title: string; body?: string }> = {
    start: { title: "" },
    loading: { title: t("common.loading") },
    empty: { title: "" },
    error: { title: t("states.errorTitle"), body: t("states.errorBody") },
    "no-access": { title: t("states.noAccessTitle"), body: t("states.noAccessBody") },
    "not-found": { title: t("states.notFoundTitle"), body: t("states.notFoundBody") },
  };
  const heading = title ?? defaults[kind].title;
  const text = body ?? defaults[kind].body;
  return (
    <div
      role={kind === "error" ? "alert" : "status"}
      aria-busy={kind === "loading" || undefined}
      className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-line bg-surface/70 px-4 py-10 text-center"
    >
      <span
        className={
          kind === "error" || kind === "no-access"
            ? "mb-1 inline-flex size-14 items-center justify-center rounded-full bg-problem-bg text-problem"
            : "mb-1 inline-flex size-14 items-center justify-center rounded-full bg-brand-soft text-brand"
        }
      >
        <Icon aria-hidden className={kind === "loading" ? "size-7 animate-spin" : "size-7"} />
      </span>
      {heading && <p className="text-base font-semibold text-ink">{heading}</p>}
      {text && <p className="max-w-prose text-base text-muted">{text}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

/** Picks the right state for a failed request. */
export function errorStateKind(error: unknown): PageStateKind {
  return error instanceof ApiError && (error.status === 404 || error.status === 403) ? "no-access" : "error";
}
