import { MutationCache, QueryClient } from "@tanstack/react-query";
import { notify } from "../components/ui/toast";
import i18n from "../i18n";

declare module "@tanstack/react-query" {
  interface Register {
    mutationMeta: { silent?: boolean; toast?: string };
  }
}

// api/client.ts already retries what is safe to retry (keyed creates after a
// network failure) and renews the session on 401. TanStack Query's own
// retries are switched off so nothing is retried twice over, and window-focus
// refetching is off to save data on weak connections.
// Every successful change shows a brief "Saved" confirmation. Mutations that
// only read (sign-in, search) set `meta: { silent: true }`.
export const queryClient = new QueryClient({
  mutationCache: new MutationCache({
    onSuccess: (_data, _vars, _ctx, mutation) => {
      if (mutation.meta?.silent) return;
      notify(mutation.meta?.toast ?? i18n.t("toast.saved"));
    },
  }),
  defaultOptions: {
    queries: {
      retry: false,
      refetchOnWindowFocus: false,
      staleTime: 30_000,
    },
    mutations: {
      retry: false,
    },
  },
});
