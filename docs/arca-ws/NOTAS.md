# ARCA WS - Notas prácticas

Última actualización: 2026-06-12

Este archivo resume lo que conviene recordar rápido sin volver a abrir todos los PDFs.

## Homologación - checklist operativo real

1. Adherir `WSASS - Autogestion Certificados Homologacion`
2. Generar CSR con el CUIT del titular del certificado
3. Crear DN y certificado en WSASS
4. Crear autorización al servicio `wsfe` para el CUIT representado
5. Verificar punto de venta habilitado
6. Emitir y validar por `FECompConsultar`

## Lo que aprendimos hoy

### 1. Verificacion de homologación

- No confiar en QR como validación de homologación.
- El QR de PDF debe codificar la URL oficial heredada
  `https://www.afip.gob.ar/fe/qr/?p={base64}` con JSON de comprobante en
  Base64. En tests se decodifica el payload y se verifican campos ARCA:
  `ver`, `fecha`, `cuit`, `ptoVta`, `tipoCmp`, `nroCmp`, `importe`, `moneda`,
  `ctz`, `tipoDocRec`, `nroDocRec`, `tipoCodAut`, `codAut`.
- La verificacion correcta es por webservice, usando `FECompConsultar`.

### 2. Puntos de venta

- En el portal no se detectó una pantalla separada de "puntos de venta homologación".
- Hay que mirar la pantalla habitual `A/B/M de puntos de venta / emision`.
- Para webservices, el indicio útil es la columna `Sistema`, por ejemplo `RECE para aplicativo y web services`.

### 3. `FEParamGetPtosVenta`

- En homologación puede responder `602 - Sin Resultados`.
- Eso no significa necesariamente que el punto de venta sea invalido.
- En esta sesión `FECompUltimoAutorizado` y la emisión real sí funcionaron.
- El campo `Bloqueado` llega como `N`/`S`. `N` significa no bloqueado; no debe
  evaluarse como booleano directo porque cualquier string no vacío es truthy en
  Python.

### 4. `CondicionIVAReceptorId`

ARCA exigió este campo en homologación.

Mapping aplicado en el proyecto:
- `RI` -> `1`
- `Monotributo` -> `6`
- `Exento` -> `4`
- `CF` -> `5`

### 4.b Consumidor final

- Para consumidor final, ARCA pública que el comprobante debe llevar la leyenda
  `A CONSUMIDOR FINAL`.
- Si el importe es igual o superior a `$10.000.000`, corresponde informar
  CUIT/CUIL/CDI/DNI, pasaporte u otro documento válido.
- FactuFlow usa tipo documento `99` y número `0` cuando el Excel no trae
  documento y el importe queda bajo ese umbral. No crea cliente persistente por
  defecto en ese caso; guarda snapshot del receptor en el comprobante.

### 4.c Fecha de emisión

- No asumir fecha del día actual para `CbteFch`.
- La prohibicion aplica a facturas, notas de crédito y notas de débito. No usar
  `date.today()`, `datetime.today()`, `new Date()` ni equivalentes como default
  de fecha fiscal.
- FactuFlow exige `fecha_emision` explícita en emisión individual y en lotes.
- Antes de solicitar CAE, la UI debe mostrar: `Está seguro que quiere emitir
  comprobantes con fecha XX/XX/XX? Recuerde que luego no podrá emitir
  comprobantes con fecha anterior para ese mismo punto de venta.`
- La API debe bloquear el pedido si no llega la confirmación fiscal explícita:
  `confirmacion_fecha_fiscal=true` para emisión individual o
  `X-Confirmacion-Fecha-Fiscal` con token exacto
  `fechas=YYYY-MM-DD,...;puntos_venta=N,...` para lotes. El token de confirmación de lotes usa fechas técnicas `YYYY-MM-DD`; el texto visible de confirmación debe mostrarlas en `DD/MM/AAAA`.
- Si ARCA ya devolvio CAE y falla la persistencia local posterior, conservar
  punto de venta, número, fecha, total y CAE, marcar
  `requiere_reconciliacion` y bloquear reintentos. Primero consultar ARCA y
  reconciliar.
- En lotes, el usuario debe elegir si la fecha de emisión sale del archivo o si
  se fija una fecha para todos los comprobantes antes de validar.
- Los perfiles de carga masiva pueden sugerir reglas relativas como último día
  del mes anterior o emisión mas días, pero la UI no debe convertirlas usando la
  fecha del navegador al autoaplicar el perfil. El usuario debe elegir una fecha
  exacta, tomarla del archivo o confirmar una base explícita antes de validar.
  No son defaults fiscales silenciosos.
- Los perfiles de carga masiva pueden sugerir un punto de venta fijo solo si el
  punto está cargado para el emisor activo, es Web Services, activo, no
  bloqueado y no tiene fecha de baja. Si no, el lote debe usar el punto del
  archivo o completar primero `Puntos de venta`.
- Para servicios también se deben resolver `FchServDesde`, `FchServHasta` y
  `FchVtoPago`.
- Validación preventiva usada por el proyecto:
  - productos: N-5 / N+5
  - servicios o productos y servicios: N-10 / N+10
  - N es la fecha de solicitud de autorización
- Si una fecha de extracto queda fuera de ventana, el lote debe quedar observado
  antes de emitir para que el usuario/contador defina el criterio fiscal.

### 4.d Concepto fiscal ARCA y descripción facturada

- No asumir productos ni servicios por defecto.
- Antes de emitir, el usuario debe elegir `Productos`, `Servicios` o
  `Definido por archivo`.
- Si se elige `Definido por archivo`, el Excel debe traer una columna válida con
  `Producto` o `Servicio` en todas las filas.
- Si la columna falta o una fila trae un valor distinto, se debe informar al
  usuario y bloquear la emisión del lote observado.
- Esto define el concepto fiscal ARCA del comprobante; no define el texto del
  ítem facturado. La descripción/concepto facturado del ítem, por ejemplo
  `Honorarios`, `Zapatillas` o `Servicio mensual`, debe venir de una columna del
  archivo o de un valor fijo confirmado para todo el lote.
- No usar defaults ocultos para la descripción del ítem antes de validar o
  emitir.
- Los perfiles de carga masiva pueden precargar punto de venta, concepto fiscal
  ARCA y descripción facturada solo como valores visibles/editables antes de
  validar.
- Si la fecha del archivo queda fuera de la ventana ARCA aplicable al concepto,
  el usuario debe elegir por pantalla una fecha permitida por el web service
  antes de emitir.

### 4.e Reconciliación externa de lotes

- Para comprobantes emitidos manualmente en ARCA Web, FactuFlow debe usar
  `FECompConsultar` antes de registrarlos localmente.
- La consulta debe coincidir con emisor activo, receptor, tipo, punto de venta,
  número, fecha fiscal, total, resultado autorizado y CAE.
- Un comprobante externo verificado no puede vincularse a más de un grupo local;
  la base lo refuerza con unicidad parcial sobre el `comprobante_id` del grupo.
- Esos comprobantes se guardan con `origen_emision = arca_web`.
- Si un lote quedó en `requiere_reconciliacion` o un grupo quedó
  `reintentando` por fallo posterior a ARCA, no reintentar. Primero consultar
  ARCA y reconciliar.
- Si un lote masivo queda `procesando` y supera la ventana operativa
  `BATCH_PROCESSING_STALE_MINUTES`, la ventana vencida no habilita reemisión
  automática. El worker solo puede vincular comprobantes locales ya autorizados
  sin pedir CAE si están respaldados por un intento fiscal `autorizado` del
  mismo lote/grupo, con comprobante, número planificado, CAE, fecha, receptor y
  total coherentes. Un comprobante local parecido pero sin ese intento no debe
  cerrar el grupo. Si queda cualquier pendiente o duda, debe pasar a
  `requiere_reconciliacion` con evento `bloqueo_operativo_no_reemitir` y marcar
  los grupos `validado` remanentes como `requiere_reconciliacion`.
- `Completado` queda reservado para comprobantes emitidos por FactuFlow.
  Cuando hubo emisión externa verificada, el cierre correcto es
  `cerrado_reconciliado`.

### 4.f Idempotencia fiscal y CAE

- La llave de idempotencia de una emisión no es el CAE. La llave operativa es
  `X-Idempotency-Key` junto con emisor, tipo de operación y hash del payload
  fiscal.
- El CAE confirma autorización fiscal y sirve para persistir, auditar y
  reconciliar; llega después de la llamada irreversible a ARCA, por eso no puede
  ser el primer control de duplicación.
- Emisión individual, procesamiento de lotes y reintento de fallidos deben
  rechazar pedidos sin `X-Idempotency-Key` antes de solicitar CAE.
- Misma clave y mismo payload debe devolver la respuesta ya persistida o el
  estado actual de la operación, sin volver a llamar a ARCA. Misma clave con
  datos distintos debe devolver conflicto.
- Antes de `FECAESolicitar`, FactuFlow debe crear intento fiscal durable con
  tipo, punto de venta, número planificado, fecha, total y receptor. Esa reserva
  bloquea reintentos inciertos.
- Si un intento queda `en_proceso` vencido, consultar `FECompConsultar` por
  tipo, punto y número planificado. Solo liberar numeración si ARCA confirma que
  el comprobante no existe. Si ARCA confirma CAE, vincular o reconstruir cuando
  haya datos locales suficientes; si no, dejar `requiere_reconciliacion`.
- Los duplicados lógicos son advertencias operativas: pueden requerir
  confirmación adicional, pero no reemplazan la confirmación fiscal ni bloquean
  automáticamente la emisión.

### 5. Estructura SOAP correcta en `FECAESolicitar`

El proyecto tuvo que corregir estas estructuras:

- `FeDetReq` debe enviarse como:
  - `{ "FECAEDetRequest": [ ... ] }`
- `Iva` debe enviarse como:
  - `{ "AlicIva": [ ... ] }`
- `Tributos` debe enviarse como:
  - `{ "Tributo": [ ... ] }`
- Para notas de crédito/débito con comprobante asociado, `CbtesAsoc` debe
  enviarse como:
  - `{ "CbteAsoc": [ ... ] }`
- Para comprobantes tipo C (`11`, `12`, `13`), no enviar el objeto `Iva`.
  ARCA rechaza con `10071` aunque se informe alícuota 0.
- FactuFlow debe bloquear localmente cualquier ítem tipo C con IVA distinto de
  0 antes de solicitar CAE.
- Antes de habilitar acciones WSFE desde la UI, FactuFlow debe verificar que
  haya certificado activo para el `ARCA_ENV` actual. Un certificado válido de
  otro ambiente no sirve para esa operación.

### 5.a Sublotes en `FECAESolicitar`

- `FECAESolicitar` permite enviar un comprobante o un lote de comprobantes.
- `FeCabReq.CantReg` debe coincidir exactamente con la cantidad de detalles
  `FECAEDetRequest` enviados.
- Un request con mas de un detalle debe ser homogeneo: mismo `PtoVta` y mismo
  `CbteTipo`.
- La cantidad máxima no se debe hardcodear. Se consulta con
  `FECompTotXRequest`, que devuelve `RegXReq`.
- FactuFlow consulta `RegXReq` al procesar el lote y divide por sublotes de ese
  tamaño. Si ARCA no informa `RegXReq`, degrada al modo unitario y deja aviso
  explícito en el lote para el usuario.
- Los tipos FCE/MiPyME documentados por ARCA se fuerzan a modo unitario aunque
  `RegXReq` permita más registros.
- La respuesta de un sublote se correlaciona por `CbteDesde`, no por posición
  en la lista. La cantidad de detalles debe coincidir, no puede haber números
  duplicados y el conjunto de `CbteDesde` devuelto debe ser exactamente el de
  los comprobantes solicitados.
- Si falla la preparación local antes de contactar ARCA, los intentos batch ya
  creados se marcan `fallido_verificado` con categoría
  `pre_arca_reserva_fallida`. Ese caso no requiere reconciliación porque el
  sublote no fue enviado.
- Si un sublote enviado no devuelve detalle confiable, el lote queda en
  `requiere_reconciliacion`; no se reintenta automáticamente y ningún grupo
  remanente debe seguir mostrándose como listo para emitir.
- Si el CAE fue autorizado y luego falla el cierre del intento fiscal local, el
  resultado conserva CAE/número y queda `requiere_reconciliacion`. No se debe
  devolver un error genérico que habilite reintento automático.

### 5.b Notas de crédito C por duplicados productivos

- Para Nota de Crédito C usar `tipo_comprobante = 13`.
- Si anula una Factura C, informar como asociado `tipo = 11`, punto de venta,
  número, fecha y CUIT del emisor de la factura duplicada.
- Los importes van positivos; el tipo de comprobante define que se trata de un
  crédito.
- El 2026-05-08 se generó un Excel privado local con 19 notas de crédito para
  anular duplicados productivos. Se válido contra una copia de la base, sin
  emisión: 19 válidas, 0 errores, 0 emitidas.
- Luego el usuario emitió las 19 notas en producción. Verificación posterior
  solo lectura por `FECompConsultar`: 19 con `Resultado=A`, CAE coincidente e
  informacion de `CbtesAsoc` contra la factura duplicada esperada.
- En la respuesta de `FECompConsultar`, usar `CbteDesde`/`CbteHasta` para el
  número; no depender de `CbteNro`.

### 6. Cache de tickets WSAA

- Antes el cache era solo en memoria.
- Ahora persiste en disco para evitar depender del proceso actual.
- Archivo actual: `backend/data/arca_token_cache.json`

### 7. CUIT correcto para WSFE

- Si el certificado pertenece a un titular y opera para una empresa representada, no mezclar ambos CUIT.
- El helper de ARCA debe operar con el CUIT de la empresa activa representada.
- Este punto fue clave para corregir la sincronización de puntos de venta desde UI.
- Antes de solicitar CAE, el backend debe confirmar que el punto de venta y el
  `cliente_id` opcional sean del emisor activo. Un ID válido pero de otro CUIT
  se rechaza localmente para no mezclar comprobantes, clientes ni numeración.

### 8. Paths legacy de certificados

- La base local puede traer rutas tipo `certs/archivo.crt`.
- El runtime ahora acepta path absoluto dentro de `CERTS_PATH`, filename simple
  y valor legacy con prefijo `certs/`.
- El upload de certificados no acepta paths arbitrarios en `key_filename`: debe
  ser una clave generada por FactuFlow para el CUIT y ambiente activos.
- Las claves privadas nuevas se cifran con `ARCA_PRIVATE_KEY_PASSWORD` o, si no
  está configurada, con `APP_SECRET_KEY`. Las claves legacy sin cifrar se pueden
  seguir leyendo para continuidad operativa.
- Este ajuste destrabo la consulta de próximo número y la emisión individual desde UI.

## Donde mirar en el código

- `backend/app/arca/cache.py`
- `backend/app/arca/models.py`
- `backend/app/arca/wsfev1.py`
- `backend/app/services/facturacion_service.py`
- `backend/app/services/lote_worker.py`

## Producción

- Usar certificado productivo y autorización `wsfe` productiva; los certificados
  de homologación no sirven para producción.
- Después de crear el certificado productivo, asociar el alias del computador al
  servicio `wsfe` desde `Administrador de Relaciones de Clave Fiscal`. Si falta
  esa asociacion, WSAA devuelve `Computador no autorizado a acceder al servicio`.
- Usar punto de venta productivo especifico para webservices y mantener numeración correlativa.
- En el piloto productivo de la Fundacion, `FEParamGetPtosVenta` devolvio
  habilitados `6`, `8`, `10`, `12`, `13` y `14`; `7` y `9` estaban bloqueados.
- El 2026-05-08 se corrigió la validación de emisión para interpretar
  `Bloqueado=N` como punto habilitado. Antes de ese ajuste, el lote observado
  podía marcar como no habilitados puntos válidos como `6`, `10` y `13`.
- La lista completa de puntos con sistema, domicilio y nombre fantasia no vino
  por WSFEv1; se importo desde la constancia PDF de puntos de venta.
- El WSDL productivo de WSFEv1 requirio transporte TLS con `SECLEVEL=1` por
  compatibilidad con el handshake del endpoint.
- El perfil productivo del repo es `docker-compose.prod.yml` con PostgreSQL.
- Antes de mover la operación a VPS, preparar el paquete con
  `python -m app.scripts.vps_migration`: `preflight` debe bloquear cualquier
  certificado activo sin `.crt` y `.key` resolubles, `export` re-cifra claves
  privadas con la contraseña destino y `import` exige PostgreSQL limpio ya
  migrado con Alembic.
- La contraseña usada en `ARCA_MIGRATION_TARGET_KEY_PASSWORD` durante el export
  debe coincidir con `ARCA_PRIVATE_KEY_PASSWORD` en `.env.production`.
- La migración y el ensayo local no solicitan CAE ni emiten comprobantes.
- Al 2026-05-22, FactuFlow ya fue usado en producción real. No tratar la
  producción como pendiente de primer piloto; tratarla como operación
  post-piloto que requiere backup/restauración, trazabilidad, observabilidad y
  controles fiscales antes de cada nuevo lote.

## Dato histórico útil

El smoke real de homologación del 2026-03-09 emitió:
- comprobante individual con CAE registrado en evidencia local privada
- lote con CAEs registrados en evidencia local privada

La QA real del 2026-04-10 agregó:
- comprobante individual `0005-00000004` con CAE registrado en evidencia local privada
- lote `0005-00000005` con CAE registrado en evidencia local privada
- lote `0005-00000006` con CAE registrado en evidencia local privada

Detalle completo:
- `docs/project/notes/SESSION_2026-03-09.md`
