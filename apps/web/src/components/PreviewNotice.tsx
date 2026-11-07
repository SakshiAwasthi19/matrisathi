import { Sparkles } from "lucide-react";
import { useTranslation } from "react-i18next";

/** Top of every preview screen: says plainly that nothing here is live. */
export function PreviewNotice({ body }: { body: string }) {
  const { t } = useTranslation();
  return (
    <div role="note" className="flex gap-3 rounded-[var(--radius-card)] border border-[#f1d9b3] bg-accent-soft/70 p-4 text-ink">
      <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-lg bg-surface text-accent ring-1 ring-[#f1d9b3]">
        <Sparkles aria-hidden className="size-4" />
      </span>
      <div className="space-y-0.5">
        <p className="font-semibold">{t("sample.noticeTitle")}</p>
        <p className="text-sm text-ink-2">{body}</p>
      </div>
    </div>
  );
}
