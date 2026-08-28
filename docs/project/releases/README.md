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

## Estado actual de releases

- `v0.3.1`: candidato congelado el 28/08/2026; tag, publicación y despliegue
  permanecen como checkpoints separados:
  `docs/project/releases/v0.3.1-candidate.md`
- [`v0.3.0`](https://github.com/Santi-RL/FactuFlow/releases/tag/v0.3.0),
  publicada y marcada como `Latest` el 11/08/2026; el estado desplegado actual
  se consulta en `VPS Hostinger` / `vps-admin`
- `v0.2.2`, publicada y desplegada el 2026-07-23:
  `docs/project/releases/v0.2.2-candidate.md`

## Snapshot de cierre de preparación de v0.3.0

- `v0.3.0`: alcance y notas versionados. Al cerrar el snapshot el 11/08/2026
  todavía no se habían ejecutado tag, publicación ni despliegue. El
  `autoreview`, PF-16G, PostgreSQL/Runtime Smoke y el ensayo privado están
  cerrados. El merge funcional `2add308a` aprobó los siete checks; el cierre
  documental `147693f2` y la preparación final `6fb2878` aprobaron sus recorridos
  Nivel 0. Los checkpoints posteriores se registran por separado:
  `docs/project/releases/v0.3.0-candidate.md`
