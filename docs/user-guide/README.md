# Manual de usuario - FactuFlow

Última actualización: 2026-06-27

Este manual describe el uso actual del producto. Si una función no aparece acá, no debe asumirse como disponible para usuarios finales.

Nota 2026-06-24: se cerró el checkpoint visual v01 del frontend público. Los
flujos y pasos de uso descritos en este manual no cambian por ese cierre; la
actualización es de presentación visual e identidad.

Nota 2026-06-25: `Sistema` incorpora una primera pestaña `Estado` para revisar
señales operativas básicas sin ejecutar automáticamente pruebas externas de
ARCA.

Nota 2026-06-27: `Emisión masiva` reorganiza la preparación, validación y
revisión del lote activo. La ayuda inicial queda como guía compacta desplegable,
los requisitos se muestran como checklist, `Validar lote` también aparece al
cierre de la configuración fiscal y, después de validar, la vista prioriza
importes, avance y siguiente acción. Las acciones excepcionales de resolución
de pendientes quedan agrupadas bajo `Resolver pendientes`.

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

En pantallas chicas, el menú lateral se abre con el botón de menú de la esquina
superior izquierda y se cierra desde el mismo botón o al elegir una sección.

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
- emisión masiva
- certificados
- puntos de venta
- reportes
- nueva factura

Antes de emitir o consultar información, verifica siempre que el emisor activo sea el correcto.
Si cambias el emisor activo, las pantallas principales recargan la información
para mostrar solo datos de ese CUIT. En `Nueva Factura`, cambiar el emisor
recarga puntos de venta y limpia el cliente seleccionado.

El emisor activo se mantiene por pestaña del navegador. Si abres otra pestaña y
cambias de emisor, esa nueva selección no cambia silenciosamente una factura o
un lote que ya estabas revisando en la pestaña anterior.

Como protección adicional, la emisión se bloquea si el punto de venta o el
cliente seleccionado no pertenecen al emisor activo.
La misma separación aplica a certificados, comprobantes, lotes, PDFs, reportes,
perfiles de carga y formatos de importación: no deben mezclarse entre emisores.

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

## 6. Emisión masiva

La emisión masiva está pensada para cargar muchas facturas desde Excel. Puede
usar la plantilla oficial de FactuFlow o una plantilla configurada para un
emisor o para todos los emisores.

Flujo general:

1. Descargar la plantilla oficial, la plantilla recordada por el perfil o la
   plantilla configurada para ese emisor.
2. Si existe, revisar el perfil de carga masiva aplicado para el emisor activo.
3. Subir el Excel.
4. Revisar la plantilla/formato sugerido por FactuFlow.
5. Si es un archivo externo, elegir o confirmar la plantilla correcta.
6. Elegir si el punto de venta sale del archivo o si se fija un punto habilitado
   del emisor.
7. Elegir explícitamente si el lote corresponde a `Productos`, `Servicios` o
   `Definido por archivo`.
8. Definir la descripción/concepto facturado del ítem: desde el archivo o como
   texto fijo para todo el lote.
9. Definir explícitamente la fecha de emisión y, si corresponde, el período de
   servicios y vencimiento de pago.
10. Revisar el checklist de validación y presionar `Validar lote` al cierre de
    la configuración fiscal.
11. Revisar comprobantes detectados, concepto fiscal ARCA, descripción del ítem,
   fechas, totales listos para emitir, receptor y punto de venta.
12. Confirmar la emisión con `Emitir comprobantes válidos`.
13. Revisar resultados del lote.
14. Si lo necesitas, descargar el archivo observado del lote.

La pantalla muestra un checklist de validación con emisor activo, archivo y
plantilla/formato, punto de venta, concepto ARCA, descripción facturada y fechas
fiscales. Usalo para ver qué falta antes de validar el lote.

Después de validar, el lote activo muestra primero los totales listos para
emitir, el avance y la siguiente acción recomendada según el estado. El resumen
operativo completo y el detalle de comprobantes quedan disponibles en secciones
plegables para auditoría, soporte o revisión puntual. Las acciones
excepcionales quedan agrupadas en `Resolver pendientes`; abrí ese modo solo
cuando necesites reintentar, descartar o reconciliar. Si una acción aplica sobre
comprobantes visibles, el detalle debe estar abierto para ver las filas
alcanzadas.

Validar un lote no emite comprobantes ni consume numeración fiscal. La emisión
recién ocurre cuando confirmás el lote validado.

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
datos locales. Si un lote que estaba `Procesando` queda vencido, los grupos que
todavía figuraban como validados pasan a reconciliación para no mostrarse como
listos para emitir, y la pantalla muestra pendientes visibles porque el detalle
del lote se consulta por páginas. En ese estado `Reintentar fallidos` queda
deshabilitado aunque existan grupos fallidos: la acción segura es auditar y
reconciliar. Si un reintento de fallidos se interrumpe justo después de tomar el
comprobante para emisión, el grupo también queda para reconciliación: no vuelve
automáticamente a `Fallido`, porque reemitirlo podría duplicar una autorización
fiscal.

### Gestión de lotes parciales y limpieza

Cuando un lote queda con comprobantes emitidos y otros pendientes, FactuFlow
puede mostrar acciones de resolución. Estas acciones aparecen agrupadas bajo
`Resolver pendientes` y el panel arranca cerrado para no mezclar casos
excepcionales con la revisión normal del lote:

- `Reintentar fallidos`: vuelve a solicitar CAE para comprobantes fallidos. La
  pantalla muestra una confirmación de fecha fiscal y punto de venta; si esos
  datos no son correctos, cancela y revisa el lote. No se habilita para lotes en
  `Requiere reconciliación`.
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

Cuando presionas `Emitir comprobantes válidos`, el lote queda en seguimiento y
la pantalla muestra una barra de avance real. La barra informa comprobantes
procesados, emitidos, fallidos, pendientes, tiempo transcurrido y tiempo
estimado restante. Si el lote todavía está `En cola`, el avance se muestra como
estimación hasta que el worker empieza a procesar. Revisa el resumen final antes
de volver a intentar. El sistema bloquea una segunda ejecución del mismo lote si
ya está procesando o si ya fue procesado. Si un proceso queda trabado y supera
la ventana operativa configurada como `BATCH_PROCESSING_STALE_MINUTES`,
FactuFlow no vuelve a pedir CAE automáticamente. Primero vincula comprobantes
locales ya autorizados si puede hacerlo sin consultar ARCA; si queda cualquier
pendiente o duda fiscal, el lote pasa a `Requiere reconciliación` y debe
auditarse antes de continuar.

Para acelerar lotes grandes, FactuFlow consulta a ARCA cuántos comprobantes
pueden enviarse por request (`RegXReq`) y divide la emisión en sublotes por
punto de venta y tipo de comprobante. Esto no cambia la confirmación fiscal: el
usuario sigue revisando fecha, punto de venta, concepto, descripción y totales
antes de solicitar CAE.

Si ARCA no informa la capacidad máxima por request, FactuFlow emite en modo
unitario para no bloquear la operación. En ese caso la pantalla del lote muestra
un aviso indicando que el procesamiento pudo demorar más por esa degradación.

Regla importante: FactuFlow no completa la fecha de emisión con la fecha del día
por defecto. Antes de validar un lote debes elegir si la fecha de emisión sale
del archivo o si se usará una fecha fija para todos los comprobantes. Para
comprobantes de servicios también debes definir cómo se completan `desde`,
`hasta` y vencimiento de pago. Si una fecha elegida queda fuera de la ventana
que ARCA permite para autorizar comprobantes, el lote queda observado antes de
emitir. Para emitir, debes elegir una fecha permitida por el web service; el
sistema no la reemplaza automáticamente.

Antes de emitir, FactuFlow debe mostrar una confirmación final de fecha fiscal
con este texto: `Está seguro que quiere emitir comprobantes con fecha
XX/XX/XX? Recuerde que luego no podrá emitir comprobantes con fecha anterior
para ese mismo punto de venta.` Si la fecha o el punto de venta no son los que
corresponden, cancela la emisión y vuelve a revisar el lote. En lotes con más
de una fecha o punto de venta, la confirmación debe mostrar todos los valores
concretos; el backend solo procesa si la UI envía el token exacto calculado
desde esos grupos validados.

Regla crítica de concepto fiscal ARCA: FactuFlow no asume que el lote sea de
productos o de servicios. Antes de validar debes elegir `Productos`,
`Servicios` o `Definido por archivo`. Esta decisión es fiscal y define cómo se
arma el comprobante para ARCA, qué ventana de fechas aplica y si hacen falta
fechas de servicio. Si eliges `Definido por archivo`, el Excel debe traer una
columna válida con `Producto` o `Servicio` en todas las filas. Si falta la
columna o hay un valor distinto, FactuFlow informa el problema y no deja emitir
ese lote hasta corregirlo o elegir un criterio válido.

Regla crítica de descripción del ítem: el concepto fiscal ARCA no es el texto
que aparece facturado en el renglón del comprobante. Textos como `Honorarios`,
`Zapatillas`, `Servicio mensual` o `Abono` son la descripción/concepto facturado
del ítem. Esa descripción también debe definirse antes de validar: puede venir
de una columna del archivo o fijarse como un valor único para todo el lote. No
debe completarse con un default oculto del formato.

Los lotes viejos validados antes de esta regla deben revalidarse. FactuFlow no
permite procesarlos sin una política de concepto fiscal guardada.

Regla de punto de venta en lotes: podés usar el punto de venta definido en el
archivo o fijar un punto habilitado del emisor. Para elegir un punto fijo, ese
punto debe estar cargado primero en `Puntos de venta` y debe figurar como usable
por FactuFlow. Si el emisor no tiene puntos habilitados cargados, la pantalla lo
indica y solo queda disponible usar el punto informado por el archivo hasta
completar la pantalla correspondiente.

Al emitir, FactuFlow vuelve a verificar en backend que el punto de venta y un
cliente precargado opcional pertenezcan al emisor activo.

### Perfiles de carga masiva

Cada emisor puede tener perfiles de carga masiva para completar más rápido la
pantalla de emisión masiva. Se administran desde `Emisores > Carga masiva`.

Un perfil de carga masiva puede recordar:
- plantilla opcional
- punto de venta: utilizar el definido en el archivo o fijar uno habilitado del
  emisor
- concepto fiscal ARCA
- descripción facturada desde archivo o fija
- fecha de emisión relativa, por ejemplo último día del mes anterior, o una
  fecha personalizada cargada de forma explícita
- período de servicios, por ejemplo mes anterior completo o mes actual completo
- vencimiento de pago, por ejemplo mismo día de emisión o emisión más una
  cantidad de dias

Si un emisor tiene un solo perfil de carga masiva, FactuFlow lo aplica al entrar
en `Emisión masiva`. Si tiene varios, se aplica el marcado como predeterminado.
Si no hay predeterminado, el usuario elige uno.

Si una plantilla se edita y queda una versión nueva, los perfiles que recordaban
la versión anterior deben actualizarse antes de validar nuevos lotes. FactuFlow
rechaza versiones reemplazadas para nuevas cargas para evitar usar mapeos
obsoletos.

El perfil de carga masiva no valida ni emite automáticamente. Solo completa la
pantalla con valores visibles. Antes de validar podés cambiar cualquier selector
o fecha. Si el perfil trae reglas relativas, FactuFlow no usa la fecha del
navegador para convertirlas automáticamente en fecha fiscal al entrar a
`Emisión masiva`: antes de validar debes elegir una fecha exacta, tomarla del
archivo o confirmar explícitamente la política fiscal de esa carga. Si cambias
un dato precargado, esa carga queda como configuración manual y no como snapshot
del perfil de carga masiva.

Por seguridad fiscal, un perfil de carga masiva no ofrece `Fecha actual` como
regla de fecha de emisión.

Para guardar un perfil con punto de venta fijo, el punto debe estar cargado en
`Puntos de venta` para ese emisor y estar habilitado para usar en FactuFlow. Si
todavia no hay puntos cargados, completalos primero desde esa pantalla.

### Plantillas de carga masiva

La pantalla habla de `Plantillas`, aunque internamente el backend las guarda
como formatos de importación versionados. Se administran desde
`Emisores > Carga masiva > Plantillas`.

Una plantilla puede ser:
- global, reutilizable por cualquier emisor y administrada solo por usuarios
  administradores
- exclusiva del emisor activo, administrable por usuarios activos
- del sistema, protegida contra edición directa

FactuFlow lee los encabezados del Excel, muestra las columnas detectadas y
sugiere la plantilla/formato con mayor coincidencia. Si la coincidencia es alta,
esa plantilla queda seleccionada automáticamente y podés cambiarla si no estás
de acuerdo. Si no hay una sugerencia confiable, debes elegir la plantilla antes
de validar. Si los encabezados no se analizaron automáticamente, la pantalla
muestra la acción `Analizar encabezados` y mantiene bloqueada la validación
hasta completar ese paso.

Desde `Emisores > Carga masiva > Plantillas` puedes crear una plantilla desde
cero o subir un Excel de ejemplo para tomar encabezados. El constructor permite
ordenar, agregar y quitar columnas, elegir qué campo FactuFlow representa cada
columna, definir valores fijos, revisar compatibilidad con el emisor activo y
descargar un `.xlsx` con hoja `Comprobantes`, hoja `Instrucciones` y metadatos
no fiscales en una hoja oculta.

Las plantillas pueden mapear datos de cuatro maneras:
- por encabezado, usando nombres o alias de columnas
- por columna fija, usando letra o índice cuando el archivo no tiene encabezados
  confiables
- por constante, para completar campos que siempre tienen el mismo valor
- por emisor, solo para datos que FactuFlow resuelve explícitamente, como el
  CUIT del emisor activo

El IVA del ítem debe estar definido de forma explícita en la plantilla: puede
venir desde una columna del Excel o quedar fijo como constante. Para Factura C,
esa constante debe ser `0`; FactuFlow no debe completar el IVA por un valor
oculto.

Si el archivo externo trae un total informado, FactuFlow compara ese total con
el total calculado desde los ítems e IVA. Si no coinciden, el comprobante queda
observado antes de emitir. Esta validación evita usar por error una columna de
total final como si fuera precio neto.

Descargar una plantilla no valida ni emite comprobantes. Los metadatos ocultos
del Excel solo ayudan a sugerir la plantilla al subirlo; FactuFlow no confía en
esos metadatos para emitir. Siempre vuelve a validar archivo, perfil, emisor,
fechas, tipo de comprobante, punto de venta y comprobantes asociados.

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

La sección `Reportes` muestra consultas básicas:
- ventas
- IVA
- ranking de clientes

Los reportes usan el emisor activo seleccionado.
Si cambias el emisor activo mientras un reporte está cargando, FactuFlow
descarta la respuesta anterior para no mostrar datos de otro CUIT. El subdiario
IVA muestra detalle por alícuota, incluyendo gravado e IVA 27% cuando
corresponde.

## 8. Certificados

En `Certificados` gestionás los certificados de ARCA por ambiente.

Uso recomendado:
- trabajar primero en homologación
- verificar vigencia del certificado antes de emitir
- mantener un solo certificado activo por empresa y ambiente

Las claves privadas generadas por FactuFlow quedan guardadas dentro del
directorio de certificados configurado y cifradas por la aplicación. Si subís
una renovación para el mismo emisor y ambiente, FactuFlow deja activo el
certificado nuevo y conserva el anterior como histórico inactivo.

En la pantalla actual puedes:
- ver nombre, CUIT, ambiente y vencimiento
- agregar un certificado
- probar la conexión del certificado activo contra ARCA antes de emitir
- eliminar un certificado

Si cambias el emisor activo mientras la lista está cargando, FactuFlow descarta
la respuesta anterior para evitar mezclar certificados entre CUITs.

Al cargar un certificado nuevo, el wizard muestra una barra de pasos con avance
visual y estados de completado. Incluye un paso obligatorio para autorizar el
servicio `WSFE` en ARCA antes de probar la conexión. En producción esa
autorización se hace desde `Administrador de Relaciones de Clave Fiscal`; en
homologación se hace desde WSASS. El certificado puede ser válido y aun así
fallar si no está asociado a ese servicio.

Antes de emitir comprobantes reales en producción, usa `Probar conexión` sobre
el certificado productivo del emisor activo. La prueba valida la comunicación
con ARCA usando ese certificado, sin generar comprobantes ni consumir
numeración fiscal.

En `Puntos de venta`, la sincronización con ARCA se habilita solo cuando existe
un certificado activo del emisor para el ambiente backend actual
(`homologación` o `producción`). Un certificado activo de otro ambiente no
habilita esa acción.

## 9. Puntos de venta

En `Puntos de venta` puedes ver y sincronizar los puntos de venta habilitados para el emisor activo.

Importante:
- el número debe coincidir con el punto de venta habilitado en ARCA para el sistema usado
- para homologación o producción con webservices, validar el punto de venta antes de emitir
- puedes usar `Sincronizar con ARCA` para contrastar lo local con el servicio
- la sincronización importa o actualiza puntos no bloqueados y sin fecha de
  baja como puntos Web Services usables
- si cambias el emisor activo mientras la pantalla está cargando, FactuFlow
  descarta la respuesta anterior para no mezclar puntos de venta entre CUITs
- puedes usar `Importar constancia` para cargar el PDF de ARCA con la lista
  completa de puntos, incluyendo sistema, domicilio y nombre de fantasía
- FactuFlow marca como `Usable` solo los puntos Web Services activos, no
  bloqueados y sin baja; los puntos Factuweb, Comprobantes en Linea o
  Controlador Fiscal quedan visibles como referencia pero no se usan para emitir
- los datos importados se pueden editar manualmente desde `Editar`

## 10. Emisores

En `Emisores` puedes editar y guardar los datos fiscales y generales del emisor activo, o agregar otro CUIT para operar.
Completa `Ingresos Brutos` para que ese dato salga informado en los PDFs.

La pantalla tiene dos secciones:
- `Datos del emisor`: datos fiscales y de contacto.
- `Carga masiva`: perfiles y plantillas de carga masiva.

Desde `Carga masiva > Perfiles` puedes crear, editar, eliminar y marcar un
perfil de carga masiva como predeterminado. Ese perfil se usará para precargar
la pantalla de emisión masiva del mismo emisor.

Desde `Carga masiva > Plantillas` puedes crear plantillas visuales del emisor
activo, iniciar una plantilla desde un Excel de ejemplo, revisar compatibilidad,
descargar el Excel generado, clonar plantillas del sistema y desactivar
plantillas propias. Las plantillas globales solo pueden crearlas o modificarlas
usuarios administradores. El alcance de una plantilla existente no se cambia
editándola; si necesitás otro alcance, cloná la plantilla y elegí el destino de
la copia.

Al agregar un emisor, puedes subir una constancia de inscripción ARCA en PDF o
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

La sección `Sistema` solo aparece para usuarios administradores. Incluye las
pestañas `Estado` y `Almacenamiento`.

Desde `Sistema > Estado` puedes ver señales operativas básicas:
- aplicación backend disponible
- base de datos disponible
- certificado local del emisor activo para el ambiente ARCA configurado
- conexión ARCA como prueba manual explícita
- resumen de almacenamiento
- señales pendientes de instrumentar, como worker de lotes, último backup y
  acceso a logs según entorno

La pantalla usa estados simples: `Correcto`, `Necesita atención` y
`No disponible`. La acción `Probar conexión` puede llamar a ARCA; no se ejecuta
automáticamente al abrir la pantalla.

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

Al 2026-06-25:

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
- `Sistema > Estado` ya muestra un primer diagnóstico operativo con API, base,
  certificado local, ARCA manual y almacenamiento; todavía faltan healthcheck
  dedicado de worker, backup visible y trazabilidad histórica más completa
- la gestión de lotes ya permite cerrar parciales, reconciliar externos,
  descartar pendientes, compactar y eliminar cargas sin emisión; todavía falta
  una vista administrativa más completa de eventos y trazabilidad histórica
  para soporte
