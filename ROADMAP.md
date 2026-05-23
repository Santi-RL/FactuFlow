# Roadmap de FactuFlow

Ultima actualizacion: 2026-05-22

Este roadmap vuelve a cumplir dos funciones:
- marcar el estado real del producto y del MVP
- conservar el norte de largo plazo para una plataforma robusta, desplegable y utilizable por muchas empresas

## Como leer este archivo

- `[x]` Hecho
- `[~]` En curso
- `[ ]` Pendiente

## Vision del producto

FactuFlow no apunta a quedar como una utilidad puntual de facturacion. La vision a largo plazo es una plataforma de facturacion electronica ARCA:

- simple para personal administrativo no tecnico
- robusta en operacion diaria
- preparada para que contadores independientes y estudios chicos operen varios
  emisores con seguridad
- auditable, mantenible y documentada
- con capacidad de escalar desde uso controlado hasta adopcion por multiples equipos o clientes

## Objetivo actual

Consolidar el MVP despues del uso productivo real controlado, centrado en:
- emision individual y masiva por Excel
- formatos de importacion configurables para archivos externos
- uso administrativo no tecnico
- homologacion real y operacion productiva inicial con ARCA
- multiemisor con un emisor activo explicito por vez
- robustez operativa: backups, trazabilidad, observabilidad y soporte

## Decisiones de producto vigentes

- FactuFlow es una herramienta para facturar. El alcance central es
  facturacion electronica ARCA, emision individual, emision masiva, PDFs,
  reportes operativos y soporte administrativo del flujo de facturacion.
- No esta planificado incorporar manejo de cuentas corrientes, stock ni
  catalogos como modulos del producto.
- Las integraciones externas quedan para una etapa posterior, cuando la
  facturacion este madura y productiva estable. Esas integraciones deben estar
  enfocadas en obtener datos desde otras fuentes o aplicaciones, o enviar datos
  hacia ellas, usando la API existente o su evolucion.
- El modelo multiemisor vigente es el de una empresa/emisor activo por vez. Un
  contador independiente o estudio chico puede administrar varios CUITs, pero
  toda operacion debe quedar scopiada al emisor activo seleccionado.
- No se avanza por ahora hacia una plataforma multiempresa compleja con
  administracion central completa, permisos finos por organizacion, reportes
  globales consolidados u operacion simultanea entre emisores.
- La seguridad multiemisor es prioritaria: clientes, certificados, puntos de
  venta, comprobantes, lotes, PDFs, reportes, perfiles de carga y formatos de
  importacion no deben mezclarse entre emisores.
- El despliegue local con launcher ya existe y esta probado hasta nivel
  desarrollo/QA. El siguiente hito de despliegue es instalar FactuFlow en un VPS
  con `docker-compose.prod.yml` y PostgreSQL.
- La distribucion comercial instalable queda para una etapa posterior, cuando
  el producto sea estable y repetible funcionando en VPS.
- La observabilidad operativa estandar es obligatoria antes de ampliar el uso
  productivo. Debe permitir diagnosticar emisiones, lotes, errores ARCA,
  reconciliaciones, estado del sistema y backups con lenguaje simple para
  usuarios no tecnicos. No requiere todavia monitoreo complejo con herramientas
  externas.

## Foto actual del proyecto

### Producto y negocio
- [x] Objetivo principal redefinido: emision masiva y UX administrativa simple
- [x] Modelo multiemisor definido: varios CUITs por usuario, un emisor activo
  explicito por vez
- [~] Criterios UX no tecnicos parcialmente implementados
- [x] Login informa claramente cuando el servidor local no esta disponible
- [x] Produccion real inicial utilizada con comprobantes autorizados
- [ ] Refuerzo continuo de aislamiento entre emisores antes de ampliar volumen
  o uso productivo

### Backend
- [x] FastAPI operativo con auth, clientes, empresa, puntos de venta, certificados, comprobantes, PDF, lotes y reportes
- [x] Integracion WSAA + WSFEv1 operativa en homologacion y produccion inicial
- [x] Emision individual real validada con CAE
- [x] Emision masiva por Excel implementada
- [x] Formatos de importacion configurables para emision masiva con alcance global y por emisor
- [x] Perfiles de carga masiva por emisor para precargar formato, punto de
  venta, concepto, descripcion y fechas visibles antes de validar
- [x] Perfiles de carga masiva no permiten guardar fecha actual como regla de
  emision fiscal
- [x] Emision masiva permite consumidor final desde Excel sin cliente precargado cuando la normativa no exige identificar receptor
- [x] Fecha de emision explicita; no se asume fecha del dia actual al emitir
- [x] Confirmacion final obligatoria de fecha fiscal antes de solicitar CAE
- [x] Procesamiento de lotes exige token exacto de confirmacion fiscal con
  fechas y puntos de venta validados, no un boolean generico
- [x] Emision valida que punto de venta y cliente opcional pertenezcan al
  emisor activo antes de solicitar CAE
- [x] Nueva factura ofrece solo puntos de venta usables por FactuFlow y la API
  rechaza numeracion para puntos no Web Services con error de negocio
- [x] Uploads de lotes limitados por `BATCH_MAX_UPLOAD_BYTES` y XLSX
  malformados rechazados antes de validar
- [x] Concepto fiscal ARCA explicito; no se asume productos o servicios por defecto
- [~] Descripcion/concepto facturado del item documentado como dato separado
  del concepto fiscal ARCA; debe venir del archivo o de un valor fijo confirmado
  para todo el lote, sin defaults ocultos
- [x] Numeracion ARCA adelantada y fallos post-CAE quedan como
  `requiere_reconciliacion`, sin persistir respuestas no aprobadas como
  comprobantes emitidos
- [x] Sincronizacion manual de puntos de venta ARCA validada desde UI; los
  puntos devueltos por WSFE se crean o actualizan como Web Services usables
- [x] Validacion de puntos de venta en emision normaliza `Bloqueado=N`/`S` de ARCA
- [x] Factura C no informa objeto `Iva` en WSFE y bloquea items con IVA distinto de 0
- [x] UI de puntos de venta valida certificado activo del ambiente ARCA actual
  antes de sincronizar WSFE
- [x] Emisor activo consistente por pestaña y API con rechazo de conflictos
  entre `X-Empresa-Id` y query legacy `empresa_id`
- [~] Endurecimiento de seguridad multiemisor para evitar mezcla de clientes,
  certificados, puntos de venta, comprobantes, lotes, PDFs, reportes, perfiles
  y formatos entre emisores
- [x] Excel observado de lotes escapa valores con forma de formula
- [x] Notas de credito/debito informan comprobantes asociados en WSFE
  (`CbtesAsoc`) cuando corresponde
- [~] Alineacion limpia entre base legacy y Alembic
- [ ] Arquitectura de jobs robusta para procesos largos

### Frontend
- [x] Vue + Pinia + Router operativos
- [x] Dashboard, clientes, comprobantes, emision masiva, reportes, certificados, puntos de venta y empresa operativos
- [x] Selector de emisor activo para operar varios CUITs desde un usuario
- [x] Secciones principales scopiadas por emisor activo y verificadas al
  cambiar el selector
- [x] Vistas sensibles descartan respuestas asincronicas viejas al cambiar el
  emisor activo, incluyendo reportes, certificados, puntos de venta y
  numeracion de nueva factura
- [x] Autodeteccion asistida de formato al subir Excel externo para emision masiva
- [x] Nueva factura exige CUIT para Factura A y Notas A, y el refresco de lista
  posterior a CAE es no bloqueante
- [x] QA manual guiada de flujos reales
- [ ] Operaciones masivas de PDF desde listado

### Operacion y plataforma
- [x] Arranque local simple con `run-local.ps1`
- [x] Launcher local Windows manual con icono en tray para desarrollo/QA
- [x] Perfiles Docker separados para local y produccion
- [x] PostgreSQL definido como base recomendada para operacion real
- [x] Comando administrativo para crear/promover usuario propietario
- [~] Instalacion en VPS con Docker produccion y PostgreSQL como proximo hito
- [ ] CI/CD completo y alineado al estado real del repo
- [~] Observabilidad operativa estandar definida como requisito post-piloto
- [ ] Observabilidad, backups y politicas operativas implementadas y probadas

## Fase 0 - Fundacion y base tecnica

Objetivo: tener un repo mantenible, ejecutable y documentado.

- [x] Repositorio, estructura base y guias para agentes
- [x] Backend y frontend levantables en local
- [x] Acceso local manual `FactuFlow Local.vbs` sin consola visible, con estado
  de backend, frontend y base de datos en tray
- [x] `.env.example` y configuracion base
- [x] Documentacion tecnica inicial
- [~] Docker y compose alineados al estado real
- [ ] Pipeline CI basico confiable para backend y frontend
- [x] Corte versionado `0.2.0-mvp` y changelog como historial principal

## Fase 1 - Core funcional de negocio

Objetivo: poder operar una empresa y emitir comprobantes reales.

### Dominio principal
- [x] Empresa
- [x] Usuario y autenticacion
- [x] Clientes
- [x] Puntos de venta
- [x] Certificados
- [x] Comprobantes e items

### API y backend
- [x] Endpoints base para auth, clientes, empresa y comprobantes
- [x] Seguridad basica por empresa
- [x] Generacion de PDF bajo demanda
- [x] PDF de comprobante con formato administrativo profesional, ubicacion de
  elementos principales alineada a la factura oficial ARCA y QR ARCA testeado
  por payload decodificable
- [x] Reportes basicos de consulta
- [~] Consistencia documental completa de endpoints y contratos

### UX
- [x] Login
- [x] Dashboard
- [x] Formularios principales
- [~] Refinamiento de mensajes y ayudas contextuales
- [ ] Estados vacios y recuperacion de errores totalmente pulidos

## Fase 2 - Integracion ARCA real

Objetivo: dejar la emision validada contra servicios reales.

### WSAA
- [x] Generacion de TRA
- [x] Firma y login CMS
- [x] Obtencion de Token y Sign
- [x] Cache persistente de tickets
- [ ] Politica de invalidacion/rotacion mas robusta

### WSFEv1
- [x] `FECAESolicitar`
- [x] `FECompUltimoAutorizado`
- [x] `FECompConsultar` util para verificacion
- [x] Validacion de numeracion y punto de venta en emision
- [x] Mapeo de `CondicionIVAReceptorId`
- [x] Validacion local de ventana ARCA para fecha de emision antes de emitir
- [~] Manejo fino de edge cases homologacion vs produccion

### Homologacion
- [x] Certificado homologacion emitido por WSASS
- [x] Autorizacion `wsfe` creada para CUIT representado
- [x] Smoke real individual
- [x] Smoke real masivo
- [x] QA manual completa desde UI
- [ ] Smoke repetible documentado como procedimiento de soporte

### Produccion
- [x] Piloto productivo real ejecutado con comprobantes autorizados
- [x] Certificado productivo cargado y prueba WSAA/ARCA exitosa
- [~] Certificados y proceso de produccion
- [x] Certificados ARCA con paths gestionados dentro de `CERTS_PATH`, claves
  nuevas cifradas y un unico certificado activo por emisor/ambiente
- [~] Checklist operativo post-piloto: fecha fiscal, punto de venta, backup,
  logs, restauracion y evidencia sanitaria
- [ ] Validacion sistematica de diferencias operativas entre homologacion y produccion

## Fase 3 - Emision masiva como nucleo del producto

Objetivo: que FactuFlow sea realmente util para operaciones administrativas de volumen.

### Lotes
- [x] Entidades de lote, grupo y filas
- [x] Plantilla Excel fija
- [x] Formatos de importacion configurables por encabezado, columna o constante
- [x] Formato global para extractos bancarios con columnas `Fecha`, `Créditos`, `Leyendas Adicionales1`, `Leyendas Adicionales2` y `Pto Vta`
- [x] Formato particular local para emisor Responsable Inscripto privado
  (`Factura B IVA 21%`) con neto
  gravado como precio del item, total como referencia y consumidor final sin
  documento cuando corresponde
- [x] Formato particular local para emisor privado con Factura B IVA 21%,
  vinculado al perfil predeterminado del emisor, con `Imp. Neto Gravado` como
  neto del item e `Imp. Total` solo como control de consistencia
- [x] Validacion de consistencia entre total informado por archivo externo y
  total calculado desde items e IVA antes de permitir emision
- [x] Politica explicita de fecha de emision por lote: desde archivo o fecha fija confirmada
- [x] Politica explicita de concepto fiscal ARCA por lote: productos, servicios
  o definido por archivo
- [x] Politica explicita de descripcion facturada del item por lote: desde
  archivo o valor fijo para todo el lote, independiente del concepto fiscal ARCA
- [x] Perfiles de carga masiva por emisor, con predeterminado, punto de venta y
  reglas relativas de fechas visibles, sin materializar fecha fiscal en emision
  masiva sin una base explicita del usuario
- [x] Agrupacion por `comprobante_ref`
- [x] Prevalidacion por fila y por comprobante
- [x] Reintento seguro del mismo archivo cuando el lote previo no emitio CAE
- [x] Toma atomica del lote antes de emitir para evitar procesamiento concurrente
- [x] Fallos post-CAE quedan como `requiere_reconciliacion` y no habilitan
  reintentos automaticos
- [x] Confirmacion fiscal final de lotes usa token exacto derivado de los grupos
  validados: fechas y puntos de venta concretos
- [x] Archivos XLSX malformados o por encima de `BATCH_MAX_UPLOAD_BYTES` quedan
  rechazados antes de crear o validar lotes
- [x] Snapshot fiscal del receptor en comprobantes
- [x] Persistencia de fechas de servicio y vencimiento de pago en comprobantes
  nuevos y backfill desde payloads historicos de lotes para reflejarlas en el
  PDF
- [x] Clientes precargados opcionales para lotes masivos
- [x] Emision de lotes chicos desde UI observable por background/polling
- [x] Ejecucion asincronica para lotes grandes
- [x] Worker evita reencolar lotes activos y solo retoma `procesando` cuando
  estan stale

### UX de lotes
- [x] Wizard de emision masiva
- [x] Preseleccion del formato sugerido con alta confianza antes de validar
  archivos externos
- [x] Confirmacion de fecha de emision y fechas de servicio antes de validar
- [x] Modal final de advertencia antes de emitir: confirma fecha fiscal y avisa
  que luego no se podran emitir comprobantes con fecha anterior para ese mismo
  punto de venta
- [x] Confirmacion de concepto fiscal ARCA antes de validar; si viene del archivo, todas las filas deben indicar `Producto` o `Servicio`
- [x] Confirmacion de descripcion/concepto facturado del item antes de validar:
  desde archivo o texto fijo para todo el lote
- [x] Selector de perfil de carga masiva en emision masiva, con aplicacion
  automatica cuando el emisor tiene uno solo o uno predeterminado
- [x] Selector de punto de venta en perfiles y emision masiva: usar el punto del
  archivo o fijar uno usable del emisor activo
- [x] Si el usuario modifica una configuracion precargada por perfil de carga
  masiva, el lote se valida sin snapshot de perfil aplicado
- [x] Separacion clara entre validar lote y emitir comprobantes validos
- [x] Resumen previo a emision con neto, IVA 21%, IVA 10,5% y total de
  comprobantes listos para emitir
- [x] Mensajes basicos de validacion
- [~] Pulido de ayudas, tooltips y lenguaje administrativo
- [x] Descarga de archivo observado validada manualmente
- [x] PDF de comprobante rediseñado con ubicaciones principales similares a la
  factura oficial ARCA, sin copiar identidad visual oficial, con datos
  fiscales, CAE, QR, detalle y totales organizados profesionalmente
- [x] QA manual local del formato global de extracto bancario sin emitir
- [x] QA visual local del selector obligatorio de fechas fiscales en lotes
- [x] QA visual local de descripcion/concepto facturado del item independiente
  del concepto fiscal ARCA, sin defaults ocultos
- [x] QA visual local de perfiles de carga masiva: crear, editar, eliminar,
  predeterminar, autoaplicar, modificar antes de validar y verificar modal final
  de fecha fiscal sin emitir
- [x] Preparacion y validacion segura sin emision de lote de Nota de Credito C
  para anular duplicados productivos
- [x] Emision y verificacion por consulta ARCA de 19 Nota de Credito C para
  anular duplicados productivos
- [x] Preparacion y validacion segura sin emision de 1113 Nota de Credito B
  para corregir Factura B de un emisor privado emitidas con total usado como neto
- [~] QA manual especifica de formatos particulares por emisor
- [ ] Descarga de archivo observado con errores mas amigable
- [x] Progreso real de lotes con barra, timer, ETA, emitidos, fallidos y pendientes

### Operacion masiva posterior a la emision
- [ ] Descarga masiva de PDFs en ZIP
- [ ] Seleccion multiple en listado de comprobantes
- [ ] Preparacion asincronica de PDFs para lotes grandes
- [ ] Trazabilidad de tareas masivas iniciadas por usuario

## Fase 4 - UX administrativa no tecnica

Objetivo: reducir al minimo la necesidad de soporte tecnico para operar.

- [x] Uso de espanol claro en pantallas core
- [x] Eliminacion de `alert()` y `confirm()` nativos en flujos principales
- [~] Mensajes accionables en errores de negocio
- [x] Mensaje claro en login cuando el backend local no responde
- [~] Ayudas contextuales en pantallas sensibles
- [ ] Pantalla de estado del sistema dentro del frontend
- [ ] Integracion formal entre launcher local y UI web
- [ ] Tooltips y microcopy sistematizados en toda la app
- [ ] Checklists previos a la emision
- [ ] Vistas vacias guiadas
- [ ] Confirmaciones claras para acciones sensibles
- [ ] Revision completa de accesibilidad y legibilidad

## Fase 5 - Datos, migraciones y estabilidad

Objetivo: que el proyecto soporte evolucion sin deuda estructural peligrosa.

### Base de datos
- [x] Modelos principales definidos
- [x] Migracion inicial de esquema creada
- [x] Modelos versionados de formatos de importacion y trazabilidad del mapeo usado por lote
- [~] Estrategia de convivencia con DB local legacy
- [ ] Stamping/migracion limpia de instalaciones existentes
- [ ] Politica clara de seeds y datos de desarrollo

### Calidad y testing
- [x] Suite backend activa
- [~] E2E frontend con Playwright
- [x] Smoke real de homologacion ejecutado manualmente
- [x] QA manual funcional cerrada
- [x] Script de lint frontend no destructivo `npm run lint:check`
- [x] Reparaciones Clawpatch 2026-05-16/17 cerradas con
  backend/frontend/repo en `openFindings=0`
- [x] Reportes IVA calculan notas de credito con signo negativo y el detalle de
  subdiario incluye gravado e IVA 27%
- [ ] Corregir setup E2E para que `npm run test:e2e` vuelva a ser evidencia
  confiable en auditorias
- [ ] Cobertura mas profunda sobre detalles de comprobantes, PDF y reportes
- [ ] Smoke automatizado de stack completo local

### Robustez
- [x] Jobs de lotes reanudables desde estado persistido en BD con ventana stale
- [x] Reintentos bloqueados cuando existe incertidumbre post-ARCA
- [ ] Reintentos controlados para otros procesos largos
- [~] Idempotencia mas visible para usuario final
- [ ] Auditoria de eventos operativos criticos

## Fase 6 - Multiemisor con emisor activo

Objetivo: permitir que contadores independientes o estudios chicos administren
varios emisores desde una misma instalacion, operando siempre un emisor activo
explicito por vez. No incluye, por ahora, administracion central compleja,
permisos finos por organizacion, reportes globales consolidados ni operacion
simultanea entre emisores.

- [x] Header `X-Empresa-Id` para admins
- [x] Selector de emisor activo en frontend
- [x] Alta basica de nuevos emisores desde UI admin
- [x] Configuracion de perfiles de carga masiva desde `Emisores > Carga masiva`,
  incluyendo punto de venta por archivo o punto fijo usable del emisor
- [x] Precarga de emisor desde constancia de inscripcion ARCA en PDF,
  constancia de inscripcion de persona fisica y constancia de opcion de
  Monotributo, con provincia validada contra catalogo argentino
- [x] Importacion de constancia ARCA de puntos de venta con domicilio y nombre fantasia
- [x] Re-scopeo de dashboard, clientes, comprobantes, emision masiva,
  reportes, certificados, puntos de venta y nueva factura por emisor activo
- [x] Scoping backend de emision contra punto de venta y cliente del emisor
  activo
- [~] Modelo multiemisor validado con mas de un emisor real de prueba
- [ ] Auditoria de aislamiento entre emisores en certificados, puntos de venta,
  clientes, comprobantes, lotes, PDFs, reportes, perfiles y formatos
- [ ] Tests de regresion multiemisor para operaciones criticas antes de ampliar
  volumen productivo
- [ ] Onboarding multiemisor mas claro para contadores y estudios chicos

## Fase 7 - Plataforma lista para despliegue serio

Objetivo: que FactuFlow pueda instalarse y operarse con menor riesgo tecnico.

### Contenedores y despliegue
- [x] Dockerfiles y compose existentes
- [x] `docker-compose.yml` para local/desarrollo
- [x] `docker-compose.prod.yml` para VPS/produccion con PostgreSQL
- [~] Instalacion real en VPS con `docker-compose.prod.yml`
- [~] Variables de entorno cerradas por ambiente
- [~] Guia de despliegue local y servidor
- [ ] Reverse proxy y TLS documentados

### Operacion
- [ ] Logs operativos con identificador de seguimiento por emisor, usuario,
  lote/comprobante, job y error local o ARCA
- [ ] Retencion de logs privados definida por entorno
- [ ] Healthchecks claros para backend, base, worker, ARCA y certificado del
  emisor activo
- [ ] Backup y restauracion de base y certificados
- [ ] Definir si los certificados productivos se migran desde local al VPS o si
  se generan certificados nuevos para el servidor
- [ ] Politica de manejo de secretos

### Diagnostico operativo simple
- [x] Decision de observabilidad operativa estandar documentada en
  `docs/agents/operational-observability.md`
- [ ] Pantalla `Estado del sistema` en la interfaz, con estados simples como
  `Correcto`, `Necesita atencion` y `No disponible`
- [ ] Trazabilidad visible de lotes, reintentos, estados parciales y
  reconciliaciones
- [ ] Mensajes de error con explicacion simple, impacto y proximo paso seguro
- [ ] Runbook de diagnostico para soporte y usuarios administrativos
- [ ] Metricas y alertas avanzadas, despues de estabilizar VPS

## Fase 8 - Distribucion, releases y adopcion

Objetivo: profesionalizar la entrega del producto.

### Releases
- [x] Changelog operativo consistente como fuente principal de historial
- [x] Corte actual `0.2.0-mvp` definido como linea base
- [x] Resumenes de fases antiguas consolidados en changelog para evitar
  snapshots obsoletos
- [~] Politica de versiones posteriores al MVP
- [ ] Paquetes o imagenes publicables
- [~] Notas de release por version desde el corte actual

### Distribucion
- [ ] Instalacion simplificada para terceros, posterior a estabilizar VPS
- [ ] Plantillas de configuracion por ambiente
- [ ] Demo controlada o entorno de evaluacion
- [ ] Procedimiento de upgrade entre versiones

### Soporte y adopcion
- [ ] Runbooks de soporte
- [ ] Manuales de troubleshooting para usuarios administrativos
- [ ] Manuales tecnicos para deploy y mantenimiento
- [ ] Politica de compatibilidad y migraciones

## Fase 9 - Evolucion del producto

Objetivo: ampliar valor mas alla del MVP.

- [x] Produccion ARCA inicial
- [~] Operacion productiva robusta y repetible
- [ ] Exportaciones de reportes
- [ ] Envio de comprobantes por email
- [ ] Integraciones externas de entrada/salida de datos via API, posteriores a
  la madurez productiva de facturacion
- [ ] Dashboard de operacion mas rico

## Prioridades inmediatas

1. Mantener documentacion viva alineada con el estado post-piloto productivo,
   separando evidencia privada de resumenes versionables.
2. Realizar la instalacion en VPS con Docker produccion y PostgreSQL.
3. Resolver la pregunta tecnica de certificados para VPS: migrar/copiar los
   certificados productivos locales existentes o generar certificados nuevos
   para el servidor.
4. Implementar observabilidad operativa estandar: trazabilidad clara, pantalla
   de estado del sistema integrada al launcher cuando exista un canal seguro,
   logs utiles para soporte y mensajes simples para usuarios no tecnicos.
5. Formalizar backup/restauracion de PostgreSQL, certificados y logs antes de
   ampliar volumen productivo.
6. Agregar descarga masiva de PDFs en ZIP y seleccion multiple desde el listado
   de comprobantes.
7. Corregir el setup E2E para que `npm run test:e2e` vuelva a ser evidencia
   confiable en auditorias.
8. Definir la politica de versiones posteriores al MVP.

## Criterio de exito del MVP

El MVP se considera cerrado cuando:

- una persona administrativa no tecnica puede emitir un comprobante individual sin ayuda tecnica
- una persona administrativa no tecnica puede emitir un lote por Excel sin soporte tecnico constante
- una persona administrativa no tecnica puede revisar el formato detectado y confirmar antes de emitir
- los comprobantes quedan autorizados con CAE en homologacion y la operacion
  productiva inicial esta documentada sin exponer datos privados
- el usuario puede consultar comprobantes, ver PDF y operar reportes basicos
- la documentacion permite retomar el proyecto y operarlo sin reconstruir contexto desde cero

## Criterio de exito de largo plazo

FactuFlow deja de ser "solo un MVP" cuando ademas:

- soporta despliegues reproducibles
- soporta varios emisores con aislamiento fuerte y emisor activo explicito
- tiene estrategia clara de migraciones, observabilidad, soporte y releases
- puede ser usado por muchos usuarios sin depender del conocimiento historico de una sola persona
