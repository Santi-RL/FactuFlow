# Puesta a punto de Clawpatch

Este documento define que debe hacer un agente cuando el usuario pida:

> Hagamos los cambios necesarios para ejecutar clawpatch

Objetivo: ejecutar `clawpatch` sobre slices útiles de FactuFlow, dejar reportes
locales para auditoría y publicar solo cierres sanitizados. No modificar
comportamiento fiscal. `review` es solo lectura; `fix` queda prohibido salvo
pedido explícito posterior.

## Estado Actual

`clawpatch` es una CLI en evolución. Usar siempre la CLI global disponible,
sin fijar versión en scripts ni comandos operativos. Su mapper nativo detecta
scripts npm, configuración, Next, Go, Rust y Swift, pero no entiende por sí
solo el backend FastAPI/Python ni las vistas/stores Vue de FactuFlow.

Por eso FactuFlow agrega una capa propia de features manuales en:

```text
tools/clawpatch/factuflow-features.mjs
tools/clawpatch/seed-features.mjs
```

Esa capa genera feature records en `.clawpatch/` con archivos reales de backend,
frontend y flujos end-to-end. El estado `.clawpatch/` es local e ignorado por
Git. Los reportes crudos de findings también quedan locales cuando detallan
vulnerabilidades abiertas; versionar solo cierres operativos o resúmenes
sanitizados.

En Windows, algunas versiones de `clawpatch` invocan `codex exec` con comillas
simples estilo POSIX. Los scripts de `review` anteponen
`tools/clawpatch/bin` al `PATH` para usar un wrapper local de `codex.cmd` que
normaliza esas comillas antes de llamar al Codex CLI real. No usar
`npx clawpatch review` directo en Windows si se espera que invoque el proveedor
`codex`; usar los scripts npm.

Nota de lectura: los reportes con fecha guardados en esta carpeta son evidencia histórica o cierres sanitizados de auditorías puntuales. Para conocer el estado vigente de hallazgos abiertos, usar primero los comandos `clawpatch ... status`, `docs/agents/current-status.md` y el cierre más reciente documentado. No usar un reporte viejo como backlog actual sin revalidarlo. `VISION.md` sigue siendo la fuente superior para decisiones de producto.

## Cierres relevantes

- 2026-05-16/17: primera reparación grande derivada de Clawpatch, documentada en
  `2026-05-16-reparaciones.md`.
- 2026-07-05: auditoría backend, frontend y repo completo cerrada con
  `openFindings=0` en los tres state dirs. Cierre y lecciones en
  `2026-07-05-cierre-auditoria.md`.

## Lecciones 2026-07-05

- No fijar versión de Clawpatch en scripts ni comandos. Usar `clawpatch` global
  y conservar `--state-dir` / `--config` explícitos.
- `revalidate --finding <id> --include-dirty` puede no seleccionar un hallazgo
  duplicado en otro nivel de feature aunque `show` lo liste. Revalidar primero
  el duplicado seleccionable y solo hacer `triage --status fixed` manual con
  nota si ambos apuntan al mismo bloque corregido.
- No usar `pagehide`/`unload` de una ventana recién abierta para limpiar blobs de
  preview: pueden dispararse durante la navegación inicial de `about:blank` al
  `blob:`. Preferir `load` y fallback largo.
- Para fechas visibles en FactuFlow, `DD/MM/AAAA` es formato soportado y debe
  validarse como tal. Los formatos ISO quedan para contratos técnicos.
- Después de cambios aceptados por `autoreview`, repetir tests enfocados y
  volver a correr `autoreview` sobre el commit final.

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

Desde la raíz:

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

- `repo`: mapper nativo de Clawpatch sobre un snapshot temporal de archivos
  versionables/no ignorados, más features manuales end-to-end. El snapshot evita
  carpetas locales ignoradas, evidencia privada y errores de `realpath` sobre
  `.tmp/`; el estado final se escribe en `.clawpatch/repo`.
- `backend`: mapper nativo de Clawpatch más features manuales FastAPI/Python.
- `frontend`: mapper nativo de Clawpatch más features manuales Vue/TS.

Verificacion de estado:

```powershell
npm run clawpatch:repo:status
npm run clawpatch:backend:status
npm run clawpatch:frontend:status
```

Criterio esperado con la puesta a punto actual:

- Los tres `status` deben responder sin error y mostrar el estado local de cada
  slice.
- No fijar el cierre a una cantidad exacta de features: el mapper nativo puede
  variar según la versión instalada de `clawpatch`. Registrar los conteos
  observados al cerrar cada auditoría.

## Features Manuales

Las features manuales versionadas cubren:

- emisión individual, fecha fiscal, confirmación final, numeración y CAE;
- lotes por Excel, formatos, perfiles, progreso, concurrencia y worker;
- certificados, WSAA/WSFE, cache, paths y puntos de venta ARCA;
- PDF, QR ARCA y reportes;
- auth, permisos y scoping por emisor activo;
- UI de emisión masiva e individual;
- UI de certificados, puntos, dashboard y reportes;
- flujos end-to-end que cruzan frontend y backend.

Si se agregan módulos críticos nuevos, actualizar
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

No ejecutar `fix`. Si Clawpatch detecta findings, generar reportes locales desde la raíz del repo:

```powershell
clawpatch --root . --state-dir .clawpatch/repo --config .clawpatch/repo/config.json report --output docs/project/audits/clawpatch/repo-YYYY-MM-DD.md
clawpatch --root . --state-dir .clawpatch/backend --config .clawpatch/backend/config.json report --output docs/project/audits/clawpatch/backend-YYYY-MM-DD.md
clawpatch --root . --state-dir .clawpatch/frontend --config .clawpatch/frontend/config.json report --output docs/project/audits/clawpatch/frontend-YYYY-MM-DD.md
```

Si se consolida manualmente, usar una versión local ignorada o un resumen
sanitizado público:

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

Regresión técnica mínima si solo se toca esta puesta a punto:

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

Para cambios solo en `tools/clawpatch/` y documentación, `npm run
clawpatch:test-seeds` y `npm run clawpatch:map-all` son el check específico.
La regresion backend/frontend completa se corre si se toca código de producto o
si algún reporte de Clawpatch obliga a revisar una zona funcional.

## Que No Hacer

- No migrar dependencias Python desde `requirements.txt` a `pyproject.toml`.
- No cambiar comandos de arranque, Docker ni Alembic.
- No tocar servicios de emisión, lotes, certificados, ARCA ni frontend durante
  la puesta a punto salvo que un test falle por la propia configuración.
- No ejecutar `clawpatch fix`.
- No commitear `.clawpatch/`.

## Cierre Esperado

Al terminar, informar:

- comandos ejecutados;
- resultado de tests;
- cantidad de features detectadas por `repo`, `backend` y `frontend`;
- ubicación de reportes generados;
- confirmación de que no se ejecutó `clawpatch fix`.
