# Puesta a punto de Clawpatch

Este documento define que debe hacer un agente cuando el usuario pida:

> Hagamos los cambios necesarios para ejecutar clawpatch

Objetivo: ejecutar `clawpatch` sobre slices útiles de FactuFlow, dejar reportes
locales para auditoría y publicar solo cierres sanitizados. No modificar
comportamiento fiscal. `review` es solo lectura; `fix` queda prohibido salvo
pedido explícito posterior.

Este archivo es el runbook operativo obligatorio y debe leerse completo antes
de ejecutar Clawpatch. Debe mantenerse actualizado durante cada ciclo con los
aprendizajes confirmados de la herramienta y del entorno de FactuFlow.

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
- 2026-07-10: ciclo de endurecimiento cerrado en `v0.2.1`, con metodología,
  interpretación del registro acumulativo y punto de reanudación en
  `2026-07-10-cierre-ciclo-v0.2.1.md`.
- 2026-07-12: auditoría completa ordenada con Clawpatch `0.7.0`, reconstrucción
  autorizada del ledger backend, evaluación controlada de `jobs` y backlog
  sanitizado en `2026-07-12-cierre-auditoria-ordenada.md`.

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

## Lecciones 2026-07-12

- En FactuFlow sobre Windows, comenzar `repo` y el primer lote grande de
  `backend` con `--jobs 1`. Solo probar `--jobs 2` en el lote siguiente si la
  pasada anterior terminó sin timeouts, errores de proveedor ni locks. Mantener
  `2` únicamente si el lote controlado también cierra limpio; no escalar más
  durante el mismo ciclo sin una nueva evaluación explícita.
- Con Clawpatch `0.7.0`, Codex CLI `0.144.0`, `gpt-5.6-sol` y `high`, los lotes
  controlados de FactuFlow cerraron correctamente con `jobs=2`. Esto es una
  observación del entorno, no un valor universal ni una garantía para versiones
  futuras.
- Los scripts npm de review fijan `--jobs 1`. Para una pasada aprobada con
  `jobs=2`, usar la CLI global directa y repetir siempre el mismo `--root`,
  `--state-dir`, `--config`, proveedor, modelo y razonamiento.
- Ejecutados desde la raíz del repo, los reportes backend y frontend deben usar
  `.tmp/...`, no `../.tmp/...`; esa segunda ruta apunta fuera de FactuFlow.
- En Clawpatch `0.7.0`, `report --json` entrega el JSON por stdout. Si además se
  pasa `--output`, no asumir que ese archivo será JSON: para automatización,
  capturar stdout y leer `items`.
- Para `triage --note` con espacios en Windows, usar la CLI global directa. El
  wrapper local de review puede fragmentar la nota al atravesar `cmd.exe`.
- Antes de aceptar un finding `test-gap` que afirme que una vista o flujo carece
  de pruebas, buscar suites hermanas en todo el slice con `rg --files` y
  contrastar su contenido. El contexto seleccionado por una feature puede omitir
  un `*.spec.ts` existente; si la premisa principal es falsa, triagear el finding
  como `false-positive` y registrar los gaps residuales por separado.
- Clawpatch `0.7.0` no ofrece un estado `deferred`: para un riesgo real P2/P3,
  conservar `status=open` y usar una nota de triage con PF y prioridad. Reservar
  `wont-fix` para una decisión permanente y `false-positive` para una premisa
  refutada.

## Reglas De Seguridad

- Durante `review`, reporte y triage no ejecutar `clawpatch fix`. Solo puede
  considerarse después, con pedido explícito y bajo la política de esta guía.
- No emitir comprobantes, no pedir CAE y no llamar endpoints reales de ARCA.
- No commitear `.clawpatch/`, bases locales, certificados, Excel privados,
  PDFs, logs ni evidencia local.
- No introducir `date.today()`, `datetime.today()` ni `new Date()` como default
  fiscal para `fecha_emision`/`CbteFch`.
- Mantener ARCA en textos nuevos; AFIP solo queda como legacy en URLs o
  variables existentes.

## Runbook Obligatorio Para Auditorías

### 1. Preflight

Desde la raíz, confirmar primero que el alcance y el worktree sean los
esperados:

```powershell
git status --short --branch
clawpatch --version
clawpatch doctor
```

Si hay cambios de una implementación anterior, commits locales pendientes o un
proveedor no disponible, detener la auditoría y resolver ese estado antes de
acumular una corrida nueva. `doctor` comprueba el proveedor; no reemplaza los
tests ni el control de Git.

### 2. Modelo Y Reproducibilidad

Para reviews y revalidaciones usar explícitamente Codex con `gpt-5.6-sol` y
razonamiento `high`. No depender del modelo predeterminado de la CLI local:

```powershell
npm run clawpatch:repo:review -- --model gpt-5.6-sol --reasoning-effort high
```

Si `gpt-5.6-sol` no puede ejecutarse después de un reintento razonable, usar
`gpt-5.5` con `high`. Registrar siempre proveedor, modelo y razonamiento reales
en el cierre. No hacer automáticamente una escalera de niveles de razonamiento.

### 3. Preparación Del Mapa

Validar primero las features manuales, regenerar los tres mapas y comprobar el
estado antes de consumir proveedor:

```powershell
npm run clawpatch:test-seeds
npm run clawpatch:map-all
npm run clawpatch:repo:status
npm run clawpatch:backend:status
npm run clawpatch:frontend:status
```

Después ejecutar un `dry-run --json` del slice que se va a revisar. En Windows,
utilizar el wrapper local para conservar el manejo correcto de Codex:

```powershell
node tools/clawpatch/run-clawpatch.mjs --root . --state-dir .clawpatch/repo --config .clawpatch/repo/config.json review --limit 50 --jobs 1 --dry-run --json --model gpt-5.6-sol --reasoning-effort high
```

El dry-run debe usarse para registrar cantidad y orden de features, no para
inferir que no existen bugs.

### 4. Orden De Revisión

Ejecutar una etapa por vez y generar un checkpoint de `status` y reporte antes
de avanzar:

1. `repo`, para riesgos end-to-end y contratos entre capas;
2. reporte y triage de `repo`;
3. `backend`, en lotes de hasta 50 features;
4. reporte y triage de cada lote backend;
5. `frontend`;
6. reporte, triage y consolidación final.

No ejecutar reviews de distintos slices en paralelo. Los scripts usan
`--jobs 1`; conservarlo para `repo` y el primer lote grande de `backend`. Si ese
lote termina sin timeouts, errores de proveedor ni locks, evaluar `--jobs 2` en
un único lote controlado y conservarlo solo si vuelve a cerrar limpio. No subir
automáticamente a `3` o más. Si quedan features pendientes después de un lote,
revisar el estado y repetir el mismo slice antes de pasar al siguiente.

### 5. Archivo O Reconstrucción De Estado

Un state dir solo puede limpiarse o reconstruirse con decisión explícita del
usuario. Antes de retirar el estado activo:

1. archivar el ledger completo bajo
   `.tmp/clawpatch/archive/<slice>-ledger-AAAA-MM-DD.zip`;
2. generar un inventario con features, findings por estado, reports y runs;
3. calcular y registrar SHA-256;
4. comprobar que el ZIP contiene `config.json` y `project.json`;
5. verificar nuevamente el hash;
6. recién entonces limpiar o reconstruir el slice autorizado.

El archivo preserva trazabilidad; no convierte sus findings en backlog vigente.
No borrar ni reinicializar estados para ocultar contadores grandes.

### 6. Aprendizaje Continuo

Durante el uso de Clawpatch, registrar fricciones, fallos, workarounds y mejoras
de interpretación. Incorporar en este runbook, dentro del mismo ciclo, todo
aprendizaje que sea confirmado, reproducible y útil para futuras auditorías.

- Actualizar `AGENTS.md` solo si aparece una regla obligatoria de seguridad,
  autorización o alcance.
- Mantener aquí comandos, orden de ejecución, recuperación, rendimiento,
  compatibilidad de Windows y criterios de interpretación.
- Usar documentos fechados para evidencia y cierres históricos, no como runbook
  vigente.
- Distinguir comportamiento observado de hipótesis. Un workaround no verificado
  debe quedar marcado como pendiente y no convertirse en regla.
- Si cambia el comportamiento upstream, registrar versión y fecha observadas,
  ajustar wrappers o tests si corresponde y verificar el nuevo procedimiento.
- Sanitizar siempre la documentación: no incluir secretos, datos fiscales,
  evidencia privada ni detalles explotables de findings abiertos.

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

En algunas sesiones de Codex sobre Windows, el wrapper puede terminar con
código 0 pero su stdout heredado no aparecer en la captura. Salida vacía no
significa `openFindings=0`. Repetir con el comando directo equivalente o leer
los JSON de findings y agrupar `status`; registrar siempre la evidencia usada.

Comandos directos equivalentes, solo si no se usa npm:

```powershell
clawpatch --root backend --state-dir ../.clawpatch/backend --config ../.clawpatch/backend/config.json status
clawpatch --root backend --state-dir ../.clawpatch/backend --config ../.clawpatch/backend/config.json map
clawpatch --root backend --state-dir ../.clawpatch/backend --config ../.clawpatch/backend/config.json review --limit 50 --jobs 1 --model gpt-5.6-sol --reasoning-effort high

clawpatch --root frontend --state-dir ../.clawpatch/frontend --config ../.clawpatch/frontend/config.json status
clawpatch --root . --state-dir .clawpatch/repo --config .clawpatch/repo/config.json status
```

Para ver qué se revisaría sin gastar proveedor:

```powershell
clawpatch --root backend --state-dir ../.clawpatch/backend --config ../.clawpatch/backend/config.json review --limit 50 --jobs 1 --model gpt-5.6-sol --reasoning-effort high --dry-run --json
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
npm run clawpatch:repo:review -- --model gpt-5.6-sol --reasoning-effort high
```

Los scripts usan `--jobs 1` como punto de partida conservador y dejan cada
feature en estado recuperable si una corrida se corta. Después de validar un
lote estable puede usarse la CLI directa con `--jobs 2`, siguiendo el criterio
de la sección **Orden De Revisión**. Si queda un lock por timeout:

```powershell
npm run clawpatch:repo:clean-locks
npm run clawpatch:repo:map
```

Después de generar el reporte y triar `repo`, profundizar por separado:

```powershell
npm run clawpatch:backend:review -- --model gpt-5.6-sol --reasoning-effort high
npm run clawpatch:frontend:review -- --model gpt-5.6-sol --reasoning-effort high
```

No lanzar ambos comandos juntos. Cada script procesa hasta 50 features; si el
slice conserva pendientes, repetirlo después de revisar `status` y el reporte
del lote anterior.

No ejecutar `map --source agent` ni `review` directo desde la raíz contra un
state dir de slice salvo que se quiera deliberadamente una revisión asistida por
proveedor de ese alcance y se pase `--root` correcto. En auditorías normales de
FactuFlow usar `npm run clawpatch:<slice>:map`, porque combina el mapper nativo
con las features manuales versionadas.

No ejecutar `fix` durante esta fase. Si Clawpatch detecta findings, generar
reportes crudos en una carpeta ignorada, nunca directamente como documentación
pública:

```powershell
clawpatch --root . --state-dir .clawpatch/repo --config .clawpatch/repo/config.json report --status open --output .tmp/clawpatch/repo-YYYY-MM-DD.md
clawpatch --root backend --state-dir ../.clawpatch/backend --config ../.clawpatch/backend/config.json report --status open --output .tmp/clawpatch/backend-YYYY-MM-DD.md
clawpatch --root frontend --state-dir ../.clawpatch/frontend --config ../.clawpatch/frontend/config.json report --status open --output .tmp/clawpatch/frontend-YYYY-MM-DD.md
```

Para consumo automático, preferir `report --status open --json` y leer `items`;
en la salida JSON la clave `findings` es un contador de compatibilidad, no el
arreglo de findings. En Clawpatch `0.7.0`, capturar el JSON desde stdout: no
presuponer que `--json --output archivo.json` escribirá JSON en el archivo.

### Interpretación de reportes grandes

`.clawpatch/` es un registro acumulativo persistente. Un reporte puede crecer por findings
históricos, duplicados entre niveles de feature, IDs ya corregidos bajo otra
feature y registros de una corrida con alcance incorrecto. `map` actualiza el
mapeo, pero no garantiza purgar todo el historial previo.

Por eso:

- usar `--status open`;
- filtrar por evidencia y propiedad reales del código;
- comparar cada finding con el código actual;
- no sumar el contador como cantidad de bugs aceptados;
- no borrar ni reinicializar el state dir sin decisión explícita;
- publicar solo un resumen sanitizado después del triage.

Los findings deben triagearse antes de reparar. Estados útiles:

```powershell
clawpatch --root backend --state-dir ../.clawpatch/backend --config ../.clawpatch/backend/config.json show --finding <id>
clawpatch --root backend --state-dir ../.clawpatch/backend --config ../.clawpatch/backend/config.json triage --finding <id> --status false-positive --note "motivo"
clawpatch --root backend --state-dir ../.clawpatch/backend --config ../.clawpatch/backend/config.json revalidate --finding <id> --model gpt-5.6-sol --reasoning-effort high
```

En Windows, ejecutar `triage` con la CLI global directa. No pasar notas con
espacios por el wrapper local de review, porque `cmd.exe` puede fragmentarlas.

## Cadencia de reparación eficiente

1. Congelar un lote coherente de findings ya triados.
2. Aislar cada cambio fiscal, de seguridad, migración, borrado, lote,
   idempotencia, reconciliación o multiemisor en su propio commit.
3. Agrupar cambios chicos únicamente cuando comparten causa, propiedad del código y
   validación.
4. Ejecutar tests enfocados y checks del área por cambio.
5. Ejecutar suites completas en checkpoints lógicos o antes de una candidata,
   no después de cada microfix.
6. Correr un `autoreview` por commit sensible o lote coherente ya probado.
7. Verificar manualmente sus findings y repetir tests/review si se cambia código.
8. Hacer push solo con autorización, verificar CI por SHA y revalidar Clawpatch
   después de varios cortes relacionados.

Modelo preferido para nuevas revisiones: `gpt-5.6-sol high`; alternativa
`gpt-5.5 high` si el modelo preferido no puede ejecutarse. El cierre histórico
de `v0.2.1` fue revisado con GPT-5.5 alto.

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
- No ejecutar `clawpatch fix` como parte automática de la puesta a punto o del
  review. Fuera de esa fase, solo usarlo bajo la política explícita anterior.
- No commitear `.clawpatch/`.

## Cierre Esperado

Al terminar, informar:

- comandos ejecutados;
- proveedor, modelo y razonamiento realmente utilizados;
- resultado de tests;
- cantidad de features detectadas por `repo`, `backend` y `frontend`;
- lotes ejecutados y features que hayan quedado pendientes;
- ubicación de reportes generados;
- triage resumido de findings aceptados, rechazados, inciertos y diferidos;
- aprendizajes operativos incorporados al runbook o pendientes de confirmar;
- confirmación de que no se ejecutó `clawpatch fix` durante la auditoría o,
  si el usuario autorizó un fix posterior, finding exacto, diff revisado y
  validaciones ejecutadas.
