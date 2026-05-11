# Manual de usuario - FactuFlow

Ultima actualizacion: 2026-05-09

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
11. Limitaciones actuales

## 1. Acceso al sistema

1. Abrir FactuFlow en el navegador.
2. Ingresar con tu correo electronico y contrasena.
3. Si es la primera vez y no hay un usuario creado, usar la opcion `Configurar sistema`.

Si ya existe al menos un usuario y se necesita crear otro administrador, hoy se hace
con el comando operativo `python -m app.scripts.create_admin_user` desde el backend.
Todavia no hay una pantalla de gestion de usuarios.

## 2. Emisor activo

Si tu usuario administra mas de un CUIT, en el encabezado veras el selector `Emisor activo`.

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
   fechas, importes, receptor y punto de venta.
12. Confirmar la emision con `Emitir comprobantes validos`.
13. Revisar resultados del lote.
14. Si lo necesitas, descargar el archivo observado del lote.

Validar un lote no emite comprobantes ni consume numeracion fiscal. La emision
recien ocurre cuando confirmas el lote validado.

Cuando uses la plantilla oficial de FactuFlow, el sistema lee la hoja llamada
`Comprobantes`. Las hojas adicionales, por ejemplo `Resumen` o `Control`, son
solo informativas y no se usan para emitir. Si el archivo no tiene una hoja
llamada `Comprobantes`, FactuFlow intenta leer la primera hoja del Excel.

Si un lote termina `fallido` o `con_errores` sin haber emitido comprobantes,
podes volver a subir el mismo archivo para revalidarlo. FactuFlow conserva el
historial del intento anterior y solo permite el reintento cuando no hubo CAE
emitido. Si el lote ya quedo validado para emitir o emitio algun comprobante, el
archivo duplicado se bloquea para evitar facturacion repetida.

Cuando presionas `Emitir comprobantes validos`, el lote queda en seguimiento y
la pantalla muestra una barra de avance real. La barra informa comprobantes
procesados, emitidos, fallidos, pendientes, tiempo transcurrido y tiempo
estimado restante. Si el lote todavia esta `En cola`, el avance se muestra como
estimacion hasta que el worker empieza a procesar. Revisa el resumen final antes
de volver a intentar. El sistema bloquea una segunda ejecucion del mismo lote si
ya esta procesando o si ya fue procesado.

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
corresponden, cancela la emision y vuelve a revisar el lote.

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
o fecha. Si el perfil trae reglas relativas, FactuFlow las muestra como fechas
concretas en la pantalla antes de validar. Si cambias un dato precargado, esa
carga queda como configuracion manual y no como snapshot del perfil de carga
masiva.

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

### Formato Cano

El emisor Cano tiene configurado localmente el formato `Cano - Factura B IVA
21%`. Esta pensado para archivos con columnas como `Fecha`, `Tipo`,
`Punto de Venta`, `Imp. Neto Gravado`, `IVA` e `Imp. Total`.

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

En Factura C los items deben tener IVA 0. FactuFlow no informa el bloque IVA a
ARCA para ese tipo de comprobante, porque el web service lo rechaza aunque la
alicuota sea cero.

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

## 8. Certificados

En `Certificados` gestionas los certificados de ARCA por ambiente.

Uso recomendado:
- trabajar primero en homologacion
- verificar vigencia del certificado antes de emitir
- mantener un solo certificado activo por empresa y ambiente

En la pantalla actual puedes:
- ver nombre, CUIT, ambiente y vencimiento
- agregar un certificado
- probar la conexion del certificado activo contra ARCA antes de emitir
- eliminar un certificado

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

## 9. Puntos de venta

En `Puntos de venta` puedes ver y sincronizar los puntos de venta habilitados para el emisor activo.

Importante:
- el numero debe coincidir con el punto de venta habilitado en ARCA para el sistema usado
- para homologacion o produccion con webservices, validar el punto de venta antes de emitir
- puedes usar `Sincronizar con ARCA` para contrastar lo local con el servicio
- la sincronizacion importa o actualiza puntos no bloqueados y sin fecha de
  baja como puntos Web Services usables
- puedes usar `Importar constancia` para cargar el PDF de ARCA con la lista
  completa de puntos, incluyendo sistema, domicilio y nombre de fantasia
- FactuFlow marca como `Usable` solo los puntos Web Services activos, no
  bloqueados y sin baja; los puntos Factuweb, Comprobantes en Linea o
  Controlador Fiscal quedan visibles como referencia pero no se usan para emitir
- los datos importados se pueden editar manualmente desde `Editar`

## 10. Emisores

En `Emisores` puedes editar y guardar los datos fiscales y generales del emisor activo, o agregar otro CUIT para operar.

La pantalla tiene dos secciones:
- `Datos del emisor`: datos fiscales y de contacto.
- `Carga masiva`: perfiles de carga masiva del emisor activo.

Desde `Carga masiva` puedes crear, editar, eliminar y marcar un perfil de carga
masiva como predeterminado. Ese perfil se usara para precargar la pantalla de
emision masiva del mismo emisor.

Al agregar un emisor, puedes subir una constancia de inscripcion ARCA en PDF o
una constancia de opcion de Monotributo. FactuFlow intenta completar
automaticamente nombre fiscal, CUIT, condicion IVA, domicilio fiscal, localidad,
provincia, codigo postal e inicio de actividades.
Antes de guardar, revisa y corrige cualquier dato detectado.

Revisa especialmente:
- CUIT
- razon social
- domicilio
- condicion IVA
- fecha de inicio de actividades
- email y telefono de contacto

## 11. Limitaciones actuales

Al 2026-05-08:

- no existe todavia descarga masiva de PDFs desde el listado
- el PDF se genera bajo demanda
- los reportes son de consulta, no de exportacion
- la validacion concluyente de homologacion se hace por webservice, no por QR
- antes de la primera prueba real en produccion hay que confirmar el punto de
  venta elegido, revisar backup/logs y emitir solo un lote chico controlado
