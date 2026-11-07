import { FlaskConical } from "lucide-react";
import { useTranslation } from "react-i18next";
import { ENV_LABEL, shouldShowEnvBanner } from "../lib/env";

/** Shown on every page, Login included, unless VITE_ENV_LABEL is "production". */
export function EnvBanner() {
  const { t } = useTranslation();
  if (!shouldShowEnvBanner(ENV_LABEL)) return null;
  return (
    <div className="relative z-40 bg-env px-4 py-1.5 text-center text-[0.8125rem] font-semibold text-env-ink print:hidden" role="note">
      <span className="inline-flex items-center gap-2">
        <FlaskConical aria-hidden className="size-4 shrink-0" />
        {t("env.banner", { label: ENV_LABEL.toUpperCase() })}
      </span>
    </div>
  );
}
