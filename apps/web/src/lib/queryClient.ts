import { QueryClient } from "@tanstack/react-query";

// api/client.ts already retries what is safe to retry (keyed creates after a
// network failure) and renews the session on 401. TanStack Query's own
// retries are switched off so nothing is retried twice over, and window-focus
// refetching is off to save data on weak connections.
export const queryClient = new QueryClient({
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
