# Especificación funcional y técnica — Aplicación de finanzas personales

## 1. Objetivo

Desarrollar una aplicación web para gestionar finanzas personales desde un servidor doméstico.

La primera versión estará orientada a una sola persona y permitirá registrar, consultar y analizar:

- Cuentas bancarias y efectivo.
- Ingresos.
- Gastos.
- Transferencias entre cuentas propias.
- Tarjetas de crédito.
- Préstamos.
- Deudas pendientes de pagar o cobrar.
- Gastos fijos y recurrentes.
- Gastos anuales prorrateados mensualmente.
- Reservas de dinero para pagos futuros.
- Presupuestos mensuales.
- Métricas y dashboard por periodos.

En versiones posteriores deberán poder existir:

- Varios usuarios.
- Un espacio financiero individual para cada persona.
- Uno o varios espacios financieros compartidos.
- Un perfil o espacio familiar para gestionar la economía común.

La aplicación debe respetar principios contables básicos, especialmente la partida doble, el devengo y la trazabilidad, pero sin exponer complejidad contable innecesaria al usuario.

---

## 2. Principios de diseño

### 2.1. Simplicidad para el usuario

La interfaz no mostrará conceptos como debe, haber, asientos o cuentas de regularización salvo en vistas técnicas o avanzadas.

El usuario trabajará con acciones comprensibles:

- Registrar ingreso.
- Registrar gasto.
- Transferir dinero.
- Comprar con tarjeta.
- Pagar tarjeta.
- Recibir préstamo.
- Pagar cuota de préstamo.
- Reservar dinero.
- Crear gasto recurrente.
- Crear obligación anual.
- Conciliar una cuenta.

El backend traducirá esas acciones a movimientos contables equilibrados.

### 2.2. Partida doble interna

No se crearán tablas independientes y desconectadas para ingresos y gastos.

Toda operación económica se representará mediante:

- Una transacción.
- Dos o más apuntes asociados.
- Una comprobación obligatoria de equilibrio.

Regla fundamental:

```text
Suma algebraica de los apuntes de una transacción = 0
```

La creación de la transacción y de todos sus apuntes deberá ejecutarse dentro de una única transacción de base de datos.

Si cualquier parte falla, se revierte toda la operación.

### 2.3. Separación de perspectivas

La aplicación distinguirá tres perspectivas:

1. **Perspectiva económica o de devengo**  
   Indica a qué periodo corresponde realmente un ingreso o gasto.

2. **Perspectiva de tesorería o caja**  
   Indica cuándo entró o salió realmente el dinero.

3. **Perspectiva presupuestaria**  
   Indica a qué mes se ha asignado el dinero para financiar gastos, ahorro o reservas.

Estas perspectivas pueden coincidir, pero no deben confundirse.

### 2.4. Trazabilidad

Cada operación deberá conservar:

- Fecha económica.
- Fecha real de cobro o pago.
- Fecha de creación.
- Fecha de modificación.
- Estado.
- Origen de la operación.
- Relación con una obligación, préstamo, tarjeta o regla recurrente cuando corresponda.

Las operaciones contabilizadas o conciliadas no se eliminarán físicamente. Se anularán o revertirán mediante una operación compensatoria.

---

## 3. Stack tecnológico

### 3.1. Frontend

- React.
- TypeScript.
- Vite.
- Aplicación SPA.
- Librería de gráficos: Recharts inicialmente.
- Cliente HTTP: `fetch` o una capa ligera propia.
- Formularios y validación tipados.

No se utilizará Next.js en la primera versión porque:

- La aplicación es privada.
- No necesita SEO.
- No necesita renderizado del lado del servidor.
- FastAPI será el backend y servidor principal.

### 3.2. Backend

- Python.
- FastAPI.
- SQLAlchemy 2.
- Alembic.
- Pydantic.
- Arquitectura monolítica modular.

Estructura orientativa:

```text
backend/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── security.py
│   │   └── exceptions.py
│   ├── users/
│   ├── financial_spaces/
│   ├── accounts/
│   ├── categories/
│   ├── transactions/
│   ├── credit_cards/
│   ├── loans/
│   ├── obligations/
│   ├── budgets/
│   ├── reserves/
│   ├── dashboard/
│   └── audit/
└── alembic/
```

Dentro de cada módulo se seguirá una separación similar a:

```text
router
service
repository
models
schemas
```

Las reglas contables deben residir en la capa de servicio, no en los routers ni en el frontend.

### 3.3. Base de datos

- SQLite.
- Un único archivo de base de datos.
- SQLAlchemy como capa de acceso.
- Alembic para migraciones.

Configuración obligatoria al abrir cada conexión:

```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;
```

SQLite es suficiente para:

- Uno o pocos usuarios.
- Pocas escrituras simultáneas.
- Uso doméstico.
- Un único proceso backend.
- Volumen moderado de movimientos.

No se migrará a PostgreSQL salvo que aparezcan necesidades reales como:

- Muchas escrituras simultáneas.
- Varias instancias del backend.
- Exposición pública.
- Sincronizaciones bancarias intensivas.
- Alta disponibilidad.
- Carga multiusuario elevada.

### 3.4. Importes monetarios

Los importes se almacenarán como enteros en la unidad monetaria mínima:

```text
1 euro = 100 céntimos
```

Ejemplo:

```text
21,50 € -> 2150
```

Motivos:

- Evitar errores de coma flotante.
- Evitar depender del comportamiento de `NUMERIC` en SQLite.
- Simplificar sumas, comparaciones y validaciones.

La moneda inicial será EUR.

La multimoneda queda fuera de la primera versión.

---

## 4. Despliegue

### 4.1. Topología

La aplicación se ejecutará en un servidor doméstico y será accesible desde la red local:

```text
http://IP_DEL_SERVIDOR:PUERTO
```

Ejemplo:

```text
http://192.168.1.50:8000
```

### 4.2. Un único servicio

El frontend se compilará mediante:

```bash
npm run build
```

FastAPI servirá:

- La API bajo `/api`.
- Los archivos estáticos compilados de React.
- El `index.html` de la SPA.

Rutas:

```text
/          -> frontend React
/api/...   -> API FastAPI
```

Ventajas:

- Un único puerto.
- Un único proceso.
- Sin CORS entre frontend y backend.
- Sin Docker.
- Sin servidor web adicional en la primera versión.

### 4.3. Servicio del sistema

En Linux se ejecutará mediante `systemd`.

Comportamiento esperado:

- Arranque automático con el servidor.
- Reinicio automático si el proceso falla.
- Ejecución bajo un usuario de sistema sin privilegios.
- Acceso de escritura únicamente al directorio de datos.
- Logs disponibles mediante `journalctl`.

El backend escuchará en:

```text
0.0.0.0:8000
```

### 4.4. Directorios orientativos

```text
/opt/personal-finance/
├── backend/
├── frontend/
├── .venv/
└── scripts/

/var/lib/personal-finance/
├── finance.sqlite3
└── backups/
```

El código y los datos no deben compartir el mismo directorio de escritura.

### 4.5. Copias de seguridad

La base de datos debe copiarse automáticamente.

Requisitos mínimos:

- Copia diaria.
- Nombre con fecha y hora.
- Retención configurable.
- Verificación de que la copia puede abrirse.
- Posibilidad de restauración manual.

No se debe copiar el archivo de SQLite de forma insegura mientras está siendo escrito. Se utilizará la API de backup de SQLite o un procedimiento compatible con WAL.

---

## 5. Modelo de dominio

## 5.1. Usuarios y espacios financieros

Aunque la primera versión tenga una sola persona, el modelo incluirá desde el principio el concepto de espacio financiero.

### Entidades

```text
users
financial_spaces
financial_space_members
```

### Conceptos

- `user`: persona que inicia sesión.
- `financial_space`: libro financiero independiente.
- `financial_space_member`: relación entre usuario y espacio.

Ejemplo futuro:

```text
Daniel
├── Finanzas personales de Daniel
└── Economía familiar

Persona B
├── Finanzas personales de Persona B
└── Economía familiar
```

En la V1:

- Existirá un usuario.
- Existirá un espacio financiero personal.
- Todas las entidades financieras incluirán `financial_space_id`.

Esto evita una migración estructural importante en el futuro.

---

## 5.2. Cuentas contables

Tipos internos:

```text
ASSET
LIABILITY
INCOME
EXPENSE
EQUITY
```

### Activos

Ejemplos:

- Cuenta corriente.
- Cuenta de ahorro.
- Efectivo.
- Reserva para gastos anuales.
- Dinero pendiente de cobrar.
- Gastos pagados por anticipado.

### Pasivos

Ejemplos:

- Tarjeta de crédito.
- Préstamo.
- Hipoteca.
- Dinero pendiente de pagar.
- Gastos devengados pendientes.

### Ingresos

Ejemplos:

- Nómina.
- Paga extra.
- Intereses.
- Venta ocasional.
- Otros ingresos.

### Gastos

Ejemplos:

- Vivienda.
- Alimentación.
- Transporte.
- Ocio.
- Salud.
- Formación.
- Seguros.
- Suscripciones.
- Intereses.
- Comisiones.

### Patrimonio

Ejemplos:

- Saldo inicial.
- Ajustes iniciales.
- Correcciones patrimoniales.

Las cuentas técnicas de regularización podrán estar ocultas para el usuario normal.

---

## 5.3. Entidades principales

Modelo orientativo:

```text
users
financial_spaces
financial_space_members

accounts
categories

transactions
transaction_entries
transaction_reversals

credit_cards
credit_card_statements

loans
loan_installments

periodic_obligations
obligation_accruals

budgets
budget_allocations

reserves
reserve_contributions

audit_events
```

No es obligatorio crear todas las tablas desde el primer commit, pero el diseño debe respetar estas responsabilidades.

---

## 6. Transacciones y apuntes

### 6.1. Transacción

Una transacción representa una operación completa.

Campos mínimos:

```text
id
financial_space_id
type
description
economic_date
cash_date
budget_period
status
source_type
source_id
created_at
updated_at
posted_at
reconciled_at
voided_at
```

### 6.2. Fechas

#### `economic_date`

Fecha o periodo al que corresponde económicamente la operación.

#### `cash_date`

Fecha real del cobro o pago.

Puede ser nula mientras la operación esté pendiente.

#### `budget_period`

Mes presupuestario al que se asigna el ingreso o gasto.

Formato lógico:

```text
YYYY-MM
```

#### Fechas técnicas

- `created_at`
- `updated_at`
- `posted_at`
- `reconciled_at`
- `voided_at`

Las fechas económicas se almacenarán como `DATE`.

Los eventos técnicos se almacenarán como fechas y horas UTC.

### 6.3. Estados

```text
PLANNED
PENDING
POSTED
RECONCILED
VOIDED
```

Significado:

- `PLANNED`: operación futura prevista.
- `PENDING`: realizada, pero todavía no confirmada.
- `POSTED`: contabilizada.
- `RECONCILED`: comprobada contra el saldo o extracto.
- `VOIDED`: anulada mediante reversión.

### 6.4. Apuntes

Cada transacción tendrá dos o más apuntes.

Campos mínimos:

```text
id
transaction_id
account_id
amount_minor
direction
memo
```

`amount_minor` siempre será positivo.

`direction` será:

```text
DEBIT
CREDIT
```

El servicio contable validará que:

```text
Total débitos = Total créditos
```

El frontend no construirá apuntes libremente. Enviará comandos de negocio y el backend generará los apuntes correctos.

---

## 7. Operaciones básicas

## 7.1. Ingreso cobrado

Ejemplo: nómina de 2.100 €.

```text
Débito:  Cuenta corriente       2.100 €
Crédito: Ingreso por nómina     2.100 €
```

Metadatos:

```text
economic_period: enero de 2026
cash_date: 31/01/2026
budget_period: febrero de 2026
```

## 7.2. Gasto pagado desde una cuenta

Ejemplo: supermercado de 72,40 €.

```text
Débito:  Gasto de alimentación  72,40 €
Crédito: Cuenta corriente       72,40 €
```

## 7.3. Transferencia entre cuentas propias

Ejemplo: mover 500 € a una cuenta de ahorro.

```text
Débito:  Cuenta de ahorro       500 €
Crédito: Cuenta corriente       500 €
```

No genera ingreso ni gasto.

## 7.4. Compra con tarjeta de crédito

Ejemplo: compra de 100 €.

```text
Débito:  Gasto correspondiente  100 €
Crédito: Deuda de tarjeta       100 €
```

Todavía no sale dinero de la cuenta bancaria.

## 7.5. Pago de tarjeta

Ejemplo: pago de 100 €.

```text
Débito:  Deuda de tarjeta       100 €
Crédito: Cuenta corriente       100 €
```

No vuelve a registrarse el gasto.

## 7.6. Recepción de préstamo

Ejemplo: préstamo de 10.000 €.

```text
Débito:  Cuenta corriente       10.000 €
Crédito: Deuda de préstamo      10.000 €
```

Recibir un préstamo no es un ingreso.

## 7.7. Pago de cuota de préstamo

Ejemplo:

```text
Cuota total: 300 €
Principal:   250 €
Intereses:    50 €
```

Apuntes:

```text
Débito:  Deuda de préstamo      250 €
Débito:  Gasto por intereses     50 €
Crédito: Cuenta corriente       300 €
```

La cuota debe permitir separar principal, intereses y posibles comisiones.

## 7.8. Reembolso

Un reembolso de un gasto debe reducir la categoría original o vincularse a la transacción original.

No se registrará por defecto como ingreso ordinario.

## 7.9. Saldo inicial

Ejemplo: al comenzar la aplicación existen 5.000 € en banco.

```text
Débito:  Cuenta corriente       5.000 €
Crédito: Patrimonio inicial     5.000 €
```

No se considera ingreso del mes.

---

## 8. Gestión de ingresos y meses presupuestarios

## 8.1. Regla principal

La aplicación no asumirá que el mes en que se cobra un ingreso es el mismo mes que financia.

Una nómina cobrada al final de un mes puede financiar el mes siguiente.

Ejemplo:

```text
Nómina correspondiente a enero
Fecha de cobro: 31/01/2026
Mes financiado: febrero de 2026
```

### Campos necesarios

```text
earned_period
cash_date
budget_period
```

- `earned_period`: periodo al que corresponde económicamente el ingreso.
- `cash_date`: fecha real de entrada del dinero.
- `budget_period`: mes al que el usuario asigna ese dinero.

### Regla automática para nóminas

Debe poder configurarse una regla:

```text
Los ingresos de categoría "Nómina" financian por defecto el mes siguiente.
```

La regla será editable.

### Ingresos extraordinarios

Para pagas extra, ventas, devoluciones u otros ingresos, el usuario podrá asignar el importe a:

- Mes actual.
- Mes siguiente.
- Varios meses.
- Reserva.
- Fondo de emergencia.
- Amortización de deuda.
- Sin asignar.

Una misma entrada de dinero puede tener varias asignaciones presupuestarias.

La división presupuestaria no crea varios ingresos contables.

---

## 9. Gastos fijos, recurrentes, devengo y reservas

## 9.1. Conceptos separados

La aplicación debe tratar como conceptos distintos:

```text
Gasto fijo
Gasto recurrente
Devengo
Reserva de dinero
Pago efectivo
```

### Gasto fijo

Coste estable o predecible.

Ejemplos:

- Alquiler.
- Seguro.
- Gimnasio.
- Suscripción.

### Gasto recurrente

Operación que se repite periódicamente.

Puede tener importe fijo o variable.

### Devengo

Reconocimiento del coste en el periodo en que se consume, independientemente de cuándo se paga.

### Reserva

Dinero apartado para un pago futuro.

Una reserva es una transferencia o asignación, no un gasto.

### Pago

Salida real de dinero.

Puede ocurrir antes, durante o después del periodo de devengo.

---

## 9.2. Obligaciones periódicas

Se creará una entidad específica:

```text
periodic_obligations
```

Campos orientativos:

```text
id
financial_space_id
name
category_id
amount_minor
frequency
period_start
period_end
next_due_date
payment_timing
accrual_method
payment_account_id
reserve_account_id
is_fixed_amount
is_active
created_at
updated_at
```

### Frecuencias

```text
MONTHLY
QUARTERLY
SEMIANNUAL
ANNUAL
CUSTOM
```

### Momento del pago

```text
ADVANCE
ARREARS
SAME_PERIOD
```

- `ADVANCE`: se paga antes de consumir el servicio.
- `ARREARS`: se paga después de consumirlo.
- `SAME_PERIOD`: se paga durante el mismo periodo.

### Método de devengo

```text
IMMEDIATE
STRAIGHT_LINE
MANUAL
```

- `IMMEDIATE`: todo el gasto se reconoce de una vez.
- `STRAIGHT_LINE`: reparto lineal entre periodos.
- `MANUAL`: el usuario define el reparto.

---

## 9.3. Gasto anual pagado por adelantado

Ejemplo:

```text
Seguro anual: 1.200 €
Pago: 1 de enero
Cobertura: enero-diciembre
Devengo: 100 € al mes
```

### En el pago

```text
Débito:  Gastos pagados por anticipado  1.200 €
Crédito: Cuenta bancaria                1.200 €
```

### Cada mes

```text
Débito:  Gasto de seguros                 100 €
Crédito: Gastos pagados por anticipado    100 €
```

El pago afecta a tesorería en enero.

El gasto económico se distribuye entre los doce meses.

---

## 9.4. Gasto anual pagado al final

Ejemplo:

```text
Coste anual: 1.200 €
Pago: diciembre
Devengo: 100 € al mes
```

### Cada mes

```text
Débito:  Gasto de seguros                 100 €
Crédito: Gastos devengados pendientes     100 €
```

### En el pago

```text
Débito:  Gastos devengados pendientes   1.200 €
Crédito: Cuenta bancaria                1.200 €
```

El pago cancela la deuda acumulada.

No genera un segundo gasto.

---

## 9.5. Reserva mensual para gastos futuros

Ejemplo:

```text
Reserva mensual: 100 €
Cuenta origen: cuenta corriente
Cuenta destino: reserva de gastos anuales
```

Movimiento:

```text
Débito:  Cuenta de reserva    100 €
Crédito: Cuenta corriente     100 €
```

No es un gasto.

La aplicación debe mostrar por separado:

```text
Gasto devengado del mes
Dinero reservado durante el mes
Pagos realizados durante el mes
Saldo acumulado de la reserva
```

En la V1, las reservas se representarán mediante una cuenta de activo designada.

Los sobres virtuales sin cuenta real quedan para una versión posterior.

---

## 9.6. Generación automática de devengos

Cada obligación con reparto periódico generará operaciones reales de devengo.

Cada generación incluirá:

```text
source_type = PERIODIC_OBLIGATION
source_id = id de la obligación
accrual_period = YYYY-MM
```

Debe existir una restricción lógica o física equivalente a:

```text
UNIQUE(source_id, accrual_period)
```

Esto evitará crear dos veces el devengo del mismo periodo.

Los devengos históricos no se recalcularán silenciosamente cuando cambie el importe de una obligación.

Los cambios afectarán a periodos futuros, salvo que el usuario solicite una corrección explícita.

---

## 10. Presupuestos

## 10.1. Concepto

El presupuesto representa cómo se asigna el dinero disponible a un periodo y a diferentes usos.

No modifica por sí mismo la contabilidad.

Ejemplo:

```text
Fondos asignados a febrero: 2.100 €

Distribución:
- Gastos corrientes: 1.200 €
- Gastos anuales:      350 €
- Ahorro:              300 €
- Ocio:                150 €
- Margen:              100 €
```

## 10.2. Elementos

```text
budgets
budget_allocations
```

Una asignación presupuestaria podrá estar vinculada a:

- Categoría de gasto.
- Reserva.
- Objetivo de ahorro.
- Pago de deuda.
- Cantidad sin asignar.

## 10.3. Regla temporal

Los gastos de un mes se compararán con el presupuesto de ese mismo mes, aunque el ingreso que lo financia se haya cobrado el mes anterior.

Ejemplo:

```text
Nómina de enero -> presupuesto de febrero
Gastos de febrero -> consumen presupuesto de febrero
```

No se vinculará cada gasto individual a una nómina concreta.

---

## 11. Dashboard

## 11.1. Vistas principales

El dashboard tendrá tres vistas o pestañas:

### Económica

Responde:

```text
¿Cuánto me ha costado realmente vivir durante el periodo?
```

Muestra:

- Ingresos devengados.
- Gastos devengados.
- Resultado económico.
- Distribución por categorías.
- Comparación con otros periodos.

### Tesorería

Responde:

```text
¿Cuánto dinero ha entrado y salido realmente?
```

Muestra:

- Cobros.
- Pagos.
- Flujo neto de caja.
- Evolución de saldos.
- Próximos cobros y pagos.
- Saldo mínimo previsto.

### Presupuestaria

Responde:

```text
¿Cuánto dinero tenía asignado y cuánto queda disponible?
```

Muestra:

- Fondos asignados.
- Presupuesto consumido.
- Presupuesto restante.
- Reservas.
- Ahorro planificado.
- Desviaciones.
- Dinero libre para gastar.

---

## 11.2. Estado del mes actual

El dashboard principal mostrará:

```text
Fecha actual
Día del mes
Días transcurridos
Días restantes
Porcentaje de mes transcurrido
```

Ejemplo:

```text
23 de julio
23 de 31 días
74,2 % del mes transcurrido
8 días restantes
```

---

## 11.3. Métricas prioritarias

### Patrimonio y saldos

- Saldo total de activos.
- Saldo líquido.
- Pasivos totales.
- Patrimonio neto.
- Saldo reservado.
- Dinero libre.
- Evolución del patrimonio.

Fórmula:

```text
Patrimonio neto = activos - pasivos
```

### Ingresos

- Ingresos devengados.
- Cobros reales.
- Ingresos recurrentes.
- Ingresos extraordinarios.
- Variación respecto al periodo anterior.
- Distribución por fuente.
- Ingresos acumulados del año.

### Gastos

- Gastos devengados.
- Pagos reales.
- Gastos por categoría.
- Gastos fijos.
- Gastos variables.
- Gastos recurrentes.
- Gastos esenciales.
- Gastos discrecionales.
- Gasto medio diario.
- Variación respecto al periodo anterior.
- Gasto acumulado anual.

### Flujo de caja

- Entradas reales.
- Salidas reales.
- Flujo neto.
- Flujo acumulado.
- Previsión de cierre.
- Próximos pagos.
- Próximos cobros.
- Saldo mínimo previsto.

### Presupuesto

- Fondos asignados.
- Presupuesto total.
- Presupuesto consumido.
- Presupuesto restante.
- Desviación absoluta.
- Desviación porcentual.
- Categorías agotadas.
- Categorías en riesgo.
- Previsión de sobrepaso.

### Ahorro

- Ahorro planificado.
- Ahorro real.
- Tasa de ahorro.
- Evolución mensual.
- Fondo de emergencia.
- Meses de cobertura.

Fórmula:

```text
Tasa de ahorro =
(ingresos devengados - gastos devengados) / ingresos devengados
```

Tratar de forma especial los periodos con ingresos iguales a cero.

### Deudas

- Saldo de tarjetas.
- Saldo de préstamos.
- Deuda total.
- Principal amortizado.
- Intereses pagados.
- Próximas cuotas.
- Utilización de tarjeta.
- Previsión de cancelación.

### Reservas y obligaciones

- Aportación mensual planificada.
- Aportación mensual real.
- Saldo reservado.
- Obligaciones previstas.
- Déficit o superávit de reserva.
- Cobertura de obligaciones.
- Próximos vencimientos.

Fórmula:

```text
Cobertura de reserva =
saldo reservado / obligaciones pendientes
```

### Calidad de datos

- Transacciones sin categoría.
- Transacciones pendientes.
- Transacciones sin conciliar.
- Devengos no generados.
- Posibles duplicados.
- Obligaciones vencidas.
- Cuentas sin actualizar.

---

## 11.4. Ritmo de gasto

Se mostrará el ritmo de consumo del presupuesto:

```text
Ritmo =
porcentaje de presupuesto consumido /
porcentaje de mes transcurrido
```

Interpretación:

- Menor que 1: gasto por debajo del ritmo del mes.
- Igual a 1: ritmo alineado.
- Mayor que 1: gasto más rápido de lo previsto.

---

## 11.5. Previsión de cierre

Cálculo inicial:

```text
Gasto previsto al cierre =
gasto realizado
+ gastos fijos pendientes
+ gasto variable diario medio * días restantes
```

Debe distinguir:

- Gastos ya realizados.
- Devengos todavía pendientes.
- Obligaciones conocidas.
- Estimación de gasto variable.

---

## 11.6. Dinero seguro para gastar

Métrica orientativa:

```text
Dinero seguro para gastar =
saldo líquido
- reservas comprometidas
- pagos próximos
- ahorro planificado
- colchón mínimo
```

También:

```text
Dinero seguro diario =
dinero seguro para gastar / días restantes
```

Esta métrica se calculará sobre la perspectiva presupuestaria, no como una magnitud contable oficial.

---

## 11.7. Filtros temporales

Todas las métricas deberán aceptar:

```text
start_date
end_date
comparison_period
financial_space_id
account_ids
category_ids
```

Periodos disponibles:

- Hoy.
- Ayer.
- Esta semana.
- Semana anterior.
- Últimos 7 días.
- Mes actual.
- Mes anterior.
- Últimos 30 días.
- Trimestre actual.
- Año actual.
- Año anterior.
- Últimos 12 meses.
- Intervalo personalizado.
- Acumulado hasta una fecha.

Para meses incompletos, las comparaciones deberán poder realizarse contra el mismo número de días del periodo anterior.

Ejemplo:

```text
1-23 de julio
vs.
1-23 de junio
```

---

## 12. Reglas de negocio obligatorias

1. Toda transacción contabilizada debe estar equilibrada.
2. Ningún importe monetario se almacenará como `float`.
3. Una transferencia entre cuentas propias no es ingreso ni gasto.
4. Recibir un préstamo no es un ingreso.
5. Devolver principal de un préstamo no es un gasto.
6. Los intereses y comisiones sí son gastos.
7. Comprar con tarjeta genera gasto y deuda.
8. Pagar la tarjeta reduce banco y deuda, pero no genera un nuevo gasto.
9. Reservar dinero no es un gasto.
10. El pago y el devengo pueden ocurrir en periodos distintos.
11. Un ingreso puede financiar un mes posterior a su cobro.
12. El saldo inicial no se registra como ingreso.
13. Los reembolsos deben reducir el gasto original cuando sea posible.
14. Las operaciones conciliadas no se eliminan físicamente.
15. Los devengos automáticos deben ser idempotentes.
16. Los cambios de una obligación no deben reescribir periodos cerrados sin confirmación.
17. Toda entidad financiera debe pertenecer a un espacio financiero.
18. Las reglas contables deben validarse en el backend.
19. El frontend no puede enviar apuntes contables arbitrarios.
20. Las operaciones complejas deben ejecutarse dentro de una única transacción de base de datos.

---

## 13. API orientativa

La API no debe exponer únicamente CRUD genérico. Debe ofrecer comandos de negocio.

Ejemplos:

```text
POST /api/transactions/income
POST /api/transactions/expense
POST /api/transactions/transfer
POST /api/transactions/refund

POST /api/credit-cards/{id}/purchases
POST /api/credit-cards/{id}/payments

POST /api/loans
POST /api/loans/{id}/installments

POST /api/obligations
POST /api/obligations/{id}/generate-accrual
POST /api/obligations/generate-due-accruals

POST /api/reserves/contributions

GET /api/dashboard/summary
GET /api/dashboard/cash-flow
GET /api/dashboard/accrual
GET /api/dashboard/budget
GET /api/dashboard/net-worth
```

Los endpoints CRUD podrán existir para configuración, pero las operaciones financieras deben usar servicios de dominio específicos.

---

## 14. Seguridad

Aunque la aplicación esté en una red local:

- Debe existir autenticación.
- Las contraseñas deben almacenarse con hash seguro.
- Las sesiones deben utilizar cookies `HttpOnly`.
- Se debe proteger contra CSRF cuando corresponda.
- Se debe validar todo dato recibido.
- No se debe confiar en cálculos enviados por el frontend.
- La base de datos no será accesible directamente desde la red.
- El puerto expuesto será únicamente el de la aplicación.
- Se registrarán eventos importantes de auditoría.

En la V1 se utilizará una autenticación local sencilla.

No se implementará SSO, OAuth ni proveedores externos.

---

## 15. Alcance funcional de la primera versión

### Incluido

- Usuario local.
- Espacio financiero personal.
- Cuentas bancarias.
- Efectivo.
- Cuentas de ahorro.
- Categorías.
- Ingresos.
- Gastos.
- Transferencias.
- Tarjetas de crédito.
- Préstamos.
- Deudas pendientes.
- Desglose de cuotas entre principal, intereses y comisiones.
- Gastos recurrentes.
- Obligaciones mensuales, trimestrales y anuales.
- Devengo lineal.
- Gastos pagados por anticipado.
- Gastos devengados pendientes.
- Cuenta de reserva para gastos futuros.
- Asignación presupuestaria por mes.
- Nómina que financia el mes siguiente.
- Dashboard económico.
- Dashboard de tesorería.
- Dashboard presupuestario.
- Filtros temporales.
- Anulación y reversión.
- Conciliación manual.
- Copias de seguridad.

### Fuera de alcance inicial

- Sincronización bancaria automática.
- Open Banking.
- Importación automática de extractos.
- Multimoneda.
- Fiscalidad.
- Inversiones con cotización automática.
- Valoración de inmuebles.
- Inteligencia artificial.
- Aplicación móvil nativa.
- Exposición pública por internet.
- Microservicios.
- Docker.
- PostgreSQL.
- Kubernetes.
- Colas de mensajes.
- Sobres virtuales sin cuenta real.
- Reparto avanzado de gastos familiares.
- Notificaciones externas.

---

## 16. Criterios de aceptación

La V1 se considerará funcional cuando permita completar correctamente los siguientes escenarios.

### Escenario 1: salario que financia el mes siguiente

1. Registrar una nómina correspondiente a enero.
2. Indicar cobro el 31 de enero.
3. Asignarla al presupuesto de febrero.
4. Verla en enero en tesorería.
5. Verla en enero en ingresos devengados.
6. Ver los fondos disponibles en el presupuesto de febrero.
7. No duplicar el ingreso en febrero.

### Escenario 2: gasto corriente

1. Registrar un gasto desde una cuenta bancaria.
2. Reducir el saldo de la cuenta.
3. Incrementar el gasto de la categoría.
4. Reducir el presupuesto correspondiente.
5. Mostrarlo en las vistas económica, de caja y presupuestaria.

### Escenario 3: compra y pago de tarjeta

1. Registrar una compra con tarjeta.
2. Incrementar el gasto.
3. Incrementar la deuda de la tarjeta.
4. Pagar posteriormente la tarjeta.
5. Reducir el saldo bancario.
6. Reducir la deuda.
7. No duplicar el gasto.

### Escenario 4: préstamo

1. Registrar la recepción de un préstamo.
2. Incrementar banco y deuda.
3. No considerarlo ingreso.
4. Registrar una cuota.
5. Separar principal, intereses y comisión.
6. Reducir correctamente la deuda.
7. Reconocer únicamente intereses y comisiones como gasto.

### Escenario 5: seguro anual pagado por adelantado

1. Crear una obligación anual de 1.200 €.
2. Pagarla en enero.
3. Reducir banco en 1.200 €.
4. Crear un activo por gasto anticipado.
5. Devengar 100 € cada mes.
6. Mostrar 1.200 € de salida de caja en enero.
7. Mostrar 100 € de gasto económico mensual.
8. Evitar devengos duplicados.

### Escenario 6: reserva mensual

1. Transferir 100 € al mes a una cuenta de reserva.
2. No registrar esa transferencia como gasto.
3. Incrementar el saldo reservado.
4. Reducir el dinero libre.
5. Mostrar la cobertura de futuras obligaciones.

### Escenario 7: reversión

1. Contabilizar una operación.
2. Conciliarla.
3. Intentar eliminarla.
4. Impedir la eliminación física.
5. Crear una reversión compensatoria.
6. Mantener el historial completo.

### Escenario 8: reinicio del servidor

1. Reiniciar el servidor doméstico.
2. Arrancar automáticamente el servicio.
3. Conservar todos los datos.
4. Acceder desde otro dispositivo de la red local mediante IP y puerto.

---

## 17. Decisiones definitivas

```text
Frontend:
React + TypeScript + Vite

Backend:
FastAPI + SQLAlchemy 2 + Alembic + Pydantic

Base de datos:
SQLite

Importes:
Enteros en céntimos

Despliegue:
Servicio systemd, sin Docker

Acceso:
IP local y puerto

Frontend y API:
Un único servicio FastAPI

Modelo:
Partida doble simplificada

Perspectivas:
Devengo, tesorería y presupuesto

Nómina:
Se registra cuando se cobra,
se atribuye al periodo trabajado
y puede financiar el mes siguiente

Gastos anuales:
Devengo periódico independiente del pago

Reservas:
Transferencias entre cuentas de activo,
no gastos

Tarjetas:
Compra = gasto + deuda
Pago = banco - deuda

Préstamos:
Recepción = activo + pasivo
Cuota = principal + intereses + comisiones

Evolución:
financial_spaces desde el diseño inicial
```

---

## 18. Instrucciones para la implementación

1. Empezar por el modelo de dominio y las invariantes contables.
2. Implementar pruebas unitarias para cada operación financiera antes de crear el dashboard.
3. No permitir creación directa de apuntes desde el frontend.
4. Crear servicios de dominio para ingresos, gastos, transferencias, tarjetas, préstamos, devengos y reservas.
5. Añadir índices por:
   - `financial_space_id`
   - fechas
   - cuentas
   - categorías
   - estados
   - origen de la operación
6. Crear migraciones Alembic desde el primer cambio de esquema.
7. Mantener una capa de compatibilidad con SQLite.
8. No introducir PostgreSQL, Docker o microservicios sin una necesidad real.
9. Crear datos de prueba que cubran un año completo.
10. Validar todos los cálculos del dashboard contra el libro contable.
11. Priorizar corrección contable y trazabilidad frente a automatizaciones prematuras.
12. Mantener la interfaz simple aunque el modelo interno sea riguroso.
