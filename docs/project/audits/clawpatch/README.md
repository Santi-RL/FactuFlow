# Puesta a punto de Clawpatch

Este documento describe qué debe hacer un agente cuando el usuario pida:

> Hagamos los cambios necesarios para ejecutar clawpatch

Objetivo: dejar `clawpatch` usable para revisar FactuFlow completo sin cambiar
comportamiento fiscal ni de frontend. La revisión debe producir reportes
versionables en esta carpeta y mantener el estado interno de `clawpatch` fuera
del historial Git.

## Estado Actual

El 2026-05-16 se probó `clawpatch@0.1.0` y no pudo mapear bien FactuFlow:

- desde la raíz del repo detectó `0` features;
- desde `backend/` detectó `0` features porque `clawpatch@0.1.0` todavía no
  tiene mapper Python; `pyproject.toml` por sí solo no alcanza;
- desde `frontend/` detectó solo scripts/configuración, no una cobertura útil
  de vistas, servicios y stores.

Por eso la puesta a punto debe hacer que `clawpatch` tenga entradas explícitas
para backend y frontend, y debe validar que el cambio no altera la app.

## Reglas De Seguridad

- No ejecutar `clawpatch fix` durante la puesta a punto.
- No emitir comprobantes, no pedir CAE y no llamar endpoints reales de ARCA.
- No commitear `.clawpatch/`, bases locales, certificados, Excel privados,
  PDFs, logs ni evidencia local.
- No agregar defaults fiscales. En particular, no introducir `date.today()`,
  `datetime.today()` ni `new Date()` como default de `fecha_emision`/`CbteFch`.
- Mantener ARCA en textos nuevos; AFIP solo queda como legacy en URLs o
  variables existentes.

## Cambios A Realizar

### 1. Ignorar el estado local de Clawpatch

Agregar a `.gitignore`:

```gitignore
# Clawpatch local state
.clawpatch/
```

Los reportes Markdown sí deben quedar versionados en:

```text
docs/project/audits/clawpatch/
```

### 2. Agregar metadata mínima para backend

Crear `backend/pyproject.toml` con metadata mínima del proyecto Python. No
mover dependencias desde `requirements.txt` todavía.

Contenido recomendado:

```toml
[project]
name = "factuflow-backend"
version = "0.2.0"
description = "Backend FastAPI de FactuFlow"
requires-python = ">=3.11"
```

Este archivo no debe declarar configuración de `pytest`, `ruff` ni `black`
mientras existan `backend/pytest.ini` y los comandos documentados en
`docs/agents/testing.md`. Así evitamos cambiar el comportamiento de tooling.

### 3. Agregar manifiesto operativo para backend

Crear `backend/package.json` solo como adaptador operativo para
`clawpatch@0.1.0`, que sí mapea scripts npm. Debe ser privado, no debe declarar
dependencias y no reemplaza el manejo Python existente.

Contenido recomendado:

```json
{
  "name": "factuflow-backend",
  "version": "0.2.0",
  "private": true,
  "scripts": {
    "test": ".\\.venv\\Scripts\\python.exe -m pytest tests -q",
    "lint": ".\\.venv\\Scripts\\python.exe -m ruff check app tests",
    "format": ".\\.venv\\Scripts\\python.exe -m black --check app tests"
  }
}
```

### 4. Agregar manifiesto raíz para orquestar auditorías

Crear un `package.json` en la raíz solo para scripts operativos de auditoría.
Debe ser privado y no debe reemplazar el `frontend/package.json`.

Contenido recomendado:

```json
{
  "name": "factuflow",
  "version": "0.2.0",
  "private": true,
  "scripts": {
    "clawpatch:backend:init": "npx -y clawpatch@0.1.0 --root backend --state-dir ../.clawpatch/backend init",
    "clawpatch:backend:map": "npx -y clawpatch@0.1.0 --root backend --state-dir ../.clawpatch/backend map",
    "clawpatch:backend:status": "npx -y clawpatch@0.1.0 --root backend --state-dir ../.clawpatch/backend status --json",
    "clawpatch:backend:review": "npx -y clawpatch@0.1.0 --root backend --state-dir ../.clawpatch/backend review --limit 10 --jobs 2",
    "clawpatch:frontend:init": "npx -y clawpatch@0.1.0 --root frontend --state-dir ../.clawpatch/frontend init",
    "clawpatch:frontend:map": "npx -y clawpatch@0.1.0 --root frontend --state-dir ../.clawpatch/frontend map",
    "clawpatch:frontend:status": "npx -y clawpatch@0.1.0 --root frontend --state-dir ../.clawpatch/frontend status --json",
    "clawpatch:frontend:review": "npx -y clawpatch@0.1.0 --root frontend --state-dir ../.clawpatch/frontend review --limit 10 --jobs 2"
  }
}
```

No agregar dependencias npm en la raíz salvo que se decida fijar `clawpatch`
como dev dependency. Para una primera puesta a punto alcanza con `npx -y
clawpatch@0.1.0`.

Nota: en `clawpatch@0.1.0`, `--state-dir` se resuelve relativo al `--root`.
Por eso se usa `../.clawpatch/...` para que el estado quede en la raíz del repo.

### 5. Inicializar y mapear por área

Ejecutar desde la raíz:

```powershell
npm run clawpatch:backend:init
npm run clawpatch:backend:map
npm run clawpatch:frontend:init
npm run clawpatch:frontend:map
```

Luego verificar:

```powershell
npm run clawpatch:backend:status
npm run clawpatch:frontend:status
```

Criterio de aceptación:

- backend debe tener `features > 0`;
- frontend debe tener `features > 0`;
- si alguno queda en `0`, no seguir con `review`; documentar la limitación en
  un reporte y ajustar la estrategia antes de insistir.

### 6. Ejecutar review sin fixes

Solo si el mapeo fue útil:

```powershell
npm run clawpatch:backend:review
npm run clawpatch:frontend:review
```

Generar reportes versionables:

```powershell
npx -y clawpatch@0.1.0 --root backend --state-dir ../.clawpatch/backend report -o ../docs/project/audits/clawpatch/backend-YYYY-MM-DD.md
npx -y clawpatch@0.1.0 --root frontend --state-dir ../.clawpatch/frontend report -o ../docs/project/audits/clawpatch/frontend-YYYY-MM-DD.md
```

Si se genera un resumen manual, usar:

```text
docs/project/audits/clawpatch/resumen-YYYY-MM-DD.md
```

## Tests Obligatorios

Estos checks deben correr después de aplicar la puesta a punto y antes de
commitear. Como la puesta a punto no debe tocar lógica de negocio, cualquier
fallo debe tratarse como regresión o como problema de entorno que hay que
documentar.

### Backend crítico

```powershell
cd backend
python -m pytest tests/test_lotes_comprobantes.py tests/test_facturacion_service.py tests/test_comprobantes_api.py -q
ruff check app tests
black --check app tests
```

Estos tests cubren la barrera fiscal, emisión individual, lotes, confirmación de
fecha fiscal y reglas principales de facturación.

### Backend completo

```powershell
cd backend
python -m pytest tests -q
```

### Frontend

```powershell
cd frontend
npm run lint:check
npm run type-check
npm run build
npm run test:unit
```

No usar `npm run lint` como check, porque ejecuta ESLint con `--fix` y puede
modificar archivos.

### Smoke de Clawpatch

```powershell
npm run clawpatch:backend:map
npm run clawpatch:frontend:map
npm run clawpatch:backend:status
npm run clawpatch:frontend:status
```

Registrar en el commit o en el reporte cuántas features detectó cada área.

## Qué No Hacer En Esta Tarea

- No migrar dependencias Python desde `requirements.txt` a `pyproject.toml`.
- No cambiar comandos de arranque, Docker ni Alembic.
- No tocar servicios de emisión, lotes, certificados, ARCA ni frontend salvo que
  un test falle por la propia puesta a punto.
- No ejecutar `clawpatch fix`.
- No commitear `.clawpatch/`.

## Cierre Esperado

Al terminar, el diff debería contener como máximo:

- `.gitignore`
- `backend/pyproject.toml`
- `backend/package.json`
- `package.json` raíz
- reportes nuevos en `docs/project/audits/clawpatch/`
- opcionalmente una referencia breve en `docs/agents/current-status.md`

El cierre debe indicar:

- comandos ejecutados;
- resultado de los tests;
- cantidad de features detectadas por backend y frontend;
- ubicación de los reportes;
- confirmación de que no se ejecutó `clawpatch fix`.
