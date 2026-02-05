# Stores (Pinia)

Stores de Pinia para estado global.

## Estructura actual

```
stores/
├── auth.ts           # Autenticacion y usuario actual
├── empresa.ts        # Empresa activa
├── clientes.ts       # Estado de clientes
├── puntos_venta.ts   # Puntos de venta
├── comprobantes.ts   # Comprobantes
└── ui.ts             # Estado UI (notificaciones, spinners, etc.)
```

## Notas

- Preferir `defineStore(..., () => { ... })` (setup stores) para tipado y composicion.
- Si un store crece demasiado, mover logica a `frontend/src/services/` y dejar el store como orquestador.

