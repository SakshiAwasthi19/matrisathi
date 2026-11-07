import { Search, UserPlus } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";
import { GuidePanel } from "../components/GuidePanel";
import { PageHeader } from "../components/PageHeader";
import { cn } from "../lib/utils";
import { FindMother } from "./FindMother";
import { RegisterNewMother } from "./RegisterNewMother";

type Mode = "find" | "register";

export function MotherRegister() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [mode, setMode] = useState<Mode>("find");
  const openEpisode = (episodeId: string) => navigate(`/episodes/${episodeId}`);

  const tab = (value: Mode, label: string, Icon: typeof Search) => (
    <button
      type="button"
      role="tab"
      id={`tab-${value}`}
      aria-selected={mode === value}
      aria-controls={`panel-${value}`}
      onClick={() => setMode(value)}
      className={cn(
        "inline-flex min-h-12 flex-1 items-center justify-center gap-2 rounded-md px-4 font-semibold md:min-h-10 md:flex-none",
        mode === value ? "bg-surface text-brand shadow-card" : "text-muted hover:text-ink",
      )}
    >
      <Icon aria-hidden className="size-4" />
      {label}
    </button>
  );

  return (
    <div className="space-y-6">
      <PageHeader title={t("mothers.title")} description={t("mothers.description")} />
      {/* Two columns on wide screens; on phones the guide moves below the form. */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start">
        <div className="space-y-4">
          <div role="tablist" className="flex gap-1 rounded-xl border border-line bg-subtle p-1 md:inline-flex">
            {tab("find", t("mothers.tabFind"), Search)}
            {tab("register", t("mothers.tabRegister"), UserPlus)}
          </div>
          <div role="tabpanel" id={`panel-${mode}`} aria-labelledby={`tab-${mode}`}>
            {mode === "find" ? (
              <FindMother onEpisodeCreated={openEpisode} />
            ) : (
              <RegisterNewMother onEpisodeCreated={openEpisode} />
            )}
          </div>
        </div>
        <aside>
          <GuidePanel />
        </aside>
      </div>
    </div>
  );
}
