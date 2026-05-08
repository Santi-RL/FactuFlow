# Docs para agentes

## Leer primero en cada sesion

- Pendientes temporales de alineacion: `docs/agents/alignment-pending.md`
- Estado operativo canonico y punto de reanudacion: `docs/agents/current-status.md`
- QA manual y ultimo checkpoint: `docs/agents/manual-qa.md`
- Roadmap canonico: `ROADMAP.md`

## Fuente de verdad operativa

- `docs/agents/current-status.md` es la fuente canonica para saber donde esta parado el proyecto hoy.
- `ROADMAP.md` solo debe resumir prioridades y avance macro, no repetir evidencia operativa detallada.
- `docs/agents/manual-qa.md` registra recorridos de QA y hallazgos manuales, no reemplaza el estado canonico.
- `docs/user-guide/README.md` describe lo que ve y puede hacer un usuario final; no debe contener bitacora tecnica.
- `docs/agents/arca.md` conserva detalles tecnicos ARCA y procedimientos seguros.

## Indice rapido por tema

- Resumen y arquitectura: `docs/agents/overview.md`
- Pendientes temporales de alineacion: `docs/agents/alignment-pending.md`
- Estructura del repo y ubicacion de archivos: `docs/agents/structure.md`
- Integracion ARCA y hallazgos de homologacion: `docs/agents/arca.md`
- Documentacion oficial ARCA WS curada: `docs/arca-ws/README.md`
- Notas practicas ARCA: `docs/arca-ws/NOTAS.md`
- API REST: `docs/api/README.md`
- Formatos de importacion para emision masiva: `docs/api/README.md`,
  `backend/app/services/README.md`, `frontend/src/services/README.md`
- Certificados y wizard: `docs/certificates/README.md`, `docs/certificados-wizard.md`
- Instalacion y setup: `docs/setup/README.md`
- Manual de usuario: `docs/user-guide/README.md`
- Seguridad y certificados: `docs/agents/security.md`
- Guia de testing: `docs/agents/testing.md`
- Bitacora tecnica de la ultima sesion: `docs/project/notes/SESSION_2026-03-09.md`

## Regla de continuidad

Si el usuario dice algo como "quiero seguir donde quedamos", la secuencia correcta es:

1. Leer `docs/agents/alignment-pending.md`
2. Si hay puntos pendientes, avisarlo brevemente antes de continuar
3. Leer `docs/agents/current-status.md`
4. Leer `docs/agents/manual-qa.md`
5. Confirmar el siguiente paso en `ROADMAP.md`

Si el usuario pregunta "como esta el proyecto" o "que es lo primero que debemos
solucionar", ir directo al primer punto pendiente de
`docs/agents/alignment-pending.md`.

No rearmar el contexto desde cero si esos archivos ya lo documentan.

## Como resolver dudas y errores

1. Buscar primero en esta documentacion local con `rg`.
2. Si el tema es ARCA, revisar `docs/agents/arca.md` y `docs/arca-ws/NOTAS.md`.
3. Si el tema es emision masiva o Excel externo, revisar tambien
   `docs/user-guide/README.md`, `docs/api/README.md` y los README de
   `backend/app/services/` y `frontend/src/services/`.
4. Si falta contexto historico de trabajo, revisar `docs/project/notes/SESSION_2026-03-09.md`.
5. Si no alcanza con la documentacion local, buscar en internet agregando `ARCA`.
6. Si con `ARCA` no aparece, repetir usando `AFIP` por compatibilidad legacy.
