# Resumen del proyecto

Última actualización: 08/08/2026

## Qué es FactuFlow

FactuFlow es un sistema de facturación electrónica ARCA para Argentina orientado
a personal administrativo no técnico. El foco es emitir, revisar y sostener
facturación individual y masiva con seguridad fiscal.

## Estado actual

- Versión productiva vigente: `v0.2.2`, también última release publicada y
  validada en producción el 23/07/2026.
- Backend FastAPI y frontend Vue operativos.
- PostgreSQL es la base productiva; Alembic es el camino canónico de schema.
- Emisión individual y masiva con WSAA/WSFE ya utilizada en producción.
- PDFs bajo demanda, reportes, clientes, certificados, puntos de venta,
  plantillas y perfiles de carga masiva.
- Varios emisores con uno activo explícito por vez.
- Administradores con acceso operativo a todos los emisores; usuarios comunes
  limitados al emisor asignado.
- VPS con Docker producción y HTTPS operativo.
- La evidencia productiva concreta permanece fuera del repositorio público.
- El estado objetivo de `main` al integrar este corte incluye PF-02A, los tres
  cortes de PF-02B, PF-03A y PF-19A. PF-02 admite historia externa legítima sin
  perder reservas ni segundo preflight; PF-03A rechaza claves superiores
  desconocidas; PF-19A agrega diseño, contención preautorización explícita e
  inventario legacy de solo lectura. Todo ese tramo es posterior a `v0.2.2`:
  todavía no pertenece a una release publicada ni está desplegado.
- PF-19B/PF-19C siguen pendientes. La clasificación actual Web Services no
  demuestra por sí sola que un punto sea RECE; una tupla omitida en la
  configuración PF-19A queda sin protección. Todavía no debe considerarse
  completa la elegibilidad fiscal de puntos ni resolverse registros históricos.

El estado detallado y el punto de reanudación viven en
`docs/agents/current-status.md`.

## Alcance confirmado

- FactuFlow es una herramienta para facturar.
- No se planifican cuentas corrientes, stock, catálogos complejos ni CRM como
  módulos centrales.
- Las integraciones externas quedan para después de estabilizar la operación.
- El modelo no busca una plataforma multiempresa con operación simultánea,
  permisos finos por organización ni reportes globales.
- La aplicación debe seguir siendo viable en una PC o VPS pequeño.
- PDFs, ZIPs y otros artefactos no vitales se generan bajo demanda y no deben
  persistir indefinidamente en el servidor.

## Arquitectura

- Frontend: Vue 3, Pinia, Vue Router y Vite.
- Backend: FastAPI, SQLAlchemy y Pydantic.
- Base: PostgreSQL productivo; SQLite para desarrollo local, tests y evidencia
  legacy, sin ser el schema canónico de producción. SQLite comparte un único
  engine entre API y worker por diseño y eso no representa degradación.
- Conexiones PostgreSQL: pool API predeterminado y máximo `4`, overflow `0`,
  reducible dentro de `1..4`; pool dedicado del worker `1`, timeout `5 s` y
  warning sanitizado de retención desde `10 s`.
- Sesiones API lazy: la conexión se adquiere con el primer SQL necesario,
  incluida la autenticación. Los timeouts y desconexiones devuelven `503`
  sanitizado.
- Servicios externos: WSAA y WSFEv1 de ARCA.
- Despliegue: Docker Compose productivo detrás de reverse proxy HTTPS.
- Procesamiento: worker de lotes embebido; mientras siga así, producción usa un
  único proceso Uvicorn. El seguimiento UI usa una allowlist liviana, una sola
  solicitud en vuelo, intervalos `3/5/10 s` y backoff máximo de `15 s`.
- Observabilidad: `Sistema > Estado` consulta un health administrativo
  sanitizado de worker/pools, además de señales operativas simples, soporte,
  backups y trazabilidad
  antes que monitoreo externo complejo.

## Próximo hito

En el estado objetivo de `main`, PF-02, PF-03A y PF-19A quedan cerrados en
unidades pequeñas; PF-05 conserva separada la reconstrucción histórica opcional
para informes. La siguiente unidad es
PF-19B: persistir elegibilidad RECE y aplicarla de extremo a extremo. Después
sigue PF-19C para errores globales estructurados y cierre legacy auditado, y
recién entonces PF-03B sobre DTO de ítem, propiedades desconocidas, descuentos
y valores no finitos. PF-19 no cambia numeración ni absorbe validaciones de
ítems; PF-14/PF-15 consumen su contrato de error y trazabilidad.

## Principios de trabajo

- Respetar `VISION.md`.
- Diseñar primero los cambios fiscales críticos.
- Mantener fixes sensibles pequeños y aislados.
- Probar el riesgo específico antes de ejecutar suites completas.
- No tratar findings automáticos como órdenes.
- Mantener documentación pública sanitizada y evidencia real en privado.
