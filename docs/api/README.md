# API REST de FactuFlow

Ultima actualizacion: 2026-05-08

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
  "email": "visual@factuflow.dev",
  "password": "admin123"
}
```

Respuesta:

```json
{
  "access_token": "...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "visual@factuflow.dev",
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
- Cada fila genera un comprobante con Factura C (`tipo_comprobante=11`), IVA
  `0`, item `Cobro registrado en cuenta bancaria` y cliente no persistente.
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
confirma. Lotes grandes pueden quedar en cola y continuar por worker.

`POST /api/lotes-comprobantes/validar` recibe `multipart/form-data`:

- `archivo`: Excel `.xlsx`.
- `formato_version_id`: opcional. Si no se envia y el archivo coincide con la
  plantilla oficial, se usa la plantilla FactuFlow. Para archivos externos,
  enviar la version confirmada por `POST /api/formatos-importacion/detectar`.

La validacion persiste el lote, encabezados detectados, mapeo usado y version de
formato. No emite comprobantes. La emision ocurre solo con
`POST /api/lotes-comprobantes/{lote_id}/procesar`.

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
