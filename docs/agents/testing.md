# Guia de testing

## Backend

```bash
cd backend
python -m pip install -r requirements.txt -r requirements-dev.txt
pytest tests/ -q
ruff check app/ tests/
black --check app/ tests/
```

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

`clawpatch:map-all` agrega features manuales versionadas para que la auditoria
revise flujos reales de FactuFlow. El nivel `repo` cubre slices end-to-end
frontend/backend; `backend` y `frontend` agregan slices focalizados por area.

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

Nota 2026-05-07:

- `npm run test:unit` incluye pruebas unitarias de perfiles de carga masiva y
  fechas relativas.
- `npm run test:e2e` no queda como evidencia vigente hasta corregir el setup de
  Playwright. En la ultima corrida el runner mostro pantalla en blanco aunque
  `http://localhost:8080/login` cargo correctamente con un script Playwright
  directo.
- `npm run lint:check` es el check no destructivo de ESLint.
- `npm run lint` ejecuta ESLint con `--fix`; usarlo solo cuando se quiere
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

Fecha: 2026-05-17

- Backend completo: `pytest tests -q` OK, 194 tests.
- Backend: `ruff check app tests` OK.
- Backend: `black --check app tests` OK.
- Backend: `alembic heads` OK, head `a3b4c5d6e7f8`.
- Frontend completo: `npm run test:unit` OK, 44 tests.
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
- CAEs emitidos
- pendientes operativos
