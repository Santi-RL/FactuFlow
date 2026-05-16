# Puesta a punto Clawpatch - 2026-05-16

## Objetivo

Habilitar `clawpatch@0.1.0` para revisar backend y frontend sin modificar
logica fiscal, frontend operativo ni flujos ARCA.

## Cambios aplicados

- `.gitignore`: se agrego `.clawpatch/` para mantener el estado local fuera de
  Git.
- `backend/pyproject.toml`: metadata minima del backend Python, sin mover
  dependencias ni configurar `pytest`, `ruff` o `black`.
- `backend/package.json`: manifiesto privado solo para que `clawpatch@0.1.0`
  tenga scripts mapeables del backend. Los scripts usan `.venv`.
- `package.json`: scripts raiz para `init`, `map`, `status` y `review` de
  backend y frontend con `--root` explicito.
- Documentacion: se actualizo la guia de Clawpatch y la matriz de testing.

## Smoke Clawpatch

Comandos ejecutados:

```powershell
npm run clawpatch:backend:init
npm run clawpatch:frontend:init
npm run clawpatch:backend:map
npm run clawpatch:frontend:map
npm run clawpatch:backend:status
npm run clawpatch:frontend:status
```

Resultado:

- Backend: 4 features detectadas.
- Frontend: 6 features detectadas.
- Estado local: `.clawpatch/backend` y `.clawpatch/frontend`, ignorado por Git.
- `clawpatch fix`: no ejecutado.
- Emision fiscal / CAE / ARCA real: no ejecutado.

Nota tecnica: `clawpatch@0.1.0` no trae mapper Python. Por eso
`backend/package.json` funciona como adaptador operativo no invasivo para
exponer scripts existentes.

## Regresion ejecutada

Backend:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m ruff check app tests
.\.venv\Scripts\python.exe -m black --check app tests
```

Resultado:

- `pytest tests -q`: 158 passed, 29 warnings.
- `ruff check app tests`: OK.
- `black --check app tests`: OK, 86 files unchanged.

Frontend:

```powershell
cd frontend
npm run lint:check
npm run type-check
npm run build
npm run test:unit
```

Resultado:

- `npm run lint:check`: 0 errores, 463 warnings existentes de estilo Vue.
- `npm run type-check`: OK.
- `npm run build`: OK.
- `npm run test:unit`: 4 archivos, 17 tests passed.

## Conclusión

La puesta a punto queda habilitada y no cambio comportamiento de producto. La
matriz tecnica posterior paso completa.

## Addendum - features manuales para repo completo

Revision posterior: el adaptador inicial permitia ejecutar Clawpatch, pero el
mapper nativo seguia cubriendo solo scripts/configuracion. Para cubrir codigo
real de FactuFlow se agrego una capa versionada de features manuales:

- `tools/clawpatch/factuflow-features.mjs`
- `tools/clawpatch/seed-features.mjs`
- `tools/clawpatch/seed-features.test.mjs`

Scripts nuevos:

```powershell
npm run clawpatch:test-seeds
npm run clawpatch:map-all
npm run clawpatch:repo:status
npm run clawpatch:backend:status
npm run clawpatch:frontend:status
```

Resultado del smoke posterior:

- `repo`: 4 features end-to-end frontend/backend.
- `backend`: 10 features, incluyendo 6 manuales de codigo FastAPI/Python.
- `frontend`: 10 features, incluyendo 4 manuales de codigo Vue/TS.
- `clawpatch fix`: no ejecutado.
- Emision fiscal / CAE / ARCA real: no ejecutado.

Nota: el nivel `repo` no usa el mapper nativo de la raiz porque puede escanear
carpetas locales ignoradas como `.tmp/`. Usa solo las features manuales, que son
las que dan cobertura util para los flujos criticos.

Tambien se agrego `tools/clawpatch/bin/codex.cmd` para corregir una limitacion
de `clawpatch@0.1.0` en Windows: la CLI invoca `codex exec` con comillas
simples POSIX y `cmd.exe` no las interpreta como quoting. Los scripts de
`review` anteponen ese wrapper al `PATH`.

Ejecucion posterior de review:

- Primer intento completo con `repo` supero el timeout local de 20 minutos, pero
  dejo findings parciales.
- Se limpiaron locks y se ejecuto el feature pendiente de scoping multiemisor de
  forma individual.
- Resultado final `repo`: 4 features revisadas, 21 findings abiertos, 0 locks.
- Los reportes bruto y resumido quedaron como evidencia local ignorada por Git,
  porque incluyen detalles accionables de hallazgos de seguridad abiertos.
  Publicar solo una version sanitizada o subirlos despues de corregir los
  findings.
