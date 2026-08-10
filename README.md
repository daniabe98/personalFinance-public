# Personal Finance

Aplicación web privada para registrar, consultar y analizar las finanzas del
hogar con rigor contable y lenguaje accesible. La primera entrega funciona como
un único servicio en Windows 10/11 x64 y se utiliza desde navegadores Windows de
la misma red doméstica.

## Funcionalidad

- saldo inicial, ingresos, gastos y transferencias;
- borradores, contabilización, reversión y conciliación;
- saldos, patrimonio, devengo y tesorería;
- sesión local, control CSRF y auditoría saneada;
- backup diario verificado y restauración aislada.

## Arquitectura

El frontend React/Vite se empaqueta dentro de un wheel Python. FastAPI sirve la
SPA y `/api/v1` desde el mismo origen; SQLite permanece en el host y no expone
ningún puerto de red. Consulta [docs/architecture.md](docs/architecture.md).

## Instalación doméstica Windows

Requisitos: Windows 10/11 x64, PowerShell 5.1 o superior, privilegios de
administrador, una IPv4 privada estable o reservada por DHCP y `uv` disponible.
El instalador crea un Python 3.13 administrado por la aplicación.

Construye el frontend y el wheel desde el repositorio:

```powershell
cd frontend
npm ci
npm run build
cd ..\backend
uv build
cd ..
```

Después ejecuta PowerShell como administrador:

```powershell
.\deploy\windows\Install-PersonalFinance.ps1 `
  -WheelPath .\backend\dist\personal_finance-0.1.0-py3-none-any.whl `
  -ServerIp <IP-privada-estable> `
  -StablePrivateIPv4Confirmed `
  -BootstrapUsername <usuario> `
  -SpaceName <espacio>
```

El instalador solicita la contraseña sin incluirla en argumentos. Instala la
aplicación en `%ProgramFiles%\PersonalFinance`, conserva configuración, SQLite,
backups y logs en `%ProgramData%\PersonalFinance`, registra las tareas
`PersonalFinance-App` y `PersonalFinance-Backup`, y abre TCP 8080 únicamente
para el perfil Privado y `LocalSubnet`.

Diagnóstico posterior:

```powershell
& "$env:ProgramFiles\PersonalFinance\Test-PersonalFinance.ps1" `
  -ServerIp <IP-privada-estable>
```

La aplicación queda disponible en `http://<IP-privada-estable>:8080`.

## Seguridad del transporte

El modo doméstico requiere `PF_TRANSPORT_MODE=http_lan` de forma explícita y
solo admite orígenes HTTP RFC1918 exactos. Usa una cookie `pf_session` con
`HttpOnly` y `SameSite=Strict`; `Secure=false` es necesario porque no se
distribuyen certificados. Las credenciales y los datos viajan sin cifrar dentro
de la LAN, por lo que el servicio no debe publicarse en Internet ni utilizarse
en una red que no sea de confianza. Este riesgo está aceptado y sujeto a
revisión el 2027-08-09.

El modo HTTPS se mantiene para pruebas internas y utiliza
`__Host-pf_session`, `Secure=true`, origen exacto y CSRF.

## Operación y recuperación

- [Instalación LAN](docs/runbooks/install-lan.md)
- [Operaciones y diagnóstico](docs/runbooks/operations.md)
- [Backup y restauración](docs/runbooks/backup-restore.md)
- [Aceptación doméstica](docs/runbooks/acceptance.md)

El desinstalador elimina tareas, regla de firewall y archivos de aplicación,
pero conserva siempre `%ProgramData%\PersonalFinance`, incluida la base de
datos y las copias.

## Desarrollo y calidad

```powershell
cd backend
uv sync --dev
uv run pytest --cov=app --cov-fail-under=80
uv run ruff check .
uv run ty check

cd ..\frontend
npm ci
npm run lint
npm run typecheck
npm test -- --run
npm run build
```

Los cambios siguen `ai-eng`, [CONSTITUTION.md](CONSTITUTION.md) y
[AGENTS.md](AGENTS.md). Antes de integrar:

```powershell
ai-eng check
ai-eng verify
```

## Estado

`spec-001` está `SHIPPED` y consolidada tras el squash merge del PR #2 con todos
los checks requeridos en verde, incluido `windows-deployment`. La aceptación
HITL doméstica se confirmó el 2026-08-10.

## Licencia

Pendiente de definición.
