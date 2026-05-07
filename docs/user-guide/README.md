# Manual de usuario - FactuFlow

Ultima actualizacion: 2026-05-05

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
- comprobantes
- emision masiva
- certificados
- reportes

Antes de emitir o consultar informacion, verifica siempre que el emisor activo sea el correcto.

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

La emision masiva esta pensada para cargar muchas facturas desde Excel.

Flujo general:

1. Descargar la plantilla.
2. Completar el archivo respetando las columnas fijas.
3. Subir el Excel.
4. Validar errores por fila o por comprobante.
5. Confirmar la emision.
6. Revisar resultados del lote.
7. Si lo necesitas, descargar el archivo observado del lote.

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
- los lotes chicos se emiten en la misma sesion
- los lotes grandes quedan `En cola` y se procesan en segundo plano con seguimiento automatico

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

Al cargar un certificado nuevo, el wizard incluye un paso obligatorio para
autorizar el servicio `wsfe` en ARCA antes de probar la conexion. En produccion
esa autorizacion se hace desde `Administrador de Relaciones de Clave Fiscal`;
en homologacion se hace desde WSASS. El certificado puede ser valido y aun asi
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
- la sincronizacion importa solo puntos no bloqueados y sin fecha de baja
- puedes usar `Importar constancia` para cargar el PDF de ARCA con la lista
  completa de puntos, incluyendo sistema, domicilio y nombre de fantasia
- FactuFlow marca como `Usable` solo los puntos Web Services activos, no
  bloqueados y sin baja; los puntos Factuweb, Comprobantes en Linea o
  Controlador Fiscal quedan visibles como referencia pero no se usan para emitir
- los datos importados se pueden editar manualmente desde `Editar`

## 10. Emisores

En `Emisores` puedes editar y guardar los datos fiscales y generales del emisor activo, o agregar otro CUIT para operar.

Al agregar un emisor, puedes subir una constancia de inscripcion ARCA en PDF.
FactuFlow intenta completar automaticamente nombre fiscal, CUIT, condicion IVA,
domicilio fiscal, localidad, provincia, codigo postal e inicio de actividades.
Antes de guardar, revisa y corrige cualquier dato detectado.

Revisa especialmente:
- CUIT
- razon social
- domicilio
- condicion IVA
- fecha de inicio de actividades
- email y telefono de contacto

## 11. Limitaciones actuales

Al 2026-05-04:

- no existe todavia descarga masiva de PDFs desde el listado
- el PDF se genera bajo demanda
- los reportes son de consulta, no de exportacion
- la validacion concluyente de homologacion se hace por webservice, no por QR
- para una primera prueba real en produccion sigue faltando configurar certificado y punto de venta productivos
