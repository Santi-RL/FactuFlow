# Diseño PF-01B — integridad persistente de estados, CAE y reservas

Última actualización: 2026-07-13

Estado: PF-01B.3 COMPLETADO. CHECKPOINT CLAWPATCH PENDIENTE.

## Objetivo

Cerrar las dos fuentes P1 restantes de PF-01 mediante invariantes de base de
datos que impidan:

- que un estado libre retire accidentalmente una reserva fiscal del índice
  parcial de `intentos_emision_fiscal`;
- que `comprobantes` persista un estado desconocido o una combinación
  contradictoria entre `estado`, `cae` y `cae_vencimiento`.

El cambio endurece persistencia y migraciones. No agrega funcionalidad de
producto, no solicita CAE, no cambia numeración global y no modifica la forma
en que FactuFlow interpreta actividad externa. PF-02 permanece separado.

## Fuentes y alcance

Fuentes Clawpatch previamente adjudicadas:

- B10: la reserva parcial depende de strings de estado sin restricción de
  dominio;
- B17: `estado` y CAE admiten combinaciones incoherentes en `comprobantes`.

Tablas y capas dentro del alcance:

- modelo `IntentoEmisionFiscal`;
- modelo `Comprobante`;
- vocabularios de estado consumidos por `IdempotenciaFiscalService`;
- una migración Alembic posterior a `f7a8b9c0d1e2`;
- preflight de datos legacy, downgrade y pruebas SQLite/PostgreSQL.

Fuera de alcance:

- estados de lotes, grupos, filas u operaciones idempotentes;
- cambios de contrato HTTP o UI;
- reconciliación automática de datos ambiguos;
- PF-02, historia externa y cálculo del siguiente número fiscal;
- despliegue, migración productiva o llamadas reales a ARCA.

## Auditoría previa sanitizada

Se inspeccionaron en modo solo lectura las bases SQLite locales ignoradas. En
las tablas aplicables no se detectaron estados desconocidos, combinaciones
contradictorias de comprobante ni reservas activas duplicadas. La evidencia y
los conteos permanecen locales y no se versionan.

Esta observación no autoriza a asumir que PostgreSQL productivo tiene el mismo
estado. Antes de cualquier despliegue, la migración debe ejecutar su propio
preflight y abortar sin modificar el esquema si encuentra una fila ambigua.
La auditoría productiva y el backup previo requieren autorización explícita.

## Decisiones de diseño

### Vocabularios canónicos

Los estados se definirán una sola vez por entidad en el módulo de su modelo. El
modelo, los `CheckConstraint`, el predicado de reserva y el servicio importarán
o derivarán sus conjuntos desde esa fuente. La migración congelará los valores
literales necesarios para que su comportamiento histórico no cambie cuando el
código futuro evolucione.

Estados legales de `IntentoEmisionFiscal`:

| Estado | Conserva reserva | Significado |
|---|---:|---|
| `en_proceso` | Sí | Existe una solicitud fiscal que todavía no tiene cierre seguro. |
| `requiere_reconciliacion` | Sí | No puede liberarse el número hasta verificar ARCA y persistencia. |
| `autorizado` | Sí | El número ya fue autorizado y debe permanecer ocupado. |
| `rechazado_arca` | No | ARCA rechazó sin CAE; el intento es terminal. |
| `fallido_verificado` | No | Se verificó que no existe autorización que conservar. |

No se agregará un estado nuevo sin decidir explícitamente si conserva reserva,
actualizar el vocabulario, el índice parcial, la migración siguiente y las
pruebas de concurrencia.

Estados legales de `Comprobante` que preservan el contrato histórico del
modelo:

| Estado | CAE | Vencimiento CAE |
|---|---|---|
| `borrador` | Debe ser nulo | Debe ser nulo |
| `pendiente` | Debe ser nulo | Debe ser nulo |
| `rechazado` | Debe ser nulo | Debe ser nulo |
| `autorizado` | Obligatorio, 14 caracteres | Obligatorio |

El flujo productivo actual crea comprobantes únicamente después de una
respuesta autorizada. Los otros estados se conservan como dominio legacy y
para no cambiar contratos fuera de PF-01B; nunca representan autorización.

### Invariantes de persistencia

1. `IntentoEmisionFiscal.estado` solo admite el vocabulario canónico.
2. Todo estado que pueda ocultar una autorización o una solicitud en curso
   conserva la reserva activa.
3. Dos reservas activas no pueden compartir emisor, punto de venta, tipo y
   número planificado.
4. Un estado terminal libera la reserva solo porque su semántica confirma que
   no hay autorización que conservar.
5. `Comprobante.estado` solo admite el vocabulario canónico.
6. `autorizado` exige CAE no vacío de longitud 14 y vencimiento presente.
7. Un comprobante no autorizado no puede conservar CAE ni vencimiento de CAE.
8. La validación de que el CAE contiene solo dígitos sigue en el borde de
   servicio; la restricción portable de base garantiza presencia y longitud en
   SQLite y PostgreSQL.
9. Ninguna migración inventa un estado, un CAE o una fecha para reparar datos.
10. Una fila ambigua bloquea la migración y exige adjudicación manual segura.

## Estados y transiciones

PF-01B no crea transiciones nuevas. Solo vuelve exigibles en persistencia las
transiciones ya usadas por los servicios:

- intento: `en_proceso -> autorizado`;
- intento: `en_proceso -> requiere_reconciliacion`;
- intento: `en_proceso -> rechazado_arca`;
- intento: `en_proceso -> fallido_verificado`;
- intento: `requiere_reconciliacion -> autorizado` después de reconciliar;
- intento: `requiere_reconciliacion -> fallido_verificado` solo cuando ARCA
  confirma que el comprobante no existe;
- comprobante: creación durable como `autorizado` con CAE y vencimiento válidos.

Las escrituras de estado y campos relacionados deben ocurrir en la misma
transacción. Un `IntegrityError` de los nuevos constraints nunca se interpreta
como rechazo de ARCA ni habilita un reintento automático.

## Orden de la migración

La migración implementada es bloqueante y sigue este orden:

1. partir de la revisión padre `f7a8b9c0d1e2`, que garantiza la existencia de
   las tablas y del índice parcial; una base fuera de esa cadena falla sin
   normalización;
2. contar estados desconocidos de ambas tablas;
3. detectar comprobantes autorizados sin CAE, con CAE de longitud distinta de
   14 o sin vencimiento;
4. detectar comprobantes no autorizados con CAE o vencimiento;
5. detectar reservas activas duplicadas según el predicado canónico;
6. si existe cualquier conflicto, abortar con un error sanitizado que indique
   clase de conflicto y cantidad, sin listar filas ni datos fiscales;
7. crear los constraints de dominio y coherencia mediante operaciones batch
   portables;
8. verificar por inspección que los constraints nuevos existen y dejar Alembic
   en el nuevo `head`.

El índice parcial existente se conserva sin recrearlo porque su predicado ya
coincide con el vocabulario canónico. Las regresiones SQLite comprueban su
semántica para estados activos y terminales.

No habrá `UPDATE` correctivo automático. Los estados desconocidos y las
combinaciones con CAE requieren determinar primero si ARCA autorizó el
comprobante. Corregirlos a ciegas podría liberar numeración o borrar evidencia.

En SQLite se usarán operaciones batch de Alembic cuando sean necesarias para
crear o retirar checks. En PostgreSQL se aplicarán constraints equivalentes.
El índice parcial existente se conservará si su definición coincide; si el
predicado debe recrearse para quedar sincronizado con el vocabulario, se hará
dentro de la misma migración después del preflight.

## Downgrade y rollback

El `downgrade` retirará únicamente los nuevos constraints y, si correspondió,
restaurará la definición anterior del índice parcial. No reescribirá datos ni
eliminará intentos o comprobantes.

Un rollback operativo posterior a un upgrade fallido consiste en restaurar el
backup previo o ejecutar el downgrade solo si la migración llegó a completar.
Si el preflight aborta antes de modificar el esquema, no hay nada que revertir.

## Fallos intermedios

| Falla | Resultado seguro esperado |
|---|---|
| Estado legacy desconocido | Upgrade abortado antes de crear constraints. |
| Autorizado sin CAE o vencimiento | Upgrade abortado; exige reconciliación manual. |
| No autorizado con CAE | Upgrade abortado; no se borra evidencia. |
| Reserva activa duplicada | Upgrade abortado; no se elige un ganador automáticamente. |
| Corte durante batch SQLite | La transacción de migración revierte; verificar schema antes de reintentar. |
| Error PostgreSQL al validar constraint | Transacción revertida; conservar backup y revisar conteos. |
| Escritura futura con estado inválido | `IntegrityError`; no llamar a ARCA ni liberar numeración por ese error. |
| Estado nuevo no incorporado al índice | Tests de contrato deben fallar antes de publicar. |

## Concurrencia

El constraint de dominio cierra la vía por la cual una cadena arbitraria podía
quedar fuera del índice parcial. La exclusión real sigue a cargo del índice
único parcial sobre:

`empresa_id, punto_venta_id, tipo_comprobante, numero_planificado`.

La matriz debe probar que exactamente una de dos reservas activas equivalentes
puede persistirse. También debe probar que un estado terminal válido libera el
número y que `autorizado` continúa ocupándolo. SQLite cubre la semántica local;
PostgreSQL desechable cubre el dialecto productivo. No se usarán datos ni ARCA
reales.

## Matriz mínima de pruebas

### Modelo y servicio

- aceptar cada estado legal de intento;
- rechazar un estado desconocido;
- impedir dos reservas activas iguales;
- permitir reutilizar el número después de `rechazado_arca` y
  `fallido_verificado`;
- impedir reutilizarlo después de `en_proceso`, `requiere_reconciliacion` y
  `autorizado`;
- demostrar que el conjunto del servicio coincide con el conjunto del índice;
- aceptar `borrador`, `pendiente` y `rechazado` solo sin CAE/vencimiento;
- aceptar `autorizado` con CAE de 14 caracteres y vencimiento;
- rechazar estado de comprobante desconocido;
- rechazar autorizado sin CAE, con CAE de longitud inválida o sin vencimiento;
- rechazar no autorizado con CAE o vencimiento.

### Migración SQLite

- upgrade limpio desde `f7a8b9c0d1e2` hasta el nuevo `head`;
- presencia de checks e índice parcial después del upgrade;
- aborto previo ante cada clase de dato legacy inválido;
- ausencia de cambios parciales después del aborto;
- downgrade y nuevo upgrade;
- base vacía y base con datos sintéticos válidos.

### PostgreSQL desechable

- upgrade, inspección de constraints y downgrade;
- matriz de estados y coherencia CAE;
- dos transacciones concurrentes sobre la misma reserva, con un solo ganador;
- preflight con datos sintéticos inválidos.

El checkpoint se ejecutó contra PostgreSQL 16 efímero, sin volumen persistente,
con datos sintéticos y sin ARCA. El contenedor se eliminó al terminar. Esta
evidencia valida el dialecto productivo, pero no constituye despliegue ni
sustituye el preflight obligatorio sobre un backup/restauración controlados.

## Cortes de implementación

1. **PF-01B.1 — diseño y vocabulario:** completado; estados contrastados contra
   código y riesgo de migración documentado.
2. **PF-01B.2 — modelo y migración:** completado localmente; constantes,
   constraints, preflight bloqueante, downgrade y regresiones SQLite forman un
   diff único y revisable.
3. **PF-01B.3 — validación productiva equivalente:** completado; PostgreSQL 16
   efímero aprobó migración, constraints, estados, CAE, preflight, downgrade y
   exclusión concurrente. La suite backend completa, Ruff y Black quedaron
   limpios.
4. **Checkpoint PF-01B:** completado; B10 y B17 quedaron `fixed` tras la
   revalidación secuencial con Clawpatch y PF-01 quedó cerrado antes de PF-02.

No se ejecutó `clawpatch fix`. Los cambios fiscales se implementaron
manualmente y se contrastaron con los findings después de las pruebas.

## Resultado local de PF-01B.2

La implementación agregó vocabularios canónicos en los modelos, checks de
dominio para intentos y comprobantes, coherencia persistida entre autorización,
CAE y vencimiento, y una migración Alembic bloqueante sin `UPDATE`
correctivo. El error de preflight informa únicamente categorías y cantidades.

Pruebas ejecutadas el 2026-07-13:

- `20` regresiones SQLite de modelo, estados, CAE y reservas: aprobadas;
- `7` regresiones Alembic de upgrade, bloqueo, downgrade y re-upgrade:
  aprobadas;
- `190` pruebas vecinas de facturación, API, lotes, PDF, emisores y reportes:
  aprobadas;
- Ruff, Black y `git diff --check`: limpios;
- `autoreview --mode local --engine codex --model gpt-5.5 --thinking high`:
  limpio, sin findings aceptados ni accionables, confianza `0,86`.

No hubo llamadas reales a ARCA, cambios de UI, normalización de datos legacy ni
ejecución de Clawpatch en ese corte. El checkpoint se completó después de
publicar y validar PF-01B.3.

## Resultado local de PF-01B.3

El harness `tests/integration/test_integridad_fiscal_postgresql.py` recrea solo
el schema de una base desechable explícita. Exige opt-in destructivo y un nombre
de base marcado como descartable antes de conectarse, ejecuta Alembic desde
`f7a8b9c0d1e2` y valida:

- instalación e inspección de los tres checks y conservación del índice único
  parcial;
- todos los estados canónicos, coherencia CAE y liberación terminal;
- dos transacciones concurrentes sobre la misma reserva, con un único ganador;
- downgrade limpio;
- aborto previo con las cinco categorías ambiguas y revisión Alembic sin avance.

Resultados del 2026-07-13:

- integración PostgreSQL 16: `4` pruebas aprobadas;
- backend completo: `531` pruebas aprobadas y `4` omitidas según configuración;
- Ruff sobre `app` y `tests`, Black sobre `app` y `tests` y `git diff --check`:
  limpios;
- CI de `f1219b7`: Security Audit, Backend Tests, Frontend Build y E2E Tests
  aprobados;
- `autoreview --mode local --engine codex --model gpt-5.5 --thinking high`:
  limpio, sin findings aceptados ni accionables, confianza `0,82`.

El contenedor no usó volumen persistente y fue eliminado. No se utilizaron
datos privados, certificados ni llamadas ARCA.

## Resultado del checkpoint PF-01B

El commit `6625254` se publicó en `main` y su CI `29270728104` aprobó
Security Audit, Backend Tests, Frontend Build y E2E Tests. Con el worktree
limpio, Clawpatch `0.7.0`, sin locks y usando el root/state/config backend
vigente:

- B10 quedó `fixed`: el estado inválido ya no puede eludir la reserva y la
  migración bloquea estados legacy o reservas activas duplicadas;
- B17 quedó `fixed`: la base rechaza estados desconocidos, autorizados sin CAE
  completo y no autorizados con CAE;
- ambas decisiones se ejecutaron secuencialmente con `gpt-5.6-sol` y
  razonamiento `high`;
- no se utilizó `clawpatch fix`, no hubo llamadas ARCA ni cambios de código
  durante el checkpoint.

La primera revalidación de B10 agotó el límite interno de 300 segundos después
de intentar una invocación recursiva de Clawpatch. No se tomó como evidencia de
cierre: se comprobó que el ledger seguía sin locks y se hizo un único reintento
razonable con el mismo modelo, que concluyó `fixed`. B17 concluyó `fixed` en
su primera ejecución. El cierre sanitizado está en
`docs/project/audits/clawpatch/2026-07-13-cierre-checkpoint-pf-01b.md`.

## Revisión temprana del diseño

El diff documental se revisó con `autoreview --mode local`, motor Codex,
modelo `gpt-5.5` y razonamiento `high`. La ejecución terminó correctamente sin
hallazgos aceptados ni accionables. No se modificó código, esquema ni datos como
resultado de la revisión.

## Criterio de cierre

PF-01B quedó cerrado el 2026-07-13 porque:

- el preflight no normaliza ni oculta datos ambiguos;
- SQLite y PostgreSQL aplican la misma semántica fiscal;
- la matriz de estados, CAE y concurrencia está aprobada;
- `autoreview` no deja hallazgos aceptados pendientes;
- B10 y B17 se revalidan como `fixed` o se documenta explícitamente por qué no;
- la documentación viva refleja el resultado real;
- no hubo llamadas reales a ARCA ni datos privados versionados.