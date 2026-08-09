---
spec: spec-001
slug: personal-finance-v1
title: Primera versión de Personal Finance
status: in-progress
effort: large
summary: "Entrega un núcleo financiero doméstico utilizable que registra operaciones equilibradas, conserva trazabilidad, permite conciliación manual y protege el acceso y la recuperación de datos."
refs: []
---

# Spec 001 — Primera versión de Personal Finance

## Summary

Personal Finance necesita una primera entrega utilizable que permita gestionar
las operaciones financieras cotidianas sin exponer complejidad contable. Esta
spec define un núcleo vertical completo: identidad local, libro de partida
doble, cuentas y categorías personalizables, operaciones básicas, vistas
económicas y de tesorería, reversión, conciliación, acceso seguro y recuperación
verificada.

## Goals

- Permitir crear un usuario local y un espacio financiero personal al que
  pertenezcan todas las entidades financieras.
- Permitir crear, renombrar y archivar cuentas de activo o pasivo y categorías
  planas de ingreso o gasto; ninguna entidad referenciada se elimina físicamente
  y una entidad archivada no admite nuevas operaciones hasta desarchivarse.
- Permitir registrar saldo inicial, ingreso, gasto y transferencia mediante
  acciones accesibles que generen internamente apuntes equilibrados.
- Almacenar todos los importes monetarios como enteros en céntimos de EUR y
  rechazar cualquier operación cuya suma de débitos y créditos no coincida.
- Confirmar la operación y todos sus apuntes de forma atómica y dentro del mismo
  espacio financiero.
- Mantener los estados `DRAFT`, `POSTED`, `RECONCILED` y `VOIDED`: `DRAFT` no
  afecta al libro; las operaciones contabilizadas, incluidas las anuladas,
  conservan sus apuntes; una reversión contabilizada compensa el original.
- Impedir la edición o eliminación física desde `POSTED`; toda corrección crea
  una reversión equilibrada y, cuando corresponda, una nueva operación vinculada.
- Conservar una fecha económica exacta y exigir una fecha de caja al
  contabilizar las operaciones de este núcleo que mueven dinero; derivar los
  periodos de informe sin almacenar un periodo económico duplicado.
- Mostrar saldos de cuentas, activos, pasivos, patrimonio neto, ingresos,
  gastos, resultado económico, cobros, pagos y flujo neto para intervalos
  seleccionados.
- Permitir conciliar una cuenta indicando fecha y saldo real, seleccionando los
  apuntes de esa cuenta que han sido comprobados y exigiendo diferencia cero
  para completar el proceso.
- Derivar `RECONCILED` para una operación solo cuando todos sus apuntes
  conciliables estén incluidos en conciliaciones completadas; una transferencia
  puede seguir `POSTED` tras conciliarse únicamente en una de sus cuentas.
- Considerar conciliables únicamente los apuntes de cuentas visibles de activo
  o pasivo configuradas para contrastarse con un saldo real; excluir cuentas
  internas de ingreso, gasto, patrimonio y contrapartidas técnicas.
- Hacer idempotentes los comandos que crean o contabilizan operaciones: la misma
  clave, comando, payload y espacio devuelve el resultado previo incluso después
  de reiniciar; reutilizar la clave con un payload diferente es rechazado.
- Registrar eventos de auditoría para autenticación, contabilización, reversión,
  conciliación, backup y restauración sin incluir secretos.
- Exigir HTTPS para accesos desde la red local y limitar HTTP a `localhost`;
  proteger la sesión con una cookie no accesible a JavaScript y restringida al
  mismo origen.
- Limitar el alta inicial y la recuperación de credenciales a una acción local
  sobre el servidor, invalidando las sesiones anteriores tras un restablecimiento.
- Crear automáticamente una copia local diaria de SQLite, aplicar una retención
  configurable, verificar su integridad y demostrar una restauración real antes
  de aceptar la entrega.
- Ejecutar la aplicación como un único servicio doméstico que conserva los datos
  y vuelve a estar disponible después de reiniciar el servidor.
- Usar lenguaje cotidiano en la interfaz y reservar la terminología contable
  para el modelo interno o vistas avanzadas.

## Non-Goals

- Tarjetas de crédito, préstamos y deudas genéricas por pagar o cobrar.
- Operaciones `PLANNED` o `PENDING`.
- Gastos recurrentes, obligaciones periódicas, devengos y reservas.
- Presupuestos, asignaciones entre meses y cálculo de dinero seguro para gastar.
- Dashboard predictivo, detección de duplicados y métricas avanzadas de calidad.
- Subcategorías; la primera entrega utiliza una lista plana personalizable.
- Varios usuarios, espacios compartidos y economía familiar.
- Sincronización bancaria, importación automática, Open Banking y multimoneda.
- Aplicación móvil nativa, acceso público por Internet e inteligencia artificial.
- Docker, microservicios, PostgreSQL, Kubernetes y colas de mensajes.
- Copias obligatorias fuera del servidor; se incorporarán en una evolución
  posterior de recuperación.
- Fechas de liquidación diferentes para cada lado de una transferencia; el
  núcleo inicial usa una fecha de caja común.
- Cierre y reapertura formal de periodos contables.

## Acceptance Criteria

### AC-001 — Puesta en marcha

1. La persona operadora completa el alta local y accede mediante HTTPS desde
   otro dispositivo de la LAN.
2. La aplicación crea su espacio financiero personal.
3. Una petición sin sesión válida no puede consultar ni modificar datos.
4. HTTP desde otro dispositivo no permite usar la aplicación; `localhost` puede
   habilitarse para diagnóstico local.

### AC-002 — Configuración accesible

1. La persona operadora crea cuentas de activo y pasivo.
2. Puede usar categorías iniciales y crear categorías propias de ingreso o gasto.
3. Puede renombrar o archivar una categoría.
4. Una categoría usada no puede eliminarse físicamente y sus operaciones
   históricas siguen siendo consultables.
5. Una cuenta usada tampoco puede eliminarse físicamente.
6. Una cuenta o categoría archivada aparece en el historial, pero no puede
   seleccionarse para nuevas operaciones hasta desarchivarse.

### AC-003 — Saldo inicial

1. Se registra un saldo inicial en una cuenta.
2. El activo aumenta por el importe indicado.
3. El patrimonio inicial aumenta por el mismo importe.
4. La operación no aparece como ingreso del periodo.
5. Un saldo inicial de pasivo incrementa el pasivo y ajusta el patrimonio por el
   mismo importe, sin crear ingreso, gasto, cobro ni pago.
6. El importe introducido es positivo y la naturaleza de la cuenta determina su
   efecto contable.
7. El apunte de apertura de una cuenta conciliable forma parte de su saldo base
   de conciliación usando `economic_date`, sin convertirse en flujo de caja.

### AC-004 — Ingreso y gasto

1. Un ingreso contabilizado incrementa la cuenta de destino y el ingreso de su
   categoría por el mismo importe.
2. Un gasto contabilizado incrementa el gasto de su categoría y reduce la cuenta
   de origen por el mismo importe.
3. Las vistas económica y de tesorería usan respectivamente `economic_date` y
   `cash_date`.
4. Una operación en borrador no modifica saldos ni métricas.
5. Al contabilizar una operación que mueve dinero, `cash_date` es obligatoria y
   toma `economic_date` como valor inicial si el usuario no la cambia.
6. El saldo inicial nunca aparece como flujo de caja.
7. Una transferencia usa una fecha de caja común para origen y destino.

### AC-005 — Transferencia

1. Una transferencia reduce la cuenta de origen e incrementa la de destino.
2. Ambas cuentas pertenecen al mismo espacio financiero.
3. La transferencia no genera ingreso ni gasto.
4. Un reintento con la misma clave y payload devuelve la misma transferencia sin
   duplicar el movimiento.
5. Reutilizar esa clave con datos diferentes es rechazado.

### AC-006 — Integridad y atomicidad

1. Una operación desequilibrada es rechazada antes de contabilizarse.
2. Si falla cualquier apunte, no se conserva ninguna parte de la operación.
3. Ningún importe persistido utiliza coma flotante.
4. Los saldos se derivan del libro y no de acumuladores paralelos.
5. El contrato de idempotencia se verifica para saldo inicial, ingreso, gasto,
   transferencia y contabilización de un borrador, incluso tras reiniciar.

### AC-007 — Corrección y reversión

1. Una operación `DRAFT` puede editarse o descartarse.
2. Una operación `POSTED` o `RECONCILED` no puede editarse ni eliminarse.
3. La anulación crea una reversión equilibrada vinculada a la operación original.
4. Los apuntes originales permanecen en el libro y la reversión contabilizada
   produce un efecto neto cero sobre los saldos.
5. Los informes permiten identificar el original anulado y su reversión sin
   excluir ninguno de los dos del historial contable.
6. La reversión usa fechas explícitas que por defecto corresponden al momento de
   la anulación; no modifica las fechas de la operación original.
7. Si el original pertenece a un mes y la reversión a otro, cada periodo muestra
   su efecto; solo un intervalo que incluya ambos presenta efecto económico y de
   caja neto cero.

### AC-008 — Conciliación

1. La persona elige una cuenta, una fecha de corte y el saldo real observado.
2. La aplicación ofrece apuntes de cuentas visibles de activo o pasivo
   configuradas como conciliables, con `cash_date` igual o anterior al corte y
   que aún no pertenezcan a otra conciliación completada.
3. Los apuntes de apertura son elegibles mediante `economic_date` y forman el
   saldo base sin aparecer como flujo de caja.
4. La persona selecciona los apuntes comprobados en el extracto.
5. El saldo conciliado se calcula a partir de los apuntes de conciliaciones
   completadas anteriormente más los seleccionados en la conciliación actual.
6. La diferencia es el saldo real menos el saldo conciliado y debe ser cero para
   completar la conciliación.
7. Un apunte no puede pertenecer a dos conciliaciones completadas.
8. Los apuntes originales anulados y sus reversos son conciliables de forma
   independiente cuando aparecen en la cuenta real.
9. Conciliar una transferencia en la cuenta de origen no concilia su apunte en
   la cuenta de destino.
10. La operación completa solo se muestra como `RECONCILED` cuando todos sus
   apuntes conciliables lo están; en caso contrario permanece `POSTED`.
11. Un gasto queda `RECONCILED` al conciliar su apunte de cuenta financiera; el
    apunte de categoría de gasto no requiere conciliación.
12. Una cuenta con saldo inicial de 1.000 €, sin otros movimientos, puede
    conciliarse contra un saldo real de 1.000 € con diferencia cero.

### AC-009 — Vistas básicas

1. Para un intervalo, la vista económica muestra ingresos, gastos y resultado
   según `economic_date`.
2. Para un intervalo, la vista de tesorería muestra cobros, pagos y flujo neto
   según `cash_date`.
3. La vista de patrimonio muestra activos, pasivos y patrimonio neto a una fecha.
4. Las transferencias, saldos iniciales y reversos no se clasifican erróneamente
   como ingresos o gastos.

### AC-010 — Backup y restauración

1. Se crea automáticamente una copia diaria consistente con SQLite.
2. La copia usa la zona horaria doméstica configurada, tiene fecha identificable
   y respeta una retención configurable.
3. Una verificación fallida queda visible y se registra sin declarar éxito.
4. Antes de aceptar la entrega se restaura una copia en un entorno aislado.
5. La restauración abre la base de datos, supera la comprobación de integridad y
   conserva las entidades y saldos de un conjunto de datos conocido.
6. Si el servidor arranca y no existe una copia válida para la fecha doméstica
   actual, intenta crearla sin duplicar una copia ya completada.
7. Configurando una retención de tres copias y generando cuatro fechas válidas,
   solo se conservan las tres más recientes.

### AC-011 — Reinicio y auditoría

1. Tras reiniciar el servidor, el servicio arranca y los datos permanecen.
2. Los eventos relevantes registran fecha UTC, acción, resultado, actor,
   entidad o correlación y pueden consultarse solo con una sesión autorizada.
3. Un fallo de contabilización, conciliación, backup o restauración queda
   registrado con un resultado inequívoco.
4. Los eventos no revelan contraseñas, tokens ni datos financieros innecesarios.
5. Los flujos principales no muestran debe, haber o asiento; los errores indican
   la acción fallida y su consecuencia en lenguaje cotidiano.

## Decisions

### D-001-01 — Entrega vertical del núcleo financiero

La primera spec entrega un flujo utilizable de extremo a extremo y divide el
resto de la visión en especificaciones posteriores.

**Rationale**: una spec monolítica con todas las capacidades descritas impediría
validar el producto de forma incremental; una base solo técnica retrasaría el
feedback sobre accesibilidad.

### D-001-02 — Libro como única fuente de saldos

Los saldos, ingresos, gastos y patrimonio se derivan de transacciones y apuntes
equilibrados. Las categorías visibles corresponden internamente a cuentas
`INCOME` o `EXPENSE`; no mantienen saldos paralelos.

**Rationale**: una única fuente canónica evita divergencias entre cuentas,
categorías e informes y mantiene la partida doble detrás de una interfaz
comprensible.

### D-001-03 — Categorías planas y personalizables

La primera entrega ofrece categorías iniciales y permite crear, renombrar y
archivar categorías propias. Las subcategorías quedan en la hoja de ruta.

**Rationale**: un catálogo cerrado no cubre todos los hogares; una lista plana
aporta flexibilidad inmediata sin introducir todavía una jerarquía.

### D-001-04 — Ciclo de vida mínimo e inmutable

Las operaciones usan `DRAFT`, `POSTED`, `RECONCILED` y `VOIDED`. Desde
`POSTED`, toda corrección se realiza mediante reversión. Una operación `VOIDED`
conserva sus apuntes y queda compensada por una transacción de reversión
contabilizada y vinculada.

**Rationale**: separa claramente edición y efectos reales, preserva trazabilidad
y evita reglas ambiguas para planificación o confirmaciones pendientes.

### D-001-05 — Fecha económica exacta

`economic_date` es la referencia económica canónica y `cash_date` representa el
cobro o pago real. Los periodos de informe se derivan de las fechas. La primera
entrega usa una fecha de caja común para ambos lados de una transferencia.

**Rationale**: evita contradicciones entre fecha y periodo almacenado y mantiene
separadas las perspectivas económica y de tesorería; las fechas de liquidación
por apunte se posponen hasta que exista un caso doméstico que las requiera.

### D-001-06 — Conciliación contra saldo real

Una conciliación pertenece a una cuenta y una fecha, registra el saldo real y
agrupa los apuntes comprobados de esa cuenta. Solo se completa con diferencia
cero. El estado `RECONCILED` de una operación es derivado y requiere que todos
sus apuntes conciliables estén conciliados.

**Rationale**: marcar movimientos individualmente no demuestra que el saldo
completo coincida; conciliar por apunte evita que comprobar una cara de una
transferencia marque como comprobada la otra cuenta. El apunte de apertura forma
el saldo base sin clasificarse como flujo de caja.

### D-001-07 — HTTPS dentro de la LAN

Los accesos desde otros dispositivos usan HTTPS. HTTP se limita a `localhost`.

**Rationale**: la aplicación transporta credenciales, cookies de sesión y datos
financieros; HTTPS permite proteger confidencialidad e integridad y aplicar
cookies `Secure`.

### D-001-08 — Recuperación local demostrable

La primera entrega realiza backup local diario, verificación de integridad,
retención configurable y una restauración real previa a la aceptación.

**Rationale**: crear un archivo no demuestra capacidad de recuperación; exigir
una restauración valida el procedimiento completo sin bloquear la primera
entrega por una segunda ubicación de almacenamiento.

### D-001-09 — Hoja de ruta separada

`.ai-engineering/solution-intent.md` es la fuente canónica de la hoja de ruta;
esta spec enlaza la visión posterior sin incorporarla a su alcance.

**Rationale**: separar la entrega activa de la evolución futura evita que
`spec-001` crezca o que varias listas de roadmap diverjan.

### D-001-10 — Límites tecnológicos, no diseño detallado

La solución utiliza los stacks activos Python y TypeScript, persiste el libro en
SQLite y se despliega como un único servicio doméstico. La selección final de
frameworks, librerías, estructura modular y mecanismo de servicio pertenece a
`/ai-plan`.

**Rationale**: estos límites sostienen los requisitos aprobados de operación y
recuperación sin convertir la spec funcional en un plan de implementación ni
ratificar automáticamente todos los detalles del documento orientativo.

### D-001-11 — Reversión en el periodo de corrección

La reversión conserva fechas propias que por defecto corresponden al momento de
la anulación. La operación original mantiene sus fechas y su efecto histórico;
un informe solo presenta efecto neto cero cuando incluye ambos eventos. La
reversión conserva la naturaleza de caja del original: si el original no tenía
efecto de caja, tampoco lo crea; en caso contrario, su `cash_date` toma por
defecto la fecha doméstica de anulación.

**Rationale**: reescribir las fechas del original ocultaría cuándo ocurrió la
operación y cuándo se corrigió. Fechas explícitas mantienen trazabilidad entre
periodos sin introducir todavía un modelo de cierre y reapertura.

## Risks

- **Alcance creciente**: cualquier capacidad de los Non-Goals requiere una spec
  posterior y una actualización de la hoja de ruta.
- **Complejidad contable visible**: las pruebas de aceptación deben evaluar
  acciones y mensajes comprensibles, no solo corrección interna.
- **Duplicación por reintentos**: los comandos con efectos financieros deben
  conservar una identidad idempotente y devolver el resultado previo.
- **Certificados domésticos difíciles de usar**: el plan debe escoger un proceso
  de confianza local documentado y verificable en los dispositivos admitidos.
- **Backup en el mismo servidor**: protege frente a errores lógicos, pero no
  frente a pérdida física; la copia externa permanece en la hoja de ruta.
- **Restauración incompatible con migraciones**: cada cambio de esquema deberá
  preservar o documentar la recuperación de copias soportadas.
- **Conciliación confusa**: la interfaz debe explicar saldo real, saldo
  comprobado y diferencia sin exponer jerga innecesaria.
- **Transferencias con liquidación asimétrica**: la fecha de caja común puede no
  representar bancos que asientan cada lado en días distintos; una spec futura
  introducirá fechas por apunte si aparece esa necesidad.

## References

- doc: CONSTITUTION.md
- doc: especificacion_app_finanzas_personales_v1.md
- doc: .ai-engineering/solution-intent.md
- doc: https://cheatsheetseries.owasp.org/cheatsheets/Transport_Layer_Security_Cheat_Sheet.html
- doc: https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie
- research: .ai-engineering/runtime/research/https-aplicacion-domestica-lan-2026-07-23.md

## Open Questions

- Ninguna pregunta bloqueante permanece abierta para redactar el plan. Las
  decisiones de implementación se resolverán en `/ai-plan`.
