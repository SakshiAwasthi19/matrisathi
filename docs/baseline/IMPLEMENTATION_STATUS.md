# Implementation status — baseline 2026-11-02 (`39059e9`)

**Source of IDs:** `docs/specifications/MatriSathi_Stage_Gate_Task_Tracker_with_FS_and_TS.xlsx` (Tasks, Acceptance,
Decisions, Functional Specs, Technical Specs).

**Status vocabulary:**
- **IMPL+VERIFIED** — implemented and verified by tests, CI and live/browser runs in this baseline.
- **IMPL-UNVERIFIED** — implemented but not verified.
- **PARTIAL** — partially implemented.
- **NOT IMPL** — not implemented.
- **BLOCKED** — blocked by a dependency.
- **NEEDS REVIEW** — requires review or approval.

No item is reviewer-accepted. In the tracker, every "Actual reviewer" cell is empty and every "Review result" says Pending.

## SG0 — Kickoff and working agreement

| Task | Requirement | Status | Files / evidence | Known issues | Dependencies | Next action |
|---|---|---|---|---|---|---|
| M001 / F001 | Baseline, capacity, pilot sites, language, reviewers | **NEEDS REVIEW** (not started) | — | D01, D02 open | Team lead | Record D01/D02 |
| M002 / T001 | Shared repo + engineering agreement | **PARTIAL** | Remote exists, CI exists, `.gitignore` excludes `.env`, `.claude/settings.json` asks before commit/push | Commits go straight to `main`; protected-main policy not evidenced; repo is public | D03 | Team lead decides D03; repo admin enables protection |
| T001 | Architecture: React/Vite/TS + FastAPI + PostgreSQL/Alembic | **IMPL+VERIFIED** (stack) / **NEEDS REVIEW** (adoption) | Whole repo | Object storage and durable worker not started (needed SG2/SG3); R09/G15 amendment not applied to the workbook | D01 D03 D04 | Tech lead records the stack decision |

## SG1 — Independent foundation

| Task | Requirement | Status | Relevant files | Test coverage | Known issues | Next action |
|---|---|---|---|---|---|---|
| M003 | Tech-lead review of identity/auth/tenant/audit design | **NEEDS REVIEW** | `docs/delivery/evidence/SG1/report.md` §9 | — | Not started | Tech lead review, using this baseline |
| M004 / T003 | Scaffold API, DB, first migrations (Org/Facility/Membership/Person/Contact/Episode) | **IMPL+VERIFIED** | `apps/api/app/models/*`, `alembic/versions/*` | Empty-DB upgrade + `alembic check` (local + CI) | No `version` columns (T003); no DB check constraints for age exclusivity; "Session" entity is named `refresh_token` | Accept; add `version` with SG2's first update endpoint |
| M005 / T004 | Staff login, refresh, logout, expiry, disable, replay | **IMPL+VERIFIED** | `routers/auth.py`, `core/security.py`, `core/deps.py` | `test_auth.py` (12), live probe, browser | O4: username-only throttle lets anyone lock an account; PyJWT 2.9.0 advisories | D04 approval; decide on throttling and upgrades |
| M005 / T005 | Facility/org authorization on every read/write/search/link; separate DB roles | **IMPL+VERIFIED** (facility scope) / **PARTIAL** (roles) | `core/deps.py`, all routers, `0002_app_role_grants.py` | `test_access_isolation`, `test_org_admin`, `test_admin_membership`, `test_person_pregnancy_authz`, live probe | Role capabilities not enforced; O5 admin self-grant; O6 cross-org staff grant; inactive facility still readable | Decisions on O5/O6; central policy layer before SG2 |
| M005 / T006 | Audit of success/denial; runtime can't alter; safe diagnostics | **PARTIAL** | `services/audit_service.py`, `models/audit.py` | `test_audit.py` (4), live DB-role check | O2: SQL params (patient phone) logged on DB errors; O9: `verify_contact` denials not audited; no request ID / reason field; audit not atomic with the business commit | Fix log redaction + O9 (small, needs approval) |
| M005 / T002 | `/api/v1`, OpenAPI, consistent errors, bounded queries, operation IDs, entity version | **PARTIAL** | `main.py`, routers | `test_idempotency_concurrency.py` (5) | 500s on malformed IDs/lengths (O1); no input range/format validation (O3); search capped at 50 rather than paginated; no version on updates (no updates exist yet) | Validation and error-contract hardening |
| M005 / F037 (early part) | Audit foundation | see T006 | | | | |
| M006 / F002 | Find or create person; intake with age precision; history/allergies; create episode; reopen after reload | **PARTIAL** | `routers/people.py`, `routers/pregnancies.py`, `web/src/pages/*` | `test_person_search_and_intake.py` (11), browser run | **The UI captures no dating** (the API accepts `dating_estimate`/`dating_source`), so "register early, late and unknown-date cases" can't be demonstrated in the UI; no "source" field; can't reopen an existing episode from search; multiple ACTIVE episodes per mother | Decide the episode model + dating semantics; then add UI |
| M006 / F003 | Contact separate from identity; confirm who a contact belongs to; safe preferences; duplicate review; number change | **PARTIAL** | `models/identity.py`, `verify_contact` | `test_shared_phone.py`, search tests, browser | Safe preferences deferred to SG3 (F016); changing a number not built (needs a decision); phone not normalized, so "98…" and "+91 98…" won't match | Decide the phone format + contact-change design |
| F004 | Staff roles and assigned records | **PARTIAL** | `admin.py`, `StaffRole` | admin/org tests | No role differences; no assignment concept; admin UI absent (API only); no org-creation API | Needs M008 (doctor) role limits before building |
| M006 / T007 | Locked installs, setup docs, PG-backed tests, lint/type/tests, browser smoke, empty-DB migration, secret/dep checks, CI | **PARTIAL** | `ci.yml`, `uv.lock`, `package-lock.json`, README | CI green at `39059e9` | No frontend lint; no browser smoke in CI; no secret or dependency scanning; CI runs only on Linux | Add the missing CI steps (new dev deps need approval) |
| M006 / AT05 | Repeatable foundation | **IMPL+VERIFIED (technical)** / **NEEDS REVIEW** | `BASELINE_TEST_REPORT.md` §5 | Fresh clone + CI run 41196159598 | Tracker still says Blocked | Tester/Tech lead accepts, then updates the tracker |
| M007 | Reviewer, language and messaging onboarding | **NOT IMPL** (human task) | — | — | — | Team lead; D06 lead time |
| M008 | Doctor validates intake, roles, journey coverage | **NEEDS REVIEW** (not started) | Intake fields in `models/identity.py` | — | Medical history/allergies fields are unreviewed | Doctor review |

**SG1 gate:** **not passed.** Technically SG1 is close: AT01–AT05 evidence is now available, including CI. It is
still missing M003, M008, D01–D04, reviewer sign-offs, and the hardening items O1–O4 and O9–O10.

## SG2 — Pregnancy care and next actions (Week 2 in the restart plan)

| Task | Scope (F/T) | Status | Blockers / dependencies |
|---|---|---|---|
| M009 | Plan/task state + private media design review (T002 T008 T009) | NOT IMPL | M003; tech lead + doctor |
| M010 | Patient/caregiver access mechanism (F015, T010) | NOT IMPL | **D07 (blocking)** |
| M011 | Dating, ANC plan, appointments, owned tasks (F005–F008, T008) | NOT IMPL | M009; **D05 approved ANC template**; episode-model decision |
| M012 | Reports, prescriptions, observations, referrals, local contacts (F009–F012, F044, T009) | NOT IMPL | M009; object storage decision (new infra); doctor approval of fields |
| M013 | Patient next-action, birth plan, public urgent help, caregiver access (F006, F013–F015) | NOT IMPL | M010/D07; doctor-approved urgent wording |
| M014 | Channel approval + clinical content prep | NOT IMPL | D06 |
| M015 | Doctor approves ANC template and urgent wording | NOT IMPL | D05 |
| M016 | Tester: AT01–AT10, AT28 | NOT IMPL | M013 |

## SG3 — WhatsApp and voice (M017–M024; F016–F020; T011–T013)

All **NOT IMPL**. **BLOCKED** by D06 (provider, account, budget), D08 (language narrator), M014 template approval,
and staff test numbers (M007). Needs new infrastructure: a durable outbox/worker (T012) and private media storage
(T009).

## SG4 — Birth and early postpartum (M025–M032; F021–F028; T014–T015)

All **NOT IMPL**. Depends on: the pediatric reviewer (D02), the M025 data-integrity review, and the SG3 messaging
pause (for AT17). There's no Child, relationship or event schema yet.

## SG5 — Complete MVP (M033–M048; F029–F040; T016–T020)

All **NOT IMPL**. Depends on: D07 (guardian access), D09 (hosting/retention), D10 (thresholds/budget), the content
approvals (12 packages), and the offline device policy (M033). F040/AT31 (AI-disabled behavior) is trivially true
today because there's no AI. It needs re-verifying once optional services exist.

## SG6 — Field validation and resilience (M049–M055; F041–F042; T021–T022)

All **NOT IMPL**. Requires representative users, D10, D11, and a restore/rollback environment.

## SG7 — Pilot-deployable release (M056–M062; F043; T023)

All **NOT IMPL**. Requires D12 and three separate sign-offs.

## Decisions (D01–D12)

| ID | Due | Status in tracker | Baseline note |
|---|---|---|---|
| D01 | SG0 | Open | Names/hours unknown |
| D02 | SG0 | Open | Pilot sites, language, pediatric reviewer unknown |
| D03 | SG0 | Open | Branch/PR/merge approver. Auditing account is read-only. |
| D04 | SG1 | Open (proposal recorded) | Built as proposed; **runtime dependency advisories** (PyJWT, Starlette) should be part of the approval |
| D05 | SG2 | Open | Blocks M011/M015 |
| D06 | SG2 | Open | Blocks SG3; needs lead time |
| D07 | SG2 | Open | Blocks M010/M013/F015 |
| D08 | SG3 | Open | |
| D09 | SG5 | Open | Staging on Render/Vercel/Supabase is synthetic-only |
| D10–D12 | SG5–SG7 | Open | |

**Decisions not in the tracker but needed now:**
- Product name (MatriSathi vs JananiSaathi).
- Episode model: one active episode per mother? A reopen path?
- What `dating_estimate` means (LMP or EDD?).
- Phone format and normalization.
- Org-admin self-grant and cross-org staff policy.
- Login throttling policy.
- Dependency upgrades (PyJWT, FastAPI/Starlette).
- Repo visibility.
- VitaInspire-reuse conflict (R09/G15 amendment).

## Duplicates and inconsistencies

- Two different tracker files exist:
  - the repo copy (status-edited by the previous implementer);
  - `Downloads/MCH/...Tracker_with_FS_and_TS.xlsx` (the original, with everything "Not started").
  - In the repo copy, cached formula values (gate counts, "Verified done") are blank because it was saved through openpyxl. Recalculate it in Excel.
- The spec workbook name differs between copies: `MatriSathi_Specifications_Updated.xlsx` in the repo vs `MatriSathi_Specifications_Team_7EKL6G.xlsx` / `Maternal_Child_Health_Dual_Tier_Specifications_updated.xlsx` in Downloads. The restart plan cites the dual-tier workbook.
- `JananiSaathi_Week_by_Week_Execution_Plan.docx` is stale. It says 6 commits, status.md last updated 30 Sep, and "commit staged SG1 work". In fact there are 8 commits, status.md was updated 31 Oct, and all work is committed with CI green.
