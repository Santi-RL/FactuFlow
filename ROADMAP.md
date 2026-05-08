# Roadmap de FactuFlow

Ultima actualizacion: 2026-05-08

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
- preparada para despliegue serio y multiempresa
- auditable, mantenible y documentada
- con capacidad de escalar desde uso controlado hasta adopcion por multiples equipos o clientes

## Objetivo actual

Cerrar un MVP funcional centrado en:
- emision individual y masiva por Excel
- formatos de importacion configurables para archivos externos
- uso administrativo no tecnico
- homologacion real con ARCA
- una empresa por vez, con base preparada para multiempresa posterior

## Foto actual del proyecto

### Producto y negocio
- [x] Objetivo principal redefinido: emision masiva y UX administrativa simple
- [x] Single-company operativo como foco inicial
- [~] Criterios UX no tecnicos parcialmente implementados
- [ ] Multiempresa completo para admins globales

### Backend
- [x] FastAPI operativo con auth, clientes, empresa, puntos de venta, certificados, comprobantes, PDF, lotes y reportes
- [x] Integracion WSAA + WSFEv1 operativa en homologacion
- [x] Emision individual real validada con CAE
- [x] Emision masiva por Excel implementada
- [x] Formatos de importacion configurables para emision masiva con alcance global y por emisor
- [x] Emision masiva permite consumidor final desde Excel sin cliente precargado cuando la normativa no exige identificar receptor
- [x] Sincronizacion manual de puntos de venta ARCA validada desde UI
- [~] Alineacion limpia entre base legacy y Alembic
- [ ] Arquitectura de jobs robusta para procesos largos

### Frontend
- [x] Vue + Pinia + Router operativos
- [x] Dashboard, clientes, comprobantes, emision masiva, reportes, certificados, puntos de venta y empresa operativos
- [x] Selector de empresa activa para admins
- [x] Autodeteccion asistida de formato al subir Excel externo para emision masiva
- [x] QA manual guiada de flujos reales
- [ ] Operaciones masivas de PDF desde listado

### Operacion y plataforma
- [x] Arranque local simple con `run-local.ps1`
- [x] Perfiles Docker separados para local y produccion
- [x] PostgreSQL definido como base recomendada para operacion real
- [x] Comando administrativo para crear/promover usuario propietario
- [ ] CI/CD completo y alineado al estado real del repo
- [ ] Observabilidad, backups y politicas operativas

## Fase 0 - Fundacion y base tecnica

Objetivo: tener un repo mantenible, ejecutable y documentado.

- [x] Repositorio, estructura base y guias para agentes
- [x] Backend y frontend levantables en local
- [x] `.env.example` y configuracion base
- [x] Documentacion tecnica inicial
- [~] Docker y compose alineados al estado real
- [ ] Pipeline CI basico confiable para backend y frontend
- [ ] Politica clara de versionado y releases

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
- [~] Manejo fino de edge cases homologacion vs produccion

### Homologacion
- [x] Certificado homologacion emitido por WSASS
- [x] Autorizacion `wsfe` creada para CUIT representado
- [x] Smoke real individual
- [x] Smoke real masivo
- [x] QA manual completa desde UI
- [ ] Smoke repetible documentado como procedimiento de soporte

### Produccion
- [~] Base funcional lista para primer piloto controlado
- [x] Certificado productivo cargado y prueba WSAA/ARCA exitosa
- [~] Certificados y proceso de produccion
- [ ] Checklist de salida a produccion
- [ ] Validacion de diferencias operativas entre homologacion y produccion

## Fase 3 - Emision masiva como nucleo del producto

Objetivo: que FactuFlow sea realmente util para operaciones administrativas de volumen.

### Lotes
- [x] Entidades de lote, grupo y filas
- [x] Plantilla Excel fija
- [x] Formatos de importacion configurables por encabezado, columna o constante
- [x] Formato global para extractos bancarios con columnas `Fecha`, `Créditos`, `Leyendas Adicionales1`, `Leyendas Adicionales2` y `Pto Vta`
- [x] Agrupacion por `comprobante_ref`
- [x] Prevalidacion por fila y por comprobante
- [x] Snapshot fiscal del receptor en comprobantes
- [x] Clientes precargados opcionales para lotes masivos
- [x] Emision sync para lotes chicos
- [x] Ejecucion asincronica para lotes grandes

### UX de lotes
- [x] Wizard de emision masiva
- [x] Confirmacion de formato antes de validar archivos externos
- [x] Separacion clara entre validar lote y emitir comprobantes validos
- [x] Mensajes basicos de validacion
- [~] Pulido de ayudas, tooltips y lenguaje administrativo
- [x] Descarga de archivo observado validada manualmente
- [x] QA manual local del formato global de extracto bancario sin emitir
- [ ] QA manual especifica de formatos particulares por emisor
- [ ] Descarga de archivo observado con errores mas amigable
- [ ] Mejores estados de seguimiento para lotes grandes

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
- [~] Ayudas contextuales en pantallas sensibles
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
- [ ] Corregir setup E2E para que `npm run test:e2e` vuelva a ser evidencia
  confiable en auditorias
- [ ] Cobertura mas profunda sobre detalles de comprobantes, PDF y reportes
- [ ] Smoke automatizado de stack completo local

### Robustez
- [~] Jobs de lotes reanudables desde estado persistido en BD
- [ ] Reintentos controlados para procesos largos
- [~] Idempotencia mas visible para usuario final
- [ ] Auditoria de eventos operativos criticos

## Fase 6 - Multiempresa y administracion central

Objetivo: pasar de una operacion de una sola empresa a una plataforma gestionable por admins globales.

- [x] Header `X-Empresa-Id` para admins
- [x] Selector de emisor activo en frontend
- [x] Alta basica de nuevos emisores desde UI admin
- [x] Precarga de emisor desde constancia de inscripcion ARCA en PDF
- [x] Importacion de constancia ARCA de puntos de venta con domicilio y nombre fantasia
- [~] Re-scopeo de comprobantes, reportes y certificados por empresa activa
- [ ] Multiempresa validado con mas de una empresa real de prueba
- [ ] Alta y gestion de multiples empresas por admin global
- [ ] Controles de permisos mas finos
- [ ] Onboarding multiempresa mas claro

## Fase 7 - Plataforma lista para despliegue serio

Objetivo: que FactuFlow pueda instalarse y operarse con menor riesgo tecnico.

### Contenedores y despliegue
- [x] Dockerfiles y compose existentes
- [x] `docker-compose.yml` para local/desarrollo
- [x] `docker-compose.prod.yml` para VPS/produccion con PostgreSQL
- [~] Variables de entorno cerradas por ambiente
- [ ] Guia de despliegue local y servidor
- [ ] Reverse proxy y TLS documentados

### Operacion
- [ ] Logs estructurados
- [ ] Retencion de logs
- [ ] Healthchecks completos
- [ ] Backup y restauracion de base y certificados
- [ ] Politica de manejo de secretos

### Observabilidad
- [ ] Metricas basicas
- [ ] Alertas operativas
- [ ] Trazabilidad de jobs
- [ ] Panel de estado interno o dashboard tecnico

## Fase 8 - Distribucion, releases y adopcion

Objetivo: profesionalizar la entrega del producto.

### Releases
- [ ] Changelog operativo consistente
- [ ] Versionado semantico o politica equivalente
- [ ] Paquetes o imagenes publicables
- [ ] Notas de release por version

### Distribucion
- [ ] Instalacion simplificada para terceros
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

- [ ] Produccion ARCA
- [ ] Exportaciones de reportes
- [ ] Envio de comprobantes por email
- [ ] Integraciones externas
- [ ] Dashboard de operacion mas rico
- [ ] Catalogos, stock o modulos complementarios si el producto lo justifica

## Prioridades inmediatas

1. Repetir la validacion con el lote definitivo del usuario y confirmar totales/puntos de venta antes de emitir
2. Ejecutar primera prueba real controlada con lote chico y punto de venta Web Services confirmado
3. Levantar entorno productivo con `docker-compose.prod.yml` y `.env.production`
4. Probar backup/restauracion de PostgreSQL, certificados y logs
5. Documentar evidencia del primer CAE productivo

## Criterio de exito del MVP

El MVP se considera cerrado cuando:

- una persona administrativa no tecnica puede emitir un comprobante individual sin ayuda tecnica
- una persona administrativa no tecnica puede emitir un lote por Excel sin soporte tecnico constante
- una persona administrativa no tecnica puede revisar el formato detectado y confirmar antes de emitir
- los comprobantes quedan autorizados con CAE en homologacion
- el usuario puede consultar comprobantes, ver PDF y operar reportes basicos
- la documentacion permite retomar el proyecto y operarlo sin reconstruir contexto desde cero

## Criterio de exito de largo plazo

FactuFlow deja de ser "solo un MVP" cuando ademas:

- soporta despliegues reproducibles
- soporta mas de una empresa y administracion central
- tiene estrategia clara de migraciones, observabilidad, soporte y releases
- puede ser usado por muchos usuarios sin depender del conocimiento historico de una sola persona
