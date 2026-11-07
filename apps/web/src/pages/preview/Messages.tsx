import { ArrowLeft, Image, Link2, Lock, Mic, SendHorizontal } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { initials } from "../../components/Avatar";
import { PageHeader } from "../../components/PageHeader";
import { PreviewNotice } from "../../components/PreviewNotice";
import { Card } from "../../components/ui/card";
import { SampleBadge } from "../../components/ui/kit";
import { StatusBadge, type StatusKind } from "../../components/ui/status";
import { sampleThreads, type SampleThread, type ThreadStatus } from "../../demo/sample";
import { cn } from "../../lib/utils";

const THREAD_STATUS: Record<ThreadStatus, StatusKind> = { open: "neutral", unlinked: "unknown", closed: "confirmed" };

function KindIcon({ kind }: { kind: SampleThread["kind"] }) {
  if (kind === "voice") return <Mic aria-hidden className="size-3.5 shrink-0" />;
  if (kind === "photo") return <Image aria-hidden className="size-3.5 shrink-0" />;
  return null;
}

/** PREVIEW: the family-message inbox (WhatsApp channel, later phase). Sample data only. */
export function Messages() {
  const { t } = useTranslation();
  const [selected, setSelected] = useState<string | null>(sampleThreads[0].id);
  const [mobileThread, setMobileThread] = useState(false);
  const thread = sampleThreads.find((x) => x.id === selected) ?? sampleThreads[0];

  return (
    <div className="space-y-6">
      <PageHeader title={t("messages.title")} description={t("messages.description")} badge={<SampleBadge />} showContext={false} />
      <PreviewNotice body={t("messages.notice")} />

      <Card className="grid overflow-hidden p-0 md:grid-cols-[20rem_1fr] md:p-0">
        {/* Inbox */}
        <div className={cn("border-line md:border-r", mobileThread && "hidden md:block")}>
          <div className="border-b border-line px-4 py-3 text-sm font-semibold text-muted">{t("messages.inbox", { count: sampleThreads.length })}</div>
          <ul>
            {sampleThreads.map((th) => (
              <li key={th.id}>
                <button
                  type="button"
                  onClick={() => {
                    setSelected(th.id);
                    setMobileThread(true);
                  }}
                  aria-current={th.id === thread.id}
                  className={cn(
                    "flex w-full items-start gap-3 border-b border-line/70 px-4 py-3.5 text-left transition-colors",
                    th.id === thread.id ? "bg-brand-tint" : "hover:bg-subtle/70",
                  )}
                >
                  <span aria-hidden className="inline-flex size-10 shrink-0 items-center justify-center rounded-full bg-accent-soft text-sm font-semibold text-accent">
                    {th.status === "unlinked" ? "?" : initials(th.name)}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex items-baseline justify-between gap-2">
                      <span className="truncate font-semibold text-ink">{th.name}</span>
                      <span className="shrink-0 text-xs text-faint">{th.time}</span>
                    </span>
                    <span className="mt-0.5 flex items-center gap-1.5 truncate text-sm text-muted">
                      <KindIcon kind={th.kind} />
                      <span className="truncate">{th.preview}</span>
                    </span>
                  </span>
                  {th.unread > 0 && (
                    <span className="tabular mt-1 inline-flex size-5 shrink-0 items-center justify-center rounded-full bg-brand text-[0.6875rem] font-semibold text-brand-ink">
                      {th.unread}
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </div>

        {/* Thread */}
        <div className={cn("flex min-h-[28rem] flex-col", !mobileThread && "hidden md:flex")}>
          <div className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3">
            <button
              type="button"
              onClick={() => setMobileThread(false)}
              aria-label={t("messages.back")}
              className="-ml-2 inline-flex size-10 items-center justify-center rounded-lg text-muted hover:bg-subtle md:hidden"
            >
              <ArrowLeft aria-hidden className="size-5" />
            </button>
            <div className="min-w-0 flex-1">
              <p className="truncate font-semibold">{thread.name}</p>
              <p className="tabular text-sm text-muted">{thread.phoneTail}</p>
            </div>
            <StatusBadge kind={THREAD_STATUS[thread.status]}>{t(`messages.status.${thread.status}`)}</StatusBadge>
            {thread.status === "unlinked" && (
              <button type="button" disabled className="inline-flex min-h-10 items-center gap-2 rounded-[10px] border border-line px-3 text-sm font-semibold text-muted opacity-70" title={t("messages.notAvailable")}>
                <Link2 aria-hidden className="size-4" />
                {t("messages.link")}
              </button>
            )}
          </div>
          <ol className="flex-1 space-y-3 bg-page/60 px-4 py-5">
            {thread.messages.map((m, i) => (
              <li key={i} className={cn("flex", m.from === "staff" ? "justify-end" : m.from === "system" ? "justify-center" : "justify-start")}>
                {m.from === "system" ? (
                  <span className="max-w-md rounded-full bg-subtle px-3 py-1 text-center text-xs text-muted">{m.text}</span>
                ) : (
                  <div
                    className={cn(
                      "max-w-[80%] rounded-2xl px-3.5 py-2.5 text-[0.95rem] shadow-card",
                      m.from === "staff" ? "rounded-br-md bg-brand text-brand-ink" : "rounded-bl-md border border-line bg-surface text-ink",
                    )}
                  >
                    <p className="flex items-center gap-2">
                      {m.kind === "voice" && <Mic aria-hidden className="size-4" />}
                      {m.kind === "photo" && <Image aria-hidden className="size-4" />}
                      {m.text}
                    </p>
                    <p className={cn("mt-1 text-right text-[0.6875rem]", m.from === "staff" ? "text-white/70" : "text-faint")}>{m.time}</p>
                  </div>
                )}
              </li>
            ))}
          </ol>
          <div className="border-t border-line p-3">
            <div className="flex items-center gap-2 rounded-[10px] border border-line bg-subtle/60 px-3 py-2 text-sm text-faint">
              <Lock aria-hidden className="size-4 shrink-0" />
              <span className="flex-1">{t("messages.composerDisabled")}</span>
              <SendHorizontal aria-hidden className="size-4" />
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}
