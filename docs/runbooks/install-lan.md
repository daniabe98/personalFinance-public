# Instalación doméstica por HTTPS

Esta guía presupone un host Linux con `systemd`, un usuario de servicio
`personal-finance` sin inicio de sesión y Python 3.13. Sustituye los valores
entre `<...>` localmente; no los copies a incidencias ni al repositorio.

1. Construye el wheel con `pwsh scripts/build.ps1` y crea
   `/opt/personal-finance` desde ese artefacto bloqueado.
2. Crea `/var/lib/personal-finance`, `/var/backups/personal-finance` y
   `/etc/personal-finance/tls`, propiedad del usuario de servicio y modo 0700.
3. Fuera del repositorio ejecuta:
   `scripts/create-lan-certificate.sh /etc/personal-finance/tls <dns.local> <ip-lan>`.
4. Copia `deploy/personal-finance.env.example` a
   `/etc/personal-finance/personal-finance.env`, ajusta el origen HTTPS y
   conserva modo 0600. Nunca añadas contraseñas al archivo.
5. Crea el esquema y la identidad doméstica antes de habilitar el servicio:
   `/opt/personal-finance/bin/personal-finance migrate` y después
   `/opt/personal-finance/bin/personal-finance bootstrap --username <usuario> --space-name <casa>`.
   Ambos comandos se ejecutan como `personal-finance`; la contraseña se solicita
   de forma interactiva y no se escribe en argumentos ni archivos.
6. Instala los tres units de `deploy/` en `/etc/systemd/system`, ejecuta
   `systemctl daemon-reload` y habilita:
   `systemctl enable --now personal-finance.service personal-finance-backup.timer`.
7. Importa **solo** `ca.crt` como autoridad de confianza en cada cliente
   doméstico admitido. No distribuyas `ca.key` ni `server.key`.

Comprueba `https://<dns.local>:8443/health/ready`. No se publica listener HTTP:
el puerto 80 debe permanecer cerrado. Renueva el leaf antes de 397 días
repitiendo el paso 3 y reiniciando el servicio tras validar los SAN DNS/IP,
localhost y 127.0.0.1.
