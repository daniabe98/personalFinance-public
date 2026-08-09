---
spec: spec-001
status: approved-input
generated_by: ai-design
revision: 2
---

# Design intent — Personal Finance V1

## Dirección

**“Porcelana y señal”**: una interfaz editorial de vidriomorfismo contenido que
combina una base Porcelain cálida con planos Blue Signal precisos. Transmite la
claridad de un extracto bancario sin enseñar contabilidad. La cualidad
recordable será una serie de capas translúcidas, como vidrio sobre porcelana,
donde cada operación explica **qué ocurrió**, **cuándo cuenta** y **cuándo se
movió el dinero**.

La aplicación es una herramienta privada para uso frecuente en casa, no un
dashboard financiero aspiracional. Debe sentirse luminosa, estable y directa.
El vidrio organiza niveles y contexto; no convierte cada elemento en una
tarjeta, no reduce contraste y no introduce gamificación ni animación
ornamental.

## Arquitectura de información

La navegación primaria tendrá cinco destinos:

1. **Resumen** — saldos, patrimonio y resultados del intervalo.
2. **Movimientos** — historial y alta de ingreso, gasto, transferencia o saldo
   inicial.
3. **Conciliar** — cuentas conciliables, progreso y sesiones de conciliación.
4. **Organizar** — cuentas y categorías, incluidas las archivadas.
5. **Ajustes** — sesión, backups, auditoría y datos operativos.

En escritorio se utilizará una barra lateral estable y un área de trabajo con
ancho máximo. En móvil, navegación inferior de cinco elementos con icono SVG y
texto. Las rutas clave serán enlazables y conservarán filtros al volver.

## Pantallas y flujos

### Alta y acceso

- El alta inicial solo explica que debe completarse localmente en el servidor.
- El formulario de acceso muestra etiquetas permanentes, error junto al campo y
  un mensaje inequívoco si la conexión no es segura.
- El cierre de sesión es visible desde el menú de cuenta.

### Resumen

- Selector de intervalo accesible y explícito.
- Tres grupos, no un mosaico indiscriminado: **Lo que tienes** (activos,
  pasivos, patrimonio), **Actividad del periodo** (ingresos, gastos, resultado)
  y **Dinero que entró y salió** (cobros, pagos, flujo neto).
- Importes alineados con cifras tabulares. Cada bloque incluye enlace a sus
  movimientos y un estado vacío explicativo.
- No se requieren gráficos en V1; cifras, comparaciones y tablas responden mejor
  al alcance y evitan decoración sin evidencia.

### Movimiento

- Un selector inicial ofrece cuatro verbos: **Añadir ingreso**, **Añadir
  gasto**, **Mover dinero** y **Indicar saldo inicial**.
- El formulario revela solo los campos pertinentes. `economic_date` se presenta
  como **Fecha a la que corresponde** y `cash_date` como **Fecha en que se movió
  el dinero**, inicialmente igual a la primera.
- Antes de contabilizar se muestra un resumen en lenguaje cotidiano. Guardar
  borrador y contabilizar son acciones distintas.
- Una operación contabilizada no ofrece editar ni borrar. **Anular con un
  movimiento compensatorio** abre una confirmación que explica el efecto y pide
  las nuevas fechas.
- Los estados visibles son **Borrador**, **Contabilizado**, **Comprobado** y
  **Anulado**, siempre con texto e icono además de color.

### Conciliación

- Flujo lineal: elegir cuenta → indicar fecha de corte y saldo real → seleccionar
  movimientos comprobados → revisar diferencia → completar.
- La cabecera fija del paso de selección muestra **Saldo real**, **Saldo
  comprobado** y **Diferencia**. La diferencia cero habilita completar; si no es
  cero, el texto explica cuánto falta sin culpabilizar.
- Cada fila muestra fecha, descripción, importe y estado. El saldo inicial se
  etiqueta **Base inicial** y no se mezcla con entradas o salidas de dinero.

### Organización, backups y auditoría

- Cuentas y categorías usan listas simples con filtros Activas/Archivadas.
  Archivar exige confirmación; desarchivar es inmediato.
- Backups muestran última copia válida, próxima expectativa, retención y
  resultado de verificación. Restaurar es un procedimiento operativo guiado, no
  una acción casual dentro de la navegación principal.
- Auditoría traduce acciones a frases comprensibles y evita mostrar payloads,
  secretos o importes innecesarios.

## Sistema visual

### Tipografía

- **Newsreader** 600 para títulos de página y cifras-resumen con carácter
  editorial.
- **Atkinson Hyperlegible Next** 400/500/700 para navegación, formularios,
  tablas y texto general.
- Cifras financieras con `font-variant-numeric: tabular-nums`.
- Fuentes autohospedadas, `font-display: swap` y fallbacks serif/sans-serif; la
  aplicación no dependerá de una CDN.

Escala: 12, 14, 16, 18, 24 y 32 px; texto base de 16 px y altura de línea entre
1.5 y 1.65. El ancho de texto explicativo no superará 72 caracteres.

### Color

“Blue Signal” se concreta como un azul profundo cercano a RAL 5005 y
“Porcelain” como un blanco mineral cálido. Son decisiones mediante tokens: el
matiz exacto puede ajustarse después sin alterar la semántica ni los
componentes.

Tokens de tema claro:

| Token | Valor | Uso |
|---|---:|---|
| `background` | `#F5F1E8` | Porcelain, fondo dominante |
| `background-blue-wash` | `#DCE8F2` | Halo ambiental frío |
| `surface-solid` | `#FBF9F4` | Formularios y tablas densas |
| `glass` | `rgba(251, 249, 244, 0.72)` | Panel principal |
| `glass-strong` | `rgba(251, 249, 244, 0.90)` | Modal y contenido crítico |
| `glass-border` | `rgba(255, 255, 255, 0.78)` | Borde iluminado |
| `text` | `#102538` | Texto principal azul-tinta |
| `text-muted` | `#4B6072` | Texto secundario |
| `primary` | `#154889` | Blue Signal, acción principal |
| `primary-hover` | `#103A70` | Blue Signal profundo |
| `primary-soft` | `#D7E4F0` | Selección y foco ambiental |
| `border` | `#B9C7D1` | Separación estructural |
| `success` | `#236746` | Resultado confirmado |
| `warning` | `#8A5A13` | Revisión necesaria |
| `danger` | `#983B36` | Error o anulación |
| `info` | `#154889` | Información operativa |

Todos los pares de texto del tema claro alcanzarán 4.5:1 y ningún estado
dependerá solo del color. El tema oscuro queda como refinamiento posterior: sus
tokens no forman parte del gate de V1.

### Vidrio, espacio, forma y movimiento

- Escala espacial de 4/8 px; separaciones de sección 16/24/32/48 px.
- El fondo combina Porcelain con dos halos Blue Signal de baja opacidad y una
  textura mineral casi imperceptible; nunca usa el degradado azul-púrpura típico
  de productos SaaS.
- Los planos principales usan `backdrop-filter: blur(18px) saturate(120%)`,
  fondo `glass`, borde interior claro de 1 px, radio de 14 px y sombra azul
  difusa. Navegación y modales usan `glass-strong`.
- Formularios, tablas, menús y mensajes de error emplean `surface-solid` o una
  opacidad mínima del 90 %. Ningún texto financiero importante se coloca sobre
  una transparencia variable.
- No se anidan superficies con blur y no hay más de tres planos de vidrio
  grandes por viewport. Si `backdrop-filter` no está disponible, `@supports`
  aplica automáticamente una superficie Porcelain sólida con el mismo borde.
- La jerarquía nace de profundidad, espacio y tipografía; no se crea una tarjeta
  de vidrio para cada cifra.
- Objetivos táctiles mínimos de 48×48 px y separación mínima de 8 px.
- Microinteracciones de 150–220 ms sobre opacidad y transformación; respuesta
  visual en menos de 100 ms y soporte completo de `prefers-reduced-motion`.
- Iconos SVG de una sola familia, sin emojis estructurales.

## Responsive y accesibilidad

- Diseño mobile-first validado a 375, 768, 1024 y 1440 px, sin desplazamiento
  horizontal.
- HTML semántico, orden visual igual al orden de foco, navegación completa por
  teclado y anillo de foco de 3 px.
- Etiquetas visibles; el placeholder nunca sustituye a la etiqueta. Validación
  al perder el foco y resumen de errores al enviar.
- Botones con estados normal, hover condicionado a puntero fino, pressed,
  loading, disabled, success y error.
- Tablas financieras cambian en móvil a filas apiladas semánticas; no ocultan
  importes, fechas ni estado.
- Las operaciones de más de un segundo muestran esqueleto o progreso y conservan
  espacio para evitar cambios de layout.
- El contraste se comprueba contra el color compuesto real de cada capa de
  vidrio, no contra el valor RGBA aislado. El foco Blue Signal incluye contorno
  Porcelain para seguir visible sobre fondos claros y azules.
- V1 usa un tema claro completo. La arquitectura de tokens no impedirá añadir un
  tema oscuro en una spec posterior.

## Lenguaje

- Verbos concretos: añadir, mover, comprobar, archivar, anular.
- “Debe”, “haber” y “asiento” quedan fuera de los flujos principales.
- Los errores indican acción y consecuencia: “No se contabilizó el gasto; no se
  guardó ningún movimiento”.
- Los importes EUR se presentan con formato local, pero viajan y se almacenan
  como céntimos enteros.

## Gate de diseño

La entrega de interfaz no se acepta hasta verificar:

- contraste, foco visible, teclado, lector de pantalla y movimiento reducido;
- objetivos táctiles, mensajes junto a campos y estados no basados solo en color;
- vistas a 375/768/1024/1440 px sin scroll horizontal ni contenido oculto;
- flujos completos de alta, operación, reversión, conciliación y backup;
- combinación Blue Signal/Porcelain coherente, vidriomorfismo con fallback
  sólido y contraste verificado sobre el color compuesto;
- ausencia de blur anidado, más de tres grandes planos translúcidos o texto
  financiero sobre transparencias inestables;
- cifras tabulares, estados vacíos y ausencia de jerga contable en el flujo
  principal;
- ausencia de dependencias visuales externas necesarias para operar en la LAN.
