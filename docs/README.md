# Documentacion

Este directorio agrupa la documentacion del proyecto.

## Indice

- Changelog y corte versionado actual: `CHANGELOG.md`
- Instalacion y setup: `docs/setup/README.md`
- Manual de usuario: `docs/user-guide/README.md`
- API REST (referencia y ejemplos): `docs/api/README.md`
- Certificados ARCA (guia): `docs/certificates/README.md`
- Wizard de certificados (doc tecnica): `docs/certificados-wizard.md`
- Integracion ARCA historica/tecnica inicial: `docs/arca-integration.md`
- Integracion ARCA operativa vigente: `docs/agents/arca.md` y `docs/arca-ws/NOTAS.md`
- PDFs y reportes: `docs/FASE_6_PDF_REPORTES.md`
- Documentacion para agentes (operativa del repo): `docs/agents/README.md`
- Estado actual y continuidad: `docs/agents/current-status.md`
- QA manual en curso: `docs/agents/manual-qa.md`
- Observabilidad operativa estandar: `docs/agents/operational-observability.md`
- Documentacion interna del proyecto (auditorias y notas historicas puntuales): `docs/project/README.md`

## Notas

- Textos publicos y documentacion nueva: usar **ARCA**. "AFIP" queda para nomenclatura legacy (URLs/variables existentes).
- Si estas buscando "donde esta X en el codigo", empeza por `docs/agents/structure.md`.
- Los documentos de `docs/project/` son historicos o de trabajo: pueden
  contener decisiones, versiones o endpoints de su fecha. Para estado actual,
  usar primero `docs/agents/current-status.md` y `ROADMAP.md`.
- Desde el corte `0.2.0-mvp` del 2026-05-22, evitar nuevos snapshots largos de
  documentacion. El avance historico debe resumirse en `CHANGELOG.md` y las
  instrucciones vigentes deben vivir en los documentos canonicos.
