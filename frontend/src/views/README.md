# Views (Paginas)

Esta carpeta contiene las vistas/paginas de la app (rutas).

## Estructura actual

```
views/
├── auth/            # Login y setup inicial
├── dashboard/       # Dashboard
├── empresa/         # Configuracion de empresa
├── puntos_venta/    # Puntos de venta
├── clientes/        # CRUD clientes
├── comprobantes/    # Emision, consulta y lotes de comprobantes
├── certificados/    # Listado + wizard de certificados
└── reportes/        # Reportes
```

Las rutas se definen en `frontend/src/router/index.ts`.

## Vistas relevantes

- `comprobantes/LotesComprobantesView.vue`: emision masiva. Descarga plantilla,
  sube Excel, consulta formatos de importacion, detecta encabezados, permite
  confirmar el formato, exige seleccionar concepto fiscal ARCA
  (`Productos`/`Servicios`/archivo), descripcion/concepto facturado del item
  (archivo o valor fijo), fecha de emision y fechas de servicio, valida el lote
  y emite solo despues de la confirmacion del usuario. Antes de llamar a
  procesar, debe mostrar el modal `Confirmar fecha fiscal` con el mensaje:
  `Está seguro que quiere emitir comprobantes con fecha XX/XX/XX? Recuerde que luego no podrá emitir comprobantes con fecha anterior para ese mismo punto de venta.`
- `comprobantes/ComprobanteNuevoView.vue`: emision individual. La fecha de
  emision debe completarse explicitamente; no se usa la fecha del dia como
  default fiscal. Antes de emitir debe mostrar el mismo modal de confirmacion de
  fecha fiscal. Los items deben tener `descripcion` propia; esa descripcion no
  se reemplaza por el concepto fiscal ARCA.
