# Documentación interna del proyecto

Documentos históricos y/o de trabajo (resúmenes de implementación, auditorías, notas de seguridad).

Importante: estos documentos pueden quedar desactualizados. La documentación canónica para uso diario está indexada en `docs/README.md`.

Desde el corte `0.2.0-mvp` del 2026-05-22, el historial del producto debe
resumirse principalmente en `CHANGELOG.md`. Evitar agregar nuevos snapshots
largos en este directorio salvo que sean auditorías puntuales o evidencia
técnica que no pueda resumirse sin perder trazabilidad.

Regla de lectura:
- No usar estos archivos para decidir el estado actual del producto sin
  contrastar antes `docs/agents/current-status.md`, `ROADMAP.md`,
  `CHANGELOG.md` y el código.
- Las menciones a versiones, endpoints, pendientes o "producción" reflejan el
  momento en que se escribió cada documento.
- Si un documento histórico contiene una instrucción peligrosa o datos privados
  versionados, se puede corregir o redactar sin borrar el valor histórico del
  hallazgo.
- Si un snapshot viejo ya está resumido en `CHANGELOG.md` y no aporta valor
  operativo, puede eliminarse en una limpieza documental dedicada, revisando
  antes que no contenga instrucciones vigentes ni datos privados que deban
  redactarse.

## Índice

- Releases / fases:
  - Los resúmenes de fases antiguas quedaron consolidados en `CHANGELOG.md`.
    No mantener nuevos archivos de fase salvo que haya una razón operativa
    concreta.
- Auditorías:
  - Verificación del proyecto: `docs/project/audits/VERIFICACION_PROYECTO.md`
  - Clawpatch: `docs/project/audits/clawpatch/README.md`
  - Cierre del ciclo `v0.2.1`:
    `docs/project/audits/clawpatch/2026-07-10-cierre-ciclo-v0.2.1.md`
- Seguridad:
  - Update de dependencias (security patch): `docs/project/security/SECURITY_UPDATE.md`
- Notas:
  - Sesión histórica 2026-03-09:
    `docs/project/notes/SESSION_2026-03-09.md`
  - Las bitácoras extensas de estado/QA previas a la normalización del
    2026-07-10 se consultan, solo como historia, en el commit `ece2bdf`.
