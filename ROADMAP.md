# Roadmap de FactuFlow

Última actualización: 2026-07-07

Este roadmap traduce la visión estable del producto en prioridades, fases y
trabajo planificado. La visión canónica vive en `VISION.md` y no debe cambiarse
desde este archivo.

## Como leer este archivo

- `[x]` Hecho
- `[~]` En curso
- `[ ]` Pendiente

## Visión del producto

La visión canónica del producto está definida en `VISION.md`.

Todo ítem de este roadmap debe alinearse con esa visión. Si una prioridad,
fase, implementacion o cambio deseado contradice `VISION.md`, primero debe
modificarse explícitamente la visión y recién después incorporarse al roadmap.

## Objetivo actual

Consolidar el MVP después del uso productivo real controlado, centrado en:
- emisión individual y masiva por Excel
- formatos de importación configurables para archivos externos
- uso administrativo no técnico
- homologación real y operación productiva inicial con ARCA
- multiemisor con un emisor activo explícito por vez
- instalación local o en VPS pequeño, con consumo eficiente de procesamiento,
  RAM y almacenamiento
- visibilidad administrativa del uso de almacenamiento por instalación, emisor
  y tipo de dato
- robustez operativa: backups, trazabilidad, observabilidad y soporte
- rediseño secuencial de carga masiva para reducir ruido operativo sin tocar
  garantías fiscales

## Decisiones de producto vigentes

- FactuFlow es una herramienta para facturar. El alcance central es
  facturación electrónica ARCA, emisión individual, emisión masiva, PDFs,
  reportes operativos y soporte administrativo del flujo de facturación.
- No está planificado incorporar manejo de cuentas corrientes, stock ni
  catálogos como módulos del producto.
- Las integraciones externas quedan para una etapa posterior, cuando la
  facturación este madura y productiva estable. Esas integraciones deben estar
  enfocadas en obtener datos desde otras fuentes o aplicaciones, o enviar datos
  hacia ellas, usando la API existente o su evolucion.
- El modelo multiemisor vigente es el de una empresa/emisor activo por vez. Un
  contador independiente o estudio chico puede administrar varios CUITs, pero
  toda operación debe quedar scopiada al emisor activo seleccionado.
- El modelo inicial de usuarios es simple: el primer usuario de una instalación
  es administrador propietario; luego solo administradores crean, desactivan,
  reactivan o resetean usuarios. Los administradores pueden operar todos los
  emisores configurados; los usuarios comunes solo pueden operar el emisor
  asignado en su cuenta.
- No se avanza por ahora hacia una plataforma multiempresa compleja con
  administración central completa, permisos finos por organización, reportes
  globales consolidados u operación simultanea entre emisores.
- La seguridad multiemisor es prioritaria: clientes, certificados, puntos de
  venta, comprobantes, lotes, PDFs, reportes, perfiles de carga y formatos de
  importación no deben mezclarse entre emisores.
- Las operaciones que pueden solicitar CAE deben ser idempotentes desde backend,
  no solo desde UI. Emisión individual, procesamiento de lotes y reintento de
  fallidos exigen `X-Idempotency-Key`, persisten una operación durable antes de
  ARCA y dejan intentos fiscales reconciliables si el resultado queda incierto.
- El despliegue local con launcher ya existe y está probado hasta nivel
  desarrollo/QA. La primera instalación privada en VPS con
  `docker-compose.prod.yml`, PostgreSQL y HTTPS ya quedó operativa; el siguiente
  hito de plataforma es robustecer operación, observabilidad, recuperación y
  mantenimiento.
- FactuFlow debe poder operar en instalaciones locales o VPS pequeños. Las
  decisiones de arquitectura, jobs, observabilidad, reportes, PDFs y
  almacenamiento deben priorizar sencillez y bajo consumo de procesamiento, RAM
  y disco sin perder funcionalidad fiscal u operativa.
- En VPS, la persistencia debe limitarse a los datos mínimos necesarios para
  operar, auditar y recuperar el sistema. PDFs, ZIPs, archivos observados y
  otros artefactos descargables no vitales deben generarse bajo demanda,
  descargarse a la PC del usuario y limpiarse del servidor después de cumplir su
  propósito.
- El gestor de almacenamiento administrativo queda incorporado como herramienta
  de diagnóstico y mantenimiento. Muestra cuánto espacio usa la instalación y lo
  desglosa por emisor, base de datos, lotes, archivos temporales, caché,
  certificados y logs. El cálculo es liviano, acotado a rutas y tablas
  conocidas, y no expone datos privados innecesarios. Las acciones de limpieza
  sobre lotes, logs y temporales exigen resguardo ZIP descargado antes de liberar
  espacio.
- La distribución comercial instalable queda para una etapa posterior, cuando
  el producto sea estable y repetible funcionando en VPS.
- La observabilidad operativa estándar es obligatoria antes de ampliar el uso
  productivo. Debe permitir diagnosticar emisiones, lotes, errores ARCA,
  reconciliaciones, estado del sistema y backups con lenguaje simple para
  usuarios no técnicos. No requiere todavía monitoreo complejo con herramientas
  externas.

## Foto actual del proyecto

### Producto y negocio
- [x] Objetivo principal redefinido: emisión masiva y UX administrativa simple
- [x] Modelo multiemisor definido: varios CUITs por usuario, un emisor activo
  explícito por vez
- [~] Criterios UX no técnicos parcialmente implementados
- [x] Login informa claramente cuando el servidor local no está disponible
- [x] Setup inicial cerrado cuando ya existe cualquier usuario y administración
  de usuarios disponible dentro de la aplicación
- [x] Producción real inicial utilizada con comprobantes autorizados
- [ ] Refuerzo continuo de aislamiento entre emisores antes de ampliar volumen
  o uso productivo

### Backend
- [x] FastAPI operativo con auth, clientes, empresa, puntos de venta, certificados, comprobantes, PDF, lotes y reportes
- [x] Integración WSAA + WSFEv1 operativa en homologación y producción inicial
- [x] Emisión individual real validada con CAE
- [x] Emisión masiva por Excel implementada
- [x] Formatos de importación configurables para emisión masiva con alcance global y por emisor
- [x] Administrador visual de plantillas de carga masiva sobre
  `formatos_importacion`, con plantillas globales o por emisor, clonado de
  plantillas protegidas, versionado, compatibilidad con perfiles y descarga
  `.xlsx` generada bajo demanda.
- [x] Perfiles de carga masiva por emisor para precargar formato, punto de
  venta, concepto, descripción y fechas visibles antes de validar
- [x] Perfiles de carga masiva no permiten guardar fecha actual como regla de
  emisión fiscal
- [x] Emisión masiva permite consumidor final desde Excel sin cliente precargado cuando la normativa no exige identificar receptor
- [x] Fecha de emisión explícita; no se asume fecha del día actual al emitir
- [x] Confirmación final obligatoria de fecha fiscal antes de solicitar CAE
- [x] Procesamiento de lotes exige token exacto de confirmación fiscal con
  fechas y puntos de venta validados, no un boolean genérico
- [x] La emisión valida que el punto de venta y el cliente opcional pertenezcan al
  emisor activo antes de solicitar CAE
- [x] Nueva factura ofrece solo puntos de venta usables por FactuFlow y la API
  rechaza numeración para puntos no Web Services con error de negocio
- [x] Uploads de lotes limitados por `BATCH_MAX_UPLOAD_BYTES` y XLSX
  malformados rechazados antes de validar
- [x] Concepto fiscal ARCA explícito; no se asume productos o servicios por defecto
- [~] Descripción/concepto facturado del ítem documentado como dato separado
  del concepto fiscal ARCA; debe venir del archivo o de un valor fijo confirmado
  para todo el lote, sin defaults ocultos
- [x] Numeración ARCA adelantada y fallos post-CAE quedan como
  `requiere_reconciliacion`, sin persistir respuestas no aprobadas como
  comprobantes emitidos
- [x] Idempotencia fiscal obligatoria para emisión individual, procesamiento de
  lotes y reintento de fallidos mediante `X-Idempotency-Key`, hash estable de
  payload y respuesta persistida.
- [x] Intentos de emisión fiscal durables antes de ARCA, con reserva de
  numeración, snapshot mínimo, CAE cuando exista y bloqueo de reintentos
  inciertos hasta reconciliar.
- [x] Intentos fiscales `en_proceso` vencidos se verifican con
  `FECompConsultar` antes de liberar numeración o vincular un comprobante
  autorizado.
- [x] Sincronización manual de puntos de venta ARCA validada desde UI; los
  puntos devueltos por WSFE se crean o actualizan como Web Services usables
- [x] Validación de puntos de venta en emisión normaliza `Bloqueado=N`/`S` de ARCA
- [x] Factura C no informa objeto `Iva` en WSFE y bloquea ítems con IVA distinto de 0
- [x] UI de puntos de venta valida el certificado activo del ambiente ARCA actual
  antes de sincronizar WSFE
- [x] Emisor activo consistente por pestaña y API con rechazo de conflictos
  entre `X-Empresa-Id` y query legacy `empresa_id`
- [x] API `/api/usuarios` para administradores y `GET /api/auth/setup-status`
  para mostrar setup inicial solo si no hay usuarios
- [~] Endurecimiento de seguridad multiemisor para evitar mezcla de clientes,
  certificados, puntos de venta, comprobantes, lotes, PDFs, reportes, perfiles
  y formatos entre emisores
- [x] Excel observado de lotes escapa valores con forma de fórmula
- [x] Notas de crédito/débito informan comprobantes asociados en WSFE
  (`CbtesAsoc`) cuando corresponde
- [~] Alineacion limpia entre base legacy y Alembic
- [ ] Arquitectura de jobs robusta para procesos largos

### Frontend
- [x] Vue + Pinia + Router operativos
- [x] Dashboard, clientes, comprobantes, emisión masiva, reportes, certificados, puntos de venta y empresa operativos
- [x] Selector de emisor activo para operar varios CUITs desde un usuario
- [x] Selector de emisor activo visible con las opciones autorizadas para cada usuario activo
- [x] Pantalla `Usuarios` reservada a administradores para alta, edición,
  desactivación/reactivación y reseteo de claves
- [x] Integración visual controlada de identidad v01 cerrada en frontend
  público, acumulada en cortes pequeños y auditables hasta un checkpoint
  instalable en producción; no se despliegan microcortes estéticos por separado.
- [x] Diagnóstico UX específico de `/comprobantes/lotes` cerrado y rediseño
  secuencial documentado en `docs/agents/lotes-ux-redesign.md`. Cortes 1, 2,
  3 y 4 implementados en frontend: preparación/validación más directa, lote
  activo con resumen prioritario, detalles plegables, siguiente acción visible,
  resolución de pendientes como modo excepcional y navegación compacta de lotes
  recientes, sin tocar backend, ARCA, emisión, servicios, stores, rutas ni
  contratos.
- [ ] Cambio de contraseña propio para usuarios autenticados, sin intervención
  del administrador, validando contraseña actual y nueva contraseña
- [x] Secciones principales scopiadas por emisor activo y verificadas al
  cambiar el selector
- [x] Vistas sensibles descartan respuestas asincrónicas viejas al cambiar el
  emisor activo, incluyendo reportes, certificados, puntos de venta y
  numeración de nueva factura
- [x] Autodetección asistida de formato al subir Excel externo para emisión masiva
- [x] `Emisores > Carga masiva` incorpora subvista de `Plantillas` para crear,
  editar, clonar, desactivar, revisar compatibilidad y descargar Exceles
  visuales para usuarios no técnicos.
- [x] Nueva factura exige CUIT para Factura A y Notas A, y el refresco de lista
  posterior a CAE es no bloqueante
- [x] QA manual guiada de flujos reales
- [ ] Operaciones masivas de PDF desde listado

### Operación y plataforma
- [x] Arranque local simple con `run-local.ps1`
- [x] Launcher local Windows manual con icono en tray para desarrollo/QA
- [x] Perfiles Docker separados para local y producción
- [x] PostgreSQL definido como base recomendada para operación real
- [x] Comando administrativo para crear/promover usuario propietario
- [x] Alta inicial por UI solo cuando la instalación no tiene usuarios; altas
  posteriores desde menú `Usuarios`
- [x] Primera instalación privada en VPS con Docker producción, PostgreSQL y
  HTTPS validada
- [x] Herramienta privada de preparación de migración local a PostgreSQL/VPS con
  `preflight`, `export`, `import` y `validate`
- [x] Ensayo local de restauración en PostgreSQL con Docker: Alembic head,
  importación, validación de conteos/certificados/secuencias y healthcheck OK
- [x] Cierre operativo inicial del VPS: checkout limpio, configuración privada
  fuera de Git, servicios sanos y reverse proxy HTTPS funcionando
- [x] Backup manual inicial validado: dump PostgreSQL, certificados,
  configuración privada, copia cifrada fuera del VPS y restauración de prueba
  desde la copia cifrada
- [ ] CI/CD completo y alineado al estado real del repo
- [~] Observabilidad operativa estándar definida como requisito post-piloto
- [x] Gestor de almacenamiento administrativo para ver uso total y desglose por
  emisor, lotes, base, temporales, artefactos descargables, certificados y logs
- [x] QA visual local del gestor de almacenamiento con API mockeada, datos
  ficticios, E2E permanente y capturas privadas; no reemplaza la validación VPS
  con datos de prueba controlados
- [~] Observabilidad, backups manuales y políticas operativas iniciales
  parcialmente probadas; falta automatización, retención y recuperación a VPS
  nuevo

## Fase 0 - Fundacion y base técnica

Objetivo: tener un repo mantenible, ejecutable y documentado.

- [x] Repositorio, estructura base y guias para agentes
- [x] Backend y frontend levantables en local
- [x] Acceso local manual `FactuFlow Local.vbs` sin consola visible, con estado
  de backend, frontend y base de datos en tray
- [x] `.env.example` y configuración base
- [x] Documentación técnica inicial
- [~] Docker y compose alineados al estado real
- [ ] Pipeline CI básico confiable para backend y frontend
- [x] Corte versionado `0.2.0-mvp` y changelog como historial principal

## Fase 1 - Core funcional de negocio

Objetivo: poder operar una empresa y emitir comprobantes reales.

### Dominio principal
- [x] Empresa
- [x] Usuario y autenticacion
- [x] Clientes
- [x] Puntos de venta
- [x] Certificados
- [x] Comprobantes e ítems

### API y backend
- [x] Endpoints base para auth, clientes, empresa y comprobantes
- [x] Seguridad básica por empresa
- [x] Generacion de PDF bajo demanda
- [x] PDF de comprobante con formato administrativo profesional, ubicación de
  elementos principales alineada a la factura oficial ARCA y QR ARCA testeado
  por payload decodificable
- [x] Reportes básicos de consulta
- [~] Consistencia documental completa de endpoints y contratos

### UX
- [x] Login
- [x] Dashboard
- [x] Formularios principales
- [~] Refinamiento de mensajes y ayudas contextuales
- [ ] Estados vacíos y recuperacion de errores totalmente pulidos

## Fase 2 - Integración ARCA real

Objetivo: dejar la emisión validada contra servicios reales.

### WSAA
- [x] Generacion de TRA
- [x] Firma y login CMS
- [x] Obtencion de Token y Sign
- [x] Cache persistente de tickets
- [ ] Política de invalidacion/rotacion mas robusta

### WSFEv1
- [x] `FECAESolicitar`
- [x] `FECAESolicitar` por sublotes usando `FECompTotXRequest.RegXReq`
- [x] `FECompUltimoAutorizado`
- [x] `FECompConsultar` útil para verificacion
- [x] `FECompConsultar` usado para resolver intentos fiscales vencidos antes de
  liberar numeración o registrar una autorización pendiente.
- [x] Validación de numeración y punto de venta en emisión
- [x] Mapeo de `CondicionIVAReceptorId`
- [x] Validación local de ventana ARCA para fecha de emisión antes de emitir
- [~] Manejo fino de edge cases homologación vs producción

### Homologación
- [x] Certificado homologación emitido por WSASS
- [x] Autorización `wsfe` creada para CUIT representado
- [x] Smoke real individual
- [x] Smoke real masivo
- [x] QA manual completa desde UI
- [ ] Smoke repetible documentado como procedimiento de soporte

### Producción
- [x] Piloto productivo real ejecutado con comprobantes autorizados
- [x] Certificado productivo cargado y prueba WSAA/ARCA exitosa
- [~] Certificados y proceso de producción
- [x] Certificados ARCA con paths gestionados dentro de `CERTS_PATH`, claves
  nuevas cifradas y un único certificado activo por emisor/ambiente
- [~] Checklist operativo post-piloto: fecha fiscal, punto de venta, backup,
  logs, restauración y evidencia sanitaria
- [ ] Validación sistemática de diferencias operativas entre homologación y producción

## Fase 3 - Emisión masiva como nucleo del producto

Objetivo: que FactuFlow sea realmente útil para operaciones administrativas de volumen.

### Lotes
- [x] Entidades de lote, grupo y filas
- [x] Plantilla Excel fija
- [x] Formatos de importación configurables por encabezado, columna o constante
- [x] Formato global para extractos bancarios con columnas `Fecha`, `Créditos`, `Leyendas Adicionales1`, `Leyendas Adicionales2` y `Pto Vta`
- [x] Formato particular local para emisor Responsable Inscripto privado
  (`Factura B IVA 21%`) con neto
  gravado como precio del ítem, total como referencia y consumidor final sin
  documento cuando corresponde
- [x] Formato particular local para emisor privado con Factura B IVA 21%,
  vinculado al perfil predeterminado del emisor, con `Imp. Neto Gravado` como
  neto del ítem e `Imp. Total` solo como control de consistencia
- [x] Validación de consistencia entre total informado por archivo externo y
  total calculado desde ítems e IVA antes de permitir emisión
- [x] Política explícita de fecha de emisión por lote: desde archivo o fecha fija confirmada
- [x] Política explícita de concepto fiscal ARCA por lote: productos, servicios
  o definido por archivo
- [x] Política explícita de descripción facturada del ítem por lote: desde
  archivo o valor fijo para todo el lote, independiente del concepto fiscal ARCA
- [x] Perfiles de carga masiva por emisor, con predeterminado, punto de venta y
  reglas relativas de fechas visibles, sin materializar fecha fiscal en emisión
  masiva sin una base explícita del usuario
- [x] Agrupacion por `comprobante_ref`
- [x] Prevalidacion por fila y por comprobante
- [x] Reintento seguro del mismo archivo cuando el lote previo no emitió CAE
- [x] Toma atómica del lote antes de emitir para evitar procesamiento concurrente
- [x] Fallos post-CAE quedan como `requiere_reconciliacion` y no habilitan
  reintentos automáticos
- [x] Cada grupo emitible de lote o reintento crea un intento fiscal durable
  asociado a la operación idempotente de usuario.
- [x] Duplicados lógicos de comprobantes se informan como advertencia con
  confirmación adicional; no son bloqueo automático ni forman parte del hash de
  idempotencia.
- [x] Gestión resolutiva de lotes parciales: reintento de fallidos con token de
  fecha fiscal, reconciliación externa verificada contra ARCA, descarte
  auditado de pendientes y cierre como `cerrado_reconciliado` o
  `cerrado_con_descartes`
- [x] Comprobantes emitidos fuera de FactuFlow pueden registrarse con
  `origen_emision = arca_web` solo después de validar tipo, punto de venta,
  número, receptor, fecha, total y CAE con `FECompConsultar`; un mismo
  comprobante no puede cerrar más de un grupo local
- [x] Compactación de lotes cerrados para ahorrar almacenamiento: elimina filas
  originales del Excel y conserva resumen, grupos, comprobantes y auditoría
- [x] Eliminación física permitida solo para lotes sin comprobantes emitidos ni
  incertidumbre fiscal; los eventos operativos quedan preservados
- [x] Confirmación fiscal final de lotes usa token exacto derivado de los grupos
  validados: fechas y puntos de venta concretos
- [x] Archivos XLSX malformados o por encima de `BATCH_MAX_UPLOAD_BYTES` quedan
  rechazados antes de crear o validar lotes
- [x] Snapshot fiscal del receptor en comprobantes
- [x] Persistencia de fechas de servicio y vencimiento de pago en comprobantes
  nuevos y backfill desde payloads históricos de lotes para reflejarlas en el
  PDF
- [x] Clientes precargados opcionales para lotes masivos
- [x] Emisión de lotes chicos desde UI observable por background/polling
- [x] Ejecución asincrónica para lotes grandes
- [x] Worker evita reencolar lotes activos y ya no reemite lotes `procesando`
  stale: los bloquea como `requiere_reconciliacion` salvo reconciliación local
  respaldada por un intento fiscal autorizado del mismo lote/grupo con
  comprobante, número, CAE y datos fiscales coherentes. Si el bloqueo de un
  stale falla, no avanza con lotes `en_cola` en ese ciclo. Los grupos
  `validado` remanentes quedan como `requiere_reconciliacion`.
- [x] Emisión masiva por sublotes ARCA para grupos con mismo punto de venta y
  tipo, con fallback unitario explícito si `RegXReq` no está disponible

### UX de lotes
- [x] Wizard de emisión masiva
- [x] Rediseño UX secuencial de `/comprobantes/lotes` documentado en
  `docs/agents/lotes-ux-redesign.md`: reducir onboarding persistente, agrupar
  configuración fiscal, acercar `Validar lote` al cierre de requisitos, tratar
  reconciliación como modo excepcional y compactar `Lotes recientes`. Cortes 1,
  2, 3 y 4 implementados como cambios frontend-only.
- [x] Preseleccion del formato sugerido con alta confianza antes de validar
  archivos externos
- [x] Confirmación de fecha de emisión y fechas de servicio antes de validar
- [x] Modal final de advertencia antes de emitir: confirma fecha fiscal y avisa
  que luego no se podran emitir comprobantes con fecha anterior para ese mismo
  punto de venta
- [x] Confirmación de concepto fiscal ARCA antes de validar; si viene del archivo, todas las filas deben indicar `Producto` o `Servicio`
- [x] Confirmación de descripción/concepto facturado del ítem antes de validar:
  desde archivo o texto fijo para todo el lote
- [x] Selector de perfil de carga masiva en emisión masiva, con aplicacion
  automática cuando el emisor tiene uno solo o uno predeterminado
- [x] Selector de punto de venta en perfiles y emisión masiva: usar el punto del
  archivo o fijar uno usable del emisor activo
- [x] Si el usuario modifica una configuración precargada por perfil de carga
  masiva, el lote se valida sin snapshot de perfil aplicado
- [x] Separacion clara entre validar lote y emitir comprobantes válidos
- [x] Resumen previo a emisión con neto, IVA 21%, IVA 10,5% y total de
  comprobantes listos para emitir
- [x] Detalle de lotes grandes con resumen completo y grupos paginados desde
  backend para evitar renderizar miles de comprobantes en una sola pantalla
- [x] Mensajes básicos de validación
- [~] Pulido de ayudas, tooltips y lenguaje administrativo
- [x] Descarga de archivo observado validada manualmente
- [x] PDF de comprobante rediseñado con ubicaciones principales similares a la
  factura oficial ARCA, sin copiar identidad visual oficial, con datos
  fiscales, CAE, QR, detalle y totales organizados profesionalmente
- [x] QA manual local del formato global de extracto bancario sin emitir
- [x] QA visual local del selector obligatorio de fechas fiscales en lotes
- [x] QA visual local de descripción/concepto facturado del ítem independiente
  del concepto fiscal ARCA, sin defaults ocultos
- [x] QA visual local de perfiles de carga masiva: crear, editar, eliminar,
  predeterminar, autoaplicar, modificar antes de validar y verificar modal final
  de fecha fiscal sin emitir
- [x] Preparacion y validación segura sin emisión de lote de Nota de Crédito C
  para anular duplicados productivos
- [x] Emisión y verificacion por consulta ARCA de 19 Nota de Crédito C para
  anular duplicados productivos
- [x] Preparacion y validación segura sin emisión de 1113 Nota de Crédito B
  para corregir Factura B de un emisor privado emitidas con total usado como neto
- [~] QA manual especifica de formatos particulares por emisor
- [ ] Descarga de archivo observado con errores mas amigable
- [x] Progreso real de lotes con barra, timer, ETA, emitidos, fallidos y pendientes
- [x] Aviso visible cuando un lote degrada a modo unitario porque ARCA no
  informó `RegXReq`
- [x] Panel de resolución en lotes para reintentar fallidos, reconciliar
  comprobantes emitidos en ARCA Web, descartar pendientes visibles, compactar
  lotes cerrados o eliminar lotes sin emisión, con resolución excepcional
  agrupada visualmente bajo `Resolver pendientes`

### Operación masiva posterior a la emisión
- [ ] Descarga masiva de PDFs en ZIP generado bajo demanda y sin persistencia
  permanente en VPS
- [ ] Selección multiple en listado de comprobantes
- [ ] Preparación asincrónica de PDFs para lotes grandes con limpieza de
  temporales después de la descarga o vencimiento operativo
- [ ] Trazabilidad de tareas masivas iniciadas por usuario

## Fase 4 - UX administrativa no técnica

Objetivo: reducir al mínimo la necesidad de soporte técnico para operar.

- [x] Uso de espanol claro en pantallas core
- [x] Eliminacion de `alert()` y `confirm()` nativos en flujos principales
- [~] Mensajes accionables en errores de negocio
- [x] Mensaje claro en login cuando el backend local no responde
- [~] Ayudas contextuales en pantallas sensibles
- [~] Pantalla de estado del sistema dentro del frontend
- [ ] Integración formal entre launcher local y UI web
- [ ] Tooltips y microcopy sistematizados en toda la app
- [ ] Checklists previos a la emisión
- [ ] Vistas vacías guiadas
- [ ] Confirmaciones claras para acciones sensibles
- [x] Checkpoint visual v01 instalable en producción cerrado: shell,
  componentes base/comunes, auth/setup, dashboard, clientes, usuarios, reportes
  y certificados quedaron alineados con identidad v01 sin tocar backend, ARCA,
  emisión ni lotes fiscales. El despliegue productivo sigue requiriendo decisión
  explícita contra un commit o tag identificable.
- [ ] Pantalla o sección `Mi cuenta` para que cada usuario cambie su propia
  contraseña
- [ ] Revision completa de accesibilidad y legibilidad

## Fase 5 - Datos, migraciones y estabilidad

Objetivo: que el proyecto soporte evolucion sin deuda estructural peligrosa.

### Base de datos
- [x] Modelos principales definidos
- [x] Migración inicial de esquema creada
- [x] Modelos versionados de formatos de importación y trazabilidad del mapeo usado por lote
- [~] Estrategia de convivencia con DB local legacy
- [~] Stamping/migración limpia de instalaciones existentes
- [x] Export/import privado desde SQLite local a PostgreSQL limpio, preservando
  configuración operativa, certificados, formatos, perfiles, comprobantes e
  ítems, y excluyendo lotes/artefactos no vitales
- [ ] Política clara de seeds y datos de desarrollo

### Calidad y testing
- [x] Suite backend activa
- [x] E2E frontend con Playwright confiable para Chromium desktop local
- [x] Smoke real de homologación ejecutado manualmente
- [x] QA manual funcional cerrada
- [x] Script de lint frontend no destructivo `npm run lint:check`
- [ ] Migrar el entorno de build/test del frontend y CI a Node.js 24 LTS,
  validando `npm ci`, `type-check`, `lint:check`, `build` y `test:unit`, y
  documentando la versión recomendada para desarrollo local.
- [x] Reparaciones Clawpatch 2026-05-16/17 cerradas con
  backend/frontend/repo en `openFindings=0`
- [x] Auditoría Clawpatch 2026-07-05 cerrada nuevamente con repo completo,
  backend y frontend en `openFindings=0`, `autoreview` GPT-5.5 alto limpio y
  CI remoto aprobado
- [~] Auditoría backend Clawpatch 2026-07-07 en curso: cerrados cortes de
  aislamiento multiemisor, validación de rangos CAE batch, borrado de
  certificados post-commit, importación de puntos de venta sin estado ARCA,
  corrección del subdiario IVA para comprobantes autorizados con IVA cero y
  rechazo de secretos JWT productivos inseguros.
- [x] Reportes IVA calculan notas de crédito con signo negativo, incluyen
  comprobantes C con IVA cero como exentos, ítems A/B con IVA cero como no
  gravados y el detalle de subdiario incluye gravado e IVA 27%
- [x] Corregir setup E2E para que `npm run test:e2e` vuelva a ser evidencia
  confiable en auditorías locales de escritorio
- [ ] Cobertura mas profunda sobre detalles de comprobantes, PDF y reportes
- [ ] Smoke automatizado de stack completo local

### Robustez
- [x] Jobs de lotes persistidos en BD con ventana stale segura: la ventana ya
  no habilita reemisión automática, sino bloqueo y reconciliación; los grupos
  emitibles remanentes quedan marcados como inciertos.
- [x] Reintentos bloqueados cuando existe incertidumbre post-ARCA
- [ ] Reintentos controlados para otros procesos largos
- [x] Idempotencia fiscal obligatoria y visible para usuario final en caminos de
  CAE: misma clave y mismo payload no reemiten; misma clave con otros datos
  devuelve conflicto; clave ausente se rechaza.
- [ ] Auditoria de eventos operativos críticos

## Fase 6 - Multiemisor con emisor activo

Objetivo: permitir que contadores independientes o estudios chicos administren
varios emisores desde una misma instalación, operando siempre un emisor activo
explícito por vez. No incluye, por ahora, administración central compleja,
permisos finos por organización, reportes globales consolidados ni operación
simultanea entre emisores.

- [x] Header `X-Empresa-Id` para usuarios autenticados activos
- [x] Selector de emisor activo en frontend
- [x] Administradores operativos con acceso a todos los emisores configurados
- [x] Usuarios comunes restringidos al emisor asignado
- [x] Alta básica de nuevos emisores desde UI admin
- [x] Configuración de perfiles de carga masiva desde `Emisores > Carga masiva`,
  incluyendo punto de venta por archivo o punto fijo usable del emisor
- [x] Precarga de emisor desde constancia de inscripcion ARCA en PDF,
  constancia de inscripción de persona física y constancia de opción de
  Monotributo, con provincia validada contra catálogo argentino
- [x] Importación de constancia ARCA de puntos de venta con domicilio y nombre fantasia
- [x] Re-scopeo de dashboard, clientes, comprobantes, emisión masiva,
  reportes, certificados, puntos de venta y nueva factura por emisor activo
- [x] Scoping backend de emisión contra punto de venta y cliente del emisor
  activo
- [~] Modelo multiemisor validado con mas de un emisor real de prueba
- [ ] Auditoria de aislamiento entre emisores en certificados, puntos de venta,
  clientes, comprobantes, lotes, PDFs, reportes, perfiles y formatos
- [ ] Tests de regresion multiemisor para operaciones críticas antes de ampliar
  volumen productivo
- [ ] Onboarding multiemisor mas claro para contadores y estudios chicos

## Fase 7 - Plataforma lista para despliegue serio

Objetivo: que FactuFlow pueda instalarse y operarse con menor riesgo técnico.

### Contenedores y despliegue
- [x] Dockerfiles y compose existentes
- [x] `docker-compose.yml` para local/desarrollo
- [x] `docker-compose.prod.yml` para VPS/producción con PostgreSQL
- [x] Instalación real en VPS con `docker-compose.prod.yml`
- [~] Variables de entorno cerradas por ambiente
- [~] Guía de despliegue local y servidor
- [x] Runbook de migración local a VPS documentado en
  `docs/setup/vps-migration.md`
- [x] Flujo público de desarrollo, versionado, despliegue manual y auditoría
  productiva documentado en `docs/agents/production-workflow.md`
- [x] Reverse proxy y TLS validados en una instalación privada

### Operación
- [ ] Logs operativos con identificador de seguimiento por emisor, usuario,
  lote/comprobante, job y error local o ARCA
- [ ] Retencion de logs privados definida por entorno
- [ ] Política de almacenamiento mínimo para VPS: temporales, PDFs, ZIPs,
  archivos observados y artefactos no vitales con limpieza controlada
- [x] Primera acción de limpieza segura sobre lotes: compactación de detalle de
  filas en lotes cerrados y borrado restringido de lotes sin emisión
- [x] Gestor de almacenamiento para administradores, con uso total de la
  instalación, desglose por emisor y tipo de dato, alertas simples de consumo y
  acciones seguras de limpieza sobre artefactos no vitales
- [ ] Healthchecks claros para backend, base, worker, ARCA y certificado del
  emisor activo
- [~] Backup y restauración de base y certificados: prueba manual validada,
  automatización y retención pendientes
- [ ] Automatización de backups cifrados con validación periódica, política de
  retención, destino externo y alertas de fallo
- [ ] Runbook completo de recuperación a un VPS nuevo desde repositorio limpio,
  backup cifrado y configuración privada
- [x] Definir si los certificados productivos se migran desde local al VPS o si
  se generan certificados nuevos para el servidor: se migran solo como reemplazo
  del entorno local, con preflight obligatorio, archivos completos en
  `CERTS_PATH` y re-cifrado de claves privadas para producción
- [ ] Política de manejo de secretos

### Diagnostico operativo simple
- [x] Decisión de observabilidad operativa estándar documentada en
  `docs/agents/operational-observability.md`
- [~] Pantalla `Estado del sistema` en la interfaz, con estados simples como
  `Correcto`, `Necesita atención` y `No disponible`: primer corte frontend
  implementado con señales existentes de API, base, certificado local, ARCA
  manual, almacenamiento, guía rápida de soporte y ficha para soporte con datos
  seguros mínimos; faltan healthcheck dedicado de worker, backup y trazabilidad
  histórica más completa
- [x] Vista administrativa de almacenamiento integrada al diagnóstico operativo,
  sin escaneos pesados ni exposición innecesaria de datos privados
- [ ] Trazabilidad visible de lotes, reintentos, estados parciales y
  reconciliaciones
- [ ] Mensajes de error con explicacion simple, impacto y próximo paso seguro
- [~] Runbook de diagnostico para soporte y usuarios administrativos: guía y
  ficha visibles en `Sistema > Estado`, más primer runbook público sanitizado en
  `docs/agents/support-runbook.md`; quedan pendientes healthchecks dedicados y
  documentación privada por instalación
- [ ] Metricas y alertas avanzadas, después de estabilizar VPS

## Fase 8 - Distribución, releases y adopcion

Objetivo: profesionalizar la entrega del producto.

### Releases
- [x] Changelog operativo consistente como fuente principal de historial
- [x] Corte actual `0.2.0-mvp` definido como línea base
- [x] Resumenes de fases antiguas consolidados en changelog para evitar
  snapshots obsoletos
- [~] Política de versiones posteriores al MVP
- [ ] Paquetes o imagenes publicables
- [~] Notas de release por versión desde el corte actual

### Distribución
- [ ] Instalación simplificada para terceros, posterior a estabilizar VPS
- [ ] Plantillas de configuración por ambiente
- [ ] Demo controlada o entorno de evaluación
- [ ] Procedimiento de upgrade entre versiones

### Soporte y adopcion
- [ ] Runbooks de soporte
- [ ] Manuales de troubleshooting para usuarios administrativos
- [ ] Manuales técnicos para deploy y mantenimiento
- [ ] Política de compatibilidad y migraciones

## Fase 9 - Evolucion del producto

Objetivo: ampliar valor mas alla del MVP.

- [x] Producción ARCA inicial
- [~] Operación productiva robusta y repetible
- [ ] Exportaciones de reportes
- [ ] Envio de comprobantes por email
- [ ] Integraciones externas de entrada/salida de datos via API, posteriores a
  la madurez productiva de facturación
- [ ] Dashboard de operación mas rico

## Prioridades inmediatas

1. Guardar la clave real del backup cifrado en un gestor de contraseñas seguro,
   fuera de Git y fuera del VPS.
2. Mantener documentación viva alineada con el estado post-piloto productivo,
   separando evidencia privada de resúmenes versionables.
3. Convertir los detalles observados durante el uso real en un backlog
   priorizado: riesgos fiscales, UX, PDFs, reportes y soporte. El primer
   diagnóstico UX formalizado es carga masiva en
   `docs/agents/lotes-ux-redesign.md`.
4. Implementar observabilidad operativa estándar: trazabilidad clara, pantalla
   de estado del sistema integrada al launcher cuando exista un canal seguro,
   logs útiles para soporte y mensajes simples para usuarios no técnicos.
5. Diseñar la automatización futura de backups cifrados con validación,
   retención y destino externo, pero no implementarla todavía hasta cerrar la
   política operativa.
6. Documentar y ensayar el runbook completo de recuperación a un VPS nuevo.
7. Validar en VPS la política de almacenamiento mínimo y limpieza de artefactos
   descargables usando el gestor administrativo, especialmente PDFs, ZIPs y
   temporales de lotes.
8. Repetir QA visual del gestor de almacenamiento en VPS con datos de prueba
   controlados: resguardo ZIP, confirmación `Ya lo descargué`, compactación y
   limpieza segura de temporales/logs/certificados huérfanos. La prevalidación
   local con mocks ya quedó cubierta.
9. Agregar descarga masiva de PDFs en ZIP y selección múltiple desde el listado
   de comprobantes, sin persistencia permanente en el servidor.
10. Definir la política de versiones posteriores al MVP.

## Criterio de exito del MVP

El MVP se considera cerrado cuando:

- una persona administrativa no técnica puede emitir un comprobante individual sin ayuda técnica
- una persona administrativa no técnica puede emitir un lote por Excel sin soporte técnico constante
- una persona administrativa no técnica puede revisar el formato detectado y confirmar antes de emitir
- los comprobantes quedan autorizados con CAE en homologación y la operación
  productiva inicial está documentada sin exponer datos privados
- el usuario puede consultar comprobantes, ver PDF y operar reportes básicos
- la documentación permite retomar el proyecto y operarlo sin reconstruir contexto desde cero

## Criterio de exito de largo plazo

FactuFlow deja de ser "solo un MVP" cuando además:

- soporta despliegues reproducibles
- soporta varios emisores con aislamiento fuerte y emisor activo explícito
- tiene estrategia clara de migraciones, observabilidad, soporte y releases
- puede ser usado por muchos usuarios sin depender del conocimiento histórico de una sola persona
