// Set VITE_API_BASE in Vercel's project env vars for a deployed frontend —
// this must point at wherever the backend actually runs (it is never
// Vercel itself; see README "Deploying a staging environment").
const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api/v1";

/** Download link for a private file. The API checks the session and the
 * file's facility on every request; the link itself grants nothing. */
export function fileUrl(fileId: string): string {
  return `${API_BASE}/files/${fileId}`;
}

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

// --- Phase 1 care records (W2-A3) ---------------------------------------------

export type DatingPrecision = "EXACT" | "APPROXIMATE";
export type DatingEvidence = "SELF_REPORTED" | "CARD_OR_DOCUMENT" | "SCAN_REPORT" | "CLINICIAN_ASSESSMENT";

export interface Dating {
  id: string;
  lmp_date: string | null;
  edd: string | null;
  precision: DatingPrecision;
  evidence: DatingEvidence;
  state: "PROVISIONAL" | "CONFIRMED";
  recorded_by_name: string | null;
  confirmed_by_name: string | null;
  confirmed_at: string | null;
  superseded_at: string | null;
  created_at: string;
  version: number;
}

export interface DatingHistory {
  current: Dating | null;
  history: Dating[];
}

export interface DatingInput {
  lmp_date?: string | null;
  edd?: string | null;
  precision: DatingPrecision;
  evidence: DatingEvidence;
}

export interface TemplateItem {
  id: string;
  position: number;
  name: string;
  kind: string;
  timing_basis: string;
  offset_days: number | null;
  week_from: number | null;
  week_to: number | null;
  performer_role: string | null;
  preparation_text: string | null;
}

export interface CarePlanTemplate {
  id: string;
  name: string;
  version_label: string;
  is_placeholder: boolean;
  approved_by_name: string | null;
  approved_on: string | null;
  items: TemplateItem[];
}

export interface CarePlan {
  id: string;
  episode_id: string;
  template: CarePlanTemplate;
  status: string;
  published_by_name: string | null;
  published_at: string;
  version: number;
  unscheduled_item_names: string[];
}

export type AppointmentStatus = "REQUESTED" | "CONFIRMED" | "ATTENDED" | "MISSED" | "RESCHEDULED" | "CANCELLED";

export interface Appointment {
  id: string;
  episode_id: string;
  care_plan_id: string | null;
  name: string | null;
  status: AppointmentStatus;
  requested_for: string | null;
  confirmed_for: string | null;
  location_note: string | null;
  owner_staff_user_id: string | null;
  previous_appointment_id: string | null;
  status_reason: string | null;
  version: number;
}

export type TaskStatus = "NEW" | "ASSIGNED" | "AWAITING_PATIENT" | "COMPLETED" | "CANCELLED";
export type TaskOutcome = "DONE" | "DECLINED" | "UNREACHABLE" | "UNKNOWN" | "NOT_NEEDED";
export type Barrier = "TRAVEL" | "COST" | "MEDICINE_ACCESS" | "CHILDCARE" | "WORK" | "FAMILY" | "OTHER";
export type ClosureReason =
  | "DONE_AS_PLANNED"
  | "FAMILY_DECLINED"
  | "COULD_NOT_REACH"
  | "OUTCOME_UNKNOWN"
  | "NO_LONGER_NEEDED"
  | "DUPLICATE"
  | "RECORDED_IN_ERROR";

export interface CareTask {
  id: string;
  episode_id: string;
  mother_full_name: string;
  name: string | null;
  kind: string;
  status: TaskStatus;
  owner_staff_user_id: string | null;
  owner_name: string | null;
  backup_staff_user_id: string | null;
  due_at: string | null;
  overdue: boolean;
  source_appointment_id: string | null;
  last_attempt_at: string | null;
  barrier: string | null;
  outcome: string | null;
  closure_reason: string | null;
  closed_at: string | null;
  version: number;
}

const post = <T>(path: string, body: unknown) => request<T>(path, { method: "POST", body: JSON.stringify(body) });

export const careApi = {
  getDating: (episodeId: string) => request<DatingHistory>(`/pregnancy-episodes/${episodeId}/dating`),
  recordDating: (episodeId: string, input: DatingInput) =>
    post<Dating>(`/pregnancy-episodes/${episodeId}/dating`, input),
  confirmDating: (episodeId: string, datingId: string, expectedVersion: number) =>
    post<Dating>(`/pregnancy-episodes/${episodeId}/dating/confirm`, {
      dating_id: datingId,
      expected_version: expectedVersion,
    }),
  correctDating: (episodeId: string, input: DatingInput, expectedVersion: number) =>
    post<Dating>(`/pregnancy-episodes/${episodeId}/dating/correct`, { ...input, expected_version: expectedVersion }),

  listTemplates: () => request<CarePlanTemplate[]>("/care-plan-templates"),
  getCarePlan: (episodeId: string) => request<CarePlan | null>(`/pregnancy-episodes/${episodeId}/care-plan`),
  publishPlan: (episodeId: string, templateId: string) =>
    post<CarePlan>(`/pregnancy-episodes/${episodeId}/care-plan`, { template_id: templateId }),

  listAppointments: (episodeId: string) => request<Appointment[]>(`/pregnancy-episodes/${episodeId}/appointments`),
  transitionAppointment: (
    id: string,
    body: {
      to: "CONFIRMED" | "ATTENDED" | "MISSED" | "CANCELLED";
      expected_version: number;
      confirmed_for?: string;
      location_note?: string | null;
    },
  ) => post<Appointment>(`/appointments/${id}/transition`, body),
  rescheduleAppointment: (id: string, expectedVersion: number, requestedFor: string) =>
    post<{ previous: Appointment; new: Appointment }>(`/appointments/${id}/reschedule`, {
      expected_version: expectedVersion,
      requested_for: requestedFor,
    }),

  listTasks: (mine: boolean) => request<CareTask[]>(`/tasks?mine=${mine}`),
  listEpisodeTasks: (episodeId: string) => request<CareTask[]>(`/pregnancy-episodes/${episodeId}/tasks`),
  assignTask: (id: string, expectedVersion: number, ownerId: string) =>
    post<CareTask>(`/tasks/${id}/assign`, { expected_version: expectedVersion, owner_staff_user_id: ownerId }),
  recordAttempt: (id: string, expectedVersion: number, awaitingPatient: boolean, barrier: Barrier | null) =>
    post<CareTask>(`/tasks/${id}/attempt`, {
      expected_version: expectedVersion,
      awaiting_patient: awaitingPatient,
      barrier,
    }),
  closeTask: (id: string, expectedVersion: number, outcome: TaskOutcome, closureReason: ClosureReason) =>
    post<CareTask>(`/tasks/${id}/close`, {
      expected_version: expectedVersion,
      outcome,
      closure_reason: closureReason,
    }),
};

// --- Phase 1 records (W2-A4) -------------------------------------------------------

export interface FileObject {
  id: string;
  subject_person_id: string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  created_at: string;
}

export interface Investigation {
  id: string;
  episode_id: string;
  name: string;
  status: "REQUESTED" | "PERFORMED" | "RECEIVED" | "REVIEWED";
  requested_on: string | null;
  performed_on: string | null;
  received_at: string | null;
  source: string | null;
  file_id: string | null;
  reviewed_at: string | null;
  reviewed_by_name: string | null;
  version: number;
}

export type PrescriptionSource = "PAPER_PRESCRIPTION" | "MCP_CARD" | "DISCHARGE_SUMMARY" | "OTHER_DOCUMENT";

export interface Prescription {
  id: string;
  episode_id: string;
  source: PrescriptionSource;
  source_file_id: string | null;
  issued_on: string | null;
  recorded_by_name: string | null;
  instruction_status: "UNREVIEWED" | "CONFIRMED" | "UNCLEAR";
  confirmed_instruction: string | null;
  reviewed_by_name: string | null;
  reviewed_at: string | null;
  reminder_enabled: boolean;
  reminder_start: string | null;
  reminder_end: string | null;
  created_at: string;
  version: number;
}

export type ObservationSource = "MEASURED_HERE" | "OUTSIDE_RECORD" | "REPORTED_BY_FAMILY";
export type CorrectionReason = "TYPING_ERROR" | "WRONG_PERSON" | "WRONG_DATE" | "WRONG_UNIT" | "OTHER";

export interface Observation {
  id: string;
  episode_id: string;
  kind: "MEASUREMENT" | "CLINICIAN_FINDING";
  name: string;
  value_text: string;
  unit: string | null;
  observed_on: string | null;
  source: ObservationSource;
  recorded_by_name: string | null;
  corrects_id: string | null;
  correction_reason: CorrectionReason | null;
  superseded_at: string | null;
  created_at: string;
  version: number;
}

export interface ObservationInput {
  kind: "MEASUREMENT" | "CLINICIAN_FINDING";
  name: string;
  value_text: string;
  unit: string | null;
  observed_on: string | null;
  source: ObservationSource;
}

export type ServiceType = "PHC" | "REFERRAL_HOSPITAL" | "TRANSPORT" | "NUTRITION" | "BENEFITS" | "OTHER";

export interface LocalContact {
  id: string;
  facility_id: string;
  service_type: ServiceType;
  name: string;
  phone: string;
  alternate_phone: string | null;
  landmarks: string | null;
  availability_note: string | null;
  verified_by_name: string | null;
  verified_on: string;
  stale: boolean;
  version: number;
}

export type ReferralStatus = "SENT" | "CONTACTED" | "ATTENDED" | "ADVICE_RECEIVED" | "FOLLOW_UP_COMPLETED" | "CLOSED";
export type ReferralUrgency = "ROUTINE" | "SOON" | "URGENT";
export type ReferralClosureReason =
  | "FAMILY_DECLINED"
  | "NOT_ATTENDED_AFTER_FOLLOW_UP"
  | "CARE_TRANSFERRED_ELSEWHERE"
  | "NO_LONGER_NEEDED_PER_CLINICIAN"
  | "RECORDED_IN_ERROR";

export interface Referral {
  id: string;
  episode_id: string;
  destination_contact_id: string | null;
  destination_name: string | null;
  urgency: ReferralUrgency;
  clinician_instruction: string | null;
  referred_by_name: string | null;
  owner_staff_user_id: string;
  owner_name: string | null;
  status: ReferralStatus;
  contacted_at: string | null;
  attended_on: string | null;
  advice_received_at: string | null;
  advice_file_id: string | null;
  follow_up_completed_at: string | null;
  closure_reason: ReferralClosureReason | null;
  closed_at: string | null;
  created_at: string;
  version: number;
}

export const recordsApi = {
  uploadFile: (personId: string, file: File) =>
    request<FileObject>(
      `/files?subject_person_id=${encodeURIComponent(personId)}&filename=${encodeURIComponent(file.name)}`,
      { method: "POST", body: file, headers: { "Content-Type": file.type || "application/octet-stream" } },
    ),

  listInvestigations: (episodeId: string) => request<Investigation[]>(`/pregnancy-episodes/${episodeId}/investigations`),
  createInvestigation: (
    episodeId: string,
    body: { name: string; requested_on?: string | null; received_file_id?: string | null; source?: "ORDERED_HERE" | "OUTSIDE_REPORT" },
  ) => post<Investigation>(`/pregnancy-episodes/${episodeId}/investigations`, body),
  investigationStep: (id: string, step: "performed" | "received" | "reviewed", expectedVersion: number) =>
    post<Investigation>(`/investigations/${id}/${step}`, { expected_version: expectedVersion }),

  listPrescriptions: (episodeId: string) => request<Prescription[]>(`/pregnancy-episodes/${episodeId}/prescriptions`),
  recordPrescription: (
    episodeId: string,
    body: { source: PrescriptionSource; source_file_id?: string | null; issued_on?: string | null },
  ) => post<Prescription>(`/pregnancy-episodes/${episodeId}/prescriptions`, body),
  reviewPrescription: (
    id: string,
    body: {
      expected_version: number;
      decision: "CONFIRMED" | "UNCLEAR";
      confirmed_instruction?: string | null;
      reminder_enabled?: boolean;
      reminder_start?: string | null;
      reminder_end?: string | null;
    },
  ) => post<Prescription>(`/prescriptions/${id}/review`, body),

  listObservations: (episodeId: string, includeSuperseded: boolean) =>
    request<Observation[]>(`/pregnancy-episodes/${episodeId}/observations?include_superseded=${includeSuperseded}`),
  recordObservation: (episodeId: string, body: ObservationInput) =>
    post<Observation>(`/pregnancy-episodes/${episodeId}/observations`, body),
  correctObservation: (id: string, body: ObservationInput & { expected_version: number; correction_reason: CorrectionReason }) =>
    post<Observation>(`/observations/${id}/correct`, body),

  listContacts: (facilityId: string) => request<LocalContact[]>(`/local-contacts?facility_id=${encodeURIComponent(facilityId)}`),
  createContact: (body: {
    facility_id: string;
    service_type: ServiceType;
    name: string;
    phone: string;
    alternate_phone?: string | null;
    landmarks?: string | null;
    availability_note?: string | null;
  }) => post<LocalContact>("/local-contacts", body),
  verifyContact: (id: string, expectedVersion: number) =>
    post<LocalContact>(`/local-contacts/${id}/verify`, { expected_version: expectedVersion }),

  listReferrals: (episodeId: string) => request<Referral[]>(`/pregnancy-episodes/${episodeId}/referrals`),
  createReferral: (
    episodeId: string,
    body: {
      destination_contact_id?: string | null;
      destination_name?: string | null;
      urgency: ReferralUrgency;
      clinician_instruction?: string | null;
    },
  ) => post<Referral>(`/pregnancy-episodes/${episodeId}/referrals`, body),
  referralStep: (
    id: string,
    body: {
      expected_version: number;
      to: Exclude<ReferralStatus, "SENT">;
      attended_on?: string | null;
      advice_file_id?: string | null;
      closure_reason?: ReferralClosureReason | null;
    },
  ) => post<Referral>(`/referrals/${id}/step`, body),
};

// --- Next step, birth plan, public urgent help (W2-A5, W2-B3) ----------------------

export interface HelpContact {
  id: string;
  service_type: string;
  name: string;
  phone: string;
  alternate_phone: string | null;
  landmarks: string | null;
  verified_on: string;
  stale: boolean;
}

export type AppointmentFamilyReport = "DONE" | "COULD_NOT_GO" | "NEED_HELP";
export type FamilyReport = "DONE" | "NOT_DONE" | "NEED_HELP";

export interface NextAction {
  state: "CONFIRMED" | "NONE";
  appointment_id: string | null;
  name: string | null;
  confirmed_for: string | null;
  location_note: string | null;
  preparation_text: string | null;
  is_placeholder: boolean;
  family_report: AppointmentFamilyReport | null;
  family_reported_at: string | null;
  unconfirmed_requests: number;
  help_contacts: HelpContact[];
  version: number | null;
}

export interface BirthPlan {
  id: string;
  episode_id: string;
  chosen_birth_place: HelpContact | null;
  chosen_birth_place_note: string | null;
  referral_site: HelpContact | null;
  referral_site_set_by_name: string | null;
  companion_name: string | null;
  transport_arrangement: string | null;
  landmarks: string | null;
  primary_contact: HelpContact | null;
  alternate_contact: HelpContact | null;
  family_report: FamilyReport | null;
  family_reported_at: string | null;
  staff_verified_by_name: string | null;
  staff_verified_at: string | null;
  updated_at: string;
  version: number;
}

export interface BirthPlanInput {
  expected_version: number;
  chosen_birth_place_contact_id: string | null;
  chosen_birth_place_note: string | null;
  referral_site_contact_id: string | null;
  companion_name: string | null;
  transport_arrangement: string | null;
  landmarks: string | null;
  primary_contact_id: string | null;
  alternate_contact_id: string | null;
}

export interface UrgentHelp {
  facility_name: string;
  contacts: HelpContact[];
  support_hours: string | null;
  wording_approved: boolean;
}

export const nextStepApi = {
  getNextAction: (episodeId: string) => request<NextAction>(`/pregnancy-episodes/${episodeId}/next-action`),
  familyReport: (appointmentId: string, expectedVersion: number, report: AppointmentFamilyReport, barrier: Barrier | null) =>
    post<NextAction>(`/appointments/${appointmentId}/family-report`, {
      expected_version: expectedVersion,
      report,
      barrier,
    }),
  getBirthPlan: (episodeId: string) => request<BirthPlan | null>(`/pregnancy-episodes/${episodeId}/birth-plan`),
  saveBirthPlan: (episodeId: string, body: BirthPlanInput) =>
    request<BirthPlan>(`/pregnancy-episodes/${episodeId}/birth-plan`, { method: "PUT", body: JSON.stringify(body) }),
  verifyBirthPlan: (episodeId: string, expectedVersion: number) =>
    post<BirthPlan>(`/pregnancy-episodes/${episodeId}/birth-plan/verify`, { expected_version: expectedVersion }),
  birthPlanFamilyReport: (episodeId: string, expectedVersion: number, report: FamilyReport, barrier: Barrier | null) =>
    post<BirthPlan>(`/pregnancy-episodes/${episodeId}/birth-plan/family-report`, {
      expected_version: expectedVersion,
      report,
      barrier,
    }),
  // Public: no session needed.
  urgentHelp: (facilityId: string) => request<UrgentHelp>(`/public/urgent-help/${encodeURIComponent(facilityId)}`),
};

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
