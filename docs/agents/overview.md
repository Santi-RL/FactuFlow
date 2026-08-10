# Resumen del proyecto

Última actualización: 09/08/2026

## Qué es FactuFlow

FactuFlow es un sistema de facturación electrónica ARCA para Argentina orientado
a personal administrativo no técnico. El foco es emitir, revisar y sostener
facturación individual y masiva con seguridad fiscal.

## Estado actual

- Versión productiva vigente: `v0.2.2`, también última release publicada y
  validada en producción el 23/07/2026.
- Versión técnica del candidato local: `v0.3.0`, sin tag, publicación ni
  despliegue.
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
- `main` incluye PF-02A, los tres cortes de PF-02B, PF-03A, PF-19A, PF-19B y
  PF-19C completo localmente.
  PF-02 admite historia externa legítima sin perder reservas ni segundo
  preflight; PF-03A rechaza claves superiores desconocidas; PF-19A agrega la
  contención preautorización explícita y el inventario legacy de solo lectura;
  PF-19B cierra elegibilidad RECE durable, atestación administrativa productiva,
  control integral y UI. PF-19C acepta solo el `10005` entero exacto con
  cabecera global estricta como terminal; lo incierto se reconcilia y el legacy
  usa plan/apply auditado. Faltan PostgreSQL real, CI, `autoreview` y ensayo de
  migración/restauración. Todo ese tramo es posterior a `v0.2.2`: todavía no
  pertenece a una release publicada ni está desplegado.
- PF-19C completó evidencia local enfocada; preserva el error global `10005`
  como rechazo terminal solo bajo contrato oficial, detiene grupos no enviados
  y sanea historia legacy de forma auditada. PostgreSQL real, CI, `autoreview`
  y ensayo de migración/restauración continúan pendientes antes de release.
  Web Services genérico ya no acredita RECE en `main`; homologación permanece
  fail-closed mientras no exista una fuente probatoria específica.

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
- Elegibilidad RECE: ledger append-only y cabeza transaccional por punto y
  ambiente, revisión fiscal monotónica, snapshots y guardas durables antes de
  ARCA. La sincronización WSFE server-side solo actualiza estado técnico; una
  acreditación positiva exige administrador, constancia productiva fresca,
  señal exacta y confirmación expresa.
- Observabilidad: `Sistema > Estado` consulta un health administrativo
  sanitizado de worker/pools, además de señales operativas simples, soporte,
  backups y trazabilidad
  antes que monitoreo externo complejo.

## Próximo hito

En el estado objetivo de `main`, PF-02, PF-03A, PF-19A y PF-19B están cerrados;
PF-19C completó la evidencia local y PF-05 conserva separada la reconstrucción
histórica opcional para informes. La siguiente unidad es cerrar las puertas
externas de PF-19C —PostgreSQL real, CI, `autoreview` y ensayo de
migración/restauración—; recién entonces sigue PF-03B sobre DTO de ítem, propiedades desconocidas,
descuentos y valores no finitos. PF-19 no cambia numeración ni absorbe
validaciones de ítems; PF-14/PF-15 consumen su contrato de error y trazabilidad.

## Principios de trabajo

- Respetar `VISION.md`.
- Diseñar primero los cambios fiscales críticos.
- Mantener fixes sensibles pequeños y aislados.
- Probar el riesgo específico antes de ejecutar suites completas.
- No tratar findings automáticos como órdenes.
- Mantener documentación pública sanitizada y evidencia real en privado.
