---
spec: spec-002
title: Rediseño visual de actividad del periodo
status: approved
pipeline: standard
execution_route:
  version: 1
  spec: spec-002
  executor: build
  automation: dispatch
  concern_count: 1
  estimated_files: 4
  reason: "Un único cambio visual localizado con pruebas unitarias y E2E."
  safe_next_command: "/ai-build"
---

# Plan — Rediseño visual de actividad del periodo

## Design

Design intent captured at
`.ai-engineering/specs/spec-002/design-intent.md` (auto-routed from `/ai-plan`
because matched keywords: component, layout, frontend, interface, responsive,
accessibility).

## Architecture

**Ad-hoc presentational component local**. La transformación de fecha, importe y
copia accesible permanece como funciones puras junto a `EconomicReportView`; el
CSS se limita al prefijo `activity-*`. No se introduce estado, servicio ni capa
arquitectónica nueva porque el contrato de datos no cambia.

## Phase 1 — RED

- [x] T-1 — Fijar el contrato unitario y sanear los fixtures económicos — DONE
- Agent: build
- Files: `frontend/src/features/reports/reports.test.tsx`
- Principles applied: §10.5 TDD, §10.7 Clean Code
- Patch (deterministic): añadir expectativas para fecha localizada, semántica
  neutral, signos, nombre accesible y tolerancia cero; alinear el fixture normal
  con fechas y totales producibles por el backend.
- Gate: `npm --prefix frontend test -- --run src/features/reports/reports.test.tsx`

- [x] T-2 — Fijar el contrato E2E responsive y accesible — DONE
- Agent: build
- Files: `frontend/e2e/control-and-views.spec.ts`
- Principles applied: §10.5 TDD, §10.3 SOLID
- Patch (deterministic): ampliar el escenario real existente con aserciones de
  `time[datetime]`, copia neutral, signos, nombres accesibles, grid, foco,
  objetivo 48×48 y ausencia de overflow a 375/768/1024/1440 px.
- Gate: `npm --prefix frontend run e2e -- e2e/control-and-views.spec.ts`

## Phase 2 — GREEN

- [x] T-3 — Implementar el marcado editorial accesible — DONE
- Agent: build
- Files: `frontend/src/features/reports/economic.tsx`
- Principles applied: §10.3 SOLID, §10.7 Clean Code
- Patch (deterministic): incorporar funciones puras de presentación, clases
  `activity-*`, `time[datetime]`, importe firmado y acción «Ver detalle» con
  nombre accesible único, sin alterar el `href`, el orden ni los datos.
- Gate: `npm --prefix frontend test -- --run src/features/reports/reports.test.tsx && npm --prefix frontend run typecheck`

- [x] T-4 — Aplicar layout, jerarquía y estados responsive — DONE
- Agent: build
- Files: `frontend/src/styles/global.css`
- Principles applied: §10.3 SOLID, §10.7 Clean Code
- Patch (deterministic): añadir únicamente selectores `activity-*`, mobile-first,
  tres columnas desde 48 rem, filas reflow, contraste semántico, 48×48, hover de
  puntero fino y números tabulares.
- Gate: `npm --prefix frontend run format:check && npm --prefix frontend run lint && npm --prefix frontend run e2e -- e2e/control-and-views.spec.ts`

## Phase 3 — Integración

- [x] T-5 — Verificar el changeset completo — DONE_WITH_CONCERNS (el `format:check` global detecta CRLF de checkout en 68 archivos preexistentes; los cuatro archivos del cambio pasan Prettier)
- Agent: verify
- Files: los cuatro archivos de implementación y prueba de este plan
- Principles applied: §10.5 TDD, §10.7 Clean Code
- Patch (deterministic): no aplica; tarea de verificación de solo lectura.
- Gate: `npm --prefix frontend run format:check`; `npm --prefix frontend run lint`;
  `npm --prefix frontend run typecheck`; `npm --prefix frontend test -- --run`;
  `npm --prefix frontend run test:coverage`; `npm --prefix frontend run build`;
  `npm --prefix frontend run e2e -- e2e/control-and-views.spec.ts`;
  `npm --prefix frontend audit --omit=dev --audit-level=high`.

## Risks and Controls

- La prueba normal no representa estados imposibles del productor; el cero se
  cubre únicamente con render directo del componente.
- La revisión debe rechazar cualquier inferencia Ingreso/Gasto basada en signo.
- Los selectores CSS nuevos no pueden afectar `.item-list` ni `.report-totals`
  fuera de esta vista.
- No se modifican backend, API, esquemas, dependencias ni lockfile.

## Quality Outcome

Initial assessment: 0 blockers, 0 criticals, 0 highs -> PASS (96/100,
WARN por dos hallazgos low de infraestructura preexistente: CRLF global en
Windows y contadores de plan no proyectados por `ai-eng spec verify`).

## Quality Remediation

used: false
max_attempts: 1
final_reassessment: not-required

safe_next_command: `/ai-build`
