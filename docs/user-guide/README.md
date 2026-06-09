# Manual de usuario - FactuFlow

Última actualización: 2026-06-09

Este manual describe el uso actual del producto. Si una funcion no aparece aca, no debe asumirse como disponible para usuarios finales.

## Contenido

1. Acceso al sistema
2. Emisor activo
3. Dashboard
4. Clientes
5. Comprobantes
6. Emision masiva
7. Reportes
8. Certificados
9. Puntos de venta
10. Emisores
11. Usuarios
12. Sistema
13. Limitaciones actuales

## 1. Acceso al sistema

En una instalacion local de Windows para desarrollo o QA, usar el acceso
`FactuFlow Local.vbs` ubicado en la carpeta del proyecto. Ese acceso inicia
FactuFlow en segundo plano sin dejar una ventana de PowerShell abierta, muestra
un icono junto al reloj de Windows y abre el navegador cuando la aplicacion esta
lista. `FactuFlow Local.cmd` queda como acceso de compatibilidad.

Estados del icono local:
- verde: FactuFlow esta listo para usar
- amarillo: FactuFlow se esta iniciando
- rojo: FactuFlow requiere atencion

Desde el icono junto al reloj puedes:
- abrir FactuFlow
- consultar el estado del sistema
- reiniciar servicios
- detener servicios
- abrir logs
- salir del launcher local

Si el icono queda rojo, usa `Estado del sistema` o `Abrir logs`. Los mensajes
estan pensados para indicar si el problema esta en el servidor local, la base de
datos, el frontend o un puerto ocupado por otra aplicacion.

Si la pantalla de inicio de sesion indica que `FactuFlow no está listo para
iniciar sesión`, hace click derecho en el icono de FactuFlow junto al reloj de
Windows y elegi `Reiniciar servicios`. Cuando el icono quede verde, presiona
`Reintentar` en la pantalla. Si no ves el icono, abre nuevamente
`FactuFlow Local.vbs`.

En una instalación en VPS o servidor, no se usa el launcher local. En ese caso
se entra desde la URL publicada de FactuFlow. FactuFlow está pensado para poder
operar en un VPS pequeño, por lo que el servidor debe conservar solo los datos
necesarios para funcionar, auditar y recuperar la operación.

En una instalación VPS publicada, el acceso debe hacerse por HTTPS. Si la base
ya tiene usuarios, la opción `Configurar sistema` no aparece: los usuarios
nuevos se crean desde `Usuarios` con una cuenta administradora.

Luego:

1. Ingresar con tu correo electrónico y contraseña.
2. Si es la primera vez y no hay un usuario creado, usar la opción `Configurar sistema`.

La opción `Configurar sistema` solo aparece cuando la instalación no tiene
usuarios. Ese flujo crea el usuario administrador propietario inicial y el
primer emisor. Cuando ya existe al menos un usuario, el alta pública queda
cerrada: los usuarios nuevos se crean desde `Usuarios`, dentro de la aplicación.

## 2. Emisor activo

Todos los usuarios activos ven en el encabezado el selector `Emisor activo`.
Este modelo está pensado para contadores independientes o estudios chicos que
gestionan varios emisores desde la misma instalación, pero siempre trabajan con
un solo emisor activo por vez.

Todo lo que hagas en estas secciones queda asociado a ese emisor:
- dashboard
- clientes
- comprobantes
- emision masiva
- certificados
- puntos de venta
- reportes
- nueva factura

Antes de emitir o consultar informacion, verifica siempre que el emisor activo sea el correcto.
Si cambias el emisor activo, las pantallas principales recargan la informacion
para mostrar solo datos de ese CUIT. En `Nueva Factura`, cambiar el emisor
recarga puntos de venta y limpia el cliente seleccionado.

El emisor activo se mantiene por pestaña del navegador. Si abres otra pestaña y
cambias de emisor, esa nueva seleccion no cambia silenciosamente una factura o
un lote que ya estabas revisando en la pestaña anterior.

Como proteccion adicional, la emision se bloquea si el punto de venta o el
cliente seleccionado no pertenecen al emisor activo.
La misma separacion aplica a certificados, comprobantes, lotes, PDFs, reportes,
perfiles de carga y formatos de importacion: no deben mezclarse entre emisores.

## 3. Dashboard

El dashboard muestra un resumen general y accesos rapidos.

Hoy informa:
- total de clientes
- comprobantes emitidos en el mes actual
- ultimo comprobante emitido
- estado del certificado activo

Desde ahi puedes ir directo a:
- nuevo cliente
- emitir factura
- emision masiva
- configurar empresa

## 4. Clientes

En `Clientes` puedes:
- crear clientes
- editar clientes
- buscar por nombre o documento

Datos habituales:
- tipo y numero de documento
- razon social o nombre
- condicion frente al IVA
- domicilio, localidad y provincia
- email y telefono si corresponden

## 5. Comprobantes

En `Comprobantes` puedes:
- ver el listado de comprobantes emitidos
- filtrar por texto, tipo o rango de fechas
- crear un comprobante puntual
- abrir el detalle de un comprobante autorizado

Al crear un comprobante puntual, el selector de punto de venta muestra solo los
puntos habilitados para emitir por FactuFlow: Web Services activos, no
bloqueados y sin fecha de baja.

Cuando confirmas la emisión final, FactuFlow genera una clave interna de
idempotencia para esa operación. Si la conexión se corta o repetís el intento
con los mismos datos, la aplicación reutiliza esa clave y el backend no vuelve
a pedir CAE para el mismo comprobante. Si cambiás datos fiscales como fecha,
punto de venta, receptor, ítems o comprobantes asociados, la operación exige una
nueva confirmación.

Si FactuFlow detecta que el comprobante se parece mucho a otro ya autorizado,
muestra una advertencia de duplicado probable. Esa advertencia no bloquea por
sí sola la emisión, pero exige una confirmación adicional antes de solicitar
CAE. Revisá especialmente receptor, fecha fiscal, punto de venta, total,
ítems y comprobantes asociados antes de continuar.

### Detalle de comprobante

El detalle muestra:
- tipo y numero
- fecha
- cliente
- items
- importes
- CAE y vencimiento

Si el comprobante esta autorizado, veras:
- `Ver PDF`
- `Descargar PDF`

### Como funciona el PDF hoy

- El PDF no se genera automaticamente al emitir.
- Se genera bajo demanda cuando usas `Ver PDF` o `Descargar PDF`.
- Esto evita guardar archivos innecesarios.
- En una instalación sobre VPS, los PDFs descargados deben quedar en la PC del
  usuario. FactuFlow no debe usarlos como almacenamiento permanente del
  servidor.
- El PDF muestra `ORIGINAL`, letra y codigo de comprobante, emisor, receptor,
  periodo facturado, detalle, totales, CAE, vencimiento CAE y QR ARCA en una
  hoja A4 con ubicaciones principales similares a la factura oficial ARCA.
- Si el receptor es consumidor final sin documento, el PDF muestra `Doc.: -`,
  y consigna `Condicion frente al IVA: Consumidor Final`; el numero `0` queda
  como dato tecnico para ARCA/QR y no se muestra como documento visible. Si el
  comprobante tiene una razon social real del receptor, el PDF la muestra; si
  solo trae un texto generico como `A CONSUMIDOR FINAL`, el nombre queda vacio.
- Si el emisor tiene `Ingresos Brutos` cargado en `Emisores`, tambien se muestra
  en el PDF. Si no esta cargado, figura como `No informado`.
- En comprobantes nuevos de servicios, el PDF muestra periodo facturado y
  vencimiento de pago cuando esos datos fueron informados al emitir.
- En comprobantes historicos emitidos por lote, una migracion reconstruye el
  periodo y vencimiento desde el payload guardado del lote cuando esos datos no
  estaban persistidos en el comprobante.

## 6. Emision masiva

La emision masiva esta pensada para cargar muchas facturas desde Excel. Puede
usar la plantilla oficial de FactuFlow o un formato de importacion configurado
para archivos externos.

Flujo general:

1. Descargar la plantilla oficial o preparar el archivo externo acordado.
2. Si existe, revisar el perfil de carga masiva aplicado para el emisor activo.
3. Subir el Excel.
4. Revisar el formato sugerido por FactuFlow.
5. Si es un archivo externo, elegir o confirmar el formato correcto.
6. Elegir si el punto de venta sale del archivo o si se fija un punto habilitado
   del emisor.
7. Elegir explicitamente si el lote corresponde a `Productos`, `Servicios` o
   `Definido por archivo`.
8. Definir la descripcion/concepto facturado del item: desde el archivo o como
   texto fijo para todo el lote.
9. Definir explicitamente la fecha de emision y, si corresponde, el periodo de
   servicios y vencimiento de pago.
10. Validar errores por fila o por comprobante.
11. Revisar comprobantes detectados, concepto fiscal ARCA, descripcion del item,
   fechas, totales listos para emitir, receptor y punto de venta.
12. Confirmar la emision con `Emitir comprobantes validos`.
13. Revisar resultados del lote.
14. Si lo necesitas, descargar el archivo observado del lote.

Validar un lote no emite comprobantes ni consume numeracion fiscal. La emision
recien ocurre cuando confirmas el lote validado.

Al confirmar la emisión de un lote, FactuFlow también usa una clave interna de
idempotencia. Esto evita que un doble click, un refresh o un retry de red vuelva
a pedir CAE para el mismo procesamiento. La clave se conserva para el retry de
la misma operación y se reemplaza si cambiás de lote, archivo, emisor o
selección de grupos.

Cuando el lote queda validado, la pantalla muestra `Totales listos para emitir`
con cantidad de comprobantes, neto, IVA 21%, IVA 10,5% y total. Compara esos
valores contra el Excel antes de presionar `Emitir comprobantes validos`.

En lotes grandes, la pantalla no muestra todos los comprobantes a la vez. El
resumen, los totales y la confirmacion fiscal se calculan sobre el lote
completo, pero la grilla de detalle carga una pagina de comprobantes por vez.
Podes cambiar de pagina o filtrar por estado para revisar listos, observados,
autorizados, fallidos o casos que requieren reconciliacion. Para revisar el
detalle completo por fila, usa `Descargar observado`.

Cuando uses la plantilla oficial de FactuFlow, el sistema lee la hoja llamada
`Comprobantes`. Las hojas adicionales, por ejemplo `Resumen` o `Control`, son
solo informativas y no se usan para emitir. Si el archivo no tiene una hoja
llamada `Comprobantes`, FactuFlow intenta leer la primera hoja del Excel.
Si el XLSX esta malformado o supera el limite operativo configurado como
`BATCH_MAX_UPLOAD_BYTES`, FactuFlow lo rechaza antes de validar el lote.

Si un lote termina `fallido` o `con_errores` sin haber emitido comprobantes,
podes volver a subir el mismo archivo para revalidarlo. FactuFlow conserva el
historial del intento anterior y solo permite el reintento cuando no hubo CAE
emitido. Si el lote ya quedo validado para emitir o emitio algun comprobante, el
archivo duplicado se bloquea para evitar facturacion repetida.

Además del bloqueo por archivo ya cargado, FactuFlow calcula duplicados lógicos
por comprobante. Si detecta comprobantes muy similares dentro del lote o contra
comprobantes locales ya autorizados, muestra una advertencia y pide una
confirmación adicional. Confirmar esa advertencia solo indica que revisaste el
riesgo de duplicado; no reemplaza la confirmación fiscal final de fecha y punto
de venta.

Si el lote queda como `Requiere reconciliación`, no lo reintentes. Ese estado
significa que ARCA pudo haber autorizado comprobantes con CAE, pero FactuFlow no
pudo terminar de guardarlos. Primero hay que consultar ARCA y reconciliar los
datos locales. Si un reintento de fallidos se interrumpe justo después de
tomar el comprobante para emisión, el grupo también queda para reconciliación:
no vuelve automáticamente a `Fallido`, porque reemitirlo podría duplicar una
autorización fiscal.

### Gestión de lotes parciales y limpieza

Cuando un lote queda con comprobantes emitidos y otros pendientes, FactuFlow
puede mostrar acciones de resolución:

- `Reintentar fallidos`: vuelve a solicitar CAE para comprobantes fallidos. La
  pantalla muestra una confirmación de fecha fiscal y punto de venta; si esos
  datos no son correctos, cancela y revisa el lote.
- `Reconciliar ARCA Web`: úsalo cuando el comprobante pendiente ya fue emitido
  manualmente desde ARCA Web. Debes cargar el comprobante visible, número
  autorizado, CAE si lo tienes y motivo operativo. FactuFlow consulta ARCA antes
  de registrar el comprobante localmente. También se usa para cerrar reintentos
  interrumpidos que quedaron pendientes de verificación.
- `Descartar visibles`: cierra comprobantes pendientes que no deben emitirse
  desde ese lote. No se usa para comprobantes con incertidumbre post-ARCA.

Estados de cierre:

- `Completado`: todos los comprobantes fueron emitidos por FactuFlow.
- `Cerrado reconciliado`: todos quedaron autorizados, pero uno o más fueron
  emitidos fuera de FactuFlow y verificados contra ARCA.
- `Cerrado con descartes`: el lote se cerró con comprobantes descartados por una
  decisión operativa.

Para ahorrar almacenamiento en VPS pequeños, un lote cerrado puede compactarse.
Compactar elimina el detalle original por fila del Excel y conserva el resumen,
los comprobantes agrupados, los importes, el estado y la auditoría. Después de
presionar `Compactar detalle`, FactuFlow muestra una confirmación con estas
consecuencias. Si confirmas, ya no se puede descargar el archivo observado de
ese lote. No hace falta indicar un motivo: la compactación se registra como
ahorro de almacenamiento.

También puede eliminarse físicamente un lote sin emisión ni incertidumbre
fiscal, por ejemplo una carga equivocada que no llegó a emitir comprobantes.
FactuFlow no elimina lotes con comprobantes autorizados, reconciliados o
inciertos. Si el lote tiene valor fiscal o dudas sobre ARCA, debe conservarse o
cerrarse por reconciliación/descarte, no borrarse.

Cuando presionas `Emitir comprobantes validos`, el lote queda en seguimiento y
la pantalla muestra una barra de avance real. La barra informa comprobantes
procesados, emitidos, fallidos, pendientes, tiempo transcurrido y tiempo
estimado restante. Si el lote todavia esta `En cola`, el avance se muestra como
estimacion hasta que el worker empieza a procesar. Revisa el resumen final antes
de volver a intentar. El sistema bloquea una segunda ejecucion del mismo lote si
ya esta procesando o si ya fue procesado. Si un proceso queda realmente trabado,
el worker puede retomarlo solo despues de la ventana operativa configurada como
`BATCH_PROCESSING_STALE_MINUTES`.

Para acelerar lotes grandes, FactuFlow consulta a ARCA cuántos comprobantes
pueden enviarse por request (`RegXReq`) y divide la emisión en sublotes por
punto de venta y tipo de comprobante. Esto no cambia la confirmación fiscal: el
usuario sigue revisando fecha, punto de venta, concepto, descripción y totales
antes de solicitar CAE.

Si ARCA no informa la capacidad máxima por request, FactuFlow emite en modo
unitario para no bloquear la operación. En ese caso la pantalla del lote muestra
un aviso indicando que el procesamiento pudo demorar más por esa degradación.

Regla importante: FactuFlow no completa la fecha de emision con la fecha del dia
por defecto. Antes de validar un lote debes elegir si la fecha de emision sale
del archivo o si se usara una fecha fija para todos los comprobantes. Para
comprobantes de servicios tambien debes definir como se completan `desde`,
`hasta` y vencimiento de pago. Si una fecha elegida queda fuera de la ventana
que ARCA permite para autorizar comprobantes, el lote queda observado antes de
emitir. Para emitir, debes elegir una fecha permitida por el web service; el
sistema no la reemplaza automaticamente.

Antes de emitir, FactuFlow debe mostrar una confirmacion final de fecha fiscal
con este texto: `Está seguro que quiere emitir comprobantes con fecha
XX/XX/XX? Recuerde que luego no podrá emitir comprobantes con fecha anterior
para ese mismo punto de venta.` Si la fecha o el punto de venta no son los que
corresponden, cancela la emision y vuelve a revisar el lote. En lotes con mas
de una fecha o punto de venta, la confirmacion debe mostrar todos los valores
concretos; el backend solo procesa si la UI envia el token exacto calculado
desde esos grupos validados.

Regla critica de concepto fiscal ARCA: FactuFlow no asume que el lote sea de
productos o de servicios. Antes de validar debes elegir `Productos`,
`Servicios` o `Definido por archivo`. Esta decision es fiscal y define como se
arma el comprobante para ARCA, que ventana de fechas aplica y si hacen falta
fechas de servicio. Si eliges `Definido por archivo`, el Excel debe traer una
columna valida con `Producto` o `Servicio` en todas las filas. Si falta la
columna o hay un valor distinto, FactuFlow informa el problema y no deja emitir
ese lote hasta corregirlo o elegir un criterio valido.

Regla critica de descripcion del item: el concepto fiscal ARCA no es el texto
que aparece facturado en el renglon del comprobante. Textos como `Honorarios`,
`Zapatillas`, `Servicio mensual` o `Abono` son la descripcion/concepto facturado
del item. Esa descripcion tambien debe definirse antes de validar: puede venir
de una columna del archivo o fijarse como un valor unico para todo el lote. No
debe completarse con un default oculto del formato.

Los lotes viejos validados antes de esta regla deben revalidarse. FactuFlow no
permite procesarlos sin una politica de concepto fiscal guardada.

Regla de punto de venta en lotes: podés usar el punto de venta definido en el
archivo o fijar un punto habilitado del emisor. Para elegir un punto fijo, ese
punto debe estar cargado primero en `Puntos de venta` y debe figurar como usable
por FactuFlow. Si el emisor no tiene puntos habilitados cargados, la pantalla lo
indica y solo queda disponible usar el punto informado por el archivo hasta
completar la pantalla correspondiente.

Al emitir, FactuFlow vuelve a verificar en backend que el punto de venta y un
cliente precargado opcional pertenezcan al emisor activo.

### Perfiles de carga masiva

Cada emisor puede tener perfiles de carga masiva para completar mas rapido la
pantalla de emision masiva. Se administran desde `Emisores > Carga masiva`.

Un perfil de carga masiva puede recordar:
- formato de importacion opcional
- punto de venta: utilizar el definido en el archivo o fijar uno habilitado del
  emisor
- concepto fiscal ARCA
- descripcion facturada desde archivo o fija
- fecha de emision relativa, por ejemplo ultimo dia del mes anterior, o una
  fecha personalizada cargada de forma explicita
- periodo de servicios, por ejemplo mes anterior completo o mes actual completo
- vencimiento de pago, por ejemplo mismo dia de emision o emision mas una
  cantidad de dias

Si un emisor tiene un solo perfil de carga masiva, FactuFlow lo aplica al entrar
en `Emision masiva`. Si tiene varios, se aplica el marcado como predeterminado.
Si no hay predeterminado, el usuario elige uno.

El perfil de carga masiva no valida ni emite automaticamente. Solo completa la
pantalla con valores visibles. Antes de validar podes cambiar cualquier selector
o fecha. Si el perfil trae reglas relativas, FactuFlow no usa la fecha del
navegador para convertirlas automaticamente en fecha fiscal al entrar a
`Emision masiva`: antes de validar debes elegir una fecha exacta, tomarla del
archivo o confirmar explicitamente la politica fiscal de esa carga. Si cambias
un dato precargado, esa carga queda como configuracion manual y no como snapshot
del perfil de carga masiva.

Por seguridad fiscal, un perfil de carga masiva no ofrece `Fecha actual` como
regla de fecha de emision.

Para guardar un perfil con punto de venta fijo, el punto debe estar cargado en
`Puntos de venta` para ese emisor y estar habilitado para usar en FactuFlow. Si
todavia no hay puntos cargados, completalos primero desde esa pantalla.

### Formatos de importacion

La pantalla muestra formatos disponibles para el emisor activo:
- formatos globales, reutilizables por cualquier emisor
- formatos particulares de un emisor

FactuFlow lee los encabezados del Excel, muestra las columnas detectadas y
sugiere el formato con mayor coincidencia. Si la coincidencia es alta, ese
formato queda seleccionado automaticamente y podes cambiarlo si no estas de
acuerdo. Si no hay una sugerencia confiable, debes elegir el formato antes de
validar. Si los encabezados no se analizaron automaticamente, la pantalla
muestra la accion `Analizar encabezados` y mantiene bloqueada la validacion
hasta completar ese paso.

Los formatos pueden mapear datos de tres maneras:
- por encabezado, usando nombres o alias de columnas
- por columna fija, usando letra o indice cuando el archivo no tiene encabezados
  confiables
- por constante, para completar campos que siempre tienen el mismo valor

Si el archivo externo trae un total informado, FactuFlow compara ese total con
el total calculado desde los items e IVA. Si no coinciden, el comprobante queda
observado antes de emitir. Esta validacion evita usar por error una columna de
total final como si fuera precio neto.

La administracion de perfiles de carga masiva por emisor existe desde
`Emisores > Carga masiva`. La administracion avanzada de formatos de
importacion todavia se mantiene por API/configuracion; la pantalla de emision se
concentra en seleccionar y confirmar formatos ya disponibles.

### Formato privado Responsable Inscripto

Existe un formato local privado para Factura B IVA 21%. Esta pensado para
archivos con columnas como `Fecha`, `Tipo`, `Punto de Venta`,
`Imp. Neto Gravado`, `IVA` e `Imp. Total`.

El formato emite como Factura B (`tipo 6`) con IVA 21%. Usa `Imp. Neto Gravado`
como precio neto del item y `Imp. Total` como total de referencia. Como la
muestra disponible no trae numero de documento real del receptor, FactuFlow lo
trata como consumidor final sin documento cuando el importe esta bajo el umbral
legal. Si un archivo futuro trae comprobantes que requieren identificar al
receptor, se debe agregar una columna con documento real o ajustar el formato.

Si por configuracion o por archivo el total calculado no coincide con
`Imp. Total`, el lote queda observado y no se puede emitir hasta corregir el
mapeo.

La fecha del archivo no se usa automaticamente para emitir. Antes de validar el
lote hay que elegir si se toma la fecha desde el Excel o si se fija una fecha
permitida por ARCA para todo el lote.

### Formato privado con punto fijo

Existe otro formato local privado de Factura B IVA 21% vinculado a un perfil de
carga masiva con punto de venta fijo. Esta pensado para archivos con columnas
`Fecha`, `Tipo`, `Punto de Venta`, `Imp. Neto Gravado`, `IVA` e `Imp. Total`.

El formato emite como Factura B (`tipo 6`) con IVA 21%. Usa siempre
`Imp. Neto Gravado` como precio neto del item. `Imp. Total` se usa solo como
control de consistencia: si el total calculado desde neto e IVA no coincide con
el total informado por el Excel, el comprobante queda observado antes de emitir.

En el archivo privado revisado para abril 2026, la columna `Punto de Venta`
esta vacia. Por eso el perfil de carga masiva del emisor fija el punto de venta
`5`; antes de validar o emitir se debe revisar que esa seleccion sea correcta
para el lote.

### Extractos bancarios

Hay un formato global para extractos bancarios de creditos con estas columnas:
- `Fecha`: fecha de origen del movimiento, usada como fecha del archivo cuando
  el usuario elige esa opcion. FactuFlow tambien interpreta fechas que Excel
  entregue internamente como numero serial.
- `Créditos`: importe acreditado, obligatorio
- `Leyendas Adicionales1`: receptor o leyenda equivalente, opcional
- `Leyendas Adicionales2`: documento del receptor, opcional
- `Pto Vta`: punto de venta, obligatorio

Cada fila del extracto genera un comprobante. El formato global esta pensado
para emisores Exento o Monotributo y usa Factura C e IVA `0`; no crea cliente
persistente por defecto. No define por si solo si el lote es de productos o
servicios, ni que descripcion del item se va a facturar: debes elegir el tipo de
concepto fiscal ARCA y definir la descripcion facturada antes de validar. Si el
documento o receptor vienen vacios, aplican las reglas vigentes de consumidor
final. Para emisores Responsable Inscripto, el lote queda observado y se debe
crear un formato particular con Factura A/B segun corresponda.

En Factura C los items deben tener IVA 0. En nueva factura, FactuFlow limita el
selector de IVA a 0 cuando elegis Factura C; en emision masiva, los lotes tipo C
con IVA distinto de 0 quedan con error antes de emitir. FactuFlow no informa el
bloque IVA a ARCA para ese tipo de comprobante, porque el web service lo rechaza
aunque la alicuota sea cero.

### Notas de credito por lote

La plantilla oficial tambien puede usarse para notas de credito. Para Nota de
Credito C se usa `tipo_comprobante = 13`.

Cuando una nota de credito anula o ajusta una factura, el Excel debe incluir el
comprobante asociado:
- `asociado_tipo_comprobante`
- `asociado_punto_venta`
- `asociado_numero`
- `asociado_fecha`
- `asociado_cuit`

FactuFlow valida que esos datos existan antes de dejar la nota de credito lista
para emitir, y los informa a ARCA como `CbtesAsoc`. No cargues importes
negativos: el importe se carga positivo y el tipo de comprobante define que se
trata de un credito.

Si elegis servicios, no se debe emitir sin revisar el periodo de servicios. La
fecha del extracto puede usarse como fecha de emision o como base del periodo
solo si el usuario lo confirma y ARCA la admite para la fecha en que se solicita
el CAE.

Si el archivo observado informa que un punto de venta no esta habilitado, primero
contrasta `Puntos de venta > Sincronizar con ARCA`. Para el emisor real usado en
la prueba productiva, ARCA informa como no bloqueados los puntos `6`, `8`, `10`,
`12`, `13` y `14`; `7` y `9` estan bloqueados.

Si el archivo externo trae una columna para distinguir productos y servicios,
usa `Definido por archivo` solo cuando todas las filas esten completas con
`Producto` o `Servicio`. No cargues el archivo esperando que FactuFlow decida el
concepto por defecto.

Si el archivo externo trae una columna con la descripcion a facturar, usala como
descripcion del item. Si no la trae, define un texto fijo para todo el lote
antes de validar. No confundas esa descripcion con `Productos` o `Servicios`:
son datos distintos.

Reglas principales:
- un lote pertenece a un solo emisor activo
- un comprobante puede ocupar varias filas agrupadas por `comprobante_ref`
- los clientes precargados son opcionales para emision masiva
- para consumidor final en comprobantes B/C de importe menor a `$10.000.000`,
  puedes dejar vacios tipo de documento, numero, nombre y domicilio; FactuFlow
  lo normaliza como `A CONSUMIDOR FINAL`
- si el importe de consumidor final es igual o superior a `$10.000.000`, debes
  informar CUIT, CUIL, CDI, DNI, pasaporte u otro documento valido
- los comprobantes guardan una copia fiscal del receptor al emitir; editar un
  cliente despues no cambia el receptor historico del comprobante
- los errores se muestran por fila o por comprobante
- las alicuotas de IVA permitidas son `0`, `10.5`, `21` y `27`
- el concepto fiscal ARCA del lote siempre debe ser confirmado por el usuario:
  productos, servicios o definido por archivo
- la descripcion/concepto facturado del item siempre debe venir del archivo o de
  un valor fijo confirmado para el lote
- los lotes chicos y grandes se procesan con seguimiento automatico desde la UI
- la barra de progreso muestra avance, tiempo transcurrido y estimacion restante
- los lotes grandes pueden quedar `En cola` antes de pasar a `Procesando`

## 7. Reportes

La seccion `Reportes` muestra consultas basicas:
- ventas
- IVA
- ranking de clientes

Los reportes usan el emisor activo seleccionado.
Si cambias el emisor activo mientras un reporte esta cargando, FactuFlow
descarta la respuesta anterior para no mostrar datos de otro CUIT. El subdiario
IVA muestra detalle por alicuota, incluyendo gravado e IVA 27% cuando
corresponde.

## 8. Certificados

En `Certificados` gestionas los certificados de ARCA por ambiente.

Uso recomendado:
- trabajar primero en homologacion
- verificar vigencia del certificado antes de emitir
- mantener un solo certificado activo por empresa y ambiente

Las claves privadas generadas por FactuFlow quedan guardadas dentro del
directorio de certificados configurado y cifradas por la aplicacion. Si subes
una renovacion para el mismo emisor y ambiente, FactuFlow deja activo el
certificado nuevo y conserva el anterior como historico inactivo.

En la pantalla actual puedes:
- ver nombre, CUIT, ambiente y vencimiento
- agregar un certificado
- probar la conexion del certificado activo contra ARCA antes de emitir
- eliminar un certificado

Si cambias el emisor activo mientras la lista esta cargando, FactuFlow descarta
la respuesta anterior para evitar mezclar certificados entre CUITs.

Al cargar un certificado nuevo, el wizard muestra una barra de pasos con avance
visual y estados de completado. Incluye un paso obligatorio para autorizar el
servicio `WSFE` en ARCA antes de probar la conexion. En produccion esa
autorizacion se hace desde `Administrador de Relaciones de Clave Fiscal`; en
homologacion se hace desde WSASS. El certificado puede ser valido y aun asi
fallar si no esta asociado a ese servicio.

Antes de emitir comprobantes reales en produccion, usa `Probar conexion` sobre
el certificado productivo del emisor activo. La prueba valida la comunicacion
con ARCA usando ese certificado, sin generar comprobantes ni consumir
numeracion fiscal.

En `Puntos de venta`, la sincronizacion con ARCA se habilita solo cuando existe
un certificado activo del emisor para el ambiente backend actual
(`homologacion` o `produccion`). Un certificado activo de otro ambiente no
habilita esa accion.

## 9. Puntos de venta

En `Puntos de venta` puedes ver y sincronizar los puntos de venta habilitados para el emisor activo.

Importante:
- el numero debe coincidir con el punto de venta habilitado en ARCA para el sistema usado
- para homologacion o produccion con webservices, validar el punto de venta antes de emitir
- puedes usar `Sincronizar con ARCA` para contrastar lo local con el servicio
- la sincronizacion importa o actualiza puntos no bloqueados y sin fecha de
  baja como puntos Web Services usables
- si cambias el emisor activo mientras la pantalla esta cargando, FactuFlow
  descarta la respuesta anterior para no mezclar puntos de venta entre CUITs
- puedes usar `Importar constancia` para cargar el PDF de ARCA con la lista
  completa de puntos, incluyendo sistema, domicilio y nombre de fantasia
- FactuFlow marca como `Usable` solo los puntos Web Services activos, no
  bloqueados y sin baja; los puntos Factuweb, Comprobantes en Linea o
  Controlador Fiscal quedan visibles como referencia pero no se usan para emitir
- los datos importados se pueden editar manualmente desde `Editar`

## 10. Emisores

En `Emisores` puedes editar y guardar los datos fiscales y generales del emisor activo, o agregar otro CUIT para operar.
Completa `Ingresos Brutos` para que ese dato salga informado en los PDFs.

La pantalla tiene dos secciones:
- `Datos del emisor`: datos fiscales y de contacto.
- `Carga masiva`: perfiles de carga masiva del emisor activo.

Desde `Carga masiva` puedes crear, editar, eliminar y marcar un perfil de carga
masiva como predeterminado. Ese perfil se usara para precargar la pantalla de
emision masiva del mismo emisor.

Al agregar un emisor, puedes subir una constancia de inscripcion ARCA en PDF o
una constancia de opcion de Monotributo. FactuFlow intenta completar
automaticamente nombre fiscal, CUIT, condicion IVA, domicilio fiscal, localidad,
provincia, codigo postal e inicio de actividades. Provincia se elige desde un
catalogo cerrado de provincias argentinas; si la constancia no permite
detectarla con seguridad, queda pendiente de revision manual.
Antes de guardar, revisa y corrige cualquier dato detectado.

Revisa especialmente:
- CUIT
- razon social
- domicilio
- condicion IVA
- fecha de inicio de actividades
- email y telefono de contacto

## 11. Usuarios

La pantalla `Usuarios` solo aparece para usuarios administradores.

Desde esa pantalla puedes:
- crear usuarios
- editar nombre, email, estado, rol y emisor preferido
- desactivar usuarios
- reactivar usuarios
- restablecer contraseñas

Un usuario común puede operar todos los emisores configurados: crear y editar
emisores, emitir comprobantes, administrar certificados, sincronizar puntos de
venta, usar emisión masiva y consultar reportes. La única restricción inicial
visible es que no puede entrar al menú `Usuarios`. El borrado físico de un
emisor queda reservado a administradores porque puede afectar historial fiscal
y relaciones internas.

El rol `Administrador` significa que puede administrar usuarios. No es un rol de
acceso exclusivo a emisores.

Desactivar un usuario impide que vuelva a iniciar sesión, pero no borra su
historial. FactuFlow no permite que un administrador se desactive a sí mismo ni
se quite su propio permiso de administrador desde la pantalla.

## 12. Sistema

La sección `Sistema` solo aparece para usuarios administradores. Por ahora
incluye la pestaña `Almacenamiento`, pensada para instalaciones locales o VPS
pequeños donde cada MB cuenta.

Desde `Sistema > Almacenamiento` puedes ver:
- uso medido de la instalación
- espacio estimado recuperable
- límite lógico configurado, si existe
- espacio libre real del disco donde corre FactuFlow
- desglose por categorías: base de datos, lotes, certificados, logs,
  temporales y caché
- desglose resumido por emisor, sin mostrar CUIT completo ni datos de clientes
- lotes cerrados que todavía conservan filas originales compactables
- logs antiguos rotados, sin incluir el log activo
- temporales administrados por FactuFlow
- certificados huérfanos gestionados por FactuFlow y no referenciados por la
  base

### Resguardar antes de liberar espacio

Para lotes, logs antiguos y temporales, FactuFlow no libera espacio
directamente desde la selección. Primero debes:

1. Seleccionar los lotes, logs o temporales que quieres liberar.
2. Presionar `Preparar ZIP`.
3. Descargar el archivo de resguardo a tu PC con `Descargar resguardo`.
4. Verificar que el archivo quedó guardado localmente.
5. Recién entonces presionar `Liberar espacio` y confirmar `Ya lo descargué`.

El ZIP incluye un manifest con el contenido exportado, tamaño y checksum. Al
descargar, FactuFlow confirma el checksum del ZIP antes de habilitar la
liberación desde la pantalla. En lotes cerrados, el resguardo incluye resumen y
archivo observado cuando todavía
puede generarse. Después de liberar espacio, FactuFlow compacta esos lotes y
elimina el detalle original por fila del servidor. El lote, los comprobantes,
grupos, totales y auditoría se conservan, pero el archivo observado ya no puede
regenerarse desde el servidor.

La liberación de logs y temporales solo afecta archivos revalidados por el
backend dentro de rutas administradas. FactuFlow no acepta rutas manuales del
usuario ni escanea carpetas generales del sistema.

### Certificados huérfanos

Los certificados huérfanos se limpian en una acción separada. FactuFlow solo
muestra archivos que:
- están dentro de la carpeta configurada de certificados
- fueron generados o gestionados con el patrón interno de FactuFlow
- no están referenciados por ningún certificado registrado en la base

No se exportan claves privadas en los ZIPs de almacenamiento. Antes de limpiar
certificados huérfanos, revisa que la lista corresponda a archivos gestionados
que ya no se usan. Los certificados activos o referenciados no aparecen como
limpiables.

## 13. Limitaciones actuales

Al 2026-06-03:

- no existe todavia descarga masiva de PDFs desde el listado
- el PDF se genera bajo demanda y no debe quedar como archivo permanente en el
  servidor cuando la instalación corre en VPS
- los artefactos descargables no vitales, como PDFs, ZIPs, archivos observados
  y temporales, deben descargarse a la PC del usuario y limpiarse del servidor
  después de cumplir su propósito operativo
- el gestor de almacenamiento ya permite diagnóstico, resguardo ZIP y limpieza
  manual de lotes compactables, logs antiguos, temporales y certificados
  huérfanos; todavía no reemplaza una política completa de backup y
  restauración
- los reportes son de consulta, no de exportacion
- la validacion concluyente de homologacion se hace por webservice, no por QR
- el launcher local de Windows es manual y esta orientado a desarrollo/QA; no
  es todavia un instalador ni configura inicio automatico con Windows
- la produccion real ya fue operada; antes de cada nueva emision productiva hay
  que revisar punto de venta, fecha fiscal, formato, concepto fiscal ARCA,
  descripcion facturada, totales, backup/logs y confirmacion irreversible
- todavia falta una pantalla interna de `Estado del sistema` dentro del
  frontend; debe explicar con mensajes simples si la aplicacion, la base, ARCA,
  certificados y lotes estan correctos o necesitan atencion
- la gestión de lotes ya permite cerrar parciales, reconciliar externos,
  descartar pendientes, compactar y eliminar cargas sin emisión; todavía falta
  una vista administrativa más completa de eventos y trazabilidad histórica
  para soporte
