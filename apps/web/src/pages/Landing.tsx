import {
  ArrowRight,
  CalendarCheck,
  CircleHelp,
  FileStack,
  HeartPulse,
  LogIn,
  NotebookTabs,
  Search,
  ShieldCheck,
  Siren,
  Smartphone,
  Stethoscope,
  Users,
  type LucideIcon,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

const FEATURES: { icon: LucideIcon; key: string }[] = [
  { icon: Search, key: "find" },
  { icon: CalendarCheck, key: "visits" },
  { icon: FileStack, key: "records" },
  { icon: NotebookTabs, key: "birth" },
  { icon: Users, key: "roles" },
  { icon: Siren, key: "urgent" },
];

const PRINCIPLES: { icon: LucideIcon; key: string }[] = [
  { icon: Smartphone, key: "sharedPhone" },
  { icon: CircleHelp, key: "unknown" },
  { icon: Stethoscope, key: "assistive" },
  { icon: ShieldCheck, key: "facility" },
];

/** Illustrative product preview built from shapes (not a screenshot, no data). */
function ProductSketch() {
  const { t } = useTranslation();
  const bar = (w: string, c = "bg-sunken") => <span className={`block h-2.5 rounded-full ${c}`} style={{ width: w }} />;
  return (
    <figure className="relative">
      <div aria-hidden className="overflow-hidden rounded-2xl border border-line bg-surface shadow-pop">
        <div className="flex items-center gap-1.5 border-b border-line bg-page px-4 py-3">
          <span className="size-2.5 rounded-full bg-line-strong" />
          <span className="size-2.5 rounded-full bg-line-strong" />
          <span className="size-2.5 rounded-full bg-line-strong" />
        </div>
        <div className="grid grid-cols-[7.5rem_1fr]">
          <div className="space-y-3 border-r border-line p-4">
            <span className="block h-6 w-6 rounded-md bg-brand" />
            {bar("80%", "bg-brand-soft")}
            {bar("65%")}
            {bar("72%")}
            {bar("55%")}
          </div>
          <div className="space-y-4 p-5">
            {bar("45%", "bg-ink/15")}
            <div className="grid grid-cols-3 gap-3">
              {[0, 1, 2].map((i) => (
                <div key={i} className="space-y-2 rounded-xl border border-line p-3">
                  {bar("50%")}
                  <span className="block h-5 w-8 rounded bg-ink/15" />
                </div>
              ))}
            </div>
            <div className="rounded-xl border border-line p-4">
              <svg viewBox="0 0 200 60" className="h-20 w-full">
                <path d="M0 50 L30 42 L60 46 L90 30 L120 34 L150 20 L180 24 L200 12" fill="none" stroke="var(--color-series-1)" strokeWidth="2" strokeLinecap="round" />
                <path d="M0 50 L30 42 L60 46 L90 30 L120 34 L150 20 L180 24 L200 12 L200 60 L0 60 Z" fill="var(--color-series-1)" opacity="0.08" />
              </svg>
            </div>
            <div className="space-y-2.5 rounded-xl border border-line p-4">
              {["70%", "55%", "62%"].map((w, i) => (
                <div key={i} className="flex items-center gap-3">
                  <span className="size-6 rounded-full bg-accent-soft" />
                  {bar(w)}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
      <figcaption className="mt-3 text-center text-xs text-faint">{t("landing.sketchCaption")}</figcaption>
    </figure>
  );
}

/** Public page for signed-out visitors: what the product is, honestly. */
export function Landing() {
  const { t } = useTranslation();
  return (
    <div className="min-h-full bg-page">
      <header className="sticky top-0 z-20 border-b border-line/70 bg-page/85 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-3 px-4 md:px-8">
          <span className="flex items-center gap-2.5">
            <span className="inline-flex size-9 items-center justify-center rounded-[10px] bg-brand text-brand-ink">
              <HeartPulse aria-hidden className="size-5" />
            </span>
            <span className="text-lg font-semibold tracking-tight">{t("app.name")}</span>
          </span>
          <nav className="ml-auto flex items-center gap-1">
            <Link
              to="/urgent-help"
              className="hidden min-h-11 items-center gap-2 rounded-[10px] px-3 font-semibold text-urgent hover:bg-urgent/8 sm:inline-flex"
            >
              <Siren aria-hidden className="size-4" />
              {t("nav.urgentHelp")}
            </Link>
            <Link
              to="/login"
              className="inline-flex min-h-11 items-center gap-2 rounded-[10px] bg-ink px-4 font-semibold text-white hover:bg-ink-2"
            >
              <LogIn aria-hidden className="size-4" />
              {t("landing.signIn")}
            </Link>
          </nav>
        </div>
      </header>

      <main>
        <section className="mx-auto grid max-w-6xl items-center gap-12 px-4 pt-14 pb-16 md:px-8 md:pt-20 lg:grid-cols-[1.05fr_1fr]">
          <div className="animate-rise space-y-6">
            <span className="inline-flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1 text-sm font-medium text-muted shadow-card">
              <span className="size-1.5 rounded-full bg-brand" />
              {t("landing.eyebrow")}
            </span>
            <h1 className="text-4xl leading-[1.1] font-semibold tracking-tight text-ink md:text-5xl">{t("landing.title")}</h1>
            <p className="max-w-xl text-lg text-muted">{t("landing.body")}</p>
            <div className="flex flex-col gap-3 sm:flex-row">
              <Link
                to="/login"
                className="inline-flex min-h-12 items-center justify-center gap-2 rounded-[var(--radius-control)] bg-brand px-5 font-semibold text-brand-ink shadow-raised hover:bg-brand-strong"
              >
                {t("landing.ctaPrimary")}
                <ArrowRight aria-hidden className="size-4" />
              </Link>
              <a
                href="#how"
                className="inline-flex min-h-12 items-center justify-center gap-2 rounded-[var(--radius-control)] border border-line bg-surface px-5 font-semibold text-ink shadow-card hover:border-line-strong"
              >
                {t("landing.ctaSecondary")}
              </a>
            </div>
            <p className="text-sm text-faint">{t("landing.pilotNote")}</p>
          </div>
          <div className="animate-rise [animation-delay:120ms]">
            <ProductSketch />
          </div>
        </section>

        <section className="border-y border-line bg-surface">
          <div className="mx-auto max-w-6xl px-4 py-16 md:px-8">
            <div className="max-w-2xl">
              <h2 className="text-2xl font-semibold tracking-tight md:text-3xl">{t("landing.featuresTitle")}</h2>
              <p className="mt-2 text-lg text-muted">{t("landing.featuresBody")}</p>
            </div>
            <ul className="mt-10 grid gap-x-8 gap-y-10 sm:grid-cols-2 lg:grid-cols-3">
              {FEATURES.map(({ icon: Icon, key }) => (
                <li key={key} className="space-y-3">
                  <span className="inline-flex size-11 items-center justify-center rounded-xl bg-brand-tint text-brand ring-1 ring-brand-soft">
                    <Icon aria-hidden className="size-5" />
                  </span>
                  <h3 className="text-lg font-semibold">{t(`landing.feature.${key}.title`)}</h3>
                  <p className="text-muted">{t(`landing.feature.${key}.body`)}</p>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section id="how" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-16 md:px-8">
          <h2 className="text-2xl font-semibold tracking-tight md:text-3xl">{t("landing.howTitle")}</h2>
          <ol className="mt-10 grid gap-6 md:grid-cols-3">
            {[1, 2, 3].map((n) => (
              <li key={n} className="relative rounded-[var(--radius-card)] border border-line bg-surface p-6 shadow-card">
                <span className="tabular inline-flex size-9 items-center justify-center rounded-full bg-ink text-sm font-semibold text-white">{n}</span>
                <h3 className="mt-4 text-lg font-semibold">{t(`landing.how.${n}.title`)}</h3>
                <p className="mt-1.5 text-muted">{t(`landing.how.${n}.body`)}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className="bg-brand-deep text-white">
          <div className="mx-auto max-w-6xl px-4 py-16 md:px-8">
            <h2 className="text-2xl font-semibold tracking-tight md:text-3xl">{t("landing.principlesTitle")}</h2>
            <ul className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
              {PRINCIPLES.map(({ icon: Icon, key }) => (
                <li key={key} className="space-y-3 rounded-[var(--radius-card)] border border-white/10 bg-white/5 p-5">
                  <Icon aria-hidden className="size-5 text-[#8fd6cf]" />
                  <p className="font-semibold">{t(`landing.principle.${key}.title`)}</p>
                  <p className="text-sm text-white/75">{t(`landing.principle.${key}.body`)}</p>
                </li>
              ))}
            </ul>
          </div>
        </section>
      </main>

      <footer className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-8 text-sm text-faint sm:flex-row sm:items-center sm:justify-between md:px-8">
        <span>© {new Date().getFullYear()} {t("app.name")}</span>
        <span>{t("common.syntheticOnly")}</span>
      </footer>
    </div>
  );
}
