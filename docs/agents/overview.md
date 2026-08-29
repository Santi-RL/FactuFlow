# Arquitectura estable de FactuFlow

Última revisión: 29/08/2026

Estado: VIGENTE.

Este documento resume la arquitectura y las fronteras estables. No define
prioridades, estado de releases ni estado productivo.

El estado desplegado autoritativo vive en el plano de control `VPS Hostinger` /
`vps-admin`.

## Producto

FactuFlow es una aplicación de facturación electrónica ARCA para personal
administrativo y contable no técnico. Su núcleo es la emisión individual y
masiva, con evidencia, recuperación y mensajes comprensibles.

## Componentes

- **Frontend:** Vue 3, Pinia, Vue Router, TypeScript y Vite.
- **Backend:** FastAPI, SQLAlchemy y Pydantic.
- **Persistencia:** PostgreSQL en producción; SQLite en desarrollo y pruebas.
- **Esquema:** Alembic es el camino canónico fuera de tests controlados.
- **ARCA:** WSAA para autenticación y WSFEv1 para parámetros, consultas y CAE.
- **Procesamiento:** API y worker embebido para lotes; la topología concreta se
  consulta en el plano de control.
- **Entrega:** Docker Compose detrás de un proxy HTTPS en instalaciones VPS.

## Fronteras del dominio

- Un emisor activo explícito gobierna cada operación.
- Clientes, certificados, puntos de venta, comprobantes, lotes, reportes,
  perfiles y formatos se aíslan por emisor.
- La fecha fiscal nunca se completa automáticamente con la fecha actual.
- Toda ruta capaz de solicitar CAE exige confirmación irreversible.
- Las operaciones fiscales tienen idempotencia durable y conservan estados
  inciertos hasta reconciliarlos.
- ARCA gobierna numeración y señales fiscales externas; FactuFlow gobierna sus
  propios intentos, operaciones y evidencia local.
- PDFs, ZIPs y artefactos descargables no vitales se generan bajo demanda y no
  deben persistir indefinidamente.

## Capas documentales

- `VISION.md`: propósito y límites.
- `ROADMAP.md`: prioridades futuras.
- `current-status.md`: handoff del repositorio.
- `development-portfolio.md`: trabajo activo y dependencias.
- Diseños PF: contratos de una unidad concreta.
- Runbooks: procedimientos reutilizables.
- `CHANGELOG.md`, dossiers y `docs/project/history/`: historia y evidencia.

La estructura de código se consulta en [`structure.md`](structure.md). Las
reglas documentales se consultan en
[`documentation-governance.md`](documentation-governance.md).
