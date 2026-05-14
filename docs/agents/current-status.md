# Estado actual

Ultima actualizacion: 2026-05-14

## Objetivo activo

Dejar FactuFlow listo para una primera prueba real controlada en produccion, con homologacion estable y flujos administrativos validados desde la UI.

## Estado real del producto

- Backend FastAPI operativo con auth, empresas, clientes, puntos de venta, certificados, comprobantes, PDF, lotes y reportes.
- Backend ya registra formatos configurables de importacion para lotes masivos, con formatos globales y particulares por emisor.
- Backend ya registra perfiles de carga masiva por emisor para precargar
  formato, punto de venta, concepto fiscal ARCA, descripcion facturada y reglas
  de fechas.
- Frontend Vue operativo con dashboard, clientes, comprobantes, emision masiva, reportes, certificados, puntos de venta y mi empresa.
- PDF de comprobantes actualizado con formato administrativo mas prolijo,
  datos fiscales completos disponibles, QR ARCA testeable por payload y fechas
  de servicio/vencimiento persistidas en comprobantes nuevos.
- Emision masiva ahora puede usar plantilla oficial o formatos configurables con autodeteccion asistida.
- Emision masiva ahora puede aplicar perfiles de carga masiva visibles y
  editables antes de validar.
- Emision masiva muestra progreso real de emision para lotes chicos y grandes,
  con timer de tiempo transcurrido y estimacion restante.
- Selector de empresa activa implementado para admins.
- Emision individual y masiva funcionando en homologacion y validadas manualmente desde la interfaz.
- PDF generado bajo demanda y revalidado manualmente en preview y descarga.
- Se corrigieron riesgos previos de salida a produccion:
  - numeracion protegida con lock local, advisory lock PostgreSQL y constraint unico
  - idempotencia atomica de lote por hash de archivo, empresa y formato usado
  - validacion estricta de alicuotas IVA permitidas desde Excel
  - lotes grandes en cola persistente y reanudables por worker
  - perfiles Docker separados para desarrollo y produccion con PostgreSQL

## Lo mas importante que quedo hecho hoy

### PDF profesional y QR ARCA 2026-05-14

- Se rediseño el PDF de comprobante para que se vea mas prolijo y profesional
  sin replicar el formato visual oficial de ARCA.
- El PDF ahora organiza emisor, receptor, operación, detalle, totales, CAE,
  vencimiento CAE, leyenda ARCA y QR en bloques claros.
- Se agrego `ingresos_brutos` al emisor para poder mostrar ese dato fiscal en
  el PDF cuando este cargado. Los emisores existentes pueden completarlo desde
  `Emisores`.
- Los comprobantes nuevos persisten `fecha_servicio_desde`,
  `fecha_servicio_hasta` y `fecha_vto_pago` para que el PDF muestre periodo
  facturado y vencimiento cuando el concepto fiscal sea servicios o ambos.
- El QR quedo separado en payload y URL testeables. La prueba decodifica el
  Base64 y verifica campos oficiales: `ver`, `fecha`, `cuit`, `ptoVta`,
  `tipoCmp`, `nroCmp`, `importe`, `moneda`, `ctz`, `tipoDocRec`,
  `nroDocRec`, `tipoCodAut` y `codAut`.
- Verificacion tecnica focalizada: `pytest tests/test_pdf_service.py
  tests/test_facturacion_service.py -q`, `ruff check app tests alembic`,
  `black --check app tests alembic` y `npm run type-check` OK.

### Formato Roldan Factura B IVA 21% 2026-05-11

- Se creo en la base local el formato particular `Roldan - Factura B IVA 21%`
  para el emisor `ROLDAN GONZALO MATIAS`.
- El formato mapea `Imp. Neto Gravado` como `item_precio_unitario` y `Imp.
  Total` solo como total informado para control de consistencia. Esto evita
  repetir el error de usar el total final como neto y volver a agregar IVA.
- El Excel privado `Roldan a facturar 04-2026 ok envio.xlsx` contiene 1432
  filas utiles, todas `Factura B`, fecha de origen `28/02/2026`, receptor sin
  documento ni denominacion y columna `Punto de Venta` vacia.
- El perfil predeterminado local del emisor Roldan quedo vinculado al formato,
  mantiene punto de venta fijo `5`, concepto fiscal `Servicios`, descripcion
  fija `Servicios` y reglas relativas existentes.
- QA segura sin emision real sobre copia de base local: deteccion de formato
  con confianza alta `1.0`; validacion con fecha de emision fija
  `30/04/2026`, periodo `01/04/2026 - 30/04/2026`, vencimiento `30/04/2026`
  y punto fijo `5`; resultado 1432 grupos validos, 0 con error, 0 emitidos.
- QA negativa sobre copia de base local: un formato deliberadamente incorrecto
  usando `Imp. Total` como neto dejo 1432 grupos con error por diferencia entre
  total calculado y total informado, 0 validos y 0 emitidos.
- En la pantalla de detalle del lote validado se agrego un bloque de totales
  listos para emitir: comprobantes, neto, IVA 21%, IVA 10,5% y total. El
  calculo se hace sobre grupos validados antes de presionar `Emitir
  comprobantes validos`, para comparar contra el Excel sin solicitar CAE.

### Constancias de emisores mas robustas 2026-05-10

- El parser de constancias ARCA de emisores ahora distingue formatos de
  inscripcion de persona juridica, inscripcion de persona fisica y opcion de
  Monotributo.
- La extraccion corrige cortes comunes introducidos por PDFs en nombre fiscal,
  domicilio y localidad, y evita usar lineas tecnicas como provincia.
- La provincia se valida contra un catalogo cerrado de provincias argentinas en
  backend y en la pantalla `Emisores`; ya no queda como texto libre en alta o
  edicion de emisor.

### Punto de venta en perfiles de carga masiva 2026-05-10

- Los perfiles de carga masiva ahora pueden precargar si el lote usa el punto de
  venta definido en el archivo o un punto fijo del emisor activo.
- Solo se puede guardar un punto fijo si esta cargado en `Puntos de venta` para
  ese emisor y es usable por FactuFlow: Web Services, activo, no bloqueado y sin
  fecha de baja.
- Si el emisor no tiene puntos usables cargados, la UI indica que primero deben
  completarse en `Puntos de venta`.
- En `Emision masiva`, la seleccion queda visible y editable antes de validar.
  Si se fija un punto, el backend sobrescribe el punto de venta de todas las
  filas antes de validar y guarda la politica en `metadata_json`.
  La barrera fiscal final no cambia: antes de solicitar CAE sigue apareciendo
  el modal irreversible con fecha fiscal y puntos de venta concretos.

### Sincronizacion de puntos WSFE 2026-05-10

- Se verifico un emisor privado: ARCA produccion devuelve puntos por
  `FEParamGetPtosVenta` con `Bloqueado=N` y sin fecha de baja.
- La base local los tenia creados solo con numero, sin `sistema` ni
  `es_webservice`, por lo que FactuFlow los mostraba como `Otro sistema`.
- Se ajusto `Sincronizar con ARCA` para que los puntos devueltos por WSFE se
  creen o actualicen como Web Services activos, no bloqueados y usables por
  FactuFlow.

### Progreso real de lotes con timer 2026-05-10

- `POST /api/lotes-comprobantes/{lote_id}/procesar` acepta
  `background=true`. La UI lo usa siempre para poder seguir tambien lotes
  chicos por polling.
- La confirmacion fiscal sigue siendo obligatoria: el endpoint rechaza la
  emision si falta `X-Confirmacion-Fecha-Fiscal: true`.
- El procesamiento actualiza contadores del lote despues de cada grupo:
  emitidos, fallidos, validos restantes y mensaje de avance.
- La pantalla de emision masiva muestra avance real, estado `En cola`/
  `Procesando`, emitidos, fallidos, pendientes, tiempo transcurrido y estimado
  restante.
- Verificacion controlada sin emision real: se agregaron tests con
  `FacturacionService.emitir_comprobante` mockeado para lote chico background,
  contadores parciales, bloqueo sin confirmacion fiscal y toma atomica.
  Tambien se agregaron tests frontend para calculo de progreso, timer y ETA.

### Perfiles de carga masiva por emisor 2026-05-09

- Se agregaron perfiles de carga masiva por emisor activo, separados de los
  formatos de importacion. El formato interpreta columnas; el perfil precarga la
  pantalla de lotes con decisiones operativas visibles.
- Cada emisor puede tener varios perfiles de carga masiva. Si tiene uno solo,
  se aplica automaticamente en `Emision masiva`; si tiene varios, se aplica el
  predeterminado; si no hay predeterminado, no se aplica ninguno.
- `Emisores` ahora tiene pestaña `Carga masiva` para crear, editar, eliminar y
  marcar perfiles como predeterminados.
- Un perfil de carga masiva puede recordar formato de importacion opcional,
  punto de venta, concepto fiscal ARCA, descripcion facturada y reglas relativas
  de fechas como `ultimo_dia_mes_anterior`, `mes_anterior_completo`,
  `mismo_dia_emision` o `emision_mas_dias`.
- Por regla fiscal critica, el perfil de carga masiva no permite guardar
  `fecha_actual` como fecha de emision: no debe convertir la fecha del navegador
  en fecha fiscal.
- Las reglas relativas se resuelven en la UI a fechas concretas antes de
  validar. El backend de lotes sigue recibiendo `archivo` o `fija` con fecha
  concreta, y guarda snapshot del perfil aplicado en `metadata_json` solo si el
  usuario no modifico la configuracion precargada antes de validar.
- No se modifico la barrera fiscal: el perfil no valida ni emite
  automaticamente, y el procesamiento de lote sigue exigiendo el modal final de
  fecha fiscal y `X-Confirmacion-Fecha-Fiscal: true`.
- QA visual local completada en `http://127.0.0.1:8080`: creacion, edicion,
  eliminacion, marcado predeterminado, autoaplicacion por emisor, cambio manual
  que anula snapshot, validacion de un Excel privado local y modal final
  `Confirmar fecha fiscal` con fecha `30/04/2026` y puntos de venta concretos.
  No se presiono la confirmacion de emision.

### Consistencia por emisor activo 2026-05-09

- Se corrigio el scoping multiemisor de Clientes: la API lista, crea, obtiene,
  actualiza y elimina clientes solo dentro del emisor activo resuelto por
  `X-Empresa-Id`; la UI recarga el listado al cambiar el selector.
- Se corrigio Comprobantes para listar contra el emisor activo y recargar al
  cambiarlo, evitando datos stale cuando un admin alterna entre CUITs.
- Se corrigieron los reportes `Ventas`, `IVA ventas` y `Ranking de clientes`:
  usan `empresaActivaId` como fuente unica y, si ya habia un reporte visible,
  lo regeneran al cambiar el emisor activo.
- Se corrigio `Nueva factura` para cargar puntos de venta, proximo numero,
  cliente y preview desde el emisor activo. Si cambia el emisor mientras se
  edita, se limpia el cliente seleccionado para evitar mezclar datos.
- QA visual con usuario local de desarrollo en `http://127.0.0.1:18082`: Dashboard,
  Clientes, Comprobantes, Emision masiva, Certificados, Puntos de venta, Nueva
  factura y los tres reportes vuelven a consultar con el `X-Empresa-Id`
  correspondiente al selector.

### Control explicito de fechas fiscales 2026-05-08

- Se detecto un riesgo critico antes de la primera prueba productiva: el backend
  usaba la fecha del dia como `CbteFch` y fecha persistida, lo que podia emitir
  comprobantes con periodo fiscal incorrecto al cargar extractos de otro mes.
- Se cambio el contrato de emision para exigir `fecha_emision` explicita; ya no
  se usa `date.today()` como fecha fiscal por defecto.
- La emision masiva ahora exige elegir antes de validar si la fecha de emision
  sale del archivo o si se fija una fecha para todo el lote.
- Para comprobantes de servicios, la pantalla tambien exige definir como se
  resuelven fecha desde, fecha hasta y vencimiento de pago: desde el archivo o
  como fechas fijas.
- La validacion de lotes marca como observados los comprobantes cuya fecha de
  emision queda fuera de la ventana ARCA antes de permitir emitir.
- La columna `Fecha` de extractos bancarios se conserva como fecha de origen y
  puede usarse como fecha de emision solo si el usuario lo confirma.
- La importacion reconoce fechas del archivo aunque Excel las entregue como
  serial numerico, caso detectado con evidencia local privada.
- Se agregaron pruebas automatizadas para impedir que un extracto con fecha fuera
  de ventana quede listo para emitir.
- Se corrigio una validacion critica de puntos de venta en emision: ARCA devuelve
  `Bloqueado=N`/`S` en `FEParamGetPtosVenta`, y FactuFlow ahora interpreta `N`
  como punto habilitado. El fallo anterior hacia que la emision rechazara puntos
  validos como `6`, `10` y `13` durante el procesamiento del lote.
- Se corrigio el armado WSFE para Factura C: ARCA rechaza el objeto `Iva` en
  comprobantes tipo C, incluso si la alicuota es 0. FactuFlow ya no envia ese
  bloque para tipos `11`, `12` y `13`, y valida que esos comprobantes no tengan
  items con IVA distinto de 0.
- Se ajusto la idempotencia de lotes para reintentos seguros: si un lote previo
  quedo `fallido` o `con_errores` y no emitio ningun comprobante, el mismo
  archivo puede volver a validarse sin borrar historial. Si el lote ya esta
  validado para emitir o emitio al menos un comprobante, el duplicado sigue
  bloqueado.
- Primera emision productiva real ejecutada: lote `11` con 20 grupos autorizados
  y CAE. Se detecto concurrencia durante el procesamiento local que genero
  comprobantes adicionales no asociados al lote, por lo que quedaron 39
  comprobantes productivos autorizados en total. Se agrego transicion atomica
  para que un lote no pueda tomarse dos veces para emision.
- Se preparo la correccion operativa de los 19 comprobantes productivos
  duplicados: FactuFlow ya soporta notas de credito/debito con comprobante
  asociado informado a WSFE como `CbtesAsoc`.
- Se genero un Excel privado local con 19 Nota de Credito C, una por cada factura
  duplicada a anular. El archivo se valido contra una copia de la base local,
  sin emitir ni registrar el lote en la base operativa: `19` grupos validos,
  `0` errores y `0` emitidos. Los importes quedan en evidencia local privada.
- El usuario proceso ese archivo privado en produccion. Verificacion posterior
  solo lectura: lote `12` quedo `completado`, `19` grupos autorizados,
  `0` fallidos y `0` con error.
- Se consultaron en ARCA produccion por `FECompConsultar` las 19 Nota de Credito
  C emitidas. Todas devolvieron `Resultado=A`, CAE coincidente, fecha
  `20260508`, importe coincidente y `CbtesAsoc` apuntando a la Factura C
  duplicada esperada.
- Incidente critico: esas 19 Nota de Credito C quedaron emitidas con fecha de
  emision `08/05/2026`. Para evitar que vuelva a ocurrir, la regla del proyecto
  queda reforzada: nunca usar la fecha del dia como default fiscal y mostrar
  siempre una confirmacion final antes de solicitar CAE:
  `Está seguro que quiere emitir comprobantes con fecha XX/XX/XX? Recuerde que luego no podrá emitir comprobantes con fecha anterior para ese mismo punto de venta.`
- La confirmacion final ya no queda solo en la UI: `POST /api/comprobantes/emitir`
  exige `confirmacion_fecha_fiscal=true` y
  `POST /api/lotes-comprobantes/{lote_id}/procesar` exige
  `X-Confirmacion-Fecha-Fiscal: true`.
- Se corrigio el parser local de `FECompConsultar`: ARCA devuelve
  `CbteDesde`/`CbteHasta` en la consulta de comprobante, no `CbteNro`.
- Regla critica nueva de alineacion documental: FactuFlow no debe asumir
  productos ni servicios por defecto. Antes de emitir, el usuario debe elegir
  `Productos`, `Servicios` o `Definido por archivo`.
- Si el concepto se define por archivo, el Excel debe traer una columna valida
  con `Producto` o `Servicio` en todas las filas. Si la columna falta o algun
  valor es invalido, se informa al usuario y el lote no queda listo para emitir.
- Alineacion documental agregada: el `tipo de concepto fiscal ARCA` no es la
  descripcion facturada del item. `Productos`/`Servicios` define reglas WSFE,
  ventanas de fecha y fechas de servicio; textos como `Honorarios`,
  `Zapatillas` o `Servicio mensual` son descripcion/concepto facturado del
  item.
- Ambos datos deben quedar definidos antes de validar o emitir un lote: pueden
  venir de columnas del archivo o fijarse como valor unico para todo el lote.
  No debe haber defaults ocultos de concepto fiscal ni de descripcion de item.
- Los lotes validados antes de guardar la politica explicita de concepto quedan
  bloqueados al procesar y deben revalidarse antes de emitir.
- Los lotes validados antes de guardar la politica explicita de descripcion
  facturada tambien quedan bloqueados al procesar y deben revalidarse antes de
  emitir.
- Si la fecha tomada del archivo queda fuera de la ventana ARCA, el usuario debe
  elegir por pantalla una fecha permitida por el web service antes de emitir.

### Alineacion de formatos de importacion 2026-05-08

- Se documento la nueva capacidad de formatos de importacion configurables para
  emision masiva.
- El flujo soporta formatos globales y formatos particulares del emisor activo.
- La carga de Excel detecta encabezados y calcula candidatos. Si la coincidencia
  es de alta confianza, el formato sugerido queda preseleccionado para que el
  usuario solo lo cambie si no esta de acuerdo; si no hay sugerencia confiable,
  se exige elegir formato antes de validar.
- Si el analisis automatico de encabezados no ocurre por timing de la pantalla,
  la UI bloquea `Validar lote` y ofrece `Analizar encabezados` como reintento
  manual.
- Los mapeos soportan origen por encabezado, por columna fija o por constante.
- El lote persiste encabezados detectados, mapeo usado y version de formato para
  trazabilidad.
- El formato global inicial cubre extractos bancarios de creditos con columnas
  `Fecha`, `Créditos`, `Leyendas Adicionales1`, `Leyendas Adicionales2` y
  `Pto Vta`.
- Ese formato global usa Factura C e IVA `0`, pero no debe definir por defecto
  ni el concepto fiscal ARCA ni la descripcion facturada del item. El usuario
  debe elegir si cada dato sale del archivo o se fija para todo el lote antes de
  validar. Se valida solo para emisores Exento/Monotributo; un emisor
  Responsable Inscripto debe usar un formato particular con Factura A/B.
- Se configuro en la base local un formato particular para un emisor Responsable
  Inscripto privado: `Factura B IVA 21%`, version `5`. La muestra privada local
  se detecta con confianza alta y mapea
  `Fecha`, `Punto de Venta`, `Imp. Neto Gravado`, `Imp. Total` y
  `Nro. Doc. Receptor`. Como la muestra no trae numero de documento real, el
  receptor se trata como consumidor final sin documento cuando el importe queda
  bajo el umbral legal.
- El importador de formatos externos ahora permite mapear `item_precio_unitario`
  separado de `importe_total`. Esto permite usar neto gravado como precio del
  item y total solo como referencia para reglas de consumidor final, evitando
  recalcular IVA sobre un total ya incluido.
- Se agrego una validacion de consistencia para formatos externos: si el archivo
  trae un total informado, el total calculado por FactuFlow desde items e IVA
  debe coincidir con ese total. Si no coincide, el grupo queda con error y no se
  puede emitir. Esto bloquea el caso en que `Imp. Total` se use por error como
  neto gravado.
- Incidente con emisor Responsable Inscripto privado: se detectaron 1113
  Factura B emitidas con `Imp. Total` usado como neto y por lo tanto con 21%
  agregado de mas. Se preparo un Excel privado local
  con 1113 Nota de Credito B asociadas.
  El archivo se valido contra una copia de la base local: 1113 grupos validos,
  0 errores y 0 emitidos.
- La validacion del lote queda separada de la emision: revisar y confirmar
  `Emitir comprobantes validos` sigue siendo obligatorio antes de consumir
  numeracion fiscal.
- Quedo evidencia de QA visual local para este nuevo flujo con un extracto chico:
  deteccion del formato bancario, confirmacion obligatoria del formato,
  validacion de 3 comprobantes en puntos de venta `6`, `10` y `13`, y
  `Ya emitidos = 0`. Antes de produccion sigue faltando repetirlo con el lote
  definitivo y confirmar explicitamente la emision.

### Verificacion operativa segura 2026-05-07

- Se reviso la base local privada sin exponer claves ni
  certificados. Resultado:
  - emisor productivo privado cargado
  - certificado productivo activo para ese emisor, vencimiento `2028-05-04`
  - puntos Web Services usables `6`, `8`, `10`, `12`, `13` y `14`
  - puntos Web Services bloqueados `7` y `9`
  - lote QA privado en estado `validado`, no emitido
- Se verifico por API local, sin emitir comprobantes:
  - `POST /api/certificados/verificar-conexion/3` con `X-Empresa-Id: 2`
    devolvio `Conexion exitosa con ARCA`
  - `GET /api/arca/test-conexion` devolvio `status=ok`, ambiente
    `produccion` y servidores `OK`
  - `GET /api/arca/puntos-venta` devolvio `6`, `8`, `10`, `12`, `13` y `14`
    no bloqueados, y `7`, `9` bloqueados
  - `GET /api/arca/ultimo-comprobante/6/6` devolvio ultimo comprobante `0` y
    proximo `1` para Factura B en punto de venta `6`
- Conclusion operativa: no falta configurar desde cero certificado productivo,
  autorizacion `wsfe` ni puntos de venta Web Services. Falta confirmar el punto
  de venta elegido, preparar el lote definitivo, verificar backup/logs y emitir
  la primera prueba real controlada.

### Verificacion automatizada 2026-05-07

- Backend:
  - `pytest tests -q`: 110 passed
  - `ruff check app tests`: OK
  - `black --check app tests`: OK
- Frontend:
  - `npm run lint:check`: 0 errores, 413 warnings de estilo Vue existentes
  - `npm run type-check`: OK
  - `npm run build`: OK
  - `npm run test:unit`: OK, sin archivos de test unitarios
  - Prueba visual local: OK en `http://localhost:8080/comprobantes/lotes`
    subiendo un Excel QA privado, seleccionando el formato
    global de extracto bancario y validando sin emitir
  - `npm run test:e2e`: no confiable en esta corrida; Playwright mostro la
    pantalla en blanco dentro del runner aunque `http://localhost:8080/login`
    cargo correctamente con un script Playwright directo. No usar esta corrida
    como evidencia funcional hasta corregir el setup E2E.

### Verificacion tecnica 2026-05-08 - fechas y concepto fiscal

- Backend:
  - `pytest tests -q`: 128 passed
  - `ruff check app tests`: OK
  - `black --check app tests`: OK
  - prueba real con Excel privado local: 20 filas, fecha de archivo
    `06/04/2026`; al elegir servicios el lote `id=7` queda observado con 20
    grupos con error por ventana ARCA; no se emitio ningun comprobante
  - prueba segura posterior con Excel privado local: al elegir descripcion
    desde archivo el backend rechaza la validacion porque el Excel no trae
    columna de descripcion facturada; al elegir descripcion fija de prueba
    `Honorarios`, el lote `id=8` queda con 20 grupos con error por ventana ARCA,
    0 validos, descripcion persistida `Honorarios` y 0 comprobantes emitidos
- Frontend:
  - `npm run lint:check`: 0 errores, 440 warnings de estilo Vue existentes
  - `npm run type-check`: OK
  - `npm run build`: OK
  - `npm run test:unit`: OK, sin archivos de test unitarios
  - Revision visual basica en navegador: la ruta
    `http://localhost:8080/comprobantes/lotes` carga correctamente; al subir un
    Excel privado local muestra los controles `Tipo de concepto fiscal ARCA
    obligatorio`, `Descripcion facturada obligatoria`, las opciones de
    descripcion desde archivo o fija, y la columna `Descripcion facturada` en la
    grilla previa a emision.

### Preparacion produccion 2026-05-04

- Se separo Docker local de Docker produccion.
- Se adopto PostgreSQL como base recomendada para operacion real.
- Se agregaron constraints de integridad para numeracion e idempotencia de lotes.
- Se agrego worker de lotes reanudable desde estados persistidos.
- Se endurecio la validacion de IVA en Excel.
- Se ampliaron limites default de lotes a `20000` filas y `5000` comprobantes.
- Se agrego el comando `python -m app.scripts.create_admin_user` para crear o
  promover un usuario propietario/administrador en la base configurada.
- Se ajusto la UI para hablar de `Emisor activo` / `Emisores` y se agrego
  alta de nuevos emisores desde la pantalla fiscal.
- El alta de emisores permite subir una constancia de inscripcion ARCA en PDF
  para precompletar los campos fiscales antes de guardar. Desde 2026-05-10
  tambien acepta constancias de opcion de Monotributo y constancias de
  inscripcion de persona fisica con layout distinto al societario.
- Se corrigio el listado/alta de puntos de venta para que usuarios admin operen
  solo sobre el emisor activo seleccionado.
- Se corrigio certificados para que usuarios admin solo vean, creen y verifiquen
  certificados del emisor activo seleccionado.
- El listado de certificados expone `Probar conexion` por certificado para
  validar el certificado productivo contra ARCA antes de emitir comprobantes
  reales.
- El wizard de certificados ahora agrega un paso previo a la verificacion para
  confirmar la autorizacion del servicio `wsfe` en ARCA. En produccion se hace
  desde `Administrador de Relaciones de Clave Fiscal`; sin esto ARCA devuelve
  "Computador no autorizado a acceder al servicio".
- El certificado productivo del emisor real privado quedo probado desde la UI
  con resultado `Conexion exitosa con ARCA`.
- El backend local se reinicio en `ARCA_ENV=produccion` para continuar con la
  prueba real. La sincronizacion productiva de puntos de venta devolvio `6`,
  `8`, `10`, `12`, `13` y `14` habilitados; `7` y `9` vinieron bloqueados y no
  se importaron.
- Se agrego transporte SOAP con TLS `SECLEVEL=1` para endpoints legacy de ARCA
  que en produccion pueden fallar con `DH_KEY_TOO_SMALL`.
- Se agrego importacion de constancia PDF de puntos de venta ARCA. La constancia
  privada importo los 14 puntos con sistema, domicilio y nombre
  fantasia; FactuFlow distingue usables Web Services de Factuweb, Comprobantes
  en Linea y Controlador Fiscal, e indica bloqueados.
- La emision masiva ahora toma el receptor desde el Excel sin exigir cliente
  precargado. Para consumidor final en comprobantes B/C de importe menor a
  `$10.000.000`, acepta documento y razon social vacios, normaliza a
  `A CONSUMIDOR FINAL`, tipo documento `99` y numero `0`, y no crea un cliente
  persistente.
- Los comprobantes guardan snapshot fiscal del receptor
  (`receptor_tipo_documento`, `receptor_numero_documento`,
  `receptor_razon_social`, `receptor_condicion_iva`, `receptor_domicilio`) para
  que PDFs, listados y reportes no dependan de editar un cliente luego de emitir.
- La base SQLite local privada fue ajustada manualmente por ser legacy; se dejo
  backup local ignorado por Git y `alembic_version` quedo en `e5f6a7b8c9d0`.

### QA homologacion 2026-04-10

- Se completo la QA manual de las pantallas pendientes.
- Se emitio un comprobante individual real desde la UI.
- Se emitio un lote real desde la UI.
- Se corrigieron bugs reales de integracion ARCA detectados durante la QA.
- Se reemplazaron placeholders visibles del dashboard y de `Mi Empresa`.
- Se dejaron verdes nuevamente los tests backend y frontend.

## Resultados reales de homologacion

### Smoke previo documentado (2026-03-09)

- Emision individual
  - Punto de venta: `5`
  - Tipo: `Factura B`
  - Numero: `1`
  - CAE: registrado en evidencia local privada
  - Vencimiento CAE: `2026-03-19`
- Emision masiva
  - Grupo `SMOKE-LOTE-001`
    - Numero: `2`
    - CAE: registrado en evidencia local privada
  - Grupo `SMOKE-LOTE-002`
    - Numero: `3`
    - CAE: registrado en evidencia local privada

### QA real ejecutada hoy (2026-04-10)

- Emision individual desde UI
  - Punto de venta: `5`
  - Tipo: `Factura B`
  - Numero: `4`
  - CAE: registrado en evidencia local privada
  - Vencimiento CAE: `2026-04-19`
- Emision masiva desde UI
  - Grupo `QA-LOTE-20260410-001`
    - Numero: `5`
    - CAE: registrado en evidencia local privada
  - Grupo `QA-LOTE-20260410-002`
    - Numero: `6`
    - CAE: registrado en evidencia local privada

## QA manual cerrada

Quedo validado manualmente:

- Dashboard con metricas vivas:
  - `Total Clientes = 7`
  - `Comprobantes del Mes = 3`
  - `Ultimo Comprobante = 0005-00000006`
  - `Estado Certificado = Valido`
- Comprobantes:
  - listado con comprobantes reales
  - detalle correcto
  - `Ver PDF`
  - `Descargar PDF`
- Nueva factura:
  - preview
  - emision real con CAE
- Emision masiva:
  - descarga de plantilla
  - validacion de Excel
  - confirmacion antes de emitir
  - emision real
  - descarga de archivo observado
- Emision masiva productiva preparatoria:
  - lote QA privado validado desde API/UI para emisor real privado
  - receptor `A CONSUMIDOR FINAL`, documento `0`
  - punto de venta `6`, total estimado `$1.210,00`
  - no se emitio comprobante real; quedo listo para emitir como prueba visual
- Clientes:
  - listado correcto
  - clientes autocreados por lote visibles
- Reportes:
  - ventas por periodo
  - IVA ventas
  - ranking de clientes
- Certificados:
  - listado y vigencia correctos
- Puntos de venta:
  - listado correcto
  - sincronizacion con ARCA corregida y validada
- Mi Empresa:
  - formulario operativo
  - guardado real contra API

## Bugs resueltos en esta sesion

- Resolucion de paths legacy de certificados:
  - la base podia guardar `certs/...` y el runtime concatenaba `CERTS_PATH` de forma incorrecta
  - se corrigio para aceptar path absoluto, filename simple y valores legacy
- `GET /api/comprobantes/proximo-numero/...`:
  - fallaba en UI porque el certificado no se resolvia bien
  - impacto: bloqueaba `Nueva factura`
  - estado: corregido
- `GET /api/arca/puntos-venta`:
  - usaba el CUIT del certificado en lugar del CUIT de la empresa activa
  - impacto: `Sincronizar con ARCA` devolvia `500`
  - estado: corregido y revalidado manualmente
- Validacion de puntos de venta durante emision:
  - interpretaba `Bloqueado=N` de ARCA como valor truthy y rechazaba puntos
    validos en produccion
  - impacto: lotes con puntos `6`, `10` o `13` podian fallar al emitir aunque
    `GET /api/arca/puntos-venta` los mostrara no bloqueados
  - estado: corregido y cubierto con tests unitarios
- Sincronizacion visual de puntos Web Services:
  - `Sincronizar con ARCA` creaba puntos nuevos solo con numero, sin marcarlos
    como Web Services
  - impacto: emisores privados mostraban puntos devueltos por ARCA como
    `Otro sistema` aunque ARCA los devolviera habilitados para WSFE
  - estado: corregido en frontend; una nueva sincronizacion actualiza registros
    existentes incompletos
- Armado de IVA para Factura C:
  - el request ARCA enviaba `Iva: { AlicIva: [...] }` con alicuota 0
  - impacto: ARCA rechazaba con `[10071] Para comprobantes tipo C el objeto IVA
    no debe informarse`
  - estado: corregido y cubierto con tests unitarios
- Reintento de lotes sin CAE emitido:
  - el bloqueo por archivo duplicado tambien impedia revalidar el mismo archivo
    despues de un fallo tecnico en ARCA sin comprobantes emitidos
  - impacto: habia que limpiar historial manualmente para volver a intentar
  - estado: corregido; conserva el lote previo y libera el hash solo si no hubo
    grupos emitidos
- Concurrencia en procesamiento de lotes:
  - durante la primera prueba productiva quedaron procesos backend viejos y se
    disparo procesamiento concurrente del lote
  - impacto: se autorizaron comprobantes adicionales reales antes de que el lote
    terminara de reflejar el resumen correcto
  - estado: se agrego toma atomica de lote; si ya esta procesando o procesado,
    una segunda ejecucion queda bloqueada
- Estrategia de schema local:
  - `run-local.ps1` ahora ejecuta `alembic upgrade head` antes de levantar
    `uvicorn`
  - `backend/app/main.py` ya no ejecuta `create_all` en `development`; queda
    limitado a `test`/`testing`
  - estado: Alembic queda como camino normal de schema para arranque local y
    productivo
- Nomenclatura ARCA:
  - se corrigieron textos visibles y docstrings/comentarios conceptuales que
    todavia usaban AFIP
  - en la app actual quedan menciones solo como URLs oficiales heredadas,
    variables legacy `AFIP_*` o carpeta legacy `backend/app/afip/`
- Versionado:
  - la version de producto visible queda en `APP_VERSION` /
    `settings.app_version`: `0.2.0-mvp`
  - el frontend npm queda sincronizado a version tecnica semver `0.2.0`
  - la UI mantiene `FactuFlow v0.2.0-mvp` como version de producto
- Dashboard:
  - `Comprobantes del Mes`, `Ultimo Comprobante` y `Estado Certificado` estaban hardcodeados
  - estado: corregido
- `Mi Empresa`:
  - era una pantalla placeholder
  - estado: reemplazada por formulario operativo conectado a la API
- E2E frontend:
  - habia flakiness en Firefox por esperas de navegacion
  - estado: corregido

## Verificacion automatizada vigente

- Backend:
  - `pytest tests -q` OK, 128 tests
  - `ruff check app tests` OK
  - `black --check app tests` OK
- Frontend:
  - `npm run lint:check` OK sin errores, 444 warnings de estilo Vue existentes
  - `npm run type-check` OK
  - `npm run build` OK
  - `npm run test:unit` OK, sin casos definidos
  - `npm run test:e2e` no queda como evidencia vigente hasta corregir el setup
    del runner; ver seccion `Verificacion automatizada 2026-05-07`

## Riesgos / pendientes inmediatos

- La base local privada sigue siendo evidencia legacy
  ajustada manualmente; para nuevas instalaciones y operacion real, el camino
  canonico de schema es Alembic.
- El formato global de extracto bancario ya tiene QA visual local sin emision.
  Falta repetirlo con el lote definitivo antes de usarlo en produccion y falta
  QA manual de formatos particulares creados para un emisor.
- Falta definir con el usuario/contador la descripcion facturada real que se
  usara en el lote productivo si el archivo no trae columna de descripcion.
- Las 19 notas de credito del Excel privado local ya fueron emitidas y
  verificadas por consulta ARCA. Mantener como evidencia la fecha de emision
  `08/05/2026` y el periodo de servicios `01/04/2026 - 30/04/2026`.
- No existe todavia descarga masiva de PDFs en ZIP.
- Los emisores existentes deben completar `Ingresos Brutos` si quieren que ese
  dato figure informado en PDFs nuevos; mientras tanto el PDF lo muestra como
  `No informado`.
- Falta el tramo operativo de cierre antes de la primera emision productiva:
  - confirmar punto de venta a usar para el primer CAE real
  - definir/importar el lote chico definitivo, idealmente validando el formato
    de extracto bancario si ese sera el origen real
  - checklist de backup / logs / restauracion
- Para produccion usar `docker-compose.prod.yml`, PostgreSQL y `.env.production` basado en `.env.production.example`.

## Estado de salida

- Homologacion: lista y validada.
- Producto local: listo para un primer piloto controlado.
- Produccion real: certificado productivo, autorizacion `wsfe` y puntos de venta
  Web Services del emisor real quedaron verificados. Falta ejecutar la primera
  prueba controlada con lote chico.

## Punto exacto para retomar

Cuando se quiera avanzar a la primera prueba real en produccion:

1. Confirmar el punto de venta Web Services a usar en la primera prueba real.
2. Preparar un Excel chico definitivo, idealmente 10 a 20 comprobantes o menos.
3. Si el origen es bancario, repetir la validacion con el lote definitivo,
   confirmar el formato, elegir concepto fiscal ARCA, definir la descripcion
   facturada del item, elegir fechas fiscales permitidas por ARCA y revisar
   totales/puntos de venta antes de emitir.
4. Verificar backup/logs antes de emitir.
5. Ejecutar una prueba controlada de bajo importe con evidencia.
