# Gobierno de la documentación

Última revisión: 05/09/2026

Estado: VIGENTE.

## Objetivo

Mantener una única responsabilidad por documento, reducir el contexto necesario
para cada tarea y preservar la historia sin presentarla como instrucción actual.

## Categorías

| Categoría | Responsabilidad | Ejemplos |
|---|---|---|
| Canónico | Decisión que sólo cambia por autorización explícita | `VISION.md` |
| Prioridades | Orden y resultados futuros | `ROADMAP.md` |
| Estado | Handoff breve del repositorio aceptado | `current-status.md` |
| Portafolio | Inventario activo y dependencias | `development-portfolio.md` |
| Diseño | Contrato de una unidad concreta | documentos `pf-*` |
| Runbook | Procedimiento reutilizable | testing, QA, seguridad, producción |
| Contrato público | Conducta visible para usuario o integrador | manual y API |
| Historia | Hechos cerrados y evidencia | changelog, dossiers, auditorías, snapshots |
| Referencia | Material externo o técnico de consulta | `docs/arca-ws/` |

## Lectura mínima

- Una tarea simple no exige leer todo `docs/agents/`.
- Una decisión de producto consulta `VISION.md` y `ROADMAP.md`.
- “Continuar donde quedamos” consulta `current-status.md`, el primer ítem del
  roadmap y su diseño.
- Una tarea fiscal abre además el checklist fiscal y el diseño aplicable.
- QA, seguridad, despliegue, API o UX abren sólo su runbook o contrato.
- Auditorías, snapshots y diseños cerrados se leen únicamente para rastrear una
  decisión o evidencia.

## Cuándo actualizar

- `ROADMAP.md`: sólo si cambia una prioridad, horizonte o resultado aceptado.
- `current-status.md`: sólo si cambia el estado aceptado o el punto de handoff.
- `development-portfolio.md`: si entra, se adjudica, se depende o se cierra una
  línea de trabajo.
- `manual-qa.md`: si cambia un procedimiento reutilizable, no por el resultado
  de una corrida.
- `testing.md`: si cambian comandos, entornos o políticas, no por nuevos
  conteos.
- `CHANGELOG.md`: para cambios aceptados y releases.
- Dossier: evidencia completa de un candidato o release.
- Diseño: contrato, decisiones y aceptación de una unidad concreta.

No editar todos los documentos por reflejo. Revisar los consumidores y cambiar
sólo el dueño de cada hecho.

## Roadmap

- Mantener `Ahora`, `Después` y `Más adelante` sólo con trabajo futuro.
  El cierre y las releases se consultan en changelog, dossier y estado; el
  roadmap puede enlazarlos sin duplicar su historia ni fijar un despliegue.
- No copiar matrices, SHAs, comandos, pruebas o cronologías.
- Mover el detalle a un diseño y la historia a changelog/dossier/archivo.
- No usar fechas o versiones como compromiso sin decisión explícita.
- Si supera aproximadamente 250 líneas, revisar duplicaciones y extraer detalle.

## Estado y evidencia

- El repositorio puede declarar release publicada y capacidades aceptadas.
- Nunca fija la versión, SHA o salud desplegada de una instalación.
- Producción se consulta en `VPS Hostinger` / `vps-admin`.
- La evidencia privada no se copia al repositorio público.

## Archivo

Antes de reducir material con información única:

1. mover o copiar fielmente el original a `docs/project/history/`; anonimizar
   ejemplos sensibles o identificadores incidentales y registrar toda redacción;
2. calcular SHA-256 y registrarlo en el índice histórico;
3. marcar el snapshot como no autoritativo desde el índice y registrar cualquier
   anonimización;
4. actualizar enlaces vivos;
5. comprobar que el nuevo documento conserva o enlaza toda decisión activa.

Los documentos históricos no se corrigen para que parezcan actuales. Sólo se
redactan si contienen información privada o peligrosa.

## Simplicidad segura

La documentación debe explicar riesgos y acciones en lenguaje administrativo.
No debe convertir detalles de implementación en pasos del usuario. Si una
propuesta aumenta fricción o reduce seguridad, se aplica la regla de decisión de
`VISION.md` y `AGENTS.md`: exponer el intercambio y pedir autorización.

## Revisión

Toda unidad documental verifica:

- enlaces relativos;
- fuentes de verdad y estados transitorios;
- tildes, puntuación y nomenclatura ARCA;
- privacidad;
- `git diff --check` y `npm run docs:check`;
- rango completo antes del commit y antes del merge.
