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
- `certificados.py`: gestión de certificados (CSR, upload, verificación, alertas).
- `arca.py`: integración ARCA (WSAA/WSFEv1 via `app/arca/`).
- `comprobantes.py`: emisión y consulta de comprobantes.
- `lotes_comprobantes.py`: plantilla, validación, procesamiento y resultados de lotes Excel.
- `almacenamiento.py`: gestor administrativo de almacenamiento, resguardos ZIP
  y limpieza segura de artefactos no vitales.
- `formatos_importacion.py`: administración de plantillas/formato de Excel,
  catálogo de campos, análisis de Excel de ejemplo, compatibilidad,
  versionado, clonado, descarga y autodetección.
- `perfiles_carga_masiva.py`: perfiles de carga masiva por emisor para precargar
  configuración visible de lotes.
- `pdf.py`: generación/descarga de PDFs.
- `reportes.py`: reportes (ventas, IVA, ranking, etc.).

## Registro de routers

Los routers se registran en `backend/app/main.py` con `app.include_router(...)`.

Routers relacionados con emisión masiva:

- `/api/formatos-importacion`: plantillas/formato globales y por emisor,
  administración versionada, protección de plantillas del sistema, descarga
  `.xlsx`, compatibilidad con perfil/emisor y detección de candidatos por
  encabezados. Las mutaciones con alcance global quedan reservadas a
  administradores.
- `/api/perfiles-carga-masiva`: perfiles de carga masiva del emisor activo.
  Permiten guardar formato sugerido, concepto fiscal ARCA, descripción
  facturada y reglas de fechas relativas como prellenado visible y editable.
- `/api/lotes-comprobantes`: validación de Excel, procesamiento con confirmación
  y descarga de archivo observado. `POST /validar` puede recibir
  `formato_version_id` para aplicar el mapeo confirmado y exige políticas
  fiscales explícitas: `concepto_modo`, `fecha_emision_modo` y fechas fijas
  cuando corresponda. También puede recibir `perfil_carga_masiva_id` para
  guardar snapshot del perfil usado; el perfil no reemplaza esas políticas.

Regla crítica: ningún endpoint de emisión debe asumir fecha del día actual como
fecha fiscal. `fecha_emision` debe llegar explícita desde el usuario o desde una
política de lote confirmada antes de validar.

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

Regla crítica adicional: antes de llamar a un endpoint que pueda solicitar CAE
real, la UI debe mostrar una confirmación final de fecha fiscal:
`Está seguro que quiere emitir comprobantes con fecha XX/XX/XX? Recuerde que luego no podrá emitir comprobantes con fecha anterior para ese mismo punto de venta.`
No agregar rutas, workers o acciones administrativas que eviten esa confirmación
sin reemplazarla por una validación equivalente y visible para el usuario.
Los endpoints actuales tienen una barrera explícita: emisión individual exige
`confirmacion_fecha_fiscal=true` en el body y procesamiento de lotes exige
`X-Confirmacion-Fecha-Fiscal` con el token exacto
`fechas=YYYY-MM-DD,...;puntos_venta=N,...`, recalculado desde los grupos
validados.

Regla crítica de idempotencia fiscal: los endpoints que pueden solicitar CAE
deben exigir `X-Idempotency-Key` antes de entrar al flujo ARCA. Actualmente
aplica a `POST /api/comprobantes/emitir`,
`POST /api/lotes-comprobantes/{lote_id}/procesar` y
`POST /api/lotes-comprobantes/{lote_id}/reintentar-fallidos`. Misma clave con
mismo payload devuelve la respuesta o estado persistido sin reemitir; misma
clave con payload distinto devuelve conflicto. La confirmación de duplicado
lógico no forma parte del hash idempotente.

Regla crítica: ningún endpoint de emisión debe asumir productos o servicios por
default. `concepto` o `concepto_modo` deben llegar explícitamente antes de
emitir o validar lotes. Esto define el tipo de concepto fiscal ARCA, no el texto
facturado.

Regla crítica: la descripción/concepto facturado del ítem también debe llegar de
forma explícita. En emisión individual vía `items[].descripcion`; en lotes,
desde una columna del archivo o desde un valor fijo confirmado para todo el
lote. No usar defaults ocultos del formato ni reutilizar `Productos`/`Servicios`
como descripción facturable.

## Convenciones

- Imports absolutos desde `app/`.
- Docstrings en español.
- Usar schemas Pydantic para request/response.
- Validar permisos con dependencies.
- Manejar errores con `HTTPException`.
