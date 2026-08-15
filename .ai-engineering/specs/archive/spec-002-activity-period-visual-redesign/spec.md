---
spec: spec-002
slug: activity-period-visual-redesign
title: Rediseño visual de actividad del periodo
status: done
effort: small
summary: "Rediseña la actividad económica como un libro contable editorial, responsive y accesible, conservando intactos los datos, el orden y la navegación del informe."
refs: []
---

# Spec 002 — Rediseño visual de actividad del periodo

## Summary

La vista «Actividad del periodo» presenta los totales y movimientos como texto
crudo, con poca jerarquía, enlaces que exponen identificadores internos y una
lectura deficiente en pantallas estrechas. Se necesita una mejora puramente
visual que facilite escanear el resumen y cada aportación sin cambiar contratos,
cálculos ni comportamiento financiero.

## Goals

- Presentar ingresos, gastos y resultado con una jerarquía editorial clara; el
  resultado debe destacar como cierre del resumen.
- Mostrar el resumen en una columna a 375 px y en tres columnas desde 768 px.
- Presentar cada aportación como una fila responsive con fecha localizada en
  formato abreviado español, por ejemplo «10 ago 2026»,
  importe firmado exacto y una acción «Ver detalle».
- Mantener el orden, número de filas, totales, importes y destinos de navegación
  recibidos del servidor.
- Usar «Movimiento» para cualquier aportación no nula y «Sin impacto» para cero,
  sin inferir ingreso o gasto a partir del signo.
- Ocultar el identificador interno `transaction_id` en el texto visible y
  conservarlo codificado únicamente en el
  `href`; cada acción tendrá un nombre accesible inequívoco por importe, fecha y
  posición.
- Cumplir en la superficie modificada los criterios WCAG AA verificables de
  contraste, semántica, navegación por teclado y foco visible; ofrecer objetivos
  interactivos de al menos 48 por 48 píxeles y evitar desbordamiento o truncado
  a 375, 768, 1024 y 1440 píxeles.
- Conservar el estado vacío, el encabezado del informe y los totales visibles.

## Non-Goals

- Cambiar endpoints, esquemas, modelos, consultas o lógica del backend.
- Recalcular o reclasificar ingresos, gastos, resultado o aportaciones.
- Añadir filtros, ordenación, paginación, gráficos o nuevas acciones.
- Cambiar el destino funcional de los enlaces de detalle.
- Rediseñar otras vistas de informes o el sistema visual global.
- Introducir dependencias de ejecución nuevas.

## Acceptance Criteria

### AC-002-01 — Resumen responsive

1. Los tres totales conservan exactamente sus valores del servidor.
2. El resumen usa una columna a 375 px y tres columnas a partir de 768 px.
3. «Resultado» se distingue visualmente mediante una regla y mayor énfasis sin
   depender solo del color.

### AC-002-02 — Filas de actividad

1. Cada aportación genera exactamente una fila y mantiene el orden original.
2. La fecha se muestra con día, mes abreviado español sin punto y año, por
   ejemplo «10 ago 2026», y se expone mediante `time[datetime]` sin
   desplazamientos por zona horaria.
3. Un importe positivo incluye `+`, uno negativo usa el signo menos tipográfico
   `−` y cero no añade signo.
4. Las aportaciones no nulas se denominan «Movimiento»; cero se denomina
   «Sin impacto» y usa tratamiento neutral.
5. El enlace visible dice «Ver detalle», mantiene el `transaction_id`
   codificado en su destino y su nombre accesible sigue una forma equivalente a
   «Ver detalle de Movimiento, +100,00 €, 10 ago 2026, 1 de 4»; para cero usa
   «Sin impacto».

### AC-002-03 — Accesibilidad y reflow

1. La vista conserva una estructura semántica de lista de descripción, lista de
   movimientos y fechas.
2. Los enlaces tienen foco visible y un área interactiva mínima de 48 por
   48 píxeles.
3. No existe desbordamiento horizontal, contenido truncado ni solapamiento en
   375, 768, 1024 y 1440 px.
4. Axe no informa infracciones y las comprobaciones de contraste, teclado, foco,
   objetivo táctil y reflow pasan sobre la superficie modificada.

### AC-002-04 — Regresión funcional

1. La navegación de detalle conserva `/movimientos?transaccion=<id-codificado>`.
2. No se modifica ninguna llamada de API ni el intervalo del informe.
3. Las pruebas usan datos plausibles del productor económico: fechas dentro del
   intervalo, `resultado = ingresos - gastos`, gastos ordinarios positivos y
   reversos negativos solo cuando proceda.
4. El valor cero se valida únicamente como tolerancia defensiva del componente,
   ya que no forma parte del flujo normal producido por el libro.

## Decisions

### D-002-01 — Dirección de libro contable editorial

El resumen y las filas se agrupan en una superficie sólida, de ritmo tipográfico
amplio y sin gráficos ni ornamentación pesada.

**Rationale**: la jerarquía y el espacio mejoran la lectura de importes sin
introducir una metáfora ajena al producto ni distraer de la información.

### D-002-02 — Semántica neutral de las aportaciones

El signo solo expresa el efecto numérico de la aportación; no determina si su
categoría es ingreso o gasto. Toda aportación no nula se presenta como
«Movimiento».

**Rationale**: el productor económico puede emitir tanto ingresos como gastos
ordinarios con valor positivo y usar negativos para reversiones; clasificar por
signo comunicaría información financiera falsa.

### D-002-03 — Progresive disclosure del identificador

El identificador interno `transaction_id` permanece en el destino codificado, pero se
elimina del texto visible del enlace y se sustituye por contexto accesible.

**Rationale**: el UUID es necesario para el deep-link, no para escanear la
actividad; importe, fecha y posición distinguen la acción para tecnologías de
asistencia.

### D-002-04 — CSS local y sin nueva dependencia

El rediseño utiliza clases `activity-*` y los tokens existentes, sin alterar
estilos de otras vistas ni añadir paquetes.

**Rationale**: el aislamiento reduce la superficie de regresión y mantiene el
cambio dentro del alcance puramente visual aprobado.

## Risks

- **Semántica financiera engañosa**: se mitiga prohibiendo clasificaciones por
  signo y validando la copia neutral en pruebas.
- **Fechas desplazadas por zona horaria**: se mitiga formateando los componentes
  ISO como fecha UTC y verificando el atributo `datetime` original.
- **Nombres accesibles duplicados**: se mitiga añadiendo importe, fecha y posición
  al nombre de cada enlace sin mostrar ese detalle redundante visualmente.
- **Regresión responsive**: se mitiga con pruebas de reflow y objetivos táctiles
  en cuatro anchos representativos.
- **Pruebas que acepten estados imposibles**: se mitiga separando el caso cero
  defensivo de los fixtures normales y haciendo coherentes totales, fechas y
  aportaciones con el productor del backend.

## References

- doc: CONSTITUTION.md
- doc: frontend/src/features/reports/economic.tsx
- doc: frontend/src/styles/global.css

## Open Questions

- Ninguna pregunta bloqueante permanece abierta.
