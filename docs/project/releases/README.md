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

## Candidato listo para tag

- `v0.3.0`: alcance y notas congelados; sin tag, publicación ni despliegue. El
  `autoreview`, PF-16G, PostgreSQL/Runtime Smoke y el ensayo privado están
  cerrados. El merge funcional `2add308a` aprobó los siete checks y el cierre
  documental `147693f2` aprobó su recorrido Nivel 0. El tag debe apuntar al
  merge commit exacto de esta preparación después de su propia CI Nivel 0:
  `docs/project/releases/v0.3.0-candidate.md`
