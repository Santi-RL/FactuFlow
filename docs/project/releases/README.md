# Preparación de releases

Esta carpeta conserva dossiers operativos de candidatos concretos cuando una
release necesita inventario, migración, rollback y puertas verificables que no
entran de forma clara en el changelog.

No reemplaza las fuentes canónicas:

- `CHANGELOG.md` resume cambios;
- `ROADMAP.md` decide cortes flexibles;
- `docs/agents/current-status.md` indica el punto de reanudación;
- `docs/agents/production-workflow.md` define cómo desplegar.

Un dossier no crea un tag ni autoriza producción. Los datos, comandos y
evidencia de una instalación real permanecen en documentación privada.

## Último dossier publicado

- `v0.2.2`, publicada y desplegada el 2026-07-23:
  `docs/project/releases/v0.2.2-candidate.md`

## Candidato en preparación

- `v0.3.0`: candidato funcional validado
  `e9c583a8174ea8edc6fe30845584033feab0394d`, sobre la base `b5eefcd`, con
  PF-19C en `c1dbd82` y matriz PF-16G aceptada el 10/08/2026; sin tag, publicación ni
  despliegue. El `autoreview` final cerró limpio y la CI Nivel 2 del SHA
  funcional aprobó PostgreSQL real y Runtime Smoke. Permanece el ensayo privado
  de backup/restauración/upgrade/rollback:
  `docs/project/releases/v0.3.0-candidate.md`
