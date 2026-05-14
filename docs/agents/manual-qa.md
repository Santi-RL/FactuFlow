# QA manual

Ultima actualizacion: 2026-05-14

Este archivo registra el avance real de la prueba manual de la interfaz. Si una sesion queda a mitad de camino, se retoma desde aca.

## Preparacion

Levantar el proyecto:

```bash
powershell -ExecutionPolicy Bypass -File .\run-local.ps1
```

Entornos esperados:
- Frontend: `http://localhost:8080`
- Backend: `http://localhost:8000`

## Acceso local usado

Solo para entorno local de desarrollo:
- Usuario QA automatizable: definido en la base local privada.
- Contrasena QA local: definida en la base local privada.

Para crear o promover un usuario propietario local, usar:

```bash
cd backend
.venv\Scripts\python.exe -m app.scripts.create_admin_user
```

Si deja de funcionar, validar la base local o resetear la clave con el mismo comando.

## Recorrido ejecutado y validado

### PDF profesional y QR ARCA - verificacion tecnica 2026-05-14

- Se actualizo el PDF de comprobante para presentacion administrativa
  profesional, sin copiar el formato oficial de ARCA.
- El PDF muestra bloques de emisor, receptor, operacion, detalle, totales, CAE,
  vencimiento CAE, leyenda ARCA y QR.
- `Emisores` y el setup inicial permiten cargar `Ingresos Brutos`; el PDF lo
  muestra si esta informado y, para emisores anteriores, indica `No informado`.
- Los comprobantes nuevos guardan fechas de servicio y vencimiento de pago para
  mostrarlas en el PDF cuando corresponda.
- El QR se verifico por test decodificando el Base64 de la URL y comparando el
  payload con los campos requeridos por ARCA.
- Pendiente de QA visual: abrir un PDF real desde la UI y revisar legibilidad en
  preview/descarga con un comprobante autorizado.

### Formato Roldan - Factura B IVA 21% - QA 2026-05-11

- Se creo el formato particular `Roldan - Factura B IVA 21%` para
  `ROLDAN GONZALO MATIAS` y se vinculo al perfil predeterminado del emisor.
- El formato toma `Imp. Neto Gravado` como neto del item y usa `Imp. Total`
  solo como control de consistencia.
- El Excel privado revisado trae 1432 filas utiles, todas `Factura B`, fecha de
  origen `28/02/2026`, receptor sin identificacion y columna `Punto de Venta`
  vacia. Para la QA se uso el punto fijo `5` del perfil del emisor.
- Validacion segura en copia de la base local, sin presionar ni ejecutar
  procesamiento de emision: 1432 grupos validos, 0 observados, 0 emitidos.
- La prueba negativa con `Imp. Total` usado como neto quedo bloqueada por la
  validacion de consistencia: 1432 grupos con error y 0 emitidos.
- El detalle del lote validado ahora muestra `Totales listos para emitir` antes
  del avance y antes de confirmar emision: neto, IVA 21%, IVA 10,5% y total.
  Verificacion automatizada frontend: el helper suma solo grupos validados y
  reproduce el redondeo por comprobante.

### Progreso de lotes con timer - verificacion controlada 2026-05-10

- Se implemento seguimiento real de emision para lotes chicos y grandes: la UI
  inicia el procesamiento con `background=true` y consulta el lote por polling.
- La barra de avance muestra comprobantes procesados sobre emitibles, emitidos,
  fallidos, pendientes, tiempo transcurrido y estimado restante.
- Mientras el lote esta `En cola` o sin primer comprobante procesado, la barra
  usa animacion indeterminada y muestra `Estimando...`.
- Verificacion sin emision real: los tests backend mockean
  `FacturacionService.emitir_comprobante`, por lo que no solicitan CAE ni
  consumen numeracion fiscal real.
- Se verifico por test que la API sigue bloqueando procesamiento sin
  `X-Confirmacion-Fecha-Fiscal: true`.
- Pendiente de QA visual opcional: levantar entorno local y confirmar en
  navegador que el modal de fecha fiscal puede cancelarse con `Volver a revisar`
  y que la barra avanza durante un lote mockeado o de homologacion controlada.

### Perfiles de carga masiva - QA 2026-05-09

Validado visualmente en `http://127.0.0.1:8080` con usuario local privado:
- En `Emisores > Carga masiva`, se creo un perfil de carga masiva con formato
  global, concepto `Servicios`, descripcion fija `Ajuste QA` y reglas relativas
  `ultimo_dia_mes_anterior`, `mes_anterior_completo` y `emision_mas_dias`.
- La UI ya no ofrece `Fecha actual` como regla persistible de fecha de emision
  del perfil de carga masiva.
- Se creo un segundo perfil de carga masiva, se marco como predeterminado, se
  edito desde modal y se elimino con confirmacion visual.
- En `Emision masiva`, el perfil de carga masiva predeterminado se aplico
  automaticamente al cambiar de emisor y al entrar a la pantalla.
- Formato, concepto fiscal ARCA, descripcion facturada y fechas quedaron
  visibles y editables antes de validar.
- Al modificar manualmente una fecha calculada, la pantalla mostro que la carga
  se validaria sin snapshot de perfil de carga masiva.
- Se valido un Excel privado local para un emisor monotributo local con
  puntos de venta QA `6`, `8`, `10`, `12` y `13`: 20 comprobantes validos,
  fecha fiscal resuelta `30/04/2026`, periodo `01/04/2026 - 30/04/2026` y
  descripcion `Ajuste QA`.
- Antes de emitir aparecio el modal `Confirmar fecha fiscal` con fecha concreta
  y puntos de venta concretos:
  `Está seguro que quiere emitir comprobantes con fecha 30/04/2026 para los puntos de venta 0006, 0008, 0010, 0012, 0013? Recuerde que luego no podrá emitir comprobantes con fecha anterior para ese mismo punto de venta.`
  Se cancelo con `Volver a revisar`; no se solicito CAE.
- El cambio de emisor activo recargo perfiles, lotes y formatos sin mezclar
  CUITs.

Actualizacion 2026-05-10:
- Los perfiles de carga masiva permiten elegir `Utilizar punto de venta definido
  en el archivo` o un punto de venta usable del emisor activo.
- Si el emisor no tiene puntos usables cargados, el modal de perfil indica que
  primero deben completarse en `Puntos de venta`.
- En `Emision masiva`, el punto de venta aplicado por perfil queda visible y
  editable antes de validar; si se elige un punto fijo, la validacion usa ese
  punto para todos los comprobantes.
- Verificacion automatizada sin emision: backend cubre perfil con punto
  habilitado, rechazo de punto no usable, sobrescritura del punto del archivo al
  validar lote y bloqueo de punto fijo no cargado. Frontend cubre resolucion de
  punto fijo desde perfil.

### Selector de emisor activo - QA 2026-05-09

- Usuario usado: cuenta QA local privada.
- Se valido en `http://127.0.0.1:18082` que al cambiar el selector de emisor
  activo las secciones vuelven a pedir datos con el `X-Empresa-Id` correcto:
  Dashboard, Clientes, Comprobantes, Emision masiva, Certificados, Puntos de
  venta, Nueva factura, Reporte de ventas, Subdiario IVA y Ranking de clientes.
- En Reportes, si ya habia un resultado visible, el cambio de emisor regenera
  el reporte con el mismo filtro para el nuevo emisor.
- En Nueva factura, el cambio de emisor recarga puntos de venta/proximo numero
  y limpia el cliente seleccionado para evitar mezclar datos entre CUITs.

### 1. Dashboard

- Cargo correctamente.
- El selector de empresa activa se vio bien.
- Se corrigieron los KPIs hardcodeados.
- Estado validado hoy:
  - `Total Clientes = 7`
  - `Comprobantes del Mes = 3`
  - `Ultimo Comprobante = 0005-00000006`
  - `Estado Certificado = Valido`

### 2. Comprobantes

- El listado mostro correctamente 6 comprobantes autorizados.
- Se verificaron columnas tipo, numero, fecha, cliente, total, estado y acciones.

### 3. Detalle de comprobante

- El detalle carga correctamente.
- Se verificaron CAE, vencimiento, cliente, items y totales.

### 4. PDF

- `Ver PDF` abre correctamente.
- Se visualizo CAE y QR.
- `Descargar PDF` descarga correctamente el archivo.
- Desde 2026-05-14 el PDF tiene nuevo diseño y requiere revalidacion visual en
  navegador antes de tomarlo como evidencia manual vigente.

### 5. Nueva factura

- Se completo el flujo real desde UI.
- Se detecto y corrigio un fallo en `proximo-numero` causado por resolucion incorrecta del path de certificados legacy.
- Resultado real:
  - `Factura B`
  - `0005-00000004`
  - CAE registrado en evidencia local privada

### 6. Emision masiva

- `Descargar plantilla` funciona.
- La validacion del lote funciona.
- El flujo mantiene la separacion entre validar y emitir: no se consume
  numeracion fiscal hasta presionar `Emitir comprobantes validos`.
- La emision del lote funciona desde UI.
- `Descargar observado` funciona sobre el lote completado.
- Se valido desde UI un lote productivo preparatorio privado con consumidor
  final sin documento para el emisor real privado. Resultado:
  `Validado`, `Listos para emitir = 1`, receptor `A CONSUMIDOR FINAL`,
  documento `0`, punto de venta `6`, total estimado `$1.210,00`. No se presiono
  `Emitir comprobantes validos`.
- Resultado real:
  - `0005-00000005` -> CAE registrado en evidencia local privada
  - `0005-00000006` -> CAE registrado en evidencia local privada

Validado localmente el 2026-05-08:
- autodeteccion asistida de formato al subir Excel externo
- preseleccion automatica del formato sugerido cuando la coincidencia es alta;
  el usuario puede cambiarlo si no esta de acuerdo
- si al subir un archivo todavia no hay encabezados analizados, la pantalla
  bloquea `Validar lote` y ofrece `Analizar encabezados` como reintento manual
- formato global `Extracto bancario - creditos IVA exento`
- mapeo de columnas `Fecha`, `Créditos`, `Leyendas Adicionales1`,
  `Leyendas Adicionales2` y `Pto Vta`
- validacion de un extracto chico con puntos de venta `6`, `10` y `13`
- la validacion quedo sin emision: `Ya emitidos = 0`
- formato particular local `Factura B IVA 21%` para un emisor Responsable
  Inscripto privado
- la muestra privada local detecta ese formato con
  confianza alta, 7 filas y punto de venta `2`; mapea `Imp. Neto Gravado` como
  precio neto del item e IVA constante `21`
- la muestra no trae numero de documento real del receptor: la columna
  `Nro. Doc. Receptor` contiene nombres y `Denominación Receptor` viene vacia,
  por lo que la prueba debe tratar esos comprobantes como consumidor final sin
  documento mientras el importe este bajo el umbral legal
- la fecha de la muestra es `30/04/2026`; al probarla el usuario debe elegir
  una politica de fecha permitida por ARCA antes de validar o emitir
- se agrego validacion anti-mapeo incorrecto: si un formato externo trae
  `Imp. Total`, el total calculado desde item e IVA debe coincidir con ese total
  antes de habilitar emision. Un formato de prueba que usa `Imp. Total` como
  neto queda observado con error de diferencia de total.
- se genero un Excel privado local con 1113 Nota de Credito B para corregir el
  exceso de Factura B de un emisor Responsable Inscripto privado. Validacion
  contra copia de base local:
  1113 grupos validos, 0 errores, 0 emitidos, total `$7.288.804,44`.
- queda documentado para usuario final que, en la plantilla oficial, FactuFlow
  procesa la hoja `Comprobantes`; hojas como `Resumen` o `Control` son solo
  informativas.

Cambio critico posterior el 2026-05-08:
- la emision individual y masiva ya no debe asumir fecha del dia actual
- el lote exige definir fecha de emision antes de validar: desde archivo o fecha
  fija
- el lote no debe asumir productos ni servicios por defecto; antes de validar y
  emitir el usuario debe elegir `Productos`, `Servicios` o `Definido por archivo`
- si se elige `Definido por archivo`, el Excel debe tener una columna valida con
  `Producto` o `Servicio` en todas las filas; si falta o hay valores invalidos,
  se informa al usuario y no se habilita la emision
- el selector anterior define el tipo de concepto fiscal ARCA; no es la
  descripcion/concepto facturado del item. La descripcion del item debe
  definirse aparte, por columna del archivo o como texto fijo para todo el lote
  antes de validar, por ejemplo `Honorarios`, `Zapatillas` o `Servicio mensual`
- para servicios, el lote exige definir tambien fecha desde, fecha hasta y
  vencimiento de pago: desde archivo o fechas fijas
- la validacion observa fechas de emision fuera de ventana ARCA antes de emitir
- si la fecha del archivo queda fuera de ventana ARCA, el usuario debe elegir
  una fecha permitida por el web service antes de emitir
- se probo un Excel privado local: el archivo trae fecha `06/04/2026` como
  serial numerico de Excel; el sistema la interpreta correctamente, lo clasifica
  como servicios con el formato global vigente y bloquea los 20 comprobantes por
  estar fuera de ventana ARCA. No se emitio nada.
- se revalido ese Excel privado despues de separar descripcion facturada:
  si se elige descripcion desde archivo, el backend rechaza porque el Excel no
  trae columna de descripcion; con descripcion fija de prueba `Honorarios`, el
  lote `id=8` queda `con_errores`, 0 validos, 20 observados por fecha fuera de
  ventana ARCA y 0 emitidos.
- se reviso el archivo observado privado: el fallo de emision no era por
  puntos de venta inexistentes en el Excel, sino por una normalizacion incorrecta
  de `Bloqueado=N` devuelto por ARCA. Se corrigio la validacion para que puntos
  como `6`, `10` y `13` no se rechacen cuando ARCA los informa no bloqueados.
- se reviso el segundo fallo productivo observado: ARCA rechazo Factura C con
  codigo `10071` porque el request informaba el objeto `Iva` con alicuota 0.
  Se corrigio para no enviar `Iva` en tipos `11`, `12` y `13`, y para bloquear
  localmente Factura C con items de IVA distinto de 0.
- se corrigio el reintento de lotes: si el archivo ya fue cargado pero el lote
  termino `fallido` o `con_errores` sin ningun comprobante emitido, ahora puede
  volver a validarse el mismo archivo. El historial se conserva; solo se libera
  la clave de idempotencia del intento anterior.
- la primera prueba productiva real autorizo comprobantes con CAE. Se detecto
  procesamiento concurrente por procesos backend viejos y se corrigio la toma
  atomica del lote para impedir que una segunda ejecucion procese el mismo lote.
- se preparo un Excel privado local para anular los 19 comprobantes duplicados
  mediante Nota de Credito C. El archivo se valido contra una copia de la base
  local, sin emitir y sin registrar el lote en la base operativa: 19 grupos
  validos, 0 observados, 0 emitidos. Cada grupo incluye el comprobante asociado
  que debe enviarse a ARCA como `CbtesAsoc`.
- el usuario proceso ese Excel privado en produccion. Verificacion posterior
  sin operaciones de emision: lote `12` completado, 19 grupos autorizados,
  0 fallidos, 0 con error. `FECompConsultar` contra ARCA confirmo las 19 Nota de
  Credito C con `Resultado=A`, CAE coincidente y `CbtesAsoc` contra las facturas
  duplicadas esperadas.
- incidente critico detectado despues: las 19 Nota de Credito C quedaron
  emitidas con fecha fiscal `08/05/2026`. Desde ahora la QA manual de cualquier
  emision debe verificar que aparece el modal `Confirmar fecha fiscal` con el
  texto `Está seguro que quiere emitir comprobantes con fecha XX/XX/XX? Recuerde
  que luego no podrá emitir comprobantes con fecha anterior para ese mismo punto
  de venta.` antes de solicitar CAE.
- verificacion tecnica asociada: la API tambien bloquea emision directa si falta
  la confirmacion fiscal explicita (`confirmacion_fecha_fiscal=true` en emision
  individual o `X-Confirmacion-Fecha-Fiscal: true` en procesamiento de lotes).
- QA visual local: al subir el Excel privado, la pantalla muestra el
  selector `Tipo de concepto fiscal ARCA obligatorio`, el selector
  `Descripcion facturada obligatoria`, las opciones de descripcion desde archivo
  o fija, y la columna `Descripcion facturada` antes de emitir.

Pendiente antes de produccion:
- repetir el recorrido con el lote definitivo
- definir con el usuario/contador la fecha de emision permitida por ARCA
- antes de emitir archivos de notas de credito de emisores privados, confirmar
  explicitamente la fecha fiscal fija de emision permitida por ARCA
- definir con el usuario/contador la descripcion facturada real si no viene del
  archivo
- revisar totales, puntos de venta y formato confirmado
- emitir solo con confirmacion explicita

### 7. Clientes

- El listado carga correctamente.
- Desde 2026-05-09, el listado respeta el emisor activo tambien para usuarios
  admin y recarga al cambiar el selector.
- En el flujo legacy de homologacion se verifico que los clientes creados automaticamente por emision masiva quedaron visibles:
  - `Consumidor Final Lote Uno`
  - `Consumidor Final Lote Dos`
- Desde 2026-05-05, los lotes masivos no crean clientes persistentes por defecto
  cuando el receptor viene solo como consumidor final del Excel; el comprobante
  guarda snapshot fiscal del receptor.

### 8. Reportes

- `Ventas por periodo` carga y muestra los 3 comprobantes de abril.
- `IVA ventas` carga y refleja bases e IVA de abril.
- `Ranking de clientes` carga y ordena correctamente los clientes facturados.
- Desde 2026-05-09, los tres reportes usan el emisor activo y se regeneran al
  cambiarlo si habia un resultado visible.

### 9. Certificados

- La vista carga correctamente.
- Se visualizo certificado homologacion valido, ambiente y vencimiento.
- Se agrego accion `Probar conexion` en cada certificado para validar WSAA/ARCA
  antes de emitir, reutilizando el endpoint scopiado por emisor activo.
- Se agrego al wizard el paso previo de autorizar `wsfe` en ARCA antes de
  ejecutar `Probar conexion`.

### 10. Puntos de venta

- La vista carga correctamente.
- Se verifico el punto de venta `0005` activo.
- Durante la QA se detecto y corrigio un fallo real en `Sincronizar con ARCA`.
- Estado final: sincronizacion ejecutada con respuesta OK desde UI.
- Verificacion puntual 2026-05-10: para un emisor privado, ARCA produccion
  devolvio puntos con `Bloqueado=N` y sin fecha de baja. La UI los mostraba como
  `Otro sistema` porque habian sido sincronizados solo con numero. Se corrigio
  `Sincronizar con ARCA` para crear o actualizar puntos WSFE como Web Services
  usables.
- En preparacion productiva se sincronizaron para el emisor real los puntos
  habilitados `6`, `8`, `10`, `12`, `13` y `14`; ARCA devolvio `7` y `9`
  bloqueados.
- Se importo la constancia PDF de puntos de venta del CUIT real y se valido que
  quedan visibles sistema, domicilio, nombre fantasia, usabilidad FactuFlow y
  estado bloqueado/no bloqueado.

### 11. Mi Empresa

- La pantalla dejo de estar en placeholder.
- Se implemento formulario real contra la API.
- Se probo guardado desde UI con `PUT 200`.

## Hallazgos corregidos durante la QA

- Detalle de comprobante: faltaba `result.unique()`.
- Preview de PDF: el frontend llamaba mal la ruta.
- Proximo numero para nueva factura: path legacy de certificado mal resuelto.
- Sincronizacion de puntos de venta ARCA: helper usaba el CUIT incorrecto.
- Dashboard: KPIs hardcodeados.
- Mi Empresa: placeholder sin funcionalidad.

## Resultado

- QA manual funcional cerrada para el alcance actual del MVP en homologacion.
- El flujo de emision masiva ahora inicia desde la UI lotes chicos y grandes en
  segundo plano para poder mostrar avance real.
- La pantalla muestra estado `En cola` / `Procesando`, barra de progreso,
  emitidos, fallidos, pendientes, tiempo transcurrido y estimado restante.
- La pantalla de emision masiva permite revisar el formato detectado, confirmar
  el formato de importacion y validar antes de emitir.
- La pantalla `Emisores` permite agregar un nuevo emisor desde un modal y
  seleccionarlo como activo al crearlo.
- En el modal `Agregar emisor`, la accion `Subir constancia` procesa un PDF de
  constancia ARCA y precompleta los datos detectados sin guardar automaticamente.
- Se valido el parser con una constancia de opcion de Monotributo: detecta CUIT,
  razon social, condicion Monotributo, domicilio, localidad, provincia, codigo
  postal e inicio de actividades.
- Se valido el parser con una constancia de inscripcion de persona fisica:
  corrige cortes de texto del PDF en nombre, domicilio y localidad, detecta
  codigo postal/provincia y no completa provincia con lineas tecnicas.
- En `Emisores`, provincia se selecciona desde un catalogo cerrado de provincias
  argentinas tanto en alta como en edicion.
- Puntos de venta respeta el emisor activo: al seleccionar un emisor nuevo sin
  puntos cargados, no muestra puntos de otros emisores.
- Quedan pendientes las tareas externas de salida a produccion que no se resuelven desde esta QA local.

## Punto de reanudacion

El estado operativo canonico esta en `docs/agents/current-status.md`.

Desde la QA manual, no queda pendiente volver a configurar desde cero
certificado productivo, autorizacion `wsfe` ni puntos de venta productivos para
el emisor real: esos puntos fueron verificados en la preparacion productiva y
revalidados con checks seguros el 2026-05-07.

Retomar en la preparacion de la primera prueba real controlada:

1. Confirmar el punto de venta Web Services a usar, hoy candidato `6`.
2. Preparar o revisar el lote chico definitivo.
3. Si se usa un extracto bancario, repetir con el lote definitivo la validacion
   ya probada localmente: autodeteccion, seleccion de formato, seleccion
   explicita de concepto fiscal ARCA, definicion explicita de la descripcion
   facturada del item, seleccion explicita de fechas fiscales permitidas por
   ARCA, revision de totales y confirmacion explicita antes de emitir.
4. Verificar backup, logs y plan de restauracion.
5. Levantar o confirmar el perfil productivo con PostgreSQL usando
   `docker-compose.prod.yml`.
6. Emitir la prueba real solo con confirmacion explicita.
