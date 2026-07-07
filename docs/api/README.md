# API REST de FactuFlow

Última actualización: 2026-07-06

Esta documentación resume el contrato real expuesto por `backend/app/main.py` y
`backend/app/api/*.py`.

## URLs

- Desarrollo local: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/api/docs`
- ReDoc: `http://localhost:8000/api/redoc`
- Todas las rutas funcionales usan prefijo `/api`. No hay versionado en la URL.

## Autenticación

La API usa JWT Bearer.

```http
POST /api/auth/login
Content-Type: application/json

{
  "email": "admin.local@example.test",
  "password": "CAMBIAR_EN_LOCAL"
}
```

Respuesta:

```json
{
  "access_token": "...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "admin.local@example.test",
    "empresa_id": 1,
    "es_admin": true
  }
}
```

Para endpoints protegidos:

```http
Authorization: Bearer {token}
```

Para operar un emisor activo explícito, cualquier usuario autenticado puede
agregar:

```http
X-Empresa-Id: 2
```

También se conserva el query legacy `empresa_id` para compatibilidad. Si se
envían `X-Empresa-Id` y `empresa_id` con valores distintos, la API rechaza el
pedido. El campo `user.es_admin` significa que el usuario puede administrar
usuarios; no limita el acceso operativo a emisores.

## Health

```http
GET /api/health
GET /api/health/db
GET /
```

## Auth

```http
POST /api/auth/login
GET /api/auth/me
GET /api/auth/setup-status
POST /api/auth/setup
```

`GET /api/auth/setup-status` devuelve `{"setup_required": true}` solo cuando no
hay usuarios creados. `POST /api/auth/setup` crea el primer usuario
administrador propietario y queda cerrado en cuanto existe cualquier usuario.

## Usuarios

```http
GET /api/usuarios
POST /api/usuarios
PUT /api/usuarios/{usuario_id}
POST /api/usuarios/{usuario_id}/desactivar
POST /api/usuarios/{usuario_id}/reactivar
POST /api/usuarios/{usuario_id}/reset-password
```

Estos endpoints requieren un usuario con `es_admin=true`. `DELETE` físico de
usuarios no está expuesto: eliminar desde la interfaz significa desactivar
`activo=false`, conservando historial y trazabilidad. El backend impide que un
administrador desactive o degrade su propia cuenta, y también impide cambiar el
email propio desde la sesión actual porque el JWT vigente usa el email como
identificador.

## Almacenamiento

```http
GET /api/almacenamiento/resumen
GET /api/almacenamiento/lotes-compactables
GET /api/almacenamiento/logs
GET /api/almacenamiento/temporales
GET /api/almacenamiento/certificados-huerfanos
POST /api/almacenamiento/exportaciones
GET /api/almacenamiento/exportaciones/{token}/descargar
POST /api/almacenamiento/exportaciones/{token}/confirmar-descarga
POST /api/almacenamiento/exportaciones/{token}/confirmar-liberacion
POST /api/almacenamiento/certificados-huerfanos/limpiar
```

Estos endpoints requieren `es_admin=true`. El gestor informa uso medido,
recuperable, límite configurado, disco real, categorías y desglose seguro por
emisor. No expone rutas absolutas, CUIT completo, CAEs, nombres de clientes ni
contenido privado.

`POST /api/almacenamiento/exportaciones` recibe una selección explícita:

```json
{
  "lote_ids": [12],
  "log_ids": ["factuflow.log.1"],
  "temporal_ids": ["lotes/tmp-observado.xlsx"]
}
```

La respuesta devuelve un token opaco, el nombre del ZIP y
`checksum_sha256`. Para liberar espacio, el cliente debe descargar primero
`GET /api/almacenamiento/exportaciones/{token}/descargar`, confirmar que el ZIP
llegó al cliente usando el header `X-FactuFlow-Download-Token`, y recién
después liberar:

```json
{
  "checksum_sha256": "...",
  "download_token": "..."
}
```

La confirmación de liberación usa:

```json
{
  "confirmacion": "YA_LO_DESCARGUE"
}
```

La liberación valida contra el manifest del ZIP que logs y temporales no hayan
cambiado desde el resguardo; si cambiaron, no los borra. Luego compacta lotes
cerrados seleccionados y elimina logs/temporales revalidados por el servidor.
Los certificados no se incluyen en el ZIP; la limpieza de certificados huérfanos
usa una acción separada y solo acepta archivos gestionados por FactuFlow que no
estén referenciados por la base.

## Empresas / Emisores

```http
GET /api/empresas
POST /api/empresas
POST /api/empresas/extraer-constancia
GET /api/empresas/{empresa_id}
PUT /api/empresas/{empresa_id}
DELETE /api/empresas/{empresa_id}
```

`POST /api/empresas/extraer-constancia` recibe una constancia ARCA en PDF y
devuelve datos fiscales detectados para precompletar el alta de emisor.

Todos los usuarios activos pueden listar, crear y editar emisores. El borrado
físico `DELETE /api/empresas/{empresa_id}` queda reservado a administradores y
solo se permite para emisores sin datos operativos o fiscales asociados. Si
existen comprobantes, lotes, intentos fiscales, certificados, puntos de venta,
clientes, perfiles o formatos de importación del emisor, la API responde `409`
y conserva el historial. Si un usuario tenía ese emisor vacío como preferido,
la API limpia esa preferencia antes de borrar el emisor; no borra la cuenta del
usuario.

Los emisores aceptan `ingresos_brutos` como campo opcional. Si está cargado, se
usa en el PDF de comprobantes. Cuando un emisor ya tiene datos operativos o
fiscales asociados, `PUT /api/empresas/{empresa_id}` rechaza con `409` cambios
en identidad fiscal (`razon_social`, `cuit`, `condicion_iva`,
`ingresos_brutos`, domicilio, localidad, provincia, código postal e inicio de
actividades). Los datos no fiscales, como email, teléfono y logo, pueden seguir
actualizándose.

## Clientes

```http
GET /api/clientes
POST /api/clientes
GET /api/clientes/{cliente_id}
PUT /api/clientes/{cliente_id}
DELETE /api/clientes/{cliente_id}
```

Listado:

- `page`: página, default `1`
- `per_page`: filas por página
- `search`: busqueda por razon social o documento
- `activo`: filtro opcional

La respuesta de listado es paginada con `items`, `total`, `page`, `per_page` y
`pages`.

## Puntos De Venta

```http
GET /api/puntos-venta
POST /api/puntos-venta
POST /api/puntos-venta/importar-constancia
PUT /api/puntos-venta/{punto_venta_id}
DELETE /api/puntos-venta/{punto_venta_id}
```

`POST /api/puntos-venta/importar-constancia` recibe un PDF de constancia ARCA y
actualiza sistema, domicilio, nombre fantasia, estado bloqueado y usabilidad
FactuFlow. Un punto es usable cuando está activo, es Web Services, no está
bloqueado y no tiene fecha de baja.

## Certificados

```http
GET /api/certificados
GET /api/certificados/keys?cuit={cuit}&ambiente={homologacion|produccion}
GET /api/certificados/alertas-vencimiento
GET /api/certificados/{certificado_id}
DELETE /api/certificados/{certificado_id}
POST /api/certificados/generar-csr
POST /api/certificados/subir-certificado
POST /api/certificados/verificar-conexion/{certificado_id}
```

Flujo real:

1. `POST /api/certificados/generar-csr`
2. subir el CSR al portal ARCA correspondiente
3. autorizar el servicio `wsfe` para el CUIT representado
4. `POST /api/certificados/subir-certificado`
5. `POST /api/certificados/verificar-conexion/{certificado_id}`

`verificar-conexion` prueba WSAA/ARCA con el certificado y no emite
comprobantes ni consume numeración fiscal.

## ARCA

```http
GET /api/arca/test-conexion
GET /api/arca/status
GET /api/arca/tipos-comprobante
GET /api/arca/tipos-documento
GET /api/arca/tipos-iva
GET /api/arca/tipos-concepto
GET /api/arca/tipos-monedas
GET /api/arca/cotizacion/{moneda_id}
GET /api/arca/puntos-venta
GET /api/arca/ultimo-comprobante/{punto_venta}/{tipo_cbte}
GET /api/arca/consultar-comprobante/{punto_venta}/{tipo_cbte}/{numero}
```

Endpoints seguros para verificar producción sin emitir:

- `GET /api/arca/status`
- `GET /api/arca/test-conexion`
- `GET /api/arca/puntos-venta`
- `GET /api/arca/ultimo-comprobante/{punto_venta}/{tipo_cbte}`

`POST /api/arca/solicitar-cae` es un endpoint legacy deshabilitado. Requiere
autenticación, pero responde `410 Gone` y no llama a ARCA. Para emitir se debe
usar `POST /api/comprobantes/emitir` o el flujo de lotes, que aplican
idempotencia, persistencia de intento fiscal y confirmación irreversible antes
de solicitar CAE.

## Comprobantes

```http
GET /api/comprobantes/
GET /api/comprobantes/{comprobante_id}
POST /api/comprobantes/emitir
GET /api/comprobantes/proximo-numero/{punto_venta_id}/{tipo_comprobante}
```

`POST /api/comprobantes/emitir` emite a través del servicio de facturación y
puede consumir numeración fiscal si `ARCA_ENV=produccion`.

Este endpoint exige el header `X-Idempotency-Key`. El cliente debe generar una
clave nueva por confirmación fiscal final y conservarla para retries de la
misma operación. Misma clave con mismo payload devuelve la respuesta persistida
o el estado actual sin volver a llamar a ARCA; misma clave con datos distintos
devuelve `409`; clave ausente devuelve `400`.

Las fechas visibles que se muestran al usuario deben formatearse como `DD/MM/AAAA`. Los contratos técnicos de API pueden seguir usando `YYYY-MM-DD`, ISO datetime o `CbteFch` `YYYYMMDD` según corresponda, convirtiendo siempre en los bordes.

El body debe incluir `fecha_emision`. FactuFlow no la completa con la fecha del
día. Para comprobantes de servicios o productos y servicios también deben
informarse `fecha_servicio_desde`, `fecha_servicio_hasta` y `fecha_vto_pago`.
El backend valida preventivamente que `fecha_emision` esté dentro de la ventana
ARCA aplicable antes de solicitar CAE.

La UI debe mostrar una confirmación final antes de invocar este endpoint en
producción: `Está seguro que quiere emitir comprobantes con fecha XX/XX/XX?
Recuerde que luego no podrá emitir comprobantes con fecha anterior para ese
mismo punto de venta.` El body debe enviar `confirmacion_fecha_fiscal=true`
después de ese modal; si no llega, la API rechaza la emisión.

Si el backend detecta un duplicado lógico probable, responde `409` con
`categoria_error=duplicado_logico`. El cliente puede volver a enviar el mismo
payload y la misma `X-Idempotency-Key` con `confirmacion_duplicado_logico=true`
después de mostrar una advertencia adicional al usuario. Esa confirmación no
forma parte del hash idempotente.

El body también debe definir explícitamente el concepto fiscal ARCA. No se debe
asumir productos ni servicios por default. Los valores operativos esperados son
productos, servicios o, en flujos masivos, definido por archivo. Este dato no es
la descripción del ítem: cada ítem debe traer su `descripcion` real, por ejemplo
`Honorarios` o `Zapatillas`, como texto facturado independiente del concepto
fiscal ARCA.

## Plantillas / Formatos De Importación

```http
GET /api/formatos-importacion
POST /api/formatos-importacion
GET /api/formatos-importacion/catalogo-campos
POST /api/formatos-importacion/analizar-excel
POST /api/formatos-importacion/compatibilidad
POST /api/formatos-importacion/detectar
GET /api/formatos-importacion/{formato_id}
PUT /api/formatos-importacion/{formato_id}
DELETE /api/formatos-importacion/{formato_id}
POST /api/formatos-importacion/{formato_id}/clonar
GET /api/formatos-importacion/{formato_id}/descargar
```

La UI habla de `Plantillas`. Internamente siguen siendo
`formatos_importacion` versionados para no duplicar dominio ni romper lotes
existentes. Todos respetan el emisor activo resuelto por `X-Empresa-Id`, por el
query legacy `empresa_id` o por la preferencia del usuario.

`GET /api/formatos-importacion` lista plantillas globales y plantillas
particulares del emisor activo. Cada una expone su `version_vigente`.

`POST /api/formatos-importacion` crea una plantilla. Los usuarios activos pueden
crear plantillas con `alcance=emisor`; `alcance=global` queda reservado a
administradores porque afecta a todos los emisores. Las plantillas internas del
sistema se marcan en `configuracion_json.plantilla_sistema_protegida=true`: se
pueden clonar, pero no editar ni desactivar directamente.

`PUT /api/formatos-importacion/{formato_id}` actualiza datos y, si cambia
`configuracion_json`, reemplaza la versión vigente por una versión nueva. No
borra versiones históricas usadas por lotes. Solo administradores pueden editar
plantillas globales o promover una plantilla de emisor a global.

`DELETE /api/formatos-importacion/{formato_id}` es soft-delete:
`activo=false`.

`POST /api/formatos-importacion/{formato_id}/clonar` crea una copia editable y
quita la marca protegida si venía de una plantilla del sistema.

`GET /api/formatos-importacion/{formato_id}/descargar` genera un `.xlsx` bajo
demanda con hoja `Comprobantes`, hoja `Instrucciones` y hoja oculta
`_factuflow` con metadatos no fiscales. La validación backend no confía en esos
metadatos para emitir.

`GET /api/formatos-importacion/catalogo-campos` devuelve los campos FactuFlow
disponibles para el constructor visual, agrupados por emisor, comprobante,
receptor, fechas, ítems, totales y comprobantes asociados.

Ejemplo mínimo de configuración:

```json
{
  "nombre": "Banco X - creditos",
  "descripcion": "Extracto mensual del banco X",
  "alcance": "emisor",
  "configuracion_json": {
    "tipo": "extracto_bancario_creditos",
    "header_row": 1,
    "modo_agrupacion": "fila",
    "plantilla": {
      "nombre_publico": "Banco X - créditos",
      "columnas": [
        {
          "campo_destino": "importe_total",
          "etiqueta": "Créditos",
          "origen": "header",
          "transformacion": "decimal",
          "requerido": true,
          "ejemplo": "10000.00"
        }
      ]
    },
    "campos": {
      "importe_total": {
        "origen": "header",
        "encabezados": ["Créditos", "Creditos"],
        "transformacion": "decimal",
        "requerido": true
      },
      "punto_venta_numero": {
        "origen": "columna",
        "letra_columna": "E",
        "transformacion": "entero",
        "requerido": true
      },
      "tipo_comprobante": {
        "origen": "constante",
        "valor": 11
      }
    }
  }
}
```

Origenes soportados en `campos`:

- `header`: busca encabezados o alias normalizados.
- `columna`: usa `letra_columna` o `indice_columna`.
- `constante`: usa `valor` para completar siempre el mismo dato.
- `empresa`: toma datos del emisor activo solo cuando el campo tiene resolvedor
  implementado; en esta versión se limita a `empresa_cuit`.

`POST /api/formatos-importacion/analizar-excel` recibe `multipart/form-data`
con `archivo` (`.xlsx`) y devuelve hoja, fila de encabezado y columnas
detectadas. Sirve para iniciar el constructor visual desde un Excel de ejemplo.

`POST /api/formatos-importacion/compatibilidad` recibe:

```json
{
  "configuracion_json": {},
  "perfil_configuracion_json": {}
}
```

Devuelve `estado` (`compatible`, `advertencia` o `incompatible`) y mensajes
separados en `faltantes`, `omitibles`, `advertencias` y `conflictos`. Cruza la
plantilla con el perfil y el emisor activo para detectar columnas faltantes,
datos omitibles porque el perfil fija valores, conflictos donde el perfil exige
datos desde archivo y la plantilla no los trae, incompatibilidades de
Responsable Inscripto/Monotributo/Exento con tipos A/B/C, productos/servicios y
notas de crédito/débito sin comprobante asociado.

`POST /api/formatos-importacion/detectar` recibe `multipart/form-data` con
`archivo` (`.xlsx`). El backend rechaza archivos que superen
`BATCH_MAX_UPLOAD_BYTES` o que no puedan abrirse como XLSX válido antes de
intentar detectar encabezados. Si el archivo es válido, devuelve:

```json
{
  "headers_detectados": [
    "Fecha",
    "Créditos",
    "Leyendas Adicionales1",
    "Leyendas Adicionales2",
    "Pto Vta"
  ],
  "candidatos": [
    {
      "formato_id": 1,
      "formato_version_id": 1,
      "nombre": "Extracto bancario - creditos IVA exento",
      "alcance": "global",
      "version": 1,
      "score": 1.0,
      "confianza": "alta",
      "columnas_detectadas": [
        "Fecha",
        "Créditos",
        "Leyendas Adicionales1",
        "Leyendas Adicionales2",
        "Pto Vta"
      ],
      "columnas_faltantes": [],
      "mensajes": ["Coincide con las columnas requeridas."]
    }
  ],
  "formato_sugerido_version_id": 1,
  "requiere_confirmacion": true
}
```

El cliente debe confirmar el formato antes de validar cualquier archivo externo.
La deteccion automática es una sugerencia: no crea lotes ni consume numeración.

Formato global inicial:

- Nombre: `Extracto bancario - creditos IVA exento`
- Columnas esperadas: `Fecha`, `Créditos`/`Creditos`,
  `Leyendas Adicionales1`, `Leyendas Adicionales2`, `Pto Vta`
- Requeridas: `Créditos`/`Creditos` y `Pto Vta`
- Cada fila genera un comprobante con Factura C (`tipo_comprobante=11`) e IVA
  `0`, y cliente no persistente. El formato no debe definir por defecto ni el
  concepto fiscal ARCA ni la descripción facturada del ítem: el usuario debe
  elegir productos, servicios o archivo para el dato fiscal, y archivo o valor
  fijo para el texto del ítem antes de validar.
- Este formato global está pensado para emisores Exento o Monotributo. Si el
  emisor activo es Responsable Inscripto, la validación observa el lote para
  evitar emitir Factura C incorrectamente.

## Lotes De Comprobantes

```http
GET /api/lotes-comprobantes
GET /api/lotes-comprobantes/plantilla
POST /api/lotes-comprobantes/validar
POST /api/lotes-comprobantes/{lote_id}/procesar
POST /api/lotes-comprobantes/{lote_id}/reintentar-fallidos
GET /api/lotes-comprobantes/{lote_id}/resumen
GET /api/lotes-comprobantes/{lote_id}/grupos
GET /api/lotes-comprobantes/{lote_id}
GET /api/lotes-comprobantes/{lote_id}/resultados
GET /api/lotes-comprobantes/{lote_id}/archivo-observado
```

El flujo correcto es validar primero el Excel y procesar solo cuando el usuario
confirma. Lotes grandes pueden quedar en cola y continuar por worker. La UI usa
`POST /api/lotes-comprobantes/{lote_id}/procesar?background=true` también para
lotes chicos, para mostrar progreso real por polling.

Para pantallas de usuario, preferir `GET /api/lotes-comprobantes/{lote_id}/resumen`
y `GET /api/lotes-comprobantes/{lote_id}/grupos` en lugar de abrir el detalle
completo con todas las filas. El endpoint de resumen devuelve los contadores,
totales listos para emitir, fechas/puntos validados y el token exacto de
confirmación fiscal para el lote completo. El endpoint de grupos acepta
`page`, `per_page` (máximo 200) y `estado` opcional, y devuelve la página con
`items`, `total`, `total_pages`, `page` y `per_page`.

`GET /api/lotes-comprobantes/{lote_id}` y `/resultados` conservan el contrato
legacy de detalle completo con `grupos` y `filas`. No deben usarse para abrir
lotes grandes en la UI porque pueden traer miles de registros.

`POST /api/lotes-comprobantes/validar` recibe `multipart/form-data`:

- `archivo`: Excel `.xlsx`.
  El backend rechaza archivos que superen `BATCH_MAX_UPLOAD_BYTES` o que no
  puedan abrirse como XLSX válido.
- `formato_version_id`: opcional. Si no se envía y el archivo coincide con la
  plantilla oficial, se usa la plantilla FactuFlow. Para archivos externos,
  enviar la versión confirmada por `POST /api/formatos-importacion/detectar`.
- `perfil_carga_masiva_id`: opcional. Si se envía, la validación guarda un
  snapshot del perfil de carga masiva aplicado. La UI debe omitirlo si el
  usuario modifica la configuración precargada antes de validar. El perfil no
  reemplaza las políticas fiscales del form; esas políticas deben llegar ya
  resueltas y visibles para el usuario.
- `punto_venta_modo`: opcional, default `archivo`. Valores: `archivo` o
  `fijo`. Si es `archivo`, se usa el punto de venta mapeado desde el Excel. Si
  es `fijo`, la validación sobrescribe el punto de venta de todas las filas con
  `punto_venta_numero`.
- `punto_venta_numero`: requerido cuando `punto_venta_modo=fijo`. Debe existir
  para el emisor activo y estar activo, Web Services, no bloqueado y sin fecha
  de baja. Si no está cargado en `Puntos de venta`, la API rechaza la
  validación.
- `fecha_emision_modo`: obligatorio. Valores: `archivo` o `fija`.
- `fecha_emision_fija`: obligatorio solo si `fecha_emision_modo=fija`.
- `concepto_modo`: obligatorio. Valores: `productos`, `servicios` o `archivo`.
- Si `concepto_modo=archivo`, el formato confirmado debe mapear una columna del
  Excel con `Producto` o `Servicio` en todas las filas. No se envia un nombre de
  columna aparte en el form; se toma del mapeo del formato/plantilla.
- `item_descripcion_modo`: requerido por contrato operativo para lotes
  externos. Valores esperados: `archivo` o `fija`.
- `item_descripcion_fija`: requerido cuando `item_descripcion_modo=fija`.
- Si `item_descripcion_modo=archivo`, el formato/plantilla debe mapear una
  columna con la descripción/concepto facturado del ítem. Este texto es
  independiente de `concepto_modo`: `Productos` o `Servicios` no son una
  descripción facturable suficiente.
- `fecha_servicio_desde_modo`, `fecha_servicio_hasta_modo` y
  `fecha_vto_pago_modo`: valores `archivo` o `fija` para comprobantes de
  servicios.
- `fecha_servicio_desde_fija`, `fecha_servicio_hasta_fija` y
  `fecha_vto_pago_fija`: obligatorias cuando el modo correspondiente es `fija`.

La validación persiste el lote, encabezados detectados, mapeo usado y versión de
formato. No emite comprobantes. La emisión ocurre solo con
`POST /api/lotes-comprobantes/{lote_id}/procesar`.

`POST /api/lotes-comprobantes/{lote_id}/procesar` acepta query param opcional:

- `background=true`: deja el lote en cola para procesamiento por worker aunque
  sea un lote chico. La respuesta devuelve `en_progreso=true`, estado `en_cola`
  y el cliente debe consultar `GET /api/lotes-comprobantes/{lote_id}` para
  actualizar progreso, contadores, `started_at`, `finished_at` y
  `mensaje_resumen`.
- sin `background=true`: conserva compatibilidad con clientes existentes; lotes
  chicos se procesan en la misma request y lotes grandes se encolan según
  `BATCH_SYNC_LIMIT`.

Este endpoint exige `X-Idempotency-Key`. La clave cubre lote, modo background y
confirmación fiscal; debe mantenerse para retries de la misma operación. Si el
lote tiene duplicados lógicos probables, la API responde `409` con
`categoria_error=duplicado_logico_lote` y `confirmacion_duplicado_logico`. El
cliente debe mostrar una advertencia adicional y, si el usuario decide
continuar, reenviar la misma clave con el header
`X-Confirmacion-Duplicado-Logico` igual al token recibido.

`POST /api/lotes-comprobantes/{lote_id}/reintentar-fallidos` comparte el mismo
contrato idempotente: exige `X-Idempotency-Key`,
`X-Confirmacion-Fecha-Fiscal` y, si corresponde,
`X-Confirmacion-Duplicado-Logico`. El body puede incluir `grupo_ids` para
acotar el reintento. Un grupo tomado para reintento que queda incierto debe
tratarse como reconciliable, no como fallido reintentable.

Durante el procesamiento, el backend actualiza `grupos_emitidos`,
`grupos_fallidos`, `grupos_validos` y `mensaje_resumen` después de cada grupo,
para que la UI pueda mostrar avance real, tiempo transcurrido y estimación
restante sin usar SSE/WebSocket.

Regla fiscal crítica: FactuFlow no asume fecha de emisión del día actual. La
fecha de comprobante debe venir del archivo o de una fecha fija confirmada por
el usuario. La validación observa los comprobantes cuya fecha queda fuera de la
ventana admitida por ARCA antes de permitir emitir. Si la fecha del archivo
queda fuera de ventana, el usuario debe elegir una fecha permitida y revalidar.
Antes de llamar a `procesar`, el cliente debe mostrar la confirmación final de
fecha fiscal con el mismo texto usado en emisión individual y enviar el header
`X-Confirmacion-Fecha-Fiscal` con el token exacto derivado de los grupos
validados:

```http
X-Confirmacion-Fecha-Fiscal: fechas=YYYY-MM-DD,...;puntos_venta=N,...
```

La API recalcula ese token desde el lote validado y rechaza la emisión si falta
o no coincide. Esto evita confirmar un lote distinto al que el usuario revisó.

Regla fiscal crítica: FactuFlow tampoco asume si el lote corresponde a productos
o servicios. El usuario debe elegirlo antes de validar, o confirmar que el
archivo trae esa definición fila por fila. Si se usa `archivo`, la columna
configurada debe existir y todas las filas deben tener `Producto` o `Servicio`;
si falta o hay valores inválidos, la API debe devolver errores de validación
para informar al usuario y no dejar el lote listo para emitir.

Regla de ítem crítica: el concepto fiscal ARCA no es la descripción/concepto
facturado del ítem. El lote también debe definir la descripción del ítem antes
de validar o emitir, desde archivo o como valor fijo para todo el lote. No debe
haber defaults ocultos como descripción facturada.

## Perfiles De Carga Masiva

```http
GET /api/perfiles-carga-masiva
POST /api/perfiles-carga-masiva
PUT /api/perfiles-carga-masiva/{perfil_id}
DELETE /api/perfiles-carga-masiva/{perfil_id}
POST /api/perfiles-carga-masiva/{perfil_id}/predeterminado
```

Los perfiles de carga masiva pertenecen al emisor activo resuelto por JWT y
`X-Empresa-Id`. Permiten guardar una configuración visible para precargar
`Emision masiva`: plantilla/formato opcional, punto de venta, concepto fiscal
ARCA, descripción facturada y reglas relativas de fechas.

El payload usa `configuracion_json` versionado. Valores principales:
- `formato_importacion_version_id`: opcional; debe ser global o pertenecer al
  emisor activo.
- `punto_venta.modo`: `archivo` para usar el punto definido en el Excel o
  `fijo` para precargar un punto concreto del emisor.
- `punto_venta.numero`: requerido cuando `punto_venta.modo=fijo`; debe estar
  cargado como punto usable por FactuFlow en `Puntos de venta`.
- `concepto_modo`: `productos`, `servicios`, `archivo` o vacío para completar
  en la carga.
- `descripcion_item_modo`: `archivo`, `fija` o vacío.
- `fecha_emision.modo`: `archivo`, `manual`, `ultimo_dia_mes_anterior` o
  `personalizada`.
- `periodo_servicio.modo`: `archivo`, `manual`, `mes_anterior_completo`,
  `mes_actual_completo` o `personalizado`.
- `fecha_vto_pago.modo`: `archivo`, `manual`, `mismo_dia_emision`,
  `emision_mas_dias` o `personalizada`.

Regla crítica: el perfil de carga masiva no valida ni emite. La UI debe resolver
las reglas relativas solo cuando exista una base explícita del usuario o una
política del archivo; no debe convertirlas usando la fecha del navegador al
autoaplicar un perfil en `Emision masiva`. Todos los controles deben quedar
visibles y editables antes de validar. `fecha_actual` no es un modo válido de
fecha de emisión para perfiles de carga masiva. Si se marca un perfil como
predeterminado, la API desmarca cualquier otro predeterminado del mismo emisor.

## PDF

```http
GET /api/pdf/comprobante/{comprobante_id}
GET /api/pdf/comprobante/{comprobante_id}/preview
```

El PDF fiscal se genera bajo demanda solo para comprobantes `autorizado` con
CAE y vencimiento de CAE persistidos; si faltan esos datos, la API responde
`409` y no genera un documento rotulado como autorizado. Incluye QR ARCA con
payload Base64 según la especificación oficial y muestra datos fiscales del
emisor/receptor, operación, detalle, totales, CAE y vencimiento CAE. En
comprobantes nuevos de servicios también muestra período facturado y vencimiento
de pago. Los datos libres renderizados en la plantilla se escapan como HTML.

## Reportes

```http
GET /api/reportes/ventas
GET /api/reportes/iva-ventas
GET /api/reportes/clientes
```

Los reportes se calculan para el emisor activo.
`GET /api/reportes/iva-ventas` calcula notas de crédito/débito con signo
fiscal correspondiente y el detalle discrimina alícuotas 10,5%, 21% y 27%.
Los comprobantes C autorizados con IVA cero se informan como importe exento en
el subdiario, también con signo fiscal para notas de crédito.

## Codigos De Error

| Código | Descripción |
| --- | --- |
| 200 | OK |
| 201 | Recurso creado |
| 204 | Sin contenido |
| 400 | Datos inválidos |
| 401 | No autenticado |
| 403 | Sin permisos |
| 404 | Recurso no encontrado |
| 422 | Error de validación |
| 500 | Error interno |
| 503 | Servicio externo no disponible |

## Notas

- No hay rate limiting implementado en el backend actual.
- La versión visible de la API sale de `APP_VERSION`; el contrato HTTP no está
  versionado en la URL.
- Para el estado operativo actual, usar `docs/agents/current-status.md`.
