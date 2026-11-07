import { CheckCircle2, X } from "lucide-react";
import * as React from "react";

type Toast = { id: number; message: string };
const ToastContext = React.createContext<(message: string) => void>(() => undefined);

// Lets code outside React (the query client) raise a toast.
const listeners = new Set<(message: string) => void>();
export function notify(message: string): void {
  listeners.forEach((l) => l(message));
}

/** Brief "Saved" style confirmations after an action succeeds. Announced to
 * screen readers through a polite live region. */
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = React.useState<Toast[]>([]);
  const push = React.useCallback((message: string) => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t.slice(-2), { id, message }]);
    window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3200);
  }, []);
  React.useEffect(() => {
    listeners.add(push);
    return () => {
      listeners.delete(push);
    };
  }, [push]);
  return (
    <ToastContext.Provider value={push}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-20 z-50 flex flex-col items-center gap-2 px-4 md:bottom-6 md:items-end md:pr-6 print:hidden">
        {toasts.map((t) => (
          <div
            key={t.id}
            className="pointer-events-auto flex animate-rise items-center gap-3 rounded-xl bg-ink px-4 py-3 text-sm font-medium text-white shadow-pop"
          >
            <CheckCircle2 aria-hidden className="size-4 text-[#7fd3b0]" />
            {t.message}
            <button
              type="button"
              aria-label="Dismiss"
              className="-mr-1 rounded p-1 text-white/70 hover:text-white"
              onClick={() => setToasts((all) => all.filter((x) => x.id !== t.id))}
            >
              <X aria-hidden className="size-3.5" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  return React.useContext(ToastContext);
}
