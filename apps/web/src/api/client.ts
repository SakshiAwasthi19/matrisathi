// Set VITE_API_BASE in Vercel's project env vars for a deployed frontend —
// this must point at wherever the backend actually runs (it is never
// Vercel itself; see README "Deploying a staging environment").
const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api/v1";

// The auth session rides on httpOnly cookies (set by the API), never in
// localStorage or a JS-readable cookie — this frontend never touches the
// token value directly, it just needs `credentials: "include"` so the
// browser sends/receives those cookies on same-site cross-port requests.
const CSRF_HEADER_NAME = "X-MatriSathi-Client";
const CSRF_HEADER_VALUE = "web";

export class ApiError extends Error {
  status: number;
  /** The server's `detail`, kept as-is: a string, or an object for structured errors. */
  detail: unknown;
  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

/** The episode a 409 "already has an active episode" points at, if any. */
export function existingEpisodeId(err: unknown): string | null {
  if (!(err instanceof ApiError) || err.status !== 409) return null;
  const detail = err.detail as { existing_episode_id?: unknown } | null;
  return typeof detail?.existing_episode_id === "string" ? detail.existing_episode_id : null;
}

function detailMessage(detail: unknown, status: number): string {
  if (typeof detail === "string") return detail;
  const message = (detail as { message?: unknown } | null)?.message;
  return typeof message === "string" ? message : `Request failed (${status})`;
}

// A keyed create is safe to resend: the server returns the original record
// for a repeated Idempotency-Key instead of creating a second one. Only those
// requests are retried automatically after a network failure (the request may
// or may not have reached the server — on a weak connection we can't tell).
const NETWORK_RETRY_DELAYS_MS = [1000, 3000];

// Endpoints whose 401 means "bad credentials / no session", not "access token
// expired" — refreshing in response to these would be wrong or circular.
// Logout is deliberately absent: it needs a live access token, and an expired
// one must be renewed first or the refresh token would never get revoked.
const NO_REFRESH_PATHS = new Set(["/auth/login", "/auth/refresh"]);

let onSessionExpired: (() => void) | null = null;

/** Called once a refresh has failed, i.e. the user must sign in again. */
export function setSessionExpiredHandler(handler: (() => void) | null): void {
  onSessionExpired = handler;
}

interface RequestOptions extends RequestInit {
  idempotencyKey?: string;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function send(path: string, options: RequestOptions): Promise<Response> {
  const { idempotencyKey, ...init } = options;
  const method = (init.method ?? "GET").toUpperCase();
  const isMutating = method !== "GET";

  const doFetch = () =>
    fetch(`${API_BASE}${path}`, {
      ...init,
      method,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...(isMutating ? { [CSRF_HEADER_NAME]: CSRF_HEADER_VALUE } : {}),
        ...(idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {}),
        ...(init.headers ?? {}),
      },
    });

  if (!idempotencyKey) return doFetch();

  for (let attempt = 0; ; attempt++) {
    try {
      return await doFetch();
    } catch (err) {
      // fetch() only rejects on network failure; HTTP error statuses
      // resolve normally and are never retried here.
      if (attempt >= NETWORK_RETRY_DELAYS_MS.length) throw err;
      await sleep(NETWORK_RETRY_DELAYS_MS[attempt]);
    }
  }
}

// One refresh at a time. Within this tab, concurrent 401s share the same
// in-flight promise; across tabs, the Web Locks API serializes refreshes.
// Both matter because refresh tokens rotate on every use and the server
// treats a reused (already-rotated) token as theft, revoking every session
// for the user. Cookies are shared between tabs, so a tab that waited on the
// lock sends the freshly rotated token, not the stale one.
let refreshInFlight: Promise<boolean> | null = null;

function withRefreshLock<T>(fn: () => Promise<T>): Promise<T> {
  const locks = typeof navigator !== "undefined" ? navigator.locks : undefined;
  return locks ? (locks.request("matrisathi-refresh", fn) as Promise<T>) : fn();
}

/** Resolves true if the session was renewed, false if the server refused
 * (the user must sign in again). Rejects on a network failure, which says
 * nothing about whether the session is still valid. */
function refreshSession(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = withRefreshLock(async () => {
      const res = await send("/auth/refresh", { method: "POST" });
      return res.ok;
    }).finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let res = await send(path, options);

  if (res.status === 401 && !NO_REFRESH_PATHS.has(path)) {
    // The access token is short-lived; renew it and replay once. A 401 is
    // returned before any work is done server-side, so replaying a keyed
    // create with the same Idempotency-Key is safe.
    if (await refreshSession()) {
      res = await send(path, options);
    }
    if (res.status === 401) onSessionExpired?.();
  }

  if (res.status === 204) {
    return undefined as T;
  }

  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new ApiError(res.status, detailMessage(body.detail, res.status), body.detail);
  }
  return body as T;
}

export interface Membership {
  facility_id: string;
  facility_name: string;
  role: string;
}

export interface Staff {
  id: string;
  username: string;
  full_name: string;
  memberships: Membership[];
}

export type AgePrecision = "EXACT_DOB" | "YEAR_ONLY" | "APPROXIMATE_AGE" | "UNKNOWN";

export interface Person {
  id: string;
  full_name: string;
  age_precision: AgePrecision;
  date_of_birth: string | null;
  birth_year: number | null;
  reported_age_years: number | null;
  preferred_language: string | null;
  reported_medical_history: string | null;
  known_allergies_medicines: string | null;
  registering_facility_id: string;
  phone: string;
  contact_verified_at: string | null;
  contact_verified_by_name: string | null;
}

export interface PregnancyEpisode {
  id: string;
  mother_person_id: string;
  mother_full_name: string;
  facility_id: string;
  dating_estimate: string | null;
  dating_source: string;
  status: string;
  created_at: string;
}

export interface PersonCreateInput {
  full_name: string;
  facility_id: string;
  phone: string;
  age_precision?: AgePrecision;
  date_of_birth?: string | null;
  birth_year?: number | null;
  reported_age_years?: number | null;
  preferred_language?: string | null;
  reported_medical_history?: string | null;
  known_allergies_medicines?: string | null;
}

export const api = {
  login: (username: string, password: string) =>
    request<Staff>("/auth/login", { method: "POST", body: JSON.stringify({ username, password }) }),
  me: () => request<Staff>("/auth/me"),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  createPerson: (input: PersonCreateInput, idempotencyKey: string) =>
    request<Person>("/people", { method: "POST", body: JSON.stringify(input), idempotencyKey }),
  getPerson: (id: string) => request<Person>(`/people/${id}`),
  searchPeople: (params: { phone?: string; full_name?: string }) => {
    const q = new URLSearchParams();
    if (params.phone) q.set("phone", params.phone);
    if (params.full_name) q.set("full_name", params.full_name);
    return request<Person[]>(`/people?${q.toString()}`);
  },
  verifyContact: (personId: string) =>
    request<Person>(`/people/${personId}/contact/verify`, { method: "POST" }),
  createPregnancyEpisode: (personId: string, idempotencyKey: string) =>
    request<PregnancyEpisode>("/pregnancy-episodes", {
      method: "POST",
      body: JSON.stringify({ person_id: personId }),
      idempotencyKey,
    }),
  getPregnancyEpisode: (id: string) => request<PregnancyEpisode>(`/pregnancy-episodes/${id}`),
  listEpisodes: (personId: string) => request<PregnancyEpisode[]>(`/people/${personId}/episodes`),
};
