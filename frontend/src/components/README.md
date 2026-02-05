# Componentes (Vue)

Esta carpeta contiene componentes reutilizables del frontend.

## Estructura actual

```
components/
├── layout/         # Layout principal (Sidebar, Header, etc.)
├── ui/             # Componentes base (Base*.vue)
├── common/         # Componentes compartidos no-UI (paginacion, dialogs, etc.)
├── comprobantes/   # Componentes de dominio
└── certificados/   # Wizard y componentes de certificados
```

## Convenciones

- Composition API con `<script setup>` y TypeScript recomendado.
- Componentes en PascalCase.
- Eventos en kebab-case.
- Preferir Tailwind utilities; usar CSS custom solo cuando sea necesario.

## Componentes base

Los componentes base del proyecto viven en `frontend/src/components/ui/` y usan prefijo `Base` (ej: `BaseButton.vue`, `BaseInput.vue`, `BaseModal.vue`).

