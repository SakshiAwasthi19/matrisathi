import { FlaskConical } from "lucide-react";
import { useTranslation } from "react-i18next";
import { ENV_LABEL, shouldShowEnvBanner } from "../lib/env";

/** Shown on every page, Login included, unless VITE_ENV_LABEL is "production". */
export function EnvBanner() {
  const { t } = useTranslation();
  if (!shouldShowEnvBanner(ENV_LABEL)) return null;
  return (
    <div className="bg-env px-4 py-2 text-center text-sm font-semibold text-env-ink" role="note">
      <span className="inline-flex items-center gap-2">
        <FlaskConical aria-hidden className="size-4 shrink-0" />
        {t("env.banner", { label: ENV_LABEL.toUpperCase() })}
      </span>
    </div>
  );
}
