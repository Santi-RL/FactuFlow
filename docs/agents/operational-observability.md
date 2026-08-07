# Observabilidad operativa estándar

Estado: decisión vigente desde 2026-05-22.

Última actualización: 2026-08-07.

## Objetivo

FactuFlow ya fue usado en producción real. Antes de ampliar el uso productivo,
el sistema debe poder explicar qué pasó en una operación importante sin depender
de memoria manual ni de revisar la base a ciegas.

Esta etapa no busca monitoreo complejo. Busca diagnóstico operativo claro,
simple y accionable para usuarios administrativos, soporte y desarrollo.

## Principio de producto

- Los mensajes deben estar escritos para usuarios no técnicos.
- Si algo falla, la pantalla debe explicar qué pasó, qué impacto tiene y cuál
  es el próximo paso seguro.
- No mostrar opciones técnicas sin explicación.
- No usar términos internos como única respuesta. Si aparece un dato técnico,
  debe tener una descripción simple.
- No mezclar datos entre emisores. Todo diagnóstico debe indicar o respetar el
  emisor activo correspondiente.
- No copiar CUITs, CAEs, datos de clientes, Excels, PDFs ni logs privados en
  documentación versionada.

## Alcance obligatorio

### 1. Registro claro de operaciones críticas

Cada operación importante debe dejar una pista suficiente para reconstruir que
ocurrio:

- usuario que inicio la acción
- emisor activo usado
- lote, comprobante o recurso afectado
- punto de venta cuando aplique
- fecha fiscal cuando aplique
- estado inicial y estado final
- si el error ocurrio antes de llamar a ARCA, durante la llamada o después de
  una respuesta de ARCA
- código o identificador de seguimiento para soporte

### 2. Trazabilidad visible de lotes

Los lotes deben mostrar estados entendibles:

- pendiente
- en cola
- procesando
- completado
- completado parcial
- fallido
- requiere reconciliacion

Cuando un lote quede en error, el usuario debe poder entender si puede corregir
el archivo, reintentar, esperar al worker o pedir soporte. Si existe
incertidumbre después de ARCA, no debe sugerirse un reintento automático sin
reconciliación.

El seguimiento activo usa una allowlist de estado y contadores, no el detalle
completo. La UI mantiene una sola solicitud en vuelo y consulta cada `3 s`
durante `30 s`, cada `5 s` hasta los `2 min` y luego cada `10 s`. Los errores
temporales aplican backoff hasta `15 s`; una respuesta satisfactoria restaura el
intervalo base. Un fallo temporal de seguimiento no demuestra que el lote haya
desaparecido.

### 3. Estado del sistema en la interfaz

Debe existir una pantalla o panel de `Estado del sistema` con lenguaje simple.
Como mínimo debe informar:

- aplicación backend disponible
- base de datos disponible
- worker de lotes y separación de capacidad entre API y worker
- conexión ARCA según ambiente
- certificado activo del emisor seleccionado
- vencimiento o problema visible del certificado
- uso de almacenamiento de la instalación, con desglose por emisor y tipo de
  dato, cuando el usuario sea administrador
- ubicación o acceso a logs relevantes cuando sea seguro
- último backup conocido o aviso de backup no verificado, cuando esa evidencia
  exista

Los estados visibles deben usar etiquetas simples como `Correcto`,
`Necesita atención` y `No disponible`, con una explicación corta.

El corte local de observabilidad incorpora `GET /api/health/worker`, exclusivo
para administradores. Su respuesta usa una allowlist de estado y métricas: no
expone DSN, credenciales, SQL, rutas privadas ni errores internos crudos.

Con PostgreSQL, `separation_required=true`: el pool API tiene capacidad
predeterminada y máxima de `4`, overflow `0`, y puede reducirse dentro de
`1..4`; el worker conserva un pool dedicado de `1`. El timeout de adquisición
es `5 s` y una conexión retenida por `10 s` genera una advertencia sanitizada.
Las sesiones API son lazy y recién ocupan una conexión al ejecutar el primer SQL
necesario, incluida la autenticación. Los timeouts y desconexiones de base
devuelven `503` sanitizado.

Con SQLite, `separation_required=false`: API y worker comparten un único engine
por diseño, por lo que `separated=false` no es degradación. `Sistema > Estado`
traduce estas reglas a un diagnóstico simple del worker y los pools.

La capacidad PostgreSQL `4+1` se validó con una instancia efímera, sin crear
lotes ni llamar a ARCA. Esta evidencia no declara un despliegue; cada entorno
debe verificarse contra el commit o tag que realmente ejecuta.

La vista administrativa también incluye `Sistema > Almacenamiento`: muestra uso
medido, recuperable, límite configurado, espacio libre de disco, categorías y
uso por emisor, y permite resguardar/descargar antes de liberar artefactos no
vitales.

### 3.1. Conectividad visible y recuperación segura

PF-17 planifica una señal global y no invasiva para que una persona usuaria
pueda distinguir entre una pantalla cargando, una conexión inestable, el
servidor de FactuFlow no disponible y una recuperación en curso. Esta sección
define el contrato futuro; no declara que la capacidad esté implementada.

- La detección debe combinar los eventos del navegador como indicio con el
  healthcheck real, errores de API y fallos al cargar vistas diferidas.
- El costo debe ser mínimo: usar el healthcheck liviano solo con la pestaña
  activa, suspender comprobaciones en segundo plano y aplicar backoff después de
  un fallo. No agregar monitoreo externo, telemetría pesada ni polling agresivo.
- La interfaz debe mostrar un aviso persistente y accesible, explicar el
  impacto, ofrecer una acción segura y confirmar la recuperación sin apilar
  notificaciones duplicadas.
- FactuFlow no operará offline: no se guardarán formularios, payloads, datos
  fiscales o evidencia privada para reenvío posterior, ni se crearán colas
  locales o service workers de operaciones.
- Ninguna escritura, emisión, solicitud de CAE, reintento o reconciliación puede
  repetirse automáticamente. Una pérdida de conexión posterior a una acción
  fiscal debe conservar el estado de incertidumbre y orientar a verificar o
  reconciliar, nunca a recargar o volver a emitir.
- Los reintentos automáticos quedan limitados a healthchecks y lecturas
  expresamente seguras. Cualquier recuperación de una mutación requiere el
  contrato idempotente y la decisión específica de su flujo.

Este trabajo pertenece a la banda C del portafolio y depende de los contratos
de errores de PF-14, las señales sanitizadas de PF-15 y las garantías fiscales
de PF-01. No desplaza las prioridades inmediatas vigentes.

### 4. Backups y restauración probados

Antes de ampliar volumen productivo, debe existir un procedimiento probado para:

- backup de PostgreSQL
- backup de certificados y claves
- backup de configuración productiva
- restauración en entorno controlado
- verificacion posterior de que la aplicacion levanta y puede consultar datos

La documentación debe explicar el procedimiento paso a paso y con advertencias
claras sobre datos privados.

### 5. Logs útiles para soporte

Los logs deben servir para diagnosticar sin exponer datos privados en el repo.
Deben permitir correlacionar una operación con:

- emisor interno
- usuario interno
- lote o comprobante
- job o worker involucrado
- error local o error ARCA

Los logs privados quedan fuera de Git. La documentación versionada solo debe
describir donde se generan y como usarlos de forma segura.

### 6. Runbook de diagnostico

Debe existir una guia de soporte con casos comunes:

- la aplicacion no inicia
- no se puede iniciar sesión
- ARCA no responde
- certificado vencido o no autorizado
- lote trabado o parcial
- comprobante con incertidumbre post-ARCA
- backup o restauración requerida

Cada caso debe indicar pasos concretos, en orden, y cuando detenerse para evitar
acciones fiscales riesgosas.

Primeros cortes visibles:

- Desde 2026-06-28, `Sistema > Estado` incluye una guía rápida de soporte con
  casos frecuentes, qué revisar, próximo paso seguro y cuándo detenerse.
- Desde 2026-06-29, `Sistema > Estado` incluye una ficha para soporte con los
  datos seguros mínimos para diagnosticar incidentes sin copiar CUIT completo ni
  evidencia privada a documentación versionada.
- `docs/agents/support-runbook.md` contiene el primer runbook público y
  sanitizado de diagnóstico operativo.

El health dedicado de worker ya forma parte del corte local. Siguen pendientes
la señal automática de backup, mayor trazabilidad histórica y la documentación
privada de cada instalación. La presencia de este contrato en el repositorio no
debe interpretarse como evidencia de despliegue.

## Fuera de alcance por ahora

Estas herramientas pueden venir después, pero no son requisito de esta etapa:

- Grafana, Prometheus o dashboards técnicos avanzados
- alertas automáticas externas
- monitoreo distribuido
- trazas distribuidas
- centralizacion completa de logs

## Criterio de completado

La observabilidad operativa estándar queda lista cuando una persona de soporte o
un usuario administrativo puede responder, desde la interfaz y la documentación:

1. Que emisor estaba activo.
2. Que lote o comprobante se intento operar.
3. Que estado tiene ahora.
4. Si ARCA fue llamada o no.
5. Si hay incertidumbre fiscal o no.
6. Donde mirar el detalle seguro.
7. Que acción corresponde hacer ahora.
