# Services - Lógica de Negocio

Esta carpeta contiene la lógica de negocio de la aplicación.

## Estructura

Los servicios encapsulan la lógica compleja y son llamados desde los endpoints.

```
services/
├── certificados_service.py  # CSR, validacion y operacion con certificados
├── facturacion_service.py   # Orquestacion de emision de comprobantes
├── pdf_service.py           # Generacion de PDF (QR ARCA, templates)
└── reportes_service.py      # Reportes (ventas, IVA, ranking, etc.)
```

## Principios

- **Separación de responsabilidades**: La lógica de negocio NO debe estar en los endpoints
- **Reutilización**: Los servicios pueden ser llamados desde múltiples endpoints o entre sí
- **Testeable**: Los servicios deben poder testearse independientemente
- **Transaccional**: Manejar transacciones de BD dentro de servicios

## Donde entra cada servicio

- Validaciones y flujo ARCA: ver `backend/app/services/facturacion_service.py` y `backend/app/arca/`.
- PDF/reportes: ver `docs/FASE_6_PDF_REPORTES.md`.
