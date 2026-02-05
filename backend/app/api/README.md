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
- `pdf.py`: generacion/descarga de PDFs.
- `reportes.py`: reportes (ventas, IVA, ranking, etc.).

## Registro de routers

Los routers se registran en `backend/app/main.py` con `app.include_router(...)`.

## Convenciones

- Imports absolutos desde `app/`.
- Docstrings en espanol.
- Usar schemas Pydantic para request/response.
- Validar permisos con dependencies.
- Manejar errores con `HTTPException`.
