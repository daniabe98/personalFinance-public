# Changelog

Todos los cambios relevantes de este proyecto se documentarán en este archivo.

El formato se basa en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

## [Unreleased]

### Added

- Ya está disponible la base de gobierno del proyecto mediante `ai-eng`, con
  controles de calidad, seguridad, trazabilidad y flujo de contribución.
- Se han definido los principios constitucionales que priorizan la integridad
  de los datos financieros y un lenguaje accesible para la persona usuaria.
- Se incorpora una especificación funcional y técnica inicial como documento
  orientativo para preparar y aprobar el alcance del producto.
- Se entrega el núcleo financiero con saldo inicial, ingresos, gastos,
  transferencias, borradores, reversión, conciliación e informes básicos.
- Se incorpora una SPA React servida por FastAPI desde el mismo wheel, con
  sesión local, CSRF, idempotencia y auditoría saneada.
- Se añade instalación nativa para Windows 10/11 mediante PowerShell, Python
  3.13 administrado por `uv`, Programador de tareas y firewall limitado al
  perfil Privado y `LocalSubnet`.
- Se añaden backup diario verificado, retención y restauración aislada con doble
  comprobación de integridad SQLite.
- Se incorpora el job de CI `windows-deployment` con análisis de PowerShell,
  construcción del wheel y smoke test HTTP-LAN empaquetado.

### Changed

- El despliegue doméstico de `spec-001` se replanificó para un host y clientes
  Windows mediante HTTP en una IPv4 privada estable y TCP 8080.
- Las claves idempotentes del navegador incluyen un fallback UUID v4 compatible
  con el contexto HTTP privado, donde `crypto.randomUUID` no está disponible.

### Removed

- Se retiraron los assets de Linux, systemd, Bash y certificados domésticos al
  quedar sustituidos por la operación Windows comprobada.

### Security

- HTTP LAN solo se habilita con `PF_TRANSPORT_MODE=http_lan`, origen RFC1918
  exacto, cookie `HttpOnly`/`SameSite=Strict`, CSRF y firewall privado. El riesgo
  explícito de tráfico sin cifrar se revisará el 2027-08-09.
