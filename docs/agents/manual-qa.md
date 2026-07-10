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
- ausencia de reintentos automáticos cuando ARCA pudo haber autorizado.

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

### P1 pool/worker

Antes de ampliar volumen productivo:

1. instrumentar saturación y espera de pool/worker;
2. ejecutar una prueba controlada de lote grande;
3. observar polling, procesamiento y tiempos sin emitir duplicados;
4. verificar que no se alteren CAE, numeración, idempotencia ni reconciliación;
5. documentar recuperación privada y mensajes seguros para soporte.

### Operación VPS

Queda pendiente, con datos de prueba controlados:

- QA visual del gestor de almacenamiento;
- resguardo ZIP y confirmación `Ya lo descargué`;
- compactación y limpieza segura;
- healthcheck dedicado de worker;
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

La primera QA nueva corresponde al P1 pool/worker. No volver a ejecutar como
pendiente el setup productivo inicial, el rediseño UX de lotes ni la validación
de `v0.2.1`.

Para conocer el estado de desarrollo y el orden exacto, usar
`docs/agents/current-status.md` y `ROADMAP.md`.