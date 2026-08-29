# Archivo histórico documental

Estado: HISTÓRICO; NO AUTORITATIVO.

Esta carpeta conserva snapshots y documentos retirados de la lectura diaria.
Reflejan el momento en que fueron escritos y pueden contener versiones,
prioridades o instrucciones superadas.

Para decisiones actuales usar, en este orden:

1. `VISION.md`;
2. `ROADMAP.md`;
3. `docs/agents/current-status.md`;
4. el diseño o runbook aplicable.

## Manifiesto de preservación — 29/08/2026

Las siguientes versiones se preservaron de forma fiel antes de resumirlas. Los
siete documentos principales se movieron; los cuatro índices se recuperaron del
`HEAD` original antes de reemplazarlos. La tabla registra el hash del origen y,
para los índices, los blobs Git se verificaron contra ese origen. Los snapshots
pueden anonimizar ejemplos fiscales o identificadores numéricos incidentales sin
alterar decisiones, estado ni trazabilidad; esas excepciones se detallan debajo.

| Snapshot | Origen | Líneas | SHA-256 del origen |
|---|---|---:|---|
| `roadmap-through-2026-08-29.md` | `ROADMAP.md` | 1442 | `2c494df9a32c1cdcc425c0c394fad5d4286e4827f9aecd4fe333cdd8bf413046` |
| `current-status-through-v0.3.2.md` | `docs/agents/current-status.md` | 754 | `de2744fb00d2138b55c9deea91d543e206422d70df9aaadce20344e9b90601f8` |
| `development-portfolio-through-v0.3.2.md` | `docs/agents/development-portfolio.md` | 227 | `d3e2a9a6921ff6ab4638144570e86cc4154f41e942c86bf640b5dbd1f90fe436` |
| `testing-through-v0.3.2.md` | `docs/agents/testing.md` | 599 | `cc1788a763cdff90bd9c3cad2c265f08c69ca2bc8cc3e4174365b7aadf7a449f` |
| `manual-qa-through-v0.3.2.md` | `docs/agents/manual-qa.md` | 574 | `9f20bf095182fd1a3dda51dd95bb9c1daa3267b6101069461458ba5014ad8dbe` |
| `overview-through-v0.3.2.md` | `docs/agents/overview.md` | 112 | `3c7ad9ec4706a25564735f103eca7215f567a13e4ff549d27bb0ef821778f433` |
| `alignment-audit-closed-2026-05-07.md` | `docs/agents/alignment-pending.md` | 250 | `b865b35906a1a60e4868ea3c30a40c7db9f4836f058b7b097dee007fd3705a3c` |
| `docs-index-through-v0.3.2.md` | `docs/README.md` | 49 | `b7f461d3515ef077eef5503031220c30c24112fbd98a486088618378d880c869` |
| `agents-index-through-v0.3.2.md` | `docs/agents/README.md` | 220 | `befa218cf6add0beae9d9710c3f40060d066f4785bb9827cbc1af54559a1f04f` |
| `project-index-through-v0.3.2.md` | `docs/project/README.md` | 45 | `73c4eea85357e28f5fb6f8190ebaef9699f636357b70324b0cd1b7f301470763` |
| `releases-index-through-v0.3.2.md` | `docs/project/releases/README.md` | 41 | `8f323e2936653832ccb107b1b382433784b301ecc3eb12b3c71db3ffcba1b4e7` |

También se reubicaron estos documentos; la tabla conserva el hash del origen:

| Archivo | Origen | SHA-256 |
|---|---|---|
| `fase-6-pdf-reportes.md` | `docs/FASE_6_PDF_REPORTES.md` | `301d96cc2f276685d96529477829cef2610fad21287bbf8aae16fe9e8d520f93` |
| `integracion-arca-inicial.md` | `docs/arca-integration.md` | `80cc5f1642314e5f4a1a8598ccd4bc621daf9ec31d49b47768444687880dc83e` |
| `../releases/v0.3.2-design-qa.md` | `design-qa.md` | `b17436f5fe30a20814a33e5aa30be359703208e2f6c6dfb4668d4413f8d0e36a` |

## Anonimización aplicada

Para evitar confundir ejemplos o identificadores públicos con datos fiscales
reales, se sustituyeron CUIT, documentos, códigos de autorización y números de
ejecuciones CI por marcadores descriptivos. No se eliminaron decisiones,
resultados ni referencias a PR, commits, tags o dossiers.

| Snapshot anonimizado | SHA-256 del snapshot |
|---|---|
| `roadmap-through-2026-08-29.md` | `20dedee8f38d3ae11cbf4da136eaadadc95a2e111cacf657cab59744faa567d1` |
| `current-status-through-v0.3.2.md` | `7bc748b7faf317d122983d0cf156ef5fbc9d8ab7d55a8652626b62af6f90daee` |
| `testing-through-v0.3.2.md` | `4c6d29600658fd38665a59fc4262d301b2df3f3f1f504c32ecd031a3532aecb6` |
| `manual-qa-through-v0.3.2.md` | `5d12e258dea8d97a0a5430be820bb31d11083ffe0d426a42f7e9628bd30dfc66` |
| `fase-6-pdf-reportes.md` | `bd479dbfba3da98ae09f204e6e665cd44468adf06b718e4ce2ff1b566ee8c28b` |

## Auditoría de reorganización

La clasificación del corpus, las decisiones de migración y la adjudicación de
los 91 ítems no cerrados del roadmap se registran en
[`documentation-audit-2026-08-29.md`](documentation-audit-2026-08-29.md).

## Regla de uso

- No actualizar estos snapshots para alinearlos con el presente.
- No seguir instrucciones históricas sin contrastar una fuente viva.
- No copiar evidencia privada a esta carpeta.
- Si un snapshot contiene un dato sensible o un ejemplo que pueda confundirse
  con uno real, anonimizarlo y registrar la razón y el nuevo hash en este índice.
