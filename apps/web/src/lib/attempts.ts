// Stable Idempotency-Key per logical create attempt. Resubmitting the same
// payload reuses its key, so the server hands back the record it already
// created instead of making a duplicate (e.g. the response was lost on a weak
// connection). An edited payload gets a fresh key, because the server rejects
// a reused key sent with a different body (409).
//
// Kept in memory only: a full page reload starts a new attempt.

export type AttemptStore = Map<string, { payload: string; key: string }>;

export function createAttemptStore(): AttemptStore {
  return new Map();
}

function newKey(): string {
  // randomUUID only exists in secure contexts (https, localhost); a dev
  // server opened over plain-http LAN still needs a key.
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

export function attemptKey(store: AttemptStore, scope: string, payload: unknown): string {
  const serialized = JSON.stringify(payload);
  const existing = store.get(scope);
  if (existing && existing.payload === serialized) return existing.key;
  const key = newKey();
  store.set(scope, { payload: serialized, key });
  return key;
}

export function clearAttempt(store: AttemptStore, scope: string): void {
  store.delete(scope);
}
