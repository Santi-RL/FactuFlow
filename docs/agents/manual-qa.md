# QA manual

Última actualización: 2026-07-10

Este documento conserva únicamente el checkpoint vigente y la QA todavía
accionable. El historial técnico está en `CHANGELOG.md` y en las auditorías
fechadas de `docs/project/**`.

## Último checkpoint aceptado

`v0.2.1` quedó validada en producción el 2026-07-10.

- El despliegue verificó backup y restauración aislada, Alembic, constraints,
  integridad básica de datos, runtime, worker, healthchecks, login y PDF
  sintético.
- La validación manual autenticada confirmó el acceso y la operación normal.
- Se emitieron comprobantes fiscales reales correctamente.
- No queda QA manual bloqueante para `v0.2.1`.
- Los datos fiscales y la evidencia detallada permanecen en el entorno operativo
  privado.

## Preparación local

Para desarrollo o QA manual en Windows:

```powershell
.\FactuFlow Local.vbs
```

Camino técnico alternativo:

```powershell
powershell -ExecutionPolicy Bypass -File .\run-local.ps1
```

Entornos locales esperados:

- frontend: `http://localhost:8080`;
- backend: `http://localhost:8000`.

No reutilizar certificados productivos en local mientras el VPS sea el entorno
operativo. Usar datos ficticios, mínimos o anonimizados.

## Matriz mínima por tipo de cambio

### Fiscal o ARCA

Antes de probar, completar `docs/agents/fiscal-change-checklist.md`.

Verificar al menos:

- fecha visible en `DD/MM/AAAA` y payload técnico correcto;
- fecha calendario inválida rechazada;
- punto de venta y emisor activo;
- concepto fiscal y fechas de servicio aplicables;
- totales, IVA y comprobantes asociados;
- confirmación irreversible antes de CAE;
- idempotencia, replay con mismo payload y conflicto con payload distinto;
- falla pre-ARCA, respuesta ambigua, falla post-CAE y reconciliación;
- caída pre-ARCA: `503` con `Retry-After: 2` solo tras recuperación durable sin
  intentos fiscales;
- intento existente o recuperación no persistible: `409
  pre_arca_estado_bloqueado`, misma clave, sin operación nueva ni reconciliación
  ARCA;
- caída desde la frontera irreversible: `409`, sin retry, con evidencia conocida
  preservada y reconciliación obligatoria;
- aislamiento entre emisores.

No solicitar CAE real durante QA salvo decisión fiscal explícita del usuario.

### Lotes y worker

Verificar:

- validación antes de encolar;
- `503` sin mutar el lote cuando el worker no está disponible;
- un único procesamiento efectivo por lote;
- reanudación de un lote vencido solo si los pendientes están intactos y la
  numeración ARCA/local fue comprobada;
- preservación como `validado` de grupos intactos cuando el lote se bloquea;
- reconciliación solo para grupos con evidencia fiscal o incertidumbre;
- polling sin ciclos solapados y sin mensajes falsos de lote inexistente;
- ausencia de reintentos automáticos cuando ARCA pudo haber autorizado;
- worker pre-ARCA: solo reencola sin intentos, conserva la operación
  `en_proceso`, impide replay HTTP paralelo y corta el ciclo;
- corte del ciclo del worker post-frontera, sin tomar ni procesar lotes
  posteriores.

### Multiemisor

Verificar con dos emisores ficticios:

- administrador: puede operar todos los emisores;
- usuario común: solo puede operar el emisor asignado;
- cambio de emisor limpia estado, modales y respuestas tardías;
- clientes, puntos de venta, certificados, comprobantes, lotes, PDFs, reportes,
  perfiles y plantillas particulares no se mezclan.

### UI y documentación

Para cambios visuales o de texto:

- `npm run lint:check`;
- `npm run type-check`;
- tests unitarios enfocados;
- build cuando cambia composición o routing;
- E2E solo cuando el flujo real lo justifica.

Los cambios solo documentales no requieren `autoreview` salvo pedido explícito.

## QA pendiente

### Regresión DB/FECAE — QA manual pendiente

La implementación tiene validación automatizada local. En una próxima QA
controlada, sin solicitar CAE real, simular:

1. pre-ARCA sin intentos: confirmar recuperación durable, `503`, transición
   `en_proceso -> interrumpida_pre_arca` y un único replay ganador por CAS;
2. individual/lote/reintento sin intentos: lote `validado` o grupo exacto
   `fallido`, con reanudación mediante la misma clave;
3. intento existente o recuperación no persistible: confirmar
   `409 pre_arca_estado_bloqueado`, misma clave, sin nueva operación ni
   reconciliación ARCA;
4. post-frontera: confirmar `409`, ausencia de retry y reconciliación;
5. cleanup: fallos de `rollback`/`close` no reemplazan la excepción primaria ni
   degradan un `409` post-ARCA a `503`;
6. worker pre-ARCA sin intentos: lote `en_cola`, operación `en_proceso`, replay
   HTTP paralelo impedido y corte del ciclo; post-ARCA conserva el bloqueo.

Estos casos tienen pruebas automatizadas enfocadas aprobadas, pero no registran
QA manual ni evidencia productiva. La publicación exige el cierre final limpio de
`autoreview`.

### P1 pool/worker — cierre local

La implementación y la capacidad estructural quedaron validadas localmente:

1. pool API PostgreSQL máximo `4`, overflow `0` y pool worker dedicado `1`;
2. sesiones API lazy, instrumentación sanitizada y timeouts HTTP `503`;
3. polling allowlist adaptativo, no solapado y protegido por emisor;
4. prueba PostgreSQL efímera con saturación `4 + 1`, sin datos ni ARCA;
5. suites backend/frontend y regresiones fiscales vecinas aprobadas.

Después de un despliegue explícitamente autorizado todavía corresponde verificar
en el entorno privado `Sistema > Estado`, logs sanitizados y tiempos de un lote
de prueba controlado. El runbook privado de la instalación debe registrar el
commit desplegado y sus comandos concretos sin llevar esos datos al repo.

### Operación VPS

Queda pendiente, con datos de prueba controlados:

- QA visual del gestor de almacenamiento;
- resguardo ZIP y confirmación `Ya lo descargué`;
- compactación y limpieza segura;
- healthcheck de worker visible y coherente con el runtime desplegado;
- señal de último backup;
- trazabilidad histórica más completa;
- ensayo de recuperación hacia un VPS nuevo.

## Smoke posterior a futuros despliegues

La validación mínima debe cubrir:

- health público de frontend y backend;
- login;
- emisor activo;
- listado de comprobantes;
- certificados y puntos de venta;
- PDF;
- un único Uvicorn y worker iniciado;
- logs sin errores nuevos;
- servicios vecinos sin afectación.

Si hubo migraciones, comprobar `alembic current`, `heads`, constraints, conteos
básicos y restauración aislada. Seguir
`docs/agents/production-workflow.md`.

## Punto de reanudación de QA

La próxima matriz de QA debe diseñarse para el P1 fiscal de historia previa y
emisión multicanal. La validación productiva del P1 pool/worker solo se ejecuta
cuando exista autorización explícita de despliegue. No repetir como pendiente el
setup productivo inicial, el rediseño UX de lotes ni la validación de `v0.2.1`.

Para conocer el estado de desarrollo y el orden exacto, usar
`docs/agents/current-status.md` y `ROADMAP.md`.
