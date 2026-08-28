# PF-19B — Elegibilidad RECE durable y fail-closed

Fecha de diseño: 08/08/2026. Actualizado para el parche `0.3.1`: 28/08/2026.

Estado objetivo al integrar: PF-19B.1, PF-19B.2 y PF-19B.3 forman una única
unidad completa aceptada en `main`. La última release publicada y la versión
desplegada continúan siendo `v0.2.2`, que no incluyen PF-19B. La publicación y
el despliegue requieren un checkpoint posterior explícito.

## Objetivo y frontera

PF-19B reemplaza la inferencia mutable `es_webservice == RECE` por una autoridad
durable, versionada y específica por ambiente. Ningún camino capaz de solicitar
CAE podrá usar un punto si su revisión vigente no es `verificado_rece` para el
ambiente ARCA actual.

El corte incluye:

- ledger de elegibilidad por punto y ambiente;
- revisión fiscal monotónica del punto de venta;
- migración fail-closed de todo dato legacy;
- clasificación de una constancia ARCA fresca con reglas exactas;
- snapshots de elegibilidad en operación individual, intento y grupo de lote;
- precheck antes de crear idempotencia y guarda durable antes de FECAE;
- filtros coherentes en API, perfiles, Excel, selectores, lotes, worker,
  reintentos y recuperación stale;
- invalidación de confirmaciones y continuaciones idempotentes cuando cambia el
  contexto fiscal del punto;
- UI que diferencia `Verificado RECE`, `No RECE` y `No verificado`.

No incluye:

- convertir el error global `10005` en rechazo terminal;
- cambiar la taxonomía de errores globales de WSFE;
- resolver o editar intentos, operaciones, grupos o comprobantes legacy;
- inferir elegibilidad histórica desde `sistema`, `fuente`, logs o texto de un
  error;
- retirar automáticamente la contención privada PF-19A;
- emitir, reintentar o consultar ARCA real durante tests o QA automatizada.

Los errores globales estructurados y el saneamiento legacy pertenecen a
PF-19C.

## Autoridad fiscal y ambientes

Fuentes oficiales consultadas el 08/08/2026: el
[índice de factura electrónica de ARCA](https://arca.gob.ar/ws/documentacion/ws-factura-electronica.asp),
la
[documentación de certificados](https://www.arca.gob.ar/ws/documentacion/certificados.asp)
y los
[conceptos de WSASS](https://www.arca.gob.ar/ws/WSASS/html/conceptos.html).
ARCA documenta endpoints y certificados separados para homologación y
producción. Esas fuentes no establecen que la constancia administrativa de
puntos acredite RECE en ambos ambientes. Por eso PF-19B no extrapola evidencia
productiva hacia homologación y nunca usa `FEParamGetPtosVenta` como promoción.

La frase ya observada en la constancia es una señal textual, no autoridad por sí
sola. El PDF llega desde el cliente y no tiene autenticidad criptográfica
verificable por FactuFlow. Por eso solo se vuelve evidencia durable mediante una
atestación de un administrador, al procesar un documento válido del
emisor activo con CUIT y punto exactos, clasificador versionado, hash, fecha y
actor, bajo las restricciones siguientes.

## Decisiones de autoridad

1. `FEParamGetPtosVenta` prueba presencia y bloqueo técnico, no pertenencia a
   RECE. La sincronización WSFE nunca promueve un punto a `verificado_rece`.
2. `es_webservice`, `activo`, `bloqueado`, `fecha_baja`, `sistema`, `fuente` y
   `usable_factuflow` dejan de ser autoridad RECE por separado.
3. Una constancia puede crear evidencia durable únicamente para `produccion`,
   cuando el servidor tiene `ARCA_ENV=produccion` y el actor es administrador.
   La fecha del documento debe parsearse sin ambigüedad y no ser futura; no hay
   límite máximo de antigüedad. El documento no se reutiliza como acreditación
   de homologación. La revisión positiva no vence por tiempo. La comprobación
   técnica es otra dimensión: se considera desactualizada a los 90 días y se
   renueva opcionalmente desde la UI o automáticamente antes de emitir.
4. La señal administrativa normalizada debe coincidir exactamente con una
   allowlist versionada. `rece_constancia_v1` solo admitía
   `RECE para aplicativo y web services`. El parche `0.3.1` introduce
   `rece_constancia_v2` y agrega las modalidades oficiales exactas para
   Responsable Inscripto, Exento en IVA y Monotributo. Solo se normalizan
   espacios, mayúsculas, variantes de guion y la escritura `Webservices`;
   coincidencias parciales, sinónimos o cambios futuros del formulario fallan
   cerrado hasta actualizar clasificador y tests.
5. Una descripción genérica que solo dice `Web Service` o `Web Services` queda
   `no_verificado`; no se completa por semejanza ni por presencia en WSFE.
6. Un sistema distinto, vacío, ilegible o contradictorio queda
   `no_verificado`. `no_rece` queda reservado para una señal negativa oficial,
   exacta y versionada que PF-19B no infiere de este formulario.
7. El alta o la edición manual no pueden promover elegibilidad en este corte.
   Crear, importar o cambiar campos fiscales del punto requiere administrador;
   un usuario operativo solo puede cambiar datos meramente descriptivos. Los
   cambios de número, sistema, marca Web Services o procedencia invalidan a
   `no_verificado` para ambos ambientes.
8. La edición de estado técnico puede conservar la clasificación RECE, pero
   los cambios fiscalmente relevantes incrementan la revisión fiscal para
   invalidar confirmaciones previas. Una edición solo descriptiva no lo hace.
9. La contención PF-19A continúa como una denegación adicional. Una revisión
   `verificado_rece` no puede levantar una regla privada todavía vigente.
10. El ledger no guarda PDFs, payloads, mensajes ARCA ni texto libre del usuario.
    Conserva snapshots privados del CUIT y número validados, tipo, SHA-256 de la
    evidencia, versión del clasificador y metadatos mínimos; ninguno se expone
    en respuestas o logs ordinarios.

No queda una decisión funcional bloqueante para el camino productivo: se adopta
la promoción exclusiva por atestación administrativa, constancia válida,
señal exacta y servidor en producción. Homologación permanece deliberadamente
`no_verificado` hasta que
exista una fuente probatoria específica; no se la habilita mediante una
selección del usuario. Una promoción manual futura requerirá otro diseño fiscal,
autorización explícita y trazabilidad propia.

## Modelo durable

### Punto de venta

`puntos_venta` agrega `revision_fiscal`, entero positivo no nulo con valor
inicial `1`. La fila usa control optimista de versión: cada modificación fiscal
relevante incrementa la revisión y una actualización concurrente obsoleta falla
en vez de sobrescribir silenciosamente.

El parche `0.3.1` agrega además `ultima_comprobacion_arca_en`, nullable y UTC.
Una marca nula o con al menos 90 días exige preflight técnico antes de emitir,
pero no degrada la acreditación inicial.

La revisión cambia ante hechos fiscalmente relevantes:

- número, sistema, procedencia o marca Web Services;
- alta, baja, activación, bloqueo o fecha de baja;
- nueva observación de elegibilidad que cambie estado, fuente o evidencia;
- cualquier edición que altere la selección o el significado fiscal del punto;
- toda constancia válida procesada, incluso cuando su hash y resultado coincidan
  con la revisión anterior, para que una observación posterior invalide
  confirmaciones previas.

Nombre amigable, domicilio y fantasía meramente descriptivos conservan el estado
RECE y no incrementan `revision_fiscal`. Una sincronización idéntica tampoco
crea una revisión nueva.

`punto_revision_fiscal` en la evidencia registra cuándo fue observada; cada
operación snapshottea además la revisión actual del punto. Bloqueo, baja,
desactivación o ausencia obtenidos de ARCA crean una revisión sucesora que
traslada la acreditación positiva y, al cambiar la revisión actual, invalidan
toda confirmación de emisión previa. Número, CUIT, emisor, una señal RECE
contradictoria o una edición local fiscal nunca dependen solo de ese mismatch:
escriben atómicamente una nueva cabeza `no_verificado`.

### Ledger de elegibilidad

PF-19B separa una cabeza transaccional del historial inmutable:

- `puntos_venta_elegibilidad_rece_actual` contiene una fila única por
  `empresa + punto + ambiente` y apunta a la revisión vigente;
- `puntos_venta_elegibilidad_rece_revisiones` es append-only. La aplicación no
  actualiza ni borra revisiones.

Cada mutación bloquea el punto y la cabeza o cabezas afectadas, inserta la
siguiente revisión y actualiza el puntero dentro de la misma transacción. Los
consumidores unen contra la cabeza; no calculan `MAX(revision)` en cada guarda
fiscal.

Campos de la revisión:

| Campo | Contrato |
|---|---|
| `id` | Identidad inmutable de la evidencia |
| `empresa_id` | Emisor propietario, ligado de forma consistente al punto |
| `punto_venta_id` | FK `RESTRICT` al punto |
| `ambiente` | `homologacion` o `produccion` |
| `revision` | Entero positivo monotónico por punto y ambiente |
| `estado` | `verificado_rece`, `no_rece` o `no_verificado` |
| `fuente` | Allowlist: migración, alta manual, WSFE, constancia o edición |
| `evidencia_tipo` | Categoría allowlist; nunca texto ARCA libre |
| `evidencia_sha256` | Hash de la evidencia fresca o nulo para altas/migración |
| `clasificador_version` | Versión exacta de la allowlist aplicada |
| `empresa_cuit_snapshot` | CUIT exacto usado en la validación; privado |
| `punto_venta_numero_snapshot` | Número exacto validado en la evidencia |
| `punto_revision_fiscal` | Revisión del punto al registrar la evidencia |
| `documento_emitido_en` | Fecha argentina parseada del documento, si aplica |
| `vigente_hasta` | Campo histórico compatible; no participa en elegibilidad y las revisiones nuevas pueden guardarlo nulo |
| `observado_en` | Fecha/hora UTC del hecho observado |
| `verificado_en` | Fecha/hora UTC solo cuando existe acreditación positiva |
| `creado_por_usuario_id` | Usuario autenticado o nulo para migración |
| `actor_usuario_id_snapshot` | ID durable del actor al atestiguar, sin FK mutable |
| `created_at` | Fecha/hora UTC de persistencia |

La cabeza conserva `empresa_id`, `punto_venta_id`, `ambiente`,
`revision_actual_id` y timestamps de control. La revisión referenciada debe
pertenecer a esa misma tupla.

Constraints e índices:

- cabeza única `(punto_venta_id, ambiente)`;
- revisión única `(punto_venta_id, ambiente, revision)`;
- FKs o constraints compuestos que impidan cruzar emisor, punto, ambiente y
  revisión actual;
- check de ambiente, estado, fuente, evidencia y revisión positiva;
- índice `(punto_venta_id, ambiente, revision DESC)`;
- FK del usuario con `SET NULL`, snapshot durable de actor y FK del punto con
  `RESTRICT`;
- ninguna revisión `verificado_rece` puede carecer de fuente, hash, versión de
  clasificador, snapshots fiscales, ambiente, fecha documental, actor o revisión
  fiscal del punto; `vigente_hasta` puede ser nulo;
- `verificado_rece` implica `produccion`, fuente
  `constancia_arca_atestada` y evidencia
  `rece_aplicativo_web_services_v1`;
- migración, alta, WSFE y edición no admiten estado positivo;
- `verificado_en` solo existe en evidencia positiva. `vigente_hasta` queda como
  historial compatible y no se compara para decidir elegibilidad.

Para que las FKs compuestas sean portables, `puntos_venta` declara además el
unique redundante `(id, empresa_id)`; la revisión declara
`(id, empresa_id, punto_venta_id, ambiente)` como unique. La cabeza, el intento
y las asociaciones referencian la misma combinación, no solo un ID suelto. El
grupo agrega `empresa_id`, backfilleado desde su lote, y una FK compuesta que
impide mezclar lote/emisor. Los estados y ambientes usan `String` con
`CheckConstraint`, no enums nativos.

`operaciones_idempotentes` declara también `(id, empresa_id)` como unique. Toda
guarda y asociación referencia por FK compuesta la operación de ese mismo
emisor y la revisión de ese mismo emisor/punto/ambiente. Todo camino nuevo capaz
de solicitar CAE debe tener `operacion_id`; la opcionalidad física solo conserva
historia legacy. Intento y guarda quedan ligados por FK compuesta y los tests
rechazan inserciones cruzadas aun si el servicio se saltea.

### Snapshots en caminos fiscales

`intentos_emision_fiscal` agrega ambiente,
`punto_venta_elegibilidad_revision_id` y `punto_venta_revision_fiscal`.
`lotes_comprobantes_grupos` agrega además `empresa_id` y `punto_venta_id`
explícitos, porque el número guardado en el payload no alcanza para identificar
una fila durable ni garantizar aislamiento en base.

Las operaciones usan un snapshot normalizado:

- `operaciones_idempotentes` agrega `rece_snapshot_hash`;
- `operaciones_idempotentes_elegibilidad_rece` relaciona cada operación con
  uno o más puntos, ambientes, revisiones inmutables y revisiones fiscales;
- el digest se calcula sobre el conjunto canónico y ordenado de esas filas.

`rece_snapshot_hash` usa JSON canónico versionado, enteros y enums normalizados,
orden `empresa + punto + ambiente` y cero duplicados. La operación padre, sus
asociaciones y el digest se crean en un único commit. La recuperación de una
creación ambigua compara payload, digest y asociaciones completas; una operación
sin asociaciones no puede continuar hacia ARCA.

La emisión individual crea una asociación; una operación de lote puede crear
varias. No se modela un único snapshot engañoso en la fila padre.

Las columnas son nulas para historia anterior a PF-19B. En operaciones nuevas
son obligatorias por contrato de aplicación cuando el camino puede solicitar
CAE. Un registro legacy sin snapshot nunca se habilita para reemisión; una
respuesta terminal ya persistida sí puede reproducirse porque no llama a ARCA.

El payload idempotente y el token de confirmación enlazan también
`rece_snapshot_hash`. El backend deriva todas las asociaciones; nunca confía en
IDs de evidencia enviados libremente por el cliente.

### Guarda durable durante FECAE

Un lock transaccional no alcanza porque el intento debe quedar commiteado antes
de llamar a ARCA. La tabla `puntos_venta_guardas_emision_rece` mantiene una
guarda durable con operación propietaria obligatoria, token interno, revisión
RECE, revisión fiscal, fase y timestamps. Un índice parcial permite una sola
guarda activa por `empresa + punto + ambiente`; cada intento nuevo referencia la
guarda que lo protegió.

Las fases son `pre_arca`, `arca_iniciada`, `requiere_reconciliacion`,
`cerrada_pre_arca` y `cerrada_terminal`. Las tres primeras son activas. Las
filas cerradas permanecen como auditoría y no bloquean una guarda posterior.

La guarda se crea atómicamente con el primer intento del sublote después de
bloquear brevemente punto y cabeza, y revalidar acreditación, estado técnico,
revisión fiscal y PF-19A. Mientras existe:

- otra emisión nueva para esa tupla falla antes de FECAE. Si pierde el CAS
  después de una lectura segura WSAA/WSFE, descarta esa respuesta y no escribe
  en ARCA;
- una edición, importación o sincronización que alteraría contexto fiscal
  responde conflicto y no modifica la cabeza;
- todos los intentos del mismo sublote pueden compartirla;
- solo se cierra en la misma transacción que deja todos sus intentos en un
  resultado terminal conocido;
- inmediatamente antes de FECAE pasa a `arca_iniciada` mediante CAS y commit;
- ese CAS comprueba nuevamente propiedad, snapshots y revisión fiscal;
- un timeout, caída o resultado incierto pasa o permanece en
  `requiere_reconciliacion` hasta resolución segura. No existe vencimiento que
  la cierre automáticamente.

La carrera queda serializada por la cabeza: si la mutación gana, la emisión ve
otra revisión y no crea la guarda; si la emisión gana, la mutación ve la guarda
durable y se detiene. Esto sobrevive al commit previo a FECAE y no consume una
segunda conexión del pool.

Una mutación compartida bloquea el punto y ambas cabezas en orden
`homologacion`, `produccion`. Una emisión toma numeración, punto y luego la cabeza
de su ambiente. Las operaciones multipunto ordenan por ID de punto. Las
mutaciones no toman el lock de numeración, por lo que no forman un ciclo.

La recuperación stale puede cerrar por CAS una guarda `pre_arca` solo cuando no
hay marca de inicio ni otra evidencia de llamada. `arca_iniciada` o una fase
ambigua exige reconciliación; una guarda huérfana o inconsistente falla cerrado
y requiere revisión manual. Worker y fallback solo reclaman una guarda propia
por CAS, nunca reapropian una ajena. Una revocación urgente usa mientras tanto
la denegación PF-19A, que conserva precedencia; no se reescribe el ledger debajo
de una solicitud incierta.

## Migración fail-closed

La revisión Alembic debe:

1. abortar si encuentra puntos sin emisor o números inválidos;
2. agregar `revision_fiscal=1` a todos los puntos existentes;
3. crear cabeza, ledger y sus constraints;
4. insertar para cada punto dos revisiones iniciales, una por ambiente, ambas
   `no_verificado`, fuente `migracion_legacy`, y apuntar cada cabeza a su fila;
5. crear las guardas durables y agregar asociaciones/snapshots nulos a
   operaciones, intentos y grupos históricos, incluidos `empresa_id`
   backfilleado desde el lote y `punto_venta_id` nulo en grupos legacy;
6. verificar conteos: exactamente dos cabezas y dos revisiones iniciales por
   punto, sin duplicados ni estados fuera de allowlist;
7. conservar operaciones, intentos, lotes, grupos y comprobantes sin
   reclasificarlos.

La migración no usa `sistema`, `fuente`, `es_webservice`, la lista PF-19A ni
mensajes legacy para promover puntos. SQLite y PostgreSQL deben producir el
mismo estado lógico. El downgrade aborta si existe cualquier revisión cuya
fuente no sea `migracion_legacy`; nunca elimina silenciosamente puntos nuevos ni
historial probatorio. No se usa como mecanismo operativo después de aceptar
evidencia nueva. También aborta antes de cualquier DDL si hay snapshots o
asociaciones PF-19B no nulos, `revision_fiscal != 1`, guardas, cabezas que no
apunten a su revisión inicial o conteos inconsistentes.

## Productores y precedencia

| Productor | Estado nuevo | Ambiente | Efecto sobre revisión |
|---|---|---|---|
| Migración legacy | `no_verificado` | ambos | inicial `1` |
| Alta manual | `no_verificado` | ambos | crea contexto inicial |
| Sincronización `FEParamGetPtosVenta` | nunca promueve; punto nuevo `no_verificado` | contexto actual y contraparte cerrada | incrementa solo si cambia estado técnico relevante |
| Atestación admin con constancia válida y modalidad exacta de la allowlist | `verificado_rece` | solo producción y servidor productivo | siempre crea revisión ledger y fiscal |
| Atestación admin con Web Services genérico | `no_verificado` | solo producción y servidor productivo | siempre crea revisión ledger y fiscal |
| Atestación admin con sistema no allowlist | `no_verificado` | solo producción y servidor productivo | siempre crea revisión ledger y fiscal |
| Edición de número/sistema/Web Services/fuente | `no_verificado` | ambos | nueva revisión ledger y fiscal |
| Baja, bloqueo, desactivación o ausencia informada por ARCA | conserva acreditación, pero no usabilidad | ambos | nueva revisión ledger y fiscal |
| Edición local fiscal, identidad contradictoria o recreación | `no_verificado` | ambos | nueva revisión ledger y fiscal |

La importación confirmada completa primero el procesamiento del PDF y las
consultas técnicas WSAA/`FEParamGetPtosVenta`, sin escrituras de puntos o
cabezas. Antes de cualquier `db.add` o `flush` de esos hijos, toma la frontera
`Usuario administrador -> Empresa` mediante `FOR UPDATE`, `populate_existing` y
`no_autoflush`: revalida que el actor continúe activo y sea administrador, y que
el CUIT persistido siga coincidiendo. Solo entonces puede crear o modificar
puntos y cabezas. El productor revalida idempotentemente esa misma frontera y
continúa `puntos por ID ascendente -> cabezas por ambiente -> guardas activas`
antes del único commit. `update_empresa` toma el lock de `Empresa`, fuerza la
relectura del estado persistido y solo entonces compara campos y consulta
dependencias. Así, si el cambio de CUIT o la degradación del actor ganan, la
atestación anterior responde conflicto sin crear hijos ni evidencia positiva;
si gana la atestación, publica evidencia bajo la autoridad todavía válida y la
mutación competidora continúa después. Ningún desenlace mezcla evidencia de una
identidad o autoridad obsoletas.

La constancia más nueva reemplaza como autoridad solo al crear una
revisión posterior; las revisiones previas permanecen auditables. Ningún merge
entre fuentes puede producir un estado más permisivo que la evidencia exacta.

El paso del tiempo no reescribe ni degrada el ledger. Una cabeza
`verificado_rece` conserva su autoridad; la UI sólo advierte cuando la última
comprobación técnica tiene 90 días. Si está pendiente o desactualizada, el
servidor consulta `FEParamGetPtosVenta` una vez por emisor antes de crear estado
fiscal. Una falla, respuesta vacía o inconsistente produce `503` y cero
operaciones, intentos, reservas o solicitudes CAE nuevas.

## Invariantes verificables

1. Solo `verificado_rece` para `ARCA_ENV`, con señal técnica activa confirmada,
   puede avanzar hacia CAE.
2. `no_rece`, `no_verificado`, revisión ausente, ambiente distinto o evidencia
   inexistente fallan cerrado.
3. La presencia en `FEParamGetPtosVenta` no cambia el estado RECE.
4. Una constancia genérica nunca produce `verificado_rece`.
5. La migración nunca promueve datos legacy.
6. El ledger es inmutable y monotónico por punto y ambiente; cada cabeza apunta
   atómicamente a una revisión de su propia tupla.
7. Dos escrituras concurrentes no pueden crear la misma revisión ni perder una
   invalidación; una debe serializarse o responder conflicto.
8. `revision_fiscal` se modifica por CAS. Un escritor con revisión obsoleta
   obtiene `409`; ningún update bulk saltea esa condición.
9. Cada operación individual nueva captura evidencia y revisión antes de crear
   la fila idempotente y su asociación normalizada.
10. Cada intento y cada grupo nuevo capturan el mismo contexto autorizado.
11. La acreditación, el estado técnico y sus revisiones se revalidan bajo el
    lock fiscal y otra vez inmediatamente antes de `FECAESolicitar`.
12. Guarda e intentos nacen atómicamente; FECAE solo ocurre después de persistir
    `arca_iniciada` y una guarda incierta nunca se cierra por TTL.
13. Cambiar y restaurar un punto no revive una confirmación anterior: la
    revisión fiscal sigue aumentando.
14. Un replay terminal con mismo payload devuelve su respuesta durable sin
    consultar ni solicitar a ARCA, aunque el punto haya cambiado.
15. Un replay que podría continuar, confirmar duplicado, reintentar o reanudar
    exige que evidencia y revisión coincidan con el contexto capturado.
16. Una clave existente con payload distinto conserva el conflicto de
    idempotencia actual.
17. Una operación legacy sin snapshot puede reproducir una respuesta terminal,
    pero no continuar hacia ARCA.
18. El hash y la confirmación de lote incluyen el contexto RECE de todos los
    grupos; un cambio obliga a revalidar el lote y confirmar nuevamente.
19. Worker, fallback unitario, reintento y stale no poseen una excepción a la
    guarda común.
20. Reconciliación puede consultar evidencia externa segura, pero PF-19B no la
    convierte en camino de emisión ni sanea historia.
21. Ningún filtro de UI, perfil o Excel vuelve a usar `es_webservice` como
    sustituto de RECE.
22. Solo una atestación productiva de administrador puede promover; el PDF y su
    hash no se presentan como autenticidad criptográfica.
23. PF-19A puede bloquear un punto verificado; nunca puede volver elegible uno
    no verificado.
24. No cambian fecha fiscal, numeración, receptor, importe, CAE ni comprobantes
    asociados.
25. No se hacen llamadas ARCA reales en tests ni se versiona evidencia privada.
26. Una revisión positiva queda ligada a `empresa_cuit_snapshot`. El contexto
    emitible compara ese snapshot con el CUIT actual y falla cerrado ante una
    divergencia, aunque la cabeza siga apuntando a `verificado_rece`.

## Orden de operaciones individual

1. Autenticar usuario, resolver el emisor y validar request, confirmación de
   fecha y forma de la clave idempotente.
2. Calcular el hash del payload y buscar la operación dentro de ese emisor, sin
   crearla.
3. Si la clave existe con otro payload, responder conflicto.
4. Si existe una respuesta terminal, reproducirla sin abrir una continuación.
5. Para una operación nueva o continuable, bloquear brevemente la cabeza y
   cargar el punto dentro del emisor y la última revisión del ambiente.
6. Exigir estado `verificado_rece`, punto técnicamente activo y ausencia de
   contención PF-19A.
7. Si es nueva, crear operación, asociaciones y digest con los snapshots exactos
   en la misma transacción corta que protege la cabeza. Un punto no elegible no
   crea operación, intento, reserva ni comprobante.
8. Si es continuable, comparar los snapshots; cualquier diferencia invalida la
   confirmación y exige una nueva clave.
9. Tomar el lock de numeración y luego la cabeza RECE, recargar el contexto y
   repetir la comparación.
10. Crear guarda e intento con los mismos snapshots en una única transacción y
    reservar según PF-01/PF-02.
11. Ejecutar el segundo preflight y comprobar propiedad de la guarda.
12. Pasar la guarda por CAS a `arca_iniciada`, commitear e invocar
    `FECAESolicitar` una sola vez.
13. Persistir resultado, CAE, comprobante, intento, guarda y respuesta
    idempotente con las reglas existentes. Un resultado incierto conserva la
    guarda activa.

Un resultado `requiere_reconciliacion` nunca se vuelve continuable por recuperar
elegibilidad. La resolución corresponde a reconciliación o PF-19C.

En emisión, el orden global es lock de numeración, punto y luego cabeza RECE.
Las mutaciones ordinarias de elegibilidad toman punto y las cabezas afectadas,
pero nunca numeración. La atestación agrega antes los locks de `Usuario` y
`Empresa`; la importación confirmada los adquiere antes de crear hijos y el
productor los revalida idempotentemente con `no_autoflush` antes de Punto y
cabezas. `update_empresa` comparte el lock de `Empresa` antes de mirar
dependencias. En operaciones multipunto, los puntos se bloquean por ID
ascendente y sus cabezas por ambiente. SQLite usa además un lock en proceso para
desarrollo y tests; no se considera una garantía multiworker productiva.

## Orden de lotes, worker y reintentos

1. La validación del Excel resuelve cada punto mediante la revisión vigente del
   ambiente; un grupo no elegible queda con error y sin payload emitible.
2. Cada grupo válido guarda emisor, `punto_venta_id`, ambiente, evidencia y
   revisión fiscal junto con su payload.
3. El hash material de grupos y el token de confirmación incorporan un digest
   estable del contexto RECE, además de fechas y números visibles.
4. La API autentica y resuelve emisor/lote antes de buscar un replay. Una
   respuesta terminal se reproduce sin reevaluar RECE; toda continuación
   compara la membresía completa confirmada y todos los snapshots con el estado
   vigente antes de crear la operación de proceso o reintento.
5. Antes de WSAA, `FECompTotXRequest` u otra lectura ARCA del worker, el servicio
   vuelve a comparar todos los grupos que podrían avanzar.
6. Bajo la cabeza de cada sublote, se repite la comparación y se crean una
   guarda más todos sus intentos de forma atómica; antes de FECAE la guarda pasa
   a `arca_iniciada` por CAS.
7. El fallback unitario recibe el snapshot del grupo; no deriva uno nuevo para
   eludir una invalidación.
8. Un grupo legacy sin snapshot puede reconciliar una autorización ya probada,
   pero no reemitirse ni volver a cola.
9. Revalidar el archivo o lote crea nuevos grupos/snapshots; recién entonces el
   usuario obtiene un token de confirmación nuevo.

Si falta snapshot o cambia un solo grupo material, la acción completa aborta
antes de `FECAESolicitar`. El orquestador exterior puede haber autenticado WSAA
o ejecutado una lectura segura de capacidad antes de formar sublotes; nunca se
filtra silenciosamente ese grupo para emitir el resto.

## Consumidores obligatorios

| Área | Cambio PF-19B |
|---|---|
| Configuración | `ARCA_ENV` enum estricto; un valor inválido impide iniciar |
| Modelo y Alembic | ledger, revisión fiscal, snapshots y constraints |
| Constancia PDF | encabezados histórico/actual y repetidos por página; clasificador exacto, hash y versión; sin texto probatorio persistido |
| Importación | admin, atestación/fecha y escritura atómica de punto + revisión |
| Sincronización WSFE | conserva solo estado técnico; nunca promueve RECE |
| Alta/edición/baja | estado inicial cerrado e invalidación monotónica |
| Listado/API | expone estado, fuente, fecha y revisión vigentes |
| Próximo número | bloquea antes de WSAA si no hay contexto válido |
| Emisión individual | lookup terminal, pre-idempotencia, locks e intento |
| Perfiles | solo permite punto fijo verificado para el ambiente |
| Validación Excel | filtra, snapshottea y muestra error por fila/grupo |
| Procesamiento batch | precheck antes de operación y recheck antes de `FECAESolicitar` |
| Worker | misma autoridad y cero FECAE con contexto inválido; la capa exterior puede ejecutar lecturas seguras de capacidad |
| Fallback unitario | usa snapshots del grupo |
| Reintentos | contexto idéntico o nueva validación/confirmación |
| Stale | no reencola grupos legacy u obsoletos |
| Reconciliación | lectura segura; sin promoción ni reemisión |
| Frontend Puntos | badges, procedencia, fecha y guía de importación |
| Selectores individual/lote/perfil | DTO/query RECE; nunca el hybrid legacy |
| Confirmaciones UI | reset ante cambio de revisión o emisor |
| Docs/API/QA | contrato, rollout y evidencia de suites |

## Estados y transiciones

| Estado actual | Hecho | Estado siguiente | ¿Puede emitir? |
|---|---|---|---|
| ausencia legacy | migración | `no_verificado` | no |
| `no_verificado` | sync WSFE | `no_verificado` | no |
| cualquiera | constancia con modalidad exacta admitida en servidor productivo | `verificado_rece` de producción | sí, si técnica y contextualmente válido |
| cualquiera | constancia genérica o no allowlist | `no_verificado` de producción | no |
| cualquiera | señal negativa oficial futura y versionada | `no_rece` | no |
| `verificado_rece` | cambio de identidad/señal | `no_verificado` | no |
| cualquiera | baja/desactivación/ausencia confirmada por ARCA | conserva acreditación; revisión mayor | no mientras siga la señal negativa |
| `verificado_rece` | bloqueo técnico confirmado por ARCA | mismo estado, revisión mayor | no mientras siga bloqueado |
| `verificado_rece` | señal ARCA vuelve a activa | mismo estado, revisión mayor | sí; no requiere otro PDF |
| cualquiera | edición local fiscal o identidad contradictoria | `no_verificado` | no |

Las transiciones agregan filas; nunca reescriben evidencia anterior.

El hybrid ORM legacy se conserva temporalmente como
`PuntoVenta.usable_factuflow` con semántica exclusivamente técnica. El
serializer sobrescribe el campo público `usable_factuflow` con la conjunción de
ese filtro y la cabeza efectiva del ambiente. Ningún servicio fiscal usa el
hybrid ORM por sí solo como autoridad RECE.

## Fallos intermedios y concurrencia

| Falla | Resultado requerido |
|---|---|
| Dos importaciones concurrentes | revisiones distintas serializadas o un `409`; nunca mismo número |
| Edición concurrente obsoleta | conflicto optimista, sin sobrescritura |
| Cambio de CUIT gana antes de la frontera de atestación | persiste el CUIT nuevo; la constancia anterior responde conflicto sin agregar ni flushear Punto/cabezas |
| Atestación gana antes del cambio de CUIT | persiste evidencia ligada al CUIT original; el update ve dependencias y responde `409` |
| Desactivación o degradación de admin gana antes de la frontera | la atestación responde conflicto y no crea evidencia positiva |
| Atestación gana antes de desactivar o degradar al admin | la revisión positiva se confirma bajo la autoridad válida; la mutación del actor continúa después |
| CUIT actual diverge del snapshot por dato legacy o escritura fuera del contrato | contexto RECE no emitible; cero `FECAESolicitar` |
| Punto cambia antes de crear operación | cero operación y cero intento |
| Cambia después de operación y antes de intento | operación no continuable; cero FECAE |
| Cambia después del intento y antes de FECAE | intento pre-ARCA cerrado de forma verificable; cero FECAE |
| Cambia después de iniciar FECAE | rigen PF-01/PF-02; nunca reintento automático |
| Grupo cambia antes de procesar | operación no creada o respuesta pre-ARCA terminal |
| Preparación/reserva batch falla antes de FECAE | rollback de toda la transacción: cero guardas, intentos y reservas nuevos; WSAA o lecturas seguras pueden haber ocurrido |
| Worker toma snapshot obsoleto | no consulta ARCA ni reencola |
| Crash con guarda `pre_arca` | cierre por CAS solo si se prueba cero inicio |
| Crash con `arca_iniciada` | guarda incierta y reconciliación obligatoria |
| Mutación durante guarda activa | `409`, sin cambiar cabeza ni evidencia |
| Persistencia del ledger falla | rollback conjunto con el punto |
| Migración PostgreSQL parcial | rollback transaccional; la revisión Alembic no avanza |
| Migración SQLite falla después de DDL | detener; restaurar el backup físico verificado antes de reintentar; que Alembic no avance no prueba que SQLite haya quedado intacta |
| Snapshot legacy nulo | replay terminal permitido; continuación bloqueada |
| Respuesta UI del emisor A llega después de cambiar a B | antes del primer `await`, Lotes invalida generaciones y vacía formatos, perfiles y puntos; sus tres loaders y el loader agregado de EmpresaConfig ignoran éxito/error obsoleto, y los `finally` protegidos no apagan el loading vigente |

## Matriz mínima de tests

### Modelo, migración y ledger

- SQLite y PostgreSQL: upgrade, downgrade y re-upgrade; en SQLite, upgrade y
  downgrade requieren backup físico distinto y verificado antes del DDL;
- dos estados `no_verificado` por punto legacy, sin inferencia desde texto;
- constraints de estado, ambiente, revisión y unicidad;
- cabeza transaccional, FKs compuestas, revisión append-only y pertenencia;
- inserciones cruzadas operación/asociación/guarda/intento/grupo rechazadas por
  la base;
- carrera de dos escritores y conflicto optimista;
- backfill con cero puntos y con múltiples emisores;
- snapshots legacy nulos conservan filas históricas;
- downgrade aborta cuando existe evidencia no migratoria.

### Productores y API

- constancia con modalidad exacta admitida, actor admin y fecha documental
  argentina válida/no futura; cubrir antigüedades de 8, 90 y 365 días;
- usuario común, fecha ausente, inválida o futura nunca promueven;
- promoción solo con administrador, atestación y servidor productivo;
  homologación y ambiente inválido fallan cerrado;
- Web Services genérico, sistema no allowlist, vacío y contradictorio quedan
  `no_verificado`, nunca `no_rece` por inferencia;
- dos cargas idénticas crean revisiones monotónicas distintas;
- reloj inyectable: bordes de 89/90 días para la comprobación técnica sin
  degradar la acreditación;
- CUIT de otro emisor sigue rechazado;
- CUIT cambiado antes de la frontera aborta la atestación antes de cualquier
  `db.add` o `flush` de Punto/cabezas;
- el contexto emitible rechaza un `empresa_cuit_snapshot` distinto del CUIT
  actual;
- PostgreSQL serializa la carrera update/atestación con ambos ganadores: update
  primero deja cero evidencia; atestación primero bloquea el cambio fiscal;
- PostgreSQL serializa también atestación frente a `activo=false` y
  `es_admin=false`, con ambos ganadores y sin publicar evidencia bajo una
  autoridad obsoleta;
- FEParam disponible, vacío, bloqueado y con baja nunca promueve;
- alta manual crea ambos ambientes cerrados;
- edición de identidad invalida ambos ambientes;
- edición técnica incrementa revisión;
- pertenencia multiemisor y respuesta sin datos privados.

### Individual e idempotencia

- no verificado/no RECE/ambiente incorrecto: cero operación, intento, WSAA y
  FECAE;
- verificado: flujo feliz existente;
- PF-19A sigue denegando;
- replay terminal después de cambio devuelve respuesta sin ARCA;
- replay continuable y confirmación de duplicado con revisión distinta fallan;
- operación, asociaciones y digest canónico se crean atómicamente; recuperación
  ambigua exige el conjunto completo;
- misma clave/payload distinto conserva `409`;
- operación legacy sin snapshot no continúa;
- cambio entre precheck, lock, intento y segundo preflight;
- emisor cruzado y punto recreado/renumerado.

### Lotes, worker y stale

- punto fijo, punto desde archivo y perfil aceptan acreditados listos o
  pendientes; una señal negativa confirmada queda deshabilitada;
- grupo guarda evidencia y revisión;
- grupo guarda identidad durable del punto y la operación normaliza snapshots
  de múltiples puntos;
- digest RECE forma parte de hash y confirmación;
- cambio posterior invalida proceso y reintento;
- cambio y restauración también invalida;
- worker/núcleo bloquea antes de FECAE; WSAA y `FECompTotXRequest` pueden ocurrir
  en la capa exterior antes de formar el sublote;
- guarda única activa, fases/CAS, batch con varios intentos, cierre terminal,
  crash pre-ARCA e incertidumbre sin liberación por TTL;
- fallback conserva snapshot;
- grupo legacy no reemite;
- reconciliación autorizada existente sigue siendo solo lectura/registro;
- aislamiento por emisor, lote y grupo.

### Frontend

- textos `Listo para emitir`, `Comprobación recomendada`, `Pendiente de
  comprobar con ARCA` y `Requiere atención`;
- sync crea/mantiene puntos no verificados;
- importación refresca evidencia;
- selectores mantienen acreditados pendientes con “se comprobará al emitir” y
  ocultan señales negativas o puntos sin constancia;
- cambio de emisor o revisión invalida selección, confirmación y clave;
- el watcher de Lotes invalida generaciones y vacía formatos, perfiles y puntos
  antes del primer `await` de un cambio de emisor;
- los tres loaders de Lotes capturan empresa + generación de request, descartan
  éxito/error obsoleto y la cadena revalida el emisor después de cada `await`
  antes de iniciar el siguiente loader; el `finally` de perfiles tampoco apaga
  el loading vigente;
- el loader agregado de configuración aplica la misma guarda, vacía de inmediato
  perfiles, formatos, puntos y catálogo, y un `finally` tardío no apaga el
  loading de la solicitud vigente;
- la garantía limpia el estado propio de esos loaders y descarta la finalización
  tardía; no implica cancelar la request HTTP ni se extiende por inferencia a
  otros loaders;
- lote exige token nuevo después de revalidación.

El listado usa el estado efectivo calculado por el servidor, muestra fuente,
revisión y frescura técnica, y oculta la vigencia histórica. La comprobación
técnica se ejecuta en una única operación server-side; el navegador no encadena
escrituras punto por punto.

Cada caso ARCA usa dobles. No se justifica excluir ningún invariante capaz de
habilitar FECAE; los tests PostgreSQL pueden omitirse solo cuando falte la URL
desechable explícita y deben ejecutarse en CI o antes del release candidate.

## Rollout y rollback operativo

1. Mantener la lista PF-19A durante todo el rollout.
2. Un administrador obtiene una constancia desde la gestión productiva de ARCA;
   FactuFlow procesa el archivo sin conservarlo.
3. Ensayar migración sobre PostgreSQL desechable o restauración aislada.
4. Confirmar backup recuperable y conteos preflight.
5. Migrar: todos los puntos quedan cerrados por defecto.
6. Iniciar la aplicación con `ARCA_ENV=produccion`; el administrador selecciona
   la constancia y la importación sigue directamente el camino seguro.
   Homologación permanece cerrada en este corte.
7. Verificar por UI/API que solo la señal exacta quede acreditada, que los
   pendientes sigan seleccionables y que señales negativas queden excluidas.
8. Ejecutar QA post-deploy sin solicitar CAE.
9. Retirar una regla PF-19A solo mediante una decisión operativa posterior,
   contra evidencia exacta y nunca dentro de la migración.

La UI no muestra `Vigente hasta`. A los 90 días recomienda `Comprobar con ARCA`,
pero la acción es opcional: cualquier emisión pendiente ejecuta el mismo
preflight automáticamente y falla cerrado si ARCA no puede confirmar el estado.

El rollback de código conserva el ledger. Volver a un binario que ignore PF-19B
podría reabrir puntos y no es seguro sin restaurar una contención equivalente;
por eso el rollback operativo debe reponer la versión anterior junto con la
lista PF-19A completa y verificar cero operaciones iniciadas durante la ventana.

## Cortes internos de implementación

1. **PF-19B.1 — fail-closed central, completado:** configuración estricta,
   modelo, migración, cabeza/ledger, guarda durable y compuerta final en los
   callsites individual y batch.
2. **PF-19B.2 — autoridad y enforcement completo, completado:** atestación
   productiva administrativa, snapshots/idempotencia atómicos, intentos,
   grupos, perfiles, Excel, proceso, worker, reintentos, stale y tests fiscales.
3. **PF-19B.3 — UI y documentación, completado en el estado objetivo:** tipos,
   badges y estados efectivos, selectores, invalidaciones, sincronización
   server-side, manuales, API y QA.

Los tres cortes forman una única unidad PF-19B. B.1 aislado denegaría toda
emisión porque no tendría un productor runtime de `verificado_rece`; B.2 agrega
la única atestación positiva admitida y B.3 alinea los consumidores visibles.
No se publica ni se despliega un corte parcial.

## Aplicación del checklist fiscal Nivel 2 para 0.3.1

- **Alcance y consumidores:** se revisaron importación y listado de puntos,
  perfiles, selectores, emisión individual, lotes nuevos, continuaciones,
  worker, reintentos e idempotencia. No cambian fecha fiscal, numeración,
  receptor, importes, comprobantes asociados ni persistencia de CAE.
- **Contrato externo:** la única lectura nueva es `FEParamGetPtosVenta`; una
  respuesta fallida, vacía, duplicada o fuera de contrato se considera no
  disponible. Las pruebas usan dobles y nunca consultan ARCA real.
- **Orden fiscal:** un replay terminal se devuelve primero. Para trabajo nuevo o
  continuable, la comprobación pendiente/desactualizada ocurre antes de crear
  operación, intento, reserva o guarda; luego se toman los locks RECE y se
  ejecutan los compare-and-swap existentes antes de `FECAESolicitar`.
- **Invariantes:** sólo una constancia exacta acredita; la sincronización nunca
  promueve. El tiempo no degrada la acreditación. Bloqueo, baja o ausencia
  confirmados impiden emitir. Un cambio de identidad o una señal RECE
  contradictoria invalida. Cada emisor usa como máximo un snapshot técnico por
  preflight.
- **Fallos y recuperación:** indisponibilidad técnica devuelve `503` sin estado
  fiscal nuevo. Una continuación conserva su estado recuperable. Una carrera
  posterior se detecta por la revisión fiscal; si ARCA pudo autorizar, siguen
  rigiendo las guardas inciertas y la reconciliación, sin reintento automático.
- **Atomicidad y base:** el snapshot técnico completo se valida antes de escribir
  y se aplica con un único commit. La migración preserva acreditaciones positivas
  y el downgrade rellena vigencias nulas antes de restaurar la constraint de
  siete días. SQLite cubre upgrade/downgrade/re-upgrade; PostgreSQL se ejecuta
  mediante su harness desechable en CI.
- **Matriz y privacidad:** se cubren 8/90/365 días, fecha futura, primera carga
  sin ARCA, recuperación posterior, borde 89/90, varios puntos por emisor,
  señales negativas, `503` sin operación y la UI sin modal. No se versionan PDF,
  CUIT, certificados, CAE ni evidencia real.

## Puertas de cierre

- matriz backend/frontend completa; PostgreSQL desechable debe quedar probado
  por CI o por una ejecución explícita con el guard destructivo exacto;
- Ruff, Black, ESLint, type-check, build, suites raíz y auditorías productivas;
- puerta documental semántica completa;
- `autoreview` único con Codex `gpt-5.6-sol medium` después de estabilizar el
  diff;
- clasificación explícita de cada hallazgo;
- PR Nivel 2, CI verde y verificación posterior al merge;
- release y despliegue solo mediante el checkpoint separado, con backup,
  migración ensayada, constancia válida y autorización explícita.
