# Services (API client)

Servicios para hablar con el backend (HTTP).

## Estructura actual

```
services/
├── api.ts                    # Axios configurado (baseURL, interceptors, etc.)
├── auth.service.ts           # Auth (setup/login/me)
├── usuarios.service.ts       # Administración de usuarios
├── empresa.service.ts        # Empresa
├── clientes.service.ts       # Clientes
├── puntos_venta.service.ts   # Puntos de venta
├── certificados.service.ts   # Certificados
├── arca.service.ts           # ARCA (tipos, puntos de venta, dummy, etc.)
├── sistema.service.ts        # Health de aplicación y base para Estado del sistema
├── almacenamiento.service.ts # Gestor administrativo de almacenamiento
├── comprobantes.service.ts   # Comprobantes
├── formatos-importacion.service.ts # Plantillas/formato configurables de importacion
├── lotes-comprobantes.service.ts # Emision masiva por Excel
├── perfiles-carga-masiva.service.ts # Perfiles de carga masiva por emisor
├── pdf.service.ts            # PDFs
└── reportes.service.ts       # Reportes
```

## Convenciones

- Endpoints del backend usan prefijo `/api/...` (ver `backend/app/main.py`).
- Evitar duplicar lógica de negocio: el frontend arma requests, el backend valida.
- Los tipos de lotes viven en `frontend/src/types/lote-comprobante.ts`.
- Los tipos de almacenamiento viven en `frontend/src/types/almacenamiento.ts`.
- Los tipos de formatos viven en `frontend/src/types/formato-importacion.ts`.
- Los tipos de perfiles de carga masiva viven en
  `frontend/src/types/perfil-carga-masiva.ts`.
- Los tipos de usuarios viven en `frontend/src/types/auth.ts`.
- `auth.service.ts` usa `GET /api/auth/setup-status` para mostrar setup inicial
  solo cuando no hay usuarios.
- `usuarios.service.ts` habla con `/api/usuarios`; esas rutas son exclusivas de
  administradores.
- `sistema.service.ts` consulta `/api/health` y `/api/health/db` para la pestaña
  `Estado` dentro de `Sistema`, sin disparar llamadas externas a ARCA.
- `almacenamiento.service.ts` habla con `/api/almacenamiento`; esas rutas son
  exclusivas de administradores y cubren resumen, selección de artefactos,
  resguardo ZIP, descarga y liberación posterior.
- `formatos-importacion.service.ts` respalda la UI pública de `Plantillas`:
  lista, crea, edita, desactiva, clona, descarga, analiza Exceles de ejemplo,
  evalúa compatibilidad y detecta candidatos desde un Excel antes de validar el
  lote.
- `lotes-comprobantes.service.ts` puede enviar `formato_version_id` al validar
  cuando el usuario confirmo un formato externo, y `perfil_carga_masiva_id`
  cuando corresponde guardar snapshot del perfil aplicado.
- `comprobantes.service.ts` y `lotes-comprobantes.service.ts` envían
  `X-Idempotency-Key` en las acciones que pueden solicitar CAE. La clave se
  genera en la vista al confirmar la operación fiscal y se conserva para retries
  de esa misma operación.
- `perfiles-carga-masiva.service.ts` lista, crea, edita, elimina y marca como
  predeterminado perfiles del emisor activo.
