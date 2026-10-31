import { useEffect, useRef, useState } from "react";
import { api, setSessionExpiredHandler, type Staff } from "./api/client";
import { Login } from "./pages/Login";
import { MotherRegister } from "./pages/MotherRegister";
import { PregnancyView } from "./pages/PregnancyView";
import { SessionContext } from "./state/session";

function useHashRoute(): string {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {
    const onChange = () => setHash(window.location.hash);
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return hash;
}

function AppShell() {
  const [staff, setStaffState] = useState<Staff | null>(null);
  const [checkedSession, setCheckedSession] = useState(false);
  const [sessionEnded, setSessionEnded] = useState(false);
  const hash = useHashRoute();
  const staffRef = useRef(staff);
  staffRef.current = staff;
  const loggingOutRef = useRef(false);

  useEffect(() => {
    // Fires when the API client could not renew the session. Only tell the
    // user their session ended if they were actually signed in — the initial
    // "who am I?" check on a logged-out browser lands here too.
    setSessionExpiredHandler(() => {
      if (staffRef.current && !loggingOutRef.current) {
        setSessionEnded(true);
        setStaff(null);
      }
    });
    return () => setSessionExpiredHandler(null);
  }, []);

  useEffect(() => {
    // A reload keeps the httpOnly session cookie, so re-check who (if
    // anyone) is signed in rather than assuming a fresh, logged-out state.
    api
      .me()
      .then(setStaffState)
      .catch(() => setStaffState(null))
      .finally(() => setCheckedSession(true));
  }, []);

  function setStaff(next: Staff | null) {
    setStaffState(next);
    if (next) setSessionEnded(false);
    if (!next) window.location.hash = "";
  }

  async function handleLogout() {
    loggingOutRef.current = true;
    await api.logout().catch(() => undefined);
    loggingOutRef.current = false;
    setStaff(null);
  }

  if (!checkedSession) return <p style={{ fontFamily: "sans-serif" }}>Loading...</p>;

  return (
    <SessionContext.Provider value={{ staff, setStaff }}>
      <div style={{ padding: "2rem" }}>
        {staff ? (
          <>
            <header style={{ marginBottom: 24, fontFamily: "sans-serif" }}>
              Signed in as <strong>{staff.full_name}</strong> ({staff.username}){" "}
              <button onClick={handleLogout}>Log out</button>
              {" | "}
              <a href="#">Find / register mother</a>
            </header>
            {hash.startsWith("#/episodes/") ? (
              <PregnancyView episodeId={hash.replace("#/episodes/", "")} />
            ) : (
              <MotherRegister onEpisodeCreated={(id) => (window.location.hash = `#/episodes/${id}`)} />
            )}
          </>
        ) : (
          <Login notice={sessionEnded ? "Your session has ended. Please sign in again." : null} />
        )}
      </div>
    </SessionContext.Provider>
  );
}

export function App() {
  return <AppShell />;
}
