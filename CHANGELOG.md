# Changelog

Todos los cambios relevantes de este proyecto se documentarán en este archivo.

El formato se basa en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

## [Unreleased]

### Added

- Los nuevos movimientos exigirán una descripción clara y el Resumen podrá
  consultar su detalle sin abandonar el informe.
- Se incorporan composiciones visuales para Dinero disponible, Patrimonio,
  Revisión, Organizar y Copia de seguridad, conservando cifras exactas y
  navegación accesible.
- Se documenta la doctrina de persistencia que asigna cada dato a una única
  fuente writable y define cómo reconstruir sus proyecciones.

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

- Las decisiones de diseño viven junto a su spec; su índice estructurado se
  trata como una proyección reconstruible, mientras las aceptaciones de riesgo
  conservan su lifecycle canónico en el registro JSON.

- La actividad del periodo presenta ahora un resumen editorial responsive y
  movimientos con fechas localizadas, importes firmados y enlaces de detalle
  accesibles, sin cambiar los cálculos ni el orden del informe.
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

### Fixed

- Los snapshots archivados de la spec 002 reflejan ahora sus estados terminales
  reales y las referencias a la doctrina de persistencia dejan de estar rotas.
