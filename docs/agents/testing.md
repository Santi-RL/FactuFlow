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

## Notas
- La configuración de pytest está en `backend/pytest.ini`.
- Los tests de ARCA viven en `backend/tests/test_arca/`.
