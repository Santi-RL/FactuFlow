# Services - Lógica de Negocio

Esta carpeta contiene la lógica de negocio de la aplicación.

## Estructura

Los servicios encapsulan la lógica compleja y son llamados desde los endpoints.

```
services/
├── almacenamiento_service.py            # Resumen, resguardo ZIP y limpieza segura de almacenamiento
├── certificados_service.py              # CSR, validacion y operacion con certificados
├── constancia_arca_service.py           # Extraccion de datos fiscales desde constancia ARCA
├── constancia_puntos_venta_service.py   # Extraccion de puntos de venta desde constancia ARCA
├── facturacion_service.py               # Orquestacion de emision de comprobantes
├── formatos_importacion_service.py      # Formatos, autodeteccion y mapeo de Excel externos
├── lote_comprobantes_service.py         # Validacion y procesamiento de lotes Excel
├── lote_worker.py                       # Worker reanudable para lotes grandes
├── perfiles_carga_masiva_service.py     # Perfiles de carga masiva por emisor
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
  `fecha_emision` es obligatoria y se valida contra la ventana ARCA antes de
  solicitar CAE; no usar fecha del dia como default fiscal. `concepto` tambien
  es obligatorio; no asumir productos o servicios por default. Ese `concepto`
  es el tipo de concepto fiscal ARCA, no la descripcion del item.
- Lotes masivos: ver `backend/app/services/lote_comprobantes_service.py` y
  `backend/app/services/lote_worker.py`. Los lotes requieren politica explicita
  de concepto fiscal ARCA, descripcion/concepto facturado del item, fecha de
  emision y fechas de servicio antes de validar. El concepto fiscal puede ser
  `Productos`, `Servicios` o venir del archivo; la descripcion del item puede
  venir del archivo o de un valor fijo para todo el lote.
- Formatos de importacion: ver `formatos_importacion_service.py`. Administra
  formatos globales y por emisor, detecta encabezados, resuelve mapeos por
  encabezado/columna/constante y normaliza archivos externos al contrato interno
  de lotes. Un formato no debe ocultar defaults para concepto fiscal ARCA ni
  para descripcion del item antes de la validacion. En formatos de Responsable
  Inscripto, se puede mapear `item_precio_unitario` desde el neto gravado y
  `importe_total` aparte como referencia para consumidor final. Si un archivo
  externo informa total, `lote_comprobantes_service.py` compara ese valor contra
  el total calculado desde items e IVA y observa el grupo si no coincide.
- Perfiles de carga masiva: ver `perfiles_carga_masiva_service.py`. Administra
  configuraciones reutilizables por emisor activo para precargar la pantalla de
  lotes. El perfil puede recordar formato, concepto fiscal ARCA, descripcion
  facturada y reglas relativas de fechas, pero no valida ni emite por si mismo:
  la UI resuelve y muestra los valores antes de llamar a lotes.
- Almacenamiento: ver `almacenamiento_service.py`. Calcula uso de base, lotes,
  certificados, logs, temporales y caché con operaciones acotadas; prepara ZIPs
  de resguardo para lotes/logs/temporales seleccionados; compacta lotes cerrados
  o elimina archivos solo después de una descarga confirmada; y limpia
  certificados huérfanos únicamente cuando fueron gestionados por FactuFlow y no
  están referenciados por la base.
- Extractos bancarios: el formato global inicial interpreta `Fecha`,
  `Créditos`, `Leyendas Adicionales1`, `Leyendas Adicionales2` y `Pto Vta`.
  La descripcion a facturar debe confirmarse aparte o venir mapeada desde el
  archivo; no se debe inferir de `Productos`/`Servicios`.
- Constancias ARCA: ver `constancia_arca_service.py` para emisores y
  `constancia_puntos_venta_service.py` para puntos de venta. El parser de
  emisores distingue constancia de inscripcion de persona juridica, inscripcion
  de persona fisica y opcion Monotributo; valida provincia contra el catalogo
  argentino antes de completar el campo.
- PDF/reportes: ver `docs/FASE_6_PDF_REPORTES.md`.
