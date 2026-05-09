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

Nota 2026-05-07:

- `npm run test:unit` no tiene archivos de test unitarios y sale con codigo 0.
- `npm run test:e2e` no queda como evidencia vigente hasta corregir el setup de
  Playwright. En la ultima corrida el runner mostro pantalla en blanco aunque
  `http://localhost:8080/login` cargo correctamente con un script Playwright
  directo.
- `npm run lint:check` es el check no destructivo de ESLint.
- `npm run lint` ejecuta ESLint con `--fix`; usarlo solo cuando se quiere
  autocorregir y revisar el diff posterior.

## Arranque local

La forma mas simple de levantar el proyecto completo es:

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

Fecha: 2026-05-08

- Backend: `pytest tests -q` OK, 114 tests.
- Backend: `ruff check app tests` OK.
- Backend: `black --check app tests` OK.
- Backend: la prueba
  `tests/test_lotes_comprobantes.py::test_validar_lote_rechaza_fecha_emision_fuera_de_ventana_arca`
  cubre fechas de extracto como serial numerico de Excel.
- Backend: se agregaron pruebas para rechazar emisión individual sin `concepto`,
  aceptar `Producto`/`Servicio` desde archivo y rechazar `Definido por archivo`
  cuando el Excel no mapea columna de concepto.
- API local: `.tmp/ParaPruebas.xlsx` detectado como
  `Extracto bancario - creditos IVA exento`; al elegir servicios y
  `fecha_emision_modo=archivo` el lote `id=7` quedo con 20/20 grupos
  observados por fecha
  `06/04/2026` fuera de ventana ARCA. No se emitio ningun comprobante.
- Frontend: `npm run lint:check` OK sin errores, con 440 warnings de estilo Vue.
- Frontend: `npm run type-check` OK.
- Frontend: `npm run build` OK.
- Frontend: `npm run test:unit` OK, sin archivos de test unitarios.
- Browser: carga basica de `http://localhost:8080/comprobantes/lotes` OK; falta
  QA visual subiendo un Excel para revisar los selectores de concepto y fechas
  fiscales.

## Smoke real ARCA

El smoke real completado el 2026-03-09 quedo documentado en:

- `docs/project/notes/SESSION_2026-03-09.md`

Ese documento incluye:
- problemas encontrados
- como se resolvieron
- CAEs emitidos
- pendientes operativos
