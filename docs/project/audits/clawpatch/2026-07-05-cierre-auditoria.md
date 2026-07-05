# Cierre de auditoría Clawpatch - 2026-07-05

Este documento conserva el aprendizaje operativo de la auditoría larga de
Clawpatch sobre FactuFlow. Es un resumen sanitizado: no incluye datos privados,
CUITs, CAEs, PDFs, Exceles, logs ni evidencia productiva.

## Alcance

- Auditoría backend, frontend y repo completo con los state dirs existentes:
  `.clawpatch/backend`, `.clawpatch/frontend` y `.clawpatch/repo`.
- No se ejecutó `clawpatch fix`.
- No se solicitó CAE, no se emitieron comprobantes y no se hicieron llamadas
  reales a ARCA.
- Cada reparación aceptada se hizo como commit separado, con validaciones
  enfocadas y `autoreview` con Codex/GPT-5.5 en esfuerzo alto.
- El cierre remoto se verificó con GitHub Actions usando `gh run list` y
  `gh run view`, no el endpoint legacy de commit statuses.

## Resultado final

- `clawpatch --state-dir .clawpatch/repo --config .clawpatch/repo/config.json status`
  quedó con `openFindings=0`.
- `clawpatch --state-dir .clawpatch/backend --config .clawpatch/backend/config.json status`
  quedó con `openFindings=0`.
- `clawpatch --state-dir .clawpatch/frontend --config .clawpatch/frontend/config.json status`
  quedó con `openFindings=0`.
- CI remoto en GitHub Actions para `ebc176d` quedó aprobado:
  `Frontend Build`, `Backend Tests`, `Security Audit` y `E2E Tests` en
  `success`.

## Cambios realizados

### Mapper nativo del repo

- Problema: el mapeo repo no ejecutaba correctamente el mapper nativo de
  Clawpatch y podía dejar fuera features detectables por la CLI.
- Decisión: llamar a la CLI global `clawpatch` sin pin de versión y mantener
  el wrapper propio para mapear el repo de forma segura.
- Archivos relevantes: `tools/clawpatch/map-repo-native.mjs`, scripts de
  `package.json`, tests de scripts y documentación de testing.
- Validaciones: `npm run clawpatch:test-seeds`, `npm run clawpatch:map-all`,
  `git diff --check` y `autoreview` GPT-5.5 alto.

### Preview de PDF

- Problema: `previsualizarPDF` revocaba el `blob:` a los 100 ms, antes de que
  una pestaña nueva pudiera cargar confiablemente el visor de PDF.
- Corrección: mantener vivo el object URL hasta el evento `load` de la ventana
  de preview o hasta un fallback largo.
- Error detectado por `autoreview`: enganchar `pagehide` o `unload` en la
  ventana devuelta por `window.open` puede revocar el blob durante la navegación
  inicial de `about:blank` al `blob:`, reproduciendo la carrera. Evitar esos
  listeners tempranos.
- Test agregado: `frontend/src/services/pdf.service.spec.ts`, con stubs de
  `URL.createObjectURL`, `window.open` y `URL.revokeObjectURL`.

### Workflow E2E

- Problema: el workflow decía `E2E Tests (on PR only)`, pero el job corría en
  pushes a `main` y en pull requests.
- Decisión: mantener E2E en pushes a `main`, porque el flujo habitual del repo
  trabaja directamente sobre `main` y esa cobertura es valiosa. Se corrigió el
  comentario en lugar de agregar un `if` PR-only.
- Validación: Clawpatch revalidó el hallazgo como `fixed` y `autoreview` no
  encontró defectos.

### Fechas visibles y parsing seguro

- Problema: `formatearFecha` aceptaba cualquier string y lo trataba como
  `YYYY-MM-DD`, pudiendo inventar fechas para strings no soportados.
- Primera corrección insuficiente: conservar `DD/MM/AAAA` como passthrough
  evitaba romper la UI, pero no lo validaba como formato argentino soportado.
- Corrección final: `formatearFecha` soporta explícitamente `DD/MM/AAAA`,
  `YYYY-MM-DD`, ISO datetime y `Date` válido. Strings vacíos devuelven vacío.
  Fechas con forma válida pero calendario inválido, como `31/02/2026` o
  `2026-02-31`, se conservan sin normalizarlas silenciosamente.
- Documentación agregada: `AGENTS.md`, `docs/agents/testing.md` y
  `CONTRIBUTING.md` dejan la regla permanente de fechas argentinas.
- Test agregado: `frontend/src/composables/useFormatters.spec.ts`.

## Lecciones para próximos agentes

- No fijar versión de Clawpatch en comandos ni scripts. Usar la CLI global
  disponible y dejar que el proyecto controle solo `--state-dir` y `--config`.
- Empezar auditorías Clawpatch con `status`, `map`, `review --limit <n>` y
  `report`. Si se corrige código, revalidar con el mismo state dir/config.
- `clawpatch revalidate --finding <id> --include-dirty` puede no seleccionar
  findings duplicados o de otro nivel de feature aunque `show` los liste. En ese
  caso, usar una revalidación acotada por abiertos (`--all --status open
  --include-dirty --limit <n>`) y solo hacer `triage --status fixed` manual si
  el duplicado exacto ya fue revalidado como fixed, dejando nota.
- Los hallazgos de Clawpatch y `autoreview` son asesoramiento. Clasificar cada
  finding antes de reparar: aceptar, rechazar o diferir. No aplicar fixes
  automáticos.
- Después de que `autoreview` encuentre un defecto real y se cambie código,
  repetir validaciones enfocadas y volver a correr `autoreview` sobre el commit
  final.
- En Windows, las operaciones Git de escritura y algunas lecturas del repo
  pueden requerir permiso elevado por ACL del sandbox.
- Para verificar CI remoto, usar `gh run list` y `gh run view` sobre el SHA
  esperado. Confirmar jobs, no solo conclusión general.
- En flujos con fechas, recordar que FactuFlow es una aplicación argentina: la
  UI debe usar `DD/MM/AAAA`, pero los contratos técnicos pueden seguir usando
  `YYYY-MM-DD`, ISO datetime o `CbteFch` `YYYYMMDD` según corresponda.

## Validaciones ejecutadas durante el ciclo

- Backend según los commits tocados: tests/lint/formato focalizados y CI remoto.
- Frontend: `npm run lint:check`, `npm run type-check`, `npm run test:unit`,
  tests enfocados de `pdf.service.spec.ts` y `useFormatters.spec.ts`.
- Clawpatch: `status`, `map-all`, `revalidate` y `status` final en repo,
  backend y frontend.
- Autoreview: Codex/GPT-5.5 con `--thinking high` sobre cada commit relevante.
- GitHub Actions: run remoto `28754521857` para `ebc176d` en `success`.

## Estado posterior

La auditoría Clawpatch queda cerrada para el estado actual. El siguiente trabajo
de producto vuelve al roadmap operativo post-piloto: observabilidad, backups,
trazabilidad, almacenamiento mínimo en VPS y mejoras operativas planificadas.
