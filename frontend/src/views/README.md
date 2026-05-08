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
  confirmar el formato, valida el lote y emite solo despues de la confirmacion
  del usuario.
