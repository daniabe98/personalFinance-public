# Constitución de Personal Finance

> Versión: 1.0.0  
> Ratificada: 2026-07-23  
> Estado: vigente

## 1. Misión

Personal Finance es una aplicación web privada para registrar, consultar y
analizar finanzas personales con rigor contable y una experiencia accesible.
Debe preservar la integridad, trazabilidad y comprensión de cada operación sin
exponer complejidad contable innecesaria.

El proyecto no presta servicios bancarios, fiscales ni asesoramiento financiero
profesional, y no debe presentar sus métricas o previsiones como tales.

## 2. Partes interesadas

En la primera versión, la parte interesada principal es una única persona
operadora que registra sus datos y toma decisiones basadas en ellos. En futuras
versiones podrán depender de la aplicación integrantes de espacios financieros
personales, compartidos o familiares.

Cuando la aplicación falla, la persona operadora asume el coste: pérdida o
corrupción de datos, saldos incorrectos, pérdida de trazabilidad y decisiones
financieras equivocadas. La protección de sus datos prevalece sobre la rapidez
de entrega.

## 3. Vocabulario

El modelo interno utilizará terminología contable precisa para garantizar
corrección y trazabilidad, pero la interfaz y la documentación dirigida al
usuario emplearán lenguaje cotidiano y accesible.

Conceptos como debe, haber, asiento, devengo o regularización permanecerán
ocultos salvo en vistas avanzadas. El usuario trabajará principalmente con
términos como ingreso, gasto, transferencia, compra con tarjeta, pago de
tarjeta, cuota, dinero reservado, gasto pendiente, conciliación y anulación.

Cuando sea necesario relacionar ambos niveles, la documentación deberá explicar
el término técnico mediante una acción o consecuencia comprensible, sin perder
precisión.

## 4. Prohibiciones

Está prohibido:

- Almacenar o calcular importes monetarios mediante tipos de coma flotante.
- Contabilizar una transacción cuyos apuntes no estén equilibrados.
- Eliminar físicamente operaciones contabilizadas o conciliadas.
- Permitir que el frontend envíe apuntes contables arbitrarios.
- Reescribir silenciosamente periodos cerrados o datos históricos.
- Exponer directamente la base de datos a la red.
- Ejecutar migraciones destructivas o irreversibles sin autorización explícita
  y una vía de recuperación verificada.
- Confiar en cálculos financieros recibidos del cliente sin validarlos en el
  backend.
- Ocultar fallos que puedan afectar a saldos, trazabilidad, seguridad o
  recuperación de datos.

## 5. Controles de cumplimiento

Toda entrega deberá superar los controles aplicables de `ai-eng`, las pruebas
automatizadas de las invariantes contables y las validaciones de seguridad,
trazabilidad y consistencia de datos.

Los cambios de esquema deberán incluir y validar sus migraciones. Los mecanismos
de copia de seguridad deberán comprobar que la copia puede abrirse y que existe
un procedimiento de restauración. Ninguna certificación externa es obligatoria
durante la fase actual.

Un control crítico fallido bloquea la entrega hasta que se corrija o la persona
operadora adopte una decisión explícita conforme al proceso de gobierno.

## 6. Antiobjetivos

La primera versión no pretende cubrir sincronización bancaria automática, Open
Banking, importación automática de extractos, multimoneda, fiscalidad,
inversiones con cotización automática, valoración de inmuebles, inteligencia
artificial ni aplicaciones móviles nativas.

Tampoco pretende operar como servicio público de Internet ni introducir
microservicios, Docker, PostgreSQL, Kubernetes, colas de mensajes o
infraestructura distribuida sin una necesidad demostrada y una nueva decisión
aprobada.

Estos límites protegen la corrección del núcleo financiero y evitan complejidad
operativa prematura.

## 7. Límites de propiedad

El framework `ai-eng` administra sus superficies, plantillas, hooks y archivos
marcados como generados. No se editarán manualmente los archivos que declaren
una fuente canónica o una política de regeneración.

El equipo del proyecto administra el código de la aplicación, las
especificaciones aprobadas, la documentación funcional, la configuración del
producto, las migraciones y los procedimientos operativos. Los datos financieros
pertenecen a la persona operadora y permanecerán separados del código y de los
artefactos generados.

Cuando exista duda sobre la propiedad de un archivo, se consultará su
declaración de fuente de verdad antes de modificarlo.

## 8. Escalado

La persona operadora es la autoridad final del proyecto. Debe detenerse el
trabajo y solicitarse su aprobación explícita ante:

- Riesgo de pérdida, corrupción o exposición de datos.
- Incumplimiento de una invariante contable.
- Migraciones destructivas o restauraciones no verificadas.
- Vulnerabilidades o controles críticos fallidos.
- Ambigüedades que puedan alterar saldos, periodos cerrados o el significado
  económico de una operación.

Los problemas menores que no afecten a estas áreas podrán resolverse dentro del
flujo ordinario y deberán quedar documentados cuando corresponda.

## 9. Idioma

La documentación funcional, las especificaciones y la comunicación con la
persona operadora se redactarán en español claro.

El código, los identificadores técnicos, los contratos de API y el esquema de
base de datos se expresarán en inglés. Los commits seguirán Conventional Commits
y podrán redactar su descripción en español.

## 10. Fase del ciclo de vida

El proyecto se encuentra en fase `greenfield`: se está definiendo y construyendo
su primera versión, sin usuarios de producción ni compromisos de compatibilidad
anteriores.

Las decisiones deben favorecer un núcleo correcto y verificable. El cambio a
una fase de estabilización, madurez o retirada requerirá una enmienda explícita
de esta constitución.
