# Documentacion Interna del Proyecto

Documentos historicos y/o de trabajo (resumenes de implementacion, auditorias, notas de seguridad).

Importante: estos documentos pueden quedar desactualizados. La documentacion "canonica" para uso diario esta indexada en `docs/README.md`.

Desde el corte `0.2.0-mvp` del 2026-05-22, el historial del producto debe
resumirse principalmente en `CHANGELOG.md`. Evitar agregar nuevos snapshots
largos en este directorio salvo que sean auditorias puntuales o evidencia
tecnica que no pueda resumirse sin perder trazabilidad.

Regla de lectura:
- No usar estos archivos para decidir el estado actual del producto sin
  contrastar antes `docs/agents/current-status.md`, `ROADMAP.md`,
  `CHANGELOG.md` y el codigo.
- Las menciones a versiones, endpoints, pendientes o "produccion" reflejan el
  momento en que se escribio cada documento.
- Si un documento historico contiene una instruccion peligrosa o datos privados
  versionados, se puede corregir o redactar sin borrar el valor historico del
  hallazgo.
- Si un snapshot viejo ya esta resumido en `CHANGELOG.md` y no aporta valor
  operativo, puede eliminarse en una limpieza documental dedicada, revisando
  antes que no contenga instrucciones vigentes ni datos privados que deban
  redactarse.

## Indice

- Releases / fases:
  - Los resumenes de fases antiguas quedaron consolidados en `CHANGELOG.md`.
    No mantener nuevos archivos de fase salvo que haya una razon operativa
    concreta.
- Auditorias:
  - Verificacion del proyecto: `docs/project/audits/VERIFICACION_PROYECTO.md`
- Seguridad:
  - Update de dependencias (security patch): `docs/project/security/SECURITY_UPDATE.md`
- Notas:
  - Sesion 2026-03-09 (smoke real ARCA, fixes y punto de continuidad): `docs/project/notes/SESSION_2026-03-09.md`
