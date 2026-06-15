# Estado actual

Última actualización: 2026-06-15

## Objetivo activo

Consolidar FactuFlow después del piloto productivo real: documentación
alineada, reglas fiscales críticas preservadas, operación masiva controlada,
backups/restauración y robustez de soporte antes de ampliar el uso.

## Estado real del producto

- Backend FastAPI operativo con auth, usuarios, empresas, clientes, puntos de
  venta, certificados, comprobantes, PDF, lotes y reportes.
- Backend ya registra formatos configurables de importación para lotes masivos,
  con formatos globales y particulares por emisor. La capa pública ahora los
  presenta como `Plantillas`: se pueden crear, editar con nueva versión,
  clonar, desactivar, descargar como `.xlsx`, analizar desde un Excel de
  ejemplo y evaluar contra perfil/emisor. Las plantillas globales quedan
  reservadas a administradores; los usuarios activos administran plantillas del
  emisor activo.
- Backend ya registra perfiles de carga masiva por emisor para precargar
  formato, punto de venta, concepto fiscal ARCA, descripcion facturada y reglas
  de fechas.
- Tooling Python actualizado el 2026-06-03: `.gitattributes` fija LF para
  `*.py`/`*.pyi`, se normalizó el working tree Python, se limpió el cache local
  roto de Black y `black --check app tests`, `ruff format --check app tests`,
  `ruff check app tests` y `pytest tests -q` quedaron OK.
- Frontend Vue operativo con dashboard, clientes, comprobantes, emisión masiva,
  reportes, certificados, puntos de venta, emisores y usuarios.
- Integración visual controlada iniciada en frontend público: el corte 1 agregó
  fundaciones de identidad sin cambios visibles, el corte 2A aplicó la marca
  solo al shell común de la app, el corte 2B tokenizó componentes `Base*` y el
  corte 2C alcanzó componentes comunes (`ConfirmDialog` y `Pagination`), sin
  tocar lógica fiscal, servicios, rutas ni pantallas de emisión completas.
- Launcher local Windows manual agregado para desarrollo/QA: `FactuFlow
  Local.vbs` inicia backend/frontend en segundo plano sin ventana de
  PowerShell, muestra estado en el tray y abre `http://localhost:8080` cuando
  el sistema queda listo.
- El uso local con launcher ya está implementado y testeado hasta nivel
  desarrollo/QA. La primera instalación privada en VPS con Docker producción,
  PostgreSQL y HTTPS quedó validada el 2026-06-09.
- El VPS quedó cerrado operativamente después del primer uso real: checkout
  limpio y alineado con `origin/main`, configuración privada fuera de Git,
  servicios sanos, backup manual validado, copia cifrada fuera del VPS y
  restauración de prueba verificada.
- Herramienta privada de migración local a VPS implementada para preparar el
  paso de `backend/data/factuflow.db` a PostgreSQL, preservando configuración
  operativa, certificados activos, formatos, perfiles, comprobantes e ítems, y
  excluyendo lotes, artefactos, temporales, PDFs, Excel, logs y cachés.
- El preflight real bloqueó inicialmente por un certificado demo activo que
  apuntaba a `pendiente.crt` / `pendiente.key`. Se hizo backup privado de la
  SQLite, se desactivó solo ese placeholder demo y el preflight quedó OK con 9
  certificados activos.
- La visión vigente define que FactuFlow debe poder instalarse localmente o en
  un VPS pequeño. Las nuevas decisiones técnicas deben optimizar
  procesamiento, RAM y almacenamiento, y evitar persistir artefactos no vitales
  cuando puedan generarse bajo demanda, descargarse a la PC del usuario y
  limpiarse del servidor.
- Gestor de almacenamiento administrativo implementado para conocer el uso total
  de la instalación y desglosarlo por emisor, base, lotes, temporales, caché,
  certificados y logs, con cálculo liviano, acceso solo para administradores y
  sin exponer datos privados innecesarios.
- La observabilidad operativa estándar queda definida como requisito antes de
  ampliar produccion: trazabilidad de lotes y comprobantes, estado del sistema,
  logs utiles para soporte, backup/restauracion y mensajes claros para usuarios
  no tecnicos.
- El login ya distingue servidor local no disponible de errores de credenciales
  y guia al usuario a usar click derecho en el icono del tray >
  `Reiniciar servicios`, o relanzar `FactuFlow Local.vbs` si el icono no
  aparece.
- El setup inicial queda cerrado cuando ya existe cualquier usuario. La pantalla
  `Configurar sistema` se muestra solo con `GET /api/auth/setup-status` en
  estado requerido; las altas posteriores se hacen desde el menú `Usuarios`.
- El rol `es_admin` queda definido como permiso para administrar usuarios. Los
  usuarios comunes activos pueden operar todos los emisores configurados; el
  emisor activo sigue resolviendo el alcance de datos por request.
- Clawpatch backend/frontend/repo queda sin hallazgos abiertos despues del
  ciclo de reparaciones 2026-05-16/17.
- PDF de comprobantes actualizado con formato administrativo alineado a la
  ubicacion principal de la factura oficial ARCA, datos fiscales completos
  disponibles, QR ARCA testeable por payload y fechas de servicio/vencimiento
  persistidas en comprobantes nuevos.
- Emisión masiva ahora puede usar plantilla oficial o plantillas/formato
  configurables con autodetección asistida. Si un perfil recuerda una
  plantilla, la descarga usa esa plantilla; si no, conserva la plantilla oficial.
- Emision masiva ahora puede aplicar perfiles de carga masiva visibles y
  editables antes de validar.
- `Emisores > Carga masiva` tiene subtabs de `Perfiles` y `Plantillas`. El
  constructor visual permite partir de cero o de encabezados de un Excel,
  ordenar/agregar/quitar campos, fijar valores constantes, revisar
  compatibilidad y descargar un Excel con hoja `Comprobantes`, hoja
  `Instrucciones` y metadatos no fiscales ocultos.
- QA visual local de plantillas ejecutada el 2026-06-10: creación desde cero,
  constructor desde Excel, clonación de plantilla protegida, scoping por emisor,
  permisos de usuario común, descarga directa y descarga desde perfil en
  `Emisión masiva`, sin validar lotes, emitir ni llamar a ARCA.
- Emision masiva muestra progreso real de emision para lotes chicos y grandes,
  con timer de tiempo transcurrido y estimacion restante.
- Selector de emisor activo implementado para que contadores independientes o
  estudios chicos operen varios emisores con un emisor activo explicito por vez.
- La decisión de producto vigente evita una plataforma multiempresa compleja
  por ahora; el foco es reforzar que clientes, certificados, puntos de venta,
  comprobantes, lotes, PDFs, reportes, perfiles y formatos no se mezclen entre
  emisores.
- Emision individual y masiva funcionando en homologacion y validadas manualmente desde la interfaz.
- Produccion real ya fue utilizada con comprobantes autorizados y lotes
  productivos. La evidencia detallada vive en base/logs/archivos privados
  ignorados por Git y no debe copiarse a documentacion versionada.
- La auditoría post-emisión productiva se ejecutó con llamadas ARCA seguras de
  solo lectura. No solicitó CAE, no emitió comprobantes y no modificó datos.
  Resultado sanitario: numeración local alineada con ARCA para combinaciones
  operativas consultables, CAE y totales coincidentes en los últimos
  comprobantes consultados, secuencias PostgreSQL correctas y sin
  inconsistencias internas bloqueantes.
- El flujo público de desarrollo, versionado, despliegue manual al VPS y
  auditoría productiva quedó documentado en
  `docs/agents/production-workflow.md`. Los datos concretos de la instalación
  real quedan en documentación privada del VPS.
- PDF generado bajo demanda y revalidado manualmente en preview y descarga.
- Se corrigieron riesgos previos de salida a produccion:
  - numeracion protegida con lock local, advisory lock PostgreSQL y constraint unico
  - idempotencia atomica de lote por hash de archivo, empresa y formato usado
  - idempotencia fiscal obligatoria por request para los caminos que solicitan
    CAE, con `X-Idempotency-Key`, operación durable e intentos fiscales
    reconciliables
  - validacion estricta de alicuotas IVA permitidas desde Excel
  - lotes grandes en cola persistente; si quedan `procesando` vencidos, el
    worker los bloquea en `requiere_reconciliacion` antes de cualquier nuevo CAE
    y marca los grupos `validado` remanentes como pendientes de reconciliación
  - perfiles Docker separados para desarrollo y produccion con PostgreSQL

## Lo más importante que quedó hecho hoy

### Integración visual controlada - usuarios 2026-06-15

- Se aplicaron tokens de marca a `UsuariosView`: encabezado, textos de tabla,
  acciones inline, checkboxes y modales de creación/restablecimiento de clave.
- El cambio quedó acotado a presentación visual. No se modificaron permisos,
  validaciones, servicios, stores, endpoints, backend ni lógica de usuarios.
- QA visual local ejecutada con sesión administradora ficticia y respuestas API
  simuladas para listado, modal de creación, modal de clave y mobile. Las
  capturas sanitizadas quedaron en
  `private/brand-lab/exports/corte-usuarios-*`; no se usaron datos reales,
  backend productivo ni ARCA.
- Verificación frontend: `git diff --check` OK, `npm run lint:check` OK,
  `npm run type-check` OK, `npm run build` OK y `npm run test:unit` OK
  (63 tests).

### Integración visual controlada - dashboard 2026-06-15

- Se aplicaron tokens de marca a `DashboardView`: encabezado, alerta de
  certificados, métricas principales y accesos rápidos.
- El cambio quedó acotado a presentación visual. No se modificaron cargas,
  watchers, navegación, servicios, stores, backend ni lógica fiscal.
- QA visual local ejecutada con sesión ficticia y respuestas API simuladas para
  dashboard escritorio/mobile, alertas, métricas y accesos rápidos. Las capturas
  sanitizadas quedaron en `private/brand-lab/exports/corte-dashboard-*`; no se
  usaron datos reales, backend productivo ni CAE.
- Verificación frontend: `git diff --check` OK, test enfocado de
  `DashboardView` OK, `npm run lint:check` OK, `npm run type-check` OK,
  `npm run build` OK y `npm run test:unit` OK (63 tests).

### Integración visual controlada - setup inicial 2026-06-15

- Se aplicaron tokens de marca a `SetupView`: fondo, wordmark, subtítulo,
  estado de verificación, indicador de progreso, títulos de paso y acciones
  responsive.
- El cambio quedó acotado a presentación visual. No se modificaron validaciones
  de usuario administrador, datos de empresa, submit, setup inicial, servicios,
  stores, rutas, backend ni lógica de autenticación.
- QA visual local con respuestas API simuladas: paso de usuario administrador y
  paso de datos de empresa en escritorio y mobile. Las capturas quedaron en
  `private/brand-lab/exports/` con prefijo `corte-setup-*`. No se usaron datos
  reales, no se llamó al backend productivo y no se solicitó CAE.
- Verificación frontend: `git diff --check` OK, `npm run lint:check` OK,
  `npm run type-check` OK, `npm run build` OK y `npm run test:unit` OK
  (63 tests).

### Integración visual controlada - login 2026-06-15

- Se aplicaron tokens de marca a `LoginView`: fondo, wordmark, subtítulo,
  título del formulario y enlace de configuración inicial.
- El cambio quedó acotado a presentación visual. No se modificaron validaciones,
  disponibilidad de servidor, login, setup inicial, servicios, stores, rutas,
  backend ni lógica de autenticación.
- QA visual local con respuestas API simuladas: login en escritorio, login
  mobile con enlace de primera instalación y aviso de servidor local no
  disponible. Las capturas quedaron en `private/brand-lab/exports/` con prefijo
  `corte-login-*`. No se usaron datos reales, no se llamó al backend productivo
  y no se solicitó CAE.
- Verificación frontend: `git diff --check` OK, test enfocado de `LoginView`
  OK, `npm run lint:check` OK, `npm run type-check` OK, `npm run build` OK y
  `npm run test:unit` OK (63 tests).

### Integración visual controlada - formulario de cliente 2026-06-15

- Se aplicaron tokens de marca a `ClienteFormView`: título, subtítulo,
  encabezados de sección, textarea de notas, separador inferior y disposición
  responsive de acciones.
- El cambio quedó acotado a clases visuales. No se modificaron `formData`,
  validaciones, submit, payloads, carga de cliente, navegación, stores,
  servicios ni backend.
- QA visual local con sesión ficticia y respuestas API simuladas: alta de
  cliente en escritorio, edición en escritorio y edición en mobile. Las
  capturas quedaron en `private/brand-lab/exports/` con prefijo
  `corte-cliente-form-*`. No se usaron datos reales, no se llamó al backend
  productivo y no se solicitó CAE.
- Verificación frontend: `git diff --check` OK, `npm run lint:check` OK,
  `npm run type-check` OK, `npm run build` OK y `npm run test:unit` OK
  (63 tests).

### Integración visual controlada - detalle de cliente 2026-06-15

- Se aplicaron tokens de marca a `ClienteDetailView`: título, acciones,
  secciones de lectura, etiquetas, valores y separadores.
- El cambio quedó acotado a clases visuales y adaptación responsive de botones.
  No se modificaron stores, servicios, rutas, carga de datos, navegación,
  edición, loading ni manejo de errores.
- QA visual local con sesión ficticia y respuestas API simuladas: detalle de
  cliente en escritorio y mobile, con datos sanitizados. Las capturas quedaron
  en `private/brand-lab/exports/` con prefijo `corte-cliente-detalle-*`. No se
  usaron datos reales, no se llamó al backend productivo y no se solicitó CAE.
- Verificación frontend: `git diff --check` OK, `npm run lint:check` OK,
  `npm run type-check` OK, `npm run build` OK y `npm run test:unit` OK
  (63 tests).

### Integración visual controlada - Clientes 2026-06-15

- Se aplicaron tokens de marca a la pantalla general `Clientes`: encabezado,
  subtítulo, buscador, textos de celdas e íconos de acciones.
- El cambio quedó acotado a clases visuales de `ClientesListView`. No se
  modificaron stores, servicios, rutas, carga de datos, paginación, acciones de
  navegación, eliminación ni confirmaciones.
- QA visual local con sesión ficticia y respuestas API simuladas: listado de
  clientes en escritorio y mobile, buscador, paginación y diálogo de
  eliminación. Las capturas sanitizadas quedaron en
  `private/brand-lab/exports/` con prefijo `corte-clientes-*`. No se usaron
  datos reales, no se llamó al backend productivo y no se solicitó CAE.
- Verificación frontend: `git diff --check` OK, `npm run lint:check` OK,
  `npm run type-check` OK, `npm run build` OK y `npm run test:unit` OK
  (63 tests).

### Integración visual controlada - componentes comunes 2026-06-15

- Se aplicaron tokens de marca a componentes comunes que todavía no habían
  pasado por la capa `Base*`: `ConfirmDialog` y `Pagination`.
- El cambio quedó acotado a estilos visuales de componentes reutilizables. No
  se modificaron props, emits, cálculo de paginación, rutas, servicios, stores,
  backend, ARCA, CAE, fechas fiscales, lotes ni pantallas fiscales completas.
- QA visual local con sesión ficticia y respuestas API simuladas sobre
  `Clientes`: paginación visible en escritorio y mobile, y diálogo de
  eliminación.
  Las capturas sanitizadas quedaron en `private/brand-lab/exports/` con prefijo
  `corte-2c-componentes-comunes-*`. No se usaron datos reales, no se llamó al
  backend productivo y no se solicitó CAE.
- Verificación frontend: `git diff --check` OK, `npm run lint:check` OK,
  `npm run type-check` OK, `npm run build` OK y `npm run test:unit` OK
  (63 tests). `autoreview` con Codex `gpt-5.5` en `high` quedó limpio, sin
  hallazgos aceptados ni accionables.
- Commit publicado en `origin/main`: `2debd2b chore(frontend): style common
  components with brand tokens`.

### Integración visual controlada - shell común 2026-06-15

- Se aplicó la identidad v01 aprobada al shell común del frontend: fondo general
  de página, header, sidebar, footer, estados de navegación y wordmark de
  FactuFlow en la barra lateral.
- El cambio quedó acotado a `AppLayout`, `Header`, `Sidebar`, `Footer` y al
  estado inicial del menú móvil en el store UI. No se modificaron rutas,
  servicios, stores fiscales, formularios de emisión, ARCA, CAE, fechas
  fiscales, lotes ni backend.
- En mobile, el menú lateral ahora inicia cerrado y se abre con el botón de la
  esquina superior izquierda. Se corrigieron superposiciones del botón con el
  header y con el wordmark del sidebar.
- QA visual local con sesión ficticia y respuestas API simuladas: capturas
  sanitizadas generadas en `private/brand-lab/exports/` para escritorio, mobile
  cerrado y mobile con menú abierto. No se usaron datos reales, no se llamó al
  backend productivo y no se solicitó CAE.
- Verificación frontend: `npm run lint:check` OK, `npm run type-check` OK,
  `npm run build` OK, `npm run test:unit` OK (61 tests) y `git diff --check`
  OK.

### Contención P0 de reanudación insegura de lotes 2026-06-12

- Después del incidente productivo de emisión masiva documentado en el VPS, se
  corrigió el contrato local del worker: un lote `procesando` que supera
  `BATCH_PROCESSING_STALE_MINUTES` ya no se reanuda automáticamente para pedir
  nuevos CAE.
- Si el lote vencido tiene comprobantes locales ya autorizados y no vinculados,
  FactuFlow solo puede reconciliarlos localmente sin llamar a ARCA cuando existe
  un `intentos_emision_fiscal` autorizado del mismo `lote_id` y `grupo_id`, con
  `comprobante_id`, número planificado, CAE, fecha, receptor y total
  coherentes. Si esa reconciliación local fuerte cierra el lote, queda en el
  estado cerrado que corresponda: `completado`, `cerrado_reconciliado` o
  `cerrado_con_descartes`.
- Si después de esa reconciliación quedan comprobantes pendientes o el estado
  sigue incierto, el lote pasa a `requiere_reconciliacion`, queda registrado un
  evento `bloqueo_operativo_no_reemitir` y la operación idempotente observable
  queda en estado de reconciliación.
- Los grupos que seguían `validado` dentro de un lote stale bloqueado también
  pasan a `requiere_reconciliacion`, con mensaje de no reintento, para que la UI
  no los muestre como comprobantes listos para emitir.
- El worker ahora procesa automáticamente solo lotes `en_cola`; los lotes
  `procesando` vencidos se convierten en tarea de auditoría/reconciliación, no
  en reemisión. Si falla el bloqueo de cualquier lote vencido, el worker
  pospone los lotes `en_cola` de ese ciclo para no avanzar con nuevos CAE sobre
  una cola fiscal todavía incierta.
- La UI no ofrece `Reintentar fallidos` cuando el lote está
  `requiere_reconciliacion`; en ese estado muestra pendientes visibles porque el
  detalle de grupos está paginado y la resolución debe hacerse por auditoría.
- Verificación final sin llamadas ARCA reales: `pytest tests -q` OK
  (303 tests), `ruff check app tests` OK y `black --check app tests` OK.
  Frontend: `npm run test:unit` OK (61 tests), `npm run build` OK,
  `npm run type-check` OK, `npm run lint:check` OK y
  `npm run test:e2e -- --reporter=list` OK (31 tests).

### E2E frontend recuperado 2026-06-11

- `npm run test:e2e` vuelve a ser evidencia local confiable para Chromium
  desktop: el wrapper levanta Vite en un puerto dedicado, falla si el puerto ya
  está ocupado, ejecuta Playwright y corta el servidor al finalizar.
- Los mocks E2E de emisión individual y masiva ahora exigen fecha fiscal
  explícita, concepto fiscal ARCA, confirmación fiscal e idempotencia, para no
  tapar regresiones críticas solo con respuestas mockeadas.
- La matriz completa de navegadores/mobile queda opt-in con
  `E2E_FULL_BROWSER_MATRIX=1`. No es el recorrido por defecto porque estos
  flujos administrativos están pensados para PC.
- Verificación frontend ejecutada: `npm run test:e2e -- --reporter=list` OK
  (31 tests), `npm run test:unit` OK (61 tests), `npm run build` OK,
  `npm run type-check` OK y `npm run lint:check` OK.

### Instalación VPS privada validada 2026-06-09

- Se instaló FactuFlow en un VPS privado existente sin afectar otros servicios
  del host.
- La app quedó con PostgreSQL remoto, backend, frontend y configuración privada
  fuera de Git.
- Se importó un paquete privado validado sobre PostgreSQL limpio ya migrado con
  Alembic hasta `e2f3a4b5c6d7`.
- `python -m app.scripts.vps_migration validate` quedó OK contra la base,
  certificados restaurados, tablas excluidas y health público HTTPS.
- Se publicó la instalación detrás de un reverse proxy HTTPS. HTTP redirige a
  HTTPS.
- QA no destructiva ejecutada: `/`, `/api/health`, `/api/docs`,
  `/api/auth/setup-status`, smoke de navegador headless sobre login público,
  health de FactuFlow y verificación de servicios existentes del host.
- Durante la instalación no se solicitó CAE ni se emitió ningún comprobante.
- Se detectó y corrigió en `backend/Dockerfile` una dependencia faltante de
  WeasyPrint para producción: librerías nativas de Cairo/Pango/GObject.

### Cierre operativo, backup y auditoría post-emisión 2026-06-10

- El VPS quedó operativo detrás de HTTPS con FactuFlow, PostgreSQL y
  configuración privada fuera del repositorio público.
- El checkout remoto quedó limpio y alineado con `origin/main`. El warning de
  Docker Compose por `version` obsoleto se resolvió quitando esa línea del
  compose productivo y actualizando el VPS.
- Se generó un backup manual privado de PostgreSQL, certificados,
  configuración privada y snapshots operativos mínimos. El backup se validó con
  checksums, `pg_restore --list` y restauración en una base temporal.
- Se creó una copia cifrada fuera del VPS y se probó restaurarla en un
  PostgreSQL local efímero desde el archivo cifrado. La prueba confirmó que el
  dump puede recuperarse sin depender del servidor original.
- La automatización de backups no se implementa todavía por decisión operativa:
  queda pendiente definir frecuencia, retención, almacenamiento externo,
  verificación periódica y runbook completo de recuperación a un VPS nuevo.
- Después de emisiones reales hechas desde la instalación VPS, se ejecutó una
  auditoría segura contra ARCA con `FECompUltimoAutorizado` y
  `FECompConsultar`. Fue una revisión de solo lectura: no solicitó CAE, no
  emitió comprobantes, no reinició servicios y no modificó datos.
- La auditoría no encontró desfases fiscales ni inconsistencias bloqueantes
  entre FactuFlow y ARCA para las combinaciones operativas consultables. Una
  combinación histórica sin certificado activo quedó registrada como no
  consultable, no como error operativo actual.

### Idempotencia y deduplicación fiscal segura 2026-06-04

- Se agregó idempotencia fiscal obligatoria para emisión individual,
  procesamiento de lotes y reintento de fallidos.
- El backend rechaza operaciones fiscales sin `X-Idempotency-Key`; misma clave
  con mismo payload devuelve la respuesta persistida o el estado actual, y misma
  clave con datos distintos devuelve conflicto.
- Antes de solicitar CAE, FactuFlow persiste `operaciones_idempotentes` y
  `intentos_emision_fiscal` con snapshot mínimo: emisor, usuario, tipo, punto de
  venta, número planificado, fecha fiscal, total, receptor, CAE si existe,
  lote/grupo y categoría de error.
- La numeración queda reservada por intento fiscal para estados activos. Si un
  intento queda `en_proceso` vencido, FactuFlow consulta `FECompConsultar` antes
  de liberar la reserva o vincular un comprobante autorizado.
- Si ARCA confirma CAE y FactuFlow puede encontrar o reconstruir el comprobante
  desde un grupo de lote, lo vincula. Si no tiene payload fiscal completo, el
  intento queda `requiere_reconciliacion`; no se reintenta automáticamente.
- La deduplicación lógica es advertencia con confirmación adicional. La
  confirmación de duplicado no integra el hash idempotente, por lo que permite
  continuar la misma operación después de la advertencia sin cambiar clave.
- La UI genera claves con `crypto.randomUUID()` por confirmación fiscal final,
  las reutiliza para retries de la misma operación y las resetea cuando cambian
  datos fiscales, lote, selección o cancelación definitiva.
- La columna `Ref` de lotes queda fuera de este control: sigue siendo dato de
  agrupación/UI del lote, no llave fiscal de idempotencia.
- Verificación completa ejecutada después de la implementación: backend
  `.venv\Scripts\python.exe -m pytest tests` OK (262 tests),
  `ruff check backend\app backend\tests` OK y `black --check backend\app
  backend\tests` OK; frontend `npm run test:unit` OK (57 tests),
  `npm run type-check` OK y `npm run lint:check` OK.

### Control de diseño fiscal crítico 2026-06-04

- Se agregó `docs/agents/fiscal-change-checklist.md` como checklist obligatorio
  antes de implementar funcionalidades, correcciones o mejoras que afecten
  ARCA/WSFE, CAE, numeración, fechas fiscales, comprobantes, lotes, reintentos,
  reconciliación, certificados, puntos de venta, migraciones fiscales,
  confirmaciones irreversibles o aislamiento por emisor.
- Las instrucciones ahora exigen diseñar cambios fiscales con invariantes
  verificables, tabla de estados, orden de operaciones, fallos intermedios,
  concurrencia, constraints, reconciliación y matriz de tests antes del código.
- El uso de `autoreview` para cambios fiscales críticos queda definido como
  escalonado y crítico: `gpt-5.5 low`, luego `medium` y luego `high`, corrigiendo
  solo hallazgos aceptados después de verificarlos contra el código y el alcance
  real.

### Preparación local de migración a VPS 2026-06-04

- Se agregó `python -m app.scripts.vps_migration` con subcomandos
  `preflight`, `export`, `import` y `validate`.
- `preflight` valida SQLite local, head Alembic, tablas esperadas,
  certificados activos y ausencia de certificados incompletos.
- `export` genera paquetes privados en `.tmp/vps-migration/<timestamp>/` con
  `manifest.json`, JSONL por tabla incluida, certificados activos y plantilla
  privada de variables requeridas, sin guardar secretos reales en Git.
- Las claves privadas exportadas se re-cifran con
  `ARCA_MIGRATION_TARGET_KEY_PASSWORD`; el importador exige que
  `.env.production` use la misma contraseña como `ARCA_PRIVATE_KEY_PASSWORD`.
- `import` restaura sobre PostgreSQL limpio ya migrado con Alembic, preserva
  IDs, ajusta secuencias y no modifica `alembic_version`.
- `validate` compara conteos, tablas excluidas, certificados restaurados,
  secuencias y disponibilidad básica opcional por API/login.
- El alcance migrado es operación futura: emisores, usuarios, clientes, puntos
  de venta, certificados, formatos, perfiles, comprobantes e ítems. Se excluyen
  lotes, filas, temporales, PDFs, Excel, logs, cachés y exportaciones.
- Verificación enfocada: `pytest tests/test_vps_migration.py -q` OK (9 tests),
  `ruff check app/scripts/vps_migration.py tests/test_vps_migration.py` OK y
  `black --check app/scripts/vps_migration.py tests/test_vps_migration.py` OK.
- Ensayo real local seguro completado en PostgreSQL con Docker:
  `alembic upgrade head` llegó a `e2f3a4b5c6d7`, la importación del paquete
  privado quedó OK, `validate` quedó OK, las tablas excluidas quedaron vacías,
  las secuencias quedaron por encima del máximo ID restaurado, se restauraron 9
  `.crt` y 9 `.key`, y `/api/health` respondió 200 contra el backend temporal.
  No se solicitó CAE ni se hicieron emisiones.

### Gestor de almacenamiento administrativo 2026-06-03

- Se agregó la sección administrativa `Sistema > Almacenamiento`, visible solo
  para usuarios con `es_admin`.
- El backend expone `/api/almacenamiento` para resumen de uso, lotes
  compactables, logs antiguos, temporales administrados, certificados huérfanos
  gestionados, creación de resguardos ZIP, descarga y liberación posterior.
- La liberación de lotes, logs y temporales exige preparar un ZIP, descargarlo
  y confirmar `Ya lo descargué`; no hay limpieza automática después de la
  descarga.
- Los lotes cerrados se compactan desde el gestor usando el mismo criterio de
  ahorro de almacenamiento: se elimina el detalle original por fila y se
  conservan lote, grupos, comprobantes, totales y auditoría.
- Los certificados no se exportan en ZIP. La limpieza de certificados queda
  separada y solo aplica a archivos gestionados por FactuFlow que no están
  referenciados por la base.
- Se agregó auditoría genérica con `EventoSistema` y registro de
  `ExportacionAlmacenamiento` con token opaco, checksum, tamaño, selección y
  manifest.
- Verificación enfocada: backend
  `pytest tests/test_almacenamiento.py -q` OK (7 tests); frontend
  `npm run test:unit -- --run src/components/layout/Sidebar.spec.ts src/views/sistema/SistemaView.spec.ts`
  OK.

### Gestión inicial de usuarios 2026-06-03

- La instalación nueva mantiene el flujo de primer administrador propietario,
  pero ahora expone `GET /api/auth/setup-status` para que la UI muestre
  `Configurar sistema` solo cuando no hay usuarios.
- Se agregó `/api/usuarios` para administradores: listar, crear, editar,
  desactivar/reactivar y restablecer contraseña. No hay borrado físico de
  usuarios.
- El backend impide que un administrador desactive, degrade o cambie el email de
  su propia cuenta desde la sesión activa, preservando acceso administrativo.
- Todos los usuarios activos pueden seleccionar cualquier emisor configurado por
  `X-Empresa-Id` o `empresa_id`; `empresa_id` del usuario queda como preferencia
  inicial, no como restricción de acceso operativo. El borrado físico de
  emisores queda reservado a administradores porque puede afectar historial
  fiscal y relaciones internas; antes de borrar se limpia esa preferencia en
  usuarios globales para no eliminar cuentas por cascade.
- El frontend muestra el selector `Emisor activo` para todos los usuarios y
  agrega la pantalla `Usuarios` solo para administradores, con guard de ruta.
- Verificación focalizada:
  `pytest tests/test_auth.py tests/test_usuarios_api.py tests/test_clientes.py tests/test_empresas.py -q`
  OK (37 tests), frontend
  `npm run test:unit -- --run src/views/auth/LoginView.spec.ts src/stores/empresa.spec.ts src/components/layout/Sidebar.spec.ts`
  OK (12 tests) y `npm run type-check` OK.

### Emisión masiva por sublotes ARCA 2026-06-03

- El backend ahora puede emitir lotes WSFE en sublotes: consulta
  `FECompTotXRequest`, toma `RegXReq` como máximo permitido y arma
  `FECAESolicitar` con `CantReg` igual a la cantidad de detalles enviados.
- Los sublotes se agrupan solo por mismo emisor, punto de venta y tipo de
  comprobante. Los tipos FCE/MiPyME se fuerzan a emisión unitaria.
- Si `FECompTotXRequest` falla o ARCA no devuelve `RegXReq`, FactuFlow degrada
  al modo unitario existente, guarda metadata `arca_batch` en el lote y muestra
  aviso en la pantalla para explicar que el procesamiento puede demorar más.
- Si un sublote ya enviado no devuelve detalle confiable, el lote queda en
  `requiere_reconciliacion` para evitar reintentos automáticos hasta consultar
  ARCA.
- El progreso del lote ahora recalcula contadores con agregaciones SQL, sin
  cargar todos los grupos y filas en cada avance.
- Verificación técnica segura, sin llamadas reales a ARCA ni CAEs:
  `python -m pytest backend/tests/test_arca/test_wsfev1.py backend/tests/test_facturacion_service.py::test_emitir_comprobantes_lote_usa_un_request_arca_y_persiste_numeracion backend/tests/test_lotes_comprobantes.py::test_procesar_lote_usa_sublotes_arca_segun_regxreq backend/tests/test_lotes_comprobantes.py::test_procesar_lote_fallback_regxreq_degrada_a_unitario_con_aviso -q`
  OK (6 tests).

### Gestión resolutiva y compactación de lotes 2026-06-03

- Los lotes parciales ya no quedan obligados a vivir indefinidamente como
  `autorizado_parcial`: la UI permite reintentar fallidos, reconciliar
  comprobantes emitidos manualmente en ARCA Web o descartar pendientes que no
  deben emitirse desde FactuFlow.
- Reintentar fallidos vuelve a exigir el token exacto
  `X-Confirmacion-Fecha-Fiscal` calculado desde esos grupos. No se relaja la
  regla fiscal crítica de fecha de emisión.
- El reintento toma el grupo de forma durable antes de pedir CAE. Si el proceso
  se interrumpe en esa ventana, el grupo queda como `reintentando` y se trata
  como reconciliable; no vuelve a `fallido` para evitar una segunda solicitud
  fiscal sin verificar ARCA.
- La reconciliación externa consulta `FECompConsultar` antes de tocar datos
  locales. Solo se registra el comprobante como `origen_emision = arca_web` si
  ARCA confirma emisor, receptor, tipo, punto de venta, número, fecha fiscal,
  total y CAE.
- Los cierres quedan diferenciados:
  - `completado`: todos los comprobantes fueron emitidos por FactuFlow
  - `cerrado_reconciliado`: todos quedaron autorizados, pero uno o más se
    emitieron fuera de FactuFlow y fueron verificados contra ARCA
  - `cerrado_con_descartes`: el lote se cerró con pendientes descartados por
    decisión operativa
- La compactación de lotes cerrados elimina las filas originales del Excel para
  ahorrar almacenamiento y conserva lote, grupos, comprobantes, totales y
  eventos auditables. Después de compactar, ya no se puede regenerar el archivo
  observado porque ese archivo depende del detalle por fila.
- Ajuste posterior de UX: compactar no requiere cargar motivo. La UI muestra un
  popup con consecuencias y el evento interno usa el motivo estándar
  `Compactación para ahorro de almacenamiento`.
- La eliminación física queda restringida a lotes sin emisión ni incertidumbre
  fiscal. Antes de borrar se registra un evento auditado con los metadatos del
  lote eliminado.
- Verificación enfocada segura, sin llamadas reales a ARCA ni CAEs:
  backend `python -m pytest backend/tests/test_lotes_comprobantes.py -q` OK
  (63 tests); frontend `npm run test:unit -- --run src/utils/lote-progress.spec.ts src/utils/lote-totals.spec.ts src/views/comprobantes/LotesComprobantesView.spec.ts`
  OK (14 tests), `npm run type-check` OK y `npm run lint:check` OK.

### Detalle paginado de lotes grandes 2026-05-29

- La pantalla `Emision masiva` ya no abre el lote trayendo y renderizando todos
  los grupos y filas. Ahora usa `GET /api/lotes-comprobantes/{lote_id}/resumen`
  para el resumen fiscal completo y
  `GET /api/lotes-comprobantes/{lote_id}/grupos` para una pagina de grupos.
- El resumen fiscal conserva el alcance completo del lote: totales listos para
  emitir, fechas de emision validas, puntos de venta validos y token exacto de
  confirmacion fiscal `fechas=...;puntos_venta=...`.
- La grilla de comprobantes carga 100 grupos por pagina y permite filtrar por
  estado. El Excel observado sigue siendo el camino para revisar el detalle por
  fila completo.
- Verificacion visual local con navegador integrado sobre un lote de 1432
  comprobantes: la vista inicial quedo en 100 filas renderizadas, `nodeCount`
  aproximado 2026 y `scrollHeight` aproximado 15371. Antes de este cambio la
  misma pagina tenia aproximadamente 24629 nodos y `scrollHeight` 165654.
- Verificacion tecnica: backend
  `python -m pytest backend/tests/test_lotes_comprobantes.py -q` OK
  (46 tests), `ruff check` OK, `ruff format --check` OK; frontend
  `npm run test:unit -- LotesComprobantesView`, `npm run type-check` y
  `npm run lint:check` OK. Nota posterior 2026-06-03: el cuelgue local de
  `black --check` se atribuyó al cache local de Black y quedó resuelto al
  limpiar `%LOCALAPPDATA%\black\black\Cache\23.12.1`.

### Alineacion documental post-piloto 2026-05-22

- Se verifico evidencia local en modo solo lectura y se confirmo que la
  documentacion que todavia hablaba de "primera prueba real pendiente" estaba
  desactualizada.
- La operacion productiva real ya ocurrio. Los detalles privados de CUITs,
  CAEs, clientes, comprobantes, Excels y logs siguen fuera de Git.
- Se hizo un corte versionado en `CHANGELOG.md` para dejar `0.2.0-mvp` como
  linea base actual y resumir el avance historico sin sumar snapshots largos.
- Desde este punto, el foco operativo ya no es ejecutar el primer CAE real, sino
  consolidar el uso post-piloto: evidencia resumida, backups/restauracion,
  observabilidad, trazabilidad de lotes, descarga masiva de PDFs y mejoras de
  soporte administrativo.

### Launcher local Windows 2026-05-18

- Se agrego `FactuFlow Local.vbs` como acceso de doble click para iniciar el
  entorno local sin exponer ventanas tecnicas. `FactuFlow Local.cmd` queda como
  compatibilidad y delega en el mismo launcher oculto.
- Se agrego `scripts/factuflow-local-tray.ps1`, un launcher con icono en el
  tray que verifica backend, base de datos y frontend, inicia servicios faltantes
  con el flujo actual y muestra estados verde/amarillo/rojo.
- El menu del tray permite abrir FactuFlow, consultar estado del sistema,
  reiniciar servicios iniciados por el launcher, detenerlos, abrir logs y salir.
- Los logs quedan en `.tmp/local-launcher/` y no se versionan.
- Esta etapa no es un instalador, no empaqueta dependencias y no configura
  inicio automatico con Windows; sigue orientada a entorno local de desarrollo o
  QA.
- Verificacion: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File
  scripts\factuflow-local-tray.ps1 -SelfTest`, backend `pytest tests -q`,
  `ruff`, `black`; frontend `lint:check`, `type-check`, `build` y `test:unit`.

### Login con backend local no disponible 2026-05-18

- Se agrego chequeo de `GET /api/health` antes del login.
- Si el backend local no responde, la UI muestra
  `FactuFlow no está listo para iniciar sesión` y no envia credenciales.
- El mensaje indica hacer click derecho en el icono de FactuFlow junto al reloj,
  elegir `Reiniciar servicios`, esperar a que quede verde y presionar
  `Reintentar`. Si el icono no aparece, indica abrir nuevamente
  `FactuFlow Local.vbs`.
- Quedo documentado el runbook de etapas futuras en
  `docs/agents/local-launcher-runbook.md`.

### Puesta a punto Clawpatch 2026-05-16

- Se agrego estado local ignorado `.clawpatch/`, metadata minima
  `backend/pyproject.toml`, manifiesto operativo `backend/package.json` y
  scripts raiz para inicializar, mapear, consultar estado y revisar backend y
  frontend con `clawpatch@0.1.0`.
- La version actual de Clawpatch no trae mapper Python. Para que backend tenga
  entradas detectables sin tocar runtime, el manifiesto del backend expone los
  checks Python existentes contra `.venv`.
- Smoke ejecutado sin fixes: backend detecta 4 features y frontend detecta 6
  features. El estado interno queda fuera del historial Git en `.clawpatch/`.
- Ajuste posterior: se agrego una capa versionada de features manuales en
  `tools/clawpatch/` para cubrir codigo real de FactuFlow. El smoke actual con
  `npm run clawpatch:map-all` deja `repo=4`, `backend=10` y `frontend=10`
  features. El nivel `repo` cubre flujos end-to-end frontend/backend y no usa
  el mapper nativo de la raiz porque puede escanear carpetas locales ignoradas.
- Review ejecutado sobre `repo`: 4 features end-to-end revisadas, 21 findings
  abiertos, sin `fix`, sin CAE ni llamadas reales ARCA. Los reportes crudos
  quedan como evidencia local ignorada por Git porque detallan hallazgos de
  seguridad abiertos; el resumen publico debe ser sanitizado antes de subirse.
- Regresion tecnica posterior OK: backend `pytest tests -q`, `ruff`, `black`;
  frontend `lint:check`, `type-check`, `build` y `test:unit`.
- Reporte de cierre:
  `docs/project/audits/clawpatch/2026-05-16-puesta-a-punto.md`.

### Reparaciones Clawpatch 2026-05-16

- Primer ciclo cerrado: la emision individual y la emision desde lotes validan
  en `FacturacionService` que el punto de venta y el `cliente_id` opcional
  pertenezcan al emisor activo antes de solicitar CAE. Esto evita vincular
  comprobantes de un emisor con clientes o puntos de venta de otro CUIT.
- Verificacion focalizada sin llamadas ARCA reales:
  `pytest tests/test_facturacion_service.py tests/test_comprobantes_api.py -q`,
  `ruff check app/services/facturacion_service.py tests/test_facturacion_service.py`
  y `black --check app/services/facturacion_service.py tests/test_facturacion_service.py`.
- Segundo ciclo cerrado: certificados ARCA endurecidos. El upload ya no acepta
  `key_filename` con paths absolutos o traversal; los paths guardados deben
  resolver dentro de `CERTS_PATH`; las claves privadas nuevas se cifran con
  `ARCA_PRIVATE_KEY_PASSWORD` o, si no esta configurada, con `APP_SECRET_KEY`;
  los nombres de certificados/claves incluyen nonce para evitar colisiones; al
  subir una renovacion se desactivan certificados activos previos del mismo
  emisor/ambiente; y al borrar un certificado se eliminan archivos gestionados
  no compartidos.
- Se agrego migracion Alembic `a3b4c5d6e7f8` con indice parcial unico para
  permitir un solo certificado activo por emisor y ambiente.
- Verificacion focalizada sin llamadas ARCA reales:
  `pytest tests/test_certificados.py tests/test_certificados_scope.py tests/test_arca/test_arca_api.py -q`,
  `ruff check` y `black --check` sobre modulos de certificados/ARCA tocados.
- Tercer ciclo actualizado el 2026-06-12: lotes en `procesando` ya no pueden
  volver a reencolarse por API ni reanudarse automáticamente por stale. El
  worker procesa lotes `en_cola`; si detecta un lote `procesando` vencido,
  primero vincula comprobantes locales ya autorizados cuando puede hacerlo sin
  pedir CAE y, si queda cualquier incertidumbre o pendiente, marca el lote como
  `requiere_reconciliacion` con evento `bloqueo_operativo_no_reemitir`. Los
  grupos `validado` remanentes pasan a `requiere_reconciliacion`.
- Verificacion focalizada sin llamadas ARCA reales:
  `pytest tests/test_lotes_comprobantes.py::test_procesar_lote_background_encola_lote_chico tests/test_lotes_comprobantes.py::test_tomar_lote_para_procesamiento_es_atomico tests/test_lotes_comprobantes.py::test_procesar_background_no_reencola_lote_en_proceso tests/test_lotes_comprobantes.py::test_tomar_lote_no_reanuda_procesando_stale tests/test_lotes_comprobantes.py::test_procesar_lote_procesando_stale_bloquea_sin_emitir tests/test_lotes_comprobantes.py::test_procesar_lote_grande_encola_y_se_reanuda -q`,
  `ruff check` y `black --check` sobre lotes/worker.
- Cuarto ciclo cerrado: fallos posteriores a una respuesta ARCA con CAE ya no
  quedan ocultos como errores genericos ni como fallos reintentables. La
  respuesta conserva punto de venta, numero, fecha, total y CAE, marca
  `requiere_reconciliacion=true`, la API individual responde `409`, y los lotes
  pasan a estado `requiere_reconciliacion` para bloquear reintentos automaticos.
- Verificacion focalizada sin llamadas ARCA reales:
  `pytest tests/test_facturacion_service.py tests/test_comprobantes_api.py tests/test_lotes_comprobantes.py::test_procesar_lote_post_arca_requiere_reconciliacion -q`,
  `ruff check`, `black --check`, frontend `type-check` y `lint:check`.
- Quinto ciclo cerrado: Factura C queda bloqueada localmente con IVA distinto
  de 0 antes de pedir CAE. En emision individual, la UI limita las alicuotas a
  IVA 0 al elegir Factura C y normaliza items existentes; en lotes, la
  validacion rechaza grupos tipo C con IVA mayor a 0.
- Verificacion focalizada sin llamadas ARCA reales:
  `pytest tests/test_lotes_comprobantes.py::test_validar_lote_rechaza_factura_c_con_iva tests/test_facturacion_service.py::test_validar_datos_rechaza_factura_c_con_iva -q`,
  `ruff check`, `black --check`, frontend `type-check` y `lint:check`.
- Sexto ciclo cerrado: el emisor activo quedo consistente entre UI y API. El
  frontend usa `sessionStorage` como fuente por pestaña para `X-Empresa-Id` y
  conserva `localStorage` solo como preferencia inicial. El backend acepta el
  query legacy `empresa_id` solo si no contradice el header y rechaza conflictos
  explicitos. La UI dejo de mandar `empresa_id` redundante en listados y
  reportes.
- Septimo ciclo cerrado: la vista previa de nueva factura ya muestra el punto
  de venta seleccionado en lugar de usar siempre `0001`.
- Octavo ciclo cerrado: el Excel observado de lotes escapa textos que Excel
  podria interpretar como formulas, tanto desde datos originales como desde
  mensajes de resultado.
- Noveno ciclo cerrado: `Puntos de venta` consulta `GET /api/arca/status` y
  habilita `Sincronizar con ARCA` solo si existe certificado activo para el
  ambiente real configurado en backend (`ARCA_ENV`).
- Verificacion focalizada sin llamadas ARCA reales:
  `pytest tests/test_clientes.py::test_admin_puede_resolver_empresa_por_query_legacy tests/test_clientes.py::test_admin_rechaza_conflicto_header_y_query_empresa tests/test_clientes.py::test_usuario_no_admin_rechaza_empresa_query_ajena tests/test_comprobantes_api.py -q`,
  `pytest tests/test_lotes_comprobantes.py::test_archivo_observado_escapa_textos_con_formulas -q`,
  `pytest tests/test_arca/test_arca_api.py::TestArcaAPIEndpoints::test_status_informa_certificado_del_ambiente_actual -q`,
  `ruff check`, `black --check`, frontend `type-check`,
  `test:unit -- empresa-activa-storage` y `lint:check`.
- Ciclos extendidos cerrados: backend y frontend quedaron revalidados feature
  por feature con Clawpatch. Se corrigieron uploads XLSX malformados o grandes,
  confirmacion fiscal de lotes con token exacto `fechas=...;puntos_venta=...`,
  numeracion ARCA adelantada como reconciliacion, reportes IVA con signo de
  notas de credito, bootstrap concurrente, carreras async por cambio de emisor
  activo, Factura A solo con CUIT, orden estable de items, refresco post-CAE no
  bloqueante, IVA 27% en detalle de subdiario y enlaces externos ARCA con
  `noopener noreferrer`.
- QA en Chrome posterior: `Nueva factura` ya no selecciona puntos que no son
  usables por FactuFlow. El selector toma el primer punto Web Services activo,
  no bloqueado y sin baja; `/api/comprobantes/proximo-numero` devuelve 400 de
  negocio si alguien consulta un punto no usable, en lugar de filtrar como
  error interno.
- Cierre Clawpatch:
  - backend `openFindings=0`
  - frontend `openFindings=0`
  - repo `openFindings=0`
  - `clawpatch review --limit 50 --jobs 1` a nivel repo no encontro features
    pendientes ni hallazgos nuevos.

### PDF profesional y QR ARCA 2026-05-14

- Se rediseño el PDF de comprobante con una estructura mas cercana a la
  ubicacion de elementos principales de la factura oficial ARCA, sin copiar
  identidad visual ni depender de un formato ARCA editable.
- El PDF ahora organiza `ORIGINAL`, caja de letra/codigo, emisor, receptor,
  periodo, detalle, totales, CAE, vencimiento CAE, leyenda ARCA y QR en una
  hoja A4.
- Para consumidor final sin documento, el PDF no expone el `0` tecnico usado en
  WSFE/QR; muestra `Doc.: -`, consigna `Condicion frente al IVA: Consumidor
  Final` y solo deja el nombre vacio cuando la razon social tambien es generica
  (`A CONSUMIDOR FINAL`/`Consumidor Final`). Si el lote trae una razon social
  real del receptor, se muestra aunque el documento sea tecnico `0`.
- Se agrego `ingresos_brutos` al emisor para poder mostrar ese dato fiscal en
  el PDF cuando este cargado. Los emisores existentes pueden completarlo desde
  `Emisores`.
- Los comprobantes nuevos persisten `fecha_servicio_desde`,
  `fecha_servicio_hasta` y `fecha_vto_pago` para que el PDF muestre periodo
  facturado y vencimiento cuando el concepto fiscal sea servicios o ambos.
- Se agrego backfill por Alembic para comprobantes historicos emitidos por lote:
  si el comprobante no tenia fechas de servicio pero el `payload_json` del grupo
  las conservaba, se reconstruyen `fecha_servicio_desde`,
  `fecha_servicio_hasta`, `fecha_vto_pago` y `fecha_vencimiento`.
- El QR quedo separado en payload y URL testeables. La prueba decodifica el
  Base64 y verifica campos oficiales: `ver`, `fecha`, `cuit`, `ptoVta`,
  `tipoCmp`, `nroCmp`, `importe`, `moneda`, `ctz`, `tipoDocRec`,
  `nroDocRec`, `tipoCodAut` y `codAut`.
- Verificacion tecnica focalizada: `pytest tests/test_pdf_service.py
  tests/test_facturacion_service.py -q`, `ruff check app tests alembic`,
  `black --check app tests alembic` y `npm run type-check` OK.

### Formato privado Factura B IVA 21% 2026-05-11

- Se creo en la base local un formato particular de Factura B IVA 21% para un
  emisor privado.
- El formato mapea `Imp. Neto Gravado` como `item_precio_unitario` y `Imp.
  Total` solo como total informado para control de consistencia. Esto evita
  repetir el error de usar el total final como neto y volver a agregar IVA.
- El Excel privado contiene 1432 filas utiles, todas `Factura B`, fecha de
  origen `28/02/2026`, receptor sin documento ni denominacion y columna
  `Punto de Venta` vacia.
- El perfil predeterminado local del emisor privado quedo vinculado al formato,
  mantiene punto de venta fijo `5`, concepto fiscal `Servicios`, descripcion
  fija `Servicios` y reglas relativas existentes.
- QA segura sin emision real sobre copia de base local: deteccion de formato
  con confianza alta `1.0`; validacion con fecha de emision fija
  `30/04/2026`, periodo `01/04/2026 - 30/04/2026`, vencimiento `30/04/2026`
  y punto fijo `5`; resultado 1432 grupos validos, 0 con error, 0 emitidos.
- QA negativa sobre copia de base local: un formato deliberadamente incorrecto
  usando `Imp. Total` como neto dejo 1432 grupos con error por diferencia entre
  total calculado y total informado, 0 validos y 0 emitidos.
- En la pantalla de detalle del lote validado se agrego un bloque de totales
  listos para emitir: comprobantes, neto, IVA 21%, IVA 10,5% y total. El
  calculo se hace sobre grupos validados antes de presionar `Emitir
  comprobantes validos`, para comparar contra el Excel sin solicitar CAE.

### Constancias de emisores mas robustas 2026-05-10

- El parser de constancias ARCA de emisores ahora distingue formatos de
  inscripción de persona jurídica, inscripción de persona física y opción de
  Monotributo.
- La extraccion corrige cortes comunes introducidos por PDFs en nombre fiscal,
  domicilio y localidad, y evita usar lineas tecnicas como provincia.
- La provincia se valida contra un catalogo cerrado de provincias argentinas en
  backend y en la pantalla `Emisores`; ya no queda como texto libre en alta o
  edicion de emisor.

### Punto de venta en perfiles de carga masiva 2026-05-10

- Los perfiles de carga masiva ahora pueden precargar si el lote usa el punto de
  venta definido en el archivo o un punto fijo del emisor activo.
- Solo se puede guardar un punto fijo si esta cargado en `Puntos de venta` para
  ese emisor y es usable por FactuFlow: Web Services, activo, no bloqueado y sin
  fecha de baja.
- Si el emisor no tiene puntos usables cargados, la UI indica que primero deben
  completarse en `Puntos de venta`.
- En `Emision masiva`, la seleccion queda visible y editable antes de validar.
  Si se fija un punto, el backend sobrescribe el punto de venta de todas las
  filas antes de validar y guarda la politica en `metadata_json`.
  La barrera fiscal final no cambia: antes de solicitar CAE sigue apareciendo
  el modal irreversible con fecha fiscal y puntos de venta concretos.

### Sincronizacion de puntos WSFE 2026-05-10

- Se verifico un emisor privado: ARCA produccion devuelve puntos por
  `FEParamGetPtosVenta` con `Bloqueado=N` y sin fecha de baja.
- La base local los tenia creados solo con numero, sin `sistema` ni
  `es_webservice`, por lo que FactuFlow los mostraba como `Otro sistema`.
- Se ajusto `Sincronizar con ARCA` para que los puntos devueltos por WSFE se
  creen o actualicen como Web Services activos, no bloqueados y usables por
  FactuFlow.

### Progreso real de lotes con timer 2026-05-10

- `POST /api/lotes-comprobantes/{lote_id}/procesar` acepta
  `background=true`. La UI lo usa siempre para poder seguir tambien lotes
  chicos por polling.
- La confirmacion fiscal sigue siendo obligatoria: el endpoint rechaza la
  emision si falta `X-Confirmacion-Fecha-Fiscal` con el token exacto de fechas
  y puntos de venta validados.
- El procesamiento actualiza contadores del lote despues de cada grupo:
  emitidos, fallidos, validos restantes y mensaje de avance.
- La pantalla de emision masiva muestra avance real, estado `En cola`/
  `Procesando`, emitidos, fallidos, pendientes, tiempo transcurrido y estimado
  restante.
- Verificacion controlada sin emision real: se agregaron tests con
  `FacturacionService.emitir_comprobante` mockeado para lote chico background,
  contadores parciales, bloqueo sin confirmacion fiscal y toma atomica.
  Tambien se agregaron tests frontend para calculo de progreso, timer y ETA.

### Perfiles de carga masiva por emisor 2026-05-09

- Se agregaron perfiles de carga masiva por emisor activo, separados de los
  formatos de importacion. El formato interpreta columnas; el perfil precarga la
  pantalla de lotes con decisiones operativas visibles.
- Cada emisor puede tener varios perfiles de carga masiva. Si tiene uno solo,
  se aplica automaticamente en `Emision masiva`; si tiene varios, se aplica el
  predeterminado; si no hay predeterminado, no se aplica ninguno.
- `Emisores` ahora tiene pestaña `Carga masiva` para crear, editar, eliminar y
  marcar perfiles como predeterminados.
- Un perfil de carga masiva puede recordar formato de importacion opcional,
  punto de venta, concepto fiscal ARCA, descripcion facturada y reglas relativas
  de fechas como `ultimo_dia_mes_anterior`, `mes_anterior_completo`,
  `mismo_dia_emision` o `emision_mas_dias`.
- Por regla fiscal critica, el perfil de carga masiva no permite guardar
  `fecha_actual` como fecha de emision: no debe convertir la fecha del navegador
  en fecha fiscal.
- Las reglas relativas no se convierten usando la fecha del navegador al
  autoaplicar un perfil en `Emision masiva`. El usuario debe elegir una fecha
  exacta, tomarla del archivo o confirmar una base explicita antes de validar.
  El backend de lotes sigue recibiendo `archivo` o `fija` con fecha concreta, y
  guarda snapshot del perfil aplicado en `metadata_json` solo si el usuario no
  modifico la configuracion precargada antes de validar.
- No se modifico la barrera fiscal: el perfil no valida ni emite
  automaticamente, y el procesamiento de lote sigue exigiendo el modal final de
  fecha fiscal y el token exacto de `X-Confirmacion-Fecha-Fiscal`.
- QA visual local completada en `http://127.0.0.1:8080`: creacion, edicion,
  eliminacion, marcado predeterminado, autoaplicacion por emisor, cambio manual
  que anula snapshot, validacion de un Excel privado local y modal final
  `Confirmar fecha fiscal` con fecha `30/04/2026` y puntos de venta concretos.
  No se presiono la confirmacion de emision.

### Consistencia por emisor activo 2026-05-09

- Se corrigio el scoping multiemisor de Clientes: la API lista, crea, obtiene,
  actualiza y elimina clientes solo dentro del emisor activo resuelto por
  `X-Empresa-Id`; la UI recarga el listado al cambiar el selector.
- Se corrigio Comprobantes para listar contra el emisor activo y recargar al
  cambiarlo, evitando datos stale cuando un admin alterna entre CUITs.
- Se corrigieron los reportes `Ventas`, `IVA ventas` y `Ranking de clientes`:
  usan `empresaActivaId` como fuente unica y, si ya habia un reporte visible,
  lo regeneran al cambiar el emisor activo.
- Se corrigio `Nueva factura` para cargar puntos de venta, proximo numero,
  cliente y preview desde el emisor activo. Si cambia el emisor mientras se
  edita, se limpia el cliente seleccionado para evitar mezclar datos.
- QA visual con usuario local de desarrollo en `http://127.0.0.1:18082`: Dashboard,
  Clientes, Comprobantes, Emision masiva, Certificados, Puntos de venta, Nueva
  factura y los tres reportes vuelven a consultar con el `X-Empresa-Id`
  correspondiente al selector.

### Control explicito de fechas fiscales 2026-05-08

- Se detecto un riesgo critico antes de la primera prueba productiva: el backend
  usaba la fecha del dia como `CbteFch` y fecha persistida, lo que podia emitir
  comprobantes con periodo fiscal incorrecto al cargar extractos de otro mes.
- Se cambio el contrato de emision para exigir `fecha_emision` explicita; ya no
  se usa `date.today()` como fecha fiscal por defecto.
- La emision masiva ahora exige elegir antes de validar si la fecha de emision
  sale del archivo o si se fija una fecha para todo el lote.
- Para comprobantes de servicios, la pantalla tambien exige definir como se
  resuelven fecha desde, fecha hasta y vencimiento de pago: desde el archivo o
  como fechas fijas.
- La validacion de lotes marca como observados los comprobantes cuya fecha de
  emision queda fuera de la ventana ARCA antes de permitir emitir.
- La columna `Fecha` de extractos bancarios se conserva como fecha de origen y
  puede usarse como fecha de emision solo si el usuario lo confirma.
- La importacion reconoce fechas del archivo aunque Excel las entregue como
  serial numerico, caso detectado con evidencia local privada.
- Se agregaron pruebas automatizadas para impedir que un extracto con fecha fuera
  de ventana quede listo para emitir.
- Se corrigio una validacion critica de puntos de venta en emision: ARCA devuelve
  `Bloqueado=N`/`S` en `FEParamGetPtosVenta`, y FactuFlow ahora interpreta `N`
  como punto habilitado. El fallo anterior hacia que la emision rechazara puntos
  validos como `6`, `10` y `13` durante el procesamiento del lote.
- Se corrigio el armado WSFE para Factura C: ARCA rechaza el objeto `Iva` en
  comprobantes tipo C, incluso si la alicuota es 0. FactuFlow ya no envia ese
  bloque para tipos `11`, `12` y `13`, y valida que esos comprobantes no tengan
  items con IVA distinto de 0.
- Se ajusto la idempotencia de lotes para reintentos seguros: si un lote previo
  quedo `fallido` o `con_errores` y no emitio ningun comprobante, el mismo
  archivo puede volver a validarse sin borrar historial. Si el lote ya esta
  validado para emitir o emitio al menos un comprobante, el duplicado sigue
  bloqueado.
- Primera emision productiva real ejecutada: lote `11` con 20 grupos autorizados
  y CAE. Se detecto concurrencia durante el procesamiento local que genero
  comprobantes adicionales no asociados al lote, por lo que quedaron 39
  comprobantes productivos autorizados en total. Se agrego transicion atomica
  para que un lote no pueda tomarse dos veces para emision.
- Se preparo la correccion operativa de los 19 comprobantes productivos
  duplicados: FactuFlow ya soporta notas de credito/debito con comprobante
  asociado informado a WSFE como `CbtesAsoc`.
- Se genero un Excel privado local con 19 Nota de Credito C, una por cada factura
  duplicada a anular. El archivo se valido contra una copia de la base local,
  sin emitir ni registrar el lote en la base operativa: `19` grupos validos,
  `0` errores y `0` emitidos. Los importes quedan en evidencia local privada.
- El usuario proceso ese archivo privado en produccion. Verificacion posterior
  solo lectura: lote `12` quedo `completado`, `19` grupos autorizados,
  `0` fallidos y `0` con error.
- Se consultaron en ARCA produccion por `FECompConsultar` las 19 Nota de Credito
  C emitidas. Todas devolvieron `Resultado=A`, CAE coincidente, fecha
  `20260508`, importe coincidente y `CbtesAsoc` apuntando a la Factura C
  duplicada esperada.
- Incidente critico: esas 19 Nota de Credito C quedaron emitidas con fecha de
  emision `08/05/2026`. Para evitar que vuelva a ocurrir, la regla del proyecto
  queda reforzada: nunca usar la fecha del dia como default fiscal y mostrar
  siempre una confirmacion final antes de solicitar CAE:
  `Está seguro que quiere emitir comprobantes con fecha XX/XX/XX? Recuerde que luego no podrá emitir comprobantes con fecha anterior para ese mismo punto de venta.`
- La confirmacion final ya no queda solo en la UI: `POST /api/comprobantes/emitir`
  exige `confirmacion_fecha_fiscal=true` y
  `POST /api/lotes-comprobantes/{lote_id}/procesar` exige
  `X-Confirmacion-Fecha-Fiscal` con el token exacto
  `fechas=AAAA-MM-DD,...;puntos_venta=N,...`.
- Se corrigio el parser local de `FECompConsultar`: ARCA devuelve
  `CbteDesde`/`CbteHasta` en la consulta de comprobante, no `CbteNro`.
- Regla critica nueva de alineacion documental: FactuFlow no debe asumir
  productos ni servicios por defecto. Antes de emitir, el usuario debe elegir
  `Productos`, `Servicios` o `Definido por archivo`.
- Si el concepto se define por archivo, el Excel debe traer una columna valida
  con `Producto` o `Servicio` en todas las filas. Si la columna falta o algun
  valor es invalido, se informa al usuario y el lote no queda listo para emitir.
- Alineacion documental agregada: el `tipo de concepto fiscal ARCA` no es la
  descripcion facturada del item. `Productos`/`Servicios` define reglas WSFE,
  ventanas de fecha y fechas de servicio; textos como `Honorarios`,
  `Zapatillas` o `Servicio mensual` son descripcion/concepto facturado del
  item.
- Ambos datos deben quedar definidos antes de validar o emitir un lote: pueden
  venir de columnas del archivo o fijarse como valor unico para todo el lote.
  No debe haber defaults ocultos de concepto fiscal ni de descripcion de item.
- Los lotes validados antes de guardar la politica explicita de concepto quedan
  bloqueados al procesar y deben revalidarse antes de emitir.
- Los lotes validados antes de guardar la politica explicita de descripcion
  facturada tambien quedan bloqueados al procesar y deben revalidarse antes de
  emitir.
- Si la fecha tomada del archivo queda fuera de la ventana ARCA, el usuario debe
  elegir por pantalla una fecha permitida por el web service antes de emitir.

### Alineacion de formatos de importacion 2026-05-08

- Se documento la nueva capacidad de formatos de importacion configurables para
  emision masiva.
- El flujo soporta formatos globales y formatos particulares del emisor activo.
- La carga de Excel detecta encabezados y calcula candidatos. Si la coincidencia
  es de alta confianza, el formato sugerido queda preseleccionado para que el
  usuario solo lo cambie si no esta de acuerdo; si no hay sugerencia confiable,
  se exige elegir formato antes de validar.
- Si el analisis automatico de encabezados no ocurre por timing de la pantalla,
  la UI bloquea `Validar lote` y ofrece `Analizar encabezados` como reintento
  manual.
- Los mapeos soportan origen por encabezado, por columna fija o por constante.
- El lote persiste encabezados detectados, mapeo usado y version de formato para
  trazabilidad.
- El formato global inicial cubre extractos bancarios de creditos con columnas
  `Fecha`, `Créditos`, `Leyendas Adicionales1`, `Leyendas Adicionales2` y
  `Pto Vta`.
- Ese formato global usa Factura C e IVA `0`, pero no debe definir por defecto
  ni el concepto fiscal ARCA ni la descripcion facturada del item. El usuario
  debe elegir si cada dato sale del archivo o se fija para todo el lote antes de
  validar. Se valida solo para emisores Exento/Monotributo; un emisor
  Responsable Inscripto debe usar un formato particular con Factura A/B.
- Se configuro en la base local un formato particular para un emisor Responsable
  Inscripto privado: `Factura B IVA 21%`, version `5`. La muestra privada local
  se detecta con confianza alta y mapea
  `Fecha`, `Punto de Venta`, `Imp. Neto Gravado`, `Imp. Total` y
  `Nro. Doc. Receptor`. Como la muestra no trae numero de documento real, el
  receptor se trata como consumidor final sin documento cuando el importe queda
  bajo el umbral legal.
- El importador de formatos externos ahora permite mapear `item_precio_unitario`
  separado de `importe_total`. Esto permite usar neto gravado como precio del
  item y total solo como referencia para reglas de consumidor final, evitando
  recalcular IVA sobre un total ya incluido.
- Se agrego una validacion de consistencia para formatos externos: si el archivo
  trae un total informado, el total calculado por FactuFlow desde items e IVA
  debe coincidir con ese total. Si no coincide, el grupo queda con error y no se
  puede emitir. Esto bloquea el caso en que `Imp. Total` se use por error como
  neto gravado.
- Incidente con emisor Responsable Inscripto privado: se detectaron 1113
  Factura B emitidas con `Imp. Total` usado como neto y por lo tanto con 21%
  agregado de mas. Se preparo un Excel privado local
  con 1113 Nota de Credito B asociadas.
  El archivo se valido contra una copia de la base local: 1113 grupos validos,
  0 errores y 0 emitidos.
- La validacion del lote queda separada de la emision: revisar y confirmar
  `Emitir comprobantes validos` sigue siendo obligatorio antes de consumir
  numeracion fiscal.
- Quedo evidencia de QA visual local para este nuevo flujo con un extracto chico:
  deteccion del formato bancario, confirmacion obligatoria del formato,
  validacion de 3 comprobantes en puntos de venta `6`, `10` y `13`, y
  `Ya emitidos = 0`. Antes de produccion sigue faltando repetirlo con el lote
  definitivo y confirmar explicitamente la emision.

### Verificacion operativa segura 2026-05-07

- Se reviso la base local privada sin exponer claves ni
  certificados. Resultado:
  - emisor productivo privado cargado
  - certificado productivo activo para ese emisor, vencimiento `2028-05-04`
  - puntos Web Services usables `6`, `8`, `10`, `12`, `13` y `14`
  - puntos Web Services bloqueados `7` y `9`
  - lote QA privado en estado `validado`, no emitido
- Se verifico por API local, sin emitir comprobantes:
  - `POST /api/certificados/verificar-conexion/3` con `X-Empresa-Id: 2`
    devolvio `Conexion exitosa con ARCA`
  - `GET /api/arca/test-conexion` devolvio `status=ok`, ambiente
    `produccion` y servidores `OK`
  - `GET /api/arca/puntos-venta` devolvio `6`, `8`, `10`, `12`, `13` y `14`
    no bloqueados, y `7`, `9` bloqueados
  - `GET /api/arca/ultimo-comprobante/6/6` devolvio ultimo comprobante `0` y
    proximo `1` para Factura B en punto de venta `6`
- Conclusion operativa de ese momento: no faltaba configurar desde cero
  certificado productivo, autorizacion `wsfe` ni puntos de venta Web Services.
  Luego se avanzo a emision productiva real; este bloque queda como evidencia
  historica de preparacion segura previa.

### Verificacion automatizada 2026-05-07

- Backend:
  - `pytest tests -q`: 110 passed
  - `ruff check app tests`: OK
  - `black --check app tests`: OK
- Frontend:
  - `npm run lint:check`: 0 errores, 413 warnings de estilo Vue existentes
  - `npm run type-check`: OK
  - `npm run build`: OK
  - `npm run test:unit`: OK, sin archivos de test unitarios
  - Prueba visual local: OK en `http://localhost:8080/comprobantes/lotes`
    subiendo un Excel QA privado, seleccionando el formato
    global de extracto bancario y validando sin emitir
  - `npm run test:e2e`: no confiable en esta corrida; Playwright mostro la
    pantalla en blanco dentro del runner aunque `http://localhost:8080/login`
    cargo correctamente con un script Playwright directo. No usar esta corrida
    como evidencia funcional hasta corregir el setup E2E.

### Verificacion tecnica 2026-05-08 - fechas y concepto fiscal

- Backend:
  - `pytest tests -q`: 128 passed
  - `ruff check app tests`: OK
  - `black --check app tests`: OK
  - prueba real con Excel privado local: 20 filas, fecha de archivo
    `06/04/2026`; al elegir servicios el lote `id=7` queda observado con 20
    grupos con error por ventana ARCA; no se emitio ningun comprobante
  - prueba segura posterior con Excel privado local: al elegir descripcion
    desde archivo el backend rechaza la validacion porque el Excel no trae
    columna de descripcion facturada; al elegir descripcion fija de prueba
    `Honorarios`, el lote `id=8` queda con 20 grupos con error por ventana ARCA,
    0 validos, descripcion persistida `Honorarios` y 0 comprobantes emitidos
- Frontend:
  - `npm run lint:check`: 0 errores, 440 warnings de estilo Vue existentes
  - `npm run type-check`: OK
  - `npm run build`: OK
  - `npm run test:unit`: OK, sin archivos de test unitarios
  - Revision visual basica en navegador: la ruta
    `http://localhost:8080/comprobantes/lotes` carga correctamente; al subir un
    Excel privado local muestra los controles `Tipo de concepto fiscal ARCA
    obligatorio`, `Descripcion facturada obligatoria`, las opciones de
    descripcion desde archivo o fija, y la columna `Descripcion facturada` en la
    grilla previa a emision.

### Preparacion produccion 2026-05-04

- Se separo Docker local de Docker produccion.
- Se adopto PostgreSQL como base recomendada para operacion real.
- Se agregaron constraints de integridad para numeracion e idempotencia de lotes.
- Se agregó worker de lotes persistente para procesar `en_cola`; desde
  2026-06-12, los lotes `procesando` vencidos ya no se reemiten
  automáticamente y pasan a reconciliación si no pueden cerrarse solo con
  comprobantes locales ya autorizados; los grupos `validado` remanentes quedan
  marcados como `requiere_reconciliacion`.
- Se endurecio la validacion de IVA en Excel.
- Se ampliaron limites default de lotes a `20000` filas y `5000` comprobantes.
- Se agrego el comando `python -m app.scripts.create_admin_user` para crear o
  promover un usuario propietario/administrador en la base configurada.
- Se ajusto la UI para hablar de `Emisor activo` / `Emisores` y se agrego
  alta de nuevos emisores desde la pantalla fiscal.
- El alta de emisores permite subir una constancia de inscripcion ARCA en PDF
  para precompletar los campos fiscales antes de guardar. Desde 2026-05-10
  tambien acepta constancias de opcion de Monotributo y constancias de
  inscripción de persona física con layout distinto al societario.
- Se corrigio el listado/alta de puntos de venta para que usuarios admin operen
  solo sobre el emisor activo seleccionado.
- Se corrigio certificados para que usuarios admin solo vean, creen y verifiquen
  certificados del emisor activo seleccionado.
- El listado de certificados expone `Probar conexion` por certificado para
  validar el certificado productivo contra ARCA antes de emitir comprobantes
  reales.
- El wizard de certificados ahora agrega un paso previo a la verificacion para
  confirmar la autorizacion del servicio `wsfe` en ARCA. En produccion se hace
  desde `Administrador de Relaciones de Clave Fiscal`; sin esto ARCA devuelve
  "Computador no autorizado a acceder al servicio".
- El certificado productivo del emisor real privado quedo probado desde la UI
  con resultado `Conexion exitosa con ARCA`.
- El backend local se reinicio en `ARCA_ENV=produccion` para continuar con la
  prueba real. La sincronizacion productiva de puntos de venta devolvio `6`,
  `8`, `10`, `12`, `13` y `14` habilitados; `7` y `9` vinieron bloqueados y no
  se importaron.
- Se agrego transporte SOAP con TLS `SECLEVEL=1` para endpoints legacy de ARCA
  que en produccion pueden fallar con `DH_KEY_TOO_SMALL`.
- Se agrego importacion de constancia PDF de puntos de venta ARCA. La constancia
  privada importo los 14 puntos con sistema, domicilio y nombre
  fantasia; FactuFlow distingue usables Web Services de Factuweb, Comprobantes
  en Linea y Controlador Fiscal, e indica bloqueados.
- La emision masiva ahora toma el receptor desde el Excel sin exigir cliente
  precargado. Para consumidor final en comprobantes B/C de importe menor a
  `$10.000.000`, acepta documento y razon social vacios, normaliza a
  `A CONSUMIDOR FINAL`, tipo documento `99` y numero `0`, y no crea un cliente
  persistente.
- Los comprobantes guardan snapshot fiscal del receptor
  (`receptor_tipo_documento`, `receptor_numero_documento`,
  `receptor_razon_social`, `receptor_condicion_iva`, `receptor_domicilio`) para
  que PDFs, listados y reportes no dependan de editar un cliente luego de emitir.
- La base SQLite local privada fue ajustada manualmente por ser legacy; se dejo
  backup local ignorado por Git y `alembic_version` quedo en `e5f6a7b8c9d0`.

### QA homologacion 2026-04-10

- Se completo la QA manual de las pantallas pendientes.
- Se emitio un comprobante individual real desde la UI.
- Se emitio un lote real desde la UI.
- Se corrigieron bugs reales de integracion ARCA detectados durante la QA.
- Se reemplazaron placeholders visibles del dashboard y de `Mi Empresa`.
- Se dejaron verdes nuevamente los tests backend y frontend.

## Resultados reales de homologacion

### Smoke previo documentado (2026-03-09)

- Emision individual
  - Punto de venta: `5`
  - Tipo: `Factura B`
  - Numero: `1`
  - CAE: registrado en evidencia local privada
  - Vencimiento CAE: `2026-03-19`
- Emision masiva
  - Grupo `SMOKE-LOTE-001`
    - Numero: `2`
    - CAE: registrado en evidencia local privada
  - Grupo `SMOKE-LOTE-002`
    - Numero: `3`
    - CAE: registrado en evidencia local privada

### QA real ejecutada hoy (2026-04-10)

- Emision individual desde UI
  - Punto de venta: `5`
  - Tipo: `Factura B`
  - Numero: `4`
  - CAE: registrado en evidencia local privada
  - Vencimiento CAE: `2026-04-19`
- Emision masiva desde UI
  - Grupo `QA-LOTE-20260410-001`
    - Numero: `5`
    - CAE: registrado en evidencia local privada
  - Grupo `QA-LOTE-20260410-002`
    - Numero: `6`
    - CAE: registrado en evidencia local privada

## QA manual historica cerrada

Este bloque conserva recorridos previos a la operacion productiva real actual;
no define el punto vigente de reanudacion.

Quedo validado manualmente:

- Dashboard con metricas vivas:
  - `Total Clientes = 7`
  - `Comprobantes del Mes = 3`
  - `Ultimo Comprobante = 0005-00000006`
  - `Estado Certificado = Valido`
- Comprobantes:
  - listado con comprobantes reales
  - detalle correcto
  - `Ver PDF`
  - `Descargar PDF`
- Nueva factura:
  - preview
  - emision real con CAE
- Emision masiva:
  - descarga de plantilla
  - validacion de Excel
  - confirmacion antes de emitir
  - emision real
  - descarga de archivo observado
- Emision masiva productiva preparatoria:
  - lote QA privado validado desde API/UI para emisor real privado
  - receptor `A CONSUMIDOR FINAL`, documento `0`
  - punto de venta `6`, total estimado `$1.210,00`
  - no se emitio comprobante real; quedo listo para emitir como prueba visual
- Clientes:
  - listado correcto
  - clientes autocreados por lote visibles
- Reportes:
  - ventas por periodo
  - IVA ventas
  - ranking de clientes
- Certificados:
  - listado y vigencia correctos
- Puntos de venta:
  - listado correcto
  - sincronizacion con ARCA corregida y validada
- Mi Empresa:
  - formulario operativo
  - guardado real contra API

## Bugs resueltos en esta sesion

- Resolucion de paths legacy de certificados:
  - la base podia guardar `certs/...` y el runtime concatenaba `CERTS_PATH` de forma incorrecta
  - se corrigio para aceptar path absoluto, filename simple y valores legacy
- `GET /api/comprobantes/proximo-numero/...`:
  - fallaba en UI porque el certificado no se resolvia bien
  - impacto: bloqueaba `Nueva factura`
  - estado: corregido
- `GET /api/arca/puntos-venta`:
  - usaba el CUIT del certificado en lugar del CUIT de la empresa activa
  - impacto: `Sincronizar con ARCA` devolvia `500`
  - estado: corregido y revalidado manualmente
- Validacion de puntos de venta durante emision:
  - interpretaba `Bloqueado=N` de ARCA como valor truthy y rechazaba puntos
    validos en produccion
  - impacto: lotes con puntos `6`, `10` o `13` podian fallar al emitir aunque
    `GET /api/arca/puntos-venta` los mostrara no bloqueados
  - estado: corregido y cubierto con tests unitarios
- Sincronizacion visual de puntos Web Services:
  - `Sincronizar con ARCA` creaba puntos nuevos solo con numero, sin marcarlos
    como Web Services
  - impacto: emisores privados mostraban puntos devueltos por ARCA como
    `Otro sistema` aunque ARCA los devolviera habilitados para WSFE
  - estado: corregido en frontend; una nueva sincronizacion actualiza registros
    existentes incompletos
- Armado de IVA para Factura C:
  - el request ARCA enviaba `Iva: { AlicIva: [...] }` con alicuota 0
  - impacto: ARCA rechazaba con `[10071] Para comprobantes tipo C el objeto IVA
    no debe informarse`
  - estado: corregido y cubierto con tests unitarios
- Reintento de lotes sin CAE emitido:
  - el bloqueo por archivo duplicado tambien impedia revalidar el mismo archivo
    despues de un fallo tecnico en ARCA sin comprobantes emitidos
  - impacto: habia que limpiar historial manualmente para volver a intentar
  - estado: corregido; conserva el lote previo y libera el hash solo si no hubo
    grupos emitidos
- Concurrencia en procesamiento de lotes:
  - durante la primera prueba productiva quedaron procesos backend viejos y se
    disparo procesamiento concurrente del lote
  - impacto: se autorizaron comprobantes adicionales reales antes de que el lote
    terminara de reflejar el resumen correcto
  - estado: se agrego toma atomica de lote; si ya esta procesando o procesado,
    una segunda ejecución queda bloqueada
- Estrategia de schema local:
  - `run-local.ps1` ahora ejecuta `alembic upgrade head` antes de levantar
    `uvicorn`
  - `backend/app/main.py` ya no ejecuta `create_all` en `development`; queda
    limitado a `test`/`testing`
  - estado: Alembic queda como camino normal de schema para arranque local y
    productivo
- Nomenclatura ARCA:
  - se corrigieron textos visibles y docstrings/comentarios conceptuales que
    todavia usaban AFIP
  - en la app actual quedan menciones solo como URLs oficiales heredadas,
    variables legacy `AFIP_*` o carpeta legacy `backend/app/afip/`
- Versionado:
  - la version de producto visible queda en `APP_VERSION` /
    `settings.app_version`: `0.2.0-mvp`
  - el frontend npm queda sincronizado a version tecnica semver `0.2.0`
  - la UI mantiene `FactuFlow v0.2.0-mvp` como version de producto
- Dashboard:
  - `Comprobantes del Mes`, `Ultimo Comprobante` y `Estado Certificado` estaban hardcodeados
  - estado: corregido
- `Mi Empresa`:
  - era una pantalla placeholder
  - estado: reemplazada por formulario operativo conectado a la API
- E2E frontend:
  - el setup de Playwright quedó recuperado para auditorías locales de
    escritorio: `npm run test:e2e` levanta Vite en puerto dedicado, ejecuta
    Chromium y corta el servidor al finalizar
  - la matriz completa de navegadores/mobile queda opt-in con
    `E2E_FULL_BROWSER_MATRIX=1`, porque la sección de plantillas y emisión
    masiva está pensada para uso en PC

## Verificacion automatizada vigente

- Backend:
  - `pytest tests -q` OK, 303 tests
  - `ruff check app tests` OK
  - `black --check app tests` OK
  - `alembic heads` OK, head `e2f3a4b5c6d7`
- Frontend:
  - `npm run lint:check` OK sin errores ni warnings
  - `npm run type-check` OK
  - `npm run build` OK
  - `npm run test:unit` OK, 61 tests
  - `npm run test:e2e -- --reporter=list` OK, 31 tests en Chromium desktop,
    con servidor Vite dedicado en `127.0.0.1:18080`

## Riesgos / pendientes inmediatos

- Revision Clawpatch 2026-05-16/17: los hallazgos reparados quedan resumidos en
  `docs/project/audits/clawpatch/2026-05-16-reparaciones.md`. Backend,
  frontend y repo quedan con `openFindings=0`.
- La base local privada sigue siendo evidencia legacy
  ajustada manualmente; para nuevas instalaciones y operacion real, el camino
  canonico de schema es Alembic.
- La documentacion anterior al 2026-05-22 mezclaba estado pre-piloto con
  evidencia productiva posterior. El corte `0.2.0-mvp` queda resumido en
  `CHANGELOG.md`; los documentos vivos son la fuente vigente.
- Para cada nueva emision productiva, seguir validando explicitamente punto de
  venta, fecha fiscal, concepto fiscal ARCA, descripcion facturada, totales y
  confirmacion irreversible antes de solicitar CAE.
- La evidencia privada de lotes productivos, CAEs, comprobantes, Excels y logs
  no debe versionarse. La documentacion publica debe registrar solo resúmenes
  operativos sanitizados.
- No existe todavia descarga masiva de PDFs en ZIP.
- La descarga masiva de PDFs, archivos observados, ZIPs y otros artefactos
  descargables debe diseñarse para VPS con almacenamiento mínimo: generación
  bajo demanda, descarga a la PC del usuario y limpieza posterior del servidor.
- El gestor de almacenamiento administrativo ya existe para diagnóstico y
  limpieza manual de artefactos no vitales. Queda pendiente validarlo
  visualmente sobre una instalación real de VPS con datos de prueba controlados.
- Los emisores existentes deben completar `Ingresos Brutos` si quieren que ese
  dato figure informado en PDFs nuevos; mientras tanto el PDF lo muestra como
  `No informado`.
- Falta formalizar operación productiva robusta:
  - guardar la clave real de recuperación del backup cifrado en un gestor de
    contraseñas seguro, fuera de Git y fuera del VPS
  - automatizar backups cifrados con validación, frecuencia, retención y
    destino externo definidos
  - documentar y ensayar el runbook completo de recuperación a un VPS nuevo
  - observabilidad operativa estándar según
    `docs/agents/operational-observability.md`
  - validación de la política de almacenamiento mínimo y limpieza de artefactos
    descargables en VPS usando el gestor administrativo
  - trazabilidad visible de lotes productivos y reintentos
  - pantalla `Estado del sistema` dentro del frontend con lenguaje simple
- Para nuevas instalaciones productivas usar `docker-compose.prod.yml`,
  PostgreSQL y `.env.production` basado en `.env.production.example`.

## Estado de salida

- Homologacion: lista y validada.
- Producto local: operativo para desarrollo/QA con launcher Windows y flujo
  tecnico alternativo.
- Despliegue: la migración local a PostgreSQL fue ensayada correctamente, la
  primera instalación privada en VPS quedó publicada por HTTPS y el cierre
  operativo inicial quedó documentado.
- Produccion real: ya fue utilizada con certificado productivo, autorizacion
  `wsfe`, puntos Web Services y comprobantes autorizados. La auditoría
  post-emisión de solo lectura no detectó desfases fiscales bloqueantes. La
  siguiente etapa es consolidar operación post-piloto y corregir detalles
  funcionales/UX observados en uso real.

## Punto exacto para retomar

Para continuar desde el estado actual:

1. Mantener alineada la documentación viva con el estado post-piloto productivo
   y conservar la historia como evidencia fechada sin datos privados.
2. Guardar la clave real del backup cifrado en un gestor de contraseñas seguro,
   porque la copia DPAPI local no es portable a otra PC o usuario.
3. Convertir los detalles observados durante el uso real en un backlog
   priorizado, separando riesgos fiscales, UX, PDF, reportes y soporte.
4. Validar la política de almacenamiento mínimo para VPS usando el gestor
   administrativo: qué queda persistido, qué se genera bajo demanda y cómo se
   limpian PDFs, ZIPs, observados y temporales no vitales.
5. Ejecutar QA visual del gestor de almacenamiento con uso total, desglose por
   emisor y tipo de dato, alertas simples, resguardo ZIP y limpieza segura de
   artefactos no vitales.
6. Implementar observabilidad operativa estándar: pantalla de estado del
   sistema, trazabilidad/reconciliación de lotes, logs útiles para soporte,
   mensajes simples y runbook de diagnóstico.
7. Diseñar la automatización futura de backups cifrados con validación y
   retención, pero no implementarla todavía hasta definir política operativa.
8. Priorizar mejoras operativas visibles restantes: descarga masiva de PDFs sin
   persistencia permanente en el servidor y ampliar E2E donde aporte evidencia
   real de flujos críticos.
9. Para cada nuevo lote productivo, validar formato, punto de venta, concepto
   fiscal ARCA, descripción facturada, fechas fiscales permitidas, totales y
   confirmación final irreversible antes de emitir.
