# Tests del Backend

Esta carpeta contiene todos los tests del backend.

## Estructura

```
tests/
├── conftest.py              # Fixtures compartidas (DB, cliente de tests)
├── test_auth.py             # Auth (setup/login/me)
├── test_clientes.py         # Clientes
├── test_certificados.py     # Certificados
├── test_health.py           # Health checks
├── test_pdf_service.py      # PDF service (generacion, QR, etc.)
├── test_reportes_service.py # Reportes service
└── test_arca/               # Tests de integracion ARCA (con mocks)
```

## Ejecutar Tests

```bash
# Todos los tests
pytest tests/ -v

# Con coverage
pytest tests/ -v --cov=app --cov-report=html

# Tests específicos
pytest tests/test_clientes.py -v

# Un test específico
pytest tests/test_clientes.py::test_crear_cliente -v
```

## Fixtures Principales

Definidas en `conftest.py`:
- `db` - Sesión de base de datos de test (SQLite en memoria)
- `client` - TestClient de FastAPI
- `mock_wsaa` - Mock de cliente WSAA
- `mock_wsfe` - Mock de cliente WSFEv1

## Convenciones

- Nombres de tests descriptivos: `test_crear_cliente_con_datos_validos`
- Un archivo de test por módulo
- Coverage mínimo del 80%
- Mockear llamadas a ARCA (no llamar a servicios reales en CI)
- Tests de integración en carpeta separada (opcional)
