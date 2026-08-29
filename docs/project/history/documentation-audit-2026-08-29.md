# Auditoría y migración de la arquitectura documental — 29/08/2026

Estado: CERRADA al integrar la unidad documental.

## Alcance y método

El inventario autoritativo de `HEAD` previo a la reorganización contenía **79
archivos Markdown rastreados**, no 80. La estimación inicial de 80 se reconcilió
contra `git ls-tree`; no existía un octogésimo Markdown sin trackear. El corpus
sumaba 22.208 líneas rastreadas, más la modificación aprobada y todavía no
confirmada en un commit de `ROADMAP.md`.

Se revisó cada archivo por audiencia, autoridad, vigencia, duplicación, enlaces,
privacidad, nomenclatura y destino. El código y la configuración sólo se usaron
como evidencia de lectura; no se modificaron.

Además de los siete documentos previstos, se preservaron versiones fieles de
los cuatro índices reescritos. La ampliación aplica el criterio de conservar
todo documento materialmente reducido; sus hashes de origen, líneas y
redacciones controladas están en el índice de esta carpeta.

## Inventarios verificados

La huella de inventario es el SHA-256 de las rutas Markdown normalizadas,
ordenadas y separadas por LF. Verifica el conjunto de archivos sin intentar una
huella autorreferencial del contenido de este mismo informe.

| Momento | Markdown | SHA-256 del inventario de rutas |
|---|---:|---|
| `HEAD` original | 79 | `056db8a9ca22c527e7a29bddded2c5fcd79235486f0540a08f0aaba1368bdcd0` |
| Arquitectura resultante | 94 | `ce5b4ccbf29146a2feae94cbfabca9d5aee5f5b5043a2981c3fcceac1bb58bd7` |

Los hashes de contenido de cada documento preservado se registran en
[`README.md`](README.md) y se verificaron después de su reubicación o copia.

## Clasificación del corpus previo

| Documento original | Clase | Resolución |
|---|---|---|
| `.github/pull_request_template.md` | Plantilla viva | Conservar y alinear con la matriz documental |
| `AGENTS.md` | Instrucción canónica | Reforzar fuentes y simplicidad segura |
| `CHANGELOG.md` | Historia versionada | Conservar; limitarlo a cambios aceptados |
| `CONTRIBUTING.md` | Guía viva | Alinear rutas y flujo documental |
| `README.md` | Resumen e índice | Conservar; enlazar arquitectura nueva |
| `ROADMAP.md` | Prioridades mezcladas con historia | Snapshot completo anonimizado y reemplazo prospectivo |
| `VISION.md` | Visión canónica protegida | Agregar regla autorizada de simplicidad segura |
| `design-qa.md` | Evidencia de release | Mover al dossier de `v0.3.2` |
| `backend/README.md` | Referencia técnica viva | Revisar y conservar |
| `backend/app/afip/README.md` | Referencia legacy | Conservar; AFIP sólo como compatibilidad técnica |
| `backend/app/api/README.md` | Índice de módulos | Revisar y conservar |
| `backend/app/core/README.md` | Índice de módulos | Revisar y conservar |
| `backend/app/models/README.md` | Índice de módulos | Revisar y conservar |
| `backend/app/services/README.md` | Índice de módulos | Actualizar enlace histórico de PDF/reportes |
| `backend/tests/README.md` | Guía técnica viva | Revisar y conservar |
| `docs/FASE_6_PDF_REPORTES.md` | Fase histórica | Mover al archivo histórico |
| `docs/README.md` | Índice general | Reescribir como enrutador por audiencia |
| `docs/agents/README.md` | Índice para agentes | Reescribir con lectura mínima por tarea |
| `docs/agents/alignment-pending.md` | Auditoría cerrada | Mover íntegra a historia; dejar de leer por defecto |
| `docs/agents/arca.md` | Referencia técnica viva | Conservar y distinguir implementación de PF-19D |
| `docs/agents/change-quality-gates.md` | Runbook vigente | Ajustar responsabilidades documentales |
| `docs/agents/current-status.md` | Estado mezclado con historia | Snapshot completo anonimizado y handoff breve |
| `docs/agents/development-portfolio.md` | Portafolio mezclado con cierres | Snapshot íntegro e inventario activo |
| `docs/agents/fiscal-change-checklist.md` | Checklist vigente | Revisar y conservar |
| `docs/agents/local-launcher-runbook.md` | Runbook vigente | Revisar y conservar |
| `docs/agents/lotes-ux-redesign.md` | Diseño activo/diferido | Conservar y consultar sólo por tarea |
| `docs/agents/manual-qa.md` | Runbook mezclado con evidencia | Snapshot completo anonimizado y matriz reutilizable |
| `docs/agents/operational-observability.md` | Diseño/runbook vigente | Conservar; enrutar a PF-15 |
| `docs/agents/overview.md` | Arquitectura mezclada con estado | Snapshot íntegro y resumen estable |
| `docs/agents/pf-01-authorization-integrity-design.md` | Diseño cerrado | Conservar como contrato e historia técnica |
| `docs/agents/pf-01b-persistence-integrity-design.md` | Diseño cerrado | Conservar como contrato e historia técnica |
| `docs/agents/pf-02a-numeracion-individual-design.md` | Diseño cerrado | Conservar como contrato e historia técnica |
| `docs/agents/pf-02b-numeracion-masiva-design.md` | Diseño cerrado | Conservar como contrato e historia técnica |
| `docs/agents/pf-03-validacion-fiscal-design.md` | Diseño parcialmente activo | Conservar; PF-03B es prioridad inmediata |
| `docs/agents/pf-06-08-permisos-multiemisor-design.md` | Diseño aceptado | Conservar para «Después» |
| `docs/agents/pf-19a-rece-contencion-design.md` | Diseño cerrado | Conservar como contrato histórico |
| `docs/agents/pf-19b-elegibilidad-rece-design.md` | Diseño cerrado | Conservar; PF-19D lo sustituye sólo hacia adelante |
| `docs/agents/pf-19c-rechazo-global-design.md` | Diseño cerrado | Conservar como contrato histórico |
| `docs/agents/production-workflow.md` | Runbook vigente | Alinear referencias; producción sigue externa |
| `docs/agents/security.md` | Runbook vigente | Revisar y conservar |
| `docs/agents/structure.md` | Índice técnico | Actualizar árbol documental |
| `docs/agents/support-runbook.md` | Runbook vigente | Revisar y conservar |
| `docs/agents/testing.md` | Guía mezclada con evidencia | Snapshot completo anonimizado y política reutilizable |
| `docs/api/README.md` | Contrato público vivo | Contrastar con rutas y conservar |
| `docs/arca-integration.md` | Integración inicial histórica | Mover al archivo histórico |
| `docs/arca-ws/NOTAS.md` | Referencia técnica viva | Conservar |
| `docs/arca-ws/README.md` | Índice de referencia | Conservar |
| `docs/arca-ws/wsass/introduccion-servicios.md` | Referencia ARCA | Conservar sin reinterpretar como estado actual |
| `docs/certificados-wizard.md` | Diseño técnico vivo | Revisar y conservar |
| `docs/certificates/README.md` | Guía de dominio | Revisar y conservar |
| `docs/project/README.md` | Índice histórico | Actualizar con carpeta de historia |
| `docs/project/audits/VERIFICACION_PROYECTO.md` | Auditoría histórica | Conservar congelada |
| `docs/project/audits/clawpatch/2026-05-16-detecciones.md` | Auditoría histórica | Conservar congelada |
| `docs/project/audits/clawpatch/2026-05-16-puesta-a-punto.md` | Auditoría histórica | Conservar congelada |
| `docs/project/audits/clawpatch/2026-05-16-reparaciones.md` | Auditoría histórica | Conservar congelada |
| `docs/project/audits/clawpatch/2026-07-05-cierre-auditoria.md` | Auditoría histórica | Conservar congelada |
| `docs/project/audits/clawpatch/2026-07-06-lecciones-operativas.md` | Auditoría histórica | Conservar congelada |
| `docs/project/audits/clawpatch/2026-07-10-cierre-ciclo-v0.2.1.md` | Auditoría histórica | Conservar congelada |
| `docs/project/audits/clawpatch/2026-07-12-cierre-auditoria-ordenada.md` | Auditoría histórica | Conservar congelada |
| `docs/project/audits/clawpatch/2026-07-13-cierre-checkpoint-pf-01a.md` | Auditoría histórica | Conservar congelada |
| `docs/project/audits/clawpatch/2026-07-13-cierre-checkpoint-pf-01b.md` | Auditoría histórica | Conservar congelada |
| `docs/project/audits/clawpatch/README.md` | Índice/ledger de auditoría | Conservar; no leer por defecto |
| `docs/project/notes/SESSION_2026-03-09.md` | Bitácora histórica | Conservar congelada |
| `docs/project/releases/README.md` | Índice de dossiers | Corregir estados transitorios e indexar QA |
| `docs/project/releases/v0.2.2-candidate.md` | Dossier histórico | Conservar congelado |
| `docs/project/releases/v0.3.0-candidate.md` | Dossier histórico | Conservar congelado |
| `docs/project/releases/v0.3.1-candidate.md` | Dossier histórico | Conservar congelado |
| `docs/project/releases/v0.3.2-candidate.md` | Dossier histórico | Conservar congelado |
| `docs/project/security/SECURITY_UPDATE.md` | Evidencia histórica | Conservar congelada |
| `docs/setup/README.md` | Guía viva | Contrastar y conservar |
| `docs/setup/vps-migration.md` | Guía histórica/operativa | Mantener como referencia, subordinada al plano de control |
| `docs/user-guide/README.md` | Contrato de usuario vivo | Contrastar con UI y conservar |
| `frontend/README.md` | Referencia técnica viva | Revisar y conservar |
| `frontend/src/assets/README.md` | Índice de módulo | Revisar y conservar |
| `frontend/src/assets/brand/README.md` | Índice de módulo | Revisar y conservar |
| `frontend/src/components/README.md` | Índice de módulo | Revisar y conservar |
| `frontend/src/services/README.md` | Índice de módulo | Revisar y conservar |
| `frontend/src/stores/README.md` | Índice de módulo | Revisar y conservar |
| `frontend/src/views/README.md` | Índice de módulo | Revisar y conservar |

## Adjudicación de los 91 ítems no cerrados

Cada fila identifica el número de línea del snapshot preservado y su destino
activo o histórico. La descripción íntegra se consulta en el snapshot.

| Línea | Estado anterior | Destino |
|---:|---|---|
| 111 | Pendiente | PF-06/PF-08 |
| 113 | En curso | PF-17 |
| 118 | Pendiente | PF-06/PF-07/PF-08 |
| 165 | En curso | PF-03B |
| 182 | En curso | Historia Clawpatch; no es trabajo activo |
| 327 | Pendiente | PF-19D y diseño propio |
| 414 | Pendiente | PF-05 |
| 475 | En curso | PF-06/PF-07/PF-08 |
| 481 | En curso | PF-12 |
| 482 | Pendiente | PF-13 |
| 502 | Pendiente | PF-08/PF-17 |
| 533 | Pendiente | PF-10/PF-18 |
| 555 | En curso | PF-16 y runbook de producción |
| 557 | En curso | PF-15 |
| 563 | En curso | PF-11/PF-15 |
| 577 | En curso | PF-16/PF-18 |
| 606 | En curso | Cerrado por esta arquitectura documental; política vigente |
| 613 | En curso | PF-17 |
| 614 | Pendiente | PF-17 |
| 628 | Pendiente | PF-09 |
| 657 | En curso | PF-09 |
| 666 | Pendiente | PF-15 y runbook de soporte |
| 676 | En curso | PF-09 |
| 679 | En curso | PF-11/PF-15 |
| 681 | Pendiente | PF-09 |
| 806 | En curso | PF-17 |
| 824 | En curso | PF-13 y QA reutilizable |
| 825 | Pendiente | PF-13/PF-17 |
| 836 | Pendiente | PF-10/PF-18 |
| 838 | Pendiente | PF-18 |
| 839 | Pendiente | PF-10/PF-13/PF-18 |
| 841 | Pendiente | PF-13/PF-15 |
| 849 | En curso | PF-14/PF-17 |
| 851 | Pendiente | PF-17 |
| 878 | En curso | PF-17 |
| 879 | Pendiente | PF-17 |
| 886 | En curso | PF-15/PF-17 |
| 887 | Pendiente | PF-17/PF-18 |
| 888 | Pendiente | PF-17 |
| 889 | Pendiente | PF-17; requiere decisión antes de agregar fricción |
| 890 | Pendiente | PF-17 |
| 891 | Pendiente | PF-17; aplicar simplicidad segura |
| 897 | Pendiente | PF-08/PF-17 |
| 899 | Pendiente | PF-17 |
| 910 | En curso | PF-12 |
| 911 | En curso | PF-12 |
| 917 | Pendiente | PF-12/PF-16 |
| 931 | Pendiente | PF-16 |
| 941 | En curso | Historia Clawpatch; ciclo cerrado |
| 951 | Pendiente | PF-04/PF-16 |
| 952 | Pendiente | PF-16 |
| 1041 | Pendiente | PF-16 |
| 1054 | Pendiente | PF-16/PF-18 |
| 1086 | Pendiente | PF-13/PF-14 |
| 1090 | Pendiente | PF-15 |
| 1116 | En curso | PF-06/PF-07/PF-08 |
| 1117 | Pendiente | PF-06 |
| 1119 | Pendiente | PF-06/PF-07/PF-08 y PF-16 |
| 1121 | Pendiente | PF-17, dependiente de multiemisor |
| 1122 | Pendiente | PF-06/PF-07/PF-08 |
| 1184 | En curso | PF-09/PF-16/PF-18 |
| 1185 | En curso | Setup y runbook de producción |
| 1194 | Pendiente | PF-15 |
| 1196 | Pendiente | PF-15 |
| 1197 | Pendiente | PF-10/PF-11 |
| 1204 | En curso | PF-15 |
| 1207 | En curso | PF-11 |
| 1209 | Pendiente | PF-11/PF-15 |
| 1214 | Pendiente | PF-11 |
| 1216 | Pendiente | PF-11 |
| 1222 | Pendiente | PF-09 y seguridad |
| 1228 | En curso | PF-15 |
| 1234 | Pendiente | PF-13/PF-15 |
| 1238 | Pendiente | PF-14/PF-15/PF-17 |
| 1239 | Pendiente | PF-14/PF-15/PF-17 |
| 1242 | En curso | PF-15 y runbook de soporte |
| 1246 | Pendiente | PF-15 |
| 1262 | Pendiente | PF-18 |
| 1344 | Pendiente | PF-18 |
| 1345 | Pendiente | PF-18 |
| 1346 | Pendiente | PF-18 |
| 1352 | Pendiente | PF-15/PF-18 |
| 1353 | Pendiente | PF-15/PF-17 |
| 1354 | Pendiente | PF-15/PF-18 |
| 1355 | Pendiente | PF-12/PF-18 |
| 1362 | En curso | PF-11/PF-15/PF-16 |
| 1363 | Pendiente | PF-18 |
| 1364 | Pendiente | PF-18 |
| 1365 | Pendiente | PF-18 |
| 1367 | Pendiente | PF-18 |
| 1368 | Pendiente | PF-18, idea P3 opcional |

Conteo verificado: **61 pendientes + 30 en curso = 91 adjudicados**.

## Resultado estructural

- Los 259 ítems completados permanecen en el snapshot completo del roadmap; solo
  se anonimizaron identificadores numéricos incidentales.
- Los 91 no cerrados tienen un destino explícito.
- PF-19D conserva detalle implementable en un diseño activo.
- Los documentos vivos ya no necesitan copiar evidencia cerrada.
- Los archivos históricos no forman parte de la lectura inicial de un agente.
