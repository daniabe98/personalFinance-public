# Operación doméstica

## Estado y registros

- Aplicación: `systemctl status personal-finance.service`
- Timer: `systemctl status personal-finance-backup.timer`
- Próximas ejecuciones: `systemctl list-timers personal-finance-backup.timer`
- Logs: `journalctl -u personal-finance.service --since today`
- Salud: `curl --fail --cacert <ca.crt> https://<dns.local>:8443/health/ready`

El arranque ejecuta `personal-finance backup --if-due` y falla de forma visible
si no puede verificar la copia. El código 5 significa que la copia verificada
del día ya existía y los units lo tratan como éxito idempotente; cualquier otro
fallo sigue deteniendo el arranque o marcando el oneshot como fallido. El timer
persistente recupera una ejecución perdida. Una copia fallida nunca se presenta
como válida.

## Recuperación y rollback

Sigue [backup-restore.md](backup-restore.md): toda restauración se ensaya sobre
un destino aislado con `personal-finance restore --source <backup> --destination
<nueva-db>`. No existe restauración HTTP. Para rollback de aplicación, detén el
servicio, reinstala el wheel anterior, conserva la base y certificados, ejecuta
las comprobaciones de salud y vuelve a arrancar. No reemplaces la base activa
sin la aprobación y la verificación descritas en el runbook.

Los datos persistentes autorizados son `/var/lib/personal-finance` y
`/var/backups/personal-finance`; el sistema y los hogares permanecen protegidos
por el unit endurecido.
