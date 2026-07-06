# Views (Páginas)

Esta carpeta contiene las vistas/páginas de la app (rutas).

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
├── reportes/        # Reportes
├── usuarios/        # Administración de usuarios
└── sistema/         # Diagnóstico y almacenamiento administrativo
```

Las rutas se definen en `frontend/src/router/index.ts`.

## Vistas relevantes

- `comprobantes/LotesComprobantesView.vue`: emisión masiva. Descarga plantilla,
  sube Excel, consulta perfiles de carga masiva y formatos de importación,
  detecta encabezados, permite confirmar el formato, exige seleccionar concepto fiscal ARCA
  (`Productos`/`Servicios`/archivo), descripción/concepto facturado del ítem
  (archivo o valor fijo), fecha de emisión y fechas de servicio, valida el lote
  y emite solo después de la confirmación del usuario. Antes de llamar a
  procesar, debe mostrar el modal `Confirmar fecha fiscal` con el mensaje:
  `Está seguro que quiere emitir comprobantes con fecha XX/XX/XX? Recuerde que luego no podrá emitir comprobantes con fecha anterior para ese mismo punto de venta.`
- `comprobantes/ComprobanteNuevoView.vue`: emisión individual. La fecha de
  emisión debe completarse explícitamente; no se usa la fecha del día como
  default fiscal. Antes de emitir debe mostrar el mismo modal de confirmación de
  fecha fiscal. Los ítems deben tener `descripcion` propia; esa descripción no
  se reemplaza por el concepto fiscal ARCA.
- `empresa/EmpresaConfigView.vue`: configuración del emisor activo. La pestaña
  `Datos del emisor` edita datos fiscales y la pestaña `Carga masiva` administra
  perfiles y plantillas. Los perfiles solo precargan la pantalla de lotes; las
  plantillas generan/interpretan Exceles y muestran compatibilidad, pero no
  validan ni emiten automaticamente.
- `usuarios/UsuariosView.vue`: administración de usuarios. Solo se muestra a
  administradores; permite crear, editar, desactivar/reactivar y resetear
  contraseñas. Los usuarios comunes operan emisores, pero no acceden a esta
  vista.
- `sistema/SistemaView.vue`: sección administrativa reservada a
  administradores. La pestaña `Almacenamiento` muestra uso total, límite
  configurado, espacio libre real, categorías, desglose por emisor, lotes
  compactables, logs antiguos, temporales y certificados huérfanos gestionados.
  Para liberar lotes/logs/temporales primero prepara un ZIP de resguardo,
  descarga el archivo a la PC del usuario y recién después permite confirmar
  `Ya lo descargué`.
