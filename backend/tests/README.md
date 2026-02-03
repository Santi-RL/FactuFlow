# Tests del Backend

Esta carpeta contiene todos los tests del backend.

## Estructura

```
tests/
├── conftest.py              # Fixtures compartidas (DB, cliente de tests)
├── test_clientes.py         # Tests de endpoints y servicios de clientes
├── test_empresas.py         # Tests de empresas
├── test_comprobantes.py     # Tests de comprobantes
├── test_certificados.py     # Tests de certificados
└── test_afip/
    ├── test_wsaa.py         # Tests de WSAA (con mocks)
    └── test_wsfe.py         # Tests de WSFEv1 (con mocks)
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
- Mockear llamadas a AFIP (no llamar a servicios reales en CI)
- Tests de integración en carpeta separada (opcional)
