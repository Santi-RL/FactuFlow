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

## Smoke real ARCA

El smoke real completado el 2026-03-09 quedo documentado en:

- `docs/project/notes/SESSION_2026-03-09.md`

Ese documento incluye:
- problemas encontrados
- como se resolvieron
- CAEs emitidos
- pendientes operativos
