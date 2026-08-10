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

- `v0.3.0`: candidato `7f7b3808b3d4b8d5a129c193724955789a6ed4f2`, sobre
  la base `b5eefcd`, con PF-19C y matriz PF-16G aceptada el 10/08/2026; sin
  tag, publicación ni despliegue. El `autoreview` final cerró limpio, la CI
  Nivel 2 aprobó PostgreSQL real y Runtime Smoke, y el ensayo privado de backup,
  restauración aislada, upgrade y rollback quedó aprobado:
  `docs/project/releases/v0.3.0-candidate.md`
