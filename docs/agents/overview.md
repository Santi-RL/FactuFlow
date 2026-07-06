# Resumen del proyecto

## Que es FactuFlow

FactuFlow es un sistema de facturación electrónica ARCA para Argentina. El foco actual del producto es permitir emisión real, especialmente masiva, para personal administrativo no técnico.

## Objetivos confirmados

- Emisión individual y masiva con ARCA, validada primero en homologación y ya
  utilizada en producción real controlada.
- UX simple, guiada y entendible para usuarios administrativos.
- Operación multiemisor para contadores independientes y estudios chicos, con
  un emisor activo explícito por vez.
- PDF bajo demanda.
- Reportes básicos de consulta.

## Alcance confirmado

- FactuFlow es una herramienta para facturar.
- No esta planificado incorporar manejo de cuentas corrientes, stock ni
  catálogos como módulos del producto.
- Las integraciones externas quedan como evolucion futura, después de madurar
  la facturación productiva estable, y deben enfocarse en obtener datos desde
  otras aplicaciones o enviar datos hacia ellas mediante la API.
- El modelo multiemisor no busca, por ahora, una administración central
  compleja. El foco es que un usuario pueda manejar varios emisores sin mezclar
  clientes, certificados, puntos de venta, comprobantes, lotes, PDFs, reportes,
  perfiles ni formatos entre CUITs.

## Estado real al 2026-05-22

- Backend y frontend operativos.
- Lotes masivos por Excel implementados con validación previa, idempotencia por archivo y worker reanudable para lotes grandes.
- Selector de emisor activo implementado para operar varios emisores con uno
  activo por vez.
- Smoke real en homologación completado con CAEs reales.
- QA manual de interfaz cerrada para homologación.
- Producción base verificada para el emisor real: certificado productivo,
  autorización `wsfe` y puntos Web Services disponibles. La fuente canónica del
  detalle operativo es `docs/agents/current-status.md`.
- Producción real ya fue utilizada con comprobantes autorizados y lotes
  productivos. La evidencia detallada queda en base/logs privados ignorados por
  Git y no debe copiarse a documentación versionada.
- El foco actual es consolidar operación post-piloto: documentación alineada,
  instalación en VPS, backups/restauración, observabilidad, trazabilidad de
  lotes y mejoras de UX administrativa.

## Arquitectura

- Frontend: Vue 3 + Pinia + Vue Router + Vite.
- Backend: FastAPI + SQLAlchemy + Pydantic.
- DB: PostgreSQL recomendado para operación real; SQLite solo para desarrollo puntual/legacy.
- Servicios externos: WSAA y WSFEv1 de ARCA.
- Despliegue: local con launcher ya implementado para desarrollo/QA; próximo
  hito, VPS con Docker producción y PostgreSQL. La distribución comercial
  instalable queda para después de estabilizar la operación en VPS.
- Observabilidad: se adopta una observabilidad operativa estándar, enfocada en
  explicar con lenguaje simple que paso, que impacto tiene y cual es el próximo
  paso seguro. No se priorizan todavía herramientas avanzadas de monitoreo.

## Principios de trabajo

- Simplicidad primero.
- Usuario no técnico en mente.
- Seguridad y aislamiento por empresa.
- Documentación viva: si cambia algo importante, se actualizan `ROADMAP.md`, `docs/agents/current-status.md`, `docs/agents/manual-qa.md` y `docs/user-guide/README.md`.
