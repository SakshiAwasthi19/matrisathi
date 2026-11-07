import { CircleHelp, FlaskConical, Lightbulb, Search, Smartphone, type LucideIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Card } from "./ui/card";

// Working rules only (how to use the system safely). No clinical content.
const RULES: { icon: LucideIcon; key: string }[] = [
  { icon: Search, key: "guide.searchFirst" },
  { icon: Smartphone, key: "guide.sharedPhone" },
  { icon: CircleHelp, key: "guide.unknown" },
  { icon: FlaskConical, key: "guide.synthetic" },
];

export function GuidePanel() {
  const { t } = useTranslation();
  return (
    <Card className="space-y-4 lg:sticky lg:top-24">
      <h2 className="flex items-center gap-2 text-base font-semibold">
        <span className="inline-flex size-8 items-center justify-center rounded-lg bg-accent-soft text-accent">
          <Lightbulb aria-hidden className="size-4" />
        </span>
        {t("guide.title")}
      </h2>
      <ol className="space-y-4">
        {RULES.map(({ icon: Icon, key }) => (
          <li key={key} className="flex gap-3 text-[0.95rem] leading-relaxed">
            <span className="inline-flex size-8 shrink-0 items-center justify-center rounded-full bg-brand-soft text-brand">
              <Icon aria-hidden className="size-4" />
            </span>
            <span className="pt-1">{t(key)}</span>
          </li>
        ))}
      </ol>
    </Card>
  );
}
