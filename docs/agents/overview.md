# Resumen del proyecto

## Que es FactuFlow

FactuFlow es un sistema de facturacion electronica ARCA para Argentina. El foco actual del producto es permitir emision real, especialmente masiva, para personal administrativo no tecnico.

## Objetivos confirmados

- Emision individual y masiva con ARCA, validada primero en homologacion y ya
  utilizada en produccion real controlada.
- UX simple, guiada y entendible para usuarios administrativos.
- Operacion multiemisor para contadores independientes y estudios chicos, con
  un emisor activo explicito por vez.
- PDF bajo demanda.
- Reportes basicos de consulta.

## Alcance confirmado

- FactuFlow es una herramienta para facturar.
- No esta planificado incorporar manejo de cuentas corrientes, stock ni
  catalogos como modulos del producto.
- Las integraciones externas quedan como evolucion futura, despues de madurar
  la facturacion productiva estable, y deben enfocarse en obtener datos desde
  otras aplicaciones o enviar datos hacia ellas mediante la API.
- El modelo multiemisor no busca, por ahora, una administracion central
  compleja. El foco es que un usuario pueda manejar varios emisores sin mezclar
  clientes, certificados, puntos de venta, comprobantes, lotes, PDFs, reportes,
  perfiles ni formatos entre CUITs.

## Estado real al 2026-05-22

- Backend y frontend operativos.
- Lotes masivos por Excel implementados con validacion previa, idempotencia por archivo y worker reanudable para lotes grandes.
- Selector de emisor activo implementado para operar varios emisores con uno
  activo por vez.
- Smoke real en homologacion completado con CAEs reales.
- QA manual de interfaz cerrada para homologacion.
- Produccion base verificada para el emisor real: certificado productivo,
  autorizacion `wsfe` y puntos Web Services disponibles. La fuente canonica del
  detalle operativo es `docs/agents/current-status.md`.
- Produccion real ya fue utilizada con comprobantes autorizados y lotes
  productivos. La evidencia detallada queda en base/logs privados ignorados por
  Git y no debe copiarse a documentacion versionada.
- El foco actual es consolidar operacion post-piloto: documentacion alineada,
  instalacion en VPS, backups/restauracion, observabilidad, trazabilidad de
  lotes y mejoras de UX administrativa.

## Arquitectura

- Frontend: Vue 3 + Pinia + Vue Router + Vite.
- Backend: FastAPI + SQLAlchemy + Pydantic.
- DB: PostgreSQL recomendado para operacion real; SQLite solo para desarrollo puntual/legacy.
- Servicios externos: WSAA y WSFEv1 de ARCA.
- Despliegue: local con launcher ya implementado para desarrollo/QA; proximo
  hito, VPS con Docker produccion y PostgreSQL. La distribucion comercial
  instalable queda para despues de estabilizar la operacion en VPS.
- Observabilidad: se adopta una observabilidad operativa estandar, enfocada en
  explicar con lenguaje simple que paso, que impacto tiene y cual es el proximo
  paso seguro. No se priorizan todavia herramientas avanzadas de monitoreo.

## Principios de trabajo

- Simplicidad primero.
- Usuario no tecnico en mente.
- Seguridad y aislamiento por empresa.
- Documentacion viva: si cambia algo importante, se actualizan `ROADMAP.md`, `docs/agents/current-status.md`, `docs/agents/manual-qa.md` y `docs/user-guide/README.md`.
