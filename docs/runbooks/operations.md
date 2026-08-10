# Operación doméstica en Windows

## Estado y registros

Abre Windows PowerShell como Administrador:

```powershell
Get-ScheduledTask -TaskName PersonalFinance-App,PersonalFinance-Backup
Get-ScheduledTaskInfo -TaskName PersonalFinance-App
Get-ScheduledTaskInfo -TaskName PersonalFinance-Backup
Get-NetFirewallRule -DisplayName "Personal Finance LAN"
& "$env:ProgramFiles\PersonalFinance\Test-PersonalFinance.ps1" -ServerIp <IP-privada>
```

Los registros están en `%ProgramData%\PersonalFinance\logs`. El arranque de
`PersonalFinance-App` ejecuta primero migraciones y después el backup pendiente;
solo entonces inicia Uvicorn en `0.0.0.0:8080`. El Programador de tareas reintenta
la aplicación después de un fallo. `PersonalFinance-Backup` se ejecuta a diario
y `StartWhenAvailable` recupera una ejecución perdida.

Los códigos 0 (copia creada) y 5 (ya existía una copia verificada ese día) se
tratan como éxito. Cualquier otro código deja la tarea fallida y exige revisar
el log. Una copia fallida nunca se presenta como válida.

## Red y salud

La única regla admitida es TCP 8080, perfil Privado y `LocalSubnet`. Comprueba
la salud desde un cliente autorizado con
`Invoke-WebRequest http://<IP-privada>:8080/health/ready`. No crees redirecciones
de puertos en el router y no cambies la conexión del servidor a perfil Público.

## Recuperación, actualización y retirada

Sigue [backup-restore.md](backup-restore.md) para ensayar toda restauración en
un destino aislado. Restore no se expone por HTTP. Para actualizar, construye el
nuevo wheel, detén `PersonalFinance-App`, instala el wheel en el entorno
administrado, ejecuta migraciones y vuelve a iniciar la tarea. Conserva siempre
un wheel anterior para rollback.

Para retirar solo el runtime:

```powershell
& "$env:ProgramFiles\PersonalFinance\Uninstall-PersonalFinance.ps1"
```

El desinstalador elimina tareas, firewall y runtime, pero preserva siempre
configuración, base de datos, logs y backups bajo
`%ProgramData%\PersonalFinance`.
