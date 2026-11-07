import { HeartPulse, LogOut } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { NavLink, Outlet } from "react-router";
import { navItemsFor, rolesOf } from "../lib/nav";
import { cn } from "../lib/utils";
import { useSession } from "../state/session";
import { Avatar } from "./Avatar";
import { Button } from "./ui/button";

/** Header, role-aware navigation and sign-out around every signed-in page. */
export function AppShell() {
  const { t } = useTranslation();
  const { staff, signOut } = useSession();
  const [signingOut, setSigningOut] = useState(false);
  const items = navItemsFor(rolesOf(staff?.memberships ?? []));

  async function handleSignOut() {
    setSigningOut(true);
    try {
      await signOut();
    } finally {
      setSigningOut(false);
    }
  }

  return (
    <div className="min-h-full">
      <header className="sticky top-0 z-10 border-b border-line/70 bg-surface/95 shadow-card backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <div className="flex items-center gap-2.5">
            <span className="inline-flex size-9 items-center justify-center rounded-lg bg-brand text-brand-ink">
              <HeartPulse aria-hidden className="size-5" />
            </span>
            <span className="leading-tight">
              <span className="block text-lg font-semibold">{t("app.name")}</span>
              <span className="hidden text-xs text-muted sm:block">{t("app.tagline")}</span>
            </span>
          </div>
          <nav aria-label={t("nav.label")} className="order-3 w-full sm:order-0 sm:w-auto">
            <ul className="flex flex-wrap gap-1">
              {items.map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    end
                    className={({ isActive }) =>
                      cn(
                        "inline-flex min-h-12 items-center rounded-md px-3 font-semibold md:min-h-10",
                        isActive ? "bg-subtle text-brand" : "text-ink hover:bg-subtle",
                      )
                    }
                  >
                    {t(item.labelKey)}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
          <div className="ml-auto flex items-center gap-2">
            {staff && (
              <span className="hidden items-center gap-2 text-sm text-muted md:inline-flex">
                <Avatar name={staff.full_name} />
                {t("nav.signedInAs", { name: staff.full_name })}
              </span>
            )}
            <Button variant="ghost" onClick={handleSignOut} disabled={signingOut}>
              <LogOut aria-hidden className="size-4" />
              {signingOut ? t("nav.signingOut") : t("nav.signOut")}
            </Button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6 md:py-8">
        <Outlet />
      </main>
    </div>
  );
}
