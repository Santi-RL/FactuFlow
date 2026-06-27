# Changelog

Este archivo es la fuente principal para entender de donde viene FactuFlow y
hacia donde avanza.

Reglas vigentes desde 2026-05-22:

- El estado operativo actual se consulta en `README.md`,
  `docs/agents/current-status.md` y `ROADMAP.md`.
- El historial versionado se resume aca. Evitar crear nuevos snapshots largos
  de documentacion si el cambio puede quedar explicado en este changelog, el
  roadmap y la documentacion viva.
- Los documentos antiguos bajo `docs/project/**` son material historico. No
  deben usarse como fuente de verdad actual si contradicen la documentacion
  viva.
- No registrar CUITs, CAEs, nombres reales, Excels, PDFs, logs ni evidencia
  privada en este archivo.

## [Unreleased]

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

Linea base actual del proyecto. Este corte reemplaza las referencias antiguas a
versiones previas como fuente de estado operativo.

### Estado del corte

- Version visible del producto: `0.2.0-mvp`.
- Version tecnica npm/backend: `0.2.0` cuando la herramienta exige semver.
- MVP validado en homologacion y usado en produccion real controlada.
- La evidencia productiva detallada queda en bases, logs y archivos privados
  ignorados por Git.
- La documentacion viva queda alineada con estado post-piloto productivo.

### Decisiones de producto vigentes

- FactuFlow es una herramienta para facturar.
- No se planifica incorporar cuentas corrientes, stock ni catalogos.
- Las integraciones externas quedan como evolucion futura, enfocadas en entrada
  y salida de datos mediante la API, despues de estabilizar facturacion.
- El modelo operativo es multiemisor con un emisor activo explicito por vez,
  pensado para contadores independientes y estudios chicos.
- No se avanza por ahora hacia plataforma multiempresa compleja con permisos
  finos, reportes globales u operacion simultanea entre emisores.
- El uso local con launcher queda como entorno implementado para desarrollo/QA.
- El siguiente hito de despliegue es VPS con Docker produccion y PostgreSQL.
- La distribucion comercial instalable queda para despues de estabilizar VPS.
- La observabilidad operativa estandar es requisito antes de ampliar produccion:
  trazabilidad, estado del sistema, logs utiles, backups y mensajes simples para
  usuarios no tecnicos.

### Capacidades consolidadas

- Backend FastAPI con auth, empresas, clientes, certificados, puntos de venta,
  comprobantes, lotes, PDFs y reportes.
- Frontend Vue con dashboard, clientes, comprobantes, emision masiva, reportes,
  certificados, puntos de venta y emisores.
- Emision individual y masiva con ARCA WSAA/WSFEv1.
- Confirmacion fiscal explicita antes de solicitar CAE.
- Fecha de emision explicita; no se usa la fecha del dia como default fiscal.
- Formatos configurables de importacion y perfiles de carga por emisor.
- Lotes con validacion previa, estados persistidos y worker para procesos
  largos.
- Selector de emisor activo y scoping por emisor en operaciones sensibles.
- PDFs bajo demanda y reportes basicos.
- Launcher local Windows con icono en tray para desarrollo/QA.

### Seguridad y operacion

- Clientes, certificados, puntos de venta, comprobantes, lotes, PDFs, reportes,
  perfiles y formatos deben quedar aislados por emisor activo.
- Para produccion usar PostgreSQL y `docker-compose.prod.yml`.
- Queda pendiente resolver si los certificados productivos locales se migran al
  VPS o si conviene generar certificados nuevos para el servidor.
- Backups/restauracion, trazabilidad visible, logs de soporte y pantalla de
  estado del sistema son prioridad post-piloto.

### Proximo tramo

- Instalar y validar FactuFlow en VPS con Docker produccion y PostgreSQL.
- Resolver la politica tecnica de certificados ARCA en VPS.
- Implementar observabilidad operativa estandar.
- Formalizar backup/restauracion de base, certificados, configuracion y logs.
- Agregar descarga masiva de PDFs en ZIP.
- Recuperar E2E como evidencia confiable.
- Definir politica de releases posterior a `0.2.0-mvp`.

## Historial resumido anterior al corte

### Base inicial

- Se construyo la base tecnica con FastAPI, Vue, Pinia, Router, SQLAlchemy,
  Pydantic, autenticacion, setup inicial y estructura modular.
- Se incorporaron empresas, clientes, puntos de venta, certificados,
  comprobantes, PDFs y reportes.
- Se documento la primera vision de FactuFlow como sistema de facturacion
  electronica ARCA para Argentina.

### Integracion ARCA y comprobantes

- Se implemento WSAA y WSFEv1.
- Se agregaron certificados por ambiente, wizard de carga/verificacion y
  validaciones de autorizacion `wsfe`.
- Se completo emision individual, vista previa, guardado de comprobantes,
  consulta posterior y generacion de PDFs.
- Se corrigieron reglas fiscales criticas: fecha fiscal explicita, concepto
  fiscal ARCA explicito, punto de venta usable y confirmacion irreversible.

### Emision masiva

- Se implemento emision por Excel con agrupacion por `comprobante_ref`.
- Se agregaron validaciones de totales, IVA, consumidor final, puntos de venta
  y conceptos fiscales.
- Se agregaron formatos de importacion configurables y perfiles por emisor para
  facilitar archivos externos.
- Se incorporaron estados de lotes, worker para procesos largos, idempotencia y
  manejo de casos con incertidumbre post-ARCA.

### Produccion real y endurecimiento

- Se verifico homologacion y luego se opero produccion real controlada.
- Se ajusto numeracion, locking, idempotencia, reconciliacion y scoping por
  emisor.
- Se agrego launcher local Windows para desarrollo/QA y mejores mensajes cuando
  el backend local no esta disponible.
- Se reforzo la seguridad documental: no versionar datos privados, CAEs,
  CUITs, clientes, Excels, PDFs, logs ni evidencia local.

### Documentacion

- Se separo documentacion viva de documentos historicos.
- `README.md`, `ROADMAP.md`, `docs/agents/current-status.md`,
  `docs/agents/manual-qa.md`, `docs/user-guide/README.md` y este changelog
  pasan a ser la base para retomar el proyecto.
- Los snapshots antiguos conservados en `docs/project/**` quedan solo como
  referencia historica y pueden resumirse o eliminarse en futuras limpiezas si
  su contenido ya esta cubierto por este changelog y la documentacion viva.
