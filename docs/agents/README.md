# Documentación para agentes

Última revisión: 03/10/2026

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
- `architecture-direction.md` para fronteras compartidas y evolución hacia
  operación asistida, especialmente cuando un cambio cruza consumidores;
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

- PF-03/PF-04/PF-14: [asociación administrativa del receptor](pf-03-04-14-asociacion-cliente.md).
  Define el vínculo opcional sin alterar el snapshot fiscal; capacidad A-01
  permanece pendiente.

- PF-12/PF-15/PF-17: [instantes operativos y hora argentina](pf-12-15-17-tiempo-operativo.md).
  Separa instantes UTC y presentación argentina de fechas de calendario y
  antecedentes con zona desconocida.

- PF-03/PF-04/PF-13, implementación futura:
  [importes y previsualización fiscal común](pf-03-04-importes-previsualizacion-design.md).
  Separa corrección P1 de admisibilidad/revisión, ampliación P2 de categorías y
  consumo por plantillas; preserva redondeos PF-03B.
- PF-02/PF-04, implementación futura:
  [reconciliación fiscal integral](pf-02-04-reconciliacion-integral-design.md).
  Distingue comparación legacy P1 de snapshot/recuperación moderna P2.
- PF-09, implementación futura:
  [WSAA coordinado y caché cifrada](pf-09-wsaa-coordinacion-cache-design.md).
- PF-18/PF-09, implementación futura:
  [padrón para clientes y alta de emisores](pf-18-09-padron-clientes-emisores-design.md),
  con consultas anticipadas, situación registral fechada y bootstrap sin dependencia circular.
- PF-04/PF-17/PF-13, implementación futura:
  [notas de crédito y débito guiadas](pf-04-17-notas-guiadas-design.md).
- PF-13, próximo corte P1, implementación futura:
  [fidelidad del receptor en importación fiscal](pf-13-receptores-importacion-design.md).
  Distingue documento y condición IVA; admite consumidor final identificado sin
  perder datos. El constructor P2 y la UI PF-17 consumen esta regla.
- PF-11/PF-15, implementación futura:
  [recuperación y trazabilidad operativa](pf-11-15-recuperacion-trazabilidad-design.md).
- PF-13/PF-17, contrato del control de emisión masiva:
  [prevención de duplicados en lotes](pf-13-duplicados-lotes-design.md).
- PF-13/PF-17, implementación futura:
  [plantillas contables](pf-13-plantillas-contables-design.md), incluidos alias
  inequívocos y procedencia del receptor y fechas; no repite el corte P1.
- PF-18/PF-17, implementación futura:
  [dashboard mensual y fechas de emisión](pf-18-dashboard-mensual-design.md).
- PF-17, implementación futura:
  [períodos rápidos en Reporte de ventas](pf-17-reportes-periodos-design.md) y
  [usuario e historial de actividad de lotes](pf-17-actividad-lotes-design.md),
  este último con trazabilidad PF-15.
- PF-17, implementación futura:
  [UI compacta de emisión masiva](pf-17-lotes-ui-design.md), con revisión visual
  del usuario en la aplicación local antes de publicar la implementación.

El [portafolio](development-portfolio.md) distingue alcance aceptado de
contratos técnicos todavía por cerrar. Un diseño futuro no significa que la
implementación esté autorizada o terminada.
La [validación de planificación de confiabilidad ARCA](../project/analysis/confiabilidad-arca-roadmap.md)
conserva las hipótesis ensayadas, fuentes y límites; no acredita producción.
La [auditoría integral](../project/analysis/auditoria-integral-2026-10.md) conserva
la limpieza y hallazgos de estado actual; la
[dirección de arquitectura](architecture-direction.md) explica cómo encajan los
cortes y el horizonte MCP. Un hallazgo pendiente no es una capacidad terminada.

## Diseños cerrados de consulta

- PF-13/PF-17: [emisión parcial y reintentos seguros](pf-13-17-reintentos-seguros-parche.md).

- PF-19D:
  [`pf-19d-puntos-venta-authority-design.md`](pf-19d-puntos-venta-authority-design.md)
- PF-06/PF-07/PF-08:
  [`pf-06-08-permisos-multiemisor-design.md`](pf-06-08-permisos-multiemisor-design.md)
- Antecedente de lotes, cortes cerrados; la evolución pendiente está en PF-17:
  [`lotes-ux-redesign.md`](lotes-ux-redesign.md)

También están cerrados PF-01, PF-02, PF-03A/B y PF-19A/B/C. El contrato de ítems
vive en
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
