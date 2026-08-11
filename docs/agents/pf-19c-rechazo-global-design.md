# PF-19C — rechazo global excluyente y resolución legacy

## Estado y alcance

Este documento define el corte fiscal bloqueante de `v0.3.0` que completa
PF-19. Su alcance es deliberadamente cerrado:

- conservar la respuesta global de `FECAESolicitar` como datos estructurados;
- reconocer únicamente el código entero exacto `10005` como rechazo global
  excluyente, y solo cuando la respuesta completa sea coherente;
- cerrar de forma segura el sublote afectado y detener los grupos todavía no
  enviados;
- mantener en reconciliación toda respuesta desconocida, parcial,
  contradictoria o no verificable;
- ofrecer una resolución administrativa, auditable e idempotente para los
  candidatos legacy identificados por PF-19A.

Quedan fuera de este corte otros códigos globales, reconstrucción histórica
general, observabilidad fiscal avanzada, reintentos automáticos y cualquier
emisión real destinada a provocar un error de ARCA. Esos descubrimientos solo
pueden incorporarse al roadmap posterior a `v0.3.0`.

## Autoridad normativa

La fuente normativa es el manual oficial WSFEv1 v4.6, revisión 01/08/2026,
enlazado desde el índice oficial de factura electrónica de ARCA. La tabla de
validaciones excluyentes de `FeCabReq.PtoVta` define el entero `10005`: el punto
de venta debe estar dado de alta y ser RECE. El manual también establece que
los problemas de emisor o cabecera rechazan el requerimiento completo y se
informan en `Errors`.

El mismo manual contiene un ejemplo que imprime `1005`. Esa inconsistencia no
amplía el contrato: PF-19C acepta solo el entero exacto `10005`. El entero
`1005`, strings, floats, booleanos y mensajes que contengan el texto `10005`
permanecen inciertos.

## Invariantes

1. Ninguna decisión fiscal se toma a partir del texto libre de ARCA.
2. Los errores globales, eventos y cabecera se preservan por separado.
3. Solo una respuesta global completamente parseada, correlacionada y no
   contradictoria puede ser terminal.
4. `10005` alcanza exclusivamente al request exacto que llegó a ARCA. Los
   grupos posteriores se cierran localmente como no enviados, no como
   rechazados por ARCA.
5. Un rechazo global terminal no crea CAE ni comprobante local.
6. Si la persistencia posterior a ARCA no puede cerrarse de forma durable, no
   se publica un terminal incompleto: el grafo queda bloqueado para
   reconciliación.
7. El replay de una operación terminal nunca vuelve a llamar WSAA, WSFE ni
   `FECAESolicitar`.
8. Toda correlación conserva empresa, ambiente, punto, tipo, operación,
   guarda, intento, lote y grupo exactos.
9. Un candidato legacy textual no prueba por sí solo ni el código ni la causa
   histórica. La resolución solo puede acreditar autorización o ausencia de
   autorización en el ambiente consultado.
10. No se corrige historia fiscal mediante SQL manual, edición de CAE o
    creación de comprobantes inventados.

## Contrato estructurado del adaptador WSFE

El adaptador conserva, en una excepción tipada de error global:

- operación `FECAESolicitar`;
- cabecera recibida: CUIT, punto, tipo, cantidad y resultado;
- lista ordenada de errores `{codigo, mensaje}`;
- lista ordenada de eventos `{codigo, mensaje}`;
- presencia de detalles y señales de CAE;
- punto, tipo, cantidad y rangos del request correlacionado.

Los mensajes crudos sirven únicamente para logging privado. La respuesta
durable y pública conserva códigos y alcance, con texto sanitario controlado
por FactuFlow.

La clasificación pura recibe la excepción estructurada y el request exacto.
Devuelve uno de estos valores:

- `rechazo_global_excluyente`;
- `respuesta_incierta`.

No se agregan heurísticas por mensaje, prefijo, substring o cercanía numérica.

## Tabla de clasificación

| Evidencia recibida | Resultado PF-19C |
|---|---|
| Cabecera `R` exacta, `Errors=[10005]`, sin detalles ni CAE | rechazo global excluyente |
| Caso anterior con `Events` | rechazo global excluyente; eventos no deciden |
| `10005` mezclado, duplicado o acompañado por otro código | respuesta incierta |
| `1005`, `"10005"`, `10005.0`, `true` o texto libre | respuesta incierta |
| Cabecera ausente, `A`, `P` o discordante | respuesta incoherente |
| Cualquier detalle, CAE o rango junto con `10005` | respuesta contradictoria |
| Todos los detalles exactos en `R`, sin CAE | rechazo por detalle ya soportado |
| Mezcla `A/R`, resultado `P`, detalle faltante, extra o duplicado | respuesta parcial |
| Timeout, SOAP Fault, transporte o deserialización | respuesta incierta |

Para ser terminal deben cumplirse simultáneamente:

1. respuesta SOAP completamente parseada;
2. `FeCabResp.Resultado == "R"`;
3. CUIT, punto, tipo y `CantReg` iguales al emisor y request exactos;
4. un único error cuyo `Code` sea un entero no booleano igual a `10005`;
5. ausencia total de `FeDetResp` y de CAE;
6. grafo durable exacto de operación, guarda e intentos.

## Persistencia y estados

La respuesta pública y durable agrega una lista estructurada sanitaria de
errores ARCA con `codigo` y `alcance=global`. El intento conserva la misma
evidencia estructurada en una columna JSON canónica; los registros legacy
anteriores a PF-19C permanecen con valor nulo.

Categorías nuevas:

- `arca_rechazo_global_excluyente`: rechazo terminal confirmado por contrato;
- `no_enviado_por_rechazo_global`: cierre local de grupos posteriores;
- `legacy_sin_autorizacion_verificada`: ausencia comprobada mediante consultas
  seguras, sin atribuir retrospectivamente la causa a `10005`.

Transiciones ante un `10005` válido:

| Entidad | Transición |
|---|---|
| intentos del sublote enviado | `en_proceso -> rechazado_arca` |
| guarda del sublote | `arca_iniciada -> cerrada_terminal` |
| grupos/filas del sublote | `procesando -> fallido`, categoría global terminal |
| grupos/filas posteriores no enviados | `procesando -> fallido`, causa local no enviado |
| lote | contadores recalculados y cierre con errores |
| operación idempotente | respuesta terminal del lote o emisión, por CAS |

El cierre del rechazo global se difiere al caller cuando este es dueño del
lote. Así intentos, guarda, grupos, filas y lote comparten la transacción de
cierre. La publicación de la operación usa el CAS existente; si esa
publicación pierde una carrera, el grafo fiscal ya cerrado impide una nueva
emisión y el replay debe reconstruir el terminal sin llamar a ARCA.

El ownership es evidencia durable, no una inferencia por estado. La operación
`A` solo puede publicar o inmovilizar su propio grafo si conserva
`operacion_id=A`, empresa, lote, snapshots RECE, versión y respuesta esperada.
Si en una carrera el owner pasa de `A` a `B`, `A` no puede publicar ni emitir
sobre `B`: recarga el grafo y devuelve el terminal de su dueño real o conserva
reconciliación. El worker aplica el mismo CAS sobre su marcador canónico
`en_progreso`; no toma una operación síncrona ni una respuesta de otro owner.

En emisión individual, el caller publica la respuesta idempotente en la misma
transacción diferida que cierra intento y guarda. Los usos directos internos
que no posean una operación publicable cierran su grafo fiscal antes de
retornar.

## Orden de operaciones actual

1. validar elegibilidad RECE y ownership PF-19B;
2. crear y confirmar guarda e intentos pre-ARCA;
3. marcar la guarda `arca_iniciada` de forma durable;
4. llamar una sola vez a `FECAESolicitar`;
5. parsear y clasificar la respuesta estructurada;
6. bloquear operación -> intentos ordenados -> guardas -> lote -> grupos y
   filas ordenados;
7. validar nuevamente identidad, snapshots RECE, estado y cardinalidad;
8. persistir el cierre completo y la evidencia estructurada;
9. publicar la respuesta terminal por CAS;
10. devolver el replay durable sin otra llamada externa.

Como política local fail-closed, se aborta el lote seleccionado completo aunque
los grupos posteriores pertenezcan a otra tupla de punto y tipo. Esos grupos se
marcan como no enviados antes del commit que cierra el lote y permanecen
reintentables mediante el flujo seguro. El procesador abandona el bucle
inmediatamente después. Ninguna respuesta local afirma que ARCA rechazó un
grupo que no fue enviado.

La publicación idempotente distingue dos contratos:

- el procesamiento síncrono solo puede publicar desde `response_json` SQL
  `NULL`, con estado y versión esperados;
- el worker solo puede reemplazar su respuesta canónica `en_progreso`, ligada
  al lote, empresa, operación y material RECE exactos, también por CAS de
  estado y versión.

Si cualquiera de los CAS pierde, se recarga el grafo. Un terminal ya publicado
se devuelve como replay; un estado incompatible queda bloqueado y no vuelve a
llamar a ARCA.

## Resolución administrativa legacy

La resolución se implementa como servicio interno y CLI privada de dos fases.
No reutiliza el endpoint de reconciliación externa, porque ese endpoint crea un
comprobante autorizado y el caso legacy puede acreditar exactamente lo
contrario.

### Fase `plan`

- siempre read-only y con rollback;
- recibe un único `intento_id`, empresa, punto, tipo y ambiente explícitos;
- reutiliza el inventario PF-19A y exige
  `candidato_10005_no_confirmado`;
- rechaza CAE, comprobante, referencias cruzadas, estados terminales, siblings
  inciertos o una operación cuyo sublote histórico no pueda reconstruirse;
- genera un `plan_sha256` determinista con IDs, estados, versiones y
  precondiciones;
- no llama a ARCA ni escribe la base.

### Fase `apply`

Exige:

- ventana de mantenimiento para la tupla empresa/punto/tipo;
- backup inmediato y restaurable, identificado por timestamp, propósito,
  commit/tag y SHA-256, sin guardar el path ni el dump en el repo;
- plan inmutable y confirmación administrativa explícita;
- alcance de ambientes derivado de evidencia durable, nunca elegido libremente
  por el operador.

Si el intento conserva `ambiente` durable, se consulta solo ese ambiente. Si
el intento legacy tiene ambiente nulo, el plan fija obligatoriamente producción
y homologación; el cierre terminal solo es posible cuando ambas consultas
demuestran ausencia. Un fallo o una evidencia de autorización en cualquiera de
ellas conserva reconciliación.

Orden:

1. advisory lock fiscal y filas en orden determinista;
2. recargar todo con `FOR UPDATE`, recalcular el plan y abortar si cambió;
3. consultar `FECompUltimoAutorizado` para cada ambiente fijado por el plan;
4. llamar `FECompConsultar` solo si el último autorizado de ese ambiente es
   mayor o igual al número planificado;
5. clasificar y escribir un journal append-only en el mismo commit.

| Consulta segura | Acción |
|---|---|
| todos los ambientes requeridos tienen último autorizado menor al planificado | ausencia verificada; cierre `fallido_verificado` |
| algún ambiente tiene último mayor/igual y comprobante exacto autorizado | no cerrar; derivar a reconciliación autorizada |
| último mayor/igual y la consulta no devuelve un comprobante exacto | sin cambio; continúa reconciliación |
| timeout, error desconocido o respuesta inconsistente en cualquier ambiente | sin cambio; continúa reconciliación |

La ausencia de autorización no prueba que la causa histórica haya sido
`10005`. Por eso el cierre legacy usa
`legacy_sin_autorizacion_verificada`, no
`arca_rechazo_global_excluyente` ni `rechazado_arca`.

El journal no guarda CUIT, CAE, payload, mensaje SOAP, DSN, credenciales, rutas
ni contenido del backup. Conserva IDs internos, acción, `actor_usuario_id`,
ambientes consultados, resultados sanitizados de consultas, digest y metadatos
mínimos del backup, timestamp y resultado. Una FK compuesta prueba que intento
y empresa coinciden, y una constraint única impide dos cierres terminales del
mismo intento. El journal se inserta solo cuando existe una mutación terminal;
los resultados sin cambio se devuelven de forma sanitaria. La base impide
`UPDATE` y `DELETE` sobre el journal tanto en PostgreSQL como en SQLite.

La revisión Alembic `c0d1e2f3a4b` agrega `errores_arca_json` al intento y el
journal, su FK compuesta intento/empresa, hashes obligatorios, unicidad por
intento y triggers append-only. Su downgrade falla cerrado si ya hay evidencia
estructurada o una resolución administrativa: nunca borra historia aceptada.
El paquete privado de migración VPS valida la coherencia de esa evidencia, pero
omite del traslado los intentos, guardas, lotes, grupos y journal terminales
PF-19C. Conserva conteos y evidencia sanitizada de la omisión; no reatesta ni
recrea un cierre administrativo en el destino.

## Concurrencia, fallos y rollback

- El plan no bloquea ni escribe; `apply` siempre revalida bajo locks.
- Dos aplicaciones simultáneas producen un ganador y un replay/conflicto
  determinista.
- Un cambio de estado, ownership, snapshot, número o relación después del plan
  aborta antes de consultar o escribir.
- Un fallo antes del commit revierte intento, guarda, grupo, filas, lote,
  operación y journal.
- Un commit ambiguo se resuelve mediante lectura del journal y del grafo; nunca
  repite una consulta o mutación ciegamente.
- Un fallo al publicar la respuesta idempotente no habilita reemisión: intentos
  y guardas terminales permanecen bloqueantes para el resolver.

## Matriz automatizada mínima

### Adaptador y clasificación

- `Err`/`Evt` singleton y lista;
- tipos estrictos de código;
- cabecera exacta, ausente, discordante, `A`, `R` y `P`;
- detalles ausentes, `A`, `R`, `P`, con CAE, cardinalidad y rangos inválidos;
- `10005` único, duplicado, mezclado, `1005` y texto libre;
- timeout, Fault, transporte y deserialización.

### Servicio, lote y replay

- individual y batch terminales con cero comprobantes/CAE;
- todos los intentos y guarda del sublote cerrados;
- grupos posteriores no enviados y cero llamadas `FECAESolicitar`;
- fallback unitario, worker, reintento y stale;
- replay terminal con cero WSAA, FEComp y FECAE;
- fallo inyectado en cada frontera de persistencia;
- CAS perdedor, cardinalidad, payload y ownership alterados;
- aislamiento multiemisor, ambiente, punto y tipo;
- SQLite y PostgreSQL para constraints y concurrencia.

### Legacy

- plan determinista y sanitizado;
- candidato válido e inválidos por cada precondición;
- ambiente durable y ambiente legacy nulo con doble consulta; último menor,
  último mayor con comprobante e incertidumbre;
- backup/plan inválidos producen cero llamadas y cero escrituras;
- apply idempotente, concurrente, rollback total y commit ambiguo;
- firma textual permanece candidata, nunca prueba terminal por sí sola.

## QA y release

La QA no provocará `10005` ni solicitará un CAE real. Usará dobles controlados,
PostgreSQL descartable en CI y lecturas seguras para el procedimiento legacy.
La evidencia privada de backup, ambiente y consultas no se versiona.

PF-19C quedó integrado en `main` con diseño, migración, rollback,
tests y documentación. El `autoreview` final cerró limpio y la CI Nivel 2 del
SHA funcional aprobó PostgreSQL real y Runtime Smoke. La aceptación PF-16G y el
ensayo privado de backup/restauración/upgrade/rollback quedaron aprobados el
10/08/2026. Al cerrar este diseño, tag, publicación y despliegue de `v0.3.0`
requerían autorizaciones posteriores separadas.
