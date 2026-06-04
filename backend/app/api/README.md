# API (FastAPI)

Esta carpeta contiene los endpoints (routers) de la API REST de FactuFlow.

## Archivos

- `deps.py`: dependencias compartidas (DB session, usuario actual, etc.).
- `health.py`: health checks.
- `auth.py`: setup-status/setup/login/me.
- `usuarios.py`: administración de usuarios por administradores.
- `empresas.py`: CRUD de empresas.
- `clientes.py`: CRUD de clientes.
- `puntos_venta.py`: CRUD de puntos de venta.
- `certificados.py`: gestion de certificados (CSR, upload, verificacion, alertas).
- `arca.py`: integracion ARCA (WSAA/WSFEv1 via `app/arca/`).
- `comprobantes.py`: emision y consulta de comprobantes.
- `lotes_comprobantes.py`: plantilla, validacion, procesamiento y resultados de lotes Excel.
- `almacenamiento.py`: gestor administrativo de almacenamiento, resguardos ZIP
  y limpieza segura de artefactos no vitales.
- `formatos_importacion.py`: listado, creacion y autodeteccion de formatos configurables de Excel.
- `perfiles_carga_masiva.py`: perfiles de carga masiva por emisor para precargar
  configuracion visible de lotes.
- `pdf.py`: generacion/descarga de PDFs.
- `reportes.py`: reportes (ventas, IVA, ranking, etc.).

## Registro de routers

Los routers se registran en `backend/app/main.py` con `app.include_router(...)`.

Routers relacionados con emision masiva:

- `/api/formatos-importacion`: formatos globales y por emisor, mas deteccion de
  candidatos por encabezados.
- `/api/perfiles-carga-masiva`: perfiles de carga masiva del emisor activo.
  Permiten guardar formato sugerido, concepto fiscal ARCA, descripcion
  facturada y reglas de fechas relativas como prellenado visible y editable.
- `/api/lotes-comprobantes`: validacion de Excel, procesamiento con confirmacion
  y descarga de archivo observado. `POST /validar` puede recibir
  `formato_version_id` para aplicar el mapeo confirmado y exige politicas
  fiscales explicitas: `concepto_modo`, `fecha_emision_modo` y fechas fijas
  cuando corresponda. Tambien puede recibir `perfil_carga_masiva_id` para
  guardar snapshot del perfil usado; el perfil no reemplaza esas politicas.

Regla critica: ningun endpoint de emision debe asumir fecha del dia actual como
fecha fiscal. `fecha_emision` debe llegar explicita desde el usuario o desde una
politica de lote confirmada antes de validar.

Regla de usuarios: `es_admin` significa administrar usuarios, no operar emisores.
Todos los usuarios activos pueden operar el emisor activo seleccionado. Solo las
rutas `/api/usuarios` y `/api/almacenamiento` quedan reservadas a
administradores.

Regla de almacenamiento: las rutas `/api/almacenamiento` solo pueden escanear
rutas administradas por FactuFlow y tablas conocidas. No deben devolver rutas
absolutas, CUITs completos, CAEs, nombres de clientes ni contenido de archivos.
La liberación de espacio sobre lotes, logs o temporales debe ocurrir después de
preparar un ZIP de resguardo, descargarlo, confirmar explícitamente la descarga
con checksum y el token emitido por el endpoint de descarga, y confirmar luego
`Ya lo descargué` antes de borrar o compactar.

Regla critica adicional: antes de llamar a un endpoint que pueda solicitar CAE
real, la UI debe mostrar una confirmacion final de fecha fiscal:
`Está seguro que quiere emitir comprobantes con fecha XX/XX/XX? Recuerde que luego no podrá emitir comprobantes con fecha anterior para ese mismo punto de venta.`
No agregar rutas, workers o acciones administrativas que eviten esa confirmacion
sin reemplazarla por una validacion equivalente y visible para el usuario.
Los endpoints actuales tienen una barrera explicita: emision individual exige
`confirmacion_fecha_fiscal=true` en el body y procesamiento de lotes exige
`X-Confirmacion-Fecha-Fiscal` con el token exacto
`fechas=AAAA-MM-DD,...;puntos_venta=N,...`, recalculado desde los grupos
validados.

Regla crítica de idempotencia fiscal: los endpoints que pueden solicitar CAE
deben exigir `X-Idempotency-Key` antes de entrar al flujo ARCA. Actualmente
aplica a `POST /api/comprobantes/emitir`,
`POST /api/lotes-comprobantes/{lote_id}/procesar` y
`POST /api/lotes-comprobantes/{lote_id}/reintentar-fallidos`. Misma clave con
mismo payload devuelve la respuesta o estado persistido sin reemitir; misma
clave con payload distinto devuelve conflicto. La confirmación de duplicado
lógico no forma parte del hash idempotente.

Regla critica: ningun endpoint de emision debe asumir productos o servicios por
default. `concepto` o `concepto_modo` deben llegar explicitamente antes de
emitir o validar lotes. Esto define el tipo de concepto fiscal ARCA, no el texto
facturado.

Regla critica: la descripcion/concepto facturado del item tambien debe llegar de
forma explicita. En emision individual via `items[].descripcion`; en lotes,
desde una columna del archivo o desde un valor fijo confirmado para todo el
lote. No usar defaults ocultos del formato ni reutilizar `Productos`/`Servicios`
como descripcion facturable.

## Convenciones

- Imports absolutos desde `app/`.
- Docstrings en espanol.
- Usar schemas Pydantic para request/response.
- Validar permisos con dependencies.
- Manejar errores con `HTTPException`.
