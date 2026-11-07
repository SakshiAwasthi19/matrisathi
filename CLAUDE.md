# MatriSathi — Maternal & Child Health

## Product
Build a practical MCH companion for rural and semi-urban India.
Support patients, caregivers, doctors and care coordinators.
Prioritize low bandwidth, shared phones, simple language,
WhatsApp communication and accessible voice/audio experiences.

Use the approved specification as the source of product scope.
Do not invent clinical schedules, medical content or requirements.
Identify contradictions and seek a decision before implementing them.

## Clinical boundaries
Assistive workflows only.
No diagnosis, treatment recommendations, clinical risk scoring,
medical-data interpretation or autonomous clinical advice.
Clinical content and escalation wording require doctor approval.
Keep human override and an audit trail for important actions.
Never imply that an unmonitored inbox provides emergency support.

## Architecture
This is an independent, self-contained application.

Prefer React/Vite/TypeScript, FastAPI and PostgreSQL, subject to the
approved architecture and specification.
Start with a modular monolith and clear module boundaries.
Avoid unnecessary microservices and infrastructure.

Do not identify or merge people solely by phone number.
Enforce organization, facility and caregiver access server-side.
Persist reminder jobs; support retries and duplicate prevention.

## Working process
For substantial work:
1. Inspect relevant files and project instructions.
2. Propose a bounded plan with acceptance criteria and affected files.
3. Wait for approval of the implementation scope.
4. Implement and verify the approved scope.
5. Fix failures introduced by the change without unnecessary questions.
6. Summarize changes, verification, limitations and the next action.

Ask questions when the answer changes product scope, clinical behavior,
data ownership, security boundaries or operating cost.
Resolve routine implementation details independently within approval.

## Permissions
Each commit and push requires explicit approval.
Deployment, paid services, destructive operations, new dependencies
and authentication-boundary changes require explicit approval unless
already specifically authorized for the current task.
Do not modify production systems from this project.
Do not weaken tests, permissions or instructions to make work pass.

## Privacy
Use synthetic patient data in development and tests.
Never expose secrets, patient records or sensitive message content
in prompts, logs, screenshots, fixtures or documentation.
Keep production credentials and patient exports outside this workspace.

## Verification
Use meaningful automated tests for changed behavior.
Prioritize access isolation, shared-phone identity, caregiver access,
message retries and duplicate events.
Run applicable lint, type checks, tests and builds.
Report exact results and explicitly identify checks not run.
AI review does not replace executable tests or tech-lead review.

## Delivery
Keep tasks small enough to demonstrate and review.
Maintain a brief project status with completed work, open decisions,
known limitations and the next task.
Do not claim production readiness solely because tests pass.


## Delivery plan
Before any task, read docs/delivery/PHASE_PLAN.md and
docs/delivery/CLAUDE_BUILD_PLAN.md. Work only on the task ID I give you,
follow the task loop in CLAUDE_BUILD_PLAN.md Part C, and keep
docs/delivery/progress.md and docs/delivery/phases.md up to date.
This file (CLAUDE.md) wins if anything conflicts.