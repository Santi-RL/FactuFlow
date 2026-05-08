# Services - Lógica de Negocio

Esta carpeta contiene la lógica de negocio de la aplicación.

## Estructura

Los servicios encapsulan la lógica compleja y son llamados desde los endpoints.

```
services/
├── certificados_service.py              # CSR, validacion y operacion con certificados
├── constancia_arca_service.py           # Extraccion de datos fiscales desde constancia ARCA
├── constancia_puntos_venta_service.py   # Extraccion de puntos de venta desde constancia ARCA
├── facturacion_service.py               # Orquestacion de emision de comprobantes
├── formatos_importacion_service.py      # Formatos, autodeteccion y mapeo de Excel externos
├── lote_comprobantes_service.py         # Validacion y procesamiento de lotes Excel
├── lote_worker.py                       # Worker reanudable para lotes grandes
├── pdf_service.py                       # Generacion de PDF (QR ARCA, templates)
└── reportes_service.py                  # Reportes (ventas, IVA, ranking, etc.)
```

## Principios

- **Separación de responsabilidades**: La lógica de negocio NO debe estar en los endpoints
- **Reutilización**: Los servicios pueden ser llamados desde múltiples endpoints o entre sí
- **Testeable**: Los servicios deben poder testearse independientemente
- **Transaccional**: Manejar transacciones de BD dentro de servicios

## Donde entra cada servicio

- Validaciones y flujo ARCA: ver `backend/app/services/facturacion_service.py` y `backend/app/arca/`.
- Lotes masivos: ver `backend/app/services/lote_comprobantes_service.py` y
  `backend/app/services/lote_worker.py`.
- Formatos de importacion: ver `formatos_importacion_service.py`. Administra
  formatos globales y por emisor, detecta encabezados, resuelve mapeos por
  encabezado/columna/constante y normaliza archivos externos al contrato interno
  de lotes.
- Extractos bancarios: el formato global inicial interpreta `Fecha`,
  `Créditos`, `Leyendas Adicionales1`, `Leyendas Adicionales2` y `Pto Vta`.
- Constancias ARCA: ver `constancia_arca_service.py` para emisores y
  `constancia_puntos_venta_service.py` para puntos de venta.
- PDF/reportes: ver `docs/FASE_6_PDF_REPORTES.md`.
