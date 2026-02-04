# Guía para Agentes de IA - FactuFlow

## Alcance
- Este archivo define cómo trabajar en el repo.
- La documentación operativa extendida está en `docs/agents/README.md`.

## Nombres: ARCA vs AFIP
- Usar ARCA en textos, UI y documentación nueva.
- AFIP queda solo como nomenclatura legacy en URLs y variables de entorno existentes.
- Si agregás nuevos nombres públicos, preferí `ARCA_*` y mantené compatibilidad cuando sea necesario.

## Mapa rápido
- `backend/app/main.py`: entrada FastAPI y registro de routers.
- `backend/app/api/*.py`: endpoints (health, auth, empresas, clientes, puntos_venta, certificados, arca, comprobantes, pdf, reportes).
- `backend/app/arca/`: integración ARCA (wsaa, wsfev1, crypto, config, cache, utils).
- `backend/app/core/config.py`: settings y variables de entorno.
- `backend/app/models/`, `backend/app/schemas/`, `backend/app/services/`.
- `backend/tests/`: tests (incluye `test_arca/`).
- `frontend/src/main.ts`, `frontend/src/router/index.ts`.
- `frontend/src/views/`: vistas por dominio.
- `frontend/src/components/ui/`: componentes base `Base*.vue`.
- `docs/`: documentación del proyecto.

## Convenciones
- Python: PEP8, `black` (88), type hints obligatorios, docstrings en español.
- FastAPI: imports absolutos desde `app/`.
- Vue: Composition API con `<script setup>`, TypeScript recomendado, componentes en PascalCase, events en kebab-case.
- Tailwind: priorizar utilidades sobre CSS custom.
- UI y mensajes para usuarios en español (Argentina).

## Comandos
### Backend
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
pytest
ruff check app/ tests/
black app/ tests/
mypy app/
```

### Frontend
```bash
cd frontend
npm install
npm run dev
npm run test
npm run test:unit
npm run test:e2e
npm run lint
npm run format
npm run type-check
```

## Seguridad y certificados
- No commitear certificados ni claves privadas.
- Usar `certs/` y `data/` (gitignored).
- Ver detalles en `docs/agents/security.md`.

## Documentación operativa
- Índice: `docs/agents/README.md`
- Resumen y arquitectura: `docs/agents/overview.md`
- ARCA y endpoints: `docs/agents/arca.md`
- Testing: `docs/agents/testing.md`
- Seguridad: `docs/agents/security.md`
- Contribución y commits: `CONTRIBUTING.md`
