# PF-02B — Numeración masiva compatible con actividad externa

Fecha de diseño: 2026-07-29
Estado: PF-02B cerrado en tres cortes: batch, reintentos manuales y recuperación
stale compatible con historia externa.

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

El primer corte no incluyó cambios dedicados a recuperación de lotes stale, UI,
API o reintentos manuales de grupos; tampoco reconstrucción histórica,
`FECompConsultar`, migraciones ni QA con CAE real. La recuperación stale
conserva una puerta estricta antes de reencolar. El segundo corte que cierra el
contrato del reintento manual se documenta más abajo.

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

## Diseño del segundo corte: PF-02B.2 — reintentos manuales

### Causa raíz y alcance

Antes de este corte, el endpoint manual `reintentar-fallidos` ya reutilizaba el
núcleo individual de `FacturacionService` y, por lo tanto, admitía
`arca_adelantada` en runtime. Sin embargo, el contrato específico del lote no
demostraba qué ocurría con el grupo reclamado, los grupos restantes, la
operación idempotente y los intentos fiscales ante cada resultado del doble
preflight o después de iniciar `FECAESolicitar`.

El corte cierra esa frontera con pruebas end-to-end de backend y con ajustes
mínimos en el servicio de lotes. No cambia el contrato HTTP, la UI, los modelos,
las constraints ni el esquema de base. Tampoco modifica la recuperación stale
del worker, que corresponde a PF-02B.3.

Consumidores revisados:

- `POST /api/lotes-comprobantes/{lote_id}/reintentar-fallidos`;
- `LoteComprobantesService.reintentar_grupos_fallidos` y sus transiciones de
  grupo, filas, lote y eventos;
- `FacturacionService._emitir_comprobante_locked`, compartido con emisión
  individual y procesamiento unitario de lotes;
- `IdempotenciaFiscalService`, operaciones e intentos vinculados a lote/grupo;
- `_aplicar_resultado_emision_grupo`, compartido por procesamiento unitario,
  batch y reintento manual;
- el frontend de lotes, que ya envía confirmación fiscal e idempotencia y
  bloquea el reintento cuando el lote requiere reconciliación;
- el worker stale, revisado como consumidor vecino pero expresamente excluido
  de cambios en este corte.

### Invariantes adicionales de PF-02B.2

1. Solo un grupo `fallido` del lote y emisor activos puede pasar por CAS a
   `reintentando`; ningún request paralelo puede reclamarlo dos veces.
2. La fecha fiscal y el punto de venta se recalculan desde los grupos elegidos y
   deben coincidir con la confirmación exacta antes de reclamar el primer grupo.
3. La operación exige `X-Idempotency-Key`. Misma clave y mismo material fiscal
   devuelve el resultado guardado sin otra llamada ARCA; la misma clave con una
   selección o payload distinto responde conflicto.
4. `arca_adelantada` sin intento propio bloqueante usa `ultimo_arca + 1`, crea
   una reserva vinculada al lote/grupo y repite el preflight antes de FECAE.
5. `local_adelantada`, un intento propio activo o incierto y un replay
   conflictivo bloquean sin crear una nueva reserva ni solicitar CAE.
6. Si el segundo preflight cambia o falla, el intento queda
   `fallido_verificado`, el grupo vuelve a `fallido` sin CAE,
   `numero_asignado` ni comprobante, y se detiene la selección. Los grupos aún
   no reclamados permanecen intactos.
7. Un rechazo ARCA explícito y completo puede dejar el grupo `fallido`; una
   respuesta ambigua o una excepción posterior a iniciar FECAE nunca puede
   degradarlo a `fallido` ni habilitar otro reintento.
8. Si el núcleo devuelve o la capa de lote detecta incertidumbre post-ARCA, el
   grupo y el lote quedan `requiere_reconciliacion`, el intento conserva número
   y CAE conocidos y no se procesa ningún grupo posterior de la selección.
9. Una excepción inesperada posterior a ARCA se registra con mensaje público
   sanitizado. Rutas, credenciales, SQL, certificados y detalles internos quedan
   únicamente en logs privados.
10. `numero_asignado` solo se completa desde un resultado fiscal conocido o una
    reconciliación verificada; nunca desde el diagnóstico inicial.
11. Los grupos ya autorizados antes de una incertidumbre posterior conservan su
    autorización. No se revierte evidencia fiscal ni se reejecuta la operación
    completa.
12. El aislamiento permanece por ambiente, emisor, lote, punto de venta, tipo y
    grupo. Un ID de otro emisor no alcanza el servicio fiscal.

### Tabla de estados del reintento manual

| Situación del grupo reclamado | Intento | Grupo | Lote | Grupos posteriores | FECAE |
|---|---|---|---|---|---|
| `arca_adelantada` estable y CAE autorizado | `autorizado` | `autorizado` | recalculado | pueden continuar | una por grupo |
| `local_adelantada` o intento propio bloqueante | sin intento nuevo | `fallido` | recalculado | se detienen | no |
| segundo preflight cambió o falló | `fallido_verificado` | `fallido` | recalculado | se detienen intactos | no |
| rechazo ARCA explícito | `rechazado_arca` | `fallido` | recalculado | pueden continuar | iniciada |
| respuesta o excepción post-ARCA incierta | `requiere_reconciliacion` | `requiere_reconciliacion` | `requiere_reconciliacion` | se detienen intactos | iniciada |
| caída DB pre-ARCA sin intentos y recuperación durable | ninguno | vuelve a `fallido` | recalculado | no procesados | no |
| caída DB con intento o después de ARCA | bloqueante | `reintentando` o `requiere_reconciliacion` | bloqueado | no procesados | posible |

### Orden de operaciones del segundo corte

1. Verificar usuario, emisor activo y pertenencia del lote.
2. Resolver la operación idempotente con la selección y la huella estable de
   los payloads fiscales.
3. Recalcular y validar confirmación de fecha fiscal y punto de venta.
4. Validar la confirmación adicional de duplicado lógico cuando corresponda.
5. Obtener únicamente grupos `fallido` de la selección.
6. Reclamar cada grupo mediante `fallido -> reintentando` antes de entrar al
   núcleo fiscal.
7. Ejecutar diagnóstico, reserva durable y segundo preflight mediante el núcleo
   individual compartido.
8. Aplicar y persistir el resultado del grupo, sus filas, intento, comprobante,
   evento y resumen del lote.
9. Detener inmediatamente la selección ante bloqueo de numeración, aborto del
   segundo preflight o incertidumbre post-ARCA.
10. Guardar la respuesta idempotente final con estado `finalizado` o
    `requiere_reconciliacion` según el lote.

### Fallos intermedios, concurrencia y recuperación

- El CAS de grupo impide doble reclamo aunque dos requests superen lecturas
  previas simultáneas.
- La operación idempotente protege doble click, replay y selección conflictiva.
- Una caída durablemente recuperable antes de crear intentos restaura solo el
  grupo reclamado y abre replay con la misma clave.
- Una caída con intento existente no se presenta como reintentable: conserva la
  clave y responde el bloqueo pre-ARCA vigente.
- Una excepción al trasladar un resultado post-ARCA a grupo/lote debe hacer
  rollback de la transacción incompleta y reconstruir un estado
  `requiere_reconciliacion` desde el intento y la respuesta conocida. Si ese
  cierre tampoco puede persistirse, el grupo `reintentando` y el intento activo
  siguen siendo bloqueantes y la API responde `409`.
- No hay migración. Las constraints e índices parciales vigentes continúan como
  defensa SQLite/PostgreSQL.

### Matriz automatizada de PF-02B.2

- historia local parcial y ARCA estable: autoriza `ultimo_arca + 1`, vincula
  operación/intento/grupo y el replay exacto no vuelve a consultar ni emitir;
- avance externo y error en el segundo preflight: cero FECAE, intento
  `fallido_verificado`, grupo sin número/CAE/comprobante y selección detenida;
- `local_adelantada`: cero intentos nuevos y cero FECAE;
- intento propio `en_proceso` y `requiere_reconciliacion`: cero reservas nuevas
  y cero FECAE;
- respuesta post-ARCA ambigua: primer grupo y lote en reconciliación, grupos
  restantes intactos y ninguna llamada fiscal posterior;
- excepción de persistencia de la capa de lote después de un resultado
  autorizado: nunca vuelve a `fallido`, conserva evidencia conocida y bloquea;
- rechazo ARCA explícito: grupo `fallido`, intento `rechazado_arca` y sin
  reconciliación falsa;
- misma clave con mismo material: replay sin nueva ejecución; misma clave con
  selección distinta: `409`;
- doble reclamo concurrente: un único grupo entra al núcleo;
- emisor ajeno: rechazo antes del servicio fiscal;
- regresiones existentes de fecha fiscal, duplicado lógico, caída DB pre/post
  ARCA, procesamiento normal unitario/batch y worker stale estricto.

No se realizan llamadas ARCA reales. Las pruebas usan dobles controlados y
datos fiscales sintéticos.

## Diseño del tercer corte: PF-02B.3 — recuperación stale compatible con historia externa

### Autoridad, causa raíz y unidad vertical

ARCA conserva la autoridad sobre el último comprobante autorizado de cada
ambiente, emisor, punto de venta y tipo. FactuFlow conserva la autoridad sobre
sus intentos propios, la idempotencia, las reservas, los estados locales y toda
incertidumbre que pueda haber comenzado `FECAESolicitar`.

La recuperación stale ya distingue grupos intactos de grupos con evidencia
fiscal, reconcilia únicamente evidencia local fuerte y nunca toma la expiración
del lote como prueba de que ARCA no autorizó. La causa raíz pendiente es más
acotada: su preflight final todavía exige igualdad estricta entre la historia
local y ARCA mediante un helper anterior a PF-02A. Por eso bloquea actividad
externa legítima que el procesamiento individual, batch y el reintento manual ya
tratan de forma segura como `arca_adelantada`.

La unidad vertical de PF-02B.3 reemplaza esa igualdad estricta por el mismo
diagnóstico fiscal compartido que ya protege los demás caminos. El worker puede
reencolar grupos realmente intactos tanto con numeración `alineada` como con
`arca_adelantada`, pero no asigna números, no crea intentos, no solicita CAE y no
omite el segundo preflight inmediatamente anterior a `FECAESolicitar`.

No requiere modelo, migración, estados nuevos, rutas ni schemas de API, ni UI.
Tampoco importa historia externa, reconstruye comprobantes ajenos ni incorpora
el alcance opcional de PF-05.

Consumidores auditados:

- `LoteWorker`, incluida la prioridad de lotes stale sobre lotes nuevos y la
  detención conservadora del ciclo ante un bloqueo incompleto;
- `bloquear_lote_procesando_stale`, la clasificación de grupos intactos, la
  reconciliación local fuerte y los eventos operativos;
- procesamiento normal unitario y batch, que vuelven a diagnosticar, crean
  reservas durables y ejecutan el segundo preflight antes de FECAE;
- reintento manual, cuyo CAS de grupo e idempotencia no admiten lotes
  `en_cola`, `procesando` ni `requiere_reconciliacion`;
- `FacturacionService`, resolución de intentos propios stale,
  `FECompUltimoAutorizado` y confirmación de reservas;
- `IdempotenciaFiscalService`, el índice parcial de reservas activas y las
  operaciones vinculadas al lote;
- reconciliación local y ARCA mediante `FECompConsultar` para intentos propios;
- endpoints y frontend de lotes, que conservan el contrato HTTP, la
  confirmación fiscal y los bloqueos visuales vigentes.

### Invariantes adicionales de PF-02B.3

1. El vencimiento de `BATCH_PROCESSING_STALE_MINUTES` solo habilita diagnóstico;
   nunca demuestra ausencia de autorización ni libera una reserva fiscal.
2. Un grupo reencolable no tiene intento fiscal de ningún estado, CAE, número,
   comprobante vinculado ni comprobante local autorizado candidato con la misma
   huella fiscal.
3. Cualquier intento propio `en_proceso` activo o
   `requiere_reconciliacion`, del lote o de la misma combinación fiscal,
   bloquea la reanudación y toda nueva reserva.
4. Un intento propio `en_proceso` vencido solo deja de ser incierto si
   `FECompConsultar` confirma explícitamente que el comprobante no existe y el
   intento pasa a `fallido_verificado`, o si confirma una autorización que puede
   reconstruirse y vincularse con evidencia local completa. Una consulta ambigua
   o inconsistente conserva `requiere_reconciliacion`.
5. Un intento autorizado solo se vincula automáticamente con un comprobante
   local completo y coherente en intento, payload, emisor, punto, tipo, número,
   fecha fiscal, receptor, total y CAE. Autorizado sin comprobante local no
   habilita reemisión.
6. Los grupos mixtos se evalúan como una sola decisión conservadora: si algún
   grupo tiene evidencia fiscal o alguna combinación no supera el preflight,
   ningún grupo intacto se reencola por separado.
7. `alineada` y `arca_adelantada` son diagnósticos reencolables solo cuando no
   existe incertidumbre propia. `local_adelantada` siempre bloquea.
8. El preflight stale consulta una vez cada combinación única de ambiente
   configurado, emisor, punto de venta y tipo; un ID de otro emisor se rechaza
   antes de cualquier continuidad fiscal.
9. El diagnóstico nunca escribe `numero_asignado`, crea una reserva, cambia la
   fecha fiscal ni solicita CAE. La fecha explícita del payload se conserva sin
   usar la fecha actual como valor predeterminado.
10. Después de reencolar, el procesamiento normal vuelve a reclamar el lote de
    forma atómica. Dos workers pueden observarlo, pero solo uno puede pasar
    `en_cola -> procesando` y entrar al núcleo fiscal.
11. El núcleo normal repite `FECompUltimoAutorizado` después de crear la reserva
    o el rango durable e inmediatamente antes de FECAE. Un avance externo entre
    el preflight stale y esa segunda consulta produce cero FECAE.
12. La carrera con un reintento manual no habilita dos emisiones: el reintento
    rechaza lotes activos y la reserva parcial única protege la combinación
    fiscal entre sesiones.
13. Un fallo del preflight deja los grupos intactos sin número, CAE ni
    comprobante; el lote pasa a `requiere_reconciliacion` y no sigue el ciclo
    automático.
14. Los metadatos expuestos por la API solo conservan categorías estables de
    error. Rutas, URLs internas, certificados, credenciales y textos de
    excepciones quedan únicamente en logs privados.

### Tabla de estados de la recuperación stale

| Situación observada | Intentos/grupos | Lote | Acción ARCA | Resultado |
|---|---|---|---|---|
| todos los grupos autorizados con evidencia fuerte | `autorizado` y vinculados | cierre terminal vigente | ninguna escritura | cierra sin nuevos CAE |
| autorizado sin comprobante local o evidencia incompleta | bloqueante | `requiere_reconciliacion` | ninguna escritura | no reencola |
| intento propio activo o incierto | se conserva | `requiere_reconciliacion` | consulta segura solo si corresponde | no libera ni reemite |
| intento propio stale y ARCA confirma inexistencia | `fallido_verificado` | continúa el diagnóstico | `FECompConsultar` lectura | puede dejar de bloquear |
| intento propio stale y autorización totalmente verificable | `autorizado` y vinculado | continúa el diagnóstico | `FECompConsultar` lectura | no reemite lo ya autorizado |
| todos los pendientes intactos y `alineada` | sin intentos ni números | `en_cola` | `FECompUltimoAutorizado` lectura | procesamiento normal posterior |
| todos los pendientes intactos y `arca_adelantada` | sin intentos ni números | `en_cola` | `FECompUltimoAutorizado` lectura | usa historia externa solo como diagnóstico |
| `local_adelantada`, error o combinación insegura | intactos preservados | `requiere_reconciliacion` | cero FECAE | bloqueo conservador |
| avance externo después de reencolar | reservas cerradas `fallido_verificado` | recalculado por núcleo | segunda lectura; cero FECAE | nueva ejecución explícita requerida |

### Orden de operaciones del tercer corte

1. Detectar un lote `procesando` cuya actualización superó la ventana stale.
2. Reconciliar únicamente grupos autorizados respaldados por evidencia local
   fuerte y recalcular el lote.
3. Si el lote quedó terminal, exigir ausencia de intentos inciertos y coherencia
   fiscal completa antes de cerrarlo sin solicitar CAE.
4. Clasificar cada grupo válido como intacto o con evidencia fiscal.
5. Exigir que todos los pendientes sean intactos, que no exista evidencia
   fiscal ambigua y que el lote no conserve intentos propios inciertos.
6. Validar el payload fiscal persistido, su emisor y las combinaciones únicas de
   punto de venta y tipo.
7. Para cada combinación, validar empresa, certificado, punto habilitado e
   intentos propios mediante el diagnóstico compartido.
8. Consultar último local y `FECompUltimoAutorizado`; rechazar
   `local_adelantada` y aceptar `alineada` o `arca_adelantada`.
9. Si todas las combinaciones son seguras, persistir solo la transición del lote
   a `en_cola`, el diagnóstico y el evento de recuperación. Los grupos siguen
   sin número, CAE, intento ni comprobante.
10. Si alguna combinación falla, preservar los intactos, marcar únicamente los
    grupos con evidencia fiscal y bloquear el lote para reconciliación con una
    categoría pública sanitizada.
11. El worker vuelve a seleccionar el lote; el CAS existente permite un único
    ganador para `en_cola -> procesando`.
12. El procesamiento normal repite diagnóstico, crea reservas durables y exige
    su segundo preflight antes de cualquier `FECAESolicitar`.

### Concurrencia, fallos intermedios y recuperación

- Dos ciclos de worker no comparten autoridad fiscal externa. La recuperación
  stale no emite y el reclamo atómico posterior impide que ambos entren al
  núcleo fiscal con el mismo lote.
- Un reintento manual concurrente se bloquea por el estado activo del lote; si
  dos operaciones alcanzaran la numeración por caminos distintos, el lock de
  base y `uq_intentos_emision_fiscal_reserva_activa` impiden reservas activas
  duplicadas.
- Un avance externo entre consultas no se compensa ni replantea bajo la misma
  ejecución. El segundo preflight normal cierra la reserva como
  `fallido_verificado` y termina antes de FECAE.
- Una caída de base temporal conserva su excepción para que el worker detenga
  el ciclo; no se transforma en un lote falsamente seguro.
- Un error de certificado, WSAA, punto de venta o consulta de numeración bloquea
  la reanudación. El traceback se registra en logs privados y la respuesta
  persistida usa una categoría estable.
- Si una autorización ya existe pero falta evidencia local suficiente, no hay
  rollback destructivo ni reconstrucción optimista: el intento y el lote
  permanecen bloqueantes hasta reconciliación.
- Los datos legacy no se normalizan ni se completan. Un payload ausente o
  inválido es evidencia insuficiente y produce bloqueo conservador.

### Migraciones, contratos y cortes posteriores

No se requieren migraciones, backfill ni nuevos índices. El contrato usa el
diagnóstico, los estados y las constraints existentes. No cambia el contrato
HTTP ni la estructura visible de fechas; los metadatos de recuperación agregan
el diagnóstico seguro y reemplazan detalles de excepción por categorías
sanitizadas.

`FECompUltimoAutorizado` y, solo para resolver intentos propios stale,
`FECompConsultar` son lecturas. PF-02B.3 no agrega llamadas ARCA de escritura;
`FECAESolicitar` permanece exclusivamente en el procesamiento normal posterior
con confirmación fiscal e idempotencia vigentes.

No quedan unidades funcionales adicionales dentro de PF-02B.3. La importación o
reconstrucción de historia externa para informes continúa separada en PF-05.

### Matriz automatizada de PF-02B.3

- preflight compartido con historia alineada: devuelve próximo número y
  diagnóstico completos;
- historia externa legítima: acepta `arca_adelantada` y propone
  `ultimo_arca + 1` sin crear intento ni comprobante;
- `local_adelantada`: bloquea antes de reencolar;
- lote stale parcial con autorizado fuerte e intacto: reconcilia el primero,
  reencola el segundo y conserva número/CAE/comprobante vacíos;
- combinaciones mixtas alineada y `arca_adelantada`: todas deben aprobar y el
  diagnóstico se registra por combinación;
- una combinación insegura en un grupo mixto: ningún intacto se reencola;
- intento propio `en_proceso` activo o `requiere_reconciliacion`: cero reservas
  nuevas, cero FECAE y bloqueo;
- autorizado con y sin comprobante local, candidato local sin intento e
  intentos autorizados duplicados: solo la evidencia fuerte cierra o vincula;
- error inesperado del preflight: grupos intactos preservados, categoría pública
  sanitizada y ausencia del detalle sensible en lote y evento;
- doble recuperación: el segundo intento no duplica la transición; el CAS
  vigente prueba un único reclamo del procesamiento;
- carrera worker/reintento manual: los estados activos no son resolubles por el
  endpoint manual;
- avance externo entre consultas: regresiones individual, batch y reintento
  demuestran segundo preflight, intentos `fallido_verificado` y cero FECAE;
- aislamiento por emisor, punto y tipo, fecha fiscal explícita e idempotencia:
  regresiones vigentes del servicio y la API.

Todas las pruebas usan dobles controlados, fechas explícitas y datos sintéticos.
No solicitan CAE real ni realizan escrituras en ARCA.

### Evidencia automatizada del tercer corte

- `12` pruebas enfocadas de diagnóstico y recuperación stale;
- `164` pruebas de facturación y lotes;
- backend completo: `557` aprobadas y `4` omitidas por harness configurado;
- frontend: `131` unitarias y `33` E2E;
- `16` pruebas de scripts de repositorio;
- Ruff, Black, ESLint sin errores, type-check y build aprobados;
- `docs:check`, `pip-audit` y `npm audit --omit=dev` aprobados;
- cero migraciones, cero CAE reales, cero emisiones y cero llamadas ARCA de
  escritura.
