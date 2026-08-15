---
spec: spec-003
slug: front-visual-workflow-redesign
title: Rediseño visual y rigor de flujos del frontend
status: in-progress
effort: large
summary: "Refuerza el rigor descriptivo de los movimientos y rediseña Resumen, Revisión, Organizar y Copia de seguridad como experiencias visuales, accesibles, reactivas y coherentes."
refs:
  - spec-002
---

# Spec 003 — Rediseño visual y rigor de flujos del frontend

## Summary

Varias superficies principales de Personal Finance presentan información
correcta con una jerarquía visual insuficiente, ocultan datos relevantes o
obligan a abandonar el contexto para consultar un detalle. Además, las nuevas
operaciones pueden registrarse sin descripción y las proyecciones de informes y
conciliación sustituyen la descripción real por «Movimiento». Esta entrega
establece rigor descriptivo para toda escritura nueva y rediseña Resumen,
Revisión, Organizar y Copia de seguridad como experiencias visuales,
accesibles, responsive y coherentes, sin alterar los cálculos financieros.

## Goals

- Exigir una descripción normalizada de 1 a 500 caracteres en toda nueva
  apertura, ingreso, gasto, transferencia y borrador, con validación tanto en
  la interfaz como en la frontera canónica de escritura.
- Generar para cada reversión una descripción canónica vinculada al movimiento
  original, sin pedir al usuario que invente texto redundante.
- Conservar sin migración ni texto inventado los movimientos históricos cuya
  descripción sea nula y presentarlos explícitamente como «Sin descripción».
- Transportar y mostrar la descripción real en Actividad del periodo y
  Conciliación, eliminando el placeholder genérico «Movimiento».
- Abrir desde Actividad del periodo un modal accesible con descripción,
  importe, tipo, estado, fechas, nombres de cuentas y categoría, y relaciones
  de corrección o reversión, sin navegar a otra pestaña o ruta.
- Rediseñar Dinero disponible y Patrimonio con cifras exactas y dos
  micrográficos de composición actual que comparen Cobros/Pagos y
  Activos/Compromisos sin sustituir la información textual.
- Convertir Revisión en una composición visual progresiva: reflejar de inmediato
  los datos introducidos y obtener automáticamente el cálculo canónico cuando
  cuenta, fecha y saldo sean válidos, manteniéndolo actualizado al seleccionar
  movimientos.
- Organizar Cuentas y Categorías en dos tabs accesibles; cada panel contendrá
  su formulario y elementos de ancho completo y compartirá el filtro
  Activas/Archivadas.
- Rediseñar Copia de seguridad como una superficie horizontal y responsive que
  haga visibles el estado principal, la última copia válida, la verificación,
  la retención y la próxima ejecución esperada sin depender sólo del color.
- Corregir los estados archivados de `spec-002` y crear la doctrina de
  persistencia enlazada por las superficies de gobierno, con una fuente
  canónica y un mecanismo de reconstrucción explícitos para cada dato derivado.
- Mantener navegación por teclado, foco visible, nombres accesibles, contraste
  WCAG AA y ausencia de desbordamiento a 375, 768, 1024 y 1440 píxeles.

## Non-Goals

- Rellenar, reinterpretar o convertir a `NOT NULL` las descripciones históricas
  ausentes.
- Incorporar evolución temporal, tendencias, previsiones o nuevos cálculos a
  los micrográficos.
- Introducir una librería de gráficos o un nuevo sistema visual global.
- Cambiar importes, saldos, clasificación contable, orden de aportaciones ni
  reglas de conciliación.
- Añadir restauración de copias de seguridad desde la interfaz.
- Exponer identificadores internos como información principal del modal.
- Modificar localmente el lifecycle vendorizado de `ai-engineering`; su defecto
  de snapshot se documentará para corrección upstream.
- Implementar en esta entrega la futura visualización de series temporales.

## Acceptance Criteria

### AC-003-01 — Descripción rigurosa y legado seguro

1. Toda nueva apertura, ingreso, gasto, transferencia y alta o edición de
   borrador rechaza descripción ausente, vacía, compuesta sólo por espacios o
   superior a 500 caracteres; el backend responde `422` ante entradas HTTP no
   válidas.
2. La descripción se recorta antes de persistirse y la regla no depende
   exclusivamente de la validación del navegador.
3. Contabilizar un borrador, incluido uno histórico, exige completar antes una
   descripción válida; la mera lectura del borrador legacy sigue permitida.
4. Una reversión genera una descripción inequívoca basada en la original,
   respeta el máximo de 500 caracteres y no admite una reversión nueva sin
   descripción efectiva.
5. Los registros históricos nulos continúan siendo legibles y se presentan
   como «Sin descripción»; ninguna migración inventa contenido financiero.
6. El contrato OpenAPI y sus tipos generados representan correctamente la
   obligatoriedad en escritura y la nulabilidad histórica en lectura.

### AC-003-02 — Descripción real y detalle contextual

1. Cada aportación de Actividad del periodo y cada candidato de Conciliación
   muestra su descripción real o el fallback histórico, nunca el placeholder
   artificial «Movimiento».
2. «Ver detalle» es un botón y abre un diálogo sin cambiar la URL ni desmontar
   Resumen.
3. El diálogo presenta todos los campos comprensibles aprobados, resuelve por
   nombre cuentas y categorías activas o archivadas y, si una referencia ya no
   puede resolverse, muestra una ausencia explícita sin exponer el identificador
   como sustituto visible.
4. El diálogo comunica carga, error y ausencia de datos; se puede cerrar con
   Escape y control explícito, contiene el foco mientras está abierto y lo
   devuelve al botón que lo abrió.

### AC-003-03 — Métricas y micrográficos honestos

1. Dinero disponible conserva Cobros, Pagos y Cambio neto; Patrimonio conserva
   Activos, Compromisos y Patrimonio neto con los valores exactos del servidor.
2. Los micrográficos comparan exclusivamente Cobros/Pagos y
   Activos/Compromisos del periodo o fecha mostrados.
3. Cero, agregados negativos y reversiones conservan su signo en las cifras; el
   gráfico usa una representación neutral y no convierte importes firmados en
   porcentajes ni reclasifica su significado financiero.
4. Cada gráfico es redundante con cifras y etiquetas textuales, no introduce una
   dependencia de ejecución y no genera una serie temporal implícita.

### AC-003-04 — Revisión progresiva y canónica

1. La superficie visual de Revisión aparece progresivamente mientras se
   completan cuenta, fecha y saldo, sin exigir una acción manual para revelar
   los valores ya conocidos.
2. Al existir una combinación válida, Saldo real, Saldo comprobado y Diferencia
   proceden del cálculo canónico del servidor.
3. Seleccionar o deseleccionar candidatos actualiza el resultado y una respuesta
   antigua nunca sobrescribe una selección o entrada más reciente.
4. Los estados incompleto, cargando, cuadrado, con diferencia y error son
   distinguibles mediante texto y estructura, no sólo mediante color.

### AC-003-05 — Organizar mediante tabs

1. Cuentas y Categorías se presentan mediante semántica de `tablist`, `tab` y
   `tabpanel`, con navegación por flechas, Home y End y asociación accesible.
2. Cada tab muestra su formulario y su lista a todo el ancho disponible, con
   los detalles y acciones actuales intactos.
3. El filtro Activas/Archivadas se conserva al cambiar de tab y afecta a ambos
   catálogos de forma coherente.
4. Cambiar de tab no duplica altas ni pierde el estado válido del formulario
   activo de forma inesperada.

### AC-003-06 — Copia de seguridad visual y responsive

1. El estado de backup ocupa una superficie horizontal en escritorio y se
   reorganiza sin pérdida ni desbordamiento en pantallas estrechas.
2. Estado, última copia válida, verificación, retención y próxima ejecución
   esperada tienen jerarquía visual y etiquetas textuales inequívocas.
3. Los estados sin ejecución, pendiente, verificado y fallido coinciden con el
   contrato del backend; un fallo conserva su detalle y acceso al runbook.
4. La interfaz no ofrece ninguna acción de restauración.

### AC-003-07 — Gobernanza y documentación coherentes

1. El frontmatter archivado de la spec 002 termina en `status: done` y su plan
   archivado en `status: shipped`, coherentes con el sidecar canónico.
2. Existe `docs/persistence-doctrine.md` y todos sus enlaces resuelven.
3. La doctrina asigna cada dato a un único almacén writable, identifica cada
   proyección o caché y documenta su comando verificable de reconstrucción.
4. La ubicación canónica de las decisiones queda alineada con
   `knowledge-placement.md` y con la regla de los mirrors de instrucciones.
5. El defecto que permite archivar metadata previa al estado terminal se
   documenta como problema del framework, sin parchear manualmente artefactos
   vendorizados dentro de esta entrega.

### AC-003-08 — Calidad integral

1. Pruebas de dominio, API, contrato, componentes y E2E cubren los caminos
   nuevos, los estados de error y las regresiones funcionales.
2. Axe no informa infracciones en las superficies modificadas y todas las
   acciones son operables por teclado con foco visible y objetivos táctiles de
   al menos 48 por 48 píxeles.
3. No hay desbordamiento horizontal, solapamiento ni contenido truncado a 375,
   768, 1024 y 1440 píxeles.
4. El frontend y el wheel se construyen desde el checkout operacional, el
   runtime responde `ready` y los hashes de assets servidos coinciden con los
   instalados.

## Decisions

### D-003-01 — Obligatoriedad prospectiva con lectura nullable

Las nuevas escrituras requieren una descripción normalizada, mientras que la
lectura y la persistencia conservan compatibilidad con registros históricos
nulos mediante el texto visible «Sin descripción».

**Rationale**: mejora el rigor de toda operación futura sin inventar significado,
corromper evidencia histórica ni forzar una migración destructiva.

### D-003-02 — Descripción canónica para reversiones

Las reversiones generan su descripción a partir del movimiento original; las
demás altas y borradores exigen texto introducido por el usuario.

**Rationale**: una reversión ya tiene una relación semántica inequívoca y pedir
texto manual añadiría fricción sin aumentar la trazabilidad.

### D-003-03 — Proyecciones enriquecidas y modal contextual

Actividad del periodo y Conciliación transportan la descripción real. El detalle
se consulta bajo demanda y se muestra en un diálogo accesible con nombres de
cuentas y categoría, sin navegación ni identificadores internos visibles.

**Rationale**: la información debe llegar desde su fuente canónica y el usuario
debe conservar el contexto del informe; resolver el dato en la proyección evita
placeholders y cargas repetitivas.

### D-003-04 — Micrográficos de composición actual

Los dos gráficos representan composición Cobros/Pagos y
Activos/Compromisos mediante recursos nativos y cifras textuales exactas.

**Rationale**: los totales actuales permiten una visualización honesta sin
inventar historia temporal ni incorporar una dependencia; las tendencias se
reservan para una entrega futura con series canónicas.

### D-003-05 — Revisión progresiva híbrida

Revisión combina respuesta visual local para campos introducidos con preview
automático del servidor en cuanto la entrada sea válida, y mantiene ese preview
sincronizado con la selección.

**Rationale**: ofrece inmediatez sin duplicar ni reemplazar las reglas
financieras canónicas del backend.

### D-003-06 — Tabs accesibles con filtro compartido

Organizar separa Cuentas y Categorías en tabs de ancho completo y conserva un
único estado Activas/Archivadas al alternar entre ellas.

**Rationale**: reduce densidad visual, aumenta el espacio de cada elemento y
mantiene el modelo de filtro ya conocido sin estados paralelos sorprendentes.

### D-003-07 — Backup horizontal con estado explícito

Copia de seguridad distribuye horizontalmente el estado y sus hitos en
escritorio, colapsa de forma responsive y comunica cada estado con texto,
estructura e iconografía redundantes.

**Rationale**: la salud de recuperación debe poder evaluarse de un vistazo sin
convertirse en una lista vertical ni depender de la percepción del color.

### D-003-08 — Supersesión visual acotada de spec-002

Esta spec sustituye las decisiones de spec-002 que imponían «Movimiento»,
navegación por enlace y ausencia de gráficos, pero conserva sus garantías de
orden, exactitud, neutralidad financiera, reflow y accesibilidad.

**Rationale**: el nuevo contrato necesita evolucionar la presentación sin
debilitar las invariantes que protegían los datos y su significado.

### D-003-09 — Reparación project-owned y defecto upstream separado

La entrega corrige metadata y doctrina propiedad del proyecto, pero no modifica
el script vendorizado responsable de snapshots con estados previos al terminal.

**Rationale**: reparar las evidencias del proyecto es necesario para restaurar
coherencia; cambiar una superficie administrada por el framework mezclaría
propiedad y no resolvería de forma durable su transición pre/post-merge.

## Risks

- **Descripciones históricas nulas**: se mitiga manteniendo nullable la lectura,
  evitando backfill y probando explícitamente el fallback.
- **Validación desigual entre clientes**: se mitiga aplicando la regla en la
  frontera canónica de escritura y reflejándola en OpenAPI y frontend.
- **Visualización financiera engañosa**: se mitiga conservando cifras exactas,
  evitando clasificar por signo y definiendo cero y reversos en pruebas.
- **Respuesta de preview fuera de orden**: se mitiga garantizando que sólo la
  solicitud correspondiente a la entrada más reciente puede actualizar la UI.
- **Regresiones de accesibilidad en diálogo y tabs**: se mitiga con semántica,
  teclado, restauración de foco, axe y E2E en viewports representativos.
- **Estilos globales con efectos laterales**: se mitiga limitando cada
  composición a su superficie y verificando todas las vistas consumidoras.
- **Alcance transversal elevado**: se mitiga con ejecución por preocupaciones,
  TDD, gates multi-stack y verificación integral antes del merge.
- **Lifecycle archivando estados obsoletos**: se mitiga corrigiendo el snapshot
  afectado, verificando los estados terminales y separando el arreglo upstream.

## References

- doc: CONSTITUTION.md
- doc: .ai-engineering/specs/archive/spec-002-activity-period-visual-redesign/spec.md
- doc: .ai-engineering/reference/spec-schema.md
- doc: .ai-engineering/reference/plan-schema.md
- doc: .ai-engineering/reference/knowledge-placement.md
- doc: frontend/src/features/reports/economic.tsx
- doc: frontend/src/features/reconciliation/page.tsx
- doc: frontend/src/features/catalog/page.tsx
- doc: frontend/src/features/settings/backup-status.tsx

## Open Questions

- Ninguna pregunta bloqueante permanece abierta.
