# Estado aceptado del repositorio

Última revisión: 01/09/2026

Estado: VIGENTE.

Este documento es un handoff breve sobre lo aceptado en el repositorio. No
conserva historia de implementación, evidencia de CI ni el estado de una
instalación concreta.

El estado desplegado autoritativo vive en el plano de control `VPS Hostinger` /
`vps-admin`. No se infiere desde `main`, una release, un tag ni este documento.

## Línea base aceptada

- La release publicada más reciente es `v0.3.4`.
- El producto usa backend FastAPI, frontend Vue 3 y Alembic como camino canónico
  de esquema para PostgreSQL.
- FactuFlow admite emisión individual y masiva, clientes, comprobantes, PDFs,
  reportes, certificados, puntos de venta, perfiles y formatos de importación.
- El modelo actual mantiene un emisor activo explícito por vez.
- Los operadores tienen cero, uno o varios accesos explícitos por emisor. Una
  capacidad separada permite crear y editar emisores asignados sin conceder
  administración global ni borrado.
- Las operaciones fiscales preservan fecha explícita, confirmación irreversible,
  idempotencia, intentos durables y reconciliación cuando ARCA pudo autorizar.
- PF-01, PF-02, PF-03A/PF-03B, PF-06/PF-07/PF-08 y
  PF-19A/PF-19B/PF-19C/PF-19D están cerrados.
- `v0.3.4` usa WSFE como autoridad autenticada de puntos CAE por emisor y
  ambiente, separa su estado técnico de la preferencia compartida de uso y deja
  la constancia como complemento descriptivo opcional.
- La selección comprueba puntos WSFE desactualizados antes de habilitar opciones
  y conserva el preflight final del servidor.

La conducta aceptada de puntos de venta usa `FEParamGetPtosVenta` como autoridad
técnica por emisor y ambiente. Los puntos CAE compatibles quedan separados de
la preferencia compartida `Usar en FactuFlow`; la constancia es opcional y sólo
completa domicilio, nombre de fantasía y puntos informativos de otros sistemas.
La revisión fiscal, el preflight de 90 días, la idempotencia y la reconciliación
permanecen vigentes.

## Trabajo aceptado pendiente

1. **PF-11/PF-15:** recuperación y trazabilidad operativa.
2. Evidencia histórica y robustez según el orden de `ROADMAP.md`.

El orden y alcance macro se consultan exclusivamente en
[`ROADMAP.md`](../../ROADMAP.md). El detalle completo está en
[`development-portfolio.md`](development-portfolio.md) y los diseños enlazados.

## Punto de reanudación

Para continuar desarrollo:

1. verificar `git status --short --branch` y sincronía con `origin/main`;
2. leer `VISION.md` y la primera unidad de `ROADMAP.md`;
3. abrir únicamente el diseño y los runbooks indicados para esa unidad;
4. si el cambio es fiscal, completar `fiscal-change-checklist.md` antes de
   implementar;
5. no consultar ni modificar producción sin una autorización explícita y el
   enrutamiento establecido hacia `vps-admin`.

No se debe reconstruir el contexto leyendo auditorías o diseños cerrados. Para
historia usar `CHANGELOG.md`, dossiers o
[`docs/project/history/`](../project/history/README.md).

## Fuentes relacionadas

- Visión y decisiones de producto: [`VISION.md`](../../VISION.md)
- Prioridades: [`ROADMAP.md`](../../ROADMAP.md)
- Portafolio pendiente: [`development-portfolio.md`](development-portfolio.md)
- Arquitectura estable: [`overview.md`](overview.md)
- Índice para agentes: [`README.md`](README.md)
- Historial de versiones: [`CHANGELOG.md`](../../CHANGELOG.md)
