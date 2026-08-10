# Copias de seguridad y restauración

Este procedimiento crea una copia SQLite consistente, la abre de nuevo y exige
que `PRAGMA integrity_check` devuelva `ok` antes de declararla válida. La copia
usa la fecha doméstica configurada y conserva únicamente el número de copias
verificadas indicado por la retención.

## Preparación

- Sustituye `<APP_COMMAND>` por
  `%ProgramFiles%\PersonalFinance\venv\Scripts\personal-finance.exe`.
- Sustituye `<BACKUP_FILE>` por una copia que el estado local declare
  verificada.
- Sustituye `<ISOLATED_DESTINATION>` por un archivo nuevo en un directorio de
  ensayo. No puede ser la base activa ni un enlace que llegue a ella.
- Ejecuta los comandos desde PowerShell elevado. La ACL limita el acceso a
  Administradores, SYSTEM y `LOCAL SERVICE`.

La zona IANA y la retención proceden de `PF_DOMESTIC_TIMEZONE` y
`PF_BACKUP_RETENTION`. La fecha se calcula una vez al iniciar cada intento. Un
segundo catch-up en la misma fecha devuelve “ya existe una copia verificada” y
no crea otra.

Antes de invocar directamente el CLI, carga el JSON protegido solo en el
proceso elevado actual (no en argumentos ni en variables persistentes):

```powershell
$config = Get-Content "$env:ProgramData\PersonalFinance\config\appsettings.json" -Raw | ConvertFrom-Json
$allowed = @("PF_ALLOWED_ORIGIN", "PF_BACKUP_DIRECTORY", "PF_BACKUP_RETENTION", "PF_DATABASE_URL", "PF_DOMESTIC_TIMEZONE", "PF_SECRET_KEY", "PF_TRANSPORT_MODE")
foreach ($property in $config.PSObject.Properties) {
  if ($allowed -notcontains $property.Name) { throw "Clave de configuración no admitida" }
  [Environment]::SetEnvironmentVariable($property.Name, [string]$property.Value, "Process")
}
```

## Crear o recuperar la copia diaria

```text
<APP_COMMAND> backup --if-due
```

El proceso de arranque y la tarea diaria pueden ejecutar el mismo
comando: la reclamación durable por fecha evita declarar dos éxitos. La
configuración concreta del Programador de tareas pertenece al despliegue, no a este
runbook.

Resultados:

- `Backup created and verified.`: se publicó una copia nueva y pasó integridad.
- `A verified backup already exists today.`: el catch-up no necesitaba otra.
- `Backup failed; no new valid backup was declared.`: consulta el estado y
  corrige almacenamiento, permisos o espacio antes de reintentar.

El estado distingue la última copia válida del último fallo. Un fallo reciente
no invalida una copia anterior ya verificada. Los temporales, intentos fallidos
y archivos no catalogados no cuentan para retención.

## Ensayar una restauración aislada

Nunca uses la base activa como `<ISOLATED_DESTINATION>`.

```text
<APP_COMMAND> restore --source <BACKUP_FILE> --destination <ISOLATED_DESTINATION>
```

El comando:

1. exige que `<BACKUP_FILE>` esté catalogado y verificado;
2. copia a un temporal situado junto al destino aislado;
3. comprueba integridad, ejecuta Alembic solo sobre ese temporal y vuelve a
   comprobar integridad;
4. publica el destino con reemplazo atómico únicamente tras superar todos los
   controles;
5. elimina el temporal si falla cualquier paso.

Tras el éxito, abre `<ISOLATED_DESTINATION>` de forma local y comprueba:

```sql
PRAGMA integrity_check;
SELECT version_num FROM alembic_version;
```

El primer resultado debe ser exactamente `ok`. Además, recalcula desde los
apuntes las entidades y saldos conocidos del ensayo y compáralos con la huella
previa. No aceptes solo que el archivo exista.

La instalación administrada incluye Python, por lo que puedes obtener el
resultado sin instalar herramientas adicionales:

```powershell
& "$env:ProgramFiles\PersonalFinance\venv\Scripts\python.exe" -c "import sqlite3,sys; print(sqlite3.connect(sys.argv[1]).execute('PRAGMA integrity_check').fetchone()[0])" <ISOLATED_DESTINATION>
```

## Diagnóstico y límites

- Un fallo de copia o integridad no produce un archivo final válido.
- Un fallo de migración o de la segunda integridad no publica el destino.
- Un fallo de poda no borra ni desdeclara la copia nueva ya verificada.
- Los eventos de auditoría registran éxito o fallo y estado de verificación,
  pero no rutas, excepciones ni contenido financiero.
- Restore no está expuesto por HTTP y no sustituye automáticamente datos
  activos. Promover una base ensayada exige un procedimiento operativo
  separado, parada controlada y autorización explícita.
- La retención local no protege frente a pérdida física del mismo dispositivo.
  Este mecanismo no promete copia externa, replicación ni recuperación ante
  desastre fuera del almacenamiento configurado.
