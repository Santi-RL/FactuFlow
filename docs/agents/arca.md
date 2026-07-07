# Integración ARCA

## Nomenclatura

- ARCA es el nombre actual y debe usarse en UI, documentación nueva y textos de soporte.
- AFIP sigue apareciendo en URLs oficiales y nombres legacy por compatibilidad técnica.

## Módulos relevantes

- `backend/app/arca/wsaa.py`: autenticacion WSAA
- `backend/app/arca/wsfev1.py`: integración WSFEv1
- `backend/app/arca/crypto.py`: firmado y utilidades criptograficas
- `backend/app/arca/cache.py`: cache de tickets WSAA
- `backend/app/arca/models.py`: modelos de request/response
- `backend/app/services/facturacion_service.py`: orquestacion de emisión real
- `backend/app/api/arca.py`: endpoints HTTP vinculados a ARCA

## Endpoints oficiales

- WSAA homologación: `https://wsaahomo.afip.gov.ar/ws/services/LoginCms?wsdl`
- WSAA producción: `https://wsaa.afip.gov.ar/ws/services/LoginCms?wsdl`
- WSFEv1 homologación: `https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL`
- WSFEv1 producción: `https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL`

## Variables de entorno reales del proyecto

- `ARCA_ENV`: `homologacion` o `produccion`
- `CERTS_PATH`: base path de certificados
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
- Después de generar el certificado en `Administracion de Certificados Digitales`,
  el administrador/representante debe asociar el alias del computador al servicio
  `wsfe` desde `Administrador de Relaciones de Clave Fiscal`.
- Si falta esa autorización, WSAA responde `Computador no autorizado a acceder
  al servicio`, aunque el certificado y la clave privada coincidan.
- El wizard de FactuFlow tiene un paso previo a `Probar conexion` para confirmar
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

### Paths legacy de certificados

- La base local puede contener valores legacy como `certs/archivo.crt`.
- El proyecto ahora resuelve correctamente:
  - paths absolutos dentro de `CERTS_PATH`
  - filenames simples
  - valores legacy con prefijo `certs/`
- Los paths que resuelven fuera de `CERTS_PATH` se rechazan. El upload de
  certificados solo acepta nombres de clave generados por FactuFlow para el
  CUIT y ambiente del emisor activo.
- Las claves privadas nuevas se guardan cifradas. Las claves legacy sin cifrar
  siguen pudiendo leerse para no romper certificados existentes, pero no se
  generan claves nuevas sin cifrado salvo que no exista ninguna contraseña de
  aplicacion configurada.
- Este fix fue necesario para que `Nueva factura` volviera a obtener el próximo número desde homologación.

### Puntos de venta

- No se detectó una pantalla separada en el portal que diga "homologación" para los puntos de venta de WSFEv1.
- En la práctica se revisa la misma pantalla `A/B/M de puntos de venta / emision`.
- Para webservices, el indicio útil es la columna `Sistema`, por ejemplo `RECE para aplicativo y web services`.
- En esta sesión se usó el punto de venta `5`.
- En producción para el emisor real privado, ARCA
  devolvio habilitados `6`, `8`, `10`, `12`, `13` y `14`; `7` y `9` estaban
  bloqueados.
- `FEParamGetPtosVenta` devuelve el indicador `Bloqueado` como `N`/`S`; en
  validaciones de emisión debe normalizarse explícitamente. `N` significa no
  bloqueado y debe tratarse como punto habilitado. No evaluar ese campo como
  booleano directo.
- El 2026-05-07 se revalido de forma segura por API local contra ARCA
  producción:
  - `GET /api/arca/test-conexion`: `status=ok`, ambiente `produccion`
  - `GET /api/arca/puntos-venta`: `6`, `8`, `10`, `12`, `13` y `14` no
    bloqueados; `7` y `9` bloqueados
  - `GET /api/arca/ultimo-comprobante/6/6`: último comprobante `0`, próximo
    `1` para Factura B en punto de venta `6`
- `FEParamGetPtosVenta` no devuelve domicilio ni nombre fantasia. Esos datos se
  importan desde la constancia PDF de `Administración de Puntos de Venta y
  Domicilios`.
- `GET /api/arca/status` informa el ambiente ARCA actual y si existe
  certificado activo local para ese ambiente, sin llamar a ARCA ni consumir
  numeración. La UI de puntos de venta usa ese estado antes de permitir
  sincronización WSFE.
- Los puntos devueltos por `FEParamGetPtosVenta` pertenecen al servicio WSFE:
  al sincronizarlos en FactuFlow deben quedar marcados como Web Services,
  activos y no bloqueados cuando `Bloqueado=N` y no tienen fecha de baja. Si se
  crean solo con número, la UI los muestra erroneamente como `Otro sistema`.
- La constancia permite ver también puntos de otros sistemas como Factuweb,
  Comprobantes en Línea y Controlador Fiscal; deben mostrarse pero no tratarse
  como usables para FactuFlow si no son Web Services.
- Si al importar una constancia falla la consulta técnica `FEParamGetPtosVenta`,
  no se debe inventar estado ARCA activo: los puntos existentes conservan
  `bloqueado`, `fecha_baja` y `activo`; los puntos nuevos quedan inactivos hasta
  sincronizar con ARCA o revisarlos manualmente.

### Constancias de emisores

- El alta de emisores soporta constancias de inscripción de persona jurídica,
  constancias de inscripcion de persona fisica y constancias de opcion de
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

### Verificacion de comprobantes

- La forma confiable de verificar comprobantes de homologación es `FECompConsultar`.
- El QR sirve para comprobantes reales, pero no se tomó como mecanismo de validación de homologación.
- El QR del PDF se arma segun la especificacion ARCA con una URL
  `https://www.afip.gob.ar/fe/qr/?p={base64}`. El payload testeado incluye
  `ver`, `fecha`, `cuit`, `ptoVta`, `tipoCmp`, `nroCmp`, `importe`, `moneda`,
  `ctz`, `tipoDocRec`, `nroDocRec`, `tipoCodAut` y `codAut`.

### CAE, idempotencia e intentos fiscales

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
  intento fuerte no cierra automáticamente el grupo. Si queda cualquier
  pendiente o incertidumbre, debe marcar el lote `requiere_reconciliacion`,
  registrar `bloqueo_operativo_no_reemitir`, marcar los grupos `validado`
  remanentes como `requiere_reconciliacion` y exigir auditoría antes de
  continuar.

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

### RG 5616 / Condicion frente al IVA del receptor

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
  - normaliza a tipo documento `99`, número `0`, razon social
    `A CONSUMIDOR FINAL` y condicion IVA `CF`
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
- Un perfil de carga masiva puede precargar reglas relativas de fecha, pero la
  UI no debe convertirlas usando la fecha del navegador al autoaplicar el
  perfil. Deben quedar visibles para que el usuario elija una fecha exacta,
  tome la fecha del archivo o confirme una base explícita antes de validar. El
  backend de lotes sigue recibiendo `archivo` o `fija`; el perfil no puede
  emitir ni validar de forma silenciosa.
- Un perfil de carga masiva también puede precargar punto de venta. Las opciones
  válidas son usar el punto definido en el archivo o fijar un punto Web Services
  activo, no bloqueado y sin baja del emisor activo. Si no está cargado en
  `Puntos de venta`, no se puede elegir como punto fijo.
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
- Para los duplicados productivos del 2026-05-08 se preparo un Excel privado
  local con 19 Nota de Crédito C y se válido sin emisión contra
  una copia de la base: 19 válidas, 0 errores, 0 emitidas.
- El usuario emitió luego esas 19 Nota de Crédito C en producción. Verificacion
  posterior solo lectura por `FECompConsultar`: las 19 devolvieron
  `Resultado=A`, CAE coincidente y `CbtesAsoc` contra la Factura C duplicada
  esperada.

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
- Excepcion importante: para comprobantes tipo C (`11`, `12`, `13`) no se debe
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
- Si falla la preparación local antes de enviar el sublote a ARCA, los intentos
  ya reservados se cierran como `fallido_verificado` con categoría
  `pre_arca_reserva_fallida`; no deben quedar `en_proceso` ni forzar
  reconciliación porque ARCA no fue contactada.
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

## QA real completada el 2026-04-10

- `Ver PDF` y `Descargar PDF` revalidados manualmente.
- Emisión individual real desde UI:
  - `0005-00000004`
  - CAE registrado en evidencia local privada
- Emisión masiva real desde UI:
  - `0005-00000005`
  - CAE registrado en evidencia local privada
  - `0005-00000006`
  - CAE registrado en evidencia local privada
- `Sincronizar con ARCA` en puntos de venta corregido y revalidado manualmente.

## Referencias locales

- Curacion documental: `docs/arca-ws/README.md`
- Notas prácticas: `docs/arca-ws/NOTAS.md`
