# Flujo de desarrollo, despliegue y auditoría productiva

Este documento define el método público y reutilizable para trabajar con una
instalación productiva de FactuFlow en VPS sin exponer datos privados.

Los detalles concretos de una instalación real, como IP, dominio, usuario SSH,
rutas del servidor, nombres de contenedores, comandos exactos del reverse proxy,
ubicación de backups, certificados, claves y evidencia de diagnósticos, deben
quedar en documentación privada del entorno operativo. No deben versionarse en
este repositorio público.

## Principio general

El flujo recomendado es:

1. Desarrollar y probar en local.
2. Versionar en Git.
3. Publicar en GitHub.
4. Decidir explícitamente si ese cambió se despliega.
5. Actualizar el VPS a un commit o tag concreto.
6. Ejecutar QA post-deploy y documentar el resultado.

`git push` no significa despliegue. Producción se actualiza solo con una
decisión explícita.

## Roles de cada entorno

### Entorno local

El entorno local se usa para:

- desarrollo de funcionalidades y fixes
- tests automatizados
- reproducción de bugs con fixtures sintéticos, anonimizados o mínimos
- documentación pública sanitizada
- preparación de commits, tags y revisiones

El entorno local no debe operar simultáneamente con el VPS usando los mismos
certificados productivos. Si el VPS reemplaza la operación local, la base local
queda como histórico privado.

### GitHub

GitHub es la fuente de código público versionado.

Debe contener:

- código
- migraciones
- tests
- documentación general
- runbooks sanitizados
- ejemplos sin datos reales

No debe contener:

- `.env.production`
- certificados o claves privadas
- backups
- bases reales
- CUITs reales
- CAEs reales
- nombres reales de clientes o emisores
- Excel/PDF de clientes
- logs productivos
- evidencia privada de auditoría

### VPS

El VPS es el entorno productivo.

Debe tratarse como estado operativo sensible. Ahí viven la base real,
certificados reales, configuración privada, logs productivos y estado fiscal
vigente.

No se deben hacer cambios de código manuales permanentes en el VPS. Si aparece
una corrección urgente, primero debe registrarse el diagnóstico, luego llevarse
el fix al repo local, probarse, commitearse y desplegarse de forma controlada.

## Versionado y despliegue

La práctica recomendada es que producción corra un commit o tag identificable.

- `main` puede contener el último trabajo aceptado del proyecto.
- Un tag, por ejemplo `v0.2.1`, marca un punto desplegable o ya desplegado.
- Un tag publicado o desplegado es inmutable. No moverlo para incorporar fixes;
  cualquier cambio de código requiere una versión nueva.
- Una corrección exclusivamente documental posterior puede avanzar en `main` y
  en las notas de GitHub sin redesplegar ni mover el tag.
- El VPS debe registrar qué commit o tag está corriendo.
- La documentación privada del VPS debe registrar fecha de deploy, operador,
  commit/tag, commit de origen, comandos ejecutados, resultado de healthchecks y
  observaciones.

Para cambios chicos de documentación, puede no tener sentido desplegar al VPS.
Para cambios de backend, frontend, migraciones, Docker o configuración de
producción, el deploy debe decidirse explícitamente.

### Decidir un corte de release

La guía de candidatos vive en `ROADMAP.md > Guía flexible de cortes`. Es una
orientación revisable, no un calendario: un riesgo nuevo, una migración incierta
o un cambio de alcance puede dividir, adelantar o posponer el corte. No es
necesario terminar todo el roadmap.

Antes de declarar un candidato listo:

1. congelar una unidad funcional coherente y el rango exacto desde la versión
   productiva;
2. confirmar que no quedan P0 ni P1 bloqueantes conocidos dentro del alcance;
3. exigir CI verde sobre el commit candidato y cerrar las revisiones sensibles;
4. enumerar y ensayar migraciones, dependencias, configuración y rollback;
5. verificar backup/restauración, notas de release, upgrade y smoke;
6. decidir por separado si se crea el tag y si se despliega.

El roadmap utilizó `v0.2.2` como estabilización posterior a PF-01 y anterior a
PF-02. `v0.3.0` continúa como corte provisional después del cambio funcional de
PF-02; su nombre y alcance pueden cambiar si aparece nueva evidencia.

## Antes de desplegar

Antes de actualizar producción:

1. Confirmar que el diff no contiene secretos ni evidencia privada.
2. Ejecutar las pruebas relevantes al cambio.
3. Revisar `git status --short --branch`.
4. Commit y push del cambio aceptado.
5. Para cambios sensibles, considerar `autoreview` con confirmación explícita
   del usuario.
6. Si el cambio toca base, emisión, certificados, Docker o configuración,
   verificar que existe un backup recuperable reciente o generar uno manual.
7. Decidir el commit o tag exacto a desplegar.
8. Registrar el commit o tag que efectivamente corre en producción y comparar
   el rango completo con el objetivo, por ejemplo con
   `git diff --name-status <commit_desplegado>..<objetivo>`. Enumerar
   explícitamente migraciones Alembic, dependencias y lockfiles, Docker/compose,
   configuración y cambios de schema desde ese origen real; no inferirlos desde
   otro candidato local reciente. Revisar además `alembic current`, `heads` y la
   ruta pendiente de migraciones de la base productiva.
9. Confirmar que producción usa un único proceso Uvicorn mientras el worker de
   lotes siga embebido en el backend.
10. Confirmar `BATCH_WORKER_ENABLED=true` si la instalación permite procesar
    lotes en segundo plano.
11. Para PostgreSQL, revisar que el pool API esté dentro de `1..4`, con default y
    máximo `4`, overflow `0`, y que el worker tenga su pool dedicado de `1`.
    Confirmar también timeout de adquisición `5 s` y warning de retención `10 s`.
12. Ejecutar la prueba `integration` de capacidad contra PostgreSQL desechable,
    según `docs/agents/testing.md`. La prueba `4+1` no crea lotes ni llama a ARCA;
    su aprobación local no sustituye la verificación del commit/tag desplegado.

Si el cambio toca ARCA, WSFE, CAE, numeración, emisión individual, emisión
masiva, reintentos, reconciliación, certificados, puntos de venta, fechas
fiscales, migraciones fiscales o aislamiento por emisor, antes debe completarse
`docs/agents/fiscal-change-checklist.md`.

## Durante el despliegue

El despliegue debe hacerse desde la documentación privada del VPS, porque ahí
están los comandos reales y el contexto del host.

Reglas generales:

- No tocar servicios ajenos a FactuFlow.
- No imprimir secretos en consola o chat.
- No cambiar `.env.production` sin registrar el motivo en documentación privada.
- No borrar volúmenes ni backups salvo instrucción explícita y verificación de
  ruta.
- Si hay migraciones, ejecutarlas una sola vez y registrar el resultado.
- Si algo falla, detenerse, conservar logs y diagnosticar antes de reintentar.

### Migración inesperada o discrepancia de preflight

Si aparece una migración que el preflight no había anunciado:

1. Mantener el sitio en mantenimiento y no reabrir hasta decidir.
2. Determinar si la migración ya fue aplicada y registrar `alembic current`,
   `heads` y el rango pendiente.
3. Comparar el commit realmente desplegado antes del cambio con el target.
4. Leer `upgrade`, `downgrade`, `down_revision`, cambios de constraints y
   cualquier transformación o borrado de datos.
5. Verificar el backup mediante una restauración aislada cuando la migración
   toque schema o historial fiscal.
6. Continuar solo si la migración pertenece al rango aprobado, el target sigue
   siendo el deseado, schema/datos cumplen las invariantes y el runtime queda
   sano.
7. Elegir rollback si la migración está fuera del rango aprobado, rompe
   invariantes, deja datos inconsistentes o el target ya no es aceptable.

Nunca ejecutar un downgrade automático solo porque el prompt o preflight previo
fue incorrecto. Si la migración ya quedó aplicada, el rollback debe incluir una
estrategia explícita para schema y datos; cuando el downgrade sea destructivo o
incierto, restaurar el backup puede ser más seguro.

## Después del despliegue

La QA post-deploy mínima debe incluir:

- health público de frontend/backend
- `GET /api/health/worker` con un administrador: worker disponible y pools
  interpretados sin copiar DSN, credenciales, rutas privadas ni errores crudos
- en PostgreSQL, `separation_required=true` y `separated=true`; en SQLite,
  `separation_required=false` y engine compartido sin degradación
- login
- emisor activo
- listado básico de comprobantes
- certificados y puntos de venta visibles
- reportes básicos si el cambio los toca
- PDF si el cambio toca generación o dependencias nativas
- logs del backend sin errores nuevos y señal `Worker de lotes iniciado`
- `BATCH_WORKER_ENABLED=true` y un único proceso backend si se usa background
- sesiones API lazy y ausencia de warnings nuevos por timeout o retención; si la
  base devuelve `503`, respetar `Retry-After` y no exponer el error interno
- seguimiento de lotes con una sola solicitud en vuelo, intervalos `3/5/10 s` y
  backoff máximo de `15 s` ante fallos temporales
- servicios vecinos del host sin afectación, cuando comparten reverse proxy
- si se aplicaron migraciones, `alembic current` y `heads` alineados, invariantes
  de schema y constraints verificadas, datos básicos reconciliados y evidencia
  de restauración aislada del backup

Si se hacen validaciones ARCA, deben ser consultas seguras y explícitas, por
ejemplo `FECompUltimoAutorizado` o `FECompConsultar`. No se solicita CAE durante
QA salvo decisión fiscal explícita.

Una prueba PostgreSQL efímera aprobada, un build local o un health local no
demuestran despliegue. La evidencia post-deploy debe registrar el commit o tag
real y los resultados sanitizados del entorno, sin incluir credenciales ni
rutas privadas.

## Auditoría de errores productivos

Ante errores de emisión, lotes o inconsistencias productivas, la primera
auditoría debe mirar el VPS en modo solo lectura.

Orden recomendado:

1. Identificar lote, comprobante, emisor activo, punto de venta, tipo y fecha
   fiscal sin copiar datos privados al repo público.
2. Revisar estado local en la base productiva.
3. Revisar logs del backend alrededor del horario del incidente.
4. Revisar operaciones idempotentes e intentos fiscales.
5. Determinar si el problema ocurrió antes de ARCA, durante la llamada, después
   de recibir CAE o durante persistencia local.
6. Si hay incertidumbre fiscal, consultar ARCA con `FECompConsultar` o
   `FECompUltimoAutorizado` antes de reintentar.
7. Clasificar el caso: datos de entrada, formato, fecha fiscal, punto de venta,
   certificado, receptor, total, error ARCA, timeout, bug de código o fallo
   post-CAE.
8. Documentar el diagnóstico privado con datos suficientes para operar, pero
   sin llevar evidencia sensible al repositorio público.
9. Si hace falta código, reproducir localmente con datos mínimos o sintéticos,
   implementar el fix, probarlo y desplegarlo.

Regla crítica: nunca reintentar automáticamente una emisión fallida sin saber si
ARCA autorizó o no el comprobante.

## Documentación pública vs privada

En este repositorio público se documenta:

- método de trabajo
- reglas de seguridad
- flujo de desarrollo y deploy
- criterios de auditoría
- aprendizajes generales
- fixes de código o documentación sanitizada

En documentación privada se documenta:

- IP, dominio y usuario SSH
- rutas reales del stack
- comandos exactos del VPS
- ubicación de backups
- estado de servicios del host
- logs, CAEs, CUITs, comprobantes, clientes y evidencia privada
- diagnósticos operativos con datos reales

La regla práctica es: el repo público explica cómo operar FactuFlow; la
documentación privada sabe cómo operar una instalación concreta.
