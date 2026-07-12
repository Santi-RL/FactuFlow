# Estado actual

Última actualización: 2026-07-12

Este documento es el handoff operativo canónico y deliberadamente breve. El
historial de versiones vive en `CHANGELOG.md`; las auditorías fechadas y las
lecciones de herramientas viven en `docs/project/**`.

## Cierre local — P1 UI, pool y worker

El P1 estructural quedó implementado y validado localmente el 2026-07-10. No
está publicado ni desplegado; `v0.2.1` continúa como versión productiva.

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

No se ejecutaron Clawpatch fix, push ni despliegue. El cierre fiscal posterior
quedó integrado y validado en el commit local `e175b77`; la QA manual y
productiva continúa pendiente. Push, publicación y despliegue requieren
autorización explícita.

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

- commit local `e175b77` (`fix: preserve fiscal state on database outages`);
- backend completo: `487` tests aprobados y `2` omitidos;
- suites de API: `120` tests aprobados;
- Ruff, Black y `git diff --check`: limpios;
- `autoreview` final con `gpt-5.6-sol`, thinking `high`: limpio, sin findings
  accionables, con probabilidad `0,87` de patch correcto.

`main` está dos commits por delante de `origin/main`, con `8b311b5` y `e175b77`.
El commit está listo para push, pero no fue publicado: no hubo push, release ni
despliegue. `v0.2.1` continúa como versión productiva y la QA manual/productiva
de este corte sigue pendiente.

## Snapshot vigente

- Versión productiva: `v0.2.1`.
- Tag desplegado e inmutable:
  `8099b223f3be7342dbb29367d24c6209dee93a58`.
- La release quedó desplegada y aceptada el 2026-07-10.
- `main` contiene el cierre documental posterior a la release. Un commit solo
  documental posterior al tag no implica un nuevo despliegue.
- Producción quedó sana después de backup, restauración aislada, migración,
  smoke checks y QA manual autenticada con emisión fiscal real satisfactoria.
- La evidencia concreta del VPS permanece en documentación operativa privada.

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

El estado local ignorado quedó así después del triaje manual:

- repo: 16 abiertos, 5 `high`, 4 `medium` y 7 `low`;
- backend: 101 abiertos, 25 `high`, 52 `medium` y 24 `low`;
- frontend: 30 abiertos, 6 `high`, 20 `medium` y 4 `low`.

Los tres slices terminaron sin locks y con cero features pendientes de review.
Estos números no equivalen a 147 bugs independientes: todavía hay duplicados
entre slices, además de gaps de pruebas y contratos que deben agruparse por
causa raíz. Dentro de cada slice ya se retiraron duplicados exactos y alertas
refutadas por código, tests, migraciones o decisiones explícitas. Por eso:

1. no reparar en masa;
2. filtrar por evidencia y propiedad reales del código;
3. clasificar cada finding como aceptado, rechazado o diferido;
4. revalidar duplicados antes de tratarlos como deuda;
5. no borrar ni reinicializar `.clawpatch/` sin decisión explícita.

La guía canónica es `docs/project/audits/clawpatch/README.md`. El cierre
sanitizado de esta auditoría está en
`docs/project/audits/clawpatch/2026-07-12-cierre-auditoria-ordenada.md`.

## Riesgos y pendientes priorizados

### P1 fiscal siguiente

El P1 fiscal es la siguiente tarea planificada, pero no debe iniciarse hasta que
el usuario lo indique expresamente. Cuando lo indique, se deberá diseñar e
implementar numeración compatible con emisores que tienen historia previa o
comparten punto de venta con otros sistemas. ARCA debe ser la fuente de verdad de
la secuencia global y FactuFlow la fuente de sus propios intentos, idempotencia y
resultados inciertos.

Antes de tocar código se deben completar el checklist fiscal, estados, orden de
operaciones y matriz de tests para emisión individual y lotes. No se puede
eliminar el guardarraíl ante intentos propios inciertos, numeración local
adelantada ni autorizaciones sin comprobante local coherente. Este P1 debe tener
diseño y commits separados del cierre pool/worker.

### Backlog Clawpatch priorizado

La auditoría nueva detectó familias `high` que requieren decisión explícita
antes de seguir acumulando cambios: invariantes ARCA/CAE y reconciliación,
preservación histórica de PDFs/reportes, concurrencia de certificados y
archivos, aislamiento al cambiar emisor, almacenamiento/backup y autorización
administrativa.

No reparar en masa ni por severidad automática. Antes de empezar el P1 fiscal o
un fix de Clawpatch, comparar ambas prioridades y elegir un único corte vertical
pequeño. Los cambios fiscales, migraciones y contratos nuevos exigen diseño y
matriz de tests antes de editar.

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
5. No empezar otro fix ni usar `clawpatch fix`. La auditoría terminó y el
   siguiente paso requiere que el usuario elija la primera familia a diseñar.
6. Comparar los findings `high` sanitizados con el P1 fiscal de historia previa
   y emisión multicanal antes de decidir el primer corte. Completar
   `docs/agents/fiscal-change-checklist.md`, estados, orden de operaciones y
   matriz de tests antes de tocar código.
7. Si el usuario decide continuar con Clawpatch, leer el finding exacto,
   reagrupar duplicados entre slices, verificar código y tests vecinos y recién
   entonces convertirlo en una tarea. No usar el contador global como backlog
   ejecutable.
8. Aplicar la metodología de
   `docs/project/audits/clawpatch/README.md`: cambio sensible aislado; cambios
   chicos relacionados agrupables; tests enfocados; `autoreview` sobre el commit
   o lote coherente; push solo con autorización; CI por SHA; revalidación
   Clawpatch después de varios cortes.
9. Para próximas revisiones, usar `gpt-5.6-sol` con `high`. Si ese modelo no
   puede ejecutarse después de un reintento razonable, usar `gpt-5.5` con
   `high` y registrar cuál se utilizó.

## Referencias de continuidad

- Visión protegida: `VISION.md`
- Prioridades: `ROADMAP.md`
- QA manual vigente: `docs/agents/manual-qa.md`
- Historial: `CHANGELOG.md`
- Flujo productivo: `docs/agents/production-workflow.md`
- Checklist fiscal: `docs/agents/fiscal-change-checklist.md`
- Clawpatch: `docs/project/audits/clawpatch/README.md`
- Cierre v0.2.1:
  `docs/project/audits/clawpatch/2026-07-10-cierre-ciclo-v0.2.1.md`