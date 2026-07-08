# Services - Lógica de Negocio

Esta carpeta contiene la lógica de negocio de la aplicación.

## Estructura

Los servicios encapsulan la lógica compleja y son llamados desde los endpoints.

```
services/
├── almacenamiento_service.py            # Resumen, resguardo ZIP y limpieza segura de almacenamiento
├── certificados_service.py              # CSR, validación y operación con certificados
├── constancia_arca_service.py           # Extracción de datos fiscales desde constancia ARCA
├── constancia_puntos_venta_service.py   # Extracción de puntos de venta desde constancia ARCA
├── facturacion_service.py               # Orquestación de emisión de comprobantes
├── formatos_importacion_service.py      # Plantillas/formato, compatibilidad, descarga XLSX y mapeo de Excel externos
├── idempotencia_fiscal_service.py       # Idempotencia y deduplicación fiscal
├── lote_comprobantes_service.py         # Validación y procesamiento de lotes Excel
├── lote_worker.py                       # Worker reanudable para lotes grandes
├── perfiles_carga_masiva_service.py     # Perfiles de carga masiva por emisor
├── pdf_service.py                       # Generación de PDF (QR ARCA, templates)
└── reportes_service.py                  # Reportes (ventas, IVA, ranking, etc.)
```

## Principios

- **Separación de responsabilidades**: La lógica de negocio NO debe estar en los endpoints
- **Reutilización**: Los servicios pueden ser llamados desde múltiples endpoints o entre sí
- **Testeable**: Los servicios deben poder testearse independientemente
- **Transaccional**: Manejar transacciones de BD dentro de servicios

## Dónde entra cada servicio

- Validaciones y flujo ARCA: ver `backend/app/services/facturacion_service.py` y `backend/app/arca/`.
  `fecha_emision` es obligatoria y se valida contra la ventana ARCA antes de
  solicitar CAE; no usar fecha del día como default fiscal. `concepto` también
  es obligatorio; no asumir productos o servicios por default. Ese `concepto`
  es el tipo de concepto fiscal ARCA, no la descripción del ítem.
- Idempotencia fiscal: ver `idempotencia_fiscal_service.py`. Los caminos que
  solicitan CAE deben exigir `X-Idempotency-Key`, persistir una operación
  durable, crear intentos fiscales antes de ARCA y bloquear reintentos inciertos
  hasta consultar `FECompConsultar` o reconciliar. Los duplicados lógicos son
  advertencias con confirmación adicional, no bloqueos automáticos.
- Lotes masivos: ver `backend/app/services/lote_comprobantes_service.py` y
  `backend/app/services/lote_worker.py`. Los lotes requieren política explícita
  de concepto fiscal ARCA, descripción/concepto facturado del ítem, fecha de
  emisión y fechas de servicio antes de validar. El concepto fiscal puede ser
  `Productos`, `Servicios` o venir del archivo; la descripción del ítem puede
  venir del archivo o de un valor fijo para todo el lote.
- Plantillas/formato de importación: ver `formatos_importacion_service.py`.
  Administra plantillas globales y por emisor, protege plantillas internas del
  sistema, versiona ediciones, analiza Exceles de ejemplo, evalúa
  compatibilidad con perfil/emisor, genera `.xlsx` visuales y detecta
  encabezados. Los mapeos pueden venir por encabezado, columna, constante o
  dato del emisor. Una plantilla no debe ocultar defaults para concepto fiscal
  ARCA ni para descripción del ítem antes de la validación. En formatos de
  Responsable Inscripto, se puede mapear `item_precio_unitario` desde el neto
  gravado y `importe_total` aparte como referencia para consumidor final. Si un
  archivo externo informa total, `lote_comprobantes_service.py` compara ese
  valor contra el total calculado desde ítems e IVA y observa el grupo si no
  coincide.
- Perfiles de carga masiva: ver `perfiles_carga_masiva_service.py`. Administra
  configuraciones reutilizables por emisor activo para precargar la pantalla de
  lotes. El perfil puede recordar formato, concepto fiscal ARCA, descripción
  facturada, fecha de emisión explícita y reglas de período/vencimiento, pero no valida ni emite por sí mismo:
  la UI resuelve y muestra los valores antes de llamar a lotes.
- Almacenamiento: ver `almacenamiento_service.py`. Calcula uso de base, lotes,
  certificados, logs, temporales y caché con operaciones acotadas; prepara ZIPs
  de resguardo para lotes/logs/temporales seleccionados; compacta lotes cerrados
  o elimina archivos solo después de una descarga confirmada; y limpia
  certificados huérfanos únicamente cuando fueron gestionados por FactuFlow y no
  están referenciados por la base.
- Extractos bancarios: el formato global inicial interpreta `Fecha`,
  `Créditos`, `Leyendas Adicionales1`, `Leyendas Adicionales2` y `Pto Vta`.
  La descripción a facturar debe confirmarse aparte o venir mapeada desde el
  archivo; no se debe inferir de `Productos`/`Servicios`.
- Constancias ARCA: ver `constancia_arca_service.py` para emisores y
  `constancia_puntos_venta_service.py` para puntos de venta. El parser de
  emisores distingue constancia de inscripción de persona jurídica, inscripción
  de persona física y opción Monotributo; valida provincia contra el catálogo
  argentino antes de completar el campo.
- PDF/reportes: ver `docs/FASE_6_PDF_REPORTES.md`.
