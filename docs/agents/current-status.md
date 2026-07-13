# Estado actual

Última actualización: 2026-07-13

Este documento es el handoff operativo canónico y deliberadamente breve. El
historial de versiones vive en `CHANGELOG.md`; las auditorías fechadas y las
lecciones de herramientas viven en `docs/project/**`.

## Cierre local — P1 UI, pool y worker

El P1 estructural quedó implementado y validado localmente el 2026-07-10. Sus
commits ya están publicados en `main`, pero no desplegados; `v0.2.1` continúa
como versión productiva.

Decisiones cerradas:

- PostgreSQL usa un pool API configurable entre `1` y `4`, sin overflow, y un
  pool dedicado de una conexión para el worker; el timeout es `5 s` y la
  advertencia de retención comienza en `10 s`;
- las sesiones API son lazy: una petición sin credenciales o sin SQL no ocupa
  conexiones. Los timeouts o desconexiones no controlados responden `503` con
  mensajes sanitizados;
- SQLite conserva un único engine compartido por diseño y esa topología no se
  presenta como degradada;
- el worker permanece estrictamente secuencial y expone a administradores salud
  y métricas allowlist, sin DSN, credenciales, SQL ni errores crudos;
- el polling usa una proyección mínima de estado, una sola solicitud en vuelo,
  intervalos de `3/5/10 s`, backoff de hasta `15 s` y guards ante cambios de
  emisor, ruta o componente; los lotes pequeños encolados conservan modo
  background real;
- el corte no cambia CAE, numeración, fecha fiscal, confirmación irreversible,
  idempotencia ni reconciliación.

Validación del corte:

- backend completo: `443` tests aprobados y `2` omitidos; uno requiere permiso
  de symlink en Windows y el otro es el harness PostgreSQL cuando no se entrega
  una URL desechable;
- harness PostgreSQL ejecutado por separado: aprobado con cuatro conexiones API
  retenidas, una conexión worker independiente y timeouts correctos para la
  quinta API y segunda worker, sin tablas, lotes, certificados ni llamadas ARCA;
- frontend: `121` tests completos y `29` tests enfocados aprobados después del
  ajuste contractual; ESLint, type-check y build limpios;
- Ruff, Black y `git diff --check` aprobados sobre el estado final.
  Browserslist solo informó datos desactualizados.

Durante la validación original no se ejecutaron Clawpatch fix, push ni
despliegue. El cierre fiscal posterior quedó integrado en `e175b77` y luego fue
publicado en `main`; no se desplegó como una nueva release y su QA
manual/productiva continúa pendiente.

### Corrección local posterior — frontera DB/FECAE

Quedó implementada y validada localmente una corrección puntual de manejo de
indisponibilidad temporal de base:

- pre-ARCA solo se responde `503` con `Retry-After: 2` tras confirmar
  durablemente recuperación segura y cero intentos. La operación pasa
  `en_proceso -> interrumpida_pre_arca`; el replay con la misma clave hace CAS a
  `en_proceso` y solo uno gana;
- en individual, lote síncrono y reintento sin intentos, el lote vuelve a
  `validado` o el grupo exacto a `fallido`. Con intento existente o recuperación
  no persistible responde `409 pre_arca_estado_bloqueado`, conserva la clave y
  exige revisar/esperar, sin reconciliación ARCA porque FECAE no comenzó;
- el worker pre-ARCA solo devuelve el lote a `en_cola` sin intentos, conserva la
  operación `en_proceso` para impedir replay HTTP paralelo y corta el ciclo.
  Post-ARCA conserva `409`, reconciliación y ausencia de retry;
- `get_db` preserva la excepción primaria aunque fallen `rollback` o `close`; un
  `409` post-ARCA no se degrada a `503` por cleanup;
- `IntegrityError` conserva el comportamiento anterior. No cambian fecha,
  numeración, payload, UI, migraciones ni aislamiento multiemisor.

Las pasadas intermedias de `autoreview` detectaron P1 válidos sobre persistencia
de rechazos, estado ORM posterior a rollback, fronteras pre-ARCA y ownership de
creaciones ambiguas. Todos fueron aceptados y corregidos dentro del mismo corte.

El cierre final quedó así:

- commit `e175b77` (`fix: preserve fiscal state on database outages`);
- backend completo: `487` tests aprobados y `2` omitidos;
- suites de API: `120` tests aprobados;
- Ruff, Black y `git diff --check`: limpios;
- `autoreview` final con `gpt-5.6-sol`, thinking `high`: limpio, sin findings
  accionables, con probabilidad `0,87` de patch correcto.

`8b311b5` y `e175b77` ya son ancestros de `origin/main`. La planificación
posterior avanzó `main` hasta `4b4c210`, punto sincronizado con `origin/main`
antes de iniciar PF-01A.1. Esos cambios posteriores al tag no forman una nueva
release ni fueron desplegados. `v0.2.1` continúa como versión productiva y la QA
manual/productiva de ese corte sigue pendiente.

## Snapshot vigente

- Versión productiva: `v0.2.1`.
- Tag desplegado e inmutable:
  `8099b223f3be7342dbb29367d24c6209dee93a58`.
- La release quedó desplegada y aceptada el 2026-07-10.
- `origin/main` avanzó hasta `f9d170a`: incluye PF-01A/PF-01B, el
  endurecimiento de pools/worker, la frontera DB/FECAE y su cierre documental.
  Su CI `29275715128` aprobó seguridad, backend, frontend y E2E. Ninguno de
  estos cortes posteriores al tag implica un nuevo despliegue.
- Producción quedó sana después de backup, restauración aislada, migración,
  smoke checks y QA manual autenticada con emisión fiscal real satisfactoria.
- La evidencia concreta del VPS permanece en documentación operativa privada.

### Candidato v0.2.2

`main` prepara el candidato `0.2.2` con alcance funcional congelado después
de PF-01 y antes de PF-02. El baseline publicado es `f9d170a`; el versionado,
changelog y dossier de upgrade están en preparación local. Producción continúa
en `v0.2.1`: no existe tag, release ni despliegue `v0.2.2`.

El rango incorpora una migración fiscal (`a8b9c0d1e2f3`), Pillow `12.3.0` y
variables nuevas de pool. El versionado local aprobó lint, type-check, Black,
`531` pruebas backend, `127` frontend, `3` de scripts y build. La primera
pasada de `autoreview gpt-5.5 high` detectó un P2 válido: dos manifiestos
backend conservaban `0.2.1`. El hallazgo se aceptó y corrigió; la segunda
pasada quedó limpia, sin findings, con confianza `0,82`.

Antes de etiquetar faltan publicar el commit candidato y obtener CI verde,
confirmar en privado el backup portable, restaurar una copia,
ejecutar el preflight de las cinco categorías legacy y decidir explícitamente
el tag. El despliegue requiere una autorización posterior separada. El dossier
vigente es `docs/project/releases/v0.2.2-candidate.md`.

## Estado del producto

FactuFlow está operativo para facturación electrónica ARCA individual y masiva,
con:

- FastAPI, Vue, PostgreSQL productivo y Alembic como camino canónico de esquema;
- emisión individual y por lotes con fecha fiscal explícita, confirmación
  irreversible e idempotencia;
- reconciliación segura de estados inciertos y bloqueo de reintentos cuando ARCA
  pudo haber autorizado;
- certificados, WSAA/WSFE, puntos de venta, clientes, comprobantes, PDFs,
  reportes, perfiles y plantillas;
- varios emisores con uno activo por vez;
- administradores con acceso operativo a todos los emisores y gestión de
  usuarios, emisores y `Sistema`;
- usuarios comunes limitados al emisor asignado;
- worker embebido para lotes, con `BATCH_WORKER_ENABLED=true` y un único proceso
  Uvicorn en la instalación productiva actual;
- PDFs bajo demanda y gestor administrativo de almacenamiento.

Las reglas no negociables siguen en `VISION.md` y `AGENTS.md`. En particular:
la fecha fiscal nunca se completa con la fecha actual, ninguna ruta puede pedir
CAE sin confirmación explícita y los datos de emisores distintos no se mezclan.

## Validación vigente de v0.2.1

- Backend: 411 tests aprobados y 1 omitido según su marca preexistente.
- Frontend: 111 tests aprobados; ESLint, type-check y build limpios.
- Scripts raíz: 3 tests aprobados.
- GitHub Actions del tag `8099b22`: Security Audit, Frontend Build, Backend Tests
  y E2E Tests aprobados.
- GitHub Actions del cierre documental `ece2bdf`: los mismos cuatro jobs
  aprobados.
- `autoreview` acumulado del ciclo: GPT-5.5 en `high` sin hallazgos accionables.
- QA productiva manual: login autenticado y emisión fiscal real satisfactoria.
- Alembic productivo: `current` y `heads` en `f7a8b9c0d1e2`.

## Estado Clawpatch

El ciclo 2026-07-07/10 que formó `v0.2.1` continúa cerrado y desplegado. El
2026-07-12 se ejecutó una auditoría nueva, completa y ordenada sobre el código
actual con Clawpatch `0.7.0`, Codex `gpt-5.6-sol`, razonamiento `high` y sin
aplicar fixes.

Los checkpoints integrados PF-01A/PF-01B del 2026-07-13 dejaron el estado local
ignorado así:

- repo: 15 abiertos, 4 `high`, 4 `medium` y 7 `low`;
- backend: 96 abiertos, 20 `high`, 52 `medium` y 24 `low`;
- frontend: 29 abiertos, 5 `high`, 20 `medium` y 4 `low`.

R02, B03, B04, B24, B10 y B17 se revalidaron secuencialmente como `fixed` con
Clawpatch `0.7.0`, Codex `gpt-5.6-sol` y razonamiento `high`. No hubo
resultados inciertos, falsos positivos nuevos, locks, `clawpatch fix` ni
llamadas reales a ARCA. Los contadores restantes siguen siendo un ledger
acumulativo, no una lista de bugs confirmados.

La adjudicación original confirmó 33 problemas únicos: 20 P1, 12 P2 y un
finding rechazado; además identificó tres registros duplicados entre slices.
No se confirmó ningún P0 ni P3 entre los `high`.

La evidencia detallada permanece en `.tmp/clawpatch/2026-07-12/` y los reportes
post-PF-01A en `.tmp/clawpatch/2026-07-13/`, ambos ignorados por Git. No
reparar en masa, no usar el contador global como backlog ejecutable y no borrar
ni reinicializar `.clawpatch/` sin decisión explícita.

La guía canónica es `docs/project/audits/clawpatch/README.md`. Los cierres
sanitizados están en
`docs/project/audits/clawpatch/2026-07-12-cierre-auditoria-ordenada.md`,
`docs/project/audits/clawpatch/2026-07-13-cierre-checkpoint-pf-01a.md` y
`docs/project/audits/clawpatch/2026-07-13-cierre-checkpoint-pf-01b.md`.
El portafolio que integra estos hallazgos con el roadmap está en
`docs/agents/development-portfolio.md`.

## Riesgos y pendientes priorizados

### P1 fiscal siguiente

No apareció un P0. PF-01A.1, PF-01A.2 y PF-01A.3 ya están publicados en
`origin/main`. La UI de emisión individual
detecta el `409` fiscal estructurado, conserva en memoria una copia inmutable del
payload y la misma clave idempotente, bloquea edición, cancelación, navegación,
doble envío y verificación bajo otro emisor, y ofrece `Verificar estado` con la
operación exacta. Solo una autorización o un rechazo final HTTP `400` desbloquean
la pantalla; `409`, red y fallos no concluyentes mantienen el bloqueo.

La operación pendiente no se guarda en `localStorage` ni `sessionStorage` para no
persistir datos fiscales o privados en el navegador. Se advierte antes de cerrar
o recargar; una recarga forzada puede perder el estado visual, pero no la
autoridad durable del backend. En ese caso no debe crearse otra emisión: hay que
pedir revisión o soporte con el emisor original.

Validación de PF-01A.1:

- commit `bd0d817` publicado en `origin/main`; ejecución de GitHub Actions
  `29221936407` aprobada en Frontend Build, Backend Tests, Security Audit y E2E
  Tests;
- backend completo: `498` tests aprobados y `2` omitidos por marcas
  preexistentes;
- suite ARCA: `85` tests aprobados; servicio de facturación: `39` aprobados;
- Ruff y Black: limpios sobre `app` y `tests`; `git diff --check`: limpio;
- `autoreview` efectivo con `gpt-5.5`, thinking `high`: patch correcto, confianza
  `0,86` y sin findings accionables. `gpt-5.6-sol` se intentó dos veces, pero el
  motor exigió una versión más nueva del binario local de Codex y no revisó.

Validación de PF-01A.2:

- commit `ae18856` publicado en `origin/main`; ejecución de GitHub Actions
  `29226385118` aprobada en Frontend Build, Backend Tests, Security Audit y E2E
  Tests;
- backend completo: `503` tests aprobados y `2` omitidos por marcas
  preexistentes; regresión enfocada final de WSFE, servicio, API y lotes: `189`
  tests aprobados;
- Ruff y Black: limpios sobre `app` y `tests`; `git diff --check`: limpio;
- dos findings P2 intermedios de `autoreview` se aceptaron, corrigieron y
  cubrieron; la revisión final efectiva con `gpt-5.5 high` quedó limpia, sin
  findings accionables y con confianza `0,82`;
- no hubo llamadas reales a ARCA ni se ejecutó Clawpatch en el microcorte.

Validación de PF-01A.3 y cierre integrado:

- pruebas unitarias enfocadas: `17` aprobadas; suite frontend completa: `127`
  aprobadas;
- E2E enfocado del replay exacto: aprobado; suite E2E completa: `33` aprobadas;
- ESLint, type-check y build: limpios; Browserslist solo informó datos
  desactualizados;
- `autoreview` efectivo con `gpt-5.5 high` detectó un P1 válido sobre el rechazo
  final HTTP `400`; se corrigió y la segunda pasada quedó limpia, con confianza
  `0,80`;
- PF-01A.3 se publicó como `578a15a`. La CI `29244681533` aprobó backend,
  frontend y E2E, pero detectó cinco avisos de Pillow `12.2.0`;
- `82d4245` actualizó Pillow a `12.3.0` y `2c8ac72` sincronizó la documentación.
  El intento 2 de la CI `29245900987` aprobó Security Audit, Backend Tests,
  Frontend Build y E2E Tests; el intento 1 se canceló porque el runner quedó
  atascado más de veinte minutos al descargar Playwright;
- Clawpatch revalidó R02, B03, B04 y B24 como `fixed` con `gpt-5.6-sol high`.
  No hubo resultados inciertos, correcciones automáticas ni llamadas reales a ARCA.

PF-01B.2 quedó publicado como `f1219b7`; su CI `29268679829` aprobó Security
Audit, Backend Tests, Frontend Build y E2E Tests. PF-01B.3 se publicó como
`6625254`; su CI `29270728104` volvió a aprobar los cuatro jobs y el harness
reproducible validó PostgreSQL 16 efímero con datos sintéticos: upgrade, tres
checks, índice parcial, todos los estados, coherencia CAE, liberación terminal,
dos transacciones concurrentes con un único ganador, downgrade y preflight con
las cinco categorías ambiguas.

La integración PostgreSQL aprobó `4` pruebas; el backend completo aprobó `531` y
omitió `4` según configuración. Ruff, Black y `git diff --check` quedaron
limpios. `autoreview` con `gpt-5.5 high` quedó sin findings accionables y con
confianza `0,82`. El contenedor no tuvo volumen persistente y fue eliminado.
Clawpatch `0.7.0` revalidó B10 y B17 secuencialmente como `fixed` con
`gpt-5.6-sol high`; no se usó `clawpatch fix`. No hubo llamadas reales a ARCA
ni cambios de UI, numeración global o historia externa. PF-01 quedó cerrado.

### Backlog Clawpatch priorizado

Los 20 P1 únicos se ordenaron así: PF-01A, PF-01B, PF-03, PF-06/PF-07,
PF-08 y PF-09. Los 12 P2 quedan agrupados en PF-04, PF-09, PF-10, PF-11,
PF-13 y PF-16. El detalle público se mantiene sanitizado en
`docs/agents/development-portfolio.md`; los IDs y la evidencia permanecen en el
reporte local ignorado.

No reparar en masa ni por severidad automática. Cada corte conserva su diseño,
pruebas, documentación y revisión separados; no se ejecutará `clawpatch fix`
para trabajo fiscal, migraciones, certificados, aislamiento o borrados.

### Operación privada

Confirmar en la documentación privada si la clave portable del backup cifrado
ya está guardada en un gestor de contraseñas. El repo público no puede afirmar
ese estado.

Siguen pendientes:

- automatización de backups cifrados, retención y alertas;
- recuperación ensayada hacia un VPS nuevo;
- señal visible del último backup;
- trazabilidad operativa más completa;
- QA del gestor de almacenamiento en VPS con datos de prueba controlados;
- descarga masiva de PDFs sin persistencia permanente en el servidor.

## Punto exacto para retomar

1. Leer `docs/agents/alignment-pending.md`. Su estado actual es `COMPLETADO`; si
   sigue así, no hay conflicto de alineación que anunciar.
2. Leer `VISION.md`, este documento y las prioridades de `ROADMAP.md`.
3. Revisar `git status --short --branch` y comparar con `origin/main` antes de
   editar.
4. No repetir el despliegue, la configuración de certificados productivos ni
   los cuatro cortes UX de carga masiva: están cerrados.
5. La adjudicación de los 36 `high` está completada. No repetirla ni usar
   `clawpatch fix`; consultar el portafolio y el reporte local si hace falta
   rastrear una decisión.
6. PF-01A está cerrado: los tres cortes, el parche de Pillow, la CI final y las
   revalidaciones R02/B03/B04/B24 están completos. No repetir ni ampliar ese
   checkpoint.
7. PF-01 está cerrado: PF-01A y PF-01B fueron publicados, sus CI quedaron
   verdes y R02/B03/B04/B24/B10/B17 figuran `fixed` en Clawpatch. No repetir
   esos checkpoints.
8. Completar el candidato `v0.2.2` antes de mezclar PF-02: la validación local
   está verde y el P2 de versionado de la primera pasada de `autoreview` fue
   corregido; la pasada final quedó limpia. Falta publicar el commit y exigir
   CI verde. No crear tag todavía.
9. Después, completar en privado backup/restauración y preflight. Crear el tag
   solo con decisión explícita y desplegar únicamente con otra autorización.
   Si el corte se difiere explícitamente, continuar PF-02 y luego PF-03,
   PF-06/PF-07, PF-08 y PF-09 según el portafolio.
10. Para próximas pasadas de `autoreview`, usar directamente `gpt-5.5` con
    `high`; no intentar antes `gpt-5.6-sol` salvo nueva indicación explícita.

## Referencias de continuidad

- Visión protegida: `VISION.md`
- Prioridades: `ROADMAP.md`
- Portafolio integrado: `docs/agents/development-portfolio.md`
- Diseño PF-01A: `docs/agents/pf-01-authorization-integrity-design.md`
- Diseño PF-01B: `docs/agents/pf-01b-persistence-integrity-design.md`
- Cierre Clawpatch PF-01B:
  `docs/project/audits/clawpatch/2026-07-13-cierre-checkpoint-pf-01b.md`
- QA manual vigente: `docs/agents/manual-qa.md`
- Historial: `CHANGELOG.md`
- Flujo productivo: `docs/agents/production-workflow.md`
- Candidato v0.2.2: `docs/project/releases/v0.2.2-candidate.md`
- Checklist fiscal: `docs/agents/fiscal-change-checklist.md`
- Clawpatch: `docs/project/audits/clawpatch/README.md`
- Cierre v0.2.1:
  `docs/project/audits/clawpatch/2026-07-10-cierre-ciclo-v0.2.1.md`
