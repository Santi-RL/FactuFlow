# Resumen del proyecto

## Que es FactuFlow

FactuFlow es un sistema de facturacion electronica ARCA para Argentina. El foco actual del producto es permitir emision real, especialmente masiva, para personal administrativo no tecnico.

## Objetivos confirmados

- Emision individual y masiva con ARCA en homologacion.
- UX simple, guiada y entendible para usuarios administrativos.
- Operacion principal por una empresa a la vez.
- PDF bajo demanda.
- Reportes basicos de consulta.

## Estado real al 2026-05-07

- Backend y frontend operativos.
- Lotes masivos por Excel implementados con validacion previa, idempotencia por archivo y worker reanudable para lotes grandes.
- Selector de empresa activa implementado para admins.
- Smoke real en homologacion completado con CAEs reales.
- QA manual de interfaz cerrada para homologacion.
- Produccion base verificada para el emisor real: certificado productivo,
  autorizacion `wsfe` y puntos Web Services disponibles. La fuente canonica del
  detalle operativo es `docs/agents/current-status.md`.
- Falta ejecutar la primera prueba real controlada, previa confirmacion final
  del punto de venta, backup/logs y lote chico definitivo.

## Arquitectura

- Frontend: Vue 3 + Pinia + Vue Router + Vite.
- Backend: FastAPI + SQLAlchemy + Pydantic.
- DB: PostgreSQL recomendado para operacion real; SQLite solo para desarrollo puntual/legacy.
- Servicios externos: WSAA y WSFEv1 de ARCA.

## Principios de trabajo

- Simplicidad primero.
- Usuario no tecnico en mente.
- Seguridad y aislamiento por empresa.
- Documentacion viva: si cambia algo importante, se actualizan `ROADMAP.md`, `docs/agents/current-status.md`, `docs/agents/manual-qa.md` y `docs/user-guide/README.md`.
