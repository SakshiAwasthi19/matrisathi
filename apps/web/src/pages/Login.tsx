import { useMutation } from "@tanstack/react-query";
import { Building2, CircleHelp, HeartPulse, LogIn, Smartphone, type LucideIcon } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { api, ApiError } from "../api/client";
import { Button } from "../components/ui/button";
import { Field, Input } from "../components/ui/field";
import { Alert } from "../components/ui/status";
import { useSession } from "../state/session";

// How the system behaves (product principles), not clinical claims.
const POINTS: { icon: LucideIcon; key: string }[] = [
  { icon: Smartphone, key: "login.pointSharedPhone" },
  { icon: CircleHelp, key: "login.pointUnknown" },
  { icon: Building2, key: "login.pointFacility" },
];

export function Login() {
  const { t } = useTranslation();
  const { setStaff, sessionEnded } = useSession();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const login = useMutation({
    mutationFn: () => api.login(username, password),
    meta: { silent: true },
    onSuccess: (staff) => setStaff(staff),
  });

  // The server's message is deliberately generic ("Invalid username or
  // password"), so it is safe to show as-is.
  const errorText = login.error
    ? login.error instanceof ApiError
      ? login.error.message
      : t("login.failed")
    : null;

  return (
    <div className="flex min-h-[calc(100dvh-2.5rem)] items-center justify-center px-4 py-6 md:py-12">
      <div className="grid w-full max-w-5xl animate-rise overflow-hidden rounded-2xl border border-line bg-surface shadow-pop md:grid-cols-[1.1fr_1fr]">
        {/* Brand panel: full on desktop, compact strip on phones. */}
        <div className="relative overflow-hidden bg-brand-deep px-6 py-8 text-brand-ink md:px-10 md:py-12">
          {/* Fine dot grid; purely decorative. */}
          <span
            aria-hidden
            className="pointer-events-none absolute inset-0 opacity-[0.07] [background-image:radial-gradient(white_1px,transparent_1px)] [background-size:18px_18px]"
          />
          <Link to="/welcome" className="relative flex w-fit items-center gap-3">
            <span className="inline-flex size-11 items-center justify-center rounded-xl bg-white/12 ring-1 ring-white/15">
              <HeartPulse aria-hidden className="size-6" />
            </span>
            <span className="text-2xl font-semibold">{t("app.name")}</span>
          </Link>
          <h1 className="relative mt-8 hidden text-3xl leading-tight font-semibold md:block">{t("login.heroTitle")}</h1>
          <p className="relative mt-3 hidden text-lg text-white/85 md:block">{t("login.heroBody")}</p>
          <ul className="relative mt-10 hidden space-y-5 md:block">
            {POINTS.map(({ icon: Icon, key }) => (
              <li key={key} className="flex items-start gap-3 text-base text-white/90">
                <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-full bg-white/10 ring-1 ring-white/15">
                  <Icon aria-hidden className="size-4" />
                </span>
                <span className="pt-1.5">{t(key)}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="flex flex-col justify-center px-6 py-8 md:px-10 md:py-12">
          <h2 className="text-2xl font-semibold tracking-tight">{t("login.title")}</h2>
          <p className="mt-1 text-base text-muted">{t("login.subtitle")}</p>
          {sessionEnded && (
            <Alert kind="info" className="mt-5">
              {t("login.sessionEnded")}
            </Alert>
          )}
          <form
            className="mt-6 space-y-5"
            onSubmit={(e) => {
              e.preventDefault();
              login.mutate();
            }}
          >
            <Field label={t("login.username")} htmlFor="username">
              <Input
                id="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                required
              />
            </Field>
            <Field label={t("login.password")} htmlFor="password">
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
              />
            </Field>
            {errorText && <Alert kind="problem">{errorText}</Alert>}
            <Button type="submit" className="w-full" disabled={login.isPending}>
              <LogIn aria-hidden className="size-4" />
              {login.isPending ? t("login.submitting") : t("login.submit")}
            </Button>
          </form>
          <p className="mt-6 text-center text-sm text-muted">
            <Link to="/welcome" className="font-semibold text-brand hover:text-brand-strong">
              {t("login.aboutLink")}
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
