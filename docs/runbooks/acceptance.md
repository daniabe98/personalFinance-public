# Aceptación doméstica Windows

Estado: **aceptación HITL confirmada en un host Windows y un segundo cliente
Windows de la LAN el 2026-08-10**.

No pegues hostname, IP, usuario, rutas domésticas, tokens, cookies, credenciales
ni cifras financieras. Registra únicamente fecha, identificador anónimo del
entorno, comprobación reducida y `PASS`/`FAIL`.

| Control | Evidencia requerida | Resultado |
|---|---|---|
| AC-001 acceso HTTP LAN | Login por `http://<IP-privada>:8080`; API sin sesión devuelve 401; diagnóstico de regla Private+LocalSubnet | PASS |
| AC-002–AC-009 flujos | Flujos financieros, borradores, anulación, conciliación e informes; E2E y checks existentes | PASS |
| AC-010 recuperación | Backup diario y restore aislado con integridad SQLite `ok`; diagnóstico de la tarea diaria | PASS |
| AC-011 reinicio y auditoría | Arranque automático, disponibilidad y persistencia después del reinicio; checks de auditoría | PASS |

### Trazabilidad automatizada

| Criterio | Evidencia reproducible principal |
|---|---|
| AC-001 | `backend/tests/api/test_session_security.py`, `backend/tests/deployment/test_windows_http_smoke.py`, `backend/tests/deployment/test_windows_assets.py` |
| AC-002 | `backend/tests/integration/ledger/test_catalog.py`, `frontend/e2e/access-and-commands.spec.ts` |
| AC-003–AC-005 | `backend/tests/acceptance/test_core_operations.py`, `frontend/e2e/access-and-commands.spec.ts` |
| AC-006 | `backend/tests/integration/ledger/test_command_atomicity.py`, `backend/tests/integration/ledger/test_idempotency.py`, `backend/tests/integration/persistence/test_posting_guard.py` |
| AC-007 | `backend/tests/acceptance/test_reversal.py`, `frontend/e2e/control-and-views.spec.ts` |
| AC-008 | `backend/tests/acceptance/test_reconciliation.py`, `frontend/e2e/control-and-views.spec.ts` |
| AC-009 | `backend/tests/acceptance/test_basic_reports.py`, `frontend/e2e/control-and-views.spec.ts` |
| AC-010 | `backend/tests/integration/recovery/test_backup.py`, `backend/tests/acceptance/test_restore.py`, `backend/tests/deployment/test_windows_assets.py` |
| AC-011 | `backend/tests/integration/audit/test_audit_events.py`, `backend/tests/api/test_audit_api.py`, `backend/tests/deployment/test_windows_assets.py` |

## Evidencia confirmada

- Fecha UTC: `2026-08-10`
- Entorno anónimo: `windows-lan-1`
- Diagnóstico `Test-PersonalFinance.ps1`: `PASS`
- Acceso y login desde segundo cliente Windows: `PASS`
- Flujos financieros básicos: `PASS`
- Borradores y anulación: `PASS`
- Conciliación e informes: `PASS`
- API sin sesión devuelve 401: `PASS`
- Regla limitada al perfil Privado, TCP 8080 y `LocalSubnet`: `PASS`
- Arranque automático y diagnóstico después del reinicio: `PASS`
- Persistencia después del reinicio: `PASS`
- Backup diario: `PASS`
- Restauración aislada: `PASS`
- `PRAGMA integrity_check = ok`: `PASS`
- Confirmación expresa de la persona operadora: `CONFIRMADO`

La evidencia se registró sin hostname, IP, usuario, rutas domésticas,
credenciales, cookies, cifras ni contenido financiero. La comprobación del
firewall, las tareas, las ACL, la disponibilidad y el backup procede del
diagnóstico instalado; las interacciones y el reinicio fueron confirmados por
la persona operadora desde el entorno doméstico real.

## Plantilla para futuras repeticiones HITL

- Fecha UTC: `<AAAA-MM-DD>`
- Entorno anónimo: `<windows-lan-1>`
- Diagnóstico `Test-PersonalFinance.ps1`: `<PASS|FAIL>`
- Acceso y login desde segundo cliente Windows: `<PASS|FAIL>`
- API sin sesión devuelve 401: `<PASS|FAIL>`
- Puerto limitado a perfil Privado y LocalSubnet: `<PASS|FAIL>`
- Ambas tareas activas y recuperación de ejecución perdida: `<PASS|FAIL>`
- Persistencia tras reinicio: `<PASS|FAIL>`
- Backup diario y restore aislado (`PRAGMA integrity_check = ok`): `<PASS|FAIL>`
- Confirmación expresa de la persona operadora: `<PENDIENTE|CONFIRMADO>`

No cambies `PENDIENTE` a `CONFIRMADO` mediante pruebas automatizadas ni parseo
estático. La confirmación pertenece a la persona que opera los dos equipos.
