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
├── pdf.service.ts            # PDFs
└── reportes.service.ts       # Reportes
```

## Convenciones

- Endpoints del backend usan prefijo `/api/...` (ver `backend/app/main.py`).
- Evitar duplicar logica de negocio: el frontend arma requests, el backend valida.

