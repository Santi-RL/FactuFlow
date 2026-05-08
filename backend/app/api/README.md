# API (FastAPI)

Esta carpeta contiene los endpoints (routers) de la API REST de FactuFlow.

## Archivos

- `deps.py`: dependencias compartidas (DB session, usuario actual, etc.).
- `health.py`: health checks.
- `auth.py`: setup/login/me.
- `empresas.py`: CRUD de empresas.
- `clientes.py`: CRUD de clientes.
- `puntos_venta.py`: CRUD de puntos de venta.
- `certificados.py`: gestion de certificados (CSR, upload, verificacion, alertas).
- `arca.py`: integracion ARCA (WSAA/WSFEv1 via `app/arca/`).
- `comprobantes.py`: emision y consulta de comprobantes.
- `lotes_comprobantes.py`: plantilla, validacion, procesamiento y resultados de lotes Excel.
- `formatos_importacion.py`: listado, creacion y autodeteccion de formatos configurables de Excel.
- `pdf.py`: generacion/descarga de PDFs.
- `reportes.py`: reportes (ventas, IVA, ranking, etc.).

## Registro de routers

Los routers se registran en `backend/app/main.py` con `app.include_router(...)`.

Routers relacionados con emision masiva:

- `/api/formatos-importacion`: formatos globales y por emisor, mas deteccion de
  candidatos por encabezados.
- `/api/lotes-comprobantes`: validacion de Excel, procesamiento con confirmacion
  y descarga de archivo observado. `POST /validar` puede recibir
  `formato_version_id` para aplicar el mapeo confirmado.

## Convenciones

- Imports absolutos desde `app/`.
- Docstrings en espanol.
- Usar schemas Pydantic para request/response.
- Validar permisos con dependencies.
- Manejar errores con `HTTPException`.
