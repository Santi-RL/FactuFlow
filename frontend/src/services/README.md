# Services (API client)

Servicios para hablar con el backend (HTTP).

## Estructura actual

```
services/
├── api.ts                    # Axios configurado (baseURL, interceptors, etc.)
├── auth.service.ts           # Auth (setup/login/me)
├── empresa.service.ts        # Empresa
├── clientes.service.ts       # Clientes
├── puntos_venta.service.ts   # Puntos de venta
├── certificados.service.ts   # Certificados
├── arca.service.ts           # ARCA (tipos, puntos de venta, dummy, etc.)
├── comprobantes.service.ts   # Comprobantes
├── formatos-importacion.service.ts # Formatos configurables de importacion
├── lotes-comprobantes.service.ts # Emision masiva por Excel
├── perfiles-carga-masiva.service.ts # Perfiles de carga masiva por emisor
├── pdf.service.ts            # PDFs
└── reportes.service.ts       # Reportes
```

## Convenciones

- Endpoints del backend usan prefijo `/api/...` (ver `backend/app/main.py`).
- Evitar duplicar logica de negocio: el frontend arma requests, el backend valida.
- Los tipos de lotes viven en `frontend/src/types/lote-comprobante.ts`.
- Los tipos de formatos viven en `frontend/src/types/formato-importacion.ts`.
- Los tipos de perfiles de carga masiva viven en
  `frontend/src/types/perfil-carga-masiva.ts`.
- `formatos-importacion.service.ts` lista formatos disponibles y detecta
  candidatos desde un Excel antes de validar el lote.
- `lotes-comprobantes.service.ts` puede enviar `formato_version_id` al validar
  cuando el usuario confirmo un formato externo, y `perfil_carga_masiva_id`
  cuando corresponde guardar snapshot del perfil aplicado.
- `perfiles-carga-masiva.service.ts` lista, crea, edita, elimina y marca como
  predeterminado perfiles del emisor activo.
