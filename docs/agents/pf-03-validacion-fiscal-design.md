# PF-03 — Validación fiscal estricta de entradas e importes

Última actualización: 2026-08-08

Este documento conserva el diseño y cierre histórico de PF-03A. La tolerancia
transitoria de ítems descrita aquí fue reemplazada por
[`PF-03B`](pf-03b-items-importes-design.md), autoridad vigente para ítems e importes.

## Objetivo y secuencia de cortes

PF-03 evita que FactuFlow interprete silenciosamente una entrada distinta de la
que eligió el usuario. Se divide en unidades verticales pequeñas porque el
contrato superior de una emisión, los ítems y los importes tienen consumidores y
riesgos distintos.

La primera unidad, PF-03A, endurece exclusivamente el nivel superior de
`EmitirComprobanteRequest`:

- toda clave superior desconocida se rechaza con `422` antes de entrar al
  endpoint fiscal;
- una errata no puede activar el valor predeterminado de otro campo conocido;
- las claves conocidas, sus valores predeterminados y las validaciones fiscales
  existentes conservan su comportamiento;
- el mismo modelo sigue siendo la autoridad al revalidar payloads persistidos de
  lotes, reintentos y reconciliación.

PF-03A no hace estrictos todavía los modelos anidados. La UI individual mantiene
en memoria propiedades derivadas como `subtotal` dentro de cada ítem y hoy las
incluye al serializar. Endurecer `ItemComprobanteCreate` sin separar primero un
DTO de escritura rompería el flujo válido existente. Esa corrección, junto con
los límites de descuentos e importes no finitos, corresponde a PF-03B.

Quedan fuera de PF-03A:

- cambios de modelo, base de datos o migraciones;
- cambios de rutas, schemas de respuesta o pantallas; el `422` para un objeto
  superior inválido es la conducta intencional del corte;
- nuevos valores predeterminados de moneda, cotización o fecha;
- validación integral de ítems, descuentos, moneda, cotización y totales;
- cambios de política en numeración, idempotencia, estados de reconciliación o
  llamadas ARCA; sí se adaptan los consumidores para fallar cerrados y preservar
  evidencia al revalidar el contrato;
- reconstrucción histórica opcional, que permanece en PF-05.

## Autoridad y fronteras

1. Pydantic y `EmitirComprobanteRequest` son la autoridad del cuerpo fiscal en
   `POST /api/comprobantes/emitir` y de los snapshots batch que se revalidan.
2. El emisor autenticado y activo continúa siendo la autoridad de aislamiento;
   el endpoint reemplaza `empresa_id` por `empresa_activa_id` después de validar
   el cuerpo. PF-03A no amplía permisos ni confía en el emisor enviado.
3. Los payloads batch canónicos se construyen como modelos validados y se
   persisten mediante `model_dump(mode="json")`.
4. El servicio de facturación solo recibe un modelo ya validado. ARCA nunca es
   una capa de normalización de claves desconocidas.
5. La fecha fiscal continúa siendo explícita. Se aceptan los formatos ya
   documentados, se rechazan fechas calendario inválidas y no se agrega ningún
   valor basado en la fecha actual.

## Invariantes verificables de PF-03A

1. Una clave superior desconocida produce `422` con error
   `extra_forbidden`.
2. El rechazo ocurre antes de crear una operación idempotente, reservar número,
   persistir un intento, calcular una emisión o invocar FECAE.
3. Erratas de campos con valor predeterminado —por ejemplo `monedaa`,
   `cotizaccion` o `guardar_clientee`— no se ignoran ni terminan usando `PES`,
   `1` o `true` de forma silenciosa.
4. Una errata de una confirmación fiscal no puede degradarse a `false` y seguir
   otra rama del endpoint: el cuerpo completo se rechaza como inválido.
5. Un request formado solo por claves conocidas conserva el hash idempotente y
   el comportamiento previo.
6. El alcance de `extra="forbid"` no se propaga implícitamente a modelos
   anidados. Los ítems actuales de la UI siguen siendo compatibles hasta
   PF-03B.
7. Un payload batch canónico continúa validando en procesamiento unitario,
   procesamiento batch, reintento manual, reanudación stale y reconciliación.
8. Un payload persistido no canónico con una clave superior desconocida falla
   cerrado antes de cualquier nueva solicitud ARCA. No se elimina la clave ni
   se reconstruye el significado supuesto.
9. Un grupo inválido no habilita, libera ni reutiliza intentos
   `en_proceso` o `requiere_reconciliacion`.
10. Un grupo mixto sometido al preflight stale conserva la atomicidad actual:
    si un payload no puede validarse, ningún grupo intacto del conjunto se
    reencola.
11. El aislamiento por ambiente, emisor, punto de venta y tipo de comprobante
    no cambia.
12. PF-03A no solicita CAE real y sus pruebas usan dobles o validación local.

## Estados y decisiones

PF-03A no agrega estados persistidos. La decisión ocurre en la frontera del
contrato:

| Entrada | Resultado | Mutación fiscal | ARCA |
| --- | --- | --- | --- |
| Request HTTP con claves superiores conocidas | continúa el flujo vigente | según el flujo vigente | según el flujo vigente |
| Request HTTP con clave superior desconocida | `422` | ninguna | ninguna |
| Payload batch canónico | continúa la ruta vigente | según el estado del grupo | según el flujo vigente |
| Payload batch con clave superior desconocida durante procesamiento | grupo inválido/fallido según la defensa vigente | ninguna emisión nueva | ninguna |
| Payload inválido durante reintento manual | reintento rechazado o grupo fallido según la defensa vigente | no crea una nueva emisión | ninguna |
| Payload inválido durante preflight stale | lote bloqueado con `payload_fiscal_invalido` | ningún grupo se reencola | solo las lecturas previas permitidas; cero FECAE |
| Intento stale que ARCA confirma autorizado, con payload no canónico | `requiere_reconciliacion`, conserva CAE y vencimiento | no reconstruye comprobante con datos inválidos | solo `FECompConsultar`; cero FECAE |
| Payload inválido durante reconciliación | reconciliación rechazada o no vinculada | conserva la evidencia existente | ninguna escritura ARCA |

Los estados fiscales preexistentes conservan sus reglas. En particular,
`en_proceso` y `requiere_reconciliacion` nunca se convierten en ausencia de
autorización por un error de validación.

## Orden de operaciones

### Emisión individual

1. FastAPI resuelve las dependencias de transporte/autenticación y valida el
   body. PF-03A no depende del orden relativo entre esas tareas.
2. Si Pydantic encuentra una clave superior extra, FastAPI devuelve `422` y no
   ejecuta el cuerpo del endpoint fiscal.
3. El endpoint exige la confirmación explícita de fecha fiscal.
4. Reemplaza el `empresa_id` recibido por el emisor activo.
5. Calcula el hash y resuelve la operación idempotente con el modelo ya
   normalizado.
6. Ejecuta las validaciones, preflights, reserva, FECAE y persistencia vigentes.

La unidad no mueve la frontera irreversible: una entrada inválida se detiene
antes de que exista una operación fiscal propia.

### Lotes, worker, reintentos y reconciliación

1. El importador construye un `EmitirComprobanteRequest` y guarda solo su
   `model_dump(mode="json")`.
2. Cada consumidor revalida ese snapshot antes de calcular totales, reservar o
   emitir.
3. Si la revalidación falla, se conserva el manejo defensivo de esa ruta y no se
   invoca FECAE.
4. Reanudación stale valida todos los grupos intactos antes de reencolar alguno.
5. Reconciliación conserva sus verificaciones de intento, comprobante, hash y
   huella; un payload inválido no puede inventar ni vincular evidencia.

## Concurrencia

PF-03A no agrega locks ni transacciones porque la decisión es pura y previa al
trabajo fiscal. La validación determinista del mismo payload produce el mismo
resultado en dos workers o en una carrera worker/reintento manual.

- Dos requests inválidos concurrentes reciben `422`; ninguno crea una operación
  idempotente.
- Un request válido conserva los CAS, locks de numeración y preflights ya
  existentes.
- Un payload stale inválido bloquea el conjunto antes de reencolar; un segundo
  worker no obtiene un grupo nuevo por esta validación.
- Un avance externo entre consultas sigue bajo PF-02; PF-03A no omite el segundo
  preflight anterior a FECAE.

## Fallos intermedios, rollback y reconciliación

- No hay rollback nuevo para el request HTTP inválido porque la validación
  sucede antes de la mutación fiscal.
- Los errores de base, red o ARCA posteriores a un request válido conservan la
  clasificación pre-ARCA/post-ARCA vigente.
- Si un payload persistido inválido aparece antes de emitir, la ruta falla
  cerrado y usa un mensaje público estable y un diagnóstico técnico sin valores
  del payload. No se intenta reparar eliminando campos desconocidos.
- Si ya existe evidencia de una posible autorización, el error del payload no
  la degrada ni habilita una reemisión. Si `FECompConsultar` confirma CAE, el
  intento conserva CAE y vencimiento como `requiere_reconciliacion`, pero no
  reconstruye un comprobante desde el payload inválido. La reconciliación manual
  sigue siendo la salida segura.
- Los mensajes públicos y los logs de validación continúan sanitizados; una
  validación no debe exponer rutas, secretos ni datos fiscales privados.

## Datos legacy y migraciones

No se requiere migración. Los snapshots batch creados por FactuFlow provienen de
un modelo Pydantic y, por diseño, no conservan claves superiores desconocidas.

La política para datos legacy o manipulados es deliberadamente conservadora:

- si cumplen el contrato conocido, continúan;
- si contienen una clave superior desconocida, se consideran inválidos;
- no se elimina el campo automáticamente porque podría representar una
  instrucción fiscal que FactuFlow no comprende;
- no se solicita CAE para “probar” el significado;
- si hay evidencia fiscal previa, se preserva y se deriva a reconciliación.

Una eventual herramienta de saneamiento histórico necesitaría diseño y
autorización propios. No forma parte de PF-03A ni de una migración automática.

## Consumidores revisados

| Consumidor | Impacto de PF-03A |
| --- | --- |
| API de emisión individual | rechaza claves superiores extra con `422` antes del cuerpo del endpoint |
| Servicio de facturación unitario | la emisión recibe modelos validados; la reconstrucción stale trata un payload inválido como evidencia local insuficiente y conserva la autorización para reconciliar |
| Importación y procesamiento batch | persiste dumps canónicos y revalida antes de emitir |
| Worker | un snapshot no canónico falla antes de FECAE |
| Reintento manual | revalida el grupo reclamado; no reemite un payload inválido |
| Reanudación stale | un payload inválido bloquea el preflight del conjunto |
| Idempotencia | calcula hash solo después de validar; los hashes válidos no cambian |
| Reconciliación local/externa | no vincula evidencia usando un payload inválido |
| Frontend individual | ya envía solo claves superiores conocidas; los campos derivados anidados siguen tolerados en este corte |
| API/OpenAPI | documenta un objeto superior cerrado; no cambian ruta ni schema de respuesta |

## Matriz automatizada de PF-03A

| Caso | Nivel | Resultado esperado |
| --- | --- | --- |
| `monedaa` con ausencia de `moneda` | API | `422`, `extra_forbidden`, cero llamadas al servicio |
| `cotizaccion` con ausencia de `cotizacion` | API | `422`, sin usar cotización `1`, cero llamadas al servicio |
| `guardar_clientee` con ausencia de `guardar_cliente` | API | `422`, sin usar `true`, cero llamadas al servicio |
| errata de `confirmacion_fecha_fiscal` | API | `422`, no `400`, cero llamadas al servicio |
| clave arbitraria adicional junto a request válido | schema/API | rechazo determinista |
| request válido existente | regresión API | conserva respuesta y camino idempotente |
| ítem UI con `subtotal` derivado | schema enfocado | conserva compatibilidad anidada de PF-03A |
| dump canónico batch | servicio/lotes | continúa validando y procesando con dobles |
| payload stale con extra superior | servicio/lotes | `payload_fiscal_invalido`, ningún grupo reencolado, cero FECAE |
| payload de reintento con extra superior | servicio/lotes | fallo cerrado antes de emitir |
| procesamiento normal con extra superior | servicio/lotes | grupo fallido, mensaje sanitizado y cero emisión |
| intento stale autorizado con extra superior | servicio | conserva CAE/vencimiento, pasa a reconciliación y no crea comprobante |
| replay válido con misma clave | regresión idempotente | no emite dos veces |
| misma clave con payload conocido distinto | regresión idempotente | conserva conflicto vigente |

Los tests enfocados deben ejecutarse antes de las suites amplias. Al cierre se
ejecutan backend completo, Ruff, Black, checks documentales y las puertas
proporcionales al diff. No se realizan llamadas ARCA de escritura.

## Evidencia automatizada de PF-03A

- `9` casos enfocados: cuatro erratas superiores, compatibilidad transitoria del
  ítem UI, procesamiento y reintento manual no canónicos, stale mixto no
  canónico e intento stale autorizado con evidencia preservada.
- `29` pruebas de API de comprobantes aprobadas.
- `50` pruebas del servicio de facturación aprobadas.
- `118` pruebas de lotes aprobadas, incluidos worker, reintentos, stale,
  procesamiento y reconciliación.
- backend completo: `566` aprobadas y `4` omitidas por infraestructura
  configurada.
- puerta completa: `131` frontend, `16` scripts, `5` seeds y `33` E2E; Ruff,
  Black, type-check, lint, build, `docs:check` y auditorías productivas verdes.
- `autoreview --mode local` con Codex `gpt-5.6-sol`, thinking `medium` y el
  binario versionado `0.147.0-alpha.1.2`: TruffleHog limpio, dos pasadas, cero
  findings accionables y probabilidad `0,99` de patch correcto; no hubo fallback.
- cero emisiones reales, solicitudes de CAE, migraciones o llamadas ARCA de
  escritura.

## Criterio de cierre y siguiente unidad

PF-03A queda cerrado cuando:

1. el modelo superior prohíbe extras;
2. los errores representativos devuelven `422` antes del servicio;
3. la compatibilidad con el ítem que hoy serializa la UI queda comprobada;
4. las regresiones de lotes, stale, reintento, reconciliación e idempotencia
   permanecen verdes;
5. la documentación canónica distingue el código aceptado, la release publicada
   y la versión productiva.

La siguiente unidad propia de PF-03 es PF-03B: separar el DTO de ítem enviado
por la UI, hacer estricto `ItemComprobanteCreate` y rechazar descuentos o
valores no finitos antes de que puedan producir totales negativos o `NaN`. Ese
corte debe definir primero sus invariantes cross-layer y sus pruebas
UI/API/servicio. La secuencia global vigente prioriza PF-19A/PF-19B/PF-19C por
evidencia productiva antes de retomar PF-03B; esta reordenación no cambia el
alcance ni las invariantes de PF-03.
