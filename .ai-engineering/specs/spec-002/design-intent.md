# Design Intent — Actividad del periodo

## Design

### Concepto

**Libro contable editorial doméstico**: una superficie cálida, precisa y sobria
en la que el resultado cierra el resumen y cada movimiento se lee como una línea
de un registro, no como una tarjeta independiente.

### Propósito y tono

- **Propósito**: permitir comparar el cierre del periodo y recorrer aportaciones
  exactas con rapidez, tanto en móvil como en escritorio.
- **Tono**: editorial, sereno y fiable; evita dashboards genéricos, gráficos,
  badges ornamentales y gradientes nuevos.
- **Diferenciación**: una regla horizontal convierte «Resultado» en el cierre
  visual del bloque y las filas usan ritmo de libro mayor sin exponer IDs.

### Sistema visual existente

- Mantener `Newsreader` para el encabezado y `Atkinson Hyperlegible Next` para
  etiquetas, fechas, importes y acciones.
- Reutilizar los tokens de `tokens.css`; no añadir colores hardcoded.
- Usar escala de 4/8 px mediante `--space-1` a `--space-6`.
- Mantener importes con números tabulares.

### Composición

- El `section` recibe una superficie sólida, borde suave y padding de 24 px.
- El resumen es un `dl`: una columna por defecto y tres columnas iguales desde
  48 rem. Cada celda mantiene etiqueta pequeña e importe dominante.
- «Resultado» se separa con una regla primaria y mayor peso; en escritorio la
  regla permanece dentro de su columna para conservar el cierre visual.
- La lista conserva una fila por aportación. En móvil: contexto, importe y
  acción apilados. Desde 48 rem: contexto a la izquierda, importe alineado y
  acción a la derecha.
- Las filas usan fondos derivados con `color-mix`; movimiento usa el primario y
  cero una variante neutral. El texto siempre comunica el estado, por lo que el
  color nunca es la única señal.

### Contenido y estados

- Fecha visible: `10 ago 2026`; semántica: `<time datetime="2026-08-10">`.
- Tipo visible: `Movimiento` para cualquier importe distinto de cero y
  `Sin impacto` para cero.
- Importe visible: `+100,00 €`, `−200,00 €` o `0,00 €`.
- Acción visible: `Ver detalle`; el nombre accesible añade tipo, importe, fecha
  y posición `n de total`.
- Estado vacío: conserva encabezado y totales y anuncia «Sin actividad
  económica» sin renderizar filas ficticias.

### Interacción y accesibilidad

- Enlace con mínimo 48×48 px, foco global visible y subrayado legible.
- Hover solo bajo `@media (hover: hover) and (pointer: fine)` y transición de
  160 ms limitada a color/fondo.
- Contraste AA en texto y estados introducidos; semántica nativa antes que ARIA.
- `min-width: 0` y wrapping controlado evitan truncado y desbordamiento.

### Breakpoints y verificación

- 375 px: una columna, filas apiladas, acción de ancho útil.
- 768 px: tres totales y fila en tres zonas.
- 1024 y 1440 px: misma estructura con medida contenida; no estirar el texto.
- Verificar reflow, objetivo táctil, foco, orden, `time[datetime]`, nombres
  accesibles, contraste automatizado y ausencia de infracciones Axe.

### Checklist de entrega

- [x] Dirección estética distintiva y coherente con el producto.
- [x] Tipografía y tokens existentes reutilizados.
- [x] Sin iconos, imágenes ni dependencias nuevas.
- [x] Objetivos de 48×48 px, teclado y foco definidos.
- [x] Hover condicionado a puntero fino.
- [x] Cuatro anchos de verificación definidos.
- [x] Sin scroll horizontal ni contenido truncado.
- [x] Sin animación no esencial ni impacto de rendimiento relevante.
