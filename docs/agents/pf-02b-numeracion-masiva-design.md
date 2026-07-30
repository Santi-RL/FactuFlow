# PF-02B — Numeración masiva compatible con actividad externa

Fecha de diseño: 2026-07-29
Estado: primer corte cerrado e integrado en `main` mediante el PR `#16`
(`2c75fd2`).

## Objetivo y alcance del primer corte

Este corte extiende al request batch de `FECAESolicitar` la política segura de
PF-02A. ARCA conserva la autoridad sobre el siguiente número fiscal global y
FactuFlow conserva la autoridad sobre sus intentos propios, reservas,
idempotencia y resultados inciertos.

Incluye:

- diagnóstico inicial `alineada`, `arca_adelantada` o `local_adelantada` para
  un sublote homogéneo;
- rango consecutivo iniciado en `ultimo_arca + 1` cuando no existe un intento
  propio bloqueante;
- una reserva durable por comprobante antes de ARCA;
- segunda consulta `FECompUltimoAutorizado` después de reservar el rango
  completo e inmediatamente antes de `FECAESolicitar`;
- aborto terminal pre-ARCA de todo el sublote si el rango cambia o no puede
  reconfirmarse.

No incluye cambios dedicados a recuperación de lotes stale, UI, API o
reintentos manuales de grupos; tampoco reconstrucción histórica,
`FECompConsultar`, migraciones ni QA con CAE real. La recuperación stale
conserva una puerta estricta antes de reencolar. El reintento manual ya reutiliza
el núcleo individual compartido y por eso admite `arca_adelantada` en runtime,
pero sus transiciones y fallos todavía requieren pruebas específicas antes de
considerar cerrado ese tramo de PF-02B.

## Riesgo fiscal

El flujo batch puede solicitar varios CAE en una sola llamada. Si usa un rango
obsoleto o confunde actividad externa con un intento propio incierto, puede
reservar números incorrectos, asociar respuestas al grupo equivocado o provocar
un reintento inseguro. Los locks de FactuFlow no coordinan con otros sistemas;
por eso el segundo preflight reduce la ventana de carrera sin asumir que la
elimina.

## Invariantes verificables

1. ARCA determina el primer número del rango fiscal global.
2. FactuFlow nunca ignora un intento propio `en_proceso` o
   `requiere_reconciliacion`.
3. `arca_adelantada` sin intento propio bloqueante permite iniciar el rango en
   `ultimo_arca + 1`; no importa historia ni crea comprobantes retrospectivos.
4. `local_adelantada` bloquea el sublote antes de crear reservas.
5. Todo sublote es homogéneo por emisor, punto de venta y tipo de comprobante.
6. Cada número del rango tiene una reserva durable propia antes del segundo
   preflight.
7. El rango planificado es consecutivo, sin huecos ni solapamientos.
8. `FECAESolicitar` solo comienza si la segunda consulta confirma exactamente
   el primer número reservado.
9. Un cambio o error del segundo preflight produce cero solicitudes de CAE,
   cero comprobantes y todos los intentos en `fallido_verificado`.
10. No hay replanificación ni retry automático después del aborto: una nueva
    ejecución debe repetir diagnóstico, reservas y confirmación fiscal mediante
    el contrato idempotente del lote.
11. Un fallo posterior a iniciar `FECAESolicitar` conserva las reglas de
    reconciliación de PF-01; nunca se degrada a fallo pre-ARCA.
12. `numero_asignado` de un grupo solo procede de una respuesta fiscal o una
    reconciliación verificada, nunca del diagnóstico.
13. Fecha fiscal explícita, confirmación irreversible, receptor, totales,
    comprobantes asociados e idempotencia no cambian.
14. El aislamiento se aplica por ambiente configurado, emisor, punto de venta y
    tipo de comprobante.

## Estados y transiciones

| Estado observado | Reservas | FECAE | Resultado del sublote |
|---|---|---|---|
| `alineada` | rango desde `ultimo_arca + 1` | solo tras segundo preflight | continúa |
| `arca_adelantada` sin intento propio | mismo rango global | solo tras segundo preflight | continúa con historia externa informativa |
| `local_adelantada` | ninguna | no | bloqueado |
| intento propio activo o incierto | ninguna nueva | no | bloqueado hasta reconciliar |
| segundo preflight estable | conservadas | una llamada batch | procesa cada respuesta |
| segundo preflight cambió | `fallido_verificado` | no | aborto pre-ARCA |
| segundo preflight falló | `fallido_verificado` | no | aborto pre-ARCA |
| respuesta ambigua después de FECAE | activas/bloqueantes | ya iniciada | reconciliación PF-01 |

Las operaciones idempotentes y los grupos mantienen sus transiciones vigentes.
Este corte no agrega estados ni modifica constraints.

## Orden de operaciones

1. Normalizar y validar todos los requests del sublote.
2. Verificar homogeneidad por emisor, punto y tipo.
3. Tomar el lock local de numeración y el lock transaccional existente.
4. Validar empresa, punto de venta, certificado y habilitación WSFE.
5. Reconciliar intentos stale propios y bloquear cualquier intento propio activo
   o incierto.
6. Consultar último local y `FECompUltimoAutorizado`.
7. Rechazar `local_adelantada`; aceptar `alineada` o `arca_adelantada`.
8. Persistir una reserva por cada número consecutivo del rango.
9. Construir el request batch local sin marcar iniciada la frontera ARCA.
10. Repetir `FECompUltimoAutorizado`.
11. Si cambió o falló, cerrar todos los intentos como `fallido_verificado` y
    terminar sin FECAE.
12. Solo con coincidencia exacta, marcar la frontera irreversible e invocar
    `FECAESolicitar` una vez.
13. Ordenar y validar las respuestas por número solicitado.
14. Persistir CAE, comprobantes, intentos y resultados mediante las reglas de
    PF-01.

## Fallos intermedios y recuperación

- Una reserva duplicada o una carrera local queda protegida por el lock y el
  índice parcial de reservas activas.
- Una falla temporal de base durante la reserva conserva la política actual de
  recuperación; no se transforma en un aborto terminal optimista.
- Una falla local no transitoria durante la preparación cierra las reservas ya
  creadas como `fallido_verificado`.
- Si falla el cierre de un intento después del segundo preflight, ese intento
  puede permanecer bloqueante, pero no hay riesgo de CAE porque FECAE no comenzó.
- Un rechazo explícito de ARCA después del segundo preflight sigue siendo
  verificable y no habilita retry automático.
- Una excepción o respuesta incompleta después de iniciar FECAE conserva
  `requiere_reconciliacion` y el número reservado.

## Concurrencia y constraints

- El lock en memoria serializa el servicio por emisor, punto y tipo dentro del
  proceso.
- El lock de base existente protege la numeración entre sesiones de la
  instalación.
- `uq_intentos_emision_fiscal_reserva_activa` impide dos reservas activas para
  el mismo emisor, punto, tipo y número en SQLite y PostgreSQL.
- Los sistemas externos no comparten esos locks. La segunda consulta reduce la
  carrera; un avance posterior todavía puede producir un rechazo explícito de
  consecutividad, tratado sin inferir autorización.
- El procesamiento sigue siendo secuencial por worker y no se amplía la
  concurrencia fiscal.

## Migraciones y datos legacy

No se requieren migraciones, nuevos estados ni normalización de datos legacy.
El corte usa columnas, índices y transiciones existentes. Si las pruebas
demostraran que falta evidencia durable para distinguir un aborto batch, el
diseño debe revisarse antes de agregar metadata o una migración.

## Contratos externos

- `FECompUltimoAutorizado`: diagnóstico inicial y reconfirmación del primer
  número del rango.
- `FECAESolicitar`: una única llamada con varios detalles, solo después de las
  reservas y la reconfirmación.
- `FECompConsultar`: fuera de alcance; permanece reservado para reconciliación
  e historia opcional según PF-01/PF-05.

Las pruebas usan dobles controlados y no realizan llamadas reales a ARCA.

## Matriz automatizada del primer corte

- alineación local/ARCA y rango consecutivo;
- historia local parcial con rango desde `ultimo_arca + 1`;
- `local_adelantada`, sin reservas ni FECAE;
- intento propio `en_proceso` o `requiere_reconciliacion`, sin reservas nuevas;
- avance externo entre ambos preflights, con todos los intentos
  `fallido_verificado`, cero FECAE y cero comprobantes;
- error del segundo preflight con el mismo cierre seguro;
- falla intermedia al crear reservas;
- replay idempotente igual y conflicto con payload distinto, cubiertos por las
  pruebas API existentes y regresión del servicio de lotes;
- respuesta batch incompleta o ambigua post-FECAE, con reconciliación;
- homogeneidad y aislamiento por emisor, punto y tipo;
- preservación de fecha fiscal explícita y confirmación irreversible mediante
  las regresiones vigentes de lotes.

La concurrencia real del índice parcial ya está cubierta por el harness
PostgreSQL de integridad fiscal. Este corte agrega pruebas unitarias de la
carrera externa entre preflights; no duplica el harness de migración porque no
cambia el esquema.

## Criterio de cierre del primer corte

- `9` pruebas batch enfocadas aprobadas;
- `147` pruebas de facturación y lotes aprobadas;
- backend completo: `539` pruebas aprobadas y `4` omitidas por harness
  condicionado;
- Ruff, Black y `git diff --check` limpios;
- única revisión efectiva con Codex `gpt-5.6-sol`, thinking `medium`, sin
  findings y con confianza `0,94`;
- PR `#16` integrado después de aprobar los seis checks: Change Scope,
  Repository Checks, Backend Tests, Security Audit, Frontend Build y E2E Tests;
- documentación de diseño y contratos ARCA actualizada;
- cero CAE reales, cero emisiones, cero llamadas ARCA de escritura y cero datos
  privados.
