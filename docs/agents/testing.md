# Guía de testing

Última revisión: 29/08/2026

Estado: VIGENTE.

Esta guía contiene comandos, políticas y entornos reutilizables. Los conteos y
resultados de un corte pertenecen al PR, al changelog o a su dossier, no aquí.

## Puertas por alcance

La clasificación canónica vive en
[`change-quality-gates.md`](change-quality-gates.md):

- **Nivel 0:** Markdown o `.gitignore`; revisión del diff, privacidad,
  `docs:check` y CI liviana.
- **Nivel 1:** funcional no crítico; pruebas enfocadas y suite del área.
- **Nivel 2:** fiscal o sensible; diseño, errores, concurrencia, checklist, CI
  completa, revisión y QA proporcional.

Una duda usa el nivel superior hasta justificar lo contrario.

## Comandos desde la raíz

```bash
npm run lint
npm run test
npm run backend:format:check
npm run docs:check
```

La puerta local completa, cuando corresponde, es:

```powershell
./scripts/ci-local.ps1
```

El log se guarda en una ruta ignorada. Los comandos con `--fix` o `--write`
modifican archivos y no se usan como verificaciones pasivas.

## Backend

Desde `backend/`:

```bash
pytest
ruff check app/ tests/
black --check app/ tests/
```

Usar selecciones enfocadas antes de la suite completa:

```bash
pytest tests/ruta_relevante.py -q
pytest tests/ruta_relevante.py -k caso_relevante -q
```

Las pruebas deben usar fechas explícitas y datos sintéticos. Ninguna suite
normal llama a ARCA real ni solicita CAE.

### PostgreSQL desechable

Las pruebas de migraciones, constraints o concurrencia deben usar el harness
versionado y una base descartable. Las barreras mínimas son:

- driver `postgresql+asyncpg`;
- host loopback exacto;
- base exacta `factuflow_integration_test`;
- opt-in explícito `FACTUFLOW_TEST_POSTGRES_ALLOW_SCHEMA_RESET=1`;
- revalidación antes de cada operación destructiva;
- eliminación del entorno al finalizar.

Nunca apuntar el harness a producción, una base compartida o un nombre que sólo
“parezca” de prueba.

## Frontend

Desde `frontend/`:

```bash
npm run test:unit
npm run lint:check
npm run type-check
npm run build
```

`npm run lint:fix` y `npm run format` son comandos de modificación; revisar el
diff después de usarlos.

Las pruebas de stores y vistas con emisor activo deben cubrir respuestas tardías,
cambio de emisor, permisos y estados de carga cuando el contrato afectado lo
requiera.

## E2E

Desde la raíz:

```bash
npm run test:e2e
```

- Usar dobles y datos sintéticos.
- No reutilizar sesiones o credenciales productivas.
- No confirmar emisiones reales.
- Las capturas y reportes locales quedan en rutas ignoradas.
- Un cambio de UI sensible debe probar el camino feliz y la recuperación del
  error relevante.

## Fechas fiscales

Toda prueba nueva o modificada debe elegir fechas explícitas:

- UI y textos argentinos: `DD/MM/AAAA`;
- API y persistencia: contrato ISO aplicable;
- WSFE `CbteFch`: `YYYYMMDD`.

No usar la fecha actual como valor predeterminado ni generar expectativas que
dependan del día de ejecución.

## ARCA, idempotencia y estados inciertos

Los cambios capaces de llegar a WSAA/WSFE, numeración o CAE deben cubrir, según
el riesgo:

- éxito, rechazo y timeout;
- respuesta incompleta o contradictoria;
- concurrencia y replays idempotentes;
- segundo preflight y compare-and-swap;
- reconciliación cuando ARCA pudo autorizar;
- cero estado fiscal nuevo cuando el flujo debe abortar antes de ARCA.

Aplicar antes el
[`checklist fiscal`](fiscal-change-checklist.md). Las llamadas reales se reservan
a una autorización expresa y al runbook correspondiente.

## Evidencia

Cada PR registra comandos, escenarios y resultados de su propio rango. Una
release conserva la evidencia durable en su dossier. Esta guía no se actualiza
por nuevos conteos si los comandos y la política no cambiaron.

La evidencia histórica retirada de esta guía se conserva íntegra en
[`testing-through-v0.3.2.md`](../project/history/testing-through-v0.3.2.md).

## Antes de cerrar una unidad

1. Ejecutar primero pruebas enfocadas y luego la puerta proporcional.
2. Verificar que no hubo llamadas reales ni datos privados.
3. Revisar documentación contractual y QA aplicables.
4. Ejecutar `git diff --check` y revisar el rango completo.
5. Registrar riesgos residuales y recuperación en el PR.
6. Esperar los checks obligatorios antes de integrar.
