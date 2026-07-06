# Puesta a punto de Clawpatch

Este documento define que debe hacer un agente cuando el usuario pida:

> Hagamos los cambios necesarios para ejecutar clawpatch

Objetivo: ejecutar `clawpatch` sobre slices útiles de FactuFlow, dejar reportes
locales para auditoría y publicar solo cierres sanitizados. No modificar
comportamiento fiscal. `review` es solo lectura; `fix` queda prohibido salvo
pedido explícito posterior.

## Estado Actual

`clawpatch` es una CLI en evolución. Usar siempre la CLI global disponible,
sin fijar versión en scripts ni comandos operativos. La documentación upstream
actual indica que el mapper nativo ya detecta Python, pytest y rutas
Flask/FastAPI/Django, además de scripts npm, configuración, frameworks frontend
y otros stacks. Aun así, FactuFlow mantiene una capa propia de features
manuales porque el riesgo principal no es solo tecnológico sino de dominio:
fecha fiscal, CAE, idempotencia, reconciliación, lotes, PDFs fiscales y
aislamiento por emisor.

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

Regla crítica de alcance: `--state-dir` define dónde se guarda el estado, pero
no define qué parte del repo se audita. Para auditar backend, frontend o repo
completo hay que usar los scripts npm de este proyecto o pasar `--root`
explícito. No ejecutar desde la raíz comandos directos como
`clawpatch --state-dir .clawpatch/backend ... review` sin `--root backend`,
porque eso audita el repo completo y puede contaminar el state dir de backend
con features de frontend o tooling general.

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
- 2026-07-06: lecciones operativas sobre uso correcto de `--root`, diferencia
  entre state dir y alcance real, consulta de documentación upstream y manejo de
  un temporal inaccesible en `.tmp/`, documentadas en
  `2026-07-06-lecciones-operativas.md`.

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

Verificación de estado:

```powershell
npm run clawpatch:repo:status
npm run clawpatch:backend:status
npm run clawpatch:frontend:status
```

Comandos directos equivalentes, solo si no se usa npm:

```powershell
clawpatch --root backend --state-dir ../.clawpatch/backend --config ../.clawpatch/backend/config.json status
clawpatch --root backend --state-dir ../.clawpatch/backend --config ../.clawpatch/backend/config.json map
clawpatch --root backend --state-dir ../.clawpatch/backend --config ../.clawpatch/backend/config.json review --limit 50 --jobs 1

clawpatch --root frontend --state-dir ../.clawpatch/frontend --config ../.clawpatch/frontend/config.json status
clawpatch --root . --state-dir .clawpatch/repo --config .clawpatch/repo/config.json status
```

Para ver qué se revisaría sin gastar proveedor:

```powershell
clawpatch --root backend --state-dir ../.clawpatch/backend --config ../.clawpatch/backend/config.json review --limit 50 --jobs 1 --dry-run --json
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

No ejecutar `map --source agent` ni `review` directo desde la raíz contra un
state dir de slice salvo que se quiera deliberadamente una revisión asistida por
proveedor de ese alcance y se pase `--root` correcto. En auditorías normales de
FactuFlow usar `npm run clawpatch:<slice>:map`, porque combina el mapper nativo
con las features manuales versionadas.

No ejecutar `fix`. Si Clawpatch detecta findings, generar reportes locales desde la raíz del repo:

```powershell
clawpatch --root . --state-dir .clawpatch/repo --config .clawpatch/repo/config.json report --output docs/project/audits/clawpatch/repo-YYYY-MM-DD.md
clawpatch --root . --state-dir .clawpatch/backend --config .clawpatch/backend/config.json report --output docs/project/audits/clawpatch/backend-YYYY-MM-DD.md
clawpatch --root . --state-dir .clawpatch/frontend --config .clawpatch/frontend/config.json report --output docs/project/audits/clawpatch/frontend-YYYY-MM-DD.md
```

Para consumo automático, preferir `report --json` y leer `items`; en la salida
JSON la clave `findings` es un contador de compatibilidad, no el arreglo de
findings.

Los findings deben triagearse antes de reparar. Estados útiles:

```powershell
clawpatch --root backend --state-dir ../.clawpatch/backend --config ../.clawpatch/backend/config.json show --finding <id>
clawpatch --root backend --state-dir ../.clawpatch/backend --config ../.clawpatch/backend/config.json triage --finding <id> --status false-positive --note "motivo"
clawpatch --root backend --state-dir ../.clawpatch/backend --config ../.clawpatch/backend/config.json revalidate --finding <id>
```

## Política Para Usar `clawpatch fix`

`clawpatch fix` no es el camino normal para resolver hallazgos sensibles de
FactuFlow. Es una herramienta de parche asistido para un finding aceptado,
localizado y de bajo riesgo relativo. Solo puede ejecutarse con pedido explícito
del usuario, worktree limpio, finding ID concreto y entendiendo que el diff debe
revisarse manualmente antes de conservarlo.

Usar `clawpatch fix` cuando se cumplan todas estas condiciones:

- El finding ya fue triageado como real o altamente probable.
- El alcance está acotado a uno o pocos archivos.
- La reparación esperada es mecánica o local: validación faltante, manejo de
  error, script roto, contrato menor, test faltante o limpieza de complejidad.
- Hay comandos de validación o tests enfocados razonables para verificar el
  cambio.
- El cambio no requiere decidir política fiscal, migración de datos, nuevo
  estado de negocio ni coordinación amplia entre backend, frontend y docs.

Reparar manualmente, sin delegar el cambio principal a `clawpatch fix`, cuando
el finding toque cualquiera de estos temas:

- ARCA, WSAA, WSFE, CAE, numeración fiscal o `FECAESolicitar`.
- Fecha fiscal, confirmación irreversible, idempotencia, reintentos,
  reconciliación o estados inciertos post-ARCA.
- Emisión individual, emisión masiva, lotes, worker o sublotes ARCA.
- Migraciones, borrado de historial fiscal, certificados, datos fiscales,
  multiemisor, permisos o aislamiento entre emisores.
- PDFs fiscales, reportes impositivos o datos que puedan quedar como evidencia
  operativa.
- Cualquier caso donde primero haya que definir invariantes, tabla de estados,
  rollback/reconciliación, migración o matriz de tests.

Para esos hallazgos sensibles, el flujo esperado es: diseño manual con
`docs/agents/fiscal-change-checklist.md` si aplica, tests de regresión, cambio
pequeño y revisable, validaciones enfocadas, documentación viva y recién después
revalidación con Clawpatch. Si `fix` se usa en un subproblema mecánico dentro de
ese trabajo, tratar su diff como propuesta externa y revisarlo línea por línea.

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
