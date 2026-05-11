# API REST de FactuFlow

Ultima actualizacion: 2026-05-10

Esta documentacion resume el contrato real expuesto por `backend/app/main.py` y
`backend/app/api/*.py`.

## URLs

- Desarrollo local: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/api/docs`
- ReDoc: `http://localhost:8000/api/redoc`
- Todas las rutas funcionales usan prefijo `/api`. No hay versionado en la URL.

## Autenticacion

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

Para usuarios admin que operan un emisor activo distinto al propio, agregar:

```http
X-Empresa-Id: 2
```

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
POST /api/auth/setup
```

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

## Clientes

```http
GET /api/clientes
POST /api/clientes
GET /api/clientes/{cliente_id}
PUT /api/clientes/{cliente_id}
DELETE /api/clientes/{cliente_id}
```

Listado:

- `page`: pagina, default `1`
- `per_page`: filas por pagina
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
FactuFlow. Un punto es usable cuando esta activo, es Web Services, no esta
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
comprobantes ni consume numeracion fiscal.

## ARCA

```http
GET /api/arca/test-conexion
GET /api/arca/tipos-comprobante
GET /api/arca/tipos-documento
GET /api/arca/tipos-iva
GET /api/arca/tipos-concepto
GET /api/arca/tipos-monedas
GET /api/arca/cotizacion/{moneda_id}
GET /api/arca/puntos-venta
GET /api/arca/ultimo-comprobante/{punto_venta}/{tipo_cbte}
POST /api/arca/solicitar-cae
GET /api/arca/consultar-comprobante/{punto_venta}/{tipo_cbte}/{numero}
```

Endpoints seguros para verificar produccion sin emitir:

- `GET /api/arca/test-conexion`
- `GET /api/arca/puntos-venta`
- `GET /api/arca/ultimo-comprobante/{punto_venta}/{tipo_cbte}`

`POST /api/arca/solicitar-cae` solicita CAE real en el ambiente configurado y
solo debe ejecutarse con autorizacion explicita.

## Comprobantes

```http
GET /api/comprobantes/
GET /api/comprobantes/{comprobante_id}
POST /api/comprobantes/emitir
GET /api/comprobantes/proximo-numero/{punto_venta_id}/{tipo_comprobante}
```

`POST /api/comprobantes/emitir` emite a traves del servicio de facturacion y
puede consumir numeracion fiscal si `ARCA_ENV=produccion`.

El body debe incluir `fecha_emision`. FactuFlow no la completa con la fecha del
dia. Para comprobantes de servicios o productos y servicios tambien deben
informarse `fecha_servicio_desde`, `fecha_servicio_hasta` y `fecha_vto_pago`.
El backend valida preventivamente que `fecha_emision` este dentro de la ventana
ARCA aplicable antes de solicitar CAE.

La UI debe mostrar una confirmacion final antes de invocar este endpoint en
produccion: `Está seguro que quiere emitir comprobantes con fecha XX/XX/XX?
Recuerde que luego no podrá emitir comprobantes con fecha anterior para ese
mismo punto de venta.` El body debe enviar `confirmacion_fecha_fiscal=true`
despues de ese modal; si no llega, la API rechaza la emision.

El body tambien debe definir explicitamente el concepto fiscal ARCA. No se debe
asumir productos ni servicios por default. Los valores operativos esperados son
productos, servicios o, en flujos masivos, definido por archivo. Este dato no es
la descripcion del item: cada item debe traer su `descripcion` real, por ejemplo
`Honorarios` o `Zapatillas`, como texto facturado independiente del concepto
fiscal ARCA.

## Formatos De Importacion

```http
GET /api/formatos-importacion
POST /api/formatos-importacion
POST /api/formatos-importacion/detectar
```

Estos endpoints administran y detectan formatos configurables para emision
masiva. Todos respetan el emisor activo por JWT y, para admins, por
`X-Empresa-Id`.

`GET /api/formatos-importacion` lista formatos globales y formatos particulares
del emisor activo. Cada formato expone su `version_vigente`.

`POST /api/formatos-importacion` crea un formato particular del emisor activo.
Los formatos globales salen de migraciones/seed de sistema, no de esta ruta.

Ejemplo minimo de configuracion:

```json
{
  "nombre": "Banco X - creditos",
  "descripcion": "Extracto mensual del banco X",
  "configuracion_json": {
    "tipo": "extracto_bancario_creditos",
    "header_row": 1,
    "modo_agrupacion": "fila",
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

`POST /api/formatos-importacion/detectar` recibe `multipart/form-data` con
`archivo` (`.xlsx`) y devuelve:

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
La deteccion automatica es una sugerencia: no crea lotes ni consume numeracion.

Formato global inicial:

- Nombre: `Extracto bancario - creditos IVA exento`
- Columnas esperadas: `Fecha`, `Créditos`/`Creditos`,
  `Leyendas Adicionales1`, `Leyendas Adicionales2`, `Pto Vta`
- Requeridas: `Créditos`/`Creditos` y `Pto Vta`
- Cada fila genera un comprobante con Factura C (`tipo_comprobante=11`) e IVA
  `0`, y cliente no persistente. El formato no debe definir por defecto ni el
  concepto fiscal ARCA ni la descripcion facturada del item: el usuario debe
  elegir productos, servicios o archivo para el dato fiscal, y archivo o valor
  fijo para el texto del item antes de validar.
- Este formato global esta pensado para emisores Exento o Monotributo. Si el
  emisor activo es Responsable Inscripto, la validacion observa el lote para
  evitar emitir Factura C incorrectamente.

## Lotes De Comprobantes

```http
GET /api/lotes-comprobantes
GET /api/lotes-comprobantes/plantilla
POST /api/lotes-comprobantes/validar
POST /api/lotes-comprobantes/{lote_id}/procesar
GET /api/lotes-comprobantes/{lote_id}
GET /api/lotes-comprobantes/{lote_id}/resultados
GET /api/lotes-comprobantes/{lote_id}/archivo-observado
```

El flujo correcto es validar primero el Excel y procesar solo cuando el usuario
confirma. Lotes grandes pueden quedar en cola y continuar por worker. La UI usa
`POST /api/lotes-comprobantes/{lote_id}/procesar?background=true` tambien para
lotes chicos, para mostrar progreso real por polling.

`POST /api/lotes-comprobantes/validar` recibe `multipart/form-data`:

- `archivo`: Excel `.xlsx`.
- `formato_version_id`: opcional. Si no se envia y el archivo coincide con la
  plantilla oficial, se usa la plantilla FactuFlow. Para archivos externos,
  enviar la version confirmada por `POST /api/formatos-importacion/detectar`.
- `perfil_carga_masiva_id`: opcional. Si se envia, la validacion guarda un
  snapshot del perfil de carga masiva aplicado. La UI debe omitirlo si el
  usuario modifica la configuracion precargada antes de validar. El perfil no
  reemplaza las politicas fiscales del form; esas politicas deben llegar ya
  resueltas y visibles para el usuario.
- `punto_venta_modo`: opcional, default `archivo`. Valores: `archivo` o
  `fijo`. Si es `archivo`, se usa el punto de venta mapeado desde el Excel. Si
  es `fijo`, la validacion sobrescribe el punto de venta de todas las filas con
  `punto_venta_numero`.
- `punto_venta_numero`: requerido cuando `punto_venta_modo=fijo`. Debe existir
  para el emisor activo y estar activo, Web Services, no bloqueado y sin fecha
  de baja. Si no esta cargado en `Puntos de venta`, la API rechaza la
  validacion.
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
  columna con la descripcion/concepto facturado del item. Este texto es
  independiente de `concepto_modo`: `Productos` o `Servicios` no son una
  descripcion facturable suficiente.
- `fecha_servicio_desde_modo`, `fecha_servicio_hasta_modo` y
  `fecha_vto_pago_modo`: valores `archivo` o `fija` para comprobantes de
  servicios.
- `fecha_servicio_desde_fija`, `fecha_servicio_hasta_fija` y
  `fecha_vto_pago_fija`: obligatorias cuando el modo correspondiente es `fija`.

La validacion persiste el lote, encabezados detectados, mapeo usado y version de
formato. No emite comprobantes. La emision ocurre solo con
`POST /api/lotes-comprobantes/{lote_id}/procesar`.

`POST /api/lotes-comprobantes/{lote_id}/procesar` acepta query param opcional:

- `background=true`: deja el lote en cola para procesamiento por worker aunque
  sea un lote chico. La respuesta devuelve `en_progreso=true`, estado `en_cola`
  y el cliente debe consultar `GET /api/lotes-comprobantes/{lote_id}` para
  actualizar progreso, contadores, `started_at`, `finished_at` y
  `mensaje_resumen`.
- sin `background=true`: conserva compatibilidad con clientes existentes; lotes
  chicos se procesan en la misma request y lotes grandes se encolan segun
  `BATCH_SYNC_LIMIT`.

Durante el procesamiento, el backend actualiza `grupos_emitidos`,
`grupos_fallidos`, `grupos_validos` y `mensaje_resumen` despues de cada grupo,
para que la UI pueda mostrar avance real, tiempo transcurrido y estimacion
restante sin usar SSE/WebSocket.

Regla fiscal critica: FactuFlow no asume fecha de emision del dia actual. La
fecha de comprobante debe venir del archivo o de una fecha fija confirmada por
el usuario. La validacion observa los comprobantes cuya fecha queda fuera de la
ventana admitida por ARCA antes de permitir emitir. Si la fecha del archivo
queda fuera de ventana, el usuario debe elegir una fecha permitida y revalidar.
Antes de llamar a `procesar`, el cliente debe mostrar la confirmacion final de
fecha fiscal con el mismo texto usado en emision individual y enviar el header
`X-Confirmacion-Fecha-Fiscal: true`; si no llega, la API rechaza la emision.

Regla fiscal critica: FactuFlow tampoco asume si el lote corresponde a productos
o servicios. El usuario debe elegirlo antes de validar, o confirmar que el
archivo trae esa definicion fila por fila. Si se usa `archivo`, la columna
configurada debe existir y todas las filas deben tener `Producto` o `Servicio`;
si falta o hay valores invalidos, la API debe devolver errores de validacion
para informar al usuario y no dejar el lote listo para emitir.

Regla de item critica: el concepto fiscal ARCA no es la descripcion/concepto
facturado del item. El lote tambien debe definir la descripcion del item antes
de validar o emitir, desde archivo o como valor fijo para todo el lote. No debe
haber defaults ocultos como descripcion facturada.

## Perfiles De Carga Masiva

```http
GET /api/perfiles-carga-masiva
POST /api/perfiles-carga-masiva
PUT /api/perfiles-carga-masiva/{perfil_id}
DELETE /api/perfiles-carga-masiva/{perfil_id}
POST /api/perfiles-carga-masiva/{perfil_id}/predeterminado
```

Los perfiles de carga masiva pertenecen al emisor activo resuelto por JWT y
`X-Empresa-Id`. Permiten guardar una configuracion visible para precargar
`Emision masiva`: formato opcional, punto de venta, concepto fiscal ARCA,
descripcion facturada y reglas relativas de fechas.

El payload usa `configuracion_json` versionado. Valores principales:
- `formato_importacion_version_id`: opcional; debe ser global o pertenecer al
  emisor activo.
- `punto_venta.modo`: `archivo` para usar el punto definido en el Excel o
  `fijo` para precargar un punto concreto del emisor.
- `punto_venta.numero`: requerido cuando `punto_venta.modo=fijo`; debe estar
  cargado como punto usable por FactuFlow en `Puntos de venta`.
- `concepto_modo`: `productos`, `servicios`, `archivo` o vacio para completar
  en la carga.
- `descripcion_item_modo`: `archivo`, `fija` o vacio.
- `fecha_emision.modo`: `archivo`, `manual`, `ultimo_dia_mes_anterior` o
  `personalizada`.
- `periodo_servicio.modo`: `archivo`, `manual`, `mes_anterior_completo`,
  `mes_actual_completo` o `personalizado`.
- `fecha_vto_pago.modo`: `archivo`, `manual`, `mismo_dia_emision`,
  `emision_mas_dias` o `personalizada`.

Regla critica: el perfil de carga masiva no valida ni emite. La UI debe resolver
las reglas relativas a fechas concretas, mostrar todos los controles y dejar que
el usuario edite antes de validar. `fecha_actual` no es un modo valido de fecha
de emision para perfiles de carga masiva. Si se marca un perfil como
predeterminado, la API desmarca cualquier otro predeterminado del mismo emisor.

## PDF

```http
GET /api/pdf/comprobante/{comprobante_id}
GET /api/pdf/comprobante/{comprobante_id}/preview
```

El PDF se genera bajo demanda.

## Reportes

```http
GET /api/reportes/ventas
GET /api/reportes/iva-ventas
GET /api/reportes/clientes
```

Los reportes se calculan para el emisor activo.

## Codigos De Error

| Codigo | Descripcion |
| --- | --- |
| 200 | OK |
| 201 | Recurso creado |
| 204 | Sin contenido |
| 400 | Datos invalidos |
| 401 | No autenticado |
| 403 | Sin permisos |
| 404 | Recurso no encontrado |
| 422 | Error de validacion |
| 500 | Error interno |
| 503 | Servicio externo no disponible |

## Notas

- No hay rate limiting implementado en el backend actual.
- La version visible de la API sale de `APP_VERSION`; el contrato HTTP no esta
  versionado en la URL.
- Para el estado operativo actual, usar `docs/agents/current-status.md`.
