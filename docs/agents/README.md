# Documentación para agentes

Última revisión: 05/09/2026

Este índice evita reconstruir el proyecto leyendo historia irrelevante. Abrir
sólo la fuente que gobierna la tarea actual.

## Fuentes de verdad

| Pregunta | Fuente |
|---|---|
| ¿Qué producto construimos y qué decisiones requieren autorización? | `VISION.md` |
| ¿Qué viene ahora y en qué orden? | `ROADMAP.md` |
| ¿Qué está aceptado en el repositorio y dónde retomar? | `current-status.md` |
| ¿Qué trabajo activo existe y de qué depende? | `development-portfolio.md` |
| ¿Qué cambió en cada versión? | `CHANGELOG.md` y dossiers |
| ¿Qué está desplegado realmente? | `VPS Hostinger` / `vps-admin` |
| ¿Dónde está la evidencia o documentación retirada? | `docs/project/history/` |

Ninguna release o tag prueba por sí solo el estado de una instalación.

## Lectura mínima por tarea

### Continuar donde quedamos

1. `current-status.md`;
2. primer ítem de `ROADMAP.md`;
3. diseño enlazado por ese ítem;
4. `git status --short --branch` y sincronía con `origin/main`.

### Decisión de producto o UX

- `VISION.md`;
- `ROADMAP.md` si cambia prioridad;
- manual de usuario o diseño de la pantalla.

Aplicar siempre la regla de simplicidad segura. Si una solución agrega fricción
o reduce una protección, detener la decisión e involucrar al usuario.

### Cambio fiscal, ARCA o emisión

- `fiscal-change-checklist.md`;
- diseño PF aplicable;
- `arca.md` y `docs/arca-ws/NOTAS.md` cuando corresponda;
- `testing.md` y `manual-qa.md`.

### Backend, frontend o estructura

- `structure.md` para ubicar módulos;
- README del módulo afectado;
- `overview.md` sólo si cambia arquitectura.

### QA y calidad

- `testing.md` para comandos y políticas;
- `manual-qa.md` para recorridos reutilizables;
- `change-quality-gates.md` para riesgo, PR y CI.

### Seguridad, soporte o despliegue

- `security.md`;
- `support-runbook.md` u `operational-observability.md`;
- `production-workflow.md` sólo con autorización productiva.

## Diseños activos

- PF-13/PF-17, implementación futura:
  [plantillas contables](pf-13-plantillas-contables-design.md) y
  [prevención de duplicados en lotes](pf-13-duplicados-lotes-design.md).
- PF-18/PF-17, implementación futura:
  [dashboard mensual y fechas de emisión](pf-18-dashboard-mensual-design.md).
- PF-19D:
  [`pf-19d-puntos-venta-authority-design.md`](pf-19d-puntos-venta-authority-design.md)
- PF-06/PF-07/PF-08:
  [`pf-06-08-permisos-multiemisor-design.md`](pf-06-08-permisos-multiemisor-design.md)
- Rediseño de lotes diferido:
  [`lotes-ux-redesign.md`](lotes-ux-redesign.md)

PF-01, PF-02, PF-03A/B y PF-19A/B/C están cerrados. El contrato de ítems vive en
[`pf-03b-items-importes-design.md`](pf-03b-items-importes-design.md).
Sus diseños se consultan sólo para
preservar invariantes o rastrear decisiones.

## Runbooks

- Arquitectura estable: [`overview.md`](overview.md)
- Estructura del repositorio: [`structure.md`](structure.md)
- Integración ARCA: [`arca.md`](arca.md)
- Testing: [`testing.md`](testing.md)
- QA manual: [`manual-qa.md`](manual-qa.md)
- Seguridad: [`security.md`](security.md)
- Observabilidad: [`operational-observability.md`](operational-observability.md)
- Soporte: [`support-runbook.md`](support-runbook.md)
- Launcher local: [`local-launcher-runbook.md`](local-launcher-runbook.md)
- Producción: [`production-workflow.md`](production-workflow.md)
- Gobierno documental:
  [`documentation-governance.md`](documentation-governance.md)

## Reglas de continuidad

- No reabrir un corte cerrado sin evidencia nueva.
- No convertir findings automáticos en prioridades sin validación.
- No copiar conteos, SHAs o historia en roadmap, estado, testing o QA.
- No incluir nombres de ramas temporales en documentación viva.
- No versionar evidencia privada ni datos fiscales reales.
- Corregir hechos comprobables; presentar al usuario las decisiones abiertas.
- Usar ARCA en contenido nuevo y AFIP sólo para compatibilidad legacy.

La política completa de actualización y archivo vive en
[`documentation-governance.md`](documentation-governance.md).
