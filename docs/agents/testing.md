# Guía de testing

## Backend
```bash
cd backend
# Igual que CI (ver .github/workflows/ci.yml)
python -m pip install -r requirements.txt -r requirements-dev.txt
black --check app/ tests/
pytest tests/ -v --cov=app --cov-report=xml
```

## Frontend
```bash
cd frontend
# Igual que CI (ver .github/workflows/ci.yml)
npm ci
npm run type-check
npm run lint
npm run build
npm run test:unit
```

## Checklist Antes De Push (Mantener "Todo Verde")
- No dejar warnings en CI. Si aparece una annotation nueva (lint/type-check), se corrige o se justifica y se configura explícitamente la regla.
- Frontend (cuando tocamos UI o flujos core): `npm run type-check`, `npm run lint`, `npm run build`, `npx playwright test --project=chromium` (smoke E2E con mocks)
- Backend (cuando tocamos API/modelos/servicios): `pytest`, `ruff check app/ tests/` y/o `black --check app/ tests/` según lo que esté habilitado en el repo/CI

## Notas
- La configuración de pytest está en `backend/pytest.ini`.
- Los tests de ARCA viven en `backend/tests/test_arca/`.
