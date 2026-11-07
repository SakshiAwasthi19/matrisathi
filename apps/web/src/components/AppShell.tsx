import { HeartPulse, LogOut, Menu, MoreHorizontal, Search, Siren, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router";
import { navItemsFor, rolesOf, type NavGroup, type NavItem } from "../lib/nav";
import { cn } from "../lib/utils";
import { useSession } from "../state/session";
import { Avatar } from "./Avatar";

const GROUPS: NavGroup[] = ["work", "network", "preview"];

function Brand() {
  const { t } = useTranslation();
  return (
    <Link to="/" className="flex items-center gap-2.5 rounded-lg outline-offset-4">
      <span className="inline-flex size-9 items-center justify-center rounded-[10px] bg-brand text-brand-ink shadow-[inset_0_1px_0_rgb(255_255_255/0.15)]">
        <HeartPulse aria-hidden className="size-5" />
      </span>
      <span className="leading-tight">
        <span className="block text-[1.05rem] font-semibold tracking-tight text-ink">{t("app.name")}</span>
        <span className="block text-xs text-muted">{t("app.tagline")}</span>
      </span>
    </Link>
  );
}

function NavRow({ item, onNavigate }: { item: NavItem; onNavigate?: () => void }) {
  const { t } = useTranslation();
  const Icon = item.icon;
  return (
    <NavLink
      to={item.to}
      end={item.to === "/"}
      onClick={onNavigate}
      className={({ isActive }) =>
        cn(
          "group flex min-h-12 items-center gap-3 rounded-[10px] px-3 text-[0.95rem] font-medium transition-colors lg:min-h-10",
          isActive ? "bg-brand-tint text-brand-strong" : "text-ink-2 hover:bg-subtle hover:text-ink",
        )
      }
    >
      {({ isActive }) => (
        <>
          <Icon aria-hidden className={cn("size-[18px] shrink-0", isActive ? "text-brand" : "text-faint group-hover:text-muted")} />
          <span className="flex-1 truncate">{t(item.labelKey)}</span>
          {item.preview && (
            <span className="rounded-full bg-accent-soft px-1.5 py-px text-[0.6875rem] font-semibold text-accent">
              {t("nav.previewTag")}
            </span>
          )}
        </>
      )}
    </NavLink>
  );
}

/** Sidebar contents, shared by the desktop rail and the phone drawer. */
function SidebarBody({ items, onNavigate }: { items: NavItem[]; onNavigate?: () => void }) {
  const { t } = useTranslation();
  const { staff, signOut } = useSession();
  const [signingOut, setSigningOut] = useState(false);
  const facilityId = staff?.memberships[0]?.facility_id;
  const facilityName = staff?.memberships[0]?.facility_name;
  const role = staff?.memberships[0]?.role;

  return (
    <div className="flex h-full flex-col">
      {facilityName && (
        <div className="mx-3 mb-4 rounded-xl border border-line bg-page px-3 py-2.5">
          <p className="text-[0.6875rem] font-semibold tracking-wide text-faint uppercase">{t("nav.facility")}</p>
          <p className="truncate text-sm font-semibold text-ink">{facilityName}</p>
        </div>
      )}
      <nav aria-label={t("nav.label")} className="flex-1 space-y-5 overflow-y-auto px-3">
        {GROUPS.map((group) => {
          const groupItems = items.filter((i) => i.group === group);
          if (groupItems.length === 0) return null;
          return (
            <div key={group}>
              <p className="mb-1.5 px-3 text-[0.6875rem] font-semibold tracking-wide text-faint uppercase">
                {t(`nav.group.${group}`)}
              </p>
              <ul className="space-y-0.5">
                {groupItems.map((item) => (
                  <li key={item.to}>
                    <NavRow item={item} onNavigate={onNavigate} />
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </nav>
      <div className="space-y-3 border-t border-line p-3">
        {facilityId && (
          <Link
            to={`/urgent-help/${facilityId}`}
            className="flex min-h-12 items-center gap-3 rounded-[10px] px-3 text-[0.95rem] font-semibold text-urgent hover:bg-urgent/8 lg:min-h-10"
          >
            <Siren aria-hidden className="size-[18px]" />
            {t("nav.urgentHelp")}
          </Link>
        )}
        {staff && (
          <div className="flex items-center gap-3 rounded-xl px-2 py-1.5">
            <Avatar name={staff.full_name} size="sm" />
            <div className="min-w-0 flex-1 leading-tight">
              <p className="truncate text-sm font-semibold text-ink">{staff.full_name}</p>
              {role && <p className="truncate text-xs text-muted">{t(`nav.role.${role}`, { defaultValue: role })}</p>}
            </div>
            <button
              type="button"
              disabled={signingOut}
              aria-label={signingOut ? t("nav.signingOut") : t("nav.signOut")}
              title={t("nav.signOut")}
              onClick={async () => {
                setSigningOut(true);
                try {
                  await signOut();
                } finally {
                  setSigningOut(false);
                }
              }}
              className="inline-flex size-10 items-center justify-center rounded-lg text-muted transition-colors hover:bg-subtle hover:text-ink disabled:opacity-50"
            >
              <LogOut aria-hidden className="size-4" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

/** Search from any page. The text travels in router state, never in the URL,
 * so phone numbers and names stay out of browser history. */
function QuickFind({ className }: { className?: string }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  return (
    <form
      role="search"
      onSubmit={(e) => {
        e.preventDefault();
        if (!q.trim()) return;
        navigate("/mothers", { state: { quickFind: q.trim() } });
        setQ("");
      }}
      className={cn(
        "flex min-h-10 w-full max-w-sm items-center gap-2.5 rounded-[10px] border border-line bg-surface px-3 shadow-card transition-colors focus-within:border-brand focus-within:ring-2 focus-within:ring-brand-soft hover:border-line-strong",
        className,
      )}
    >
      <Search aria-hidden className="size-4 shrink-0 text-faint" />
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        aria-label={t("nav.quickFindLabel")}
        placeholder={t("nav.quickFind")}
        autoComplete="off"
        className="min-w-0 flex-1 bg-transparent py-2 text-sm text-ink outline-none placeholder:text-faint"
      />
      <kbd className="hidden rounded border border-line bg-subtle px-1.5 text-[0.6875rem] font-semibold text-faint xl:inline">{t("nav.enterKey")}</kbd>
    </form>
  );
}

/** Sidebar navigation (desktop), drawer + bottom tabs (phones), around every signed-in page. */
export function AppShell() {
  const { t } = useTranslation();
  const { staff } = useSession();
  const location = useLocation();
  const [drawer, setDrawer] = useState(false);
  const items = navItemsFor(rolesOf(staff?.memberships ?? []));
  const bottom = items.filter((i) => ["/", "/today", "/mothers"].includes(i.to));

  // Close the drawer on navigation and on Escape.
  useEffect(() => setDrawer(false), [location.pathname]);
  useEffect(() => {
    if (!drawer) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setDrawer(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawer]);

  return (
    <div className="flex min-h-full">
      <a href="#main" className="sr-only z-50 rounded-md bg-surface px-3 py-2 focus:not-sr-only focus:fixed focus:top-2 focus:left-2">
        {t("nav.skip")}
      </a>

      {/* Desktop sidebar */}
      <aside className="hidden w-64 shrink-0 border-r border-line bg-surface lg:block print:hidden">
        <div className="sticky top-0 flex h-dvh flex-col">
          <div className="px-5 pt-5 pb-5">
            <Brand />
          </div>
          <SidebarBody items={items} />
        </div>
      </aside>

      {/* Phone / tablet drawer */}
      {drawer && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label={t("nav.label")}>
          <button type="button" aria-label={t("nav.close")} className="absolute inset-0 animate-fade-in bg-ink/30" onClick={() => setDrawer(false)} />
          <div className="absolute inset-y-0 left-0 flex w-[min(20rem,85vw)] animate-slide-in flex-col bg-surface shadow-pop">
            <div className="flex items-center justify-between px-5 pt-5 pb-5">
              <Brand />
              <button
                type="button"
                aria-label={t("nav.close")}
                onClick={() => setDrawer(false)}
                className="inline-flex size-11 items-center justify-center rounded-lg text-muted hover:bg-subtle"
              >
                <X aria-hidden className="size-5" />
              </button>
            </div>
            <SidebarBody items={items} onNavigate={() => setDrawer(false)} />
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Top bar */}
        <div className="sticky top-0 z-30 border-b border-line/80 bg-page/90 backdrop-blur-md print:hidden">
          <div className="mx-auto flex h-16 max-w-6xl items-center gap-3 px-4 md:px-8">
            <button
              type="button"
              aria-label={t("nav.open")}
              onClick={() => setDrawer(true)}
              className="-ml-2 inline-flex size-11 items-center justify-center rounded-lg text-ink-2 hover:bg-subtle lg:hidden"
            >
              <Menu aria-hidden className="size-5" />
            </button>
            <div className="lg:hidden">
              <Link to="/" className="flex items-center gap-2 font-semibold tracking-tight">
                <span className="inline-flex size-8 items-center justify-center rounded-lg bg-brand text-brand-ink">
                  <HeartPulse aria-hidden className="size-4" />
                </span>
                <span className="hidden sm:inline">{t("app.name")}</span>
              </Link>
            </div>
            <QuickFind className="ml-auto hidden md:flex lg:ml-0" />
            <Link
              to="/mothers"
              aria-label={t("nav.quickFind")}
              className="ml-auto inline-flex size-11 items-center justify-center rounded-lg text-ink-2 hover:bg-subtle md:hidden"
            >
              <Search aria-hidden className="size-5" />
            </Link>
          </div>
        </div>

        <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 pt-6 pb-28 md:px-8 md:pt-8 lg:pb-12">
          <div key={location.pathname} className="animate-fade-in">
            <Outlet />
          </div>
        </main>
      </div>

      {/* Phone bottom tabs */}
      <nav
        aria-label={t("nav.bottom")}
        className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-surface/95 pb-[env(safe-area-inset-bottom)] backdrop-blur-md lg:hidden print:hidden"
      >
        <ul className="mx-auto grid max-w-md grid-cols-4">
          {bottom.map((item) => {
            const Icon = item.icon;
            return (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={item.to === "/"}
                  className={({ isActive }) =>
                    cn(
                      "flex min-h-16 flex-col items-center justify-center gap-1 text-xs font-semibold",
                      isActive ? "text-brand" : "text-muted",
                    )
                  }
                >
                  <Icon aria-hidden className="size-5" />
                  {t(item.labelKey)}
                </NavLink>
              </li>
            );
          })}
          <li>
            <button
              type="button"
              onClick={() => setDrawer(true)}
              className="flex min-h-16 w-full flex-col items-center justify-center gap-1 text-xs font-semibold text-muted"
            >
              <MoreHorizontal aria-hidden className="size-5" />
              {t("nav.more")}
            </button>
          </li>
        </ul>
      </nav>
    </div>
  );
}
