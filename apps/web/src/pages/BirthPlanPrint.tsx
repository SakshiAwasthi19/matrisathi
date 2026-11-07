import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Printer } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router";
import { api, nextStepApi, type HelpContact } from "../api/client";
import { errorStateKind, PageState } from "../components/PageState";
import { Button } from "../components/ui/button";
import { formatDate } from "../lib/format";
import { urgentHelpUrl } from "../lib/urgent";

function Line({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="grid grid-cols-[11rem_1fr] gap-3 border-b border-line py-2 print:border-black/40">
      <dt className="font-semibold">{label}</dt>
      {/* Blank line to fill in by hand when nothing is recorded. */}
      <dd className="min-h-7">{value || <span className="inline-block w-full border-b border-dashed border-line print:border-black/50" />}</dd>
    </div>
  );
}

function contactText(c: HelpContact | null, verified: (d: string) => string): string | null {
  if (!c) return null;
  return `${c.name} · ${c.phone}${c.alternate_phone ? ` / ${c.alternate_phone}` : ""} (${verified(c.verified_on)})`;
}

/** Printable birth plan (F013). Plain black-on-white when printed. */
export function BirthPlanPrint() {
  const { t } = useTranslation();
  const { episodeId = "" } = useParams();
  const episode = useQuery({ queryKey: ["episode", episodeId], queryFn: () => api.getPregnancyEpisode(episodeId) });
  const plan = useQuery({ queryKey: ["birthPlan", episodeId], queryFn: () => nextStepApi.getBirthPlan(episodeId) });

  if (episode.isPending || plan.isPending) return <PageState kind="loading" />;
  if (episode.isError) return <PageState kind={errorStateKind(episode.error)} />;
  if (plan.isError) return <PageState kind={errorStateKind(plan.error)} />;
  const p = plan.data;
  const e = episode.data;
  const verified = (d: string) => t("birth.verifiedOn", { date: formatDate(d) });

  return (
    <div className="mx-auto max-w-3xl bg-surface p-6 print:max-w-none print:p-0">
      <div className="mb-4 flex flex-wrap gap-2 print:hidden">
        <Button asChild variant="ghost" className="-ml-2">
          <Link to={`/episodes/${episodeId}`}>
            <ArrowLeft aria-hidden className="size-4" />
            {t("episode.title")}
          </Link>
        </Button>
        <Button onClick={() => window.print()}>
          <Printer aria-hidden className="size-4" />
          {t("birth.print")}
        </Button>
      </div>

      <h1 className="text-2xl font-semibold">{t("birth.printTitle")}</h1>
      <p className="mt-1 text-lg">{t("birth.printFor", { name: e.mother_full_name })}</p>

      <dl className="mt-4">
        <Line label={t("birth.birthPlace")} value={[contactText(p?.chosen_birth_place ?? null, verified), p?.chosen_birth_place_note].filter(Boolean).join(" — ") || null} />
        <Line label={t("birth.referralSite")} value={contactText(p?.referral_site ?? null, verified)} />
        <Line label={t("birth.companion")} value={p?.companion_name} />
        <Line label={t("birth.transport")} value={p?.transport_arrangement} />
        <Line label={t("birth.landmarks")} value={p?.landmarks} />
        <Line label={t("birth.primary")} value={contactText(p?.primary_contact ?? null, verified)} />
        <Line label={t("birth.alternate")} value={contactText(p?.alternate_contact ?? null, verified)} />
      </dl>

      <div className="mt-5 rounded-lg border-2 border-urgent p-3 print:border-black">
        <p className="font-semibold">{t("birth.printUrgent")}</p>
        <p className="mt-1 font-mono text-base break-all">{urgentHelpUrl(e.facility_id)}</p>
      </div>

      <div className="mt-5">
        <p className="font-semibold">{t("birth.printNotes")}</p>
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-8 border-b border-dashed border-line print:border-black/50" />
        ))}
      </div>

      <p className="mt-4 text-sm text-muted print:text-black">
        {t("birth.noDispatch")} {t("birth.printedOn", { date: formatDate(new Date().toISOString()) })}
      </p>
    </div>
  );
}
