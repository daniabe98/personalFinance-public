# Arquitectura

La distribución es un único wheel Python: FastAPI publica `/api/v1`,
`/health/*` y la SPA Vite empaquetada en el mismo origen. Las rutas de assets
ausentes y cualquier prefijo reservado mantienen 404 real; solo los deep links
de interfaz reciben `index.html`.

En el host doméstico Uvicorn termina TLS directamente en 8443 bajo un usuario
sin privilegios. `systemd` limita escrituras a datos y backups y un timer
persistente invoca el mismo CLI idempotente que el arranque. SQLite, copias,
claves y CA privada nunca forman parte del artefacto ni del repositorio.

La aceptación automatizada usa temporales, SQLite sintético y TLS efímero
loopback. La semántica real de systemd, confianza de un cliente LAN y
persistencia tras reinicio quedan tras el control HITL documentado.
