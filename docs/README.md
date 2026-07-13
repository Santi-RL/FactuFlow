# Documentación

Este directorio agrupa la documentación del proyecto.

## Índice

- Changelog y corte versionado actual: `CHANGELOG.md`
- Candidato de release `v0.2.2`: `docs/project/releases/v0.2.2-candidate.md`
- Instalación y setup: `docs/setup/README.md`
- Migración local a VPS: `docs/setup/vps-migration.md`
- Manual de usuario: `docs/user-guide/README.md`
- API REST (referencia y ejemplos): `docs/api/README.md`
- Certificados ARCA (guía): `docs/certificates/README.md`
- Wizard de certificados (doc técnica): `docs/certificados-wizard.md`
- Integración ARCA histórica/técnica inicial: `docs/arca-integration.md`
- Integración ARCA operativa vigente: `docs/agents/arca.md` y `docs/arca-ws/NOTAS.md`
- PDFs y reportes (documento técnico histórico de fase): `docs/FASE_6_PDF_REPORTES.md`
- Documentación para agentes (operativa del repo): `docs/agents/README.md`
- Estado actual y continuidad: `docs/agents/current-status.md`
- QA manual vigente y pendientes accionables: `docs/agents/manual-qa.md`
- Cierre metodológico Clawpatch/v0.2.1:
  `docs/project/audits/clawpatch/2026-07-10-cierre-ciclo-v0.2.1.md`
- Observabilidad operativa estándar: `docs/agents/operational-observability.md`
- Documentación interna del proyecto (auditorías y notas históricas puntuales): `docs/project/README.md`

## Notas

- Textos públicos y documentación nueva: usar **ARCA**. "AFIP" queda para nomenclatura legacy (URLs/variables existentes).
- Si estás buscando "dónde está X en el código", empezá por `docs/agents/structure.md`.
- Los documentos de `docs/project/` son históricos o de trabajo: pueden
  contener decisiones, versiones o endpoints de su fecha. Para estado actual,
  usar primero `docs/agents/current-status.md` y `ROADMAP.md`.
- Desde el corte `0.2.0-mvp` del 2026-05-22, evitar nuevos snapshots largos de
  documentación. El avance histórico debe resumirse en `CHANGELOG.md` y las
  instrucciones vigentes deben vivir en los documentos canónicos.
