# Guía de testing

## Backend
```bash
cd backend
pytest
pytest tests/ -v
```

## Frontend
```bash
cd frontend
npm run test
npm run test:unit
npm run test:e2e
```

## Notas
- La configuración de pytest está en `backend/pytest.ini`.
- Los tests de ARCA viven en `backend/tests/test_arca/`.
