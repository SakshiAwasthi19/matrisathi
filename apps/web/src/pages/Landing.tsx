import {
  ArrowRight,
  CalendarCheck,
  CheckCircle2,
  CircleHelp,
  ClipboardList,
  Clock,
  FileStack,
  HeartPulse,
  LogIn,
  NotebookTabs,
  Phone,
  Search,
  ShieldCheck,
  Siren,
  Smartphone,
  Stethoscope,
  UserPlus,
  Users,
  type LucideIcon,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { cn } from "../lib/utils";

const FEATURES: { icon: LucideIcon; key: string; wide?: boolean }[] = [
  { icon: Search, key: "find", wide: true },
  { icon: CalendarCheck, key: "visits" },
  { icon: FileStack, key: "records" },
  { icon: NotebookTabs, key: "birth" },
  { icon: Siren, key: "urgent", wide: true },
];

const JOURNEY: { icon: LucideIcon; key: string }[] = [
  { icon: UserPlus, key: "register" },
  { icon: ClipboardList, key: "plan" },
  { icon: CalendarCheck, key: "visits" },
  { icon: FileStack, key: "reports" },
  { icon: NotebookTabs, key: "birth" },
];

const PRINCIPLES: { icon: LucideIcon; key: string }[] = [
  { icon: Smartphone, key: "sharedPhone" },
  { icon: CircleHelp, key: "unknown" },
  { icon: Stethoscope, key: "assistive" },
  { icon: ShieldCheck, key: "facility" },
];

const ROLES = ["COORDINATOR", "NURSE", "ASHA", "DOCTOR"] as const;

/** Small static copies of real UI pieces, for the hero illustration only. */
function Pill({ tone, icon: Icon, children }: { tone: "ok" | "pending"; icon: LucideIcon; children: React.ReactNode }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[0.6875rem] font-semibold",
        tone === "ok" ? "border-ok-line bg-ok-bg text-ok" : "border-pending-line bg-pending-bg text-pending",
      )}
    >
      <Icon aria-hidden className="size-3" />
      {children}
    </span>
  );
}

/** Hero illustration: a composed mock of the record and worklist, using
 * obviously synthetic names. Decorative; described by its caption. */
function HeroMock() {
  const { t } = useTranslation();
  const steps = ["register", "plan", "visits", "reports", "birth"];
  return (
    <figure className="relative mx-auto w-full max-w-[36rem]">
      <div aria-hidden className="relative pt-4 pb-20 sm:pr-10">
        {/* Soft backdrop shape and dot grid (solid tint, no gradient). */}
        <div className="absolute -inset-4 -z-10 rounded-[2rem] bg-brand-tint ring-1 ring-brand-soft sm:-inset-6" />
        <div className="absolute -inset-4 -z-10 rounded-[2rem] opacity-60 [background-image:radial-gradient(var(--color-brand-soft)_1.2px,transparent_1.2px)] [background-size:16px_16px] sm:-inset-6" />

        {/* Record card */}
        <div className="rounded-2xl border border-line bg-surface p-5 pb-16 shadow-pop">
          <div className="flex items-center gap-3">
            <span className="inline-flex size-11 items-center justify-center rounded-full bg-accent-soft text-sm font-semibold text-accent">SA</span>
            <div className="min-w-0 flex-1">
              <p className="text-[0.625rem] font-semibold tracking-wide text-faint uppercase">{t("landing.mock.record")}</p>
              <p className="truncate font-semibold text-ink">{t("landing.mock.name")}</p>
            </div>
            <span className="hidden rounded-lg bg-brand px-2.5 py-1.5 text-xs font-semibold text-brand-ink sm:inline">{t("landing.mock.nextStep")}</span>
          </div>
          <div className="mt-3 flex flex-wrap gap-1.5">
            <Pill tone="ok" icon={CheckCircle2}>
              {t("landing.mock.datingConfirmed")}
            </Pill>
            <Pill tone="pending" icon={Clock}>
              {t("landing.mock.contactPending")}
            </Pill>
          </div>
          {/* Journey progress */}
          <div className="mt-5">
            <div className="flex items-center">
              {steps.map((s, i) => (
                <div key={s} className="flex flex-1 items-center last:flex-none">
                  <span
                    className={cn(
                      "inline-flex size-6 shrink-0 items-center justify-center rounded-full text-[0.625rem] font-bold",
                      i < 3 ? "bg-brand text-brand-ink" : i === 3 ? "bg-surface text-brand ring-2 ring-brand" : "bg-subtle text-faint ring-1 ring-line",
                    )}
                  >
                    {i < 3 ? <CheckCircle2 className="size-3.5" /> : i + 1}
                  </span>
                  {i < steps.length - 1 && <span className={cn("mx-1 h-0.5 flex-1 rounded-full", i < 3 ? "bg-brand" : "bg-line")} />}
                </div>
              ))}
            </div>
            <div className="mt-2 flex justify-between text-[0.625rem] font-medium text-muted">
              {steps.map((s) => (
                <span key={s} className="w-12 text-center first:text-left last:text-right">
                  {t(`landing.journey.${s}.short`)}
                </span>
              ))}
            </div>
          </div>
          {/* Facts */}
          <div className="mt-5 grid grid-cols-3 gap-2 border-t border-line pt-4">
            {[
              [t("landing.mock.edd"), "1 Mar"],
              [t("landing.mock.visits"), "3 / 8"],
              [t("landing.mock.reports"), "2"],
            ].map(([k, v]) => (
              <div key={k}>
                <p className="text-[0.625rem] font-semibold tracking-wide text-faint uppercase">{k}</p>
                <p className="tabular text-sm font-semibold text-ink">{v}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Floating worklist card */}
        <div className="absolute bottom-0 left-4 w-[15.5rem] rounded-xl border border-line bg-surface p-3.5 shadow-pop sm:-left-8">
          <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-ink">
            <CalendarCheck className="size-3.5 text-brand" />
            {t("landing.mock.upNext")}
          </p>
          {[
            [t("landing.mock.task1"), t("landing.mock.today")],
            [t("landing.mock.task2"), t("landing.mock.thu")],
          ].map(([task, when]) => (
            <div key={task} className="flex items-center justify-between gap-2 border-t border-line/70 py-1.5 text-xs">
              <span className="truncate text-ink-2">{task}</span>
              <span className="shrink-0 text-faint">{when}</span>
            </div>
          ))}
        </div>

        {/* Floating confirmation toast */}
        <div className="absolute top-0 right-0 hidden items-center gap-2 rounded-xl bg-ink px-3 py-2 text-xs font-medium text-white shadow-pop sm:flex">
          <CheckCircle2 className="size-3.5 text-[#7fd3b0]" />
          {t("landing.mock.saved")}
        </div>

        {/* Floating urgent help chip */}
        <div className="absolute right-2 bottom-[4.25rem] hidden items-center gap-2 rounded-xl border border-line bg-surface px-3 py-2 text-xs font-semibold text-urgent shadow-raised sm:flex">
          <Phone className="size-3.5" />
          {t("landing.mock.urgent")}
        </div>
      </div>
      <figcaption className="mt-6 text-center text-xs text-faint">{t("landing.sketchCaption")}</figcaption>
    </figure>
  );
}

/** Public page for signed-out visitors: what the product is, honestly. */
export function Landing() {
  const { t } = useTranslation();
  return (
    <div className="min-h-full overflow-x-hidden bg-page">
      <header className="sticky top-0 z-20 border-b border-line/70 bg-page/85 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-3 px-4 md:px-8">
          <span className="flex items-center gap-2.5">
            <span className="inline-flex size-9 items-center justify-center rounded-control bg-brand text-brand-ink">
              <HeartPulse aria-hidden className="size-5" />
            </span>
            <span className="text-lg font-semibold tracking-tight">{t("app.name")}</span>
          </span>
          <nav aria-label={t("landing.navLabel")} className="ml-6 hidden items-center gap-1 md:flex">
            {(["features", "journey", "principles"] as const).map((id) => (
              <a key={id} href={`#${id}`} className="rounded-lg px-3 py-2 text-sm font-medium text-muted hover:bg-subtle hover:text-ink">
                {t(`landing.nav.${id}`)}
              </a>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-1">
            <Link
              to="/urgent-help"
              className="hidden min-h-11 items-center gap-2 rounded-control px-3 font-semibold text-urgent hover:bg-urgent/8 sm:inline-flex"
            >
              <Siren aria-hidden className="size-4" />
              {t("nav.urgentHelp")}
            </Link>
            <Link to="/login" className="inline-flex min-h-11 items-center gap-2 rounded-control bg-ink px-4 font-semibold text-white hover:bg-ink-2">
              <LogIn aria-hidden className="size-4" />
              {t("landing.signIn")}
            </Link>
          </div>
        </div>
      </header>

      <main>
        {/* Hero */}
        <section className="mx-auto grid max-w-6xl items-center gap-14 px-4 pt-12 pb-20 md:px-8 md:pt-20 lg:grid-cols-[1fr_1.05fr] lg:gap-12">
          <div className="animate-rise space-y-7">
            <span className="inline-flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1 text-sm font-medium text-muted shadow-card">
              <span className="size-1.5 rounded-full bg-brand" />
              {t("landing.eyebrow")}
            </span>
            <h1 className="text-[2.5rem] leading-[1.05] font-semibold tracking-[-0.02em] text-ink md:text-[3.5rem]">
              {t("landing.titleLead")} <span className="text-brand">{t("landing.titleAccent")}</span>
            </h1>
            <p className="max-w-xl text-lg leading-relaxed text-muted">{t("landing.body")}</p>
            <div className="flex flex-col gap-3 sm:flex-row">
              <Link
                to="/login"
                className="group inline-flex min-h-12 items-center justify-center gap-2 rounded-control bg-brand px-5 font-semibold text-brand-ink shadow-raised hover:bg-brand-strong"
              >
                {t("landing.ctaPrimary")}
                <ArrowRight aria-hidden className="size-4 transition-transform group-hover:translate-x-0.5" />
              </Link>
              <a
                href="#journey"
                className="inline-flex min-h-12 items-center justify-center gap-2 rounded-control border border-line bg-surface px-5 font-semibold text-ink shadow-card hover:border-line-strong"
              >
                {t("landing.ctaSecondary")}
              </a>
            </div>
            <div className="space-y-2.5 border-t border-line pt-6">
              <p className="text-sm font-medium text-faint">{t("landing.builtFor")}</p>
              <ul className="flex flex-wrap gap-2">
                {ROLES.map((r) => (
                  <li key={r} className="inline-flex items-center gap-1.5 rounded-full bg-surface px-3 py-1 text-sm font-semibold text-ink-2 ring-1 ring-line">
                    <Users aria-hidden className="size-3.5 text-brand" />
                    {t(`nav.role.${r}`)}
                  </li>
                ))}
              </ul>
            </div>
          </div>
          <div className="animate-rise [animation-delay:120ms]">
            <HeroMock />
          </div>
        </section>

        {/* Journey */}
        <section id="journey" className="scroll-mt-20 border-y border-line bg-surface">
          <div className="mx-auto max-w-6xl px-4 py-20 md:px-8">
            <p className="text-sm font-semibold tracking-wide text-brand uppercase">{t("landing.journeyEyebrow")}</p>
            <h2 className="mt-2 max-w-2xl text-3xl font-semibold tracking-tight md:text-4xl">{t("landing.journeyTitle")}</h2>
            <p className="mt-3 max-w-2xl text-lg text-muted">{t("landing.journeyBody")}</p>
            <ol className="relative mt-14 grid gap-8 md:grid-cols-5 md:gap-4">
              {/* Connecting line (desktop: horizontal, phone: vertical). */}
              <span aria-hidden className="absolute top-6 right-[10%] left-[10%] hidden h-0.5 bg-brand-soft md:block" />
              <span aria-hidden className="absolute top-2 bottom-2 left-6 w-0.5 bg-brand-soft md:hidden" />
              {JOURNEY.map(({ icon: Icon, key }, i) => (
                <li key={key} className="relative flex gap-4 md:flex-col md:items-center md:text-center">
                  <span className="relative inline-flex size-12 shrink-0 items-center justify-center rounded-2xl bg-surface text-brand shadow-card ring-1 ring-brand-soft">
                    <Icon aria-hidden className="size-5" />
                    <span className="tabular absolute -top-2 -right-2 inline-flex size-5 items-center justify-center rounded-full bg-ink text-[0.625rem] font-bold text-white">
                      {i + 1}
                    </span>
                  </span>
                  <div className="md:mt-4">
                    <h3 className="font-semibold text-ink">{t(`landing.journey.${key}.title`)}</h3>
                    <p className="mt-1 text-sm text-muted">{t(`landing.journey.${key}.body`)}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* Features (bento) */}
        <section id="features" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-20 md:px-8">
          <div className="max-w-2xl">
            <p className="text-sm font-semibold tracking-wide text-brand uppercase">{t("landing.featuresEyebrow")}</p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">{t("landing.featuresTitle")}</h2>
            <p className="mt-3 text-lg text-muted">{t("landing.featuresBody")}</p>
          </div>
          <ul className="mt-12 grid gap-4 md:grid-cols-3">
            {FEATURES.map(({ icon: Icon, key, wide }) => (
              <li
                key={key}
                className={cn(
                  "group rounded-card border border-line bg-surface p-6 shadow-card transition-[box-shadow,transform] duration-200 hover:-translate-y-0.5 hover:shadow-raised",
                  wide && "md:col-span-2",
                  key === "urgent" && "md:col-span-3 lg:col-span-1",
                )}
              >
                <span
                  className={cn(
                    "inline-flex size-11 items-center justify-center rounded-xl ring-1",
                    key === "urgent" ? "bg-urgent/8 text-urgent ring-urgent/15" : "bg-brand-tint text-brand ring-brand-soft",
                  )}
                >
                  <Icon aria-hidden className="size-5" />
                </span>
                <h3 className="mt-4 text-lg font-semibold">{t(`landing.feature.${key}.title`)}</h3>
                <p className="mt-1.5 text-muted">{t(`landing.feature.${key}.body`)}</p>
              </li>
            ))}
          </ul>
        </section>

        {/* Principles */}
        <section id="principles" className="scroll-mt-20 bg-brand-deep text-white">
          <div className="mx-auto max-w-6xl px-4 py-20 md:px-8">
            <div className="grid gap-10 lg:grid-cols-[1fr_2fr]">
              <div>
                <p className="text-sm font-semibold tracking-wide text-[#8fd6cf] uppercase">{t("landing.principlesEyebrow")}</p>
                <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">{t("landing.principlesTitle")}</h2>
                <p className="mt-3 text-white/70">{t("landing.principlesBody")}</p>
              </div>
              <ul className="grid gap-4 sm:grid-cols-2">
                {PRINCIPLES.map(({ icon: Icon, key }) => (
                  <li key={key} className="rounded-card border border-white/10 bg-white/[0.04] p-5">
                    <span className="inline-flex size-9 items-center justify-center rounded-lg bg-white/8 ring-1 ring-white/10">
                      <Icon aria-hidden className="size-4.5 text-[#8fd6cf]" />
                    </span>
                    <p className="mt-3 font-semibold">{t(`landing.principle.${key}.title`)}</p>
                    <p className="mt-1 text-sm text-white/70">{t(`landing.principle.${key}.body`)}</p>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        {/* Closing call to action */}
        <section className="mx-auto max-w-6xl px-4 py-20 md:px-8">
          <div className="flex flex-col items-start gap-6 rounded-[1.25rem] border border-line bg-surface p-8 shadow-card md:flex-row md:items-center md:justify-between md:p-10">
            <div>
              <h2 className="text-2xl font-semibold tracking-tight md:text-3xl">{t("landing.ctaTitle")}</h2>
              <p className="mt-2 text-muted">{t("landing.ctaBody")}</p>
            </div>
            <div className="flex w-full flex-col gap-3 sm:w-auto sm:flex-row">
              <Link
                to="/login"
                className="inline-flex min-h-12 items-center justify-center gap-2 rounded-control bg-brand px-5 font-semibold text-brand-ink hover:bg-brand-strong"
              >
                <LogIn aria-hidden className="size-4" />
                {t("landing.signIn")}
              </Link>
              <Link
                to="/urgent-help"
                className="inline-flex min-h-12 items-center justify-center gap-2 rounded-control border border-line px-5 font-semibold text-urgent hover:bg-urgent/5"
              >
                <Siren aria-hidden className="size-4" />
                {t("nav.urgentHelp")}
              </Link>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-8 text-sm text-faint sm:flex-row sm:items-center sm:justify-between md:px-8">
          <span className="flex items-center gap-2">
            <HeartPulse aria-hidden className="size-4 text-brand" />© {new Date().getFullYear()} {t("app.name")}
          </span>
          <span>{t("common.syntheticOnly")}</span>
        </div>
      </footer>
    </div>
  );
}
