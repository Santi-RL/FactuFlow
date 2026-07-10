# Guía de testing

## Raíz

```bash
npm run lint
npm run test
npm run backend:format:check
```

Los scripts raíz `lint` y `test` agregan backend y frontend. El check de
formato backend queda explícito como `backend:format:check`. El comando
frontend `npm run format` escribe cambios y no se usa como verificación global
raíz mientras exista deuda histórica de Prettier en archivos no tocados.

## Backend

```bash
cd backend
python -m pip install -r requirements.txt -r requirements-dev.txt
pytest tests/ -q
ruff check app/ tests/
black --check app/ tests/
```

Los archivos Python deben mantenerse con saltos de línea LF. El repo fija esta
política en `.gitattributes` para `*.py` y `*.pyi`, evitando que `core.autocrlf`
de Windows deje el working tree en CRLF o mixto. Para verificarlo:

```bash
git ls-files --eol '*.py' '*.pyi'
```

Si `black --check app tests` se cuelga localmente sin reportar errores, revisar
primero el cache local de Black. En Windows se confirmó que limpiar
`%LOCALAPPDATA%\black\black\Cache\23.12.1` resuelve el cuelgue; luego Black
regenera el cache y debe terminar normalmente.

## Frontend

```bash
cd frontend
npm install
npm run lint:check
npm run type-check
npm run build
npm run test:unit
npm run test:e2e
```

## Pruebas de fechas

FactuFlow es una aplicación argentina. Todo cambio que formatee, parsee,
importe, exporte, valide o muestre fechas debe cubrir explícitamente el formato
argentino `DD/MM/AAAA` además de los formatos técnicos que use el contrato
interno (`YYYY-MM-DD`, ISO datetime o `CbteFch` `YYYYMMDD`).

Cobertura mínima esperada cuando se toca lógica de fechas:

- `DD/MM/AAAA` válido, por ejemplo `31/12/2026`.
- `YYYY-MM-DD` válido recibido desde API/backend, por ejemplo `2026-12-31`.
- ISO datetime con zona horaria si el código lo acepta, verificando que no haya
  desplazamiento de día por timezone.
- Fechas con forma válida pero calendario inválido, por ejemplo `31/02/2026` o
  `2026-02-31`, sin normalizarlas silenciosamente.
- String vacío o valor faltante.
- Para flujos fiscales, confirmación irreversible visible en `DD/MM/AAAA` y
  conversión técnica correcta antes de ARCA.

No usar `new Date(string)` ni `Date.parse` como parser general de strings de
usuario. Validar por formato soportado y por calendario real.

## Puesta a punto Clawpatch

Para ejecutar `clawpatch`, usar los scripts raíz documentados en
`docs/project/audits/clawpatch/README.md`. El smoke mínimo es:

```bash
npm run clawpatch:test-seeds
npm run clawpatch:map-all
npm run clawpatch:repo:status
npm run clawpatch:backend:status
npm run clawpatch:frontend:status
```

No ejecutar comandos directos de slice sin `--root`. `--state-dir` define dónde
se guarda el estado, no qué árbol de archivos se audita. Para backend, usar
`npm run clawpatch:backend:*` o el equivalente directo con
`--root backend --state-dir ../.clawpatch/backend --config
../.clawpatch/backend/config.json`.

`clawpatch:map-all` ejecuta el mapper nativo de cada slice y luego agrega
features manuales versionadas para que la auditoría revise flujos reales de
FactuFlow. El nivel `repo` cubre slices end-to-end frontend/backend;
`backend` y `frontend` agregan slices focalizados por área.

La regresión mínima posterior es:

```bash
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

La puesta a punto no debe ejecutar `clawpatch fix`, no debe solicitar CAE ni
modificar lógica de emisión fiscal.

Nota 2026-07-05:

- Usar siempre la CLI global `clawpatch` sin fijar versión. En FactuFlow no se
  deben escribir scripts que llamen `clawpatch@<version>`.
- Si `clawpatch revalidate --finding <id> --include-dirty` no selecciona un
  finding que `show` todavía lista, revisar si es un duplicado de otro nivel de
  feature. Se puede usar una revalidación acotada por abiertos y hacer triage
  manual solo si el duplicado exacto ya fue revalidado como fixed, dejando nota.
- Después de aceptar un finding de `autoreview` y cambiar código, repetir los
  tests enfocados y volver a correr `autoreview` sobre el commit final.
- Para verificar CI remoto, usar `gh run list` y `gh run view` sobre el SHA del
  commit esperado; no usar el endpoint legacy de commit statuses.

Nota 2026-06-10:

- `npm run test:unit` incluye pruebas unitarias de perfiles de carga masiva y
  fechas relativas.
- `npm run test:e2e` es evidencia vigente para Chromium desktop local. El script
  levanta Vite en `127.0.0.1:18080`, ejecuta Playwright y corta el servidor al
  finalizar para evitar procesos colgados en Windows. Si el puerto está ocupado,
  detener el proceso existente o usar `E2E_PORT`.
- La matriz completa de navegadores/mobile queda opt-in con la variable
  `E2E_FULL_BROWSER_MATRIX=1`; no es el recorrido por defecto porque los flujos
  administrativos de plantillas y emisión masiva están pensados para PC. En
  PowerShell usar `$env:E2E_FULL_BROWSER_MATRIX='1'; npm run test:e2e`; en bash
  usar `E2E_FULL_BROWSER_MATRIX=1 npm run test:e2e`.
- `npm run lint` y `npm run lint:check` son checks no destructivos de ESLint.
- En Windows, ejecutar `npm run lint:check` separado de `npm run build` o de
  procesos Vite activos. Si se corre en paralelo, ESLint puede intentar leer un
  archivo temporal `vite.config.ts.timestamp-*.mjs` que Vite ya eliminó y dar un
  falso `ENOENT`.
- `npm run lint:fix` ejecuta ESLint con `--fix`; usarlo solo cuando se quiere
  autocorregir y revisar el diff posterior.

## Arranque local

La forma recomendada para QA manual local en Windows es:

```bash
.\FactuFlow Local.vbs
```

El launcher muestra estado en el tray sin dejar una ventana de PowerShell
abierta y deja logs en `.tmp/local-launcher/`.

El camino técnico alternativo es:

```bash
powershell -ExecutionPolicy Bypass -File .\run-local.ps1
```

Servicios esperados:
- Frontend: `http://localhost:8080`
- Backend: `http://localhost:8000`

`run-local.ps1` ejecuta `alembic upgrade head` antes de iniciar el backend. En
entornos normales no se crean tablas con `Base.metadata.create_all`; esa ruta
queda limitada a tests.

## Checklist antes de cerrar una tarea importante

- Si se toco backend: `pytest`
- Si se toco frontend: `npm run type-check`
- Si se tocaron perfiles de carga masiva: ejecutar
  `pytest tests/test_perfiles_carga_masiva.py` y
  `npm run test:unit -- perfiles-carga-masiva`
- Si se toco un flujo visible: smoke manual o Playwright
- Si se tocaron flujos core o UX: actualizar `docs/user-guide/README.md`
- Siempre actualizar:
  - `ROADMAP.md`
  - `docs/agents/current-status.md`
  - `docs/agents/manual-qa.md`

## QA manual actual

El último checkpoint manual no está en este archivo sino en:

- `docs/agents/manual-qa.md`

Eso evita mezclar instrucciones permanentes con el estado puntual de una sesión.

## Última verificación técnica

Fecha: 2026-07-10

- Release `v0.2.1` / `8099b22`: backend 411 tests aprobados y 1 omitido.
- Frontend: 111 tests aprobados; lint, type-check y build limpios.
- Scripts raíz: 3 tests aprobados.
- GitHub Actions: Security Audit, Frontend Build, Backend Tests y E2E Tests
  aprobados para el tag y para el cierre documental `ece2bdf`.
- Clawpatch objetivo: 3 findings backend y 9 frontend revalidados como `fixed`.
- Estado local acumulativo: repo 0 abiertos, backend 85 y frontend 6. Los state
  dirs conservan históricos y duplicados; no interpretar esos contadores como
  bugs aceptados.
- QA manual productiva: login y emisión fiscal real satisfactoria.
- Cierre: `docs/project/audits/clawpatch/2026-07-10-cierre-ciclo-v0.2.1.md`.

Fecha histórica: 2026-07-05

- Clawpatch repo completo: `openFindings=0`, `features=27`, `findings=50`.
- Clawpatch backend: `openFindings=0`, `features=124`, `findings=19`.
- Clawpatch frontend: `openFindings=0`, `features=21`, `findings=18`.
- Frontend: `npm run lint:check` OK.
- Frontend: `npm run type-check` OK.
- Frontend: `npm run test:unit` OK, 83 tests.
- Frontend enfocado: `npm run test:unit -- useFormatters.spec.ts` OK, 6 tests.
- Frontend enfocado: `npm run test:unit -- pdf.service.spec.ts` OK, 2 tests.
- Clawpatch revalidate OK para los hallazgos de PDF preview, workflow E2E y
  `formatearFecha`.
- `autoreview` Codex/GPT-5.5 alto OK sobre los commits finales del ciclo.
- GitHub Actions CI remoto OK para `ebc176d`: `Frontend Build`, `Backend Tests`,
  `Security Audit` y `E2E Tests` en success.
- Cierre detallado: `docs/project/audits/clawpatch/2026-07-05-cierre-auditoria.md`.

Fecha: 2026-06-13

- Frontend E2E: `npm run test:e2e -- --reporter=list` OK, 31 tests en Chromium
  desktop.
- Frontend completo: `npm run test:unit` OK, 61 tests.
- Frontend: `npm run build` OK.
- Frontend: `npm run type-check` OK.
- Frontend: `npm run lint:check` OK.

Fecha: 2026-05-22

- Backend completo: `pytest tests -q` OK, 195 tests.
- Backend: `ruff check app tests` OK.
- Backend: `black --check app tests` OK.
- Launcher local: `scripts\factuflow-local-tray.ps1 -SelfTest` OK.
- Frontend completo: `npm run test:unit` OK, 47 tests.
- Frontend: `npm run type-check` OK.
- Frontend: `npm run build` OK.
- Frontend: `npm run lint:check` OK sin errores ni warnings.
- Clawpatch: backend, frontend y repo quedan con `openFindings=0`; la revision
  repo final no encontro features pendientes ni hallazgos nuevos.

Fecha: 2026-05-10

- Backend focalizado: `python -m pytest tests/test_lotes_comprobantes.py -q`
  OK, 30 tests. Cubre progreso real con emisión mockeada, sin solicitar CAE
  real, confirmación fiscal obligatoria y concurrencia de procesamiento.
- Backend: `ruff check app/api/lotes_comprobantes.py app/services/lote_comprobantes_service.py tests/test_lotes_comprobantes.py`
  OK.
- Backend: `black --check app/api/lotes_comprobantes.py app/services/lote_comprobantes_service.py tests/test_lotes_comprobantes.py`
  OK.
- Frontend focalizado: `npm run test:unit -- lote-progress` OK. Cubre calculo
  de porcentaje, tiempo transcurrido, estimacion restante y lotes en cola.
- Frontend: `npm run type-check` OK.
- Frontend: `npm run lint:check -- --quiet` OK.
- Frontend: `npm run build` OK.

Fecha: 2026-05-09

- Backend: `ARCA_ENV=homologacion pytest tests -q` OK, 141 tests.
- Backend: `ruff check app tests` OK.
- Backend: `black --check app tests` OK.
- Backend: la prueba
  `tests/test_lotes_comprobantes.py::test_validar_lote_rechaza_fecha_emision_fuera_de_ventana_arca`
  cubre fechas de extracto como serial numerico de Excel.
- Backend: se agregaron pruebas para rechazar emisión individual sin `concepto`,
  aceptar `Producto`/`Servicio` desde archivo y rechazar `Definido por archivo`
  cuando el Excel no mapea columna de concepto.
- Backend: `tests/test_perfiles_carga_masiva.py` cubre CRUD scopiado por
  emisor, predeterminado único, nombres por emisor, formatos accesibles,
  rechazo de `fecha_actual` como fecha fiscal y reglas incompletas.
- Frontend: `src/utils/perfiles-carga-masiva.spec.ts` cubre reglas relativas de
  fechas y selección automática de perfil de carga masiva.
- Frontend: `npm run test:unit` OK.
- Frontend: `npm run build` OK.
- Frontend: `npm run type-check` OK.
- Frontend: `npm run lint:check` OK sin errores; mantiene warnings de estilo
  Vue existentes.
- Browser: QA visual de perfiles de carga masiva en `http://127.0.0.1:8080`
  OK. Se verificó crear, editar, eliminar, predeterminar, autoaplicar, modificar
  antes de validar, validar Excel y abrir/cancelar el modal final de fecha
  fiscal sin emitir.
- API local: Excel privado local detectado como
  `Extracto bancario - creditos IVA exento`; al elegir servicios y
  `fecha_emision_modo=archivo` el lote `id=7` quedó con 20/20 grupos
  observados por fecha
  `06/04/2026` fuera de ventana ARCA. No se emitió ningún comprobante.

## Smoke real ARCA

El smoke real completado el 2026-03-09 quedó documentado en:

- `docs/project/notes/SESSION_2026-03-09.md`

Ese documento incluye:
- problemas encontrados
- como se resolvieron
- referencias privadas a CAEs emitidos; no copiarlas a documentación nueva
- pendientes operativos
