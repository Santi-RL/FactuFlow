# Estado actual

Última actualización: 2026-07-10

Este documento es el handoff operativo canónico y deliberadamente breve. El
historial de versiones vive en `CHANGELOG.md`; las auditorías fechadas y las
lecciones de herramientas viven en `docs/project/**`.

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

El ciclo de endurecimiento 2026-07-07/10 quedó cerrado para formar `v0.2.1`.
Los 3 findings backend y 9 frontend elegidos para ese corte fueron revalidados
como `fixed`. No quedó un finding crítico o alto aceptado pendiente antes del
despliegue.

El estado local ignorado conserva un backlog acumulativo:

- repo: 0 abiertos;
- backend: 85 abiertos, 57 `medium` y 28 `low`;
- frontend: 6 abiertos, todos `medium`.

Estos números no equivalen a 91 bugs confirmados. El state dir backend conserva
features históricas, duplicadas y algunas ajenas al slice debido a la corrida
del 2026-07-06 ejecutada con un `--root` incorrecto. También hay findings
abiertos cuyo bloque ya fue corregido y revalidado bajo otro feature ID. Por eso:

1. no reparar en masa;
2. filtrar por evidencia y propiedad reales del código;
3. clasificar cada finding como aceptado, rechazado o diferido;
4. revalidar duplicados antes de tratarlos como deuda;
5. no borrar ni reinicializar `.clawpatch/` sin decisión explícita.

La guía canónica es
`docs/project/audits/clawpatch/README.md`. El cierre del ciclo está en
`docs/project/audits/clawpatch/2026-07-10-cierre-ciclo-v0.2.1.md`.

## Riesgos y pendientes priorizados

### P1 técnico

Resolver la causa raíz de presión entre seguimiento UI, pool de base y worker
durante lotes grandes antes de ampliar volumen productivo. La contención
frontend ya evita polling solapado y mensajes engañosos, pero falta:

- instrumentar pool y worker;
- definir límites o separación de carga;
- probar lotes grandes en un entorno controlado;
- completar el runbook privado de recuperación;
- demostrar que el cambio no altera CAE, numeración, idempotencia ni
  reconciliación.

Este trabajo es sensible y debe tener diseño, tests y commit propios.

### Backlog Clawpatch no bloqueante

Después del P1, continuar el triage de findings `medium`/`low` en lotes pequeños.
No hay un crítico/alto aceptado que obligue a una reparación inmediata. Si un
finding requiere política fiscal, migración, estado nuevo o cambio de contrato,
debe diferirse hasta diseñar el alcance.

### Operación privada

Confirmar en la documentación privada si la clave portable del backup cifrado
ya está guardada en un gestor de contraseñas. El repo público no puede afirmar
ese estado.

Siguen pendientes:

- automatización de backups cifrados, retención y alertas;
- recuperación ensayada hacia un VPS nuevo;
- healthcheck dedicado de worker y backup visible;
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
5. Primera tarea técnica recomendada: diseñar el P1 pool/worker con
   `docs/agents/fiscal-change-checklist.md` y tests de regresión antes del código.
6. Si el usuario decide continuar primero con Clawpatch, leer el finding exacto,
   verificar el código y los tests vecinos y triarlo manualmente. No usar el
   contador global como backlog confirmado.
7. Aplicar la metodología de
   `docs/project/audits/clawpatch/README.md`: cambio sensible aislado; cambios
   chicos relacionados agrupables; tests enfocados; `autoreview` sobre el commit
   o lote coherente; push solo con autorización; CI por SHA; revalidación
   Clawpatch después de varios cortes.
8. Para próximas revisiones, usar `gpt-5.6-sol` con `high`. Si ese modelo no
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