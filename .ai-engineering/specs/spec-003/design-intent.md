---
spec: spec-003
status: planning-input
generated_by: ai-design
revision: 1
---

# Design intent — Spec 003

## Dirección

**«Libro abierto, cifras en contexto»**: una evolución del lenguaje editorial
contable existente que hace que cada cifra explique de qué está compuesta y que
cada movimiento conserve su relato, sin convertir la aplicación en un
dashboard genérico. La cualidad recordable será la lectura horizontal de una
línea financiera completa —contexto, cifra, estado y siguiente acción— como en
un libro doméstico cuidadosamente anotado.

## Propósito, tono, restricciones y diferenciación

- **Propósito**: registrar movimientos inequívocos y comprender Resumen,
  Conciliación, Organización y Backup sin cambiar de contexto ni interpretar
  una lista técnica.
- **Audiencia**: una persona que administra sus finanzas domésticas con datos
  sensibles y necesita rigor, rapidez de lectura y lenguaje cotidiano.
- **Tono**: editorial, sobrio y táctil; cálido como papel y preciso como un
  extracto. No gamifica, no celebra importes y no usa estética fintech
  aspiracional.
- **Restricciones**: React 19, CSS existente, tema claro, fuentes y tokens
  autohospedados, importes exactos del servidor, WCAG AA, SPA servida dentro del
  wheel, sin librería de gráficos ni dependencia de red.
- **Diferenciación**: los micrográficos son marcas de composición dentro de una
  ficha editorial, nunca el protagonista; la descripción humana sigue siendo
  el ancla visual de cada movimiento.

## Sistema visual que se conserva

- **Display**: `Newsreader` 600 para títulos y cifras de cierre.
- **Body**: `Atkinson Hyperlegible Next` 400/700 para formularios, estados,
  navegación y detalle. Los importes mantienen números tabulares.
- **Color**: sólo tokens de `frontend/src/styles/tokens.css`. Blue Signal
  (`--color-primary`) guía acciones y selección; Porcelain
  (`--color-background`, `--color-surface-solid`) domina las superficies;
  success, warning y danger sólo refuerzan estados que también tienen texto e
  iconografía SVG.
- **Ritmo**: escala 4/8 px mediante `--space-1` a `--space-6`; separación de
  secciones 24/32/48 px y objetivos táctiles mínimos de 48×48 px con 8 px entre
  acciones.
- **Forma**: borde estructural, radio de 10–14 px y superficie sólida para
  datos financieros. El vidrio fuerte se reserva al modal, sin blur anidado.
- **Movimiento**: feedback de 160–220 ms limitado a `opacity` y `transform`;
  nada esencial depende de animación y `prefers-reduced-motion` lo reduce.

No se crea tema oscuro ni sistema visual nuevo en esta spec. Todos los cambios
de color usan tokens semánticos existentes; el gate de contraste se aplica al
tema claro que el producto declara con `color-scheme: light`.

## Composiciones

### Descripción de movimientos

- «Descripción» es un campo visible, obligatorio y cercano al principio del
  formulario; incluye ayuda «1–500 caracteres» y error debajo del control.
- La revisión previa repite la descripción con jerarquía principal para que la
  persona detecte un texto incorrecto antes de guardar.
- El historial legacy muestra «Sin descripción» como ausencia explícita, con
  tono secundario, nunca como texto inventado.
- La reversión explica que su descripción se genera desde el original; no
  presenta un campo redundante.

### Resumen, detalle y micrográficos

- «Actividad del periodo» conserva su ritmo de libro mayor. La descripción
  sustituye a la etiqueta genérica y «Ver detalle» pasa a ser botón.
- El modal usa `<dialog>` y una única superficie `glass-strong`: encabezado con
  descripción y estado, cifra dominante, fechas, cuentas/categoría y relaciones
  de reversión/corrección agrupadas por significado. Una referencia ausente se
  expresa como «No disponible» sin mostrar el identificador.
- Cargando, error y ausencia reservan el mismo marco del modal para evitar CLS.
  Escape y el botón «Cerrar» cierran; el foco queda contenido y vuelve al botón
  activador.
- «Dinero disponible» y «Patrimonio» son dos fichas editoriales hermanas. Cada
  una conserva sus tres cifras exactas y añade un SVG horizontal de dos bandas:
  Cobros/Pagos y Activos/Compromisos.
- El SVG representa magnitudes comparables sin alterar ni ocultar signos. Si
  hay cero o valores negativos/reversiones, usa una marca neutral y mantiene el
  valor firmado en texto; no calcula porcentajes semánticamente falsos. Incluye
  título/descripción accesibles y leyenda textual redundante.

### Revisión de conciliación

- Flujo progresivo en dos zonas: entradas arriba y «Revisión» debajo. La zona
  de revisión existe desde el inicio para evitar saltos de layout.
- Mientras faltan datos muestra hitos visibles de Cuenta, Fecha y Saldo real.
  Al ser válidos, cambia a «Calculando…» y después a tres bloques visuales:
  Saldo real, Saldo comprobado y Diferencia.
- «Cuadrado» usa estado success con texto e icono; «Con diferencia» usa warning
  con cantidad exacta; carga y error conservan estructura y `aria-live`
  moderado. Color nunca es la única señal.
- La selección de candidatos actualiza el cálculo automáticamente. No hay botón
  «Revisar movimientos» como requisito para revelar la información.

### Organizar

- Un `tablist` horizontal de ancho completo contiene «Cuentas» y «Categorías».
  La pestaña activa tiene texto, regla y `aria-selected`; soporta flechas,
  Home/End y foco roving.
- El filtro compartido Activas/Archivadas se mantiene por encima del panel.
- Cada `tabpanel` contiene su formulario y lista en una sola columna a todo el
  ancho. Cada fila usa una retícula horizontal en escritorio y reflow apilado
  en móvil, sin perder detalles ni acciones.
- El panel inactivo permanece montado sólo si es necesario para conservar el
  estado válido del formulario; queda `hidden` y fuera del orden de foco.

### Copia de seguridad

- Cabecera horizontal con estado principal e icono SVG; debajo, cuatro hitos:
  última copia válida, verificación, retención y próxima ejecución.
- En escritorio, los hitos forman una secuencia horizontal; a 768 px se
  reorganizan en dos columnas y a 375 px en una columna compacta.
- `NEVER_RUN`, `PENDING`, `VERIFIED` y `FAILED` tienen título y explicación
  inequívocos. El fallo conserva fecha/detalle y el enlace al runbook.
- No aparece acción de restauración. «Abrir guía de recuperación» sigue siendo
  enlace y objetivo táctil.

## Accesibilidad e interacción

- HTML nativo antes que ARIA; `dialog`, `button`, `dl`, `time`, `tablist`,
  `tab` y `tabpanel` se usan conforme a su semántica.
- Foco visible de 3 px, orden de foco igual al visual, nombres accesibles
  descriptivos y restauración de foco al cerrar el modal.
- Tabs: flechas izquierda/derecha, Home y End; activación predecible y paneles
  asociados con `aria-controls`/`aria-labelledby`.
- Inputs con etiquetas visibles, ayuda, `required`, `maxLength=500` y error
  contextual. El backend sigue siendo la autoridad.
- Hover sólo bajo `@media (hover: hover) and (pointer: fine)`; estados pressed,
  loading y disabled son visibles sin desplazar el layout.
- Texto principal ≥4.5:1, texto grande y separadores con contraste suficiente;
  axe, teclado y foco son gates, no inspección opcional.

## Responsive y rendimiento

| Ancho | Comportamiento esperado |
|---:|---|
| 375 px | Una columna; modal con gutter de 16 px; tabs desplazables sólo si el contenido lo exige, nunca la página; acciones apiladas. |
| 768 px | Fichas y backup en dos zonas; actividad y catálogo conservan reflow sin truncado. |
| 1024 px | Retícula editorial completa; modal contenido y paneles de catálogo a ancho útil. |
| 1440 px | Medida máxima legible; el espacio extra amplía gutters, no líneas de texto ni gráficos. |

- No hay imágenes raster ni assets remotos.
- Los gráficos son SVG nativo y se renderizan con unas pocas formas; no se
  incorpora runtime de charts.
- El marco reservado para resultados evita CLS; las listas actuales no
  alcanzan el umbral que justifica virtualización.
- Ninguna animación toca width, height, margin o propiedades costosas.

## Gate de diseño

- [x] Sin emojis estructurales; iconografía exclusivamente SVG y de trazo coherente.
- [x] Tipografía, paleta, radios, sombras y espaciado reutilizan el sistema existente.
- [x] Dirección editorial contable distintiva; no usa gradiente SaaS ni patrón genérico de tarjetas.
- [x] Acciones con feedback visible, 48×48 px y separación mínima de 8 px.
- [x] Teclado, foco, labels, errores y nombres de lector definidos para modal, tabs, formularios y gráficos.
- [x] Color redundante con texto/estructura; contraste AA requerido en el tema claro vigente.
- [x] Tema oscuro marcado N/A: el producto declara sólo tema claro y esta spec no crea un sistema global nuevo.
- [x] Movimiento de 150–300 ms, hover condicionado y reducción de movimiento definidos.
- [x] 375/768/1024/1440 px cubiertos, sin overflow horizontal ni contenido truncado.
- [x] Imágenes responsive/lazy marcadas N/A: no se añaden imágenes.
- [x] Fuentes conservan `font-display: swap`; SVG y estados reservan espacio para CLS <0.1.
- [x] Listas >50/virtualización marcada N/A para el volumen actual; no se elimina la paginación existente.
- [x] Divisores, foco e interacción se verifican sobre todos los fondos del único tema soportado.
- [x] Los micrográficos son redundantes con cifras/leyendas y no cambian semántica financiera.

