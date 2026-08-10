# Estado actual

Última actualización: 09/08/2026

Este documento es el handoff operativo canónico y deliberadamente breve. El
historial de versiones vive en `CHANGELOG.md`; las auditorías fechadas y las
lecciones de herramientas viven en `docs/project/**`.

## Puerta documental reforzada

La documentación viva fue contrastada con `main`, la release publicada y el tag
productivo. El proceso exige ahora una revisión semántica después de estabilizar
código/tests y antes de staging/commit, una segunda comprobación del rango antes
de marcar el PR como listo y una verificación de `main` posterior al merge.

`npm run docs:check` agrega una defensa estructural en todos los niveles de CI:
comprueba versiones, `CHANGELOG.md > Unreleased` y estados transitorios
inequívocos. No reemplaza la matriz documental ni la lectura humana. También se
exige enumerar todos los consumidores de helpers compartidos; este control evita
repetir el punto ciego que ocultó el comportamiento real de los reintentos
manuales durante PF-02A/PF-02B.1.

La comprobación posterior a PF-02B.2 confirmó esa frontera: la puerta
estructural estaba verde mientras `overview`, la guía API y la evidencia de
testing conservaban afirmaciones anteriores. La matriz de PR separa ahora esos
tres consumidores documentales y prohíbe declarar `No aplica` solo porque el
contrato HTTP o los comandos de test no hayan cambiado.

El PR `#21` alineó ese corpus y reforzó la matriz documental. Su CI y la CI
post-merge `31052652891` aprobaron los seis checks obligatorios; `main` quedó
limpio y sincronizado en `8f25d361` antes de iniciar PF-02B.3.

El cierre aprobó `npm run docs:check`, `16` pruebas de scripts y la matriz local
completa: `539` backend con `4` omisiones configuradas, `131` frontend y `33`
E2E, además de lint, formato, tipos, build y auditorías productivas. No hubo
operaciones fiscales reales ni llamadas ARCA de escritura.

## PF-19 priorizado — PF-19C integrado en el candidato; puertas externas pendientes

Los diagnósticos privados del 07/08/2026 sobre `v0.2.2` no muestran un P0 ni
comprobantes autorizados incorrectamente, pero sí un P1 fiscal nuevo. Un punto
marcado de forma genérica como Web Services llegó a `FECAESolicitar` y ARCA
devolvió el error global excluyente `10005`, que exige un punto RECE. FactuFlow
convirtió ese rechazo de cabecera en `arca_batch_sin_respuesta` y dejó los
intentos como `requiere_reconciliacion`, aunque no hubo autorización.

La causa raíz queda en PF-19, separada de líneas ya cerradas o planificadas:

- PF-02 permanece cerrado y no cambia numeración, reservas ni segundo preflight;
- PF-03B conserva ítems, descuentos y valores no finitos, pero pasa detrás de
  esta evidencia productiva;
- PF-19A cerró estados, consumidores, contención explícita e inventario legacy
  en modo lectura. La guarda bloquea por ambiente, emisor, ID/número de punto y
  tipo antes de intento/FECAE; el inventario no modifica estados;
- PF-19B completa sus tres subcortes como una sola unidad: ledger y cabeza
  durable, migración fail-closed, atestación administrativa productiva,
  snapshots/guardas en todos los caminos fiscales y estados visibles en API/UI;
- PF-19C, incorporado por el candidato, completa el contrato: solo `10005` entero exacto bajo
  cabecera global estricta puede ser terminal; lo desconocido, mixto, parcial o
  contradictorio requiere reconciliación. El `autoreview` final autorizado
  cerró limpio con Codex `gpt-5.6-sol medium`; aún faltan PostgreSQL y Runtime
  Smoke reales en CI, CI atribuible al SHA final, aceptación PF-16G y ensayo
  privado de backup/restauración/upgrade/rollback;
- PF-11/PF-15 incorporan la evidencia exacta del backup preoperación y la
  trazabilidad que distingue aborto pre-FECAE, rechazo e incertidumbre real.

PF-19B queda cerrado en `main`: cada punto posee elegibilidad versionada por
ambiente y solo una cabeza efectiva `verificado_rece` puede avanzar hacia CAE.
Los puntos legacy migran como
`no_verificado`; Web Services genérico y `FEParamGetPtosVenta` no acreditan
RECE. La sincronización se resuelve en el servidor y modifica únicamente estado
técnico. Solo un administrador activo en un servidor productivo puede promover
producción mediante una constancia de hasta siete días, señal exacta y
confirmación expresa de procedencia; FactuFlow conserva hash y metadatos
probatorios mínimos, no el PDF. Homologación permanece fail-closed porque no
existe una fuente probatoria específica.

Los badges `Verificado RECE`, `No RECE` y `No verificado`, la procedencia y la
vigencia quedan visibles; perfiles, Excel y selectores usan el estado efectivo.
Individual, lotes, worker, fallback, reintentos y stale comparten snapshots,
revalidaciones y guardas durables antes de `FECAESolicitar`. PF-19A continúa como denegación
adicional y no puede promover un punto. PF-19B todavía no pertenece a una
release ni está desplegado: la release publicada y producción continúan en
`v0.2.2`. PF-19C está incorporado por el candidato y no está desplegado; hasta cerrar
sus puertas externas y autorizar un despliegue no deben reintentarse lotes
afectados ni sanearse registros legacy de forma manual.

## PF-03A — contrato superior estricto de emisión

PF-03A inicia PF-03 con una frontera pequeña y completa. El objeto superior de
`EmitirComprobanteRequest` prohíbe claves desconocidas: una errata fiscal
devuelve `422 extra_forbidden` antes de crear una operación idempotente, reservar
numeración, persistir intentos o invocar el servicio de facturación. Los campos
conocidos, la fecha fiscal explícita, el aislamiento por emisor y los valores
predeterminados vigentes no cambian.

Los payloads batch canónicos continúan revalidándose en procesamiento, worker,
reintento manual, stale y reconciliación. Si un snapshot histórico o manipulado
contiene una clave superior desconocida, falla cerrado sin solicitar CAE: el
reintento conserva el grupo sin número, CAE ni comprobante, y el preflight stale
mixto bloquea todos los grupos antes de consultar numeración. Si
`FECompConsultar` ya confirma una autorización, el intento conserva CAE y
vencimiento en `requiere_reconciliacion` sin reconstruir el comprobante desde el
payload inválido. No hay modelos, migraciones, rutas ni cambios de UI.

La UI todavía serializa `subtotal` como propiedad derivada del ítem. Por eso
PF-03A no endurece los modelos anidados: PF-03B debe separar primero el DTO de
escritura y luego validar ítems, descuentos y valores no finitos entre UI, API y
servicio. La matriz aprobó `9` casos enfocados, `29` de API, `50` del servicio de
facturación, `118` de lotes y el backend completo con `566` aprobados y `4`
omitidos. La puerta completa agregó `131` frontend, `16` de scripts, `5` de
seeds y `33` E2E; Ruff, Black, type-check, lint, build, `docs:check`,
`pip-audit` y `npm audit --omit=dev` quedaron verdes. Se usaron datos
sintéticos; no hubo emisiones reales, solicitudes de CAE, migraciones ni
llamadas ARCA de escritura. `autoreview --mode local` usó efectivamente Codex
`gpt-5.6-sol` con thinking `medium`: TruffleHog quedó limpio y las dos pasadas
terminaron sin findings accionables, con probabilidad `0,99` de patch correcto
y sin fallback.

## PF-02B.3 — recuperación stale compatible con historia externa

PF-02B.3 cierra PF-02 sin ampliar el alcance de PF-05. Un lote `procesando`
vencido continúa tratando la expiración solo como señal de diagnóstico: primero
reconcilia evidencia local fuerte y separa grupos intactos de grupos con
evidencia fiscal. Si todos los pendientes son realmente intactos, el preflight
compartido acepta `alineada` o `arca_adelantada`; no asigna número, no crea
intento y no solicita CAE.

Los intentos propios `en_proceso` activos o `requiere_reconciliacion`, una
autorización sin comprobante local coherente, `local_adelantada` y cualquier
consulta no concluyente conservan el bloqueo. Después de reencolar, el reclamo
atómico permite un único worker y el núcleo normal vuelve a diagnosticar, crea
reservas durables y ejecuta el segundo preflight antes de FECAE. Los metadatos
expuestos usan categorías estables; el detalle de excepciones queda solo en logs
privados.

El corte no cambia modelo, migraciones, estados, rutas, schemas ni UI. La matriz enfocada
aprobó `12` casos y la regresión completa de facturación/lotes `164`. La puerta
local aprobó `557` pruebas backend con `4` omisiones configuradas, `131`
frontend, `16` de scripts y `33` E2E, además de Ruff, Black, ESLint sin errores,
type-check, build y `docs:check`. `pip-audit` y `npm audit --omit=dev` no
encontraron vulnerabilidades productivas conocidas. Las pruebas usaron fechas
explícitas y datos sintéticos; no hubo emisiones reales, solicitudes de CAE,
migraciones ni llamadas ARCA de escritura.

## Dependencia criptográfica y auditoría

El PR `#20` integró en `main` el commit `712197d`. `main` usa
`cryptography==50.0.0`, que corrige `PYSEC-2026-3552`,
`PYSEC-2026-3553` y `PYSEC-2026-3554` sin excepciones en `pip-audit`. La
compatibilidad se prueba con material sintético para carga PEM, clave cifrada y
firma CMS. La matriz enfocada aprobó `47` pruebas y el backend completo `540`,
con `4` omisiones por harness configurado; Ruff, Black y la auditoría quedaron
limpios. Tres tests históricos de numeración batch mantienen su fecha fiscal
fija, pero ya no dependen del reloj de ejecución para validar un comportamiento
ajeno a su escenario. No se relajó la validación productiva. No hubo
certificados reales, conexiones ARCA, solicitudes de CAE ni cambios
productivos. El PR y la CI post-merge `31042753464` aprobaron los seis checks
obligatorios; la CI del PR fue `31042184221`.

## Integrado en main — PF-02B.2 reintentos manuales seguros

El PR `#19` integró en `main` el commit `1a5e335`. El segundo corte de PF-02B
cierra el contrato específico de
`reintentar-fallidos` sobre el núcleo individual compartido. El flujo admite
historia externa legítima desde `ultimo_arca + 1`, conserva el CAS
`fallido -> reintentando` y detiene inmediatamente la selección si existe un
intento propio bloqueante, la numeración local está adelantada, el segundo
preflight cambia o falla, o aparece incertidumbre después de iniciar FECAE.

Un rechazo ARCA explícito puede liberar el número y permitir el grupo siguiente.
Una respuesta ambigua o una falla local posterior a una autorización conocida
nunca vuelve el grupo a `fallido`: hace rollback de la persistencia incompleta,
conserva número y CAE conocidos en el intento y deja grupo/lote en
`requiere_reconciliacion`, con mensajes públicos sanitizados. No cambia la UI,
el contrato HTTP, el esquema ni la recuperación stale del worker.

La matriz específica aprobó `11` escenarios y la regresión completa de lotes
aprobó `109`, incluidos procesamiento unitario y batch, reanudación y worker
stale. La puerta global aprobó `548` pruebas backend con `4` omisiones por
harness, `131` frontend, `16` de scripts y `33` E2E, además de Ruff, Black,
type-check y build. Una única revisión con Codex `gpt-5.6-sol`, thinking
`medium`, completó dos pases automáticos por tamaño, quedó limpia con confianza
`0,99` y cero findings; usó el binario versionado `0.147.0-alpha.1.2`. No hubo
emisiones reales, solicitudes de CAE, migraciones ni llamadas ARCA de escritura.
La CI del PR `31043726676` y la post-merge `31044367510` aprobaron los seis
checks obligatorios. En ese checkpoint quedó pendiente PF-02B.3; la sección
anterior registra su cierre posterior sin liberar intentos propios inciertos.

## Integrado en main — PF-02B.1 numeración masiva

El primer corte de PF-02B fue integrado en `main` mediante el PR `#16`, commit
`2c75fd2`. El núcleo batch acepta una historia externa legítima como inicio del
rango global, crea una reserva durable por comprobante y repite
`FECompUltimoAutorizado` después de reservar el rango completo. Si ARCA avanzó
o la consulta falla, no comienza `FECAESolicitar`, no se crean comprobantes y
todos los intentos del sublote quedan `fallido_verificado`.

El diseño y la matriz están en
`docs/agents/pf-02b-numeracion-masiva-design.md`. El primer control enfocado
aprobó `9` pruebas batch, la regresión completa de facturación y lotes aprobó
`147` y el backend completo aprobó `539` con `4` omitidas por harness
condicionado. Una única revisión con Codex `gpt-5.6-sol`, thinking `medium`,
quedó limpia con confianza `0,94`; los seis checks del PR aprobaron. No hubo
emisiones reales, solicitudes de CAE, migraciones, cambios de UI ni llamadas
ARCA de escritura.

Al cerrar PF-02B.1, la recuperación stale todavía exigía numeración alineada y
su extensión se dejó para PF-02B.3. Ese alcance histórico quedó cerrado en la
sección anterior sin liberar intentos propios inciertos.

## Integrado en main — PF-02A numeración individual

PF-02A fue integrado en `main` mediante el PR `#15` en el commit `c872497`.
La emisión individual ahora distingue numeración `alineada`,
`arca_adelantada` y `local_adelantada`:

- una historia previa o actividad externa en ARCA se informa y usa
  `ultimo_arca + 1` sin exigir importación histórica;
- intentos propios `en_proceso` o `requiere_reconciliacion` y una numeración
  local adelantada continúan bloqueando;
- después de reservar el intento se repite `FECompUltimoAutorizado`; si el
  número cambió o la consulta falla, no se llama a FECAE, el intento queda
  `fallido_verificado` y la UI exige actualizar y reconfirmar con una nueva
  clave;
- el endpoint y `Nueva Factura` muestran emisor, punto, tipo, último local,
  último ARCA y próximo número;
- el núcleo batch se extiende por separado en PF-02B;
- PF-05 mantiene separada la reconstrucción histórica opcional para informes.

El diseño fiscal y la matriz están en
`docs/agents/pf-02a-numeracion-individual-design.md`. Las validaciones enfocadas
son `68` pruebas de servicio/API y `16` de la vista. La puerta global aprobó
`536` pruebas backend con `4` omitidas por harness condicionado, `131` frontend
y `7` de scripts; Ruff, Black, type-check y build quedaron verdes. ESLint terminó
sin errores y conservó `13` advertencias de estilo no bloqueantes. No se hicieron
emisiones reales, solicitudes de CAE, migraciones ni llamadas ARCA de escritura.
El cierre ejecutó una única revisión efectiva con Codex `gpt-5.6-sol`,
thinking `medium`: patch correcto, confianza `0,87` y cero findings. El primer
intento con el alias local obsoleto `0.130.0-alpha.5` no produjo dictamen; la
revisión válida usó el binario vigente `0.146.0-alpha.3.1` de la misma app sin
debilitar el aislamiento ni cambiar de modelo. El mock del endpoint de
numeración usado por Playwright se actualizó al contrato completo sin relajar
ningún bloqueo productivo; las `33` pruebas E2E locales quedaron verdes.

## Cierre histórico — P1 UI, pool y worker

El P1 estructural quedó implementado y validado localmente el 2026-07-10. Sus
commits se publicaron primero en `main` y luego quedaron incluidos en el
despliegue productivo de `v0.2.2` del 2026-07-23.

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
publicado en `main`. Ese estado local quedó posteriormente incluido en
`v0.2.2`; la QA manual de fallos controlados continúa separada del smoke
productivo seguro.

### Corrección histórica posterior — frontera DB/FECAE

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
antes de iniciar PF-01A.1. Esos cambios no formaron una release independiente;
quedaron incluidos en el corte productivo `v0.2.2`.

## Snapshot vigente

- Versión productiva: `v0.2.2`.
- Versión técnica del candidato: `v0.3.0`, sin tag, publicación ni
  despliegue.
- Tag desplegado e inmutable:
  `64629957ebff64ca60f474fcb44f054557e69ec0`.
- La release quedó desplegada y aceptada el 23/07/2026.
- El estado objetivo de `main` incorpora, además de `v0.2.2`, PF-02A, los tres
  cortes de PF-02B, PF-03A, PF-19A, la unidad completa PF-19B y PF-19C
  incorporado por el candidato. Todo ese tramo es posterior a
  `v0.2.2`: todavía no pertenece a una release publicada ni está desplegado.
- Producción está sana en `v0.2.2`; el upgrade y la QA post-deploy se cerraron
  el 23/07/2026.
- La evidencia concreta del VPS permanece en documentación operativa privada.

### Release v0.2.2

`main` contiene el corte `0.2.2` con alcance funcional congelado después de
PF-01 y antes de PF-02. El commit publicado `0271d8a` reúne el versionado,
changelog y dossier de upgrade; su CI `29284577864` aprobó los cuatro jobs.
La release fue publicada y desplegada mediante autorizaciones separadas el
2026-07-23 desde el tag exacto
`64629957ebff64ca60f474fcb44f054557e69ec0`.

El rango incorpora la migración fiscal `a8b9c0d1e2f3`, Pillow `12.3.0` y
variables nuevas de pool. El versionado aprobó lint, type-check, Black, `531`
pruebas backend, `127` frontend, `3` de scripts y build. La primera pasada de
`autoreview gpt-5.5 high` detectó un P2 válido de versionado; se aceptó, se
corrigió y la segunda pasada quedó limpia, sin findings, con confianza `0,82`.

El 2026-07-23 se completó en privado la puerta operativa: backup fresco cifrado
con copia externa, restauración aislada, cinco categorías de preflight en cero,
migración hasta `a8b9c0d1e2f3`, constraints, pools, worker y smoke checks
aprobados. No hubo llamadas de emisión a ARCA ni cambios productivos. El dossier
vigente es `docs/project/releases/v0.2.2-candidate.md`.

El despliegue posterior repitió el preflight PF-01B inmediatamente antes del
DDL con sus cinco categorías en cero, aplicó Alembic una sola vez hasta
`a8b9c0d1e2f3 (head)` y verificó los tres constraints, invariantes y conteos
agregados. También aprobaron pools `4 + 1`, Uvicorn único, worker saludable,
smoke autenticado de solo lectura, reportes y PDF. FactuFlow y los servicios
vecinos reabrieron sanos. No hubo llamadas ARCA de escritura, solicitudes de
CAE, emisiones, reintentos fiscales, downgrade ni restauración productiva.

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
- evolución de permisos multiemisor aceptada pero todavía no implementada:
  PF-06/PF-07/PF-08 reemplazará la asignación singular por accesos explícitos a
  varios emisores y permitirá conceder el checkbox `Puede crear y editar
  emisores`; crear autoasignará el nuevo emisor y editar exigirá además acceso
  vigente, mientras borrado y administración global seguirán reservados;
- worker embebido para lotes, con `BATCH_WORKER_ENABLED=true` y un único proceso
  Uvicorn en la instalación productiva actual;
- PDFs bajo demanda y gestor administrativo de almacenamiento.

En el estado objetivo de `main`, PF-19B agrega ledger y cabeza durable de elegibilidad RECE,
atestación administrativa de constancia productiva fresca, sincronización
técnica server-side sin promoción, badges/estados visibles y compuertas comunes
en individual, lotes, worker, reintentos y stale. Esta capacidad todavía no
pertenece a la release publicada ni está disponible en producción.

Las reglas no negociables siguen en `VISION.md` y `AGENTS.md`. En particular:
la fecha fiscal nunca se completa con la fecha actual, ninguna ruta puede pedir
CAE sin confirmación explícita y los datos de emisores distintos no se mezclan.

## Cierre histórico de v0.2.1

- Backend: 411 tests aprobados y 1 omitido según su marca preexistente.
- Frontend: 111 tests aprobados; ESLint, type-check y build limpios.
- Scripts raíz: 3 tests aprobados.
- GitHub Actions del tag `8099b22`: Security Audit, Frontend Build, Backend Tests
  y E2E Tests aprobados.
- GitHub Actions del cierre documental `ece2bdf`: los mismos cuatro jobs
  aprobados.
- `autoreview` acumulado del ciclo: GPT-5.5 en `high` sin hallazgos accionables.
- QA productiva manual: login autenticado y emisión fiscal real satisfactoria.
- Alembic productivo en ese checkpoint: `current` y `heads` en `f7a8b9c0d1e2`.

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

### P1 fiscal priorizado

PF-19 es el P1 fiscal activo por evidencia productiva. PF-19A cerró diseño,
contención explícita e inventario de solo lectura; PF-19B cerró la elegibilidad
RECE durable end-to-end, incluida su autoridad administrativa y UI. Ninguno
autoriza reintentos legacy ni ediciones directas de base. PF-19C completó su
evidencia de rechazo global y saneamiento auditado; siguen pendientes
PostgreSQL y Runtime Smoke reales en CI, CI atribuible al SHA final, aceptación
PF-16G y ensayo privado de backup/restauración/upgrade/rollback antes de una
release. Después se retoma PF-03B. Los párrafos siguientes conservan la evidencia histórica de PF-01 ya
cerrada y no cambian ese orden.

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

La puerta privada de backup portable y restauración quedó verificada para
`v0.2.2`. La custodia concreta de credenciales y artefactos continúa fuera del
repositorio público.

Siguen pendientes:

- automatización de backups cifrados, retención y alertas;
- recuperación ensayada hacia un VPS nuevo;
- señal visible del último backup;
- vínculo inequívoco entre cada backup preoperación, su propósito, timestamp y
  cualquier escritura intermedia;
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
8. `v0.2.2` quedó validada, publicada y desplegada como corte posterior a
   PF-01. No repetir el versionado, el despliegue, las revisiones, el
   backup/restauración ni la migración salvo que aparezca evidencia nueva.
9. PF-16A, PF-16B y la barrera básica de PF-16C quedaron cerradas mediante el
   PR `#14`: clasificación por riesgo, evidencia simple, una única rama
   permanente, recorrido Nivel 0 y seis checks obligatorios. La CI
   `30305581217` quedó verde y `main` bloquea force-push, borrado y bypass del
   administrador, sin exigir un segundo aprobador humano. La continuación de
   PF-16 agrega la puerta documental semántica y `npm run docs:check` sin
   presentar el control automático como sustituto de la revisión.
10. PF-02A y los tres cortes de PF-02B están integrados en `main`; PF-02 quedó
    cerrado sin mezclar la reconstrucción histórica opcional de PF-05. PF-19A
    cerró diseño, contención e inventario; PF-19B cerró sus cortes B.1+B.2+B.3
    y PF-19C está incorporado por el candidato con implementación y evidencia completas. Retomar por
    PostgreSQL y Runtime Smoke reales en CI, CI atribuible al SHA final,
    aceptación PF-16G y ensayo privado de backup/restauración/upgrade/rollback;
    recién entonces PF-03B. No reabrir PF-02 ni mezclar elegibilidad RECE o errores
    globales con ítems/importes. Después siguen
    PF-06/PF-07, PF-08 y PF-09 según el portafolio integrado.
    Al llegar a ese bloque, ejecutar primero la unidad integrada de permisos
    definida en `docs/agents/pf-06-08-permisos-multiemisor-design.md`; no crear
    una línea paralela ni presentar el diseño como funcionalidad ya disponible.
    PF-16C/D/E están implementados; falta atribuir su evidencia al rango de
    release y aceptar PF-16G.
11. La revisión local de PF-16 intentó dos veces `autoreview` con Codex
    `gpt-5.6-sol medium`, pero Codex `0.130.0-alpha.5` rechazó crear auxiliares
    bajo el directorio temporal aislado de Windows y no produjo dictamen. No se
    debilitó el aislamiento ni se cambió de modelo; no presentar esos intentos
    como una revisión limpia.
12. Para próximas pasadas de `autoreview`, mantener una única configuración de
    cierre: `--engine codex --model gpt-5.6-sol --thinking medium`. En esta
    instalación, verificar que `--codex-bin` apunte al binario vigente de la app:
    el alias `bin\codex.exe` continuaba en `0.130.0-alpha.5`; PF-02A usó el
    ejecutable versionado `0.146.0-alpha.3.1` y los cierres más recientes
    usaron `0.147.0-alpha.1.2`. Resolver y verificar siempre el binario
    versionado vigente antes de revisar. No hacer revisiones incrementales ni
    cambiar manualmente de modelo o esfuerzo.

## Referencias de continuidad

- Visión protegida: `VISION.md`
- Prioridades: `ROADMAP.md`
- Portafolio integrado: `docs/agents/development-portfolio.md`
- Diseño PF-01A: `docs/agents/pf-01-authorization-integrity-design.md`
- Diseño PF-01B: `docs/agents/pf-01b-persistence-integrity-design.md`
- Diseño de permisos multiemisor PF-06/PF-07/PF-08:
  `docs/agents/pf-06-08-permisos-multiemisor-design.md`
- Diseño PF-02A: `docs/agents/pf-02a-numeracion-individual-design.md`
- Diseño PF-02B: `docs/agents/pf-02b-numeracion-masiva-design.md`
- Cierre Clawpatch PF-01B:
  `docs/project/audits/clawpatch/2026-07-13-cierre-checkpoint-pf-01b.md`
- QA manual vigente: `docs/agents/manual-qa.md`
- Historial: `CHANGELOG.md`
- Flujo productivo: `docs/agents/production-workflow.md`
- Dossier v0.2.2: `docs/project/releases/v0.2.2-candidate.md`
- Dossier v0.3.0: `docs/project/releases/v0.3.0-candidate.md`
- Checklist fiscal: `docs/agents/fiscal-change-checklist.md`
- Clawpatch: `docs/project/audits/clawpatch/README.md`
- Cierre v0.2.1:
  `docs/project/audits/clawpatch/2026-07-10-cierre-ciclo-v0.2.1.md`
