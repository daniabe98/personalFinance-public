# Aceptación doméstica

Estado: **pendiente de evidencia HITL en Linux/systemd y cliente LAN**.

No pegues hostname, IP, usuario, rutas domésticas, tokens, cookies, credenciales
ni cifras financieras. Registra únicamente fecha, identificador anónimo del
entorno, comando reducido y `PASS`/`FAIL`.

| Control | Evidencia requerida | Resultado |
|---|---|---|
| AC-001 acceso HTTPS | Cliente confía en CA, login sin warning | PENDIENTE |
| AC-002–AC-009 flujos | E2E del wheel, dos ejecuciones limpias | AUTOMATIZABLE |
| AC-010 operación | unit y timer activos; HTTP cerrado; reinicio conserva datos | PENDIENTE |
| AC-011 recuperación | backup diario válido y restore aislado verificado | PENDIENTE |

## Plantilla HITL

- Fecha UTC: `<AAAA-MM-DD>`
- Entorno anónimo: `<linux-lan-1>`
- `systemctl is-active personal-finance.service`: `<PASS|FAIL>`
- `systemctl is-active personal-finance-backup.timer`: `<PASS|FAIL>`
- HTTPS confiado desde cliente admitido: `<PASS|FAIL>`
- HTTP LAN cerrado: `<PASS|FAIL>`
- Persistencia tras reinicio: `<PASS|FAIL>`
- Backup y restore aislado: `<PASS|FAIL>`
- Confirmación expresa de la persona operadora: `<PENDIENTE|CONFIRMADO>`

No cambies `PENDIENTE` a `CONFIRMADO` desde Windows ni mediante parseo estático.
