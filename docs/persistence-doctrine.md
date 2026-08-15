# Doctrina de persistencia

Personal Finance utiliza un modelo **files-only**: cada dato durable tiene un
único almacén writable y cualquier índice, proyección o caché debe poder
reconstruirse desde esa fuente. Una proyección nunca se edita para cambiar la
verdad que representa.

## Tres niveles

| Nivel | Propósito | Propiedades |
|---|---|---|
| NDJSON | Auditoría append-only de hechos y controles | Se añade al final; no sustituye la configuración ni la intención humana |
| JSON/YAML | Registros estructurados, lifecycle y configuración operativa | Escritura validada por esquema; un archivo canónico por dato |
| Markdown | Intención, decisiones de diseño y documentación para personas | Rationale durable; las copias generadas son sólo distribución |

## Mapa canónico y reconstrucción

| Dato | Almacén writable canónico | Derivados o cachés | Reconstrucción / verificación |
|---|---|---|---|
| Identidad, misión y prohibiciones del proyecto | `CONSTITUTION.md` | Mirrors de instrucciones que enlazan la constitución | `python scripts/sync_mirrors/core.py --check` |
| Configuración de ai-eng | `.ai-engineering/manifest.yml` | Defaults inyectados por el loader | `ai-eng check` |
| Lifecycle de una spec | `.ai-engineering/state/specs/spec-NNN.json` | `_history.md` y frontmatter/snapshot archivado | `python .ai-engineering/scripts/spec_lifecycle.py check_ledger` |
| Decisiones de diseño de una entrega | Sección `## Decisions` de la spec Markdown aprobada/archivada | Entradas de consulta en `decision-store.json` y memoria read-side | `ai-eng decision backfill` |
| Aceptaciones de riesgo y su vigencia | `.ai-engineering/state/decision-store.json` | Informes de gobierno | `ai-eng audit verify --file decisions` y `ai-eng decision expire-check` |
| Eventos de auditoría del framework | `.ai-engineering/state/framework-events.ndjson` | Métricas o vistas derivadas | `ai-eng audit verify` |
| Arquitectura/intención de solución | `.ai-engineering/solution-intent.md` | Resúmenes de PR o portal documental | `/ai-docs solution-intent-sync` |
| Datos financieros operativos | SQLite bajo `%ProgramData%\PersonalFinance` | Saldos, informes y candidatos consultados | Reabrir la copia, `PRAGMA integrity_check` y recalcular proyecciones mediante la aplicación |
| Configuración operativa instalada | Archivo de configuración bajo `%ProgramData%\PersonalFinance` | Variables de proceso de la tarea programada | Reinstalar/reiniciar la tarea y verificar `/health/ready` |
| Assets frontend instalados | Build de `frontend` empaquetado en el wheel | Assets servidos por FastAPI | `npm run build`, construir/reinstalar el wheel y comparar hashes instalados/servidos |

Los comandos `/ai-docs ...` son invocaciones de skill en la superficie de
agente, no equivalentes sintéticos de terminal.

## Decisiones y riesgos no son el mismo dato

La spec Markdown es la fuente de verdad de una decisión de diseño porque
conserva contexto, alternativas, rationale y trazabilidad con criterios de
aceptación. `decision-store.json` puede indexar esas decisiones para consulta,
pero esa proyección se reemplaza mediante `ai-eng decision backfill`; no se
edita para reescribir el significado de una spec.

Una aceptación de riesgo sí usa `decision-store.json` como registro canónico:
necesita identidad del finding, severidad, vigencia, renovación y estado de
remediación machine-readable. El texto explicativo puede enlazarla, pero no
duplica su lifecycle.

## Reglas de escritura y recuperación

1. Antes de escribir, identificar el dato y su fila en la tabla anterior.
2. Escribir sólo en el almacén canónico; regenerar los derivados con el comando
   indicado.
3. Si un derivado discrepa, corregir la fuente o el generador, no ambas copias.
4. Los logs NDJSON son evidencia append-only: no se usan como configuración ni
   se corrigen retrospectivamente.
5. Los índices read-side administrados por el framework nunca justifican una
   decisión por sí solos. El proyecto no los escribe ni declara un comando de
   reconstrucción que la versión instalada no exponga.
6. `%ProgramData%\PersonalFinance` contiene datos de la persona operadora. Los
   despliegues no lo sobrescriben ni eliminan.
7. Una copia financiera sólo cuenta como recuperable después de abrirse,
   superar integridad SQLite y permitir recalcular saldos conocidos en un
   destino aislado.

## Drift y gates

- `ai-eng check` valida integridad de contenidos y mirrors.
- `python .ai-engineering/scripts/spec_lifecycle.py check_ledger` compara
  sidecars, historia y archivos de lifecycle.
- `ai-eng decision backfill` reconstruye la proyección de decisiones de specs;
  `ai-eng audit verify --file decisions` verifica su cadena y
  `ai-eng decision expire-check` valida riesgos vigentes.
- Los enlaces de esta doctrina deben resolver desde `AGENTS.md` y las demás
  superficies que la referencien.
- Los artefactos vendorizados o marcados `generated-do-not-edit` se corrigen en
  su fuente upstream; el proyecto sólo repara sus propios datos y snapshots.
