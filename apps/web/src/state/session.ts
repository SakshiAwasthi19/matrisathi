import { createContext, useContext } from "react";
import type { Staff } from "../api/client";

export interface SessionState {
  staff: Staff | null;
  setStaff: (staff: Staff | null) => void;
  /** True after the session could not be renewed (show "Your session has ended"). */
  sessionEnded: boolean;
  signOut: () => Promise<void>;
}

export const SessionContext = createContext<SessionState | null>(null);

export function useSession(): SessionState {
  const ctx = useContext(SessionContext);
  if (!ctx) {
    throw new Error("useSession must be used within SessionContext.Provider");
  }
  return ctx;
}
