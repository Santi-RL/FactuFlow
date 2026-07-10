# Changelog

Este archivo es la fuente principal para entender de dónde viene FactuFlow y
hacia dónde avanza.

Reglas vigentes desde 2026-05-22:

- El estado operativo actual se consulta en `README.md`,
  `docs/agents/current-status.md` y `ROADMAP.md`.
- El historial versionado se resume acá. Evitar crear nuevos snapshots largos
  de documentación si el cambio puede quedar explicado en este changelog, el
  roadmap y la documentación viva.
- Los documentos antiguos bajo `docs/project/**` son material histórico. No
  deben usarse como fuente de verdad actual si contradicen la documentación
  viva.
- No registrar CUITs, CAEs, nombres reales, Excels, PDFs, logs ni evidencia
  privada en este archivo.

## [Unreleased]

Sin cambios todavía.

## [0.2.1] - 2026-07-10

Primera release formal de GitHub. Consolida el endurecimiento fiscal,
multiemisor y operativo posterior al piloto productivo. El contenido técnico de
la actualización depende del commit de origen: el despliegue realizado desde una
instalación anterior incluyó la migración `f7a8b9c0d1e2`, cambios de dependencias
y ajustes del compose productivo.

### Seguridad y confiabilidad fiscal

- La emisión individual bloquea confirmaciones sin numeración ARCA disponible,
  descarta fechas de servicio que no aplican y evita conservar un `cliente_id`
  después de editar manualmente el receptor.
- WSFE rechaza respuestas parciales o ambiguas y consulta el número de
  comprobante sin evaluar fallbacks ausentes.
- Los errores inesperados de emisión ya no exponen detalles internos; los
  fallos post-CAE preservan el estado de reconciliación.
- El transporte SOAP aplica timeout por operación, ejecuta Zeep fuera del event
  loop y conserva compatibilidad con el rango AnyIO admitido por Starlette.
- La API no encola lotes si el worker embebido no está disponible; producción
  mantiene un único proceso Uvicorn mientras ese worker siga embebido.

### Aislamiento multiemisor

- Certificados y puntos de venta cancelan acciones o respuestas obsoletas al
  cambiar el emisor activo.
- El store de puntos de venta no permite que una respuesta tardía reemplace la
  lista del nuevo emisor, incluso con identificadores coincidentes.
- La edición de emisores queda reservada a administradores y la interfaz de
  usuarios comunes permanece en modo lectura.

### Validación del corte

- Backend: 411 tests aprobados y 1 omitido según su marca preexistente.
- Frontend: 111 tests aprobados; ESLint, type-check y build limpios.
- `autoreview` acumulado con GPT-5.5 en `high` sin hallazgos accionables.
- Clawpatch revalidó como `fixed` los 3 findings backend y 9 frontend objetivo.
- GitHub Actions aprobó el commit de release `8099b22` con los jobs de seguridad,
  frontend, backend y E2E completos.

### Despliegue productivo

- Producción se actualizó al tag `v0.2.1`, commit
  `8099b223f3be7342dbb29367d24c6209dee93a58`.
- El backup previo quedó validado mediante una restauración aislada antes de
  reabrir el servicio.
- Alembic aplicó y verificó la migración `f7a8b9c0d1e2`: la relación de usuarios
  usa `SET NULL` y las entidades con historial fiscal u operativo usan
  `RESTRICT` ante el borrado de un emisor.
- La comprobación posterior confirmó `current` y `heads` alineados, conteos
  coincidentes en 40 tablas públicas, base y logs sanos, un único proceso
  Uvicorn, worker de lotes activo y ausencia de operaciones fiscales en curso.
- Los smoke checks públicos e internos, login, PDF sintético y servicios vecinos
  quedaron sanos.
- La validación manual autenticada se completó con emisión fiscal real
  satisfactoria. La evidencia y los datos fiscales permanecen en el entorno
  operativo privado.
- Con estas verificaciones, `v0.2.1` queda aceptada como despliegue productivo
  satisfactorio.

### Auditoría y mantenimiento

- Se realizó una auditoría documental de los Markdown versionados: README, manual de usuario, referencia API, guías de certificados, notas ARCA y documentos históricos quedaron alineados con las reglas vigentes sin modificar `VISION.md`.
- Se cerró la auditoría Clawpatch de backend, frontend y repo completo del
  2026-07-05 con `openFindings=0` en los tres state dirs existentes.
- Se corrigió la puesta a punto del mapper repo para usar la CLI global
  `clawpatch` sin fijar versión y conservar el mapeo nativo junto con las
  features manuales versionadas.
- Se corrigió la previsualización de PDFs para no revocar el `blob:` antes de
  que la pestaña nueva cargue el visor; se evita usar `pagehide`/`unload` en la
  navegación inicial de `about:blank` al `blob:`.
- Se aclaró el workflow CI: los E2E corren en pushes a `main` y en PRs.
- Se reforzó `formatearFecha` para soportar y validar `DD/MM/AAAA`, además de
  formatos técnicos `YYYY-MM-DD` e ISO datetime, sin normalizar fechas inválidas
  como `31/02/2026`.
- Se documentaron reglas permanentes de fechas argentinas en `AGENTS.md`,
  `docs/agents/testing.md` y `CONTRIBUTING.md`.
- Cierre detallado y lecciones operativas:
  `docs/project/audits/clawpatch/2026-07-05-cierre-auditoria.md`.
- Validaciones: tests frontend enfocados y completos, Clawpatch revalidate,
  `autoreview` Codex/GPT-5.5 alto por commit y GitHub Actions remoto aprobado.
### UX de carga masiva

- Se implementó el Corte 1 del rediseño de `/comprobantes/lotes`: guía rápida
  compacta con detalle desplegable, checklist dinámico de requisitos y acción
  `Validar lote` al cierre de la configuración fiscal.
- Se implementó el Corte 2 del rediseño de `/comprobantes/lotes`: el lote
  activo prioriza totales, avance y siguiente acción; el resumen operativo y el
  detalle de comprobantes pasan a secciones plegables. Las acciones sobre
  comprobantes visibles quedan habilitadas solo con el detalle abierto.
- Se implementó el Corte 3 del rediseño de `/comprobantes/lotes`: `Resolver
  pendientes` pasa a ser un modo desplegable que agrupa reintento de fallidos,
  descarte de visibles y reconciliación ARCA Web para casos excepcionales.
- Se implementó el Corte 4 del rediseño de `/comprobantes/lotes`: `Lotes
  recientes` queda como navegación compacta con estado, fecha, métrica principal
  y lote activo resaltado.
- Los cambios son frontend-only y mantienen intactos backend, ARCA, emisión,
  servicios, stores, rutas, payloads y contratos.
- Validaciones: `git diff --check`, test unitario enfocado de
  `LotesComprobantesView`, `npm run lint:check`, `npm run type-check`,
  `npm run build`, `npm run test:unit`, E2E Chromium y smoke visual con API
  mockeada sin llamadas ARCA.

### Observabilidad operativa

- Se agregó QA local del gestor de almacenamiento: E2E permanente con API
  mockeada y datos ficticios, más smoke visual privado para métricas,
  categorías, emisores, resguardo ZIP y confirmación `Ya lo descargué`, sin
  datos reales ni llamadas ARCA. La validación VPS con datos de prueba
  controlados sigue pendiente.
- Se agregó una guía rápida de soporte en `Sistema > Estado` con próximos pasos
  seguros para aplicación/base no disponible, ARCA/certificado con error, lotes
  detenidos o inciertos y almacenamiento/backup pendiente.
- Se agregó `Ficha para soporte` en `Sistema > Estado` con datos mínimos para
  diagnosticar incidentes sin copiar CUIT completo ni evidencia privada en
  documentación pública.
- Se agregó `docs/agents/support-runbook.md` como primer runbook público y
  sanitizado de diagnóstico operativo, sin datos privados ni comandos concretos
  de VPS.
- Se agregó el primer corte de `Sistema > Estado` para administradores, con
  señales de API, base de datos, certificado local del emisor activo,
  almacenamiento y prueba ARCA manual.
- La pantalla no llama a ARCA automáticamente al cargar; la conexión externa
  queda detrás de la acción explícita `Probar conexión`.
- Quedan pendientes healthcheck dedicado de worker, evidencia automática de
  backup y trazabilidad histórica más completa.

### Checkpoint visual v01

- Se cerró el checkpoint visual v01 del frontend público para instalación
  productiva controlada, con identidad aplicada en shell común, componentes
  base/comunes, login/setup, dashboard, clientes, usuarios, reportes y
  certificados/listado/wizard.
- Se agregaron tokens suaves de estado y se eliminó deuda visual residual del
  alcance, sin modificar backend, ARCA, emisión individual o masiva, lotes
  fiscales, servicios, stores, rutas ni contratos.
- Validaciones de cierre: `git diff --check`, `npm run lint:check`,
  `npm run type-check`, `npm run build`, `npm run test:unit` (63 tests) y
  `npm run test:e2e -- --reporter=list` (31 tests en Chromium desktop).
- Este hito no implica despliegue automático ni distribución comercial; la
  instalación productiva debe hacerse de forma explícita contra un commit o tag
  identificable.

## [0.2.0-mvp] - 2026-05-22

Línea base actual del proyecto. Este corte reemplaza las referencias antiguas a
versiones previas como fuente de estado operativo.

### Estado del corte

- Versión visible del producto: `0.2.0-mvp`.
- Versión técnica npm/backend: `0.2.0` cuando la herramienta exige semver.
- MVP validado en homologación y usado en producción real controlada.
- La evidencia productiva detallada queda en bases, logs y archivos privados
  ignorados por Git.
- La documentación viva queda alineada con estado post-piloto productivo.

### Decisiones de producto vigentes

- FactuFlow es una herramienta para facturar.
- No se planifica incorporar cuentas corrientes, stock ni catálogos.
- Las integraciones externas quedan como evolucion futura, enfocadas en entrada
  y salida de datos mediante la API, después de estabilizar facturación.
- El modelo operativo es multiemisor con un emisor activo explícito por vez,
  pensado para contadores independientes y estudios chicos.
- No se avanza por ahora hacia plataforma multiempresa compleja con permisos
  finos, reportes globales u operación simultanea entre emisores.
- El uso local con launcher queda como entorno implementado para desarrollo/QA.
- El siguiente hito de despliegue es VPS con Docker producción y PostgreSQL.
- La distribución comercial instalable queda para después de estabilizar VPS.
- La observabilidad operativa estándar es requisito antes de ampliar producción:
  trazabilidad, estado del sistema, logs útiles, backups y mensajes simples para
  usuarios no técnicos.

### Capacidades consolidadas

- Backend FastAPI con auth, empresas, clientes, certificados, puntos de venta,
  comprobantes, lotes, PDFs y reportes.
- Frontend Vue con dashboard, clientes, comprobantes, emisión masiva, reportes,
  certificados, puntos de venta y emisores.
- Emisión individual y masiva con ARCA WSAA/WSFEv1.
- Confirmación fiscal explícita antes de solicitar CAE.
- Fecha de emisión explícita; no se usa la fecha del día como default fiscal.
- Formatos configurables de importación y perfiles de carga por emisor.
- Lotes con validación previa, estados persistidos y worker para procesos
  largos.
- Selector de emisor activo y scoping por emisor en operaciones sensibles.
- PDFs bajo demanda y reportes básicos.
- Launcher local Windows con icono en tray para desarrollo/QA.

### Seguridad y operación

- Clientes, certificados, puntos de venta, comprobantes, lotes, PDFs, reportes,
  perfiles y formatos deben quedar aislados por emisor activo.
- Para producción usar PostgreSQL y `docker-compose.prod.yml`.
- Queda pendiente resolver si los certificados productivos locales se migran al
  VPS o si conviene generar certificados nuevos para el servidor.
- Backups/restauración, trazabilidad visible, logs de soporte y pantalla de
  estado del sistema son prioridad post-piloto.

### Próximo tramo

- Instalar y validar FactuFlow en VPS con Docker producción y PostgreSQL.
- Resolver la política técnica de certificados ARCA en VPS.
- Implementar observabilidad operativa estándar.
- Formalizar backup/restauración de base, certificados, configuración y logs.
- Agregar descarga masiva de PDFs en ZIP.
- Recuperar E2E como evidencia confiable.
- Definir política de releases posterior a `0.2.0-mvp`.

## Historial resumido anterior al corte

### Base inicial

- Se construyo la base técnica con FastAPI, Vue, Pinia, Router, SQLAlchemy,
  Pydantic, autenticacion, setup inicial y estructura modular.
- Se incorporaron empresas, clientes, puntos de venta, certificados,
  comprobantes, PDFs y reportes.
- Se documento la primera visión de FactuFlow como sistema de facturación
  electrónica ARCA para Argentina.

### Integración ARCA y comprobantes

- Se implemento WSAA y WSFEv1.
- Se agregaron certificados por ambiente, wizard de carga/verificacion y
  validaciones de autorización `wsfe`.
- Se completo emisión individual, vista previa, guardado de comprobantes,
  consulta posterior y generacion de PDFs.
- Se corrigieron reglas fiscales críticas: fecha fiscal explícita, concepto
  fiscal ARCA explícito, punto de venta usable y confirmación irreversible.

### Emisión masiva

- Se implemento emisión por Excel con agrupacion por `comprobante_ref`.
- Se agregaron validaciones de totales, IVA, consumidor final, puntos de venta
  y conceptos fiscales.
- Se agregaron formatos de importación configurables y perfiles por emisor para
  facilitar archivos externos.
- Se incorporaron estados de lotes, worker para procesos largos, idempotencia y
  manejo de casos con incertidumbre post-ARCA.

### Producción real y endurecimiento

- Se verificó homologación y luego se operó producción real controlada.
- Se ajusto numeración, locking, idempotencia, reconciliacion y scoping por
  emisor.
- Se agregó launcher local Windows para desarrollo/QA y mejores mensajes cuando
  el backend local no está disponible.
- Se reforzo la seguridad documental: no versionar datos privados, CAEs,
  CUITs, clientes, Excels, PDFs, logs ni evidencia local.

### Documentación

- Se separó documentación viva de documentos históricos.
- `README.md`, `ROADMAP.md`, `docs/agents/current-status.md`,
  `docs/agents/manual-qa.md`, `docs/user-guide/README.md` y este changelog
  pasan a ser la base para retomar el proyecto.
- Los snapshots antiguos conservados en `docs/project/**` quedan solo como
  referencia histórica y pueden resumirse o eliminarse en futuras limpiezas si
  su contenido ya está cubierto por este changelog y la documentación viva.
