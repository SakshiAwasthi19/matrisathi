import { QueryClientProvider } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation, useNavigate } from "react-router";
import { api, setSessionExpiredHandler, type Staff } from "./api/client";
import { AppShell } from "./components/AppShell";
import { EnvBanner } from "./components/EnvBanner";
import { PageState } from "./components/PageState";
import { Button } from "./components/ui/button";
import { queryClient } from "./lib/queryClient";
import { Login } from "./pages/Login";
import { MotherRegister } from "./pages/MotherRegister";
import { PregnancyView } from "./pages/PregnancyView";
import { Today } from "./pages/Today";
import { SessionContext, useSession, type SessionState } from "./state/session";

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

function RequireAuth({ children }: { children: ReactNode }) {
  const { staff } = useSession();
  const location = useLocation();
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
            <Link to="/mothers">{t("common.backHome")}</Link>
          </Button>
        }
      />
    </div>
  );
}


export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <EnvBanner />
        <LegacyHashRedirect />
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
              <Route index element={<Today />} />
              <Route path="mothers" element={<MotherRegister />} />
              <Route path="episodes/:episodeId" element={<PregnancyView />} />
            </Route>
            <Route path="*" element={<NotFound />} />
          </Routes>
        </SessionRoot>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
