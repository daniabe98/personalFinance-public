---
total: 46
completed: 0
spec: spec-003
title: Rediseño visual y rigor de flujos del frontend
status: approved
pipeline: full
phases: 8
execution_route:
  version: 1
  spec: spec-003
  executor: autopilot
  automation: hitl
  concern_count: 8
  estimated_files: 52
  reason: "Entrega full-stack de ocho preocupaciones, más de diez archivos, gates multi-stack, PR y despliegue operacional verificado."
  safe_next_command: "/ai-autopilot"
---

# Plan — Spec 003: Rediseño visual y rigor de flujos del frontend

## Design

Design intent captured at
`.ai-engineering/specs/spec-003/design-intent.md` (auto-routed from `/ai-plan`
because matched keywords: component, screen, form, modal, layout, ui, frontend,
interface, responsive, accessibility).

La ejecución conserva «Libro abierto, cifras en contexto», las fuentes y tokens
existentes, SVG nativo, WCAG AA, reflow a 375/768/1024/1440 px y ausencia de
librerías de gráficos.

## Architecture

**Monolito modular con arquitectura hexagonal y adaptadores de presentación**.
La regla de descripción pertenece a `ledger` dominio/aplicación; FastAPI valida
el contrato HTTP y SQLAlchemy conserva lectura nullable histórica. `reporting`
y `reconciliation` enriquecen proyecciones desde el ledger canónico sin cambiar
cálculos. React mantiene sólo estado presentacional. No se añade tabla,
migración, caché, servicio ni dependencia de runtime.

Límites: dominio sin imports de infraestructura; descripción obligatoria en
comandos nuevos pero nullable en `Transaction`/SQL; modal bajo demanda mediante
detalle + catálogos incluidos archivados; gráficos sin porcentajes/tendencias;
mirrors regenerados desde su fuente y nunca editados como copias independientes.

## Dependencies

Orden: baseline → RED descripción → GREEN dominio/API → RED/GREEN proyecciones
→ generación OpenAPI → RED/GREEN frontend → accesibilidad responsive →
gobernanza → gates → PR/merge → despliegue. Ningún GREEN comienza sin observar
su RED fallar por la razón esperada.

## Phase 0 — Baseline

- [ ] T-0.1 — Capturar lifecycle y baseline canónicos
- Agent: verify
- Files: `.ai-engineering/specs/spec.md:1`; `.ai-engineering/state/specs/spec-003.json:1`; repositorio completo (read-only)
- Principles applied: §10.5 TDD, §10.6 SDD
- Patch (deterministic): no aplica; registrar status, Git y suites focalizadas antes de editar producto.
- Gate: `python .ai-engineering/scripts/spec_lifecycle.py status spec-003`; `git status --short --branch`; `cd backend && uv run pytest tests/unit/ledger tests/api/test_finance_api.py tests/api/test_openapi_contract.py -q`; `npm --prefix frontend test -- --run`.
- Depends on: ninguna.

## Phase 1 — Descripción obligatoria y legado seguro

- [ ] T-1.1 — RED: fijar normalización y descripción de reversión
- Agent: build
- Files: `backend/tests/unit/ledger/test_description.py:1` (nuevo)
- Principles applied: §10.1 KISS, §10.5 TDD, §10.8 Hexagonal Architecture
- Patch (deterministic): casos trim, vacío/espacios, 500/501, fallback legacy y truncado de `Reversión de: …`.
- Gate: `cd backend && uv run pytest tests/unit/ledger/test_description.py -q` falla por helper ausente.
- Depends on: T-0.1.

- [ ] T-1.2 — RED: proteger altas, drafts y posteo legacy
- Agent: build
- Files: `backend/tests/integration/ledger/test_draft_commands.py:30`; `backend/tests/acceptance/test_core_operations.py:22`
- Principles applied: §10.5 TDD, §10.6 SDD, §10.8 Hexagonal Architecture
- Patch (deterministic): matriz opening/income/expense/transfer/draft que rechaza descripción inválida, persiste trim y permite leer pero no postear draft legacy nulo.
- Gate: `cd backend && uv run pytest tests/integration/ledger/test_draft_commands.py tests/acceptance/test_core_operations.py -q` falla en los nuevos casos.
- Depends on: T-1.1.

- [ ] T-1.3 — RED: fijar 422 y OpenAPI de escritura/lectura
- Agent: build
- Files: `backend/tests/api/test_finance_api.py:102`; `backend/tests/api/test_openapi_contract.py:35`
- Principles applied: §10.5 TDD, §10.6 SDD
- Patch (deterministic): payloads omitido/vacío/espacios/>500; escritura required, lectura nullable y reversal sin descripción manual.
- Gate: `cd backend && uv run pytest tests/api/test_finance_api.py tests/api/test_openapi_contract.py -q` falla con contrato opcional.
- Depends on: T-1.2.

- [ ] T-1.4 — GREEN: implementar valor de descripción de dominio
- Agent: build
- Files: `backend/app/ledger/domain/description.py:1` (nuevo)
- Principles applied: §10.1 KISS, §10.3 SOLID, §10.8 Hexagonal Architecture
- Patch (deterministic): funciones puras `normalize_required_description` y `reversal_description`, máximo 500 y `InvalidLifecycleError`, sin infraestructura.
- Gate: `cd backend && uv run pytest tests/unit/ledger/test_description.py -q`.
- Depends on: T-1.1, T-1.3.

- [ ] T-1.5 — GREEN: aplicar regla en comandos y posteo de drafts
- Agent: build
- Files: `backend/app/ledger/application/commands.py:25`; `backend/app/ledger/application/handlers.py:47`
- Principles applied: §10.3 SOLID, §10.5 TDD, §10.8 Hexagonal Architecture
- Patch (deterministic): normalizar antes de persistir, tipar escrituras nuevas como `str` y rechazar posteo legacy sin tocar `Transaction.description` ni la columna nullable.
- Gate: `cd backend && uv run pytest tests/integration/ledger/test_draft_commands.py tests/acceptance/test_core_operations.py -q`.
- Depends on: T-1.4.

- [ ] T-1.6 — GREEN: derivar reversión y cerrar FastAPI
- Agent: build
- Files: `backend/app/ledger/application/reversal.py:29`; `backend/app/api/transactions.py:68`; `backend/tests/acceptance/test_reversal.py:23`
- Principles applied: §10.1 KISS, §10.5 TDD, §10.6 SDD
- Patch (deterministic): construir descripción desde original, retirar texto libre de request/comando e introducir string Pydantic required con trim/min/max en altas/drafts; response sigue nullable.
- Gate: `cd backend && uv run pytest tests/acceptance/test_reversal.py tests/api/test_finance_api.py tests/api/test_openapi_contract.py -q`.
- Depends on: T-1.3, T-1.5.

- [ ] T-1.7 — Verificar que no existe migración ni backfill
- Agent: verify
- Files: `backend/app/shared/models_ledger.py:95`; `backend/alembic/versions`; `backend/tests/integration/persistence/test_migrations.py:1`
- Principles applied: §10.2 YAGNI, §10.6 SDD, §10.8 Hexagonal Architecture
- Patch (deterministic): no aplica; inspección de columna y diff Alembic.
- Gate: `cd backend && uv run pytest tests/integration/persistence/test_migrations.py tests/unit/ledger/test_transaction.py -q`; `git diff -- backend/alembic/versions` vacío.
- Depends on: T-1.6.

## Phase 2 — Proyecciones y contratos generados

- [ ] T-2.1 — RED: exigir descripción nullable en reporting
- Agent: build
- Files: `backend/tests/acceptance/test_basic_reports.py:28`
- Principles applied: §10.5 TDD, §10.6 SDD, §10.8 Hexagonal Architecture
- Patch (deterministic): afirmar descripción original y `None` legacy sin cambiar orden, importes ni reversión entre periodos.
- Gate: `cd backend && uv run pytest tests/acceptance/test_basic_reports.py -q` falla por campo ausente.
- Depends on: T-1.7.

- [ ] T-2.2 — RED: exigir descripción y kind en conciliación
- Agent: build
- Files: `backend/tests/acceptance/test_reconciliation.py:243`; `backend/tests/unit/reconciliation/test_reconciliation.py:1`
- Principles applied: §10.5 TDD, §10.6 SDD, §10.8 Hexagonal Architecture
- Patch (deterministic): afirmar campos desde ledger, incluido OPENING, sin alterar elegibilidad ni efecto firmado.
- Gate: `cd backend && uv run pytest tests/unit/reconciliation/test_reconciliation.py tests/acceptance/test_reconciliation.py -q` falla por campos ausentes.
- Depends on: T-1.7.

- [ ] T-2.3 — GREEN: enriquecer reporting extremo a extremo
- Agent: build
- Files: `backend/app/reporting/domain/dtos.py:28`; `backend/app/reporting/adapters/sql_queries.py:51`; `backend/app/reporting/application/queries.py:129`; `backend/app/api/reports.py:30`
- Principles applied: §10.3 SOLID, §10.4 DRY, §10.8 Hexagonal Architecture
- Patch (deterministic): transportar `TransactionRecord.description` por DTO/contribution/HTTP sin fallback ni cambios de cálculo.
- Gate: `cd backend && uv run pytest tests/acceptance/test_basic_reports.py tests/api/test_openapi_contract.py -q`.
- Depends on: T-2.1.

- [ ] T-2.4 — GREEN: enriquecer conciliación extremo a extremo
- Agent: build
- Files: `backend/app/reconciliation/domain/reconciliation.py:30`; `backend/app/reconciliation/adapters/repository.py:40`; `backend/app/api/reconciliations.py:69`
- Principles applied: §10.3 SOLID, §10.4 DRY, §10.8 Hexagonal Architecture
- Patch (deterministic): transportar description/kind; selección/cálculo continúan dependiendo sólo de IDs y céntimos.
- Gate: `cd backend && uv run pytest tests/unit/reconciliation/test_reconciliation.py tests/acceptance/test_reconciliation.py -q`.
- Depends on: T-2.2.

- [ ] T-2.5 — RED/GREEN: regenerar OpenAPI y tipos cerrados
- Agent: build
- Files: `frontend/src/api/contract.test.ts:13`; `frontend/openapi.json:1`; `frontend/src/api/schema.d.ts:1`
- Principles applied: §10.4 DRY, §10.5 TDD, §10.6 SDD
- Patch (deterministic): primero expectativas de required/nullable/candidate/contribution; después `npm --prefix frontend run api:generate`, nunca edición manual de generados.
- Gate: observar RED en `npm --prefix frontend test -- --run src/api/contract.test.ts`; después `npm --prefix frontend run api:check` y test verde.
- Depends on: T-1.6, T-2.3, T-2.4.

- [ ] T-2.6 — Verificar límites modulares
- Agent: verify
- Files: `backend/tests/architecture/test_module_boundaries.py:1`; módulos `ledger`, `reporting`, `reconciliation`
- Principles applied: §10.3 SOLID, §10.8 Hexagonal Architecture
- Patch (deterministic): no aplica; inspección de imports y prueba arquitectónica.
- Gate: `cd backend && uv run pytest tests/architecture/test_module_boundaries.py -q`.
- Depends on: T-2.5.

## Phase 3 — Formulario, detalle y métricas

- [ ] T-3.1 — RED: fijar descripción obligatoria en React
- Agent: build
- Files: `frontend/src/features/transactions/transaction-form.test.tsx:53`; `frontend/e2e/access-and-commands.spec.ts:118`
- Principles applied: §10.5 TDD, §10.6 SDD
- Patch (deterministic): label/ayuda 1–500, vacío/espacios/501, trim, revisión, legacy editable y reverse sólo con fechas.
- Gate: `npm --prefix frontend test -- --run src/features/transactions/transaction-form.test.tsx` falla con UI/payload actuales.
- Depends on: T-2.5.

- [ ] T-3.2 — GREEN: endurecer adapter y formulario
- Agent: build
- Files: `frontend/src/features/transactions/api.ts:8`; `frontend/src/features/transactions/form.tsx:45`; `frontend/src/features/transactions/reversal-dialog.tsx:1`
- Principles applied: §10.3 SOLID, §10.5 TDD, §10.7 Clean Code
- Patch (deterministic): `MovementInput.description: string`, validación/ayuda/resumen, retirar description manual de reverse y explicar derivación.
- Gate: `npm --prefix frontend test -- --run src/features/transactions/transaction-form.test.tsx`; `npm --prefix frontend run typecheck`.
- Depends on: T-3.1.

- [ ] T-3.3 — RED: fijar descripción/fallback y modal accesible
- Agent: build
- Files: `frontend/src/features/reports/reports.test.tsx:117`
- Principles applied: §10.5 TDD, §10.6 SDD, §10.7 Clean Code
- Patch (deterministic): descripción real/fallback, botón/URL estable, loading/error/ausencia, nombres/relaciones, Escape, trap y retorno de foco sin UUID visible.
- Gate: `npm --prefix frontend test -- --run src/features/reports/reports.test.tsx` falla con enlace/placeholder actuales.
- Depends on: T-2.5.

- [ ] T-3.4 — GREEN: componer detalle bajo demanda y diálogo
- Agent: build
- Files: `frontend/src/app.tsx:20`; `frontend/src/features/reports/summary.tsx:8`; `frontend/src/features/reports/movement-detail-dialog.tsx:1` (nuevo)
- Principles applied: §10.1 KISS, §10.3 SOLID, §10.5 TDD
- Patch (deterministic): consultar transaction + catálogos `include_archived=true` en paralelo, resolver nombres/ausencia y renderizar `<dialog>` con estados y foco correcto.
- Gate: `npm --prefix frontend test -- --run src/app.test.tsx src/features/reports/reports.test.tsx`; `npm --prefix frontend run typecheck`.
- Depends on: T-3.3.

- [ ] T-3.5 — GREEN: sustituir placeholder/enlace en Actividad
- Agent: build
- Files: `frontend/src/features/reports/economic.tsx:39`; `frontend/src/features/reports/summary.tsx:20`
- Principles applied: §10.3 SOLID, §10.5 TDD, §10.7 Clean Code
- Patch (deterministic): Contribution nullable, «Sin descripción» sólo legacy y botón que abre un único modal sin navegación.
- Gate: `npm --prefix frontend test -- --run src/features/reports/reports.test.tsx`.
- Depends on: T-3.4.

- [ ] T-3.6 — RED: fijar micrográficos honestos
- Agent: build
- Files: `frontend/src/features/reports/reports.test.tsx:117`; `frontend/e2e/control-and-views.spec.ts:156`
- Principles applied: §10.2 YAGNI, §10.5 TDD, §10.6 SDD
- Patch (deterministic): SVG/labels/cifras redundantes, cero/negativos/reversiones, sin porcentaje/tendencia y cuatro viewports.
- Gate: Vitest focalizado falla porque no hay gráficos.
- Depends on: T-3.5.

- [ ] T-3.7 — GREEN: implementar SVG compartido y fichas métricas
- Agent: build
- Files: `frontend/src/features/reports/composition-chart.tsx:1` (nuevo); `frontend/src/features/reports/cash.tsx:1`; `frontend/src/features/reports/net-worth.tsx:1`
- Principles applied: §10.1 KISS, §10.4 DRY, §10.5 TDD
- Patch (deterministic): escala visual por magnitud, estado neutral para cero/negativos, title/desc y leyenda; conservar tres cifras exactas por ficha.
- Gate: `npm --prefix frontend test -- --run src/features/reports/reports.test.tsx`; `npm --prefix frontend run typecheck`.
- Depends on: T-3.6.

## Phase 4 — Revisión, Organizar y Backup

- [ ] T-4.1 — RED: fijar conciliación progresiva y latest-request-wins
- Agent: build
- Files: `frontend/src/app.test.tsx:1`; `frontend/src/features/reconciliation/reconciliation.test.tsx:75`
- Principles applied: §10.5 TDD, §10.6 SDD
- Patch (deterministic): candidate real/fallback, estados incompleto/cargando/cuadrado/diferencia/error, preview automático y promesas resueltas fuera de orden.
- Gate: tests focalizados fallan por placeholder, botón manual y carrera.
- Depends on: T-2.5.

- [ ] T-4.2 — GREEN: consumir candidatos y automatizar preview
- Agent: build
- Files: `frontend/src/app.tsx:24`; `frontend/src/features/reconciliation/page.tsx:1`; `frontend/src/features/reconciliation/entry-list.tsx:3`
- Principles applied: §10.3 SOLID, §10.4 DRY, §10.5 TDD
- Patch (deterministic): mapear description/kind, derivar validez, cargar candidates/preview por efecto e invalidar respuestas antiguas con generación monotónica.
- Gate: `npm --prefix frontend test -- --run src/app.test.tsx src/features/reconciliation/reconciliation.test.tsx`; typecheck.
- Depends on: T-4.1.

- [ ] T-4.3 — GREEN: convertir Revisión en composición visual
- Agent: build
- Files: `frontend/src/features/reconciliation/summary.tsx:1`; `frontend/src/features/reconciliation/page.tsx:118`
- Principles applied: §10.3 SOLID, §10.5 TDD, §10.7 Clean Code
- Patch (deterministic): marco persistente, hitos progresivos, tres bloques canónicos y texto/icono redundante con `aria-live` moderado.
- Gate: `npm --prefix frontend test -- --run src/features/reconciliation/reconciliation.test.tsx`.
- Depends on: T-4.2.

- [ ] T-4.4 — RED: fijar tabs y filtro compartido
- Agent: build
- Files: `frontend/src/features/catalog/catalog.test.tsx:88`
- Principles applied: §10.5 TDD, §10.6 SDD
- Patch (deterministic): tablist/tab/tabpanel, flechas/Home/End, Activas/Archivadas compartido, formulario conservado y submit único.
- Gate: test focalizado falla con layout de dos columnas.
- Depends on: T-0.1.

- [ ] T-4.5 — GREEN: implementar tabs de ancho completo
- Agent: build
- Files: `frontend/src/features/catalog/page.tsx:36`
- Principles applied: §10.1 KISS, §10.3 SOLID, §10.5 TDD
- Patch (deterministic): active tab + roving tabindex, paneles asociados y cada formulario/lista en panel completo manteniendo `showArchived` común.
- Gate: `npm --prefix frontend test -- --run src/features/catalog/catalog.test.tsx`; typecheck.
- Depends on: T-4.4.

- [ ] T-4.6 — RED: fijar backup horizontal y cuatro estados
- Agent: build
- Files: `frontend/src/features/settings/settings.test.tsx:69`
- Principles applied: §10.5 TDD, §10.6 SDD
- Patch (deterministic): NEVER_RUN/PENDING/VERIFIED/FAILED, cinco hitos, fallo/runbook, `NOT_AVAILABLE` y ausencia de restore.
- Gate: test focalizado falla con lista/mapeo actuales.
- Depends on: T-0.1.

- [ ] T-4.7 — GREEN: implementar superficie de backup
- Agent: build
- Files: `frontend/src/features/settings/backup-status.tsx:1`
- Principles applied: §10.1 KISS, §10.3 SOLID, §10.5 TDD
- Patch (deterministic): estado principal con icono SVG + hitos horizontales, copia explícita y detalle de fallo/runbook; sin restore.
- Gate: `npm --prefix frontend test -- --run src/features/settings/settings.test.tsx`; `cd backend && uv run pytest tests/api/test_backup_status_api.py -q`.
- Depends on: T-4.6.

## Phase 5 — CSS, responsive y accesibilidad

- [ ] T-5.1 — RED: ampliar contraste, Axe, teclado y viewports
- Agent: build
- Files: `frontend/src/styles/control-views-contrast.test.ts:1`; `frontend/e2e/accessibility.spec.ts:3`; `frontend/e2e/control-and-views.spec.ts:156`
- Principles applied: §10.5 TDD, §10.6 SDD
- Patch (deterministic): selectores/tokens, 48 px, foco, modal/tabs, Axe y overflow/truncado a 375/768/1024/1440.
- Gate: tests fallan antes del CSS final por reglas/selectores ausentes.
- Depends on: T-3.7, T-4.3, T-4.5, T-4.7.

- [ ] T-5.2 — GREEN: aplicar estilos editoriales acotados
- Agent: build
- Files: `frontend/src/styles/global.css:190`; `frontend/src/styles/tokens.css:1`
- Principles applied: §10.3 SOLID, §10.4 DRY, §10.7 Clean Code
- Patch (deterministic): prefijos `movement-detail-*`, `composition-*`, `review-*`, `catalog-tabs-*`, `backup-*`; tokens existentes/color-mix, mobile-first, hover fino y reduced-motion.
- Gate: contraste test verde; format/lint/typecheck verdes.
- Depends on: T-5.1.

- [ ] T-5.3 — Verificar design intent completo
- Agent: verify
- Files: `.ai-engineering/specs/spec-003/design-intent.md:1`; frontend modificado (read-only)
- Principles applied: §10.6 SDD, §10.7 Clean Code
- Patch (deterministic): no aplica; cotejar checklist con DOM/CSS/tests; N/A sólo tema oscuro, imágenes y virtualización fuera de alcance.
- Gate: `npm --prefix frontend run e2e -- e2e/accessibility.spec.ts e2e/control-and-views.spec.ts`; Axe cero y sin overflow.
- Depends on: T-5.2.

## Phase 6 — Gobernanza y documentación

- [ ] T-6.1 — RED: demostrar estados spec-002 y link roto
- Agent: guard
- Files: `.ai-engineering/specs/archive/spec-002-activity-period-visual-redesign/spec.md:1`; `.ai-engineering/specs/archive/spec-002-activity-period-visual-redesign/plan.md:1`; `AGENTS.md:13`; `docs/persistence-doctrine.md:1`
- Principles applied: §10.4 DRY, §10.5 TDD, §10.6 SDD
- Patch (deterministic): aserciones read-only esperan done/shipped y archivo existente; deben fallar sólo por metadata/link conocidos.
- Gate: fallo exacto por `in-progress`, `approved` y doctrina ausente.
- Depends on: T-0.1.

- [ ] T-6.2 — GREEN: corregir metadata archivada spec-002
- Agent: build
- Files: `.ai-engineering/specs/archive/spec-002-activity-period-visual-redesign/spec.md:5`; `.ai-engineering/specs/archive/spec-002-activity-period-visual-redesign/plan.md:4`
- Principles applied: §10.4 DRY, §10.6 SDD
- Patch (deterministic):
  ```diff
  -status: in-progress
  +status: done
  -status: approved
  +status: shipped
  ```
- Gate: frontmatters coinciden con sidecar spec-002 y `python -m spec_lint --check` sin blocker.
- Depends on: T-6.1.

- [ ] T-6.3 — GREEN: crear doctrina y alinear knowledge placement
- Agent: build
- Files: `docs/persistence-doctrine.md:1` (nuevo); `.ai-engineering/reference/knowledge-placement.md:1`; `AGENTS.md:13` y mirror source si aplica
- Principles applied: §10.1 KISS, §10.4 DRY, §10.6 SDD
- Patch (deterministic): tres tiers, SSOT por dato, decisiones de spec en markdown, riesgos gobernados, decision-store derivado/rebuild `ai-eng decision backfill`, NDJSON audit y mirrors regenerables.
- Gate: enlaces resuelven; `rg` no deja contradicciones; ayuda/dry-run del rebuild verificable; sin edición manual de copias generadas.
- Depends on: T-6.2.

- [ ] T-6.4 — Documentar defecto lifecycle upstream
- Agent: build
- Files: `.ai-engineering/scripts/spec_lifecycle.py` (read-only); issue `arcasilesgroup/ai-engineering`
- Principles applied: §10.3 SOLID, §10.6 SDD
- Patch (deterministic): invocar `/ai-engineering-issue` con reproducción anónima, esperado/actual e impacto; enlazar en PR, no parche local.
- Gate: URL del issue y `git diff -- .ai-engineering/scripts/spec_lifecycle.py` vacío.
- Depends on: T-6.2.

- [ ] T-6.5 — Actualizar changelog/solution intent desde fuentes
- Agent: build
- Files: `CHANGELOG.md:1`; `.ai-engineering/solution-intent.md:1`; `README.md:1` sólo si `/ai-docs` lo determina
- Principles applied: §10.4 DRY, §10.6 SDD
- Patch (deterministic): ejecutar `/ai-docs`; no marcar spec-003 shipped antes del merge ni duplicar runbooks.
- Gate: links válidos, `git diff --check`, sin PII/rutas de operador.
- Depends on: T-5.3, T-6.3, T-6.4.

## Phase 7 — Gates regulados

- [ ] T-7.1 — Ejecutar calidad backend completa
- Agent: verify
- Files: `backend/app`; `backend/tests` (read-only)
- Principles applied: §10.5 TDD, §10.7 Clean Code, §10.8 Hexagonal Architecture
- Patch (deterministic): no aplica; formato, lint, tipos, arquitectura y cobertura.
- Gate: `cd backend && uv run ruff format --check . && uv run ruff check . && uv run ty check app && uv run pytest` con cobertura ≥80 %.
- Depends on: T-6.5.

- [ ] T-7.2 — Ejecutar calidad frontend completa
- Agent: verify
- Files: `frontend/src`; `frontend/e2e` (read-only)
- Principles applied: §10.5 TDD, §10.7 Clean Code
- Patch (deterministic): no aplica; formato, lint, tipos, contrato, cobertura, build y E2E.
- Gate: `npm --prefix frontend run format:check && npm --prefix frontend run lint && npm --prefix frontend run typecheck && npm --prefix frontend run api:check && npm --prefix frontend run test:coverage && npm --prefix frontend run build && npm --prefix frontend run e2e`.
- Depends on: T-7.1.

- [ ] T-7.3 — Ejecutar seguridad y gobierno fail-closed
- Agent: guard
- Files: repositorio completo (read-only)
- Principles applied: §10.4 DRY, §10.6 SDD
- Patch (deterministic): no aplica; gitleaks, pip-audit, npm audit, Semgrep en plataforma soportada, ai-eng/spec lint y trazabilidad AC/D.
- Gate: `gitleaks detect --source . --no-git`; `cd backend && uv run pip-audit`; `npm --prefix frontend run audit:ci`; `ai-eng check`; `ai-eng spec verify`; `python -m spec_lint --check`; sin HIGH/MEDIUM/CRITICAL ni blockers.
- Depends on: T-7.2.

- [ ] T-7.4 — Ejecutar review adversarial y remediación acotada
- Agent: guard
- Files: changeset completo (read-only; una remediación sólo para blocker/critical/high)
- Principles applied: §10.1 KISS, §10.3 SOLID, §10.7 Clean Code
- Patch (deterministic): `/ai-review` cubre finanzas, seguridad, carreras, accesibilidad, responsive y scope; máximo una pasada finding-scoped y reevaluación final.
- Gate: evaluación final sin blocker/critical/high; cualquier restante detiene el flujo.
- Depends on: T-7.3.

## Phase 8 — PR, merge y despliegue

- [ ] T-8.1 — Crear commit y PR gobernados
- Agent: build
- Files: changeset aprobado; metadata Git/GitHub
- Principles applied: §10.6 SDD, §10.7 Clean Code
- Patch (deterministic): `/ai-pr`, staging selectivo, Conventional Commit y cuerpo con AC/riesgos/issue; nunca `--no-verify`.
- Gate: PR contra `origin/main`, branch `codex/*`, árbol limpio y checks requeridos visibles.
- Depends on: T-7.4 y aprobación HITL del plan.

- [ ] T-8.2 — Vigilar CI, fusionar y consolidar lifecycle
- Agent: verify
- Files: GitHub PR/CI; sidecar/history/archive generados por lifecycle
- Principles applied: §10.4 DRY, §10.6 SDD
- Patch (deterministic): merge sólo en verde; usar cleanup lifecycle de `/ai-pr`, nunca editar `_history.md`/sidecar a mano.
- Gate: PR merged, checks incluido Windows verde, sidecar `shipped`, spec archivada `done`, plan `shipped`, sin spec activa.
- Depends on: T-8.1.

- [ ] T-8.3 — Sincronizar checkout operacional por fast-forward
- Agent: build
- Files: `C:\Users\MSI\Documents\personalFinance-public` (nunca `%ProgramData%`)
- Principles applied: §10.1 KISS, §10.6 SDD
- Patch (deterministic): `git fetch origin main` y `git pull --ff-only origin main`; abortar ante divergencia/cambios locales.
- Gate: checkout limpio y `HEAD == origin/main` del merge.
- Depends on: T-8.2.

- [ ] T-8.4 — Construir frontend y wheel operacionales
- Agent: build
- Files: artefactos de build en checkout operacional
- Principles applied: §10.5 TDD, §10.6 SDD
- Patch (deterministic): build frontend, integrar assets según pipeline existente y construir wheel desde checkout operacional.
- Gate: build y wheel verdes; wheel contiene assets recién generados.
- Depends on: T-8.3.

- [ ] T-8.5 — Reinstalar wheel y reiniciar tarea
- Agent: build
- Files: `C:\Program Files\PersonalFinance`; tarea `PersonalFinance-App`; `%ProgramData%\PersonalFinance` se preserva
- Principles applied: §10.1 KISS, §10.6 SDD
- Patch (deterministic): procedimiento PowerShell existente; nunca overwrite/delete de base, config, logs o backups.
- Gate: tarea activa sin reinicios repetidos ni error nuevo.
- Depends on: T-8.4.

- [ ] T-8.6 — Verificar readiness, hashes y smoke funcional
- Agent: verify
- Files: runtime instalado/endpoint local (read-only)
- Principles applied: §10.4 DRY, §10.5 TDD, §10.6 SDD
- Patch (deterministic): consultar readiness, comparar SHA-256 de assets y recorrer descripción/modal/métricas/Revisión/tabs/backup sin evidencia sensible.
- Gate: HTTP 200 `{"status":"ready"}`, hashes servidos=instalados, AC-003-01..08 trazados, ambos checkouts limpios/sincronizados.
- Depends on: T-8.5.

## Acceptance traceability

| AC | Tasks | Evidence |
|---|---|---|
| AC-003-01 | T-1.1–T-1.7, T-3.1–T-3.2 | unit/integration/API/OpenAPI/frontend/E2E |
| AC-003-02 | T-2.1–T-2.5, T-3.3–T-3.5 | reporting + modal/foco/URL |
| AC-003-03 | T-3.6–T-3.7, T-5.1–T-5.3 | SVG/zero/negative + viewports |
| AC-003-04 | T-4.1–T-4.3 | carrera + preview canónico + E2E |
| AC-003-05 | T-4.4–T-4.5, T-5.1–T-5.3 | teclado/tabs + acciones intactas |
| AC-003-06 | T-4.6–T-4.7, T-5.1–T-5.3 | estados/no restore/responsive |
| AC-003-07 | T-6.1–T-6.5, T-7.3, T-8.2 | metadata/links/SSOT/issue/lifecycle |
| AC-003-08 | T-7.1–T-7.4, T-8.1–T-8.6 | gates/CI/build/readiness/hashes |

## Risks and controls

- Legado: sin migración/backfill; columna nullable y tests de lectura.
- Gráficos: cifras firmadas primarias; neutral para cero/negativos; no tendencia.
- Preview: generación monotónica latest-request-wins con test inverso.
- Accesibilidad: semántica nativa, foco, Axe, teclado y cuatro viewports.
- CSS: selectores prefijados y tokens existentes.
- Lifecycle: issue upstream; diff del script vendorizado vacío.
- Operación: `%ProgramData%\PersonalFinance` nunca se sobrescribe/elimina y el
  despliegue ocurre desde checkout operacional sólo después de merge/CI verde.

## Plan self-review

- Ronda 1: corregidos tres huecos —draft legacy, catálogos archivados en modal
  y hashes post-merge— en T-1.2/T-1.5, T-3.4 y T-8.3–T-8.6.
- Ronda 2: 0 blockers, 0 criticals, 0 highs. Todas las tareas incluyen agent,
  files, principios, patch/guidance, gate y dependencias; cada GREEN tiene RED
  previo y AC-003-01..08 están trazados.

## Approval gate

El plan permanece `draft`. `/ai-autopilot` no puede ejecutarlo hasta aprobación
explícita del operador y transición del plan a `approved`.

safe_next_command: `/ai-autopilot`
