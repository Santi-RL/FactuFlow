# Guia de testing

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

Para ejecutar `clawpatch`, usar los scripts raiz documentados en
`docs/project/audits/clawpatch/README.md`. El smoke minimo es:

```bash
npm run clawpatch:test-seeds
npm run clawpatch:map-all
npm run clawpatch:repo:status
npm run clawpatch:backend:status
npm run clawpatch:frontend:status
```

`clawpatch:map-all` ejecuta el mapper nativo de cada slice y luego agrega
features manuales versionadas para que la auditoría revise flujos reales de
FactuFlow. El nivel `repo` cubre slices end-to-end frontend/backend;
`backend` y `frontend` agregan slices focalizados por área.

La regresion minima posterior es:

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

El camino tecnico alternativo es:

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

El ultimo checkpoint manual no esta en este archivo sino en:

- `docs/agents/manual-qa.md`

Eso evita mezclar instrucciones permanentes con el estado puntual de una sesion.

## Ultima verificacion tecnica

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
  OK, 30 tests. Cubre progreso real con emision mockeada, sin solicitar CAE
  real, confirmacion fiscal obligatoria y concurrencia de procesamiento.
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
  emisor, predeterminado unico, nombres por emisor, formatos accesibles,
  rechazo de `fecha_actual` como fecha fiscal y reglas incompletas.
- Frontend: `src/utils/perfiles-carga-masiva.spec.ts` cubre reglas relativas de
  fechas y seleccion automatica de perfil de carga masiva.
- Frontend: `npm run test:unit` OK.
- Frontend: `npm run build` OK.
- Frontend: `npm run type-check` OK.
- Frontend: `npm run lint:check` OK sin errores; mantiene warnings de estilo
  Vue existentes.
- Browser: QA visual de perfiles de carga masiva en `http://127.0.0.1:8080`
  OK. Se verifico crear, editar, eliminar, predeterminar, autoaplicar, modificar
  antes de validar, validar Excel y abrir/cancelar el modal final de fecha
  fiscal sin emitir.
- API local: Excel privado local detectado como
  `Extracto bancario - creditos IVA exento`; al elegir servicios y
  `fecha_emision_modo=archivo` el lote `id=7` quedo con 20/20 grupos
  observados por fecha
  `06/04/2026` fuera de ventana ARCA. No se emitio ningun comprobante.

## Smoke real ARCA

El smoke real completado el 2026-03-09 quedo documentado en:

- `docs/project/notes/SESSION_2026-03-09.md`

Ese documento incluye:
- problemas encontrados
- como se resolvieron
- referencias privadas a CAEs emitidos; no copiarlas a documentacion nueva
- pendientes operativos
