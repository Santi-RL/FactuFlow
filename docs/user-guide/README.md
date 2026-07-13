# Manual de usuario - FactuFlow

Última actualización: 2026-07-10

Este manual describe `v0.2.1`, el producto actualmente desplegado. Si una
función no aparece acá, no debe asumirse como disponible para usuarios finales.

Las fechas visibles y las ingresadas manualmente por usuarios se expresan en
`DD/MM/AAAA`. Los formatos ISO quedan reservados a API, backend y ARCA.

## Contenido

1. Acceso al sistema
2. Emisor activo
3. Dashboard
4. Clientes
5. Comprobantes
6. Emisión masiva
7. Reportes
8. Certificados
9. Puntos de venta
10. Emisores
11. Usuarios
12. Sistema
13. Limitaciones actuales

## 1. Acceso al sistema

En una instalación local de Windows para desarrollo o QA, usar el acceso
`FactuFlow Local.vbs` ubicado en la carpeta del proyecto. Ese acceso inicia
FactuFlow en segundo plano sin dejar una ventana de PowerShell abierta, muestra
un ícono junto al reloj de Windows y abre el navegador cuando la aplicación está
lista. `FactuFlow Local.cmd` queda como acceso de compatibilidad.

Estados del ícono local:
- verde: FactuFlow está listo para usar
- amarillo: FactuFlow se está iniciando
- rojo: FactuFlow requiere atención

Desde el ícono junto al reloj podés:
- abrir FactuFlow
- consultar el estado del sistema
- reiniciar servicios
- detener servicios
- abrir logs
- salir del launcher local

Si el ícono queda rojo, usá `Estado del sistema` o `Abrir logs`. Los mensajes
están pensados para indicar si el problema está en el servidor local, la base de
datos, el frontend o un puerto ocupado por otra aplicación.

Si la pantalla de inicio de sesión indica que `FactuFlow no está listo para
iniciar sesión`, primero identificá qué acceso usaste. Si usaste el acceso
directo del escritorio que ejecuta `scripts\restart-local-dev.ps1`, volvé a
ejecutarlo y esperá que muestre `Backend OK` y `Frontend OK`; ese flujo no
muestra ícono junto al reloj. Si usaste el launcher `FactuFlow Local.vbs`, hacé
clic derecho en el ícono de FactuFlow junto al reloj de Windows y elegí
`Reiniciar servicios`. Luego presióná `Reintentar` en la pantalla.

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
recarga puntos de venta y limpia el cliente seleccionado. La vista previa se
habilita solo cuando FactuFlow pudo confirmar el próximo número. Si eliges
Productos después de haber completado un período de Servicios, esas fechas se
limpian y no se envían a ARCA. Si modificas los datos de un cliente guardado, el
receptor pasa a carga manual para no conservar una vinculación incorrecta. Al
reducir la búsqueda de clientes a menos de dos caracteres, FactuFlow cierra los
resultados anteriores para evitar una selección obsoleta. Si cambia el emisor
mientras se guarda un punto de venta, la respuesta anterior no reemplaza la
lista visible del nuevo emisor.

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
- último comprobante emitido
- estado del certificado activo

Desde ahi puedes ir directo a:
- nuevo cliente
- emitir factura
- emisión masiva
- configurar empresa

## 4. Clientes

En `Clientes` puedes:
- crear clientes
- editar clientes
- buscar por nombre o documento

Datos habituales:
- tipo y número de documento
- razón social o nombre
- condición frente al IVA
- domicilio, localidad y provincia
- email y teléfono si corresponden

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
- tipo y número
- fecha
- cliente
- ítems
- importes
- CAE y vencimiento

Si el comprobante está autorizado, verás:
- `Ver PDF`
- `Descargar PDF`

### Cómo funciona el PDF hoy

- El PDF no se genera automáticamente al emitir.
- Se genera bajo demanda cuando usas `Ver PDF` o `Descargar PDF`.
- Esto evita guardar archivos innecesarios.
- En una instalación sobre VPS, los PDFs descargados deben quedar en la PC del
  usuario. FactuFlow no debe usarlos como almacenamiento permanente del
  servidor.
- El PDF muestra `ORIGINAL`, letra y código de comprobante, emisor, receptor,
  período facturado, detalle, totales, CAE, vencimiento CAE y QR ARCA en una
  hoja A4 con ubicaciones principales similares a la factura oficial ARCA.
- Si el receptor es consumidor final sin documento, el PDF muestra `Doc.: -`,
  y consigna `Condición frente al IVA: Consumidor Final`; el número `0` queda
  como dato técnico para ARCA/QR y no se muestra como documento visible. Si el
  comprobante tiene una razón social real del receptor, el PDF la muestra; si
  solo trae un texto genérico como `A CONSUMIDOR FINAL`, el nombre queda vacío.
- Si el emisor tiene `Ingresos Brutos` cargado en `Emisores`, también se muestra
  en el PDF. Si no está cargado, figura como `No informado`.
- En comprobantes nuevos de servicios, el PDF muestra período facturado y
  vencimiento de pago cuando esos datos fueron informados al emitir.
- En comprobantes históricos emitidos por lote, una migración reconstruye el
  período y vencimiento desde el payload guardado del lote cuando esos datos no
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
   servicios y vencimiento de pago. Para lotes de `Productos`, esas fechas de
   servicio no aplican; para `Servicios` o `Definido por archivo`, FactuFlow
   exige la política correspondiente antes de validar.
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

`Lotes recientes` funciona como navegación compacta para cambiar de lote. Cada
ítem muestra nombre de archivo, fecha de carga, estado y una métrica principal
según el estado del lote; el lote activo queda resaltado. El detalle completo de
contadores se consulta en el resumen del lote activo, no en el historial.

Validar un lote no emite comprobantes ni consume numeración fiscal. La emisión
recién ocurre cuando confirmás el lote validado.

Al confirmar la emisión de un lote, FactuFlow también usa una clave interna de
idempotencia. Esto evita que un doble click, un refresh o un retry de red vuelva
a pedir CAE para el mismo procesamiento. La clave se conserva para el retry de
la misma operación y se reemplaza si cambiás de lote, archivo, emisor o
selección de grupos.

Cuando el lote queda validado, la pantalla muestra `Totales listos para emitir`
con cantidad de comprobantes, neto, IVA 21%, IVA 10,5% y total. Compara esos
valores contra el Excel antes de presionar `Emitir comprobantes válidos`.

En lotes grandes, la pantalla no muestra todos los comprobantes a la vez. El
resumen, los totales y la confirmación fiscal se calculan sobre el lote
completo, pero la grilla de detalle carga una página de comprobantes por vez.
Podés cambiar de página o filtrar por estado para revisar listos, observados,
autorizados, fallidos o casos que requieren reconciliación. Para revisar el
detalle completo por fila, usa `Descargar observado`.

Cuando uses la plantilla oficial de FactuFlow, el sistema lee la hoja llamada
`Comprobantes`. Las hojas adicionales, por ejemplo `Resumen` o `Control`, son
solo informativas y no se usan para emitir. Si el archivo no tiene una hoja
llamada `Comprobantes`, FactuFlow intenta leer la primera hoja del Excel.
Si el XLSX está malformado o supera el límite operativo configurado como
`BATCH_MAX_UPLOAD_BYTES`, FactuFlow lo rechaza antes de validar el lote.

Si un lote termina `fallido` o `con_errores` sin haber emitido comprobantes,
podés volver a subir el mismo archivo para revalidarlo. FactuFlow conserva el
historial del intento anterior y solo permite el reintento cuando no hubo CAE
emitido. Si el lote ya quedó validado para emitir o emitió algún comprobante, el
archivo duplicado se bloquea para evitar facturación repetida.

Además del bloqueo por archivo ya cargado, FactuFlow calcula duplicados lógicos
por comprobante. Si detecta comprobantes muy similares dentro del lote o contra
comprobantes locales ya autorizados, muestra una advertencia y pide una
confirmación adicional. Confirmar esa advertencia solo indica que revisaste el
riesgo de duplicado; no reemplaza la confirmación fiscal final de fecha y punto
de venta.

Si el lote queda como `Requiere reconciliación`, no lo reintentes. Ese estado
significa que ARCA pudo haber autorizado comprobantes con CAE, pero FactuFlow no
pudo terminar de guardarlos. Primero hay que consultar ARCA y reconciliar los
datos locales. FactuFlow solo considera aprobado un resultado ARCA explícito
`A`; una respuesta parcial no se presenta como comprobante autorizado. Si un lote que estaba
`Procesando` queda vencido, FactuFlow separa los grupos intactos de aquellos con
evidencia fiscal. Solo reencola pendientes intactos cuando puede demostrar que
no tuvieron intento fiscal y que la numeración ARCA/local sigue alineada. Los
grupos con evidencia o incertidumbre pasan a reconciliación; si esa comprobación
no puede completarse, el lote queda bloqueado y los grupos intactos conservan su
estado sin emitirse. En ese caso no reintentes manualmente: primero audita el
lote. Si un reintento se interrumpe después de tomar un comprobante para
emisión, ese grupo también queda para reconciliación porque reemitirlo podría
duplicar una autorización fiscal.

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
ya está procesando o si ya fue procesado.

El seguimiento consulta solo el estado y los contadores necesarios: no vuelve a
cargar todas las filas ni los grupos en cada ciclo. La pantalla consulta cada
`3 s` durante los primeros `30 s`, cada `5 s` hasta los `2 min` y cada `10 s`
desde entonces, siempre con una sola solicitud en vuelo. Si hay un error
temporal, aumenta la espera hasta un máximo de `15 s` y vuelve al ritmo normal
después de una respuesta satisfactoria. Si un proceso queda trabado y supera
la ventana operativa configurada como `BATCH_PROCESSING_STALE_MINUTES`,
FactuFlow no vuelve a pedir CAE automáticamente. Primero vincula comprobantes
locales ya autorizados si puede hacerlo sin consultar ARCA. Si quedan
comprobantes pendientes, solo vuelve a poner el lote en cola cuando puede probar
que esos pendientes no tuvieron intento fiscal, CAE, número ni comprobante local
candidato y que la numeración ARCA/local sigue alineada. Si no puede probarlo,
el lote pasa a `Requiere reconciliación` y debe auditarse antes de continuar.

Si FactuFlow informa que el worker de lotes no está disponible, el lote no fue
puesto en cola y no se solicitó CAE desde ese intento. Conserva el lote y vuelve
a intentar cuando el servicio esté habilitado; no vuelvas a cargar el Excel como
un lote nuevo.

Si una emisión responde `503`, FactuFlow confirmó que ARCA no fue llamada, que no
hay intentos fiscales y que la operación quedó guardada para reanudarse. Espera
y reintenta con la misma clave; no crees otra carga. Ante
`409 pre_arca_estado_bloqueado`, conserva también esa clave, no abras otra
operación y espera o pide revisión. Ese bloqueo no requiere reconciliar ARCA
porque la solicitud fiscal no comenzó. Si el `409` es posterior al inicio de la
solicitud o indica `Requiere reconciliación`, no reintentes: pide revisión y
reconciliación. FactuFlow conserva la respuesta con la misma clave cuando puede;
repetir esa misma operación sirve para consultar su estado, no para pedir otro
CAE. En lotes, el worker detiene el ciclo y solo vuelve a poner el lote en cola
pre-ARCA cuando comprobó que no hay intentos fiscales.

Si la pantalla no puede refrescar el seguimiento por timeout o error del
servidor, eso no significa por sí mismo que el lote haya desaparecido. No vuelvas
a cargar ni emitir el mismo archivo hasta refrescar el estado, revisar la
pantalla `Sistema > Estado` o pedir soporte para auditar/reconciliar antes de
continuar.

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

Las fechas visibles del flujo se muestran en `DD/MM/AAAA`. Si el archivo o el
backend usan formatos técnicos, FactuFlow debe convertirlos en los bordes sin
mostrar `YYYY-MM-DD`, ISO datetime o `CbteFch` como formato principal para el
usuario.

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
- fecha de emisión desde archivo, a completar en carga masiva o personalizada de forma explícita
- período de servicios, por ejemplo mes anterior completo o mes actual completo
- vencimiento de pago, por ejemplo mismo día de emisión o emisión más una
  cantidad de días

Si un emisor tiene un solo perfil de carga masiva, FactuFlow lo aplica al entrar
en `Emisión masiva`. Si tiene varios, se aplica el marcado como predeterminado.
Si no hay predeterminado, el usuario elige uno.

Si una plantilla se edita y queda una versión nueva, los perfiles que recordaban
la versión anterior deben actualizarse antes de validar nuevos lotes. FactuFlow
rechaza versiones reemplazadas para nuevas cargas para evitar usar mapeos
obsoletos.

El perfil de carga masiva no valida ni emite automáticamente. Solo completa la
pantalla con valores visibles. Antes de validar podés cambiar cualquier selector
o fecha. La fecha de emisión del perfil no puede ser relativa: debe venir del
archivo, quedar para completar en la carga o ser una fecha personalizada cargada
de forma explícita. Si cambiás un dato precargado, esa carga queda como
configuración manual y no como snapshot del perfil de carga masiva.

Por seguridad fiscal, un perfil de carga masiva no ofrece `Fecha actual` como
regla de fecha de emisión.

Las fechas personalizadas de emisión, período de servicios y vencimiento deben
ser fechas reales en `DD/MM/AAAA`. FactuFlow rechaza valores vacíos o
calendarios inválidos como `31/02/2026` y guarda internamente la fecha
normalizada.

Para guardar un perfil con punto de venta fijo, el punto debe estar cargado en
`Puntos de venta` para ese emisor y estar habilitado para usar en FactuFlow. Si
todavía no hay puntos cargados, completalos primero desde esa pantalla.

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

### Plantillas privadas de una instalación

Una instalación puede tener plantillas y perfiles particulares creados por usuarios
autorizados. Su mapeo, punto de venta y ejemplos pertenecen a la
configuración privada y no forman parte de este manual público.

Antes de usar una plantilla particular, revisa en la interfaz sus campos,
constantes, emisor, punto de venta, fechas y total de referencia. Las fechas
ingresadas manualmente se cargan en `DD/MM/AAAA` y una discrepancia de totales
deja el comprobante observado.

### Extractos bancarios

Hay un formato global para extractos bancarios de créditos con estas columnas:
- `Fecha`: fecha de origen del movimiento, usada como fecha del archivo cuando
  el usuario elige esa opción. FactuFlow también interpreta fechas que Excel
  entregue internamente como número serial.
- `Créditos`: importe acreditado, obligatorio
- `Leyendas Adicionales1`: receptor o leyenda equivalente, opcional
- `Leyendas Adicionales2`: documento del receptor, opcional
- `Pto Vta`: punto de venta, obligatorio

Cada fila del extracto genera un comprobante. El formato global está pensado
para emisores Exento o Monotributo y usa Factura C e IVA `0`; no crea cliente
persistente por defecto. No define por si solo si el lote es de productos o
servicios, ni qué descripción del ítem se va a facturar: debes elegir el tipo de
concepto fiscal ARCA y definir la descripción facturada antes de validar. Si el
documento o receptor vienen vacíos, aplican las reglas vigentes de consumidor
final. Para emisores Responsable Inscripto, el lote queda observado y se debe
crear un formato particular con Factura A/B según corresponda.

En Factura C los ítems deben tener IVA 0. En nueva factura, FactuFlow limita el
selector de IVA a 0 cuando elegís Factura C; en emisión masiva, los lotes tipo C
con IVA distinto de 0 quedan con error antes de emitir. FactuFlow no informa el
bloque IVA a ARCA para ese tipo de comprobante, porque el web service lo rechaza
aunque la alícuota sea cero.

### Notas de crédito por lote

La plantilla oficial también puede usarse para notas de crédito. Para Nota de
Crédito C se usa `tipo_comprobante = 13`.

Cuando una nota de crédito anula o ajusta una factura, el Excel debe incluir el
comprobante asociado:
- `asociado_tipo_comprobante`
- `asociado_punto_venta`
- `asociado_numero`
- `asociado_fecha`
- `asociado_cuit`

FactuFlow valida que esos datos existan antes de dejar la nota de crédito lista
para emitir, y los informa a ARCA como `CbtesAsoc`. No cargues importes
negativos: el importe se carga positivo y el tipo de comprobante define que se
trata de un crédito.

Si elegís servicios, no se debe emitir sin revisar el período de servicios. La
fecha del extracto puede usarse como fecha de emisión o como base del período
solo si el usuario lo confirma y ARCA la admite para la fecha en que se solicita
el CAE.

Si el archivo observado informa que un punto de venta no está habilitado, primero
contrastá `Puntos de venta > Sincronizar con ARCA` para el emisor activo. Usá
solo puntos Web Services activos, no bloqueados y sin fecha de baja; si ARCA
marca un punto como bloqueado o inexistente, no lo uses para emitir desde ese
lote.

Si el archivo externo trae una columna para distinguir productos y servicios,
usa `Definido por archivo` solo cuando todas las filas esten completas con
`Producto` o `Servicio`. No cargues el archivo esperando que FactuFlow decida el
concepto por defecto.

Si el archivo externo trae una columna con la descripción a facturar, usala como
descripción del ítem. Si no la trae, define un texto fijo para todo el lote
antes de validar. No confundas esa descripción con `Productos` o `Servicios`:
son datos distintos.

Reglas principales:
- un lote pertenece a un solo emisor activo
- un comprobante puede ocupar varias filas agrupadas por `comprobante_ref`
- los clientes precargados son opcionales para emisión masiva
- para consumidor final en comprobantes B/C de importe menor a `$10.000.000`,
  puedes dejar vacíos tipo de documento, número, nombre y domicilio; FactuFlow
  lo normaliza como `A CONSUMIDOR FINAL`
- si el importe de consumidor final es igual o superior a `$10.000.000`, debes
  informar CUIT, CUIL, CDI, DNI, pasaporte u otro documento válido
- los comprobantes guardan una copia fiscal del receptor al emitir; editar un
  cliente después no cambia el receptor histórico del comprobante
- los errores se muestran por fila o por comprobante
- las alícuotas de IVA permitidas son `0`, `10.5`, `21` y `27`
- el concepto fiscal ARCA del lote siempre debe ser confirmado por el usuario:
  productos, servicios o definido por archivo
- la descripción/concepto facturado del ítem siempre debe venir del archivo o de
  un valor fijo confirmado para el lote
- los lotes chicos y grandes se procesan con seguimiento automático desde la UI
- la barra de progreso muestra avance, tiempo transcurrido y estimación restante
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
corresponde. Los comprobantes C autorizados con IVA 0 se incluyen como importes
exentos, con signo negativo cuando son notas de crédito. En comprobantes A/B,
los ítems guardados con IVA 0 se muestran como no gravados porque FactuFlow aún
no distingue otro subtipo fiscal para esa alícuota.

## 8. Certificados

En `Certificados` gestiónás los certificados de ARCA por ambiente.

Uso recomendado:
- trabajar primero en homologación
- verificar vigencia del certificado antes de emitir
- mantener un solo certificado activo por empresa y ambiente

Las claves privadas generadas por FactuFlow quedan guardadas dentro del
directorio de certificados configurado y cifradas por la aplicación. Si subís
una renovación para el mismo emisor y ambiente, FactuFlow deja activo el
certificado nuevo y conserva el anterior como histórico inactivo.

Los archivos de certificado de ARCA son pequeños. Si el `.crt`, `.cer` o `.pem`
supera el límite técnico `CERTIFICATE_MAX_UPLOAD_BYTES`, FactuFlow lo rechaza
antes de guardarlo para proteger memoria y almacenamiento del servidor.

En la pantalla actual puedes:
- ver nombre, CUIT, ambiente y vencimiento
- agregar un certificado
- probar la conexión del certificado activo contra ARCA antes de emitir
- eliminar un certificado

Si cambias el emisor activo mientras la lista está cargando, FactuFlow descarta
la respuesta anterior para evitar mezclar certificados entre CUITs. También
cierra una confirmación de borrado que haya quedado abierta: vuelve a seleccionar
el certificado desde el nuevo emisor antes de ejecutar cualquier acción.

Al cargar un certificado nuevo, el wizard muestra una barra de pasos con avance
visual y estados de completado. Incluye un paso obligatorio para autorizar el
servicio `WSFE` en ARCA antes de probar la conexión. En producción esa
autorización se hace desde `Administrador de Relaciones de Clave Fiscal`; en
homologación se hace desde WSASS. El certificado puede ser válido y aun así
fallar si no está asociado a ese servicio.

Antes de emitir comprobantes reales en producción, usa `Probar conexión` sobre
el certificado productivo del emisor activo. La prueba valida la comunicación
con ARCA usando ese certificado, sin generar comprobantes ni consumir
numeración fiscal. Mientras la consulta está en curso, `Reintentar` permanece
bloqueado para no enviar verificaciones concurrentes. Los tickets técnicos de ARCA quedan asociados al certificado
que los generó, por lo que una renovación no reutiliza credenciales cacheadas de
otro certificado del mismo emisor.

En `Puntos de venta`, la sincronización con ARCA se habilita solo cuando existe
un certificado activo del emisor para el ambiente backend actual
(`homologación` o `producción`) y siguen disponibles tanto el certificado
público como su clave privada. Un certificado activo de otro ambiente o con
archivos locales faltantes no habilita esa acción. En ese caso, revisá
`Certificados` y restaurá o cargá nuevamente el material correspondiente antes
de sincronizar.

## 9. Puntos de venta

En `Puntos de venta` puedes ver y sincronizar los puntos de venta habilitados para el emisor activo.

Importante:
- el número debe coincidir con el punto de venta habilitado en ARCA para el sistema usado
- para homologación o producción con webservices, validar el punto de venta antes de emitir
- puedes usar `Sincronizar con ARCA` para contrastar lo local con el servicio
- la sincronización importa o actualiza puntos no bloqueados y sin fecha de
  baja como puntos Web Services usables
- si cambias el emisor activo mientras la pantalla está cargando, FactuFlow
  descarta la respuesta anterior para no mezclar puntos de venta entre CUITs y
  cierra cualquier editor pendiente del emisor anterior
- puedes usar `Importar constancia` para cargar el PDF de ARCA con la lista
  completa de puntos, incluyendo sistema, domicilio y nombre de fantasía; si
  cambias de emisor durante la carga, FactuFlow descarta la notificación del
  contexto anterior
- si `Importar constancia` no puede consultar el estado técnico en ARCA,
  conserva el estado local de los puntos existentes y deja inactivos los puntos
  nuevos hasta sincronizar con ARCA o revisarlos manualmente
- FactuFlow marca como `Usable` solo los puntos Web Services activos, no
  bloqueados y sin baja; los puntos Factuweb, Comprobantes en Línea o
  Controlador Fiscal quedan visibles como referencia pero no se usan para emitir
- los datos importados se pueden editar manualmente desde `Editar`

## 10. Emisores

En `Emisores` puedes consultar los datos fiscales y generales del emisor
activo asignado. Solo los administradores pueden editar y guardar esa ficha o
agregar otro CUIT para operar. Si eres administrador, completa `Ingresos
Brutos` para que ese dato salga informado en los PDFs.

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

Al agregar un emisor como administrador, puedes subir una constancia de inscripción ARCA en PDF o
una constancia de opción de Monotributo. FactuFlow intenta completar
automáticamente nombre fiscal, CUIT, condición IVA, domicilio fiscal, localidad,
provincia, código postal e inicio de actividades. Provincia se elige desde un
catálogo cerrado de provincias argentinas; si la constancia no permite
detectarla con seguridad, queda pendiente de revisión manual.
Antes de guardar, revisa y corrige cualquier dato detectado.

Revisa especialmente:
- CUIT
- razón social
- domicilio
- condición IVA
- fecha de inicio de actividades
- email y teléfono de contacto

## 11. Usuarios

La pantalla `Usuarios` solo aparece para usuarios administradores.

Desde esa pantalla puedes:
- crear usuarios
- editar nombre, email, estado, rol y emisor asignado
- desactivar usuarios
- reactivar usuarios
- restablecer contraseñas

Un usuario común puede operar únicamente el emisor asignado en su cuenta:
emitir comprobantes, administrar certificados, sincronizar puntos de venta, usar
emisión masiva y consultar reportes dentro de ese emisor. Puede consultar la
ficha del emisor, pero no modificarla. Si necesita operar otro emisor o cambiar
sus datos, un administrador debe actualizar la asignación o realizar el cambio.

El rol `Administrador` significa que puede administrar usuarios, crear y
editar emisores, y operar todos los emisores configurados. El borrado físico de
un emisor queda reservado a administradores porque puede afectar historial
fiscal y relaciones internas.

Desactivar un usuario impide que vuelva a iniciar sesión, pero no borra su
historial. FactuFlow no permite que un administrador se desactive a sí mismo ni
se quite su propio permiso de administrador desde la pantalla.

## 12. Sistema

La sección `Sistema` solo aparece para usuarios administradores. Incluye las
pestañas `Estado` y `Almacenamiento`.

Desde `Sistema > Estado` puedes ver señales operativas básicas:
- aplicación backend disponible
- base de datos disponible
- worker de lotes y separación de capacidad entre API y worker
- certificado local del emisor activo para el ambiente ARCA configurado
- conexión ARCA como prueba manual explícita
- resumen de almacenamiento
- señales todavía pendientes, como último backup y acceso a logs según entorno
- guía rápida de soporte con qué revisar, próximo paso seguro y cuándo detenerse
  ante fallas frecuentes
- ficha para soporte con datos mínimos: entorno, emisor activo, recurso afectado,
  estado visible, acción ARCA si existió y evidencia privada fuera de Git

La pantalla usa estados simples: `Correcto`, `Necesita atención` y
`No disponible`. En PostgreSQL, la configuración esperada reserva hasta `4`
conexiones para la API, sin overflow, y `1` conexión dedicada al worker. En
SQLite, que API y worker compartan un único engine es el comportamiento esperado
y no se muestra como degradación. El diagnóstico no expone DSN, credenciales,
rutas privadas ni errores internos crudos.

Si la base responde `503` antes de iniciar la solicitud fiscal, FactuFlow confirmó
una recuperación durable sin intentos: reintenta la misma operación con la misma
clave. Ante `409 pre_arca_estado_bloqueado`, conserva la clave y pide revisión o
espera, sin abrir otra operación ni reconciliar ARCA si FECAE no comenzó. Si el
`409` es posterior a esa frontera, indica `Requiere reconciliación` o no sabes si
ARCA fue llamada, no generes otra clave ni cambies los datos: conserva la
operación y pide revisión. La pantalla dedicada para verificar y congelar este
estado forma parte del siguiente corte; hasta entonces, un mensaje genérico no
habilita a reemitir. La acción `Probar conexión`
puede llamar a ARCA; no se ejecuta automáticamente al abrir la pantalla. La guía
rápida y la ficha para soporte no reemplazan el runbook privado del VPS ni
autorizan reintentos fiscales automáticos cuando existe incertidumbre post-ARCA.

La separación `4+1` fue verificada con una prueba PostgreSQL efímera que no creó
lotes ni llamó a ARCA. Esa prueba no demuestra que el corte esté desplegado: para
una instalación concreta, soporte debe confirmar primero el commit o tag activo.

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

Al 2026-07-10:

- no existe todavía descarga masiva de PDFs desde el listado
- el PDF se genera bajo demanda y no debe quedar como archivo permanente en el
  servidor cuando la instalación corre en VPS
- los artefactos descargables no vitales, como PDFs, ZIPs, archivos observados
  y temporales, deben descargarse a la PC del usuario y limpiarse del servidor
  después de cumplir su propósito operativo
- el gestor de almacenamiento ya permite diagnóstico, resguardo ZIP y limpieza
  manual de lotes compactables, logs antiguos, temporales y certificados
  huérfanos; todavía no reemplaza una política completa de backup y
  restauración
- los reportes son de consulta, no de exportación
- la validación concluyente de homologación se hace por webservice, no por QR
- el launcher local de Windows es manual y está orientado a desarrollo/QA; no
  es todavía un instalador ni configura inicio automático con Windows
- la producción real ya fue operada; antes de cada nueva emisión productiva hay
  que revisar punto de venta, fecha fiscal, formato, concepto fiscal ARCA,
  descripción facturada, totales, backup/logs y confirmación irreversible
- `Sistema > Estado` ya muestra un diagnóstico operativo con API, base, worker,
  separación de pools, certificado local, ARCA manual, almacenamiento, guía
  rápida y ficha para soporte; todavía faltan backup visible y trazabilidad
  histórica más completa
- la gestión de lotes ya permite cerrar parciales, reconciliar externos,
  descartar pendientes, compactar y eliminar cargas sin emisión; todavía falta
  una vista administrativa más completa de eventos y trazabilidad histórica
  para soporte
- en el corte local, el seguimiento liviano evita polling solapado y usa
  intervalos adaptativos; PostgreSQL separa el pool API del worker y el contrato
  `4+1` fue probado en una instancia efímera, pero aún debe confirmarse el
  despliegue y la prueba controlada del entorno operativo antes de ampliar
  volumen; no ejecutes varios lotes grandes en paralelo ni reintentes uno
  demorado sin revisar antes su estado
