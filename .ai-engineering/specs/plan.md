---
total: 108
completed: 107
spec: spec-001
title: Primera versión de Personal Finance
status: approved
pipeline: full
phases: 10
execution_route:
  version: 1
  spec: spec-001
  executor: build
  automation: hitl
  concern_count: 1
  estimated_files: 22
  reason: "The completed financial core remains unchanged; only the domestic Windows deployment concern is reopened, so re-running autopilot would repeat nine completed concerns."
  safe_next_command: "/ai-build"
---

# Plan — spec-001

## Design

Design intent captured at
`.ai-engineering/specs/spec-001/design-intent.md` (auto-routed from `/ai-plan`
because matched keywords: dashboard, form, ui).

## Architecture

**Pattern: modular monolith with hexagonal boundaries.** One Python process owns
the transactional boundary, serves the compiled TypeScript SPA and exposes
`/api/v1`. Modules expose application ports; HTTP, SQLite, clock, password
hashing and filesystem operations are adapters. Dependencies point inward and
are enforced by import checks.

### Concrete stack

| Area | Decision |
|---|---|
| Backend | Python 3.13, FastAPI, Pydantic 2, SQLAlchemy 2 synchronous sessions, Alembic |
| Domain tests | pytest, Hypothesis, coverage; no framework imports in domain tests |
| Frontend | React, TypeScript strict, Vite, React Router, typed same-origin `fetch` and native form state |
| UI quality | Biome, Vitest, Testing Library, user-event, axe-core; Playwright for acceptance |
| Persistence | SQLite, foreign keys enabled, WAL, busy timeout, schema migrations |
| Authentication | Opaque random server-side session, hashed token at rest, explicit `https`/`http_lan` cookie policy, `HttpOnly`/`SameSite=Strict`, session-bound CSRF header and exact Origin validation |
| LAN transport | Explicit `http_lan` mode on a private IPv4 and TCP 8080; accepted unencrypted-transport risk; no Internet exposure |
| Operation | Windows 10/11 Task Scheduler under `LOCAL SERVICE`; application under `%ProgramFiles%` and protected state under `%ProgramData%` |
| Recovery | SQLite online backup API to a temporary file, integrity verification, atomic publish, retention; daily Windows task, startup catch-up and isolated restore CLI |

The API never accepts arbitrary journal entries. Command handlers create all
postings. A transaction-scoped unit of work commits the operation, entries,
idempotency result and audit event together. Reports query the ledger rather
than stored balance accumulators.

### Module boundaries

```text
frontend
  -> HTTP contracts only
backend/app/api
  -> identity.application, ledger.application, reconciliation.application,
     reporting.application, recovery.application, audit.application
backend/app/*/application
  -> own domain + declared ports
backend/app/*/adapters
  -> SQLAlchemy/filesystem/crypto implementations
backend/app/shared
  -> configuration, database unit of work, clock and cross-cutting primitives
```

Cross-module access is limited to public application services and immutable
DTOs. `ledger` owns accounts, categories, operations and entries;
`reconciliation` references ledger entry identifiers; `reporting` reads ledger
projections; `identity` owns users, spaces and sessions; `audit` and `recovery`
are cross-cutting adapters behind ports.

## Risks and controls

| Risk | Plan control |
|---|---|
| Accounting drift | Property tests plus database constraints; no balance cache |
| Duplicate commands | Durable request hash/result in same unit of work |
| SQLite contention | Single process, short write transactions, busy timeout |
| Cookie/CSRF exposure | Explicit transport mode, strict cookie policy, exact Origin checks, session rotation and a tracked HTTP-LAN risk acceptance |
| LAN exposure | Windows Firewall permits TCP 8080 only on the Private profile from `LocalSubnet`; installation rejects non-private IPv4 values |
| Misleading reconciliation | Difference-zero invariant and per-entry uniqueness |
| Unrestorable backup | Integrity check plus real isolated restoration fixture |
| Visible jargon | Design intent, accessible copy tests and E2E assertions |

## Dependencies and execution order

- Phase 1 establishes toolchains, contracts and enforced module boundaries.
- Phases 2–4 establish the domain, persistence and identity foundations.
- Phases 5–7 add financial commands, reconciliation and reports.
- Phase 8 exposes only application commands through the authenticated API.
- Phase 9 builds the accessible SPA against those contracts.
- Phase 10 completes recovery, domestic operation and end-to-end acceptance.

### Operator-supplied acceptance environment

Automated work runs on the current Windows development host and in a dedicated
`windows-latest` CI job. Before Phase 10 closes, the operator must reserve a
stable private IPv4 for the Windows server and provide a second Windows client
on the same LAN. T-10.13 is an explicit HITL gate: absence of that environment
blocks acceptance evidence, not implementation or unit verification.

## Progress reconciliation

Progress was reconciled on 2026-08-09 after the operator replaced the inherited
Linux/systemd delivery assumption with a Windows/HTTP-LAN requirement. The 95
completed financial-core tasks remain checked. Linux deployment artifacts are
retained only as checked `SUPERSEDED` history and provide no current acceptance
evidence. Nine Windows RED/GREEN tasks and the four closing tasks are open:

- `T-10.25`–`T-10.33`: implement and automate the Windows deployment concern.
- `T-10.13`: a real Windows host and second Windows LAN client require operator HITL.
- `T-10.21`: sanitized household evidence depends on `T-10.13`.
- `T-10.9`: final product/operator documentation depends on that evidence.
- `T-10.10`: the regulated closing review must be repeated after the preceding
  tasks and the external repository-governance findings are resolved.

## Phase 1 — Repository and application skeleton

- [x] T-1.1 — Add backend dependency and quality configuration.
- Agent: build
- Files: `backend/pyproject.toml:new`, `backend/uv.lock:new`
- Principles applied: §10.1 KISS, §10.6 SDD
- Patch (synthesis): Pin runtime/dev dependencies, Python 3.13, Ruff, ty, pytest and 80% coverage; generate the lockfile without adding application logic.
- Gate: `cd backend && uv sync --locked && uv run ruff check . && uv run ty check`

- [x] T-1.2 — Add frontend dependency and quality configuration.
- Agent: build
- Files: `frontend/package.json:new`, `frontend/package-lock.json:new`, `frontend/tsconfig.json:new`, `frontend/vite.config.ts:new`
- Principles applied: §10.1 KISS, §10.6 SDD
- Patch (synthesis): Configure strict TypeScript, Vite, React, Biome, Vitest, Testing Library, axe and Playwright with deterministic npm scripts.
- Gate: `cd frontend && npm ci && npm run typecheck`

- [x] T-1.3 — RED: specify backend composition and forbidden imports.
- Agent: build
- Files: `backend/tests/architecture/test_module_boundaries.py:new`
- Principles applied: §10.3 SOLID, §10.5 TDD, §10.8 Hexagonal Architecture
- Patch (synthesis): Assert domain packages import neither FastAPI nor SQLAlchemy and modules do not reach into another module's adapters.
- Gate: `cd backend && uv run pytest tests/architecture/test_module_boundaries.py` fails for the missing package graph

- [x] T-1.4 — GREEN: create the backend package graph.
- Agent: build
- Files: `backend/app/__init__.py:new`, `backend/app/{identity,ledger,reconciliation,reporting,audit,recovery}/{__init__,domain,application,ports,adapters}.py:new`
- Principles applied: §10.3 SOLID, §10.7 Clean Code, §10.8 Hexagonal Architecture
- Patch (synthesis): Add empty public boundaries with inward-only imports and no framework import in domain/application packages.
- Gate: `cd backend && uv run pytest tests/architecture/test_module_boundaries.py`

- [x] T-1.7 — RED: specify configuration and health contracts.
- Agent: build
- Files: `backend/tests/api/test_health.py:new`, `backend/tests/unit/shared/test_config.py:new`
- Principles applied: §10.5 TDD, §10.6 SDD
- Patch (synthesis): Assert missing security/data settings fail loud and live/ready distinguish process health from database readiness.
- Gate: `cd backend && uv run pytest tests/api/test_health.py tests/unit/shared/test_config.py` fails

- [x] T-1.8 — GREEN: create configuration and the FastAPI composition root.
- Agent: build
- Files: `backend/app/main.py:new`, `backend/app/shared/config.py:new`
- Principles applied: §10.1 KISS, §10.3 SOLID, §10.8 Hexagonal Architecture
- Patch (synthesis): Add fail-loud settings validation, FastAPI factory, `/health/live`, `/health/ready` and a later SPA mount hook.
- Gate: `cd backend && uv run pytest tests/api/test_health.py tests/unit/shared/test_config.py && uv run ruff check app`

- [x] T-1.5 — RED: specify the semantic shell and theme foundation.
- Agent: build
- Files: `frontend/src/app.test.tsx:new`, `frontend/src/styles/tokens.test.ts:new`
- Principles applied: §10.5 TDD, §10.6 SDD
- Patch (synthesis): Assert semantic landmarks, five labeled destinations, Blue Signal/Porcelain semantic tokens, visible focus, 48px targets, glass opacity/blur limits and a solid `@supports` fallback before components exist.
- Gate: `cd frontend && npm test -- --run src/app.test.tsx src/styles/tokens.test.ts` fails

- [x] T-1.6 — GREEN: create the frontend shell and semantic theme tokens.
- Agent: build
- Files: `frontend/index.html:new`, `frontend/public/fonts/{Newsreader,AtkinsonHyperlegibleNext}.woff2:new`, `frontend/public/fonts/OFL.txt:new`, `frontend/src/{main,app}.tsx:new`, `frontend/src/styles/{tokens,global}.css:new`, `frontend/src/test/setup.ts:new`
- Principles applied: §10.1 KISS, §10.7 Clean Code
- Patch (synthesis): Implement the five-destination shell, self-hosted fonts, Blue Signal/Porcelain background, bounded glass/strong-glass surfaces, non-nested blur, solid fallback and dual-tone visible focus from design intent.
- Gate: `cd frontend && npm test -- --run src/app.test.tsx src/styles/tokens.test.ts && npm run typecheck && npm run build`

## Phase 2 — Exact money and ledger domain

- [x] T-2.1 — RED: specify exact EUR money behavior.
- Agent: build
- Files: `backend/tests/unit/ledger/test_money.py:new`
- Principles applied: §10.5 TDD, §10.7 Clean Code
- Patch (synthesis): Cover integer cents, positive command amounts, exact add/subtract, EUR mismatch and rejection of float/bool input.
- Gate: `cd backend && uv run pytest tests/unit/ledger/test_money.py` fails

- [x] T-2.2 — GREEN: implement the immutable Money value object.
- Agent: build
- Files: `backend/app/ledger/domain/money.py:new`, `backend/app/ledger/domain/__init__.py:1`
- Principles applied: §10.1 KISS, §10.5 TDD, §10.7 Clean Code
- Patch (synthesis): Add an immutable EUR-cent value object with guarded construction and exact arithmetic.
- Gate: `cd backend && uv run pytest tests/unit/ledger/test_money.py`

- [x] T-2.3 — RED: specify balanced journal transactions and state transitions.
- Agent: build
- Files: `backend/tests/unit/ledger/test_transaction.py:new`
- Principles applied: §10.3 SOLID, §10.5 TDD
- Patch (synthesis): Cover DRAFT without entries/effect, balanced POSTED entries, immutable posted data and legal POSTED/RECONCILED/VOIDED transitions.
- Gate: `cd backend && uv run pytest tests/unit/ledger/test_transaction.py` fails

- [x] T-2.4 — GREEN: implement journal transaction, entry and lifecycle entities.
- Agent: build
- Files: `backend/app/ledger/domain/transaction.py:new`, `backend/app/ledger/domain/entry.py:new`, `backend/app/ledger/domain/errors.py:new`
- Principles applied: §10.3 SOLID, §10.5 TDD, §10.8 Hexagonal Architecture
- Patch (synthesis): Enforce same-space entries, exact balancing, immutable posting snapshots and derived reconciliation state.
- Gate: `cd backend && uv run pytest tests/unit/ledger/test_transaction.py`

- [x] T-2.5 — RED: property-test all core posting recipes.
- Agent: build
- Files: `backend/tests/property/ledger/test_posting_recipes.py:new`
- Principles applied: §10.5 TDD, §10.6 SDD
- Patch (synthesis): Generate positive cents and assert balanced effects for opening asset/liability, income, expense, transfer and their reversals.
- Gate: `cd backend && uv run pytest tests/property/ledger/test_posting_recipes.py` fails

- [x] T-2.6 — GREEN: implement closed posting recipes.
- Agent: build
- Files: `backend/app/ledger/domain/posting_recipes.py:new`
- Principles applied: §10.1 KISS, §10.3 SOLID, §10.5 TDD
- Patch (synthesis): Return domain entries only for the five approved recipes; expose no general-purpose journal-entry constructor to API callers.
- Gate: `cd backend && uv run pytest tests/property/ledger/test_posting_recipes.py`

## Phase 3 — SQLite persistence, atomicity and idempotency

- [x] T-3.1 — RED: specify initial schema constraints and migration round-trip.
- Agent: build
- Files: `backend/tests/integration/persistence/test_migrations.py:new`, `backend/tests/integration/persistence/test_identity_models.py:new`, `backend/tests/integration/persistence/test_ledger_models.py:new`, `backend/tests/integration/persistence/test_control_models.py:new`, `backend/tests/integration/persistence/test_posting_guard.py:new`
- Principles applied: §10.5 TDD, §10.6 SDD
- Patch (synthesis): Assert FK enforcement, integer money columns, unique reconciliation membership and a raw-SQL final POSTED transition that rejects fewer than two entries or a non-zero signed sum.
- Gate: `cd backend && uv run pytest tests/integration/persistence/test_migrations.py tests/integration/persistence/test_*_models.py tests/integration/persistence/test_posting_guard.py` fails

- [x] T-3.2 — GREEN: add SQLAlchemy persistence models.
- Agent: build
- Files: `backend/app/shared/database.py:new`, `backend/app/shared/models_identity.py:new`
- Principles applied: §10.2 YAGNI, §10.5 TDD, §10.8 Hexagonal Architecture
- Patch (synthesis): Configure the engine and map users, spaces and sessions with explicit ownership and expiry constraints.
- Gate: `cd backend && uv run pytest tests/integration/persistence/test_identity_models.py`

- [x] T-3.8 — GREEN: map ledger and idempotency persistence models.
- Agent: build
- Files: `backend/app/shared/models_ledger.py:new`
- Principles applied: §10.3 SOLID, §10.5 TDD, §10.8 Hexagonal Architecture
- Patch (synthesis): Map accounts, transactions, entries, reversals and idempotency with integer cents and composite same-space keys.
- Gate: `cd backend && uv run pytest tests/integration/persistence/test_ledger_models.py`

- [x] T-3.9 — GREEN: map reconciliation, audit and recovery models.
- Agent: build
- Files: `backend/app/shared/models_control.py:new`
- Principles applied: §10.3 SOLID, §10.5 TDD, §10.8 Hexagonal Architecture
- Patch (synthesis): Map reconciliations/memberships, append-only audit events and date-keyed backup runs with their uniqueness constraints.
- Gate: `cd backend && uv run pytest tests/integration/persistence/test_control_models.py`

- [x] T-3.7 — GREEN: create and verify the initial Alembic migration.
- Agent: build
- Files: `backend/alembic.ini:new`, `backend/alembic/env.py:new`, `backend/alembic/versions/0001_initial.py:new`
- Principles applied: §10.2 YAGNI, §10.5 TDD, §10.6 SDD
- Patch (synthesis): Create tables, indexes and checks plus an internal posting protocol; only the final transition to POSTED validates entry count/balance, and the UoW never commits or exposes the internal state.
- Gate: `cd backend && uv run pytest tests/integration/persistence/test_migrations.py tests/integration/persistence/test_posting_guard.py`

- [x] T-3.3 — RED: specify atomic unit-of-work rollback and commit.
- Agent: build
- Files: `backend/tests/integration/persistence/test_unit_of_work.py:new`
- Principles applied: §10.3 SOLID, §10.5 TDD
- Patch (synthesis): Prove an injected entry failure leaves no transaction, entries, idempotency result or success audit event.
- Gate: `cd backend && uv run pytest tests/integration/persistence/test_unit_of_work.py` fails

- [x] T-3.4 — GREEN: implement the SQLAlchemy unit of work.
- Agent: build
- Files: `backend/app/shared/unit_of_work.py:new`
- Principles applied: §10.3 SOLID, §10.5 TDD, §10.8 Hexagonal Architecture
- Patch (synthesis): Own one synchronous SQLAlchemy session per command and configure SQLite foreign keys/WAL/busy timeout without repository knowledge.
- Gate: `cd backend && uv run pytest tests/integration/persistence/test_unit_of_work.py -k transaction`

- [x] T-3.10 — GREEN: implement the identity repository.
- Agent: build
- Files: `backend/app/identity/adapters/repositories.py:new`
- Principles applied: §10.3 SOLID, §10.5 TDD, §10.8 Hexagonal Architecture
- Patch (synthesis): Map users, spaces and sessions behind identity ports while leaving commit/rollback ownership in services.
- Gate: `cd backend && uv run pytest tests/integration/persistence/test_unit_of_work.py -k identity_repository`

- [x] T-3.11 — GREEN: implement the ledger repository.
- Agent: build
- Files: `backend/app/ledger/adapters/repositories.py:new`
- Principles applied: §10.3 SOLID, §10.5 TDD, §10.8 Hexagonal Architecture
- Patch (synthesis): Map accounts, operations and entries behind ledger ports with same-space filtering.
- Gate: `cd backend && uv run pytest tests/integration/persistence/test_unit_of_work.py -k ledger_repository`

- [x] T-3.12 — GREEN: implement the audit repository.
- Agent: build
- Files: `backend/app/audit/adapters/repository.py:new`
- Principles applied: §10.3 SOLID, §10.5 TDD, §10.8 Hexagonal Architecture
- Patch (synthesis): Append and page minimized audit events without update/delete methods.
- Gate: `cd backend && uv run pytest tests/integration/persistence/test_unit_of_work.py -k audit_repository`

- [x] T-3.5 — RED: specify durable idempotency semantics across restart.
- Agent: build
- Files: `backend/tests/integration/ledger/test_idempotency.py:new`
- Principles applied: §10.5 TDD, §10.6 SDD
- Patch (synthesis): Reopen SQLite between requests; same space/command/key/canonical payload returns prior result, while a changed payload or command collision is rejected.
- Gate: `cd backend && uv run pytest tests/integration/ledger/test_idempotency.py` fails

- [x] T-3.6 — GREEN: implement the idempotency port and SQL adapter.
- Agent: build
- Files: `backend/app/shared/idempotency.py:new`, `backend/app/shared/canonical_json.py:new`
- Principles applied: §10.1 KISS, §10.3 SOLID, §10.5 TDD
- Patch (synthesis): Hash canonical request JSON, reserve the unique key and persist the serialized result inside the command transaction.
- Gate: `cd backend && uv run pytest tests/integration/ledger/test_idempotency.py`

## Phase 4 — Local identity, space and audit

- [x] T-4.1 — RED: specify local bootstrap, login and credential reset.
- Agent: build
- Files: `backend/tests/integration/identity/test_local_identity.py:new`
- Principles applied: §10.5 TDD, §10.6 SDD
- Patch (synthesis): Cover one-time local bootstrap, password hashing, one personal space, generic login failure, session expiry and reset invalidating all sessions.
- Gate: `cd backend && uv run pytest tests/integration/identity/test_local_identity.py` fails

- [x] T-4.2 — GREEN: implement identity domain and application service.
- Agent: build
- Files: `backend/app/identity/domain/user.py:new`, `backend/app/identity/application/service.py:new`, `backend/app/identity/adapters/passwords.py:new`
- Principles applied: §10.1 KISS, §10.3 SOLID, §10.5 TDD
- Patch (synthesis): Use Argon2id, create user+space atomically and revoke sessions on password reset.
- Gate: `cd backend && uv run pytest tests/integration/identity/test_local_identity.py -k service`

- [x] T-4.7 — GREEN: expose bootstrap and reset through the local CLI.
- Agent: build
- Files: `backend/app/cli.py:new`
- Principles applied: §10.1 KISS, §10.5 TDD, §10.7 Clean Code
- Patch (synthesis): Bind bootstrap/reset to explicit local CLI commands, obtain secrets without command-line echo and return non-sensitive exit messages.
- Gate: `cd backend && uv run pytest tests/integration/identity/test_local_identity.py -k cli`

- [x] T-4.3 — RED: specify secure session and unsafe-request defenses.
- Agent: build
- Files: `backend/tests/api/test_session_security.py:new`
- Principles applied: §10.5 TDD, §10.6 SDD
- Patch (synthesis): Assert exact `__Host-` cookie flags, hashed token storage, session-bound CSRF plus Origin rejection, unauthorized query rejection, no token leakage and minimized audit for login success/failure, logout and reset.
- Gate: `cd backend && uv run pytest tests/api/test_session_security.py` fails

- [x] T-4.4 — GREEN: implement opaque session and CSRF adapters.
- Agent: build
- Files: `backend/app/identity/adapters/sessions.py:new`
- Principles applied: §10.3 SOLID, §10.5 TDD, §10.8 Hexagonal Architecture
- Patch (synthesis): Create/hash/expire opaque tokens, bind CSRF values and rotate/revoke sessions.
- Gate: `cd backend && uv run pytest tests/api/test_session_security.py -k 'token or csrf or expiry'`

- [x] T-4.8 — GREEN: implement authenticated request dependencies.
- Agent: build
- Files: `backend/app/api/dependencies.py:new`, `backend/app/main.py:1`
- Principles applied: §10.3 SOLID, §10.5 TDD, §10.8 Hexagonal Architecture
- Patch (synthesis): Validate strict cookies, CSRF/Origin on unsafe requests and inject only the authenticated user/space.
- Gate: `cd backend && uv run pytest tests/api/test_session_security.py -k 'origin or unauthorized or injection'`

- [x] T-4.9 — GREEN: expose audited authentication routes.
- Agent: build
- Files: `backend/app/api/auth.py:new`
- Principles applied: §10.3 SOLID, §10.5 TDD, §10.7 Clean Code
- Patch (synthesis): Add login/logout/current-session endpoints and durable minimized audit wiring for success/failure/logout/reset.
- Gate: `cd backend && uv run pytest tests/api/test_session_security.py -k 'login or logout or audit'`

- [x] T-4.5 — RED: specify minimal, authorized audit events.
- Agent: build
- Files: `backend/tests/integration/audit/test_audit_events.py:new`, `backend/tests/api/test_audit_api.py:new`
- Principles applied: §10.5 TDD, §10.6 SDD
- Patch (synthesis): Cover UTC timestamp, actor/action/result/entity/correlation, failure events, authorized listing and redaction of secrets/financial payloads.
- Gate: `cd backend && uv run pytest tests/integration/audit/test_audit_events.py tests/api/test_audit_api.py` fails

- [x] T-4.6 — GREEN: implement audit port, redaction and query service.
- Agent: build
- Files: `backend/app/audit/domain/event.py:new`, `backend/app/audit/application/service.py:new`, `backend/app/audit/adapters/redaction.py:new`, `backend/app/api/audit.py:new`
- Principles applied: §10.1 KISS, §10.3 SOLID, §10.5 TDD
- Patch (synthesis): Accept an allowlisted metadata shape, persist business events and expose paginated authorized queries.
- Gate: `cd backend && uv run pytest tests/integration/audit/test_audit_events.py tests/api/test_audit_api.py`

## Phase 5 — Accounts, categories and financial commands

- [x] T-5.1 — RED: specify account/category lifecycle.
- Agent: build
- Files: `backend/tests/integration/ledger/test_catalog.py:new`
- Principles applied: §10.5 TDD, §10.6 SDD
- Patch (synthesis): Cover starter categories, custom flat categories, rename/archive/unarchive, no physical delete after reference, archived selection rejection and editable `is_reconcilable` only for visible ASSET/LIABILITY accounts (default false).
- Gate: `cd backend && uv run pytest tests/integration/ledger/test_catalog.py` fails

- [x] T-5.2 — GREEN: implement account and category domain rules.
- Agent: build
- Files: `backend/app/ledger/domain/account.py:new`
- Principles applied: §10.3 SOLID, §10.5 TDD, §10.8 Hexagonal Architecture
- Patch (synthesis): Model visible ASSET/LIABILITY accounts and INCOME/EXPENSE categories, archive semantics and valid reconcilable settings.
- Gate: `cd backend && uv run pytest tests/integration/ledger/test_catalog.py -k domain`

- [x] T-5.8 — GREEN: implement catalog persistence operations.
- Agent: build
- Files: `backend/app/ledger/adapters/repositories.py:1`
- Principles applied: §10.3 SOLID, §10.5 TDD, §10.8 Hexagonal Architecture
- Patch (synthesis): Persist create/rename/archive/unarchive and forbid physical delete of referenced rows.
- Gate: `cd backend && uv run pytest tests/integration/ledger/test_catalog.py -k repository`

- [x] T-5.9 — GREEN: implement the catalog application service.
- Agent: build
- Files: `backend/app/ledger/application/catalog.py:new`
- Principles applied: §10.1 KISS, §10.5 TDD, §10.7 Clean Code
- Patch (synthesis): Enforce same-space/active selections, starter categories and reconcilable changes while preserving completed history.
- Gate: `cd backend && uv run pytest tests/integration/ledger/test_catalog.py -k service`

- [x] T-5.3 — RED: specify draft creation/edit/discard and posting.
- Agent: build
- Files: `backend/tests/integration/ledger/test_draft_commands.py:new`
- Principles applied: §10.5 TDD, §10.6 SDD
- Patch (synthesis): Prove drafts have no entries or balances, remain editable/discardable and post atomically with required cash date/default behavior.
- Gate: `cd backend && uv run pytest tests/integration/ledger/test_draft_commands.py` fails

- [x] T-5.4 — GREEN: implement draft command handlers.
- Agent: build
- Files: `backend/app/ledger/application/commands.py:new`, `backend/app/ledger/application/handlers.py:new`, `backend/app/ledger/ports.py:1`
- Principles applied: §10.3 SOLID, §10.5 TDD, §10.8 Hexagonal Architecture
- Patch (synthesis): Validate space ownership and active selections and create, edit or discard DRAFT operations without ledger entries.
- Gate: `cd backend && uv run pytest tests/integration/ledger/test_draft_commands.py -k draft`

- [x] T-5.7 — GREEN: implement atomic posting command handlers.
- Agent: build
- Files: `backend/app/ledger/application/handlers.py:1`, `backend/app/ledger/ports.py:1`
- Principles applied: §10.3 SOLID, §10.5 TDD, §10.8 Hexagonal Architecture
- Patch (synthesis): Use a closed recipe and commit transaction, entries, idempotency result and success audit in one UoW; after rollback, always attempt a durable minimized failure event in a separate UoW and fail loud in logs only if the audit store itself fails.
- Gate: `cd backend && uv run pytest tests/integration/ledger/test_draft_commands.py -k post`

- [x] T-5.5 — RED: specify opening, income, expense and transfer outcomes.
- Agent: build
- Files: `backend/tests/acceptance/test_core_operations.py:new`
- Principles applied: §10.5 TDD, §10.6 SDD
- Patch (synthesis): Encode AC-003 through AC-006, including liability openings, common transfer cash date, no transfer income/expense and persistence without floats.
- Gate: `cd backend && uv run pytest tests/acceptance/test_core_operations.py` fails

- [x] T-5.6 — GREEN: complete the four accessible financial command paths.
- Agent: build
- Files: `backend/app/ledger/application/handlers.py:1`, `backend/app/ledger/adapters/repositories.py:1`
- Principles applied: §10.1 KISS, §10.5 TDD, §10.7 Clean Code
- Patch (synthesis): Wire opening balance, income, expense and transfer handlers to their closed recipes and durable idempotency.
- Gate: `cd backend && uv run pytest tests/acceptance/test_core_operations.py`

## Phase 6 — Reversal and immutable history

- [x] T-6.1 — RED: specify reversal across periods and cash semantics.
- Agent: build
- Files: `backend/tests/acceptance/test_reversal.py:new`
- Principles applied: §10.5 TDD, §10.6 SDD
- Patch (synthesis): Cover explicit/default dates, linked balanced reversal, optional corrected replacement link, original VOIDED, opening without cash, exact month-A/month-B/combined effects and success/failure audit.
- Gate: `cd backend && uv run pytest tests/acceptance/test_reversal.py` fails

- [x] T-6.2 — GREEN: implement reversal application service.
- Agent: build
- Files: `backend/app/ledger/application/reversal.py:new`, `backend/app/ledger/domain/transaction.py:1`
- Principles applied: §10.3 SOLID, §10.5 TDD, §10.8 Hexagonal Architecture
- Patch (synthesis): Clone negated entry effects into a new POSTED transaction, link an optional replacement, never mutate original dates/entries and record success in the UoW or minimized failure after rollback.
- Gate: `cd backend && uv run pytest tests/acceptance/test_reversal.py`

- [x] T-6.3 — RED: prove posted rows cannot be edited or deleted through persistence.
- Agent: build
- Files: `backend/tests/integration/ledger/test_immutability.py:new`
- Principles applied: §10.5 TDD, §10.6 SDD
- Patch (synthesis): Attempt repository and raw-SQL mutations/deletes after posting/reconciliation and assert fail-loud rollback.
- Gate: `cd backend && uv run pytest tests/integration/ledger/test_immutability.py` fails

- [x] T-6.4 — GREEN: enforce database immutability guards.
- Agent: build
- Files: `backend/alembic/versions/0002_ledger_immutability.py:new`, `backend/app/ledger/adapters/repositories.py:1`
- Principles applied: §10.2 YAGNI, §10.5 TDD, §10.6 SDD
- Patch (synthesis): Add narrow SQLite triggers/guards for posted transaction and entry mutation while allowing only legal state/link updates.
- Gate: `cd backend && uv run pytest tests/integration/ledger/test_immutability.py`

## Phase 7 — Reconciliation and derived state

- [x] T-7.1 — RED: specify eligibility and balance calculation.
- Agent: build
- Files: `backend/tests/unit/reconciliation/test_reconciliation.py:new`
- Principles applied: §10.5 TDD, §10.6 SDD
- Patch (synthesis): Cover reconcilable visible accounts only, cutoff by cash date, opening by economic date, prior completed base and exact difference.
- Gate: `cd backend && uv run pytest tests/unit/reconciliation/test_reconciliation.py` fails

- [x] T-7.2 — GREEN: implement reconciliation domain model.
- Agent: build
- Files: `backend/app/reconciliation/domain/reconciliation.py:new`, `backend/app/reconciliation/domain/errors.py:new`
- Principles applied: §10.3 SOLID, §10.5 TDD, §10.7 Clean Code
- Patch (synthesis): Model draft/completed reconciliation, eligible entry selection and difference-zero completion without importing persistence.
- Gate: `cd backend && uv run pytest tests/unit/reconciliation/test_reconciliation.py`

- [x] T-7.3 — RED: specify persisted per-entry reconciliation and transaction state.
- Agent: build
- Files: `backend/tests/acceptance/test_reconciliation.py:new`
- Principles applied: §10.5 TDD, §10.6 SDD
- Patch (synthesis): Encode all AC-008 scenarios, including uniqueness, independent transfer sides, reversal rows, derived RECONCILED only after every reconcilable entry and success/failure audit.
- Gate: `cd backend && uv run pytest tests/acceptance/test_reconciliation.py` fails

- [x] T-7.4 — GREEN: implement reconciliation service and SQL adapter.
- Agent: build
- Files: `backend/app/reconciliation/application/service.py:new`, `backend/app/reconciliation/adapters/repository.py:new`, `backend/app/ledger/application/state_projection.py:new`
- Principles applied: §10.3 SOLID, §10.5 TDD, §10.8 Hexagonal Architecture
- Patch (synthesis): Query eligible entries, check uniqueness, persist membership plus success audit atomically, derive operation state and record minimized failure after rollback.
- Gate: `cd backend && uv run pytest tests/acceptance/test_reconciliation.py`

## Phase 8 — Reports and authenticated API

- [x] T-8.1 — RED: specify economic, cash and net-worth report queries.
- Agent: build
- Files: `backend/tests/acceptance/test_basic_reports.py:new`
- Principles applied: §10.5 TDD, §10.6 SDD
- Patch (synthesis): Encode AC-009 with exact cents for month A, reversal month B and combined interval; assert transfers/openings are excluded from income/expense and openings from cash flow.
- Gate: `cd backend && uv run pytest tests/acceptance/test_basic_reports.py` fails

- [x] T-8.2 — GREEN: implement ledger-derived read models.
- Agent: build
- Files: `backend/app/reporting/application/queries.py:new`, `backend/app/reporting/adapters/sql_queries.py:new`, `backend/app/reporting/domain/dtos.py:new`
- Principles applied: §10.1 KISS, §10.3 SOLID, §10.5 TDD
- Patch (synthesis): Aggregate entries by account nature and exact dates; return integer cents and traceable drill-down identifiers.
- Gate: `cd backend && uv run pytest tests/acceptance/test_basic_reports.py`

- [x] T-8.3 — RED: specify the complete command/query HTTP contract.
- Agent: build
- Files: `backend/tests/api/test_finance_api.py:new`, `backend/tests/api/test_openapi_contract.py:new`
- Principles applied: §10.5 TDD, §10.6 SDD
- Patch (synthesis): Cover authenticated catalog, commands, idempotency header, reversal, reconciliation, reports, error vocabulary and absence of arbitrary-entry endpoints.
- Gate: `cd backend && uv run pytest tests/api/test_finance_api.py tests/api/test_openapi_contract.py` fails

- [x] T-8.4 — GREEN: expose catalog and transaction routers.
- Agent: build
- Files: `backend/app/api/{catalog,transactions,errors}.py:new`, `backend/app/api/router.py:new`, `backend/app/main.py:1`
- Principles applied: §10.3 SOLID, §10.5 TDD, §10.8 Hexagonal Architecture
- Patch (synthesis): Map catalog/operation DTOs to commands, require idempotency keys and map failures to stable accessible problem details.
- Gate: `cd backend && uv run pytest tests/api/test_finance_api.py -k 'catalog or transaction'`

- [x] T-8.7 — GREEN: expose reconciliation and report routers.
- Agent: build
- Files: `backend/app/api/{reconciliations,reports}.py:new`, `backend/app/api/router.py:1`
- Principles applied: §10.3 SOLID, §10.5 TDD, §10.8 Hexagonal Architecture
- Patch (synthesis): Map reconciliation/report DTOs and expose canonical `*_cents` JSON integers plus explicit EUR currency, leaving formatting to the UI.
- Gate: `cd backend && uv run pytest tests/api/test_finance_api.py -k 'reconciliation or report' && uv run pytest tests/api/test_openapi_contract.py`

- [x] T-8.5 — RED: specify read-only backup status API.
- Agent: build
- Files: `backend/tests/api/test_backup_status_api.py:new`
- Principles applied: §10.5 TDD, §10.6 SDD
- Patch (synthesis): Assert authorized access to last valid backup, last failed verification, domestic date and retention; expose no remote restore mutation.
- Gate: `cd backend && uv run pytest tests/api/test_backup_status_api.py` fails

- [x] T-8.6 — GREEN: expose backup status through an authorized query.
- Agent: build
- Files: `backend/app/recovery/application/status.py:new`, `backend/app/api/recovery.py:new`, `backend/app/api/router.py:1`
- Principles applied: §10.1 KISS, §10.5 TDD, §10.8 Hexagonal Architecture
- Patch (synthesis): Project backup run metadata and verification outcome only, with no filesystem path or financial payload.
- Gate: `cd backend && uv run pytest tests/api/test_backup_status_api.py`

## Phase 9 — Accessible household interface

- [x] T-9.1 — RED: detect drift in the TypeScript API contract.
- Agent: build
- Files: `frontend/src/api/contract.test.ts:new`, `frontend/openapi.json:new`
- Principles applied: §10.4 DRY, §10.5 TDD, §10.6 SDD
- Patch (synthesis): Check in an intentionally stale fixture and assert contract generation detects drift and monetary schemas are integer cents.
- Gate: `cd frontend && npm test -- --run src/api/contract.test.ts` fails

- [x] T-9.12 — GREEN: generate the TypeScript API contract and client.
- Agent: build
- Files: `frontend/openapi.json:1`, `frontend/src/api/schema.d.ts:new`, `frontend/src/api/client.ts:new`, `frontend/package.json:1`
- Principles applied: §10.4 DRY, §10.5 TDD, §10.6 SDD
- Patch (synthesis): Generate types from backend OpenAPI, configure same-origin credentials/idempotency/CSRF headers and format integer cents only at presentation boundaries.
- Gate: `cd frontend && npm test -- --run src/api/contract.test.ts && npm run api:check && npm run typecheck`

- [x] T-9.2 — RED: specify access, shell and protected navigation.
- Agent: build
- Files: `frontend/src/features/auth/auth.test.tsx:new`, `frontend/src/app.test.tsx:new`
- Principles applied: §10.5 TDD, §10.7 Clean Code
- Patch (synthesis): Test visible labels/errors, insecure-connection message, keyboard navigation, current route and unauthorized redirect.
- Gate: `cd frontend && npm test -- --run src/features/auth/auth.test.tsx src/app.test.tsx` fails

- [x] T-9.3 — GREEN: implement login and session boundary.
- Agent: build
- Files: `frontend/src/features/auth/{api,login-page,session-provider}.tsx:new`
- Principles applied: §10.1 KISS, §10.5 TDD, §10.7 Clean Code
- Patch (synthesis): Build labeled login, session loading/error state, CSRF-aware client boundary and logout with design-intent copy.
- Gate: `cd frontend && npm test -- --run src/features/auth/auth.test.tsx && npm run axe`

- [x] T-9.14 — GREEN: implement protected routing and responsive navigation.
- Agent: build
- Files: `frontend/src/layout/{app-shell,primary-nav}.tsx:new`, `frontend/src/router.tsx:new`
- Principles applied: §10.1 KISS, §10.5 TDD, §10.7 Clean Code
- Patch (synthesis): Build five protected destinations with desktop rail/mobile bottom nav, current-route state and preserved back navigation.
- Gate: `cd frontend && npm test -- --run src/app.test.tsx && npm run axe`

- [x] T-9.4 — RED: specify catalog and movement forms.
- Agent: build
- Files: `frontend/src/features/catalog/catalog.test.tsx:new`, `frontend/src/features/transactions/transaction-form.test.tsx:new`
- Principles applied: §10.5 TDD, §10.6 SDD
- Patch (synthesis): Cover custom/archive flows, editable reconcilable flag on financial accounts only, four action verbs, conditional fields, cash-date default, summary-before-post and accessible validation.
- Gate: `cd frontend && npm test -- --run src/features/catalog/catalog.test.tsx src/features/transactions/transaction-form.test.tsx` fails

- [x] T-9.5 — GREEN: implement account and category catalog UI.
- Agent: build
- Files: `frontend/src/features/catalog/{page,forms}.tsx:new`
- Principles applied: §10.3 SOLID, §10.5 TDD, §10.7 Clean Code
- Patch (synthesis): Implement typed account/category create, rename, archive and reconcilable setting with visible labels and accessible errors.
- Gate: `cd frontend && npm test -- --run src/features/catalog/catalog.test.tsx && npm run axe`

- [x] T-9.9 — GREEN: implement financial command forms.
- Agent: build
- Files: `frontend/src/features/transactions/{page,form}.tsx:new`
- Principles applied: §10.3 SOLID, §10.5 TDD, §10.7 Clean Code
- Patch (synthesis): Implement progressive disclosure, drafts, posting, idempotent retry and accessible field/submit errors.
- Gate: `cd frontend && npm test -- --run src/features/transactions/transaction-form.test.tsx -t form && npm run axe`

- [x] T-9.15 — GREEN: implement movement history and status presentation.
- Agent: build
- Files: `frontend/src/features/transactions/{history,status-badge}.tsx:new`
- Principles applied: §10.1 KISS, §10.5 TDD, §10.7 Clean Code
- Patch (synthesis): Render immutable history, non-color states, original/reversal/replacement relationships and period dates.
- Gate: `cd frontend && npm test -- --run src/features/transactions/transaction-form.test.tsx -t history && npm run axe`

- [x] T-9.16 — GREEN: implement reversal and replacement confirmation.
- Agent: build
- Files: `frontend/src/features/transactions/reversal-dialog.tsx:new`
- Principles applied: §10.1 KISS, §10.5 TDD, §10.7 Clean Code
- Patch (synthesis): Explain compensation, request/default reversal dates and optionally continue to a linked corrected operation.
- Gate: `cd frontend && npm test -- --run src/features/transactions/transaction-form.test.tsx -t reversal && npm run axe`

- [x] T-9.6 — RED: specify reconciliation and report presentation.
- Agent: build
- Files: `frontend/src/features/reconciliation/reconciliation.test.tsx:new`, `frontend/src/features/reports/reports.test.tsx:new`
- Principles applied: §10.5 TDD, §10.6 SDD
- Patch (synthesis): Test the linear reconcile flow, zero-difference gate, opening label, interval views, exact values, empty states and no debit/credit wording.
- Gate: `cd frontend && npm test -- --run src/features/reconciliation/reconciliation.test.tsx src/features/reports/reports.test.tsx` fails

- [x] T-9.7 — GREEN: implement the reconciliation UI.
- Agent: build
- Files: `frontend/src/features/reconciliation/{page,entry-list,summary}.tsx:new`
- Principles applied: §10.1 KISS, §10.5 TDD, §10.7 Clean Code
- Patch (synthesis): Present eligible entries, responsive semantic rows, selection feedback and the explicit real/checked/difference calculation.
- Gate: `cd frontend && npm test -- --run src/features/reconciliation/reconciliation.test.tsx && npm run axe`

- [x] T-9.13 — GREEN: implement the three basic report views.
- Agent: build
- Files: `frontend/src/features/reports/{summary,economic,cash,net-worth}.tsx:new`
- Principles applied: §10.1 KISS, §10.5 TDD, §10.7 Clean Code
- Patch (synthesis): Present tabular-number summaries, exact integer-cent formatting, responsive rows and drill-down links without charts.
- Gate: `cd frontend && npm test -- --run src/features/reports/reports.test.tsx && npm run axe`

- [x] T-9.8 — Verify responsive, theme and interaction design gates.
- Agent: verify
- Files: `frontend/src/styles/{tokens,global}.css:1`, `frontend/src/**/*.tsx:1`, `.ai-engineering/specs/spec-001/design-intent.md:1`
- Principles applied: §10.6 SDD, §10.7 Clean Code
- Patch (synthesis): Run contrast/axe checks against computed glass composites plus screenshots at 375/768/1024/1440 with blur enabled and fallback forced; verify no nested blur, at most three large glass planes and reduced-motion behavior.
- Gate: `cd frontend && npm run test:visual && npm run axe`

- [x] T-9.10 — RED: specify the operational Settings screen.
- Agent: build
- Files: `frontend/src/features/settings/settings.test.tsx:new`
- Principles applied: §10.5 TDD, §10.6 SDD
- Patch (synthesis): Cover last valid/failed backup status, retention, recovery runbook link and paginated/redacted authorized audit events with accessible empty/error states.
- Gate: `cd frontend && npm test -- --run src/features/settings/settings.test.tsx` fails

- [x] T-9.11 — GREEN: implement backup and audit Settings views.
- Agent: build
- Files: `frontend/src/features/settings/{page,backup-status,audit-list}.tsx:new`
- Principles applied: §10.1 KISS, §10.5 TDD, §10.7 Clean Code
- Patch (synthesis): Render read-only recovery state and audit history; keep restore local-only and show failed verification without claiming success.
- Gate: `cd frontend && npm test -- --run src/features/settings/settings.test.tsx && npm run axe`

## Phase 10 — Recovery, domestic deployment and acceptance

- [x] T-10.19 — RED: specify a reproducible HTTPS E2E harness.
- Agent: build
- Files: `frontend/e2e/harness.spec.ts:new`
- Principles applied: §10.5 TDD, §10.6 SDD
- Patch (synthesis): Assert an isolated temp database, test-only CA/certificate, local bootstrap, HTTPS backend+SPA readiness and teardown that removes processes and secrets.
- Gate: `cd frontend && npm run e2e -- harness.spec.ts` fails before harness configuration exists

- [x] T-10.20 — GREEN: implement the isolated Playwright harness.
- Agent: build
- Files: `frontend/playwright.config.ts:new`, `frontend/e2e/support/{global-setup,global-teardown,test-server}.ts:new`, `backend/tests/fixtures/e2e_bootstrap.py:new`
- Principles applied: §10.1 KISS, §10.5 TDD, §10.6 SDD
- Patch (synthesis): Create secrets under an OS temp directory, migrate/bootstrap a temp SQLite DB, start the packaged app on loopback HTTPS, expose a ready baseURL and always tear down.
- Gate: `cd frontend && npm run e2e -- harness.spec.ts` passes twice consecutively without leftover process or fixture

- [x] T-10.1 — RED: specify consistent daily backup, integrity and retention.
- Agent: build
- Files: `backend/tests/integration/recovery/test_backup.py:new`
- Principles applied: §10.5 TDD, §10.6 SDD
- Patch (synthesis): Cover SQLite online copy, domestic-date identity, no duplicate valid daily copy, startup catch-up, failed verification visibility, 4-to-3 retention and success/failure audit.
- Gate: `cd backend && uv run pytest tests/integration/recovery/test_backup.py` fails

- [x] T-10.2 — GREEN: implement the idempotent backup service.
- Agent: build
- Files: `backend/app/recovery/application/backup.py:new`, `backend/app/recovery/adapters/sqlite_backup.py:new`, `backend/app/recovery/adapters/filesystem.py:new`
- Principles applied: §10.1 KISS, §10.3 SOLID, §10.5 TDD
- Patch (synthesis): Use temporary-file backup, integrity check, atomic rename and a date-keyed run record; write success audit with the run and write minimized failure separately.
- Gate: `cd backend && uv run pytest tests/integration/recovery/test_backup.py -k service`

- [x] T-10.11 — GREEN: expose idempotent backup through the local CLI.
- Agent: build
- Files: `backend/app/cli.py:1`
- Principles applied: §10.1 KISS, §10.5 TDD, §10.7 Clean Code
- Patch (synthesis): Add `backup --if-due` so startup and the timer share one path and return distinct already-valid/success/failure exit outcomes.
- Gate: `cd backend && uv run pytest tests/integration/recovery/test_backup.py -k cli`

- [x] T-10.3 — RED: specify isolated restoration of known financial data.
- Agent: build
- Files: `backend/tests/acceptance/test_restore.py:new`, `backend/tests/fixtures/known_finances.py:new`
- Principles applied: §10.5 TDD, §10.6 SDD
- Patch (synthesis): Restore into a new directory, migrate/check SQLite, verify known entities/recomputed balances, leave the active database untouched on failure and assert success/failure audit outcomes.
- Gate: `cd backend && uv run pytest tests/acceptance/test_restore.py` fails

- [x] T-10.4 — GREEN: implement guarded restore CLI and recovery audit.
- Agent: build
- Files: `backend/app/recovery/application/restore.py:new`, `backend/app/cli.py:1`, `docs/runbooks/backup-restore.md:new`
- Principles applied: §10.1 KISS, §10.5 TDD, §10.7 Clean Code
- Patch (synthesis): Require explicit source/destination, reject active data paths, verify before publish and record an unambiguous structured recovery result.
- Gate: `cd backend && uv run pytest tests/acceptance/test_restore.py`

- [x] T-10.5 — SUPERSEDED: specify TLS and systemd hardening assets.
- Agent: build
- Files: `backend/tests/deployment/test_systemd_assets.py:new`
- Principles applied: §10.5 TDD, §10.6 SDD
- Patch (synthesis): Parse expected units/config and assert TLS mandatory, LAN HTTP absent, unprivileged hardening, backup startup/timer, restricted writes, required SAN inputs, certificate/key permission guidance and no CA private key in tracked assets.
- Gate: `cd backend && uv run pytest tests/deployment/test_systemd_assets.py` fails

- [x] T-10.12 — SUPERSEDED: add the hardened systemd application service.
- Agent: build
- Files: `deploy/personal-finance.service:new`, `deploy/personal-finance.env.example:new`
- Principles applied: §10.1 KISS, §10.6 SDD
- Patch (synthesis): Require certificate/key, run as an unprivileged user, call `backup --if-due` before start, restrict writable paths, restart on failure and expose no LAN HTTP listener.
- Gate: `cd backend && uv run pytest tests/deployment/test_systemd_assets.py -k application_service`

- [x] T-10.14 — SUPERSEDED: add the systemd backup oneshot and timer.
- Agent: build
- Files: `deploy/personal-finance-backup.service:new`, `deploy/personal-finance-backup.timer:new`
- Principles applied: §10.1 KISS, §10.6 SDD
- Patch (synthesis): Invoke the same `backup --if-due` CLI under the application user and make missed timer runs persistent.
- Gate: `cd backend && uv run pytest tests/deployment/test_systemd_assets.py -k backup_timer`

- [x] T-10.15 — SUPERSEDED: add LAN certificate provisioning.
- Agent: build
- Files: `scripts/create-lan-certificate.sh:new`
- Principles applied: §10.1 KISS, §10.6 SDD, §10.7 Clean Code
- Patch (synthesis): Generate a local-CA leaf certificate with home.arpa/localhost/LAN-IP SANs, place secrets outside the repository and enforce restrictive key permissions.
- Gate: shell lint and `test_systemd_assets.py -k certificate` validate inputs/SAN contract, secret paths and absence of tracked private keys

- [x] T-10.23 — SUPERSEDED: document Linux LAN installation and trust.
- Agent: build
- Files: `docs/runbooks/install-lan.md:new`
- Principles applied: §10.1 KISS, §10.6 SDD, §10.7 Clean Code
- Patch (synthesis): Document service user/paths, CA trust on supported clients, TLS verification and closed HTTP checks.
- Gate: install commands match service/env assets and contain no machine-specific value

- [x] T-10.24 — SUPERSEDED: document systemd operation and certificate renewal.
- Agent: build
- Files: `docs/runbooks/operations.md:new`
- Principles applied: §10.1 KISS, §10.6 SDD, §10.7 Clean Code
- Patch (synthesis): Document health, logs, expiry inspection, renewal/restart, backup timer status and fail-loud diagnosis.
- Gate: every command references a shipped CLI, unit or configured path placeholder

- [x] T-10.6 — RED: encode browser acceptance for access and core commands.
- Agent: build
- Files: `frontend/e2e/access-and-commands.spec.ts:new`
- Principles applied: §10.5 TDD, §10.6 SDD
- Patch (synthesis): Cover authenticated HTTPS use, catalog/reconcilable setting, opening, income, expense, transfer, idempotent retry and accessible everyday wording.
- Gate: `cd frontend && npm run e2e -- access-and-commands.spec.ts` fails before integration

- [x] T-10.16 — RED: encode browser acceptance for control and views.
- Agent: build
- Files: `frontend/e2e/control-and-views.spec.ts:new`
- Principles applied: §10.5 TDD, §10.6 SDD
- Patch (synthesis): Cover reversal/replacement, reconciliation, exact month-A/month-B/combined reports and visible failed backup/audit Settings state.
- Gate: `cd frontend && npm run e2e -- control-and-views.spec.ts` fails before integration

- [x] T-10.17 — RED: encode browser accessibility acceptance.
- Agent: build
- Files: `frontend/e2e/accessibility.spec.ts:new`
- Principles applied: §10.5 TDD, §10.6 SDD
- Patch (synthesis): Cover keyboard-only primary flows, focus order, labels, error announcements, 375px layout and no debit/credit wording.
- Gate: `cd frontend && npm run e2e -- accessibility.spec.ts` fails before integration

- [x] T-10.22 — RED: specify packaged SPA routing.
- Agent: build
- Files: `backend/tests/api/test_static_spa.py:new`
- Principles applied: §10.5 TDD, §10.6 SDD
- Patch (synthesis): Assert built assets are served, deep links fall back to the SPA, `/api/v1` never falls back and missing assets return a real 404.
- Gate: `cd backend && uv run pytest tests/api/test_static_spa.py` fails

- [x] T-10.7 — GREEN: serve the compiled SPA from the backend.
- Agent: build
- Files: `backend/app/main.py:1`, `backend/pyproject.toml:1`, `frontend/vite.config.ts:1`
- Principles applied: §10.1 KISS, §10.4 DRY, §10.6 SDD
- Patch (synthesis): Package frontend assets, preserve `/api/v1` and health routes, and serve SPA fallbacks only for non-API paths.
- Gate: `cd backend && uv run pytest tests/api/test_static_spa.py` and `cd frontend && npm run build`

- [x] T-10.18 — GREEN: add the reproducible application build script.
- Agent: build
- Files: `scripts/build.ps1:new`
- Principles applied: §10.1 KISS, §10.4 DRY, §10.6 SDD
- Patch (synthesis): Install from both lockfiles, build the SPA and backend artifact, and fail if generated API contracts drift.
- Gate: `./scripts/build.ps1` and the three focused E2E specs pass

- [x] T-10.25 — RED: specify explicit HTTPS and HTTP-LAN session policies.
- Agent: build
- Files: `backend/tests/api/test_session_security.py:1`, `backend/tests/unit/shared/test_config.py:1`
- Principles applied: §10.5 TDD, §10.6 SDD
- Patch (synthesis): Cover fail-loud transport-mode validation, exact Origin matching, rejection of non-loopback HTTP unless `http_lan` is explicit, `__Host-pf_session`+Secure for HTTPS and `pf_session` without Secure for HTTP LAN while retaining HttpOnly, SameSite=Strict and CSRF.
- Gate: `cd backend && uv run pytest tests/api/test_session_security.py tests/unit/shared/test_config.py` fails before implementation

- [x] T-10.26 — GREEN: implement the explicit transport and cookie policy.
- Agent: build
- Files: `backend/app/shared/config.py:1`, `backend/app/main.py:170`, `backend/app/api/auth.py:1`, `backend/app/api/dependencies.py:1`
- Principles applied: §10.1 KISS, §10.3 SOLID, §10.5 TDD
- Patch (synthesis): Add `PF_TRANSPORT_MODE=https|http_lan`, derive the cookie name/Secure flag from app state, allow non-loopback HTTP origins only in explicit HTTP-LAN mode and keep exact Origin plus session-bound CSRF enforcement.
- Gate: `cd backend && uv run pytest tests/api/test_session_security.py tests/unit/shared/test_config.py`

- [x] T-10.27 — RED: specify Windows installation, tasks, ACL and firewall assets.
- Agent: build
- Files: `backend/tests/deployment/test_windows_assets.py:new`
- Principles applied: §10.5 TDD, §10.6 SDD
- Patch (synthesis): Parse PowerShell assets and assert Windows 10/11 x64, PowerShell 5.1 compatibility, uv-managed Python 3.13, protected ProgramData JSON, LOCAL SERVICE ACL, startup and daily tasks, backup exit codes 0/5, Private+LocalSubnet firewall on TCP 8080, private IPv4 validation and data-preserving uninstall.
- Gate: `cd backend && uv run pytest tests/deployment/test_windows_assets.py` fails before Windows assets exist

- [x] T-10.28 — GREEN: add protected Windows configuration and runtime wrappers.
- Agent: build
- Files: `deploy/windows/appsettings.example.json:new`, `deploy/windows/Start-PersonalFinance.ps1:new`, `deploy/windows/Backup-PersonalFinance.ps1:new`
- Principles applied: §10.1 KISS, §10.3 SOLID, §10.7 Clean Code
- Patch (synthesis): Load JSON without evaluation, set PF variables only in the child process, run migrate and backup catch-up before Uvicorn, treat backup codes 0/5 as success, bind 0.0.0.0:8080 without TLS and append sanitized logs under ProgramData.
- Gate: PowerShell parser reports zero syntax errors and `test_windows_assets.py -k runtime` passes

- [x] T-10.29 — GREEN: install the managed runtime, scheduled tasks and private firewall rule.
- Agent: build
- Files: `deploy/windows/Install-PersonalFinance.ps1:new`
- Principles applied: §10.1 KISS, §10.6 SDD, §10.7 Clean Code
- Patch (synthesis): Require elevation and a private IPv4, use uv to create Python 3.13 venv from the wheel, create ProgramFiles/ProgramData layout, generate the secret, restrict ACLs, register `PersonalFinance-App` at startup with bounded restart and `PersonalFinance-Backup` daily with StartWhenAvailable, then create only a Private/LocalSubnet TCP 8080 firewall rule.
- Gate: PowerShell parser reports zero syntax errors and `test_windows_assets.py -k install` passes

- [x] T-10.30 — GREEN: add Windows diagnostics and data-preserving uninstall.
- Agent: build
- Files: `deploy/windows/Test-PersonalFinance.ps1:new`, `deploy/windows/Uninstall-PersonalFinance.ps1:new`
- Principles applied: §10.1 KISS, §10.6 SDD, §10.7 Clean Code
- Patch (synthesis): Report task/firewall/health/ACL status without secrets; uninstall removes tasks, firewall and application files but never ProgramData, SQLite or backups.
- Gate: PowerShell parser reports zero syntax errors and `test_windows_assets.py -k "diagnostics or uninstall"` passes

- [x] T-10.31 — RED/GREEN: run a packaged HTTP-LAN smoke flow on Windows.
- Agent: build
- Files: `backend/tests/deployment/test_windows_http_smoke.py:new`, `deploy/windows/Start-PersonalFinance.ps1:1`
- Principles applied: §10.5 TDD, §10.6 SDD
- Patch (synthesis): Install the built wheel into a temporary Windows venv, migrate/bootstrap synthetic data, launch the wrapper on loopback HTTP with `http_lan`, prove login/session/unauthenticated denial and tear down all processes and temporaries.
- Gate: `cd backend && uv run pytest tests/deployment/test_windows_http_smoke.py`

- [ ] T-10.32 — GREEN: add the protected Windows deployment CI gate.
- Agent: build
- Files: `.github/workflows/quality.yml:1`
- Principles applied: §10.4 DRY, §10.6 SDD
- Patch (synthesis): Add `windows-deployment` on windows-latest with pinned existing actions, frozen uv install, Windows asset/session tests, PowerShell parse checks, wheel build and packaged HTTP smoke; upload sanitized diagnostics only on failure.
- Gate: workflow syntax resolves and the `windows-deployment` job passes in the PR

- [x] T-10.33 — GREEN: replace Linux deployment guidance with Windows runbooks.
- Agent: build
- Files: `docs/runbooks/install-lan.md:1`, `docs/runbooks/operations.md:1`, `docs/runbooks/acceptance.md:1`, `docs/runbooks/backup-restore.md:1`
- Principles applied: §10.1 KISS, §10.4 DRY, §10.7 Clean Code
- Patch (synthesis): Document private IPv4 reservation, elevated install, Task Scheduler, firewall, logs, backup/restore, restart diagnosis and sanitized HITL evidence; remove certificates, CA, systemd and POSIX paths.
- Gate: every documented command references a shipped PowerShell script or CLI and `test_windows_assets.py -k runbook` passes

- [x] T-10.13 — HITL: inspect deployment evidence on the household environment.
- Agent: guard
- Files: `docs/runbooks/acceptance.md:1`
- Principles applied: §10.6 SDD, §10.7 Clean Code
- Patch (synthesis): Read-only inspect sanitized operator output for the two Windows tasks, Private/LocalSubnet TCP 8080 firewall rule, HTTP access from a second Windows LAN client, unauthenticated denial, restart persistence, daily backup and isolated restoration; request confirmation and stop if evidence/environment is unavailable.
- Gate: operator explicitly confirms the inspected AC-001/AC-010/AC-011 evidence

- [x] T-10.21 — Record confirmed household acceptance evidence.
- Agent: build
- Files: `docs/runbooks/acceptance.md:1`
- Principles applied: §10.4 DRY, §10.6 SDD
- Patch (synthesis): After T-10.13 approval only, record sanitized commands/results, dates and pass/fail references without hostnames, credentials, paths or financial data.
- Gate: guard re-reads the record and finds it consistent with the operator-confirmed evidence

- [x] T-10.8 — Run final backend, frontend, migration and recovery gates.
- Agent: verify
- Files: `backend/:1`, `frontend/:1`, `deploy/:1`
- Principles applied: §10.5 TDD, §10.6 SDD, §10.7 Clean Code
- Patch (synthesis): Execute full suites, 80% coverage, linters, type checks, production build, migration on blank DB, backup integrity and isolated restoration; do not edit during verification.
- Gate: `cd backend && uv run pytest --cov=app --cov-fail-under=80 && uv run ruff check . && uv run ty check` plus `cd frontend && npm run lint && npm run typecheck && npm test -- --run && npm run build && npm run e2e`

- [x] T-10.9 — Update product and operator documentation from verified behavior.
- Agent: build
- Files: `README.md:1`, `CHANGELOG.md:1`, `.ai-engineering/solution-intent.md:1`, `docs/architecture.md:new`, `docs/runbooks/acceptance.md:new`
- Principles applied: §10.4 DRY, §10.6 SDD, §10.7 Clean Code
- Patch (synthesis): Record actual Windows setup, module boundaries, supported clients, explicit HTTP-LAN risk, Task Scheduler/firewall behavior, backup/restore evidence and roadmap; change spec-001 status references only to the lifecycle state actually reached.
- Gate: links resolve, commands match lockfiles and every AC-001–AC-011 maps to reproducible evidence

- [x] T-10.10 — Perform the regulated final quality and security review.
- Agent: guard
- Files: `.ai-engineering/specs/spec.md:1`, `.ai-engineering/specs/plan.md:1`, `backend/:1`, `frontend/:1`, `deploy/:1`
- Principles applied: §10.6 SDD, §10.7 Clean Code
- Patch (synthesis): Review requirement coverage, secrets, dependency findings, suppressions, module boundaries, accessible language and recovery evidence; report blockers without implementation edits.
- Gate: `ai-eng check && ai-eng verify` reports no blocker/critical/high finding and the restoration evidence is attached

## Completion gate

The plan is complete only when every current task is checked, AC-001 through
AC-011 have reproducible evidence, backend/frontend/Windows gates pass, the
deployed application is usable at `http://<IPv4-privada>:8080` from a second
Windows LAN device, the firewall is limited to Private+LocalSubnet, restart
persistence is demonstrated, and a backup has been restored into an isolated
destination with known balances intact.

## Plan self-review

- **Scope:** Every goal and acceptance criterion maps to at least one RED/GREEN
  pair or final verification task; non-goals are not introduced.
- **Architecture:** The selected modular-monolith/hexagonal pattern matches the
  canonical reference and the approved single-service constraint.
- **Safety:** Financial writes are atomic, exact, idempotent and immutable;
  security and recovery fail loud.
- **Execution route:** One reopened Windows deployment concern uses `/ai-build`;
  re-running `/ai-autopilot` would repeat nine completed concerns and reuse a
  terminally exhausted manifest.
- **Open questions:** None block implementation. Exact dependency patch versions
  are resolved into lockfiles during Phase 1. Final acceptance remains
  deliberately HITL until the operator supplies the Windows host and second LAN
  client declared above.
