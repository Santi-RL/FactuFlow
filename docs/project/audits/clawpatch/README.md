# Puesta a punto de Clawpatch

Este documento define que debe hacer un agente cuando el usuario pida:

> Hagamos los cambios necesarios para ejecutar clawpatch

Objetivo: ejecutar `clawpatch` sobre slices utiles de FactuFlow, dejar reportes
locales para auditoria y publicar solo cierres sanitizados. No modificar
comportamiento fiscal. `review` es solo lectura; `fix` queda prohibido salvo
pedido explicito posterior.

## Estado Actual

`clawpatch@0.1.0` es una CLI temprana. Su mapper nativo detecta scripts npm,
configuracion, Next, Go, Rust y Swift, pero no entiende por si solo el backend
FastAPI/Python ni las vistas/stores Vue de FactuFlow.

Por eso FactuFlow agrega una capa propia de features manuales en:

```text
tools/clawpatch/factuflow-features.mjs
tools/clawpatch/seed-features.mjs
```

Esa capa genera feature records en `.clawpatch/` con archivos reales de backend,
frontend y flujos end-to-end. El estado `.clawpatch/` es local e ignorado por
Git. Los reportes crudos de findings tambien quedan locales cuando detallan
vulnerabilidades abiertas; versionar solo cierres operativos o resumenes
sanitizados.

En Windows, `clawpatch@0.1.0` invoca `codex exec` con comillas simples estilo
POSIX. Los scripts de `review` anteponen `tools/clawpatch/bin` al `PATH` para
usar un wrapper local de `codex.cmd` que normaliza esas comillas antes de llamar
al Codex CLI real. No usar `npx clawpatch review` directo en Windows si se
espera que invoque el proveedor `codex`; usar los scripts npm.

## Reglas De Seguridad

- No ejecutar `clawpatch fix`.
- No emitir comprobantes, no pedir CAE y no llamar endpoints reales de ARCA.
- No commitear `.clawpatch/`, bases locales, certificados, Excel privados,
  PDFs, logs ni evidencia local.
- No introducir `date.today()`, `datetime.today()` ni `new Date()` como default
  fiscal para `fecha_emision`/`CbteFch`.
- Mantener ARCA en textos nuevos; AFIP solo queda como legacy en URLs o
  variables existentes.

## Scripts Disponibles

Desde la raiz:

```powershell
npm run clawpatch:repo:init
npm run clawpatch:backend:init
npm run clawpatch:frontend:init
```

Si alguno ya estaba inicializado, `init` puede fallar con
`project already initialized`; en ese caso seguir con `map`.

Mapeo completo recomendado:

```powershell
npm run clawpatch:map-all
```

Este comando ejecuta:

- `repo`: solo features manuales end-to-end. No usa el mapper nativo de la raiz
  porque puede intentar escanear carpetas locales ignoradas como `.tmp/`.
- `backend`: mapper nativo de Clawpatch mas features manuales FastAPI/Python.
- `frontend`: mapper nativo de Clawpatch mas features manuales Vue/TS.

Verificacion de estado:

```powershell
npm run clawpatch:repo:status
npm run clawpatch:backend:status
npm run clawpatch:frontend:status
```

Criterio esperado con la puesta a punto actual:

- `repo`: 4 features end-to-end.
- `backend`: 10 features, incluyendo 6 manuales de codigo real.
- `frontend`: 10 features, incluyendo 4 manuales de codigo real.

## Features Manuales

Las features manuales versionadas cubren:

- emision individual, fecha fiscal, confirmacion final, numeracion y CAE;
- lotes por Excel, formatos, perfiles, progreso, concurrencia y worker;
- certificados, WSAA/WSFE, cache, paths y puntos de venta ARCA;
- PDF, QR ARCA y reportes;
- auth, permisos y scoping por emisor activo;
- UI de emision masiva e individual;
- UI de certificados, puntos, dashboard y reportes;
- flujos end-to-end que cruzan frontend y backend.

Si se agregan modulos criticos nuevos, actualizar
`tools/clawpatch/factuflow-features.mjs` y correr:

```powershell
npm run clawpatch:test-seeds
npm run clawpatch:map-all
```

## Ejecutar Review

Ejecutar primero el nivel end-to-end:

```powershell
npm run clawpatch:repo:review
```

Los scripts usan `--jobs 1`. Es mas lento, pero evita fallos de proveedor en
Windows y deja cada feature en estado recuperable si una corrida se corta. Si
queda un lock por timeout:

```powershell
npm run clawpatch:repo:clean-locks
npm run clawpatch:repo:map
```

Luego, si hace falta profundizar:

```powershell
npm run clawpatch:backend:review
npm run clawpatch:frontend:review
```

No ejecutar `fix`. Si Clawpatch detecta findings, generar reportes locales:

```powershell
npx -y clawpatch@0.1.0 --root . --state-dir .clawpatch/repo report -o docs/project/audits/clawpatch/repo-YYYY-MM-DD.md
npx -y clawpatch@0.1.0 --root backend --state-dir ../.clawpatch/backend report -o ../docs/project/audits/clawpatch/backend-YYYY-MM-DD.md
npx -y clawpatch@0.1.0 --root frontend --state-dir ../.clawpatch/frontend report -o ../docs/project/audits/clawpatch/frontend-YYYY-MM-DD.md
```

Si se consolida manualmente, usar una version local ignorada o un resumen
sanitizado publico:

```text
docs/project/audits/clawpatch/resumen-YYYY-MM-DD.md
```

## Tests Obligatorios

Smoke de la capa manual:

```powershell
npm run clawpatch:test-seeds
npm run clawpatch:map-all
npm run clawpatch:repo:status
npm run clawpatch:backend:status
npm run clawpatch:frontend:status
```

Regresion tecnica minima si solo se toca esta puesta a punto:

```powershell
cd backend
python -m pytest tests/test_lotes_comprobantes.py tests/test_facturacion_service.py tests/test_comprobantes_api.py -q
ruff check app tests
black --check app tests

cd ../frontend
npm run lint:check
npm run type-check
npm run build
npm run test:unit
```

Para cambios solo en `tools/clawpatch/` y documentacion, `npm run
clawpatch:test-seeds` y `npm run clawpatch:map-all` son el check especifico.
La regresion backend/frontend completa se corre si se toca codigo de producto o
si algun reporte de Clawpatch obliga a revisar una zona funcional.

## Que No Hacer

- No migrar dependencias Python desde `requirements.txt` a `pyproject.toml`.
- No cambiar comandos de arranque, Docker ni Alembic.
- No tocar servicios de emision, lotes, certificados, ARCA ni frontend durante
  la puesta a punto salvo que un test falle por la propia configuracion.
- No ejecutar `clawpatch fix`.
- No commitear `.clawpatch/`.

## Cierre Esperado

Al terminar, informar:

- comandos ejecutados;
- resultado de tests;
- cantidad de features detectadas por `repo`, `backend` y `frontend`;
- ubicacion de reportes generados;
- confirmacion de que no se ejecuto `clawpatch fix`.
