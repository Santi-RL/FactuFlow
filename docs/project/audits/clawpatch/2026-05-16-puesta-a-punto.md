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
