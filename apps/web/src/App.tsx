import { QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation, useNavigate } from "react-router";
import { api, setSessionExpiredHandler, type Staff } from "./api/client";
import { AppShell } from "./components/AppShell";
import { EnvBanner } from "./components/EnvBanner";
import { PageState } from "./components/PageState";
import { Button } from "./components/ui/button";
import { ToastProvider } from "./components/ui/toast";
import { queryClient } from "./lib/queryClient";
import { BirthPlanPrint } from "./pages/BirthPlanPrint";
import { Overview } from "./pages/Overview";
import { LocalContacts } from "./pages/LocalContacts";
import { NextStep } from "./pages/NextStep";
import { UrgentHelp } from "./pages/UrgentHelp";
import { Login } from "./pages/Login";
import { MotherRegister } from "./pages/MotherRegister";
import { PregnancyView } from "./pages/PregnancyView";
import { Today } from "./pages/Today";
import { SessionContext, useSession, type SessionState } from "./state/session";

// Rarely-visited screens load on demand to keep the first download small on phones.
const Landing = lazy(() => import("./pages/Landing").then((m) => ({ default: m.Landing })));
const Messages = lazy(() => import("./pages/preview/Messages").then((m) => ({ default: m.Messages })));
const Children = lazy(() => import("./pages/preview/Children").then((m) => ({ default: m.Children })));
const Insights = lazy(() => import("./pages/preview/Insights").then((m) => ({ default: m.Insights })));
const Admin = lazy(() => import("./pages/admin/Admin").then((m) => ({ default: m.Admin })));
const Workload = lazy(() => import("./pages/Workload").then((m) => ({ default: m.Workload })));

function Lazy({ children }: { children: ReactNode }) {
  return <Suspense fallback={<PageState kind="loading" />}>{children}</Suspense>;
}

/** Old links used hash routing (#/episodes/<id>); send them to the real URL. */
function LegacyHashRedirect() {
  const navigate = useNavigate();
  useEffect(() => {
    const match = window.location.hash.match(/^#\/episodes\/([^/?#]+)/);
    if (match) navigate(`/episodes/${match[1]}`, { replace: true });
  }, [navigate]);
  return null;
}

function SessionRoot({ children }: { children: ReactNode }) {
  const [staff, setStaffState] = useState<Staff | null>(null);
  const [checkedSession, setCheckedSession] = useState(false);
  const [sessionEnded, setSessionEnded] = useState(false);
  const staffRef = useRef(staff);
  staffRef.current = staff;
  const signingOutRef = useRef(false);

  const setStaff = useCallback((next: Staff | null) => {
    setStaffState(next);
    if (next) setSessionEnded(false);
    // Signed-out (or a different user signing in): drop every cached record
    // so nothing from the previous session stays visible on a shared device.
    queryClient.clear();
  }, []);

  useEffect(() => {
    // Fires when the API client could not renew the session. Only tell the
    // user their session ended if they were actually signed in; the initial
    // "who am I?" check on a signed-out browser lands here too.
    setSessionExpiredHandler(() => {
      if (staffRef.current && !signingOutRef.current) {
        setSessionEnded(true);
        setStaff(null);
      }
    });
    return () => setSessionExpiredHandler(null);
  }, [setStaff]);

  useEffect(() => {
    // A reload keeps the httpOnly session cookie, so ask who (if anyone) is
    // signed in rather than assuming a signed-out state.
    api
      .me()
      .then(setStaffState)
      .catch(() => setStaffState(null))
      .finally(() => setCheckedSession(true));
  }, []);

  const signOut = useCallback(async () => {
    signingOutRef.current = true;
    await api.logout().catch(() => undefined);
    signingOutRef.current = false;
    setStaff(null);
  }, [setStaff]);

  const value = useMemo<SessionState>(
    () => ({ staff, setStaff, sessionEnded, signOut }),
    [staff, setStaff, sessionEnded, signOut],
  );

  if (!checkedSession) {
    return (
      <div className="mx-auto max-w-md px-4 py-10">
        <PageState kind="loading" />
      </div>
    );
  }
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

/** An organisation admin with no facility membership has no records to work
 * on (F004), so their home is the administration page. */
function HomeRoute() {
  const { staff } = useSession();
  if (staff && staff.memberships.length === 0 && (staff.admin_organizations?.length ?? 0) > 0) {
    return <Navigate to="/admin" replace />;
  }
  return <Overview />;
}

function RequireAuth({ children }: { children: ReactNode }) {
  const { staff } = useSession();
  const location = useLocation();
  // A signed-out visit to the home address shows the public page; any other
  // address goes to sign-in and comes back afterwards.
  if (!staff && location.pathname === "/") return <Navigate to="/welcome" replace />;
  if (!staff) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <>{children}</>;
}

function LoginRoute() {
  const { staff } = useSession();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from;
  if (staff) return <Navigate to={from && from !== "/login" ? from : "/"} replace />;
  return <Login />;
}

function NotFound() {
  const { t } = useTranslation();
  return (
    <div className="mx-auto max-w-md px-4 py-10">
      <PageState
        kind="not-found"
        action={
          <Button asChild variant="secondary">
            <Link to="/">{t("common.backToOverview")}</Link>
          </Button>
        }
      />
    </div>
  );
}


export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <BrowserRouter>
          <EnvBanner />
          <LegacyHashRedirect />
          <Routes>
            {/* Public and signed-out: never waits for the session check (F014). */}
            <Route path="/urgent-help" element={<UrgentHelp />} />
            <Route path="/urgent-help/:facilityId" element={<UrgentHelp />} />
            <Route path="/welcome" element={<Lazy><Landing /></Lazy>} />
            <Route
              path="*"
              element={
                <SessionRoot>
                  <Routes>
                    <Route path="/login" element={<LoginRoute />} />
                    <Route
                      element={
                        <RequireAuth>
                          <AppShell />
                        </RequireAuth>
                      }
                    >
                      <Route index element={<HomeRoute />} />
                      <Route path="today" element={<Today />} />
                      <Route path="workload" element={<Lazy><Workload /></Lazy>} />
                      <Route path="admin" element={<Lazy><Admin /></Lazy>} />
                      <Route path="mothers" element={<MotherRegister />} />
                      <Route path="contacts" element={<LocalContacts />} />
                      <Route path="episodes/:episodeId" element={<PregnancyView />} />
                      <Route path="episodes/:episodeId/next-step" element={<NextStep />} />
                      {/* Previews on sample data; each screen is labelled as such. */}
                      <Route path="messages" element={<Lazy><Messages /></Lazy>} />
                      <Route path="children" element={<Lazy><Children /></Lazy>} />
                      <Route path="insights" element={<Lazy><Insights /></Lazy>} />
                    </Route>
                    {/* Printable page: signed in, but without the app header. */}
                    <Route
                      path="/episodes/:episodeId/birth-plan/print"
                      element={
                        <RequireAuth>
                          <BirthPlanPrint />
                        </RequireAuth>
                      }
                    />
                    <Route path="*" element={<NotFound />} />
                  </Routes>
                </SessionRoot>
              }
            />
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </QueryClientProvider>
  );
}
