# ARCA WS - Notas practicas

Ultima actualizacion: 2026-05-22

Este archivo resume lo que conviene recordar rapido sin volver a abrir todos los PDFs.

## Homologacion - checklist operativo real

1. Adherir `WSASS - Autogestion Certificados Homologacion`
2. Generar CSR con el CUIT del titular del certificado
3. Crear DN y certificado en WSASS
4. Crear autorizacion al servicio `wsfe` para el CUIT representado
5. Verificar punto de venta habilitado
6. Emitir y validar por `FECompConsultar`

## Lo que aprendimos hoy

### 1. Verificacion de homologacion

- No confiar en QR como validacion de homologacion.
- El QR de PDF debe codificar la URL oficial heredada
  `https://www.afip.gob.ar/fe/qr/?p={base64}` con JSON de comprobante en
  Base64. En tests se decodifica el payload y se verifican campos ARCA:
  `ver`, `fecha`, `cuit`, `ptoVta`, `tipoCmp`, `nroCmp`, `importe`, `moneda`,
  `ctz`, `tipoDocRec`, `nroDocRec`, `tipoCodAut`, `codAut`.
- La verificacion correcta es por webservice, usando `FECompConsultar`.

### 2. Puntos de venta

- En el portal no se detecto una pantalla separada de "puntos de venta homologacion".
- Hay que mirar la pantalla habitual `A/B/M de puntos de venta / emision`.
- Para webservices, el indicio util es la columna `Sistema`, por ejemplo `RECE para aplicativo y web services`.

### 3. `FEParamGetPtosVenta`

- En homologacion puede responder `602 - Sin Resultados`.
- Eso no significa necesariamente que el punto de venta sea invalido.
- En esta sesion `FECompUltimoAutorizado` y la emision real si funcionaron.
- El campo `Bloqueado` llega como `N`/`S`. `N` significa no bloqueado; no debe
  evaluarse como booleano directo porque cualquier string no vacio es truthy en
  Python.

### 4. `CondicionIVAReceptorId`

ARCA exigio este campo en homologacion.

Mapping aplicado en el proyecto:
- `RI` -> `1`
- `Monotributo` -> `6`
- `Exento` -> `4`
- `CF` -> `5`

### 4.b Consumidor final

- Para consumidor final, ARCA publica que el comprobante debe llevar la leyenda
  `A CONSUMIDOR FINAL`.
- Si el importe es igual o superior a `$10.000.000`, corresponde informar
  CUIT/CUIL/CDI/DNI, pasaporte u otro documento valido.
- FactuFlow usa tipo documento `99` y numero `0` cuando el Excel no trae
  documento y el importe queda bajo ese umbral. No crea cliente persistente por
  defecto en ese caso; guarda snapshot del receptor en el comprobante.

### 4.c Fecha de emision

- No asumir fecha del dia actual para `CbteFch`.
- La prohibicion aplica a facturas, notas de credito y notas de debito. No usar
  `date.today()`, `datetime.today()`, `new Date()` ni equivalentes como default
  de fecha fiscal.
- FactuFlow exige `fecha_emision` explicita en emision individual y en lotes.
- Antes de solicitar CAE, la UI debe mostrar: `Está seguro que quiere emitir
  comprobantes con fecha XX/XX/XX? Recuerde que luego no podrá emitir
  comprobantes con fecha anterior para ese mismo punto de venta.`
- La API debe bloquear el pedido si no llega la confirmacion fiscal explicita:
  `confirmacion_fecha_fiscal=true` para emision individual o
  `X-Confirmacion-Fecha-Fiscal` con token exacto
  `fechas=AAAA-MM-DD,...;puntos_venta=N,...` para lotes.
- Si ARCA ya devolvio CAE y falla la persistencia local posterior, conservar
  punto de venta, numero, fecha, total y CAE, marcar
  `requiere_reconciliacion` y bloquear reintentos. Primero consultar ARCA y
  reconciliar.
- En lotes, el usuario debe elegir si la fecha de emision sale del archivo o si
  se fija una fecha para todos los comprobantes antes de validar.
- Los perfiles de carga masiva pueden sugerir reglas relativas como ultimo dia
  del mes anterior o emision mas dias, pero la UI no debe convertirlas usando la
  fecha del navegador al autoaplicar el perfil. El usuario debe elegir una fecha
  exacta, tomarla del archivo o confirmar una base explicita antes de validar.
  No son defaults fiscales silenciosos.
- Los perfiles de carga masiva pueden sugerir un punto de venta fijo solo si el
  punto esta cargado para el emisor activo, es Web Services, activo, no
  bloqueado y no tiene fecha de baja. Si no, el lote debe usar el punto del
  archivo o completar primero `Puntos de venta`.
- Para servicios tambien se deben resolver `FchServDesde`, `FchServHasta` y
  `FchVtoPago`.
- Validacion preventiva usada por el proyecto:
  - productos: N-5 / N+5
  - servicios o productos y servicios: N-10 / N+10
  - N es la fecha de solicitud de autorizacion
- Si una fecha de extracto queda fuera de ventana, el lote debe quedar observado
  antes de emitir para que el usuario/contador defina el criterio fiscal.

### 4.d Concepto fiscal ARCA y descripcion facturada

- No asumir productos ni servicios por defecto.
- Antes de emitir, el usuario debe elegir `Productos`, `Servicios` o
  `Definido por archivo`.
- Si se elige `Definido por archivo`, el Excel debe traer una columna valida con
  `Producto` o `Servicio` en todas las filas.
- Si la columna falta o una fila trae un valor distinto, se debe informar al
  usuario y bloquear la emision del lote observado.
- Esto define el concepto fiscal ARCA del comprobante; no define el texto del
  item facturado. La descripcion/concepto facturado del item, por ejemplo
  `Honorarios`, `Zapatillas` o `Servicio mensual`, debe venir de una columna del
  archivo o de un valor fijo confirmado para todo el lote.
- No usar defaults ocultos para la descripcion del item antes de validar o
  emitir.
- Los perfiles de carga masiva pueden precargar punto de venta, concepto fiscal
  ARCA y descripcion facturada solo como valores visibles/editables antes de
  validar.
- Si la fecha del archivo queda fuera de la ventana ARCA aplicable al concepto,
  el usuario debe elegir por pantalla una fecha permitida por el web service
  antes de emitir.

### 5. Estructura SOAP correcta en `FECAESolicitar`

El proyecto tuvo que corregir estas estructuras:

- `FeDetReq` debe enviarse como:
  - `{ "FECAEDetRequest": [ ... ] }`
- `Iva` debe enviarse como:
  - `{ "AlicIva": [ ... ] }`
- `Tributos` debe enviarse como:
  - `{ "Tributo": [ ... ] }`
- Para notas de credito/debito con comprobante asociado, `CbtesAsoc` debe
  enviarse como:
  - `{ "CbteAsoc": [ ... ] }`
- Para comprobantes tipo C (`11`, `12`, `13`), no enviar el objeto `Iva`.
  ARCA rechaza con `10071` aunque se informe alicuota 0.
- FactuFlow debe bloquear localmente cualquier item tipo C con IVA distinto de
  0 antes de solicitar CAE.
- Antes de habilitar acciones WSFE desde la UI, FactuFlow debe verificar que
  haya certificado activo para el `ARCA_ENV` actual. Un certificado valido de
  otro ambiente no sirve para esa operacion.

### 5.b Notas de credito C por duplicados productivos

- Para Nota de Credito C usar `tipo_comprobante = 13`.
- Si anula una Factura C, informar como asociado `tipo = 11`, punto de venta,
  numero, fecha y CUIT del emisor de la factura duplicada.
- Los importes van positivos; el tipo de comprobante define que se trata de un
  credito.
- El 2026-05-08 se genero un Excel privado local con 19 notas de credito para
  anular duplicados productivos. Se valido contra una copia de la base, sin
  emision: 19 validas, 0 errores, 0 emitidas.
- Luego el usuario emitio las 19 notas en produccion. Verificacion posterior
  solo lectura por `FECompConsultar`: 19 con `Resultado=A`, CAE coincidente e
  informacion de `CbtesAsoc` contra la factura duplicada esperada.
- En la respuesta de `FECompConsultar`, usar `CbteDesde`/`CbteHasta` para el
  numero; no depender de `CbteNro`.

### 6. Cache de tickets WSAA

- Antes el cache era solo en memoria.
- Ahora persiste en disco para evitar depender del proceso actual.
- Archivo actual: `backend/data/arca_token_cache.json`

### 7. CUIT correcto para WSFE

- Si el certificado pertenece a un titular y opera para una empresa representada, no mezclar ambos CUIT.
- El helper de ARCA debe operar con el CUIT de la empresa activa representada.
- Este punto fue clave para corregir la sincronizacion de puntos de venta desde UI.
- Antes de solicitar CAE, el backend debe confirmar que el punto de venta y el
  `cliente_id` opcional sean del emisor activo. Un ID valido pero de otro CUIT
  se rechaza localmente para no mezclar comprobantes, clientes ni numeracion.

### 8. Paths legacy de certificados

- La base local puede traer rutas tipo `certs/archivo.crt`.
- El runtime ahora acepta path absoluto dentro de `CERTS_PATH`, filename simple
  y valor legacy con prefijo `certs/`.
- El upload de certificados no acepta paths arbitrarios en `key_filename`: debe
  ser una clave generada por FactuFlow para el CUIT y ambiente activos.
- Las claves privadas nuevas se cifran con `ARCA_PRIVATE_KEY_PASSWORD` o, si no
  esta configurada, con `APP_SECRET_KEY`. Las claves legacy sin cifrar se pueden
  seguir leyendo para continuidad operativa.
- Este ajuste destrabo la consulta de proximo numero y la emision individual desde UI.

## Donde mirar en el codigo

- `backend/app/arca/cache.py`
- `backend/app/arca/models.py`
- `backend/app/arca/wsfev1.py`
- `backend/app/services/facturacion_service.py`
- `backend/app/services/lote_worker.py`

## Produccion

- Usar certificado productivo y autorizacion `wsfe` productiva; los certificados de homologacion no sirven para produccion.
- Despues de crear el certificado productivo, asociar el alias del computador al
  servicio `wsfe` desde `Administrador de Relaciones de Clave Fiscal`. Si falta
  esa asociacion, WSAA devuelve `Computador no autorizado a acceder al servicio`.
- Usar punto de venta productivo especifico para webservices y mantener numeracion correlativa.
- En el piloto productivo de la Fundacion, `FEParamGetPtosVenta` devolvio
  habilitados `6`, `8`, `10`, `12`, `13` y `14`; `7` y `9` estaban bloqueados.
- El 2026-05-08 se corrigio la validacion de emision para interpretar
  `Bloqueado=N` como punto habilitado. Antes de ese ajuste, el lote observado
  podia marcar como no habilitados puntos validos como `6`, `10` y `13`.
- La lista completa de puntos con sistema, domicilio y nombre fantasia no vino
  por WSFEv1; se importo desde la constancia PDF de puntos de venta.
- El WSDL productivo de WSFEv1 requirio transporte TLS con `SECLEVEL=1` por
  compatibilidad con el handshake del endpoint.
- El perfil productivo del repo es `docker-compose.prod.yml` con PostgreSQL.
- Al 2026-05-22, FactuFlow ya fue usado en produccion real. No tratar la
  produccion como pendiente de primer piloto; tratarla como operacion
  post-piloto que requiere backup/restauracion, trazabilidad, observabilidad y
  controles fiscales antes de cada nuevo lote.

## Dato historico util

El smoke real de homologacion del 2026-03-09 emitio:
- comprobante individual con CAE registrado en evidencia local privada
- lote con CAEs registrados en evidencia local privada

La QA real del 2026-04-10 agrego:
- comprobante individual `0005-00000004` con CAE registrado en evidencia local privada
- lote `0005-00000005` con CAE registrado en evidencia local privada
- lote `0005-00000006` con CAE registrado en evidencia local privada

Detalle completo:
- `docs/project/notes/SESSION_2026-03-09.md`
