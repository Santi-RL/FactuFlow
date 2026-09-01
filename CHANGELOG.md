# Changelog

Este archivo resume qué cambió en FactuFlow y en qué versión. Las prioridades
futuras viven únicamente en `ROADMAP.md`.

Reglas vigentes desde 2026-05-22:

- El estado aceptado del repositorio se consulta en
  `docs/agents/current-status.md`; las prioridades, en `ROADMAP.md`.
- El historial versionado se resume acá. Evitar crear nuevos snapshots largos
  de documentación si el cambio puede quedar explicado en este changelog, el
  roadmap y la documentación viva.
- Los documentos antiguos bajo `docs/project/**` son material histórico. No
  deben usarse como fuente de verdad actual si contradicen la documentación
  viva.
- No registrar CUITs, CAEs, nombres reales, Excels, PDFs, logs ni evidencia
  privada en este archivo.

## [Unreleased]

## [0.3.4] - 2026-09-01

### Cambios

- PF-19D convierte `FEParamGetPtosVenta` en la autoridad autenticada para
  descubrir y clasificar puntos de venta por emisor y ambiente. Sólo modalidades
  `CAE - …` explícitas pueden quedar elegibles para el flujo implementado.
- Se agrega la preferencia compartida `Usar en FactuFlow`. Los puntos CAE nuevos
  quedan habilitados por defecto y toda deshabilitación explícita sobrevive a
  bloqueos, ausencias, reapariciones y comprobaciones posteriores.
- La pantalla muestra por defecto los puntos usados en FactuFlow, permite ver
  todos, confirma los cambios de uso y conserva formularios, perfiles y lotes
  recuperables cuando un punto deja de estar disponible.
- Número, sistema, presencia, bloqueo y baja pasan a ser de sólo lectura. Los
  usuarios autorizados pueden editar nombre interno, domicilio y nombre de
  fantasía; la procedencia descriptiva distingue carga manual y constancia ARCA.
- La constancia PDF queda como complemento opcional: no consulta WSFE, no
  acredita elegibilidad, no invalida ausentes y no se almacena.

### Seguridad fiscal

- La sincronización valida el snapshot completo antes de escribir y aplica
  puntos presentes, ausentes y cabezas de elegibilidad en una única transacción.
  Vacíos, duplicados, respuestas inconsistentes y timeouts fallan con `503` sin
  crear operaciones, intentos, reservas ni solicitudes CAE.
- Individual, perfiles, lotes, worker, reintentos y continuaciones consumen el
  mismo `seleccionable_para_emision`, que ahora incluye la preferencia. Se
  conservan frescura de 90 días, preflight agrupado, revisión fiscal, locks,
  compare-and-swap, idempotencia y reconciliación.
- La migración `e3f4a5b6c7d8` incorpora preferencia y procedencia, conserva el
  ledger PF-19B y aplica un backfill conservador. El rollback es exacto antes de
  producir evidencia WSFE nueva y falla cerrado después.

### Documentación

- Se actualizaron contrato API, guía de usuario, notas ARCA, QA manual, estado,
  portafolio, roadmap y dossier de release para reflejar PF-19D sin inferir el
  estado de ninguna instalación productiva.
- Se publicó la GitHub Release `v0.3.4`, marcada como `Latest`, desde el tag
  inmutable que apunta a `38cb4d6dc4faba819292ed8da9b833c68d9b8968`.
  Sus siete controles de CI aprobaron, incluido Runtime Smoke. La publicación
  no desplegó ni modificó el VPS.

## [0.3.3] - 2026-08-31

### Correcciones

- PF-03B cierra el contrato de ítems: campos desconocidos, descuentos inválidos
  y valores no finitos o no calculables se rechazan antes de crear estado fiscal.
- La UI envía únicamente datos de creación, distingue un campo vacío de un cero
  explícito, informa errores accionables y exige revisar nuevamente al editar
  importes. Las verificaciones inciertas conservan solicitud y clave originales.
- La importación oficial y personalizada conserva entradas inválidas para
  informar su error; no sustituye descuentos ilegibles por cero ni ignora un
  total informado inválido. Constantes y valores predeterminados se validan al
  guardar y al consumir formatos, incluidos los seleccionados desde perfiles.
- Lotes, worker, reintentos y reconciliación comparten el contrato estricto.
  Los snapshots válidos mantienen contenido y hash; no hay migración de base.

### Documentación

- Se reorganizó la arquitectura documental: roadmap prospectivo, handoff breve,
  portafolio activo, runbooks reutilizables y snapshots fieles, anonimizados y
  con hashes en
  `docs/project/history/`.
- Se incorporó la regla canónica de simplicidad segura: los agentes no pueden
  aumentar fricción operativa ni reducir protecciones sin una decisión explícita
  del usuario.
- PF-19D conserva su especificación aceptada en un diseño propio, sin presentar
  esa conducta futura como funcionalidad disponible en `v0.3.2`.
- Se registró la publicación de la GitHub Release `v0.3.2`, marcada como
  `Latest`, desde el tag inmutable que apunta a
  `9c0310d397001a331dc40353815ef9b2359d80de`. El estado desplegado se consulta
  exclusivamente en `VPS Hostinger` / `vps-admin`.
- Se publicó la GitHub Release `v0.3.3`, marcada como `Latest`, desde el tag
  inmutable que apunta a `3d12c43fc2406b83ab8390e76f5cb1804e5827a4`.
  Sus siete controles de CI aprobaron, incluido Runtime Smoke. La publicación
  no desplegó ni modificó el VPS.

## [0.3.2] - 2026-08-29

### Correcciones

- Los selectores de nueva factura, lotes y perfiles ya no ofrecen puntos con el
  estado “se comprobará al emitir”. FactuFlow prepara la lista con una única
  comprobación cuando hay acreditados pendientes o con 90 días, recarga y solo
  habilita puntos confirmados.
- El contrato agrega `seleccionable_para_emision` sin retirar
  `usable_factuflow` ni `puede_intentar_emision`. La guarda final del servidor
  antes de crear estado fiscal o solicitar CAE permanece intacta.
- `Comprobar con ARCA` queda disponible para cualquier usuario autorizado del
  emisor activo. La consulta continúa siendo atómica, aislada por emisor y sin
  capacidad para acreditar RECE.
- La pantalla de puntos de venta aplica la matriz UX aprobada: los estados
  normales son breves, los puntos de otros sistemas no sugieren una acción y
  los errores indican exactamente cómo resolverlos. Se eliminan procedencia,
  ambiente, revisión fiscal y explicaciones técnicas de los estados normales.
- El resumen de importación informa tres cantidades mutuamente excluyentes:
  listos para emitir, no disponibles en FactuFlow y requieren revisión.
- La versión técnica y visible queda sincronizada en `0.3.2`. Este parche no
  agrega migraciones, dependencias, cambios de Docker ni configuración
  productiva.

### Seguridad fiscal

- Una falla de preparación conserva disponibles los puntos todavía vigentes y
  excluye los pendientes. El preflight server-side sigue devolviendo `503` con
  cero operaciones, intentos, reservas y solicitudes CAE nuevas cuando ARCA no
  puede confirmar el estado.

### Documentación

- Se registró la publicación de la GitHub Release `v0.3.1`, marcada como
  `Latest`, desde el tag inmutable que apunta a
  `7afba87b1b56509ffafb7bfefa0dcd23cd2e45a7`. El despliegue continúa como un
  checkpoint separado y su estado vive en `VPS Hostinger` / `vps-admin`.

## [0.3.1] - 2026-08-28

### Correcciones

- `0.3.1` es un parche compatible de `0.3.0`: el importador de
  constancias reconoce tanto el encabezado histórico `PUNTO VENTA` como el
  formato vigente `P.VTA.` con columna `ACTIVIDAD`, y procesa de forma segura
  encabezados repetidos en documentos multipágina.
- El clasificador probatorio sube a `rece_constancia_v2` y mantiene una
  allowlist exacta de las modalidades Web Services de régimen general
  documentadas por ARCA para Responsables Inscriptos, Exentos en IVA y
  Monotributistas. Las coincidencias parciales, Comprobantes en Línea,
  Factuweb, Controlador Fiscal y `Web Services` genérico continúan cerradas.
- La acreditación inicial obtenida de una constancia válida pasa a ser durable:
  no vence por el transcurso de siete días ni obliga a cargar otro PDF. La
  fecha documental continúa siendo obligatoria, no ambigua y no futura.
- Se separa la acreditación de la comprobación técnica con ARCA. Cada punto
  registra `ultima_comprobacion_arca_en`; después de 90 días la UI recomienda
  comprobar, pero no invalida la constancia. Un punto acreditado pendiente o
  desactualizado se comprueba automáticamente antes de una emisión capaz de
  alcanzar CAE.
- Si esa comprobación automática no obtiene una respuesta completa y coherente,
  el servidor devuelve `503` antes de crear operación, intento, reserva o
  solicitud de CAE. Bloqueo, baja o ausencia confirmados impiden emitir; una
  comprobación activa posterior rehabilita el punto sin otro PDF.
- La importación de constancias ya no muestra opciones ni confirmación
  intermedia: seleccionar el PDF ejecuta siempre el camino seguro. La acción
  manual se denomina `Comprobar con ARCA` y permanece opcional.
- La versión técnica y visible queda sincronizada en `0.3.1`. El parche no
  incorpora datos, PDFs ni identificadores reales. El tag, la publicación y el
  despliegue se ejecutan y registran como checkpoints separados.

### Documentación

- Se registró la publicación de la GitHub Release `v0.3.0` desde el tag
  inmutable que apunta a `39797d1ff9c698465255cf4f821240171c235cab`.
  Producción continúa en `v0.2.2`; la publicación no autoriza ni ejecuta el
  despliegue.

## [0.3.0] - 2026-08-11

> Estado al cierre documental: contenido de release congelado. La creación del
> tag, la publicación y el despliegue se registran mediante checkpoints
> posteriores; producción permanecía en `v0.2.2`.

### Alcance de la release

- Se sincronizó la versión técnica y visible `0.3.0` en los manifiestos raíz,
  backend y frontend, la configuración/API y la barra lateral. El SHA funcional
  validado es `e9c583a8174ea8edc6fe30845584033feab0394d`, sobre `b5eefcd`;
  el merge funcional aceptado en `main`, `2add308a933109f83f73e67aeb4991d84c783dca`,
  aprobó los siete checks en la ejecución
  [`31446404345`](https://github.com/Santi-RL/FactuFlow/actions/runs/31446404345).
  El cierre documental post-merge `147693f232777e5d9cb5e9257c84802cbe359188`
  aprobó su recorrido Nivel 0 en
  [`31458109268`](https://github.com/Santi-RL/FactuFlow/actions/runs/31458109268).
  La preparación final `6fb2878479db84cfa9b3caada8de98ce9bfd009c`
  aprobó también su recorrido Nivel 0 en
  [`31462387733`](https://github.com/Santi-RL/FactuFlow/actions/runs/31462387733).
  Al cerrar este contenido, la última release publicada y producción eran
  `v0.2.2`; la creación del tag, su publicación y el despliegue se registran por
  separado.
- PF-19C en `c1dbd82` completó diseño, implementación y evidencia con dobles y SQLite.
  La suite backend registró `1049 passed`, `22 skipped`, `31 warnings` en
  `9m14s`; la cobertura total branch-aware fue `69.2278%` (líneas `73.6741%`,
  ramas `55.1759%`, gate `69%`). Los skips son PostgreSQL sin URL/daemon local.
  El `autoreview` final autorizado terminó limpio con Codex `gpt-5.6-sol`
  (`medium`): TruffleHog limpio, `5/5` pasadas, cero hallazgos y probabilidad
  `0,98` de parche correcto. La CI Nivel 2 del 10/08/2026, ejecución
  [`31354948875`](https://github.com/Santi-RL/FactuFlow/actions/runs/31354948875),
  aprobó los siete checks del SHA funcional: Backend Tests registró `1076`
  pruebas aprobadas, `32` warnings, `441,83 s` y cobertura total `70,03%`; E2E
  aprobó `33` pruebas y Runtime Smoke aprobó contra PostgreSQL real. La
  aceptación funcional-contable PF-16G fue registrada el 10/08/2026. El
  candidato `7f7b3808` aprobó además un ensayo privado con backup reciente,
  restauración aislada, upgrade hasta `c0d1e2f3a4b` y rollback exacto hasta
  `a8b9c0d1e2f3`, sin modificar producción.
- PF-16C, PF-16D y PF-16E quedaron incorporados en `main` para `v0.3.0`:
  Node.js 24, auditorías npm, cobertura con gates, CI PostgreSQL/Runtime Smoke
  y `27/27` tests de scripts. PF-16G ya tiene matriz, dossier y aceptación
  funcional-contable registrada el 10/08/2026. La firma externa de manifests
  VPS permanece como P2 posterior y no bloquea `v0.3.0`.
- La guía de trabajo prioriza unidades enfocadas y releases seguros sin ampliar
  el alcance automáticamente: un bloqueo real se consulta al desarrollador y
  los hallazgos no bloqueantes se difieren al roadmap.

### Planificación de producto

- La evidencia productiva de `v0.2.2` abrió PF-19 como P1 fiscal Nivel 2 y lo
  priorizó antes de PF-03B. El PR `#27` (merge `45c0704`) integró PF-19A en
  `main` y cerró diseño, consumidores, contención preautorización e inventario
  legacy de solo lectura. PF-19B completa en `main` sus tres cortes internos
  como una sola unidad: elegibilidad RECE durable y fail-closed, atestación
  administrativa de una constancia productiva fresca, control integral en todos
  los caminos fiscales y estados visibles en la UI. PF-19C conserva los códigos
  globales estructurados, la clasificación terminal de `10005` bajo contrato
  oficial y el cierre auditado de historia legacy; después se retoma PF-03B.
  PF-02 permanece cerrado y sin cambios de numeración; PF-03 conserva
  ítems/importes; PF-09, PF-14 y PF-15 son consumidores. La trazabilidad del
  backup preoperación se enrutó a PF-11/PF-15.
- PF-17 incorpora como trabajo futuro de banda C una señal liviana de
  conectividad y recuperación segura. La propuesta distingue pérdida de red,
  servidor no disponible, conexión inestable y recuperación; reutiliza
  healthchecks sanitizados con pestaña activa y backoff, sin monitoreo pesado.
  No habilita operación offline, caché de datos fiscales, colas locales ni
  reintentos automáticos de escrituras o solicitudes de CAE. PF-03B y el orden
  de prioridades inmediatas permanecen sin cambios.

### Validación fiscal

- PF-19C incorpora evidencia estructurada de errores globales WSFE y acepta
  como terminal únicamente `10005` entero exacto con cabecera `R` correlacionada
  (CUIT, punto, tipo, cantidad y rangos), un solo error y sin detalle ni CAE.
  Códigos mezclados, texto, tipos no enteros, respuesta parcial, timeout,
  transporte o contradicción inmovilizan la operación en
  `requiere_reconciliacion`; nunca habilitan retry ni una nueva FECAE.
- Un rechazo global confirmado cierra atómicamente el sublote enviado y detiene
  el lote: los grupos posteriores quedan `no_enviado_por_rechazo_global`, sin
  atribuirles un rechazo ARCA. La publicación y el replay conservan ownership
  por `operacion_id`; una carrera de A hacia B no permite publicar ni emitir
  sobre la operación ajena.
- La revisión `c0d1e2f3a4b` agrega evidencia ARCA estructurada y el journal
  legacy PF-19C append-only. El plan es read-only; apply exige backup verificable,
  hash, actor, plan inmutable y consultas seguras. Un ambiente legacy
  indeterminado exige producción y homologación; cualquier autorización o duda
  conserva reconciliación. La migración VPS valida esa evidencia y omite el
  journal/terminales PF-19C, sin recrearlos.

- PF-19B reemplaza la inferencia mutable de Web Services por un ledger
  inmutable de elegibilidad RECE, una cabeza transaccional por punto y ambiente,
  revisión fiscal monotónica, snapshots en operaciones/intentos/grupos y una
  guarda durable antes de `FECAESolicitar`. La migración deja cada punto legacy
  como `no_verificado` tanto en homologación como en producción, sin inferir
  elegibilidad desde texto, procedencia o actividad técnica.
- Solo un administrador activo, en un servidor configurado para producción,
  puede acreditar `verificado_rece` al procesar una constancia productiva de
  hasta siete días, confirmar expresamente su procedencia y coincidir con la
  señal exacta versionada. FactuFlow conserva hash y metadatos probatorios
  mínimos, no el PDF. Una señal genérica queda `no_verificado`; homologación
  permanece cerrada mientras no exista una fuente probatoria específica.
- La sincronización WSFE es ahora una operación server-side transaccional que
  actualiza exclusivamente el estado técnico y nunca promueve RECE. API y UI
  exponen `Verificado RECE`, `No RECE` y `No verificado`, procedencia y vigencia;
  perfiles, Excel y selectores consumen únicamente la elegibilidad efectiva.
  Emisión individual, lotes, worker, fallback, reintentos y recuperación stale
  revalidan los mismos snapshots antes de `FECAESolicitar`; un punto sin
  acreditación vigente aborta antes de crear una operación nueva o solicitar
  CAE.
- PF-19A agrega una contención privada y estricta por ambiente, emisor,
  ID/número de punto de venta y tipo de comprobante. Una coincidencia aborta
  en el núcleo fiscal antes de crear intento o invocar `FECAESolicitar`, con
  cero CAE y cero comprobantes. El match por ID o número evita levantar el
  bloqueo renumerando una fila o recreando el número fiscal con otro ID. La
  selección ante cruces es determinística (`ID+número > ID > número`). La
  contención es opt-in y adicional: una tupla omitida no activa PF-19A, pero
  tampoco elude la compuerta durable y fail-closed de PF-19B.
- El inventario PF-19A consulta candidatos `arca_batch_sin_respuesta` y
  `arca_respuesta_incierta` dentro de transacciones verificadas de solo lectura,
  siempre revertidas. Restaura el modo previo de SQLite, valida el alcance de
  punto/operación/lote/grupo y de los comprobantes directos o asociados antes de
  examinar señales, incluida la coincidencia de emisor, punto, tipo y número
  planificado; sin número planificado, la referencia no es válida. Separa
  referencias huérfanas o cruzadas. Exige emisor, acepta exactamente `500`
  registros, consulta como máximo `501` filas y aborta al detectar `501`, sin
  truncar. La salida sanitizada sigue siendo evidencia privada porque conserva
  IDs operativos, punto y tipo; omite CUIT, receptor, importes, CAE, fechas
  fiscales y marcas temporales de comprobantes/intentos, payloads y mensajes
  crudos. Conserva únicamente `generado_el` en `DD/MM/AAAA`, informa el ambiente
  histórico como indeterminado y trata una firma textual `10005` solo como
  candidata; no llama a ARCA, no cambia estados y no sanea registros. Los logs
  privados pueden conservar identificadores operativos mínimos, nunca secretos
  ni contenido fiscal sensible.
- PF-03A cierra el objeto superior de `EmitirComprobanteRequest`: una clave no
  documentada devuelve `422 extra_forbidden` antes de crear idempotencia,
  reservar numeración o alcanzar el servicio fiscal. Erratas como `monedaa`,
  `cotizaccion`, `guardar_clientee` o una confirmación mal escrita ya no pueden
  activar valores predeterminados de manera silenciosa.
- Los snapshots batch creados por FactuFlow continúan siendo canónicos. Un
  payload histórico o manipulado con claves superiores desconocidas falla
  cerrado en procesamiento, reintento, stale o reconciliación, sin solicitar
  CAE ni limpiar una instrucción fiscal que el sistema no comprende. Si una
  consulta segura ya confirma autorización, conserva CAE y vencimiento en
  `requiere_reconciliacion` sin reconstruir el comprobante desde datos inválidos.
  La serialización estricta de ítems y los límites de descuentos/importes
  quedan separados para PF-03B.

### Numeración fiscal

- PF-02A, integrado mediante el PR `#15` (`c872497`), distingue numeración
  `alineada`, `arca_adelantada` y `local_adelantada` en emisión individual.
  Cuando la diferencia proviene de historia externa legítima usa
  `ultimo_arca + 1`; los intentos propios activos o inciertos y la numeración
  local adelantada continúan bloqueando.
- PF-02B.1, integrado mediante el PR `#16` (`2c75fd2`), extiende la misma
  autoridad al núcleo batch: reserva el rango completo y repite
  `FECompUltimoAutorizado` antes de `FECAESolicitar`. Un cambio o error aborta
  el sublote con cero solicitudes de CAE y cero comprobantes nuevos.
- PF-02B.2, integrado mediante el PR `#19` (`1a5e335`), cierra el contrato de
  reintentos manuales: admite
  `arca_adelantada`, detiene la selección ante bloqueos o abortos del segundo
  preflight, permite continuar solo después de un rechazo ARCA explícito y
  conserva `requiere_reconciliacion` ante cualquier incertidumbre post-ARCA.
  Una falla local posterior a una autorización conocida hace rollback del
  comprobante incompleto, preserva número/CAE en el intento y nunca vuelve el
  grupo a `fallido`. Los errores inesperados se muestran sanitizados.
- PF-02B.3 cierra la recuperación stale del worker: los pendientes realmente
  intactos pueden volver a cola con diagnóstico `alineada` o
  `arca_adelantada`, sin asignar número, crear intento ni solicitar CAE. Los
  intentos propios activos o inciertos siguen bloqueando; el procesamiento
  normal conserva la reserva durable y el segundo preflight. Los errores
  persistidos usan categorías sanitizadas y no exponen textos de excepción.
- PF-05 mantiene separada la reconstrucción histórica opcional para informes.
  PF-02, PF-03A y PF-19A/B/C pertenecen a la release publicada `v0.3.0`, pero
  todavía no están desplegados en producción.

### Calidad y seguridad

- El PR `#20` (`712197d`) actualiza `cryptography` de `48.0.1` a `50.0.0`,
  corrigiendo
  `PYSEC-2026-3552`, `PYSEC-2026-3553` y `PYSEC-2026-3554` sin excepciones en
  la auditoría. La compatibilidad de carga PEM, claves cifradas y firma CMS se
  verifica con material criptográfico sintético.
- Tres pruebas de numeración batch conservan su fecha fiscal fija y aíslan la
  validación temporal que no forma parte de esos escenarios. Esto evita que el
  reloj de ejecución venza los tests sin relajar la validación productiva.
- Se incorpora una política proporcional de calidad con tres niveles de riesgo,
  una plantilla de PR comprensible sin leer código y una única rama permanente:
  `main`. Las ramas de trabajo son temporales y se eliminan después del merge.
- La CI agrega clasificación documental conservadora, tests de scripts, Ruff,
  Black, type-check, lint, build, unit tests, E2E y auditorías bloqueantes de
  dependencias productivas; se retira el Pylint decorativo que ignoraba fallos.
- `pypdf` se actualiza de `6.14.2` a `6.15.0` para corregir
  `CVE-2026-71852` y `CVE-2026-71870`. Los dos parsers de constancias se
  verifican con PDFs sintéticos reales generados en memoria, desde la extracción
  hasta los campos fiscales, y encapsulan PDFs malformados como errores de
  dominio.
- PostCSS permanece en `8.5.23` y su dependencia transitiva `nanoid` se resuelve
  en `3.3.17` para corregir `CVE-2026-67213`, sin cambiar `package.json` ni usar
  actualizaciones forzadas. Las auditorías productivas de Python y npm quedan
  limpias; la modernización mayor del toolchain frontend continúa planificada
  por separado.
- La alineación documental pasa a ser una puerta explícita antes del commit y
  antes de marcar un PR como listo. La plantilla exige una matriz por impacto y
  la CI comprueba versiones y marcadores transitorios también en cambios Nivel
  0; este control estructural no reemplaza la revisión semántica.
- Después de PF-02B.2, la matriz documental separa resumen/arquitectura, API y
  evidencia de testing. Un contrato HTTP o comando de test sin cambios ya no
  justifica por sí solo un `No aplica` cuando cambió la semántica documentada,
  el estado de `main` o la evidencia vigente.
- Se explicita que `autoreview --mode local` es el cierre predeterminado de un
  diff sin commit; `--mode commit` queda reservado para commits que ya existen
  por una razón real y `--mode branch` para rangos acumulados.

## [0.2.2] - 2026-07-23

> Estado: release publicada y desplegada en producción el 2026-07-23 desde el
> tag inmutable `v0.2.2`.

### Confiabilidad fiscal

- WSFE solo acepta autorizaciones individuales con `Resultado=A`, CAE ASCII de
  14 dígitos y vencimiento válido. Respuestas parciales, ambiguas o globalmente
  erróneas no se persisten como comprobantes autorizados.
- Los fallos inesperados posteriores a iniciar `FECAESolicitar` conservan un
  estado reconciliable y bloquean reintentos inseguros. La UI individual
  mantiene la misma clave y payload mientras el resultado sea incierto.
- La frontera DB/FECAE distingue recuperación pre-ARCA comprobada de estados
  inciertos. Solo devuelve `503` cuando confirmó durablemente cero intentos;
  cualquier ambigüedad conserva `409`, ownership e idempotencia.
- PF-01B incorpora vocabularios cerrados y constraints persistidos para estados,
  reservas activas y coherencia entre autorización, CAE y vencimiento.

### Migración y persistencia

- Se agrega la revisión Alembic `a8b9c0d1e2f3`, posterior a
  `f7a8b9c0d1e2`.
- La migración audita cinco categorías de datos legacy antes del DDL y aborta
  con conteos sanitizados si encuentra estados desconocidos, autorizados
  incompletos, CAE en estados no autorizados o reservas activas duplicadas.
- No normaliza ni completa datos fiscales por inferencia. SQLite y PostgreSQL 16
  efímero validaron upgrade, downgrade, constraints, estados y concurrencia.

### Operación de lotes y base de datos

- PostgreSQL separa el pool API, limitado a cuatro conexiones sin overflow, de
  una conexión dedicada al worker secuencial. Los timeouts y warnings son
  configurables con límites seguros.
- Las sesiones API adquieren conexión recién al primer SQL; saturación y
  desconexiones responden `503` sin exponer detalles internos.
- El seguimiento de lotes usa una consulta allowlist, polling adaptativo y
  guards ante cambios de emisor o respuestas tardías.
- `Sistema > Estado` muestra salud sanitizada del worker y de los pools.

### Seguridad

- Pillow se actualiza de `12.2.0` a `12.3.0` para cerrar los avisos de
  seguridad detectados por CI.
- Los errores de base y emisión mantienen detalle solo en logs privados y
  devuelven mensajes públicos sanitizados.

### Validación acumulada

- El baseline funcional `f9d170a` tiene CI `29275715128` verde en Security
  Audit, Backend Tests, Frontend Build y E2E Tests.
- PF-01B aprobó `531` pruebas backend con `4` omisiones configuradas y un
  harness PostgreSQL 16 de `4` pruebas.
- Los cortes sensibles fueron revisados con `autoreview`; las revisiones
  finales efectivas usaron `gpt-5.5 high` según la política vigente.
- Clawpatch revalidó R02/B03/B04/B24/B10/B17 como `fixed`, sin
  `clawpatch fix` ni llamadas reales a ARCA.
- La preparación `0.2.2` aprobó lint, type-check, Black, `531` pruebas
  backend, `127` frontend, `3` de scripts y build.

### Preparación de release

- El alcance funcional se congela después de PF-01 y antes de PF-02.
- El versionado técnico y visible se publicó como `0.2.2`.
- El inventario, migración, rollback y puertas pendientes están en
  `docs/project/releases/v0.2.2-candidate.md`.
- La primera pasada de `autoreview gpt-5.5 high` detectó un P2 válido:
  metadatos `0.2.1` remanentes en dos manifiestos backend. Se aceptó y corrigió;
  la pasada final quedó limpia, sin findings, con confianza `0,82`.
- El commit candidato `0271d8a` aprobó la CI `29284577864` completa:
  Security Audit, Backend Tests, Frontend Build y E2E Tests.
- El ensayo privado aprobó backup cifrado recuperable, copia externa,
  restauración aislada de un backup productivo reciente, cinco categorías de
  preflight en cero, migración, constraints, pools, worker y smoke checks sin
  llamadas de emisión a ARCA ni cambios productivos.
- El tag, la GitHub Release y el despliegue productivo tuvieron autorizaciones
  explícitas y separadas.

### Despliegue productivo

- El tag `v0.2.2` se desplegó desde el SHA exacto
  `64629957ebff64ca60f474fcb44f054557e69ec0`; `main` no se usó como target.
- Bajo mantenimiento se creó y validó un backup final mediante checksums,
  inspección del dump PostgreSQL y validación de los paquetes, sin reemplazar
  las copias recuperables existentes.
- El preflight PF-01B dio cero en las cinco categorías inmediatamente antes del
  DDL. Alembic avanzó una sola vez de `f7a8b9c0d1e2` a
  `a8b9c0d1e2f3 (head)`.
- Los tres constraints, las cinco invariantes y los conteos agregados quedaron
  preservados. Aprobaron pools API/worker `4 + 1`, Uvicorn único, worker
  saludable y los smoke checks de lectura, autenticación, reportes y PDF.
- FactuFlow reabrió correctamente y los servicios vecinos permanecieron sanos.
  No hubo llamadas ARCA de escritura, solicitudes de CAE, emisiones, reintentos
  fiscales, downgrade ni restauración productiva.
- La evidencia concreta y los artefactos permanecen en la documentación
  operativa privada.

## [0.2.1] - 2026-07-10

Primera release formal de GitHub. Consolida el endurecimiento fiscal,
multiemisor y operativo posterior al piloto productivo. El contenido técnico de
la actualización depende del commit de origen: el despliegue realizado desde una
instalación anterior incluyó la migración `f7a8b9c0d1e2`, cambios de dependencias
y ajustes del compose productivo.

### Seguridad y confiabilidad fiscal

- La emisión individual bloquea confirmaciones sin numeración ARCA disponible,
  descarta fechas de servicio que no aplican y evita conservar un `cliente_id`
  después de editar manualmente el receptor.
- WSFE rechaza respuestas parciales o ambiguas y consulta el número de
  comprobante sin evaluar fallbacks ausentes.
- Los errores inesperados de emisión ya no exponen detalles internos; los
  fallos post-CAE preservan el estado de reconciliación.
- El transporte SOAP aplica timeout por operación, ejecuta Zeep fuera del event
  loop y conserva compatibilidad con el rango AnyIO admitido por Starlette.
- La API no encola lotes si el worker embebido no está disponible; producción
  mantiene un único proceso Uvicorn mientras ese worker siga embebido.

### Aislamiento multiemisor

- Certificados y puntos de venta cancelan acciones o respuestas obsoletas al
  cambiar el emisor activo.
- El store de puntos de venta no permite que una respuesta tardía reemplace la
  lista del nuevo emisor, incluso con identificadores coincidentes.
- La edición de emisores queda reservada a administradores y la interfaz de
  usuarios comunes permanece en modo lectura.

### Validación del corte

- Backend: 411 tests aprobados y 1 omitido según su marca preexistente.
- Frontend: 111 tests aprobados; ESLint, type-check y build limpios.
- `autoreview` acumulado con GPT-5.5 en `high` sin hallazgos accionables.
- Clawpatch revalidó como `fixed` los 3 findings backend y 9 frontend objetivo.
- GitHub Actions aprobó el commit de release `8099b22` con los jobs de seguridad,
  frontend, backend y E2E completos.

### Despliegue productivo

- Producción se actualizó al tag `v0.2.1`, commit
  `8099b223f3be7342dbb29367d24c6209dee93a58`.
- El backup previo quedó validado mediante una restauración aislada antes de
  reabrir el servicio.
- Alembic aplicó y verificó la migración `f7a8b9c0d1e2`: la relación de usuarios
  usa `SET NULL` y las entidades con historial fiscal u operativo usan
  `RESTRICT` ante el borrado de un emisor.
- La comprobación posterior confirmó `current` y `heads` alineados, conteos
  coincidentes en 40 tablas públicas, base y logs sanos, un único proceso
  Uvicorn, worker de lotes activo y ausencia de operaciones fiscales en curso.
- Los smoke checks públicos e internos, login, PDF sintético y servicios vecinos
  quedaron sanos.
- La validación manual autenticada se completó con emisión fiscal real
  satisfactoria. La evidencia y los datos fiscales permanecen en el entorno
  operativo privado.
- Con estas verificaciones, `v0.2.1` queda aceptada como despliegue productivo
  satisfactorio.

### Auditoría y mantenimiento

- La auditoría documental del 2026-07-06 alineó README, manual de usuario,
  referencia API, guías de certificados, notas ARCA y documentos históricos con
  las reglas vigentes de ese corte, sin modificar `VISION.md`.
- Se cerró la auditoría Clawpatch de backend, frontend y repo completo del
  2026-07-05 con `openFindings=0` en los tres state dirs existentes.
- Se corrigió la puesta a punto del mapper repo para usar la CLI global
  `clawpatch` sin fijar versión y conservar el mapeo nativo junto con las
  features manuales versionadas.
- Se corrigió la previsualización de PDFs para no revocar el `blob:` antes de
  que la pestaña nueva cargue el visor; se evita usar `pagehide`/`unload` en la
  navegación inicial de `about:blank` al `blob:`.
- Se aclaró el workflow CI: los E2E corren en pushes a `main` y en PRs.
- Se reforzó `formatearFecha` para soportar y validar `DD/MM/AAAA`, además de
  formatos técnicos `YYYY-MM-DD` e ISO datetime, sin normalizar fechas inválidas
  como `31/02/2026`.
- Se documentaron reglas permanentes de fechas argentinas en `AGENTS.md`,
  `docs/agents/testing.md` y `CONTRIBUTING.md`.
- Cierre detallado y lecciones operativas:
  `docs/project/audits/clawpatch/2026-07-05-cierre-auditoria.md`.
- Validaciones: tests frontend enfocados y completos, Clawpatch revalidate,
  `autoreview` Codex/GPT-5.5 alto por commit y GitHub Actions remoto aprobado.

### UX de carga masiva

- Se implementó el Corte 1 del rediseño de `/comprobantes/lotes`: guía rápida
  compacta con detalle desplegable, checklist dinámico de requisitos y acción
  `Validar lote` al cierre de la configuración fiscal.
- Se implementó el Corte 2 del rediseño de `/comprobantes/lotes`: el lote
  activo prioriza totales, avance y siguiente acción; el resumen operativo y el
  detalle de comprobantes pasan a secciones plegables. Las acciones sobre
  comprobantes visibles quedan habilitadas solo con el detalle abierto.
- Se implementó el Corte 3 del rediseño de `/comprobantes/lotes`: `Resolver
pendientes` pasa a ser un modo desplegable que agrupa reintento de fallidos,
  descarte de visibles y reconciliación ARCA Web para casos excepcionales.
- Se implementó el Corte 4 del rediseño de `/comprobantes/lotes`: `Lotes
recientes` queda como navegación compacta con estado, fecha, métrica principal
  y lote activo resaltado.
- Los cambios son frontend-only y mantienen intactos backend, ARCA, emisión,
  servicios, stores, rutas, payloads y contratos.
- Validaciones: `git diff --check`, test unitario enfocado de
  `LotesComprobantesView`, `npm run lint:check`, `npm run type-check`,
  `npm run build`, `npm run test:unit`, E2E Chromium y smoke visual con API
  mockeada sin llamadas ARCA.

### Observabilidad operativa

- Se agregó QA local del gestor de almacenamiento: E2E permanente con API
  mockeada y datos ficticios, más smoke visual privado para métricas,
  categorías, emisores, resguardo ZIP y confirmación `Ya lo descargué`, sin
  datos reales ni llamadas ARCA. La validación VPS con datos de prueba
  controlados sigue pendiente.
- Se agregó una guía rápida de soporte en `Sistema > Estado` con próximos pasos
  seguros para aplicación/base no disponible, ARCA/certificado con error, lotes
  detenidos o inciertos y almacenamiento/backup pendiente.
- Se agregó `Ficha para soporte` en `Sistema > Estado` con datos mínimos para
  diagnosticar incidentes sin copiar CUIT completo ni evidencia privada en
  documentación pública.
- Se agregó `docs/agents/support-runbook.md` como primer runbook público y
  sanitizado de diagnóstico operativo, sin datos privados ni comandos concretos
  de VPS.
- Se agregó el primer corte de `Sistema > Estado` para administradores, con
  señales de API, base de datos, certificado local del emisor activo,
  almacenamiento y prueba ARCA manual.
- La pantalla no llama a ARCA automáticamente al cargar; la conexión externa
  queda detrás de la acción explícita `Probar conexión`.
- Quedan pendientes healthcheck dedicado de worker, evidencia automática de
  backup y trazabilidad histórica más completa.

### Checkpoint visual v01

- Se cerró el checkpoint visual v01 del frontend público para instalación
  productiva controlada, con identidad aplicada en shell común, componentes
  base/comunes, login/setup, dashboard, clientes, usuarios, reportes y
  certificados/listado/wizard.
- Se agregaron tokens suaves de estado y se eliminó deuda visual residual del
  alcance, sin modificar backend, ARCA, emisión individual o masiva, lotes
  fiscales, servicios, stores, rutas ni contratos.
- Validaciones de cierre: `git diff --check`, `npm run lint:check`,
  `npm run type-check`, `npm run build`, `npm run test:unit` (63 tests) y
  `npm run test:e2e -- --reporter=list` (31 tests en Chromium desktop).
- Este hito no implica despliegue automático ni distribución comercial; la
  instalación productiva debe hacerse de forma explícita contra un commit o tag
  identificable.

## [0.2.0-mvp] - 2026-05-22

Línea base histórica al 2026-05-22. Este corte reemplaza las referencias
antiguas a versiones previas como fuente de estado operativo.

### Estado del corte

- Versión visible del producto: `0.2.0-mvp`.
- Versión técnica npm/backend: `0.2.0` cuando la herramienta exige semver.
- MVP validado en homologación y usado en producción real controlada.
- La evidencia productiva detallada queda en bases, logs y archivos privados
  ignorados por Git.
- La documentación viva queda alineada con estado post-piloto productivo.

### Decisiones de producto vigentes

- FactuFlow es una herramienta para facturar.
- No se planifica incorporar cuentas corrientes, stock ni catálogos.
- Las integraciones externas quedan como evolución futura, enfocadas en entrada
  y salida de datos mediante la API, después de estabilizar facturación.
- El modelo operativo es multiemisor con un emisor activo explícito por vez,
  pensado para contadores independientes y estudios chicos.
- No se avanza por ahora hacia plataforma multiempresa compleja con permisos
  finos, reportes globales u operación simultánea entre emisores.
- El uso local con launcher queda como entorno implementado para desarrollo/QA.
- El siguiente hito de despliegue es VPS con Docker producción y PostgreSQL.
- La distribución comercial instalable queda para después de estabilizar VPS.
- La observabilidad operativa estándar es requisito antes de ampliar producción:
  trazabilidad, estado del sistema, logs útiles, backups y mensajes simples para
  usuarios no técnicos.

### Capacidades consolidadas

- Backend FastAPI con auth, empresas, clientes, certificados, puntos de venta,
  comprobantes, lotes, PDFs y reportes.
- Frontend Vue con dashboard, clientes, comprobantes, emisión masiva, reportes,
  certificados, puntos de venta y emisores.
- Emisión individual y masiva con ARCA WSAA/WSFEv1.
- Confirmación fiscal explícita antes de solicitar CAE.
- Fecha de emisión explícita; no se usa la fecha del día como default fiscal.
- Formatos configurables de importación y perfiles de carga por emisor.
- Lotes con validación previa, estados persistidos y worker para procesos
  largos.
- Selector de emisor activo y scoping por emisor en operaciones sensibles.
- PDFs bajo demanda y reportes básicos.
- Launcher local Windows con ícono en tray para desarrollo/QA.

### Seguridad y operación

- Clientes, certificados, puntos de venta, comprobantes, lotes, PDFs, reportes,
  perfiles y formatos deben quedar aislados por emisor activo.
- Para producción usar PostgreSQL y `docker-compose.prod.yml`.
- Queda pendiente resolver si los certificados productivos locales se migran al
  VPS o si conviene generar certificados nuevos para el servidor.
- Backups/restauración, trazabilidad visible, logs de soporte y pantalla de
  estado del sistema son prioridad post-piloto.

### Próximo tramo

- Instalar y validar FactuFlow en VPS con Docker producción y PostgreSQL.
- Resolver la política técnica de certificados ARCA en VPS.
- Implementar observabilidad operativa estándar.
- Formalizar backup/restauración de base, certificados, configuración y logs.
- Agregar descarga masiva de PDFs en ZIP.
- Recuperar E2E como evidencia confiable.
- Definir política de releases posterior a `0.2.0-mvp`.

## Historial resumido anterior al corte

### Base inicial

- Se construyo la base técnica con FastAPI, Vue, Pinia, Router, SQLAlchemy,
  Pydantic, autenticación, setup inicial y estructura modular.
- Se incorporaron empresas, clientes, puntos de venta, certificados,
  comprobantes, PDFs y reportes.
- Se documento la primera visión de FactuFlow como sistema de facturación
  electrónica ARCA para Argentina.

### Integración ARCA y comprobantes

- Se implemento WSAA y WSFEv1.
- Se agregaron certificados por ambiente, wizard de carga/verificación y
  validaciones de autorización `wsfe`.
- Se completo emisión individual, vista previa, guardado de comprobantes,
  consulta posterior y generación de PDFs.
- Se corrigieron reglas fiscales críticas: fecha fiscal explícita, concepto
  fiscal ARCA explícito, punto de venta usable y confirmación irreversible.

### Emisión masiva

- Se implemento emisión por Excel con agrupacion por `comprobante_ref`.
- Se agregaron validaciones de totales, IVA, consumidor final, puntos de venta
  y conceptos fiscales.
- Se agregaron formatos de importación configurables y perfiles por emisor para
  facilitar archivos externos.
- Se incorporaron estados de lotes, worker para procesos largos, idempotencia y
  manejo de casos con incertidumbre post-ARCA.

### Producción real y endurecimiento

- Se verificó homologación y luego se operó producción real controlada.
- Se ajustó numeración, locking, idempotencia, reconciliación y scoping por
  emisor.
- Se agregó launcher local Windows para desarrollo/QA y mejores mensajes cuando
  el backend local no está disponible.
- Se reforzo la seguridad documental: no versionar datos privados, CAEs,
  CUITs, clientes, Excels, PDFs, logs ni evidencia local.

### Documentación

- Se separó documentación viva de documentos históricos.
- `README.md`, `ROADMAP.md`, `docs/agents/current-status.md`,
  `docs/agents/manual-qa.md`, `docs/user-guide/README.md` y este changelog
  pasan a ser la base para retomar el proyecto.
- Los snapshots antiguos conservados en `docs/project/**` quedan solo como
  referencia histórica y pueden resumirse o eliminarse en futuras limpiezas si
  su contenido ya está cubierto por este changelog y la documentación viva.
