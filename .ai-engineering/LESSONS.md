## Rules & Patterns

Persistent learning context for AI agents. Records corrections, patterns, and rules discovered during development sessions. This file is loaded at session start and updated after corrections.

Unlike `decision-store.json` (formal decisions with expiry and risk acceptance), this file captures informal but important patterns that should persist across sessions.

## How to Add Lessons

When the user corrects AI behavior:
1. Identify the pattern (not just the specific fix)
2. Add a new section below with: context, the learning, and an example if applicable
3. Keep entries concise (3-5 lines max per lesson)

## Patterns

### Verificar el sistema operativo del despliegue doméstico

Antes de solicitar evidencia operativa, confirmar el sistema operativo real del host y los clientes; no inferirlo de assets heredados. En Personal Finance, el host y los clientes domésticos son Windows, por lo que `systemd` y rutas POSIX no constituyen evidencia de aceptación válida.

### Usar SIDs invariantes en automatización Windows

Los nombres de cuentas integradas cambian con el idioma de Windows. Para ACL,
tareas y diagnósticos automatizados, usar SIDs conocidos (`S-1-5-18`,
`S-1-5-19`, `S-1-5-32-544`) y traducir las identidades observadas a SID.

### Alojar el runtime administrado fuera del perfil instalador

Un venv de `uv` puede depender del Python situado en el perfil que ejecutó la
instalación. Si el servicio usa otra identidad, instalar Python bajo
`ProgramFiles`, copiar paquetes desde caché y conceder al SID de servicio RX.

### Detener el runtime antes de reconstruir un venv Windows

Windows bloquea ejecutables y DLL cargados. Una actualización debe detener las
tareas y terminar solo los procesos cuyo ejecutable pertenece al venv antes de
usar `uv venv --clear`; los datos persistentes permanecen fuera del runtime.

### Capturar códigos nativos antes de filtrar su salida

En Windows PowerShell, canalizar un ejecutable a `Select-Object -First` puede
cerrar anticipadamente la tubería. Capturar primero salida y `$LASTEXITCODE`, y
filtrar después, evita convertir una ejecución correcta en un falso fallo.

### No depender de randomUUID en HTTP LAN

`crypto.randomUUID()` exige un contexto seguro y no existe en HTTP sobre una
IPv4 privada. Para claves idempotentes, usar `randomUUID` en HTTPS y un UUID v4
con `crypto.getRandomValues()` como fallback criptográfico en `http_lan`.
