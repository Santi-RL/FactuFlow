# Integración ARCA

Última revisión: 31/08/2026

## Nomenclatura

- ARCA es el nombre actual y debe usarse en UI, documentación nueva y textos de soporte.
- AFIP sigue apareciendo en URLs oficiales y nombres legacy por compatibilidad técnica.

## Módulos relevantes

- `backend/app/arca/wsaa.py`: autenticación WSAA
- `backend/app/arca/wsfev1.py`: integración WSFEv1
- `backend/app/arca/crypto.py`: firmado y utilidades criptográficas
- `backend/app/arca/cache.py`: cache de tickets WSAA
- `backend/app/arca/models.py`: modelos de request/response
- `backend/app/services/facturacion_service.py`: orquestación de emisión real
- `backend/app/services/elegibilidad_rece_service.py`: autoridad RECE durable,
  snapshots WSFE y guarda fail-closed
- `backend/app/api/arca.py`: endpoints HTTP vinculados a ARCA

## Endpoints oficiales

- WSAA homologación: `https://wsaahomo.afip.gov.ar/ws/services/LoginCms?wsdl`
- WSAA producción: `https://wsaa.afip.gov.ar/ws/services/LoginCms?wsdl`
- WSFEv1 homologación: `https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL`
- WSFEv1 producción: `https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL`

## Variables de entorno reales del proyecto

- `ARCA_ENV`: enum estricto; solo `homologacion` o `produccion`. `AFIP_ENV` es
  el alias legacy y `ARCA_ENV` tiene precedencia. Si ambos faltan usa
  `homologacion`; un valor presente vacío o inválido impide iniciar.
- `CERTS_PATH`: base path de certificados
- `CERTIFICATE_MAX_UPLOAD_BYTES`: tamaño máximo para subir certificados antes
  de persistirlos
- `ARCA_PRIVATE_KEY_PASSWORD`: contraseña local para cifrar claves privadas
  nuevas. Si no se define, se usa `APP_SECRET_KEY`.
- `ARCA_TOKEN_CACHE_PATH`: cache persistente de tickets WSAA
- `ARCA_FECAESOLICITAR_BATCH_ENABLED`: habilita emisión de lotes WSFE por
  sublotes cuando ARCA informa `RegXReq`.
- `ARCA_FECAESOLICITAR_BATCH_MAX_REGISTROS`: límite operativo opcional. `0`
  significa usar el `RegXReq` completo informado por ARCA.
- En producción, usar PostgreSQL y `docker-compose.prod.yml`; no usar SQLite ni defaults de desarrollo.
- Compatibilidad legacy:
  - `AFIP_ENV`
  - `AFIP_CERTS_PATH`

## Hallazgos importantes de homologación

### Certificados y WSASS

- En homologación se trabajo con WSASS.
- El certificado se emitió para el CUIT del titular del certificado y luego se autorizo el servicio `wsfe` para el CUIT representado.
- Flujo confirmado:
  1. Adherir `WSASS - Autogestion Certificados Homologacion`
  2. Generar CSR con el CUIT del titular del certificado
  3. Crear DN/certificado en WSASS
  4. Crear autorización al servicio `wsfe` para el CUIT representado

### Certificados en producción

- En producción no alcanza con cargar el certificado emitido por ARCA.
- Después de generar el certificado en `Administración de Certificados Digitales`,
  el administrador/representante debe asociar el alias del computador al servicio
  `wsfe` desde `Administrador de Relaciones de Clave Fiscal`.
- Si falta esa autorización, WSAA responde `Computador no autorizado a acceder
  al servicio`, aunque el certificado y la clave privada coincidan.
- El wizard de FactuFlow tiene un paso previo a `Probar conexión` para confirmar
  esta asociación.
- Antes de mover la operación a VPS, usar el runbook
  `docs/setup/vps-migration.md`. La decisión operativa vigente es migrar
  certificados productivos activos solo si todos tienen `.crt` y `.key`
  resolubles dentro de `CERTS_PATH`; el preflight bloquea certificados activos
  incompletos.
- La exportación re-cifra las claves privadas activas con una nueva contraseña
  destino. Esa contraseña debe quedar como `ARCA_PRIVATE_KEY_PASSWORD` en
  `.env.production` durante la importación y operación del VPS.
- Si se necesita operar local y VPS simultáneamente, no reutilizar el mismo
  certificado productivo: generar certificados separados.

### Estado productivo real

- Al 2026-05-22, FactuFlow ya fue usado en producción real con comprobantes
  autorizados. La evidencia detallada queda en base/logs/archivos privados y no
  debe copiarse a documentación versionada.
- La regla vigente ya no es preparar "el primer CAE real", sino validar cada
  nueva emisión productiva con punto de venta, fecha fiscal, concepto fiscal
  ARCA, descripción facturada, totales, backup/logs y confirmación irreversible.

### Errores inesperados de emisión

- El endpoint de emisión no debe devolver el texto de excepciones inesperadas:
  puede contener credenciales, URLs internas o rutas de certificados.
- El detalle y el traceback quedan en logs privados. El endpoint y las
  respuestas de servicio individuales, batch, pre-ARCA y post-CAE usan un
  mensaje genérico y no habilitan un reintento automático.
- Antes de reintentar, revisar la operación idempotente y los intentos fiscales
  para determinar si ARCA pudo haber autorizado el comprobante.

### CUIT operativo para WSFE

- En el runtime del proyecto no debe reutilizarse automáticamente el `cuit` del certificado para operar WSFE.
- El flujo correcto validado hoy es:
  - resolver certificado activo
  - autenticar WSAA para la empresa activa representada
  - construir `WSFEv1Client` con el CUIT de la empresa activa
- Este ajuste fue necesario para corregir `GET /api/arca/puntos-venta`, que fallaba aunque la emisión real funcionaba.
- Antes de solicitar CAE, `FacturacionService` debe validar que el punto de
  venta y el `cliente_id` opcional pertenezcan a la empresa activa. Si no
  coinciden, la emisión se rechaza localmente y no se llama a WSFE.

### Cache WSAA y rotación de certificados

- El cache persistente de tickets WSAA se guarda en `ARCA_TOKEN_CACHE_PATH`, pero
  cada entrada queda scopiada por servicio, CUIT representado, ambiente y huella
  SHA-256 del certificado público que generó el Token/Sign.
- `Probar conexión` puede forzar un login WSAA para el certificado seleccionado;
  ese ticket no debe ser reutilizable por el certificado activo si el material
  del certificado es distinto. La UI bloquea reintentos mientras una
  verificación sigue pendiente para evitar llamadas concurrentes y respuestas
  fuera de orden.
- Al renovar certificados para el mismo emisor y ambiente, el certificado nuevo
  obtiene o reutiliza solo tickets asociados a su propia huella. Esto evita
  operar WSFE con credenciales cacheadas de un certificado anterior o no activo.

### Paths legacy de certificados

- La base local puede contener valores legacy como `certs/archivo.crt`.
- El proyecto ahora resuelve correctamente:
  - paths absolutos dentro de `CERTS_PATH`
  - filenames simples
  - valores legacy con prefijo `certs/`
- Los paths que resuelven fuera de `CERTS_PATH` se rechazan. El upload de
  certificados solo acepta nombres de clave generados por FactuFlow para el
  CUIT y ambiente del emisor activo.
- El archivo público del certificado se lee con límite y se rechaza si supera
  `CERTIFICATE_MAX_UPLOAD_BYTES`, antes de persistir un `.crt` nuevo.
- Las claves privadas nuevas se guardan cifradas y se crean con permisos
  restrictivos desde la apertura del archivo. Las claves legacy sin cifrar
  siguen pudiendo leerse para no romper certificados existentes, pero no se
  generan claves nuevas sin cifrado salvo que no exista ninguna contraseña de
  aplicación configurada.
- Este fix fue necesario para que `Nueva factura` volviera a obtener el próximo número desde homologación.

### Puntos de venta

- **Contrato PF-19D:** `FEParamGetPtosVenta`, consultado con las credenciales del
  emisor activo, es la autoridad para descubrir puntos y clasificar las
  modalidades explícitas `CAE - …` compatibles con el flujo implementado.
  Número, tipo de emisión, presencia, bloqueo y baja no se editan manualmente.
- No se detectó una pantalla separada en el portal que diga "homologación" para los puntos de venta de WSFEv1.
- En la práctica se revisa la misma pantalla `A/B/M de puntos de venta / emisión`.
- La autoridad se registra en el ledger PF-19B como evidencia
  `wsfe_param_get_ptos_venta_v1`, separada por ambiente y vinculada a la revisión
  fiscal del punto. PF-19A conserva sus denegaciones adicionales.
- `FEParamGetPtosVenta` devuelve el indicador `Bloqueado` como `N`/`S`; en
  validaciones de emisión debe normalizarse explícitamente. `N` significa no
  bloqueado y debe tratarse como punto habilitado. No evaluar ese campo como
  booleano directo. La evidencia productiva detallada, incluidos
  identificadores, conteos y numeración, permanece en el entorno operativo
  privado; este documento conserva únicamente la invariante técnica validada.
- `FEParamGetPtosVenta` no devuelve domicilio ni nombre de fantasía. Esos datos se
  importan desde la constancia PDF de `Administración de Puntos de Venta y
  Domicilios`.
- `GET /api/arca/status` informa el ambiente ARCA actual, conserva
  `certificado_activo` para indicar que existe el registro del ambiente y
  expone `certificado_disponible` solo cuando el `.crt` y la `.key` resuelven
  dentro de `CERTS_PATH` y existen como archivos. No llama a ARCA ni consume
  numeración. Puntos de venta y Estado del sistema usan la disponibilidad real;
  cualquier operación WSFE repite la comprobación antes de WSAA.
- Si falta material local, el backend registra las rutas solo en logs privados
  y devuelve un mensaje genérico al cliente.
- Certificados y puntos de venta solo consultan estado ARCA cuando existe un
  emisor confirmado para la pestaña. Un cambio de emisor cierra acciones
  pendientes e invalida resultados tardíos antes de actualizar la UI.
- La sincronización server-side valida primero el snapshot completo. Después
  crea o actualiza presentes, invalida ausentes y mueve las cabezas del ambiente
  en una única transacción con una marca temporal común. Un conjunto vacío,
  duplicado, inconsistente, sin `EmisionTipo` o un timeout produce `503` y no
  modifica ningún punto.
- Los puntos CAE compatibles nuevos quedan `usar_en_factuflow=true` aun cuando
  estén bloqueados o dados de baja temporalmente. Los de otras modalidades se
  conservan como información con uso deshabilitado. Una ausencia no borra la
  preferencia, y un regreso posterior no revierte una deshabilitación explícita.
- PF-19A contiene antes de `FECAESolicitar` cada tupla explícitamente declarada
  por ambiente, emisor, punto y tipo. La coincidencia usa tanto la identidad
  local como el número fiscal para que renumerar o recrear el punto no evite el
  bloqueo. La lista vacía no acredita elegibilidad.
- Sólo `verificado_rece` efectivo para el ambiente actual, estado técnico
  positivo, comprobación menor a 90 días y `usar_en_factuflow=true` habilitan
  `seleccionable_para_emision`. La misma regla se consume en individual,
  perfiles, lotes, worker, reintentos y continuaciones.
- Una actualización de preferencia incrementa la revisión fiscal y rechaza una
  guarda activa. Replays terminales y estados inciertos conservan su snapshot;
  nunca se reevalúan contra una preferencia posterior.
- La constancia PDF es opcional y descriptiva. Puede completar domicilio y
  nombre de fantasía o crear filas informativas de otros sistemas, pero no llama
  a WSFE, no acredita elegibilidad, no invalida ausentes y no se conserva. Una
  constancia posterior sobrescribe únicamente los campos descriptivos presentes
  y registra procedencia `constancia_arca`.
- A los 90 días se ejecuta un único preflight agrupado por emisor antes de crear
  estado fiscal. Una falla devuelve `503` sin operación, intento, reserva ni
  solicitud CAE. La guarda final inmediatamente anterior a ARCA permanece.
- Homologación y producción reciben evidencia WSFE independiente; ninguna cabeza
  positiva de un ambiente se reutiliza en el otro. La API conserva campos legacy
  por compatibilidad y los selectores usan `seleccionable_para_emision`.
- Al cambiar de emisor, Lotes invalida generaciones y vacía formatos, perfiles y
  puntos antes del primer `await`. Sus tres loaders capturan `empresa_id` y una
  generación propia, descartan éxito/error obsoleto y la cadena revalida el
  emisor después de cada espera antes de iniciar la siguiente carga;
  `loadingPerfiles` también queda protegido. EmpresaConfig conserva la limpieza
  de perfiles, formatos, puntos y catálogo y la misma guarda sobre su loader
  agregado. Los `finally` obsoletos no apagan la solicitud vigente. Las requests
  HTTP anteriores pueden completar y simplemente se ignoran.
- PF-19A no reetiqueta `10005` legacy como rechazo terminal: el código no quedó
  persistido de forma estructurada y su firma textual solo identifica
  candidatos de inventario. PF-19C, ya integrado en `main`, completa esa
  transición;
  timeout, respuesta parcial y código desconocido continúan en reconciliación.
- La constancia permite ver también puntos de otros sistemas como Factuweb,
  Comprobantes en Línea y Controlador Fiscal; deben mostrarse pero no tratarse
  como usables para FactuFlow si no son Web Services.
- Si al importar una constancia falla la consulta técnica `FEParamGetPtosVenta`,
  no se debe inventar estado ARCA activo: los puntos existentes conservan
  `bloqueado`, `fecha_baja` y `activo`; los puntos nuevos quedan inactivos hasta
  sincronizar con ARCA o revisarlos manualmente.
- La disponibilidad de este contrato en una instalación concreta se comprueba
  exclusivamente en su plano de control; no se infiere desde `main` o una
  release.

### Constancias de emisores

- El alta de emisores soporta constancias de inscripción de persona jurídica,
  constancias de inscripción de persona física y constancias de opción de
  Monotributo.
- El parser debe validar provincia contra el catálogo argentino antes de
  completar el formulario. Líneas técnicas como `IMPUESTOS/REGIMENES`,
  `ACTIVIDADES`, vigencia, URLs o footers no deben usarse como domicilio,
  localidad ni provincia.
- Los cortes de texto introducidos por el PDF deben sanearse solo por campo,
  por ejemplo nombres, localidades y numeración de domicilio.

### TLS en endpoints legacy

- El WSDL productivo de WSFEv1 puede fallar en Python/OpenSSL moderno con
  `DH_KEY_TOO_SMALL`.
- El cliente SOAP usa un transporte propio con `DEFAULT:@SECLEVEL=1`, limitado
  a llamadas ARCA, para mantener compatibilidad con esos endpoints.
- El timeout de transporte cubre tanto la carga del WSDL como cada operación
  SOAP. Las operaciones Zeep de WSAA y WSFEv1 se ejecutan fuera del event loop
  para no bloquear otras requests de FastAPI.
- El offload usa la firma básica de `to_thread.run_sync`, compatible con el rango
  `anyio>=3.6.2,<5` permitido por Starlette.
- El thread no se abandona si se cancela la espera. Un timeout o corte durante
  `FECAESolicitar` sigue siendo un resultado potencialmente incierto: no se
  reintenta automáticamente y se revisan intento fiscal, idempotencia y ARCA.

### Verificación de comprobantes

- La forma confiable de verificar comprobantes de homologación es `FECompConsultar`.
- La consulta usa `CbteNro` cuando ARCA lo devuelve y solo recurre a
  `CbteDesde` si el primero está ausente. Si faltan ambos, debe fallar
  explícitamente en vez de inventar o perder el número.
- El QR sirve para comprobantes reales, pero no se tomó como mecanismo de validación de homologación.
- El QR del PDF se arma según la especificación ARCA con una URL
  `https://www.afip.gob.ar/fe/qr/?p={base64}`. El payload testeado incluye
  `ver`, `fecha`, `cuit`, `ptoVta`, `tipoCmp`, `nroCmp`, `importe`, `moneda`,
  `ctz`, `tipoDocRec`, `nroDocRec`, `tipoCodAut` y `codAut`.

### CAE, idempotencia e intentos fiscales

PF-19C congela el tratamiento del rechazo global: solo `10005` como entero
exacto, único, con cabecera `R` correlacionada al request y sin detalles ni CAE,
es `arca_rechazo_global_excluyente`. No se interpreta texto libre ni el ejemplo
documental `1005`. Respuesta desconocida, mixta, parcial, con timeout, transporte
o contradicción queda en `requiere_reconciliacion`; el replay no vuelve a WSAA,
WSFE ni `FECAESolicitar`. En lote se cierra el sublote enviado y se detienen los
remanentes como no enviados, sin afirmar que ARCA los rechazó.

Los candidatos legacy se resuelven solo mediante la CLI privada PF-19C en fases
`plan` read-only y `apply` auditado. El plan fija ambientes por evidencia; si el
ambiente histórico es indeterminado consulta producción y homologación. `apply`
usa `FECompUltimoAutorizado` y solo `FECompConsultar` si el último alcanza el
número planificado. Autorización, fallo o duda conserva reconciliación. La
migración `c0d1e2f3a4b` guarda el cierre en journal append-only hasheado; el
paquete VPS valida y omite esa evidencia terminal, sin recrearla. La evidencia
de CI y del ensayo privado de
backup/restauración/upgrade/rollback se conserva en el dossier de `v0.3.0`, no
en este contrato vivo.

PF-01A.1 valida en el cliente WSFE que
`Resultado=A` incluya un CAE ASCII de 14 dígitos y un vencimiento calendario
válido `YYYYMMDD`. Rechaza `P`, resultados desconocidos, errores globales y
cardinalidades o rangos ambiguos; un `R` completo se conserva como rechazo
verificable. PF-01A.2 transforma toda excepción inesperada post-ARCA en una
respuesta sanitizada `requiere_reconciliacion`, individual o batch, actualiza los
intentos y persiste el `409` idempotente cuando la base lo permite. PF-01A.3
agrega en emisión individual el estado visual bloqueante: snapshot y clave quedan
congelados en memoria, `Verificar estado` repite la operación exacta y solo una
autorización o rechazo final desbloquea. No persiste payload fiscal en storage
web; una recarga forzada exige revisar el backend, no crear otra emisión. Diseño:
`docs/agents/pf-01-authorization-integrity-design.md`.

- El CAE es la prueba de autorización fiscal devuelta por ARCA. No es la llave
  primaria de idempotencia: FactuFlow no puede esperar a tener CAE para decidir
  si una operación se repite, porque el riesgo crítico ocurre precisamente
  durante o después de solicitarlo.
- La idempotencia de request se controla con `X-Idempotency-Key`, emisor activo,
  tipo de operación y hash estable del payload fiscal. La confirmación de
  duplicado lógico no forma parte de ese hash para permitir continuar la misma
  operación después de una advertencia.
- Antes de llamar a `FECAESolicitar`, FactuFlow debe persistir una
  `operaciones_idempotentes` y uno o más `intentos_emision_fiscal`, con número
  planificado, punto de venta, tipo, fecha fiscal, total y receptor normalizado.
- Pre-ARCA solo se responde `503` con `Retry-After: 2` cuando FactuFlow confirmó
  durablemente recuperación segura y cero intentos. La operación pasa
  `en_proceso -> interrumpida_pre_arca`; un replay con la misma clave hace CAS a
  `en_proceso`, con un único ganador.
- Individual, lote síncrono y reintento sin intentos restauran el lote a
  `validado` o el grupo exacto a `fallido`. Con intento existente o recuperación
  no persistible se responde `409 pre_arca_estado_bloqueado`, conservando la
  clave y sin afirmar reconciliación ARCA porque FECAE no comenzó.
- El worker pre-ARCA solo devuelve el lote a `en_cola` sin intentos, conserva la
  operación `en_proceso` e impide replay HTTP paralelo. Post-ARCA conserva `409`,
  reconciliación y ausencia de retry. `IntegrityError` no cambia.
- `get_db` preserva la excepción primaria aunque fallen `rollback` o `close`; un
  `409` post-ARCA no se degrada a `503` por cleanup.
- PF-01B.2 agrega en persistencia vocabularios cerrados para estados de intentos
  y comprobantes. Los estados `en_proceso`, `requiere_reconciliacion` y
  `autorizado` conservan la reserva parcial; `rechazado_arca` y
  `fallido_verificado` la liberan.
- Un comprobante `autorizado` exige CAE de 14 caracteres y vencimiento; cualquier
  otro estado exige ambos campos nulos. La migración aborta con conteos
  sanitizados ante datos legacy ambiguos y nunca los normaliza. PF-01B.3 validó
  la misma semántica, incluida la concurrencia, en PostgreSQL 16 efímero.
  Clawpatch revalidó B10/B17 como `fixed`; PF-01 quedó cerrado.
- La variante individual de `FECAESolicitar` solo puede continuar cuando el
  detalle tiene `Resultado=A`. Estados parciales `P`, rechazados `R` o
  cualquier valor no aprobado deben generar error y no tratarse como CAE válido.
- Si ARCA devuelve CAE y el comprobante se guarda correctamente, el intento
  queda `autorizado` y vinculado al comprobante local.
- Si ARCA devuelve CAE pero falla la persistencia local, el intento, grupo o
  lote debe quedar `requiere_reconciliacion`. No se debe reintentar con otra
  clave ni volver a solicitar CAE hasta consultar ARCA.
- Si ARCA rechaza sin CAE, el intento queda como rechazo verificado y no debe
  reservar numeración futura.
- Si un intento queda `en_proceso` y supera la ventana
  `FISCAL_ATTEMPT_STALE_MINUTES`, FactuFlow debe consultar `FECompConsultar`
  por tipo, punto de venta y número planificado antes de liberar la numeración.
  Si ARCA confirma CAE, se vincula o reconstruye el comprobante cuando existen
  datos locales suficientes; si no, queda `requiere_reconciliacion`.
- Si `FECompConsultar` confirma explícitamente que el comprobante no existe,
  recién entonces se marca el intento como `fallido_verificado` y se libera la
  numeración.
- En emisión masiva, un lote `procesando` que supera
  `BATCH_PROCESSING_STALE_MINUTES` no debe reanudarse automáticamente para
  solicitar CAE. El worker solo puede vincular comprobantes locales ya
  autorizados sin llamar a ARCA si existe un intento fiscal `autorizado` del
  mismo lote y grupo, con `comprobante_id`, número planificado, CAE, fecha,
  receptor y total coherentes. Un comprobante local parecido pero sin ese
  intento fuerte no cierra automáticamente el grupo. Si quedan pendientes, solo
  puede reencolarlos si están intactos, sin intento fiscal, CAE, número,
  comprobante vinculado ni comprobante local autorizado candidato, y si
  la comparación con `FECompUltimoAutorizado` produce un diagnóstico `alineada`
  o `arca_adelantada` por emisor, punto de venta y tipo, sin incertidumbre propia.
  La recuperación no asigna número ni crea reserva; el procesamiento normal
  vuelve a diagnosticar y conserva el segundo preflight. Si queda cualquier
  incertidumbre, debe marcar el lote
  `requiere_reconciliacion`, registrar `bloqueo_operativo_no_reemitir`, marcar
  solo los grupos con evidencia fiscal como `requiere_reconciliacion` y exigir
  auditoría antes de continuar.

### PF-02A/PF-02B: numeración individual, batch, reintentos y stale con historia externa

- `FECompUltimoAutorizado` es la fuente del siguiente número fiscal global para
  el emisor, punto de venta y tipo. Una historia ARCA posterior a la local se
  clasifica `arca_adelantada`; se informa y la emisión individual o el núcleo
  batch usan `ultimo_arca + 1` si no existe un intento propio bloqueante.
- Una numeración local posterior se clasifica `local_adelantada`, no ofrece
  candidato y bloquea. Los intentos propios `en_proceso` o
  `requiere_reconciliacion` conservan prioridad sobre cualquier diagnóstico.
- Después de crear la reserva individual o todas las reservas del rango batch,
  FactuFlow repite
  `FECompUltimoAutorizado` inmediatamente antes de `FECAESolicitar`. Si el
  siguiente número ya no coincide, responde
  `numeracion_arca_cambio_pre_arca`; si la consulta falla, responde
  `preflight_arca_no_disponible`.
- Ambos resultados son terminales y verificados antes de ARCA: no hay solicitud
  de CAE, el intento queda `fallido_verificado`, la operación idempotente queda
  `fallido` y el usuario debe actualizar la numeración y confirmar de nuevo con
  una clave nueva.
- Una excepción después de iniciar `FECAESolicitar` no usa estas categorías:
  mantiene `requiere_reconciliacion` y las reglas de PF-01.
- El procesamiento batch normal y el reintento manual aplican esta política. El
  reintento detiene la selección ante un bloqueo o aborto pre-ARCA; solo un
  rechazo ARCA explícito puede permitir continuar. Una respuesta ambigua o una
  falla local posterior a una autorización conocida conserva grupo, lote e
  intento como `requiere_reconciliacion`, hace rollback del comprobante
  incompleto y no toca los grupos posteriores.
- La recuperación stale del worker conserva una puerta estricta antes de
  reencolar y no libera intentos propios inciertos. Acepta `alineada` o
  `arca_adelantada` únicamente para grupos realmente intactos y deja la reserva
  y el segundo preflight al procesamiento normal. El valor de diagnóstico nunca
  se escribe en `numero_asignado` sin reserva, intento y resultado fiscal.
- Los errores del preflight stale se registran con traceback en logs privados;
  los metadatos visibles solo guardan categorías estables y sanitizadas.
- PF-02A no consulta ni importa comprobantes anteriores. Esa reconstrucción
  opcional corresponde a PF-05.

### PF-03A/PF-03B: contrato de entrada cerrado antes de ARCA

- `EmitirComprobanteRequest` rechaza toda clave superior desconocida con
  `422 extra_forbidden` antes de crear idempotencia, intentos o reservas y antes
  de cualquier `FECAESolicitar`.
- Una errata en moneda, cotización, guardado de cliente o confirmaciones no se
  ignora ni activa un valor predeterminado. El request completo se considera
  inválido.
- Los snapshots batch canónicos se persisten desde `model_dump(mode="json")` y
  continúan revalidándose en procesamiento, worker, reintento, stale y
  reconciliación.
- Un snapshot legacy o manipulado con una clave superior desconocida falla
  cerrado. No se elimina el campo porque podría representar una instrucción
  fiscal que FactuFlow no comprende; si existe evidencia de autorización, se
  preserva y no se habilita reemisión.
- PF-03B cierra también cada ítem: rechaza propiedades desconocidas, descuentos
  inválidos e importes no finitos o no calculables. La UI envía sólo los ocho
  campos del contrato de creación, sin `subtotal` ni IDs de respuesta.
- El cálculo fiscal conserva orden y redondeo; los snapshots válidos conservan
  contenido y hash. La importación y el resumen de lotes no convierten valores
  inválidos en cero ni generan totales parciales engañosos.
- No cambian el payload SOAP, la numeración, el segundo preflight ni los estados
  fiscales. Contrato y matriz: [`PF-03B`](pf-03b-items-importes-design.md).

### Reconciliación externa de lotes

- Si un comprobante pendiente de un lote fue emitido manualmente en ARCA Web, no
  alcanza con que el usuario cargue número o CAE: FactuFlow debe verificarlo con
  `FECompConsultar`.
- La reconciliación solo puede registrar el comprobante local cuando ARCA
  confirma:
  - CUIT del emisor activo
  - tipo de comprobante
  - punto de venta
  - número
  - tipo y número de documento del receptor
  - fecha fiscal
  - importe total
  - resultado autorizado y CAE
- Un comprobante externo verificado no puede cerrar más de un grupo del lote:
  `lotes_comprobantes_grupos.comprobante_id` tiene unicidad parcial cuando no es
  nulo.
- Los comprobantes reconciliados quedan con `origen_emision = arca_web` para
  distinguirlos de los emitidos por FactuFlow.
- Si el lote estaba en `requiere_reconciliacion` o un grupo quedó
  `reintentando` por un fallo post-ARCA, la acción correcta es consultar ARCA y
  reconciliar; no se debe reintentar el CAE.
- Un lote cerrado por reconciliación externa no debe marcarse como
  `completado`, porque ese estado queda reservado para comprobantes emitidos por
  FactuFlow.

### Particularidades observadas en homologación

- `FEParamGetPtosVenta` puede devolver error `602 - Sin Resultados` aun cuando `FECompUltimoAutorizado` y la emisión real funcionen.
- El código actual tolera ese caso solo en homologación y no bloquea la emisión si el resto de las validaciones da bien.
- En la QA del 2026-04-10 también se verificó que la sincronización de puntos de venta desde UI ya no usa el CUIT incorrecto.

### RG 5616 / Condición frente al IVA del receptor

- En homologación ARCA exigió `CondicionIVAReceptorId`.
- Mapping implementado:
  - `RI` -> `1`
  - `Monotributo` -> `6`
  - `Exento` -> `4`
  - `CF` -> `5`

### Consumidor final e identificacion del receptor

- La página pública de ARCA sobre comprobantes indica que, para receptor
  consumidor final, debe figurar la leyenda `A CONSUMIDOR FINAL`.
- También indica que la identificacion con CUIT/CUIL/CDI/DNI u otro documento es
  obligatoria cuando el importe de la operación es igual o superior a
  `$10.000.000`.
- FactuFlow aplica esto en emisión masiva para comprobantes B/C:
  - bajo ese umbral acepta documento y nombre vacíos desde Excel
  - normaliza a tipo documento `99`, número `0`, razón social
    `A CONSUMIDOR FINAL` y condición IVA `CF`
  - desde ese umbral exige documento
- Para comprobantes tipo A se mantiene obligatorio CUIT válido del receptor.

### Fecha de emisión y período de servicios

- FactuFlow no debe asumir que el comprobante se emite con la fecha del día.
- Esta regla aplica también a notas de crédito y notas de débito: nunca usar la
  fecha actual como default fiscal.
- `CbteFch` se arma desde `fecha_emision`, un dato obligatorio confirmado por
  el usuario o resuelto explícitamente desde el Excel.
- En comprobantes nuevos, `fecha_servicio_desde`, `fecha_servicio_hasta` y
  `fecha_vto_pago` se persisten junto al comprobante para poder reflejar en PDF
  el período facturado y el vencimiento usados al solicitar CAE.
- Cuando `concepto=1` (Productos), la emisión nueva no debe informar fechas de
  servicio. La UI las limpia al cambiar de concepto y el servicio backend
  rechaza una combinación inconsistente antes de llamar a ARCA.
- Antes de solicitar CAE debe existir una confirmación visible para el usuario:
  `Está seguro que quiere emitir comprobantes con fecha XX/XX/XX? Recuerde que luego no podrá emitir comprobantes con fecha anterior para ese mismo punto de venta.`
- La API debe rechazar emisiones sin confirmación fiscal explícita. En el
  contrato actual, emisión individual requiere `confirmacion_fecha_fiscal=true`
  y procesamiento de lotes requiere `X-Confirmacion-Fecha-Fiscal` con el token
  exacto `fechas=YYYY-MM-DD,...;puntos_venta=N,...`, recalculado desde los
  grupos validados.
- Si `FECAESolicitar` devuelve CAE y luego falla la persistencia local, la
  emisión debe quedar como `requiere_reconciliacion`, conservando punto de
  venta, número, fecha, total y CAE. No debe tratarse como error reintentable.
- En emisión masiva, antes de validar se debe elegir si la fecha de emisión sale
  del archivo o si se usa una fecha fija para todos los comprobantes.
- Un perfil de carga masiva puede precargar la fecha de emisión solo como
  archivo, manual o personalizada explícita. Las reglas relativas quedan para
  período de servicios o vencimiento cuando dependan de una fecha de emisión ya
  explícita. El backend de lotes sigue recibiendo `archivo` o `fija`; el perfil
  no puede emitir ni validar de forma silenciosa.
- Un perfil de carga masiva también puede precargar punto de venta. Las opciones
  válidas son usar el punto definido en el archivo o fijar uno con
  `seleccionable_para_emision=true`, incluido `verificado_rece` efectivo y
  `usar_en_factuflow=true`. El perfil no crea evidencia y el lote revalida su
  snapshot antes de emitir. Si ARCA no lo informa o su uso está deshabilitado en
  `Puntos de venta`, no se puede elegir como fijo.
- Para concepto servicios o productos y servicios, también deben resolverse
  `FchServDesde`, `FchServHasta` y `FchVtoPago`.
- La validación local aplica una ventana ARCA preventiva:
  - productos: fecha de emisión dentro de N-5 / N+5
  - servicios o productos y servicios: fecha de emisión dentro de N-10 / N+10
  - N es la fecha de solicitud de autorización
- Si un extracto bancario contiene movimientos de un mes anterior y la fecha del
  archivo queda fuera de esa ventana, el lote debe quedar observado y no listo
  para emitir hasta que el usuario/contador decida la fecha fiscal correcta.
- Si Excel entrega la fecha del archivo como serial numérico, FactuFlow debe
  convertirla a fecha real antes de validar la ventana ARCA.

### Concepto fiscal ARCA vs descripción del ítem

- FactuFlow no debe asumir productos ni servicios por defecto.
- El concepto fiscal ARCA es un dato técnico/fiscal del comprobante. Antes de
  emitir, el usuario debe elegir el concepto fiscal del lote:
  `Productos`, `Servicios` o `Definido por archivo`.
- Si el usuario elige `Productos`, el lote se trata como concepto ARCA
  productos.
- Si el usuario elige `Servicios`, el lote se trata como concepto ARCA
  servicios y deben resolverse también `FchServDesde`, `FchServHasta` y
  `FchVtoPago`.
- Si el usuario elige `Definido por archivo`, el Excel debe incluir una columna
  válida con `Producto` o `Servicio` en todas las filas. Si la columna falta o
  una fila trae otro valor, la validación debe informar el problema al usuario y
  no dejar el comprobante listo para emitir.
- Ese concepto fiscal ARCA no es la descripción/concepto facturado del ítem.
  `Honorarios`, `Zapatillas`, `Servicio mensual` o textos equivalentes son
  descripciones de ítems y deben resolverse como dato separado.
- La descripción del ítem también debe definirse antes de validar o emitir un
  lote: desde una columna del archivo o como valor fijo para todo el lote. No
  debe salir de un default oculto del formato ni del hecho de haber elegido
  `Productos` o `Servicios`.
- Un perfil de carga masiva puede precargar punto de venta, concepto fiscal
  ARCA y descripción facturada, pero esos valores deben quedar visibles y
  editables en pantalla antes de validar.
- Cuando una fecha tomada del archivo quede fuera de la ventana admitida por
  ARCA para el concepto elegido, el usuario debe elegir una fecha permitida por
  el web service antes de emitir. No se debe corregir automaticamente.

### Notas de crédito/débito y comprobantes asociados

- Para notas de crédito/débito, FactuFlow debe informar el comprobante asociado
  en `FECAESolicitar` dentro de `CbtesAsoc`.
- En lotes, las columnas oficiales para el asociado son:
  `asociado_tipo_comprobante`, `asociado_punto_venta`, `asociado_numero`,
  `asociado_fecha` y `asociado_cuit`.
- Para Nota de Crédito C se usa `tipo_comprobante = 13`; si el comprobante
  original fue Factura C, el asociado normalmente es `tipo = 11` con el punto de
  venta y número de la factura que se anula.
- La validación de lotes bloquea notas de crédito C/A/B si falta tipo, punto de
  venta o número del comprobante asociado.
- Los importes se cargan positivos; el tipo de comprobante define el efecto
  fiscal del crédito.
- La corrección productiva histórica fue validada con un Excel privado y luego
  verificada en modo solo lectura mediante `FECompConsultar`. Identificadores,
  cantidades, CAEs y asociaciones exactas permanecen en evidencia operativa
  privada; la invariante pública es que cada crédito autorizado conservó su
  `CbtesAsoc` esperado.

## Hallazgos técnicos de integración solucionados

- Cache WSAA antes solo en memoria; ahora persiste en `backend/data/arca_token_cache.json`.
- Los importes del request `FECAESolicitar` deben cuantizarse con
  `Decimal("0.01")` y redondeo `ROUND_HALF_UP` antes del payload SOAP. No usar
  `float` ni `round()` para `ImpTotal`, `ImpNeto`, `ImpIVA`, `ImpTrib`, bases ni
  importes de IVA/tributos. Los modelos internos de request ARCA (`ComprobanteRequest`,
  `IvaItem` y `TributoItem`) deben conservar `Decimal`; no degradar a `float`
  antes de `_build_fe_det_request`.
- `FECAESolicitar` debia enviar:
  - `FeDetReq: { FECAEDetRequest: [...] }`
  - `Iva: { AlicIva: [...] }`
  - `Tributos: { Tributo: [...] }`
- El proyecto ya contempla esas estructuras correctas.
- Excepción importante: para comprobantes tipo C (`11`, `12`, `13`) no se debe
  informar el objeto `Iva`. ARCA rechaza esos comprobantes con código `10071`
  aunque la alícuota enviada sea 0.
- FactuFlow también bloquea antes del WSFE los ítems tipo C con IVA distinto
  de 0: en nueva factura la UI fuerza IVA 0 y en lotes la validación marca el
  grupo con error.
- Para notas de crédito/débito con comprobante relacionado, `CbtesAsoc` debe
  enviarse como `{ "CbteAsoc": [...] }`.
- Para emisión masiva, FactuFlow puede enviar varios detalles en un mismo
  `FECAESolicitar`. En ese caso `CantReg` debe coincidir con la cantidad de
  `FECAEDetRequest`, todos los detalles deben compartir punto de venta y tipo,
  y el tamaño máximo se toma de `FECompTotXRequest.RegXReq`.
- Si `FECompTotXRequest` falla o no devuelve `RegXReq`, FactuFlow no hace prueba
  y error: degrada al flujo unitario existente y muestra un aviso persistente
  en el lote.
- Las respuestas de un sublote se ordenan y validan por `CbteDesde`, no por la
  posición del detalle devuelto por ARCA. La cantidad y el conjunto de números
  deben coincidir exactamente con lo solicitado; cualquier diferencia vuelve el
  sublote no confiable.
- Si falla la preparación o reserva local antes de `FECAESolicitar`, la
  transacción completa revierte: quedan cero guardas, intentos y reservas
  nuevos, y cero FECAE. WSAA y lecturas seguras como `FECompTotXRequest` o
  `FECompUltimoAutorizado` pueden haber ocurrido antes; no afirmar que ARCA no
  fue contactada.
- Si un sublote ya enviado a ARCA queda sin detalle confiable, el lote se marca
  como `requiere_reconciliacion` para bloquear reintentos automáticos hasta
  consultar ARCA. Los grupos todavía `validado` no deben seguir apareciendo
  como listos para emisión dentro de ese lote incierto.
- Si ARCA autorizó un CAE y luego falla el cierre del intento fiscal local, la
  respuesta debe preservar el CAE y quedar en `requiere_reconciliacion`; nunca
  debe degradarse a error genérico reintentable ni perder la evidencia fiscal.
- En `FECompConsultar`, ARCA devuelve el número consultado como
  `CbteDesde`/`CbteHasta`; no asumir `CbteNro` en esa respuesta.
- La numeración de comprobantes ahora se protege con:
  - lock en memoria por empresa/punto de venta/tipo
  - advisory lock transaccional si la base es PostgreSQL
  - constraint único local por empresa/punto de venta/tipo/número
- Para cada emisión productiva, sigue siendo obligatorio confirmar punto de
  venta productivo y numeración correlativa en ARCA antes de solicitar CAE.

## Smoke real completado el 2026-03-09

- Certificado homologación emitido y autorizado por WSASS.
- Emisión individual real OK.
- Emisión masiva real OK.
- PDF de comprobante homologado generado.

Los CAEs emitidos en la sesión quedan como evidencia local privada y no deben
copiarse a la documentación versionada.

## QA real histórica completada

- `Ver PDF`, `Descargar PDF`, emisión individual, emisión masiva y
  sincronización técnica fueron revalidados manualmente.
- Comprobantes, puntos, CAEs, cantidades y fechas exactas permanecen en la
  evidencia operativa privada; no se replican en este repositorio público.

## Referencias locales

- Curacion documental: `docs/arca-ws/README.md`
- Notas prácticas: `docs/arca-ws/NOTAS.md`
