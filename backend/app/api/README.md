# Endpoints de la API

Esta carpeta contiene todos los endpoints de la API REST de FactuFlow.

## Estructura

```
api/
├── __init__.py
├── deps.py              # Dependencias comunes (DB session, auth, etc.)
└── v1/
    ├── __init__.py
    ├── router.py        # Router principal que incluye todos los routers
    ├── clientes.py      # CRUD de clientes
    ├── empresas.py      # CRUD de empresas
    ├── comprobantes.py  # Emisión y consulta de comprobantes
    ├── certificados.py  # Gestión de certificados ARCA
    └── afip.py          # Integración directa con ARCA (WSAA, WSFEv1)
```

## Convenciones

- Todos los endpoints deben tener documentación (docstrings)
- Usar Pydantic schemas para request/response
- Validar permisos con dependencies
- Manejar errores con HTTPException
- Loggear operaciones importantes
