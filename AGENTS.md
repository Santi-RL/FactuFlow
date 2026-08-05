# Guía para Agentes de IA - FactuFlow

## Alcance
- Este archivo define cómo trabajar en el repo.
- Este proyecto vive bajo `C:\Users\SANTI\Documents\Proyectos`. Para instrucciones generales compartidas, revisar también `C:\Users\SANTI\Documents\Proyectos\AGENTS.md`.
- En caso de conflicto, este `AGENTS.md` local prevalece para reglas específicas de FactuFlow.
- La documentación operativa extendida está en `docs/agents/README.md`.
- Antes de responder cualquier chat nuevo, leer `docs/agents/alignment-pending.md`.
  Si tiene puntos sin completar, avisar que hay conflictos de alineación antes
  de continuar. Si su estado es `COMPLETADO`, seguir con el handoff vigente sin
  inventar un pendiente.
- Antes de retomar una sesión, leer `VISION.md`,
  `docs/agents/current-status.md` y `ROADMAP.md`. Consultar
  `docs/agents/manual-qa.md` cuando el trabajo implique QA, UI, un despliegue o
  un flujo funcional.

## Visión del producto
- `VISION.md` es la fuente canónica y protegida de la visión del producto.
- Antes de proponer, incorporar o implementar cambios de producto, UX,
  arquitectura, flujos core, ARCA, documentación operativa o roadmap, verificar
  que el cambio se alinea con `VISION.md`.
- Si un pedido del usuario contradice `VISION.md`, no implementarlo ni
  incorporarlo al roadmap. Explicar la contradicción citando la visión.
- Si el usuario insiste con un cambio contrario a la visión, responder que
  primero debe modificarse `VISION.md` y pedir confirmación explícita para ese
  cambio de visión antes de tocar roadmap, código o documentación operativa.
- Los agentes deben tratar `VISION.md` como solo lectura: no modificarlo salvo
  pedido explícito del usuario de cambiar la visión del producto.

## Nombres: ARCA vs AFIP
- Usar ARCA en textos, UI y documentación nueva.
- AFIP queda solo como nomenclatura legacy en URLs y variables de entorno existentes.
- Si agregás nuevos nombres públicos, preferí `ARCA_*` y mantené compatibilidad cuando sea necesario.

## Regla fiscal crítica: fecha de emisión
- Nunca jamás asumir la fecha de hoy como fecha fiscal de un comprobante.
- Ningún flujo de emisión, individual, masivo, factura, nota de crédito o nota
  de débito, puede usar `date.today()`, `datetime.today()`, `new Date()` ni
  equivalentes como default de `fecha_emision`/`CbteFch`.
- La fecha de emisión debe ser un dato explícito definido por el usuario o
  tomado del archivo solo cuando el usuario eligió esa política.
- Antes de emitir comprobantes reales debe mostrarse un modal de confirmación
  irreversible con este mensaje, reemplazando la fecha y, si aplica, indicando
  el punto de venta:
  `Está seguro que quiere emitir comprobantes con fecha XX/XX/XX? Recuerde que luego no podrá emitir comprobantes con fecha anterior para ese mismo punto de venta.`
- Si se agrega o modifica cualquier camino que pueda solicitar CAE a ARCA, hay
  que verificar esta regla en UI, API, servicios, tests y documentación antes de
  darlo por terminado.

## Formato de fechas argentino
- En UI, mensajes, documentación para usuarios, confirmaciones fiscales y PDFs,
  las fechas visibles deben mostrarse en formato argentino `DD/MM/AAAA`, salvo
  que una integración externa exija explícitamente otro formato técnico.
- Cuando el código acepte fechas como `string`, debe soportar y validar
  explícitamente `DD/MM/AAAA` para entradas argentinas y `YYYY-MM-DD` / ISO
  datetime para contratos técnicos de API/backend. No usar `new Date(string)` ni
  `Date.parse` sobre strings de usuario o strings ambiguos.
- Una fecha con forma válida pero calendario inválido, como `31/02/2026`, no
  debe normalizarse ni convertirse silenciosamente a otra fecha. Debe rechazarse
  o conservarse sin inventar una fecha, según el contrato del helper o flujo.
- Para ARCA, base de datos, payloads API y archivos técnicos, mantener los
  formatos requeridos por cada contrato (`YYYY-MM-DD`, ISO datetime o `CbteFch`
  `YYYYMMDD`) y convertirlos en los bordes hacia/desde `DD/MM/AAAA`.
- Los tests que toquen fechas deben cubrir al menos: `DD/MM/AAAA` válido,
  `YYYY-MM-DD` válido, fecha calendario inválida, string vacío y el caso de zona
  horaria si se parsean ISO datetime.

## Diseño fiscal crítico
- FactuFlow debe priorizar solidez, seguridad y confiabilidad fiscal. Un error
  en emisión, numeración, CAE, fechas fiscales, puntos de venta, comprobantes
  asociados, receptor, total, idempotencia, reconciliación o multiemisor puede
  generar comprobantes incorrectos con consecuencias impositivas y legales.
- Antes de implementar una nueva funcionalidad, corrección o mejora que toque
  ARCA/WSAA/WSFE, emisión individual, emisión masiva, reintentos,
  reconciliación, numeración, CAE, migraciones fiscales, puntos de venta,
  certificados, comprobantes, notas de crédito/débito, datos fiscales,
  confirmaciones irreversibles o aislamiento por emisor, completar primero el
  checklist de diseño fiscal: `docs/agents/fiscal-change-checklist.md`.
- El diseño debe bajar a invariantes verificables, tabla de estados, orden de
  operaciones, fallos intermedios, concurrencia, rollback/reconciliación,
  migraciones y matriz de tests. No alcanza con describir el flujo feliz.
- Para cambios fiscales críticos, definir los tests antes o durante el diseño.
  Cada invariante relevante debe tener una prueba automatizada o una razón
  explícita para no cubrirla. Los tests deben incluir errores, carreras,
  replays, datos legacy, cambios de payload y estados inciertos.
- Evitar implementar un cambio fiscal grande como un único diff amplio. Cuando
  sea posible, dividir en cortes verticales revisables: modelo/migración,
  servicio, API, UI, docs y tests. Cerrar cada corte sensible antes de acumular
  otro.
- Aplicar desde el diseño la misma disciplina que exige `autoreview`: revisar
  rutas vecinas, contratos externos, casos límite, clases de bug repetidas y
  ownership correcto. No esperar al final para descubrir invariantes faltantes.
- Si se modifica un servicio, helper o contrato compartido, enumerar todos sus
  consumidores directos e indirectos —API, UI, worker, lotes, reintentos,
  reconciliación y scripts— y revisar para cada uno comportamiento, tests y
  documentación. El nombre conceptual del método no limita su impacto real.

## Mapa rápido
- `backend/app/main.py`: entrada FastAPI y registro de routers.
- `backend/app/api/*.py`: endpoints (health, auth, empresas, clientes, puntos_venta, certificados, arca, comprobantes, pdf, reportes).
- `backend/app/arca/`: integración ARCA (wsaa, wsfev1, crypto, config, cache, utils).
- `backend/app/core/config.py`: settings y variables de entorno.
- `backend/app/models/`, `backend/app/schemas/`, `backend/app/services/`.
- `backend/tests/`: tests (incluye `test_arca/`).
- `frontend/src/main.ts`, `frontend/src/router/index.ts`.
- `frontend/src/views/`: vistas por dominio.
- `frontend/src/components/ui/`: componentes base `Base*.vue`.
- `docs/`: documentación del proyecto.

## Convenciones
- Python: PEP8, `black` (88). En código nuevo o modificado, type hints y
  docstrings en español son obligatorios para funciones, clases y helpers
  públicos. El código histórico se normaliza cuando se toca o en tareas
  técnicas dedicadas.
- Los archivos Python se versionan con saltos de línea LF mediante
  `.gitattributes` (`*.py text eol=lf`, `*.pyi text eol=lf`). Si en Windows
  `black --check` vuelve a colgarse sin errores de formato, revisar/limpiar el
  cache local de Black antes de diagnosticar deuda de formato.
- FastAPI: imports absolutos desde `app/`.
- Vue: Composition API con `<script setup>`, TypeScript recomendado, componentes en PascalCase, events en kebab-case.
- Tailwind: priorizar utilidades sobre CSS custom.
- UI y mensajes para usuarios en español (Argentina).
- Los tests deben ser portables entre Windows local y GitHub Actions en Linux.
  No comparar paths como strings con separadores fijos (`\` o `/`). Para asserts
  de rutas usar `pathlib.Path`, `Path.parts`, `Path.name`, `Path.parent`,
  `os.path.normpath` o comparaciones equivalentes independientes del sistema
  operativo. Si un fallo de CI viene de diferencias Windows/Linux, corregir el
  test o helper para expresar la intención real, no forzar el formato local.

## Continuidad y documentación viva
- Si el usuario pregunta "cómo está el proyecto" o "qué es lo primero que
  debemos solucionar", revisar primero `docs/agents/alignment-pending.md`. Si
  no tiene pendientes, responder desde `docs/agents/current-status.md > Punto
  exacto para retomar` y contrastar `ROADMAP.md > Prioridades inmediatas`.
- Si el usuario dice "seguir donde quedamos", arrancar por
  `docs/agents/current-status.md` y `ROADMAP.md`. Consultar
  `docs/agents/manual-qa.md` solo si el siguiente trabajo necesita QA.
- Después de cambios importantes en producto, UX, flujos core o ARCA, revisar
  siempre el corpus documental aplicable. Como mínimo:
  - `VISION.md` solo si el usuario pidió explícitamente cambiar la visión;
  - `README.md` cuando cambien capacidades, versión publicada o estado
    productivo;
  - `CHANGELOG.md > Unreleased` para todo cambio aceptado todavía no incluido
    en una release;
  - `ROADMAP.md`;
  - `docs/agents/current-status.md`;
  - `docs/agents/development-portfolio.md` cuando cambie el avance de una línea
    PF;
  - `docs/agents/overview.md` cuando cambien las capacidades aceptadas en
    `main`, el próximo paso o la arquitectura;
  - `docs/agents/testing.md` cuando cambien matrices, conteos, suites, CI o
    evidencia de validación, aunque los comandos permanezcan iguales;
  - `docs/agents/manual-qa.md`;
  - `docs/user-guide/README.md`;
  - `docs/api/README.md` cuando cambie la conducta documentada de un endpoint o
    servicio, aunque rutas, schemas y status HTTP permanezcan iguales;
  - el diseño del corte, `docs/setup/**`, índices o dossiers cuando sus
    afirmaciones hayan cambiado.
- Si el cambio impacta ARCA o homologación, actualizar también:
  - `docs/agents/arca.md`
  - `docs/arca-ws/NOTAS.md`
- `docs/user-guide/README.md` debe mantenerse al día cada vez que cambien pantallas, textos, pasos de uso o limitaciones funcionales visibles para usuarios.
- `docs/arca-ws/_extracted/` es material derivado. Si vuelve a generarse localmente, no tomarlo como fuente canónica.

### Puerta obligatoria de alineación documental

- Ejecutar esta puerta después de estabilizar código y tests, pero antes de
  `autoreview`, `git add` y el commit. Tocar un archivo no demuestra que quedó
  actualizado: hay que releer completas las secciones afectadas y contrastarlas
  con código, tests, estado Git, versión publicada y versión productiva.
- La documentación incluida en una rama debe describir el estado objetivo que
  tendrá `main` al integrar el PR. No dejar en documentos canónicos nombres de
  ramas temporales, "implementación local", "primer corte local", "publicado
  para revisión" ni otros estados efímeros. Ese contexto pertenece al cuerpo
  del PR. Los hechos que solo existen después, como un despliegue real, se
  registran mediante un cierre documental posterior explícito.
- Distinguir siempre tres estados: código aceptado en `main`, última release
  publicada y versión realmente desplegada. No presentar una capacidad de
  `main` como disponible en producción si todavía no pertenece al tag
  desplegado.
- Actualizar fechas, encabezados de estado, enlaces de índices y diseños cuando
  corresponda. Las menciones históricas deliberadas deben quedar rotuladas como
  tales; no reescribir evidencia histórica para simular actualidad.
- Antes de marcar un PR como listo, revisar nuevamente el rango completo contra
  su base y completar la matriz documental de
  `.github/pull_request_template.md` con archivos concretos o un `No aplica`
  justificado. Si el PR se crea por API o con un cuerpo personalizado, debe
  conservar esa misma evidencia; no omitirla por no usar la plantilla visual.
- Después del merge, verificar en modo lectura que `main` no conserve estados
  transitorios y que los documentos canónicos indiquen el siguiente paso real.
  No cerrar el ciclo ni eliminar la rama hasta completar esa comprobación.

## Git / Colaboración
- `main` es la única rama permanente y la fuente canónica del código aceptado.
- Cada unidad nueva se implementa en una rama temporal corta creada desde
  `main` sincronizada. Por defecto mantener una sola rama interna activa; no
  abrir líneas paralelas salvo decisión explícita del usuario.
- La rama temporal sirve para aislar implementación, pruebas y PR. No es una
  versión, no se despliega y debe mergearse a `main` cuando los checks estén
  verdes y los riesgos aceptados. Después del merge, verificar `main` y eliminar
  la rama local y remota.
- Los cambios Nivel 0 siguen un recorrido abreviado en CI y pueden agruparse si
  forman una unidad documental coherente. Los cambios Nivel 1/2 conservan las
  puertas indicadas en `docs/agents/change-quality-gates.md`.
- Antes de empezar un cambio, revisar `git status --short --branch` y comparar
  con `origin/main`. Si hay commits sin publicar, una rama anterior abierta o
  cambios de otra implementación, avisar y cerrar ese ciclo antes de acumular
  trabajo nuevo.
- Mantener cada implementación relevante en su propio commit. Ajustes chicos,
  bugs relacionados o correcciones de una misma verificación pueden agruparse
  si conservan una unidad lógica clara.
- No ejecutar `git push`, merge ni eliminación remota sin pedido explícito del
  usuario. Si una rama está lista, preparar el commit y pedir confirmación antes
  de publicar; una autorización para completar el ciclo puede abarcar push, PR,
  merge y eliminación cuando el alcance haya quedado explícito.
- Para verificar CI en GitHub, usar el mecanismo moderno de GitHub Actions:
  `gh run list`, `gh run view` y check-runs. No consultar el endpoint legacy de
  commit statuses (`/commits/{sha}/status`) salvo que el usuario pida auditar
  una integración antigua que dependa específicamente de ese endpoint.
- Si `gh release` devuelve `403` aunque `gh auth status` muestre una sesión
  válida en el keyring, comprobar si un `GITHUB_TOKEN` de proceso está
  reemplazando esa sesión. No imprimir el token: quitarlo solo del proceso
  actual y reintentar con la credencial ya autenticada.
- En Codex con sandbox activo, los comandos que escriben en `.git` pueden fallar
  con `Unable to create .git/index.lock: Permission denied` si se ejecutan sin
  permiso elevado. Para preparar commits o publicar, usar directamente permisos
  elevados en comandos de escritura Git (`git add`, `git commit`, `git push`) con
  justificacion breve. Los comandos de lectura (`git status`, `git diff`,
  `git log`) pueden ejecutarse normalmente salvo que el entorno los bloquee.
- En este workspace de Windows, el sandbox de Codex falla de forma recurrente
  incluso en comandos de lectura con `helper_unknown_error` y errores de ACL.
  Para comandos cuyo `workdir` esté dentro de
  `C:\Users\SANTI\Documents\Proyectos\FactuFlow` y que solo lean, modifiquen o
  validen archivos del repositorio, usar `require_escalated` desde el primer
  intento cuando sea previsible ese mismo fallo. Esto incluye búsquedas,
  lecturas, tests, lint, formato, builds, Clawpatch, `autoreview` y operaciones
  Git permitidas por el flujo vigente. No hacer primero un intento dentro del
  sandbox si ya se confirmó esa limitación en la sesión.
- Esta autorización queda limitada al workspace de FactuFlow. No habilita
  borrados destructivos, `git reset --hard`, reversión de trabajo ajeno, acceso
  o escritura fuera del proyecto, exposición de secretos o datos privados,
  despliegues ni `git push` sin el pedido correspondiente. `apply_patch` no
  admite elevación: si falla por la ACL conocida, no repetirlo y usar de
  inmediato un reemplazo exacto y verificado con permisos elevados.

## Producción, despliegue y auditoría
- El flujo productivo recomendado está documentado en
  `docs/agents/production-workflow.md`.
- `git push` no significa despliegue. La instalación productiva en VPS se
  actualiza solo con decisión explícita del usuario y contra un commit o tag
  identificable.
- El desarrollo y los fixes se hacen en local; GitHub conserva el código
  público; el VPS conserva estado operativo, base, certificados, logs y
  configuración privada.
- No hacer cambios permanentes de código directamente en el VPS. Si se detecta
  un fix urgente en producción, llevarlo al repo local, probarlo, commitearlo y
  desplegarlo de forma controlada.
- Ante errores productivos de emisión o lotes, auditar primero el VPS en modo
  solo lectura: base, logs, intentos fiscales, idempotencia y, si corresponde,
  consultas ARCA seguras como `FECompUltimoAutorizado` o `FECompConsultar`.
- Nunca reintentar automáticamente una emisión fallida sin determinar antes si
  ARCA autorizó o no el comprobante.
- Los detalles concretos de la instalación real, como IP, dominio, usuario SSH,
  rutas, comandos del host, backups, certificados, CAEs, CUITs y logs, deben
  quedar en documentación privada del VPS, no en este repositorio público.

## Comandos
### Raíz
```bash
npm run lint
npm run test
npm run backend:format:check
```

Los scripts raíz `lint` y `test` son agregadores backend + frontend. El check de
formato backend queda scopiado como `backend:format:check`; en frontend,
`npm run format` es un comando de escritura y debe ejecutarse desde
`frontend/` solo cuando se quiere aplicar formato.

### Backend
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
pytest
ruff check app/ tests/
black --check app/ tests/
```

### Frontend
```bash
cd frontend
npm install
npm run dev
npm run test
npm run test:unit
npm run test:e2e
npm run lint:check
npm run lint
npm run format
npm run type-check
```

## Seguridad y certificados
- No commitear certificados ni claves privadas.
- Usar `certs/` y `data/` (gitignored).
- No commitear datos privados: CUITs reales, nombres de clientes o emisores,
  credenciales, tokens, CAEs reales, capturas privadas, PDFs, Excel de clientes,
  bases locales, logs ni evidencia de debug.
- Mantener separado el proyecto público del entorno privado. Los archivos
  locales de prueba, QA, producción, debug o evidencia deben ir a carpetas
  ignoradas como `.tmp/`, `private/`, `evidence/`, `output/`, `data/`,
  `backend/data/` o `certs/`.
- Antes de commitear, revisar `git status --short --untracked-files=all` y el
  diff staged para confirmar que no se sube material privado.
- Ver detalles en `docs/agents/security.md`.

## Revisión de código y seguridad
- Usar `security-best-practices` si el usuario pide revisión de seguridad o si se cambian autenticación, certificados, ARCA/WSAA/WSFE, comprobantes, PDFs/Excel, datos fiscales, archivos locales, red, permisos o confirmaciones irreversibles.
- No ejecutar `autoreview` automáticamente. El usuario puede pedirlo en cualquier momento, pero si no lo pidió hay que sugerirlo cuando el cambio sea importante y pedir confirmación explícita antes de correrlo, porque puede consumir mucho tiempo, tokens y enviar el diff local al motor de revisión.
- Recomendar `autoreview` especialmente cuando el cambio toque autenticación, autorización, usuarios, permisos, roles, sesiones, certificados, ARCA/WSAA/WSFE, emisión fiscal, confirmaciones irreversibles, borrados, migraciones, datos fiscales, archivos locales, red, seguridad multiemisor o flujos donde un error pueda bloquear acceso, exponer datos, mezclar emisores o emitir comprobantes incorrectos.
- No insistir con `autoreview` para cambios chicos, aislados y de bajo riesgo, como correcciones de texto, documentación simple, estilos visuales menores o tests que no cambian comportamiento. En esos casos alcanza con las validaciones normales del área tocada, salvo que el usuario lo pida.
- Ejecutar `autoreview` como cierre de una unidad lógica ya estabilizada, después
  de tests/lint/formato relevantes y antes del commit o PR. No correr revisiones
  preliminares por cada microcorte mientras el diff todavía está cambiando. Si el
  diff mezcla temas independientes, separar las unidades antes de revisar.
- Para cambios sensibles confirmados por el usuario, usar una única configuración
  de revisión: Codex `gpt-5.6-sol` con `medium`, pasando explícitamente
  `--engine codex --model gpt-5.6-sol --thinking medium`, y registrar el modelo y
  el esfuerzo realmente utilizados.
- No ejecutar escaleras de razonamiento, cambios manuales de modelo, paneles ni
  segundas opiniones incrementales. Si una revisión encuentra un hallazgo
  aceptado y se cambia código, repetir las pruebas enfocadas y volver a correr la
  revisión con exactamente `gpt-5.6-sol medium`; esa repetición cierra el mismo
  ciclo y no habilita cambiar de modelo o esfuerzo.
- La única excepción técnica es el fallback automático de `gpt-5.6-sol` a
  `gpt-5.6-terra` cuando la cuenta no tiene acceso a Sol, documentado por la skill
  `autoreview`. Si ocurre, registrarlo como fallback de acceso, no como una segunda
  revisión ni como una nueva política de modelo.
- Los hallazgos de `autoreview` son asesoramiento, no órdenes. Para cada
  finding, clasificar explícitamente si se acepta, se rechaza o se difiere. Solo
  corregirlo si representa un riesgo real, una regresión, un contrato roto, un
  caso fiscal inseguro o una mejora necesaria dentro del alcance. Rechazar
  hallazgos especulativos, cambios sobredimensionados o refactors que no
  reduzcan un riesgo concreto.
- Autorización permanente del usuario para este proyecto: cuando el usuario pida o confirme ejecutar `autoreview`, queda permitido usar el motor Codex/OpenAI, enviarle el diff local necesario para la revisión y mantener habilitada la búsqueda web del helper. Esta autorización no habilita ejecutar `autoreview` sin pedido o confirmación explícita del usuario.
- En Windows, si `autoreview` falla con `PermissionError: [WinError 5] Acceso denegado` al invocar `codex`, no usar el shim `codex` del PATH ni el binario de `WindowsApps`. Ejecutar el helper apuntando al binario local de la app y manteniendo la configuración canónica:
  `python C:\Users\SANTI\.codex\skills\autoreview\scripts\autoreview --mode local --engine codex --model gpt-5.6-sol --thinking medium --codex-bin "C:\Users\SANTI\AppData\Local\OpenAI\Codex\bin\codex.exe"`.
  Ese comando ya funcionó en FactuFlow con motor `codex`, herramientas de solo lectura y búsqueda web habilitada.
- Elegir el modo de `autoreview` según el estado real: `--mode local` para diff
  sin commit, `--mode commit --commit HEAD` para un commit ya creado y
  `--mode branch --base <base>` para varios commits. Un `main` limpio después
  del push no se revisa con `--mode local` porque ese modo no tendría diff.
- Por defecto, en trabajo nuevo de FactuFlow ejecutar `autoreview --mode local`
  después de las validaciones y antes del commit. No crear un commit únicamente
  para poder revisarlo ni repetir en modo `commit` un diff local que ya fue
  revisado sin cambios. Si la revisión provoca modificaciones, repetir las
  pruebas enfocadas y la misma revisión antes de commitear. Reservar
  `--mode commit --commit HEAD` para un commit que ya existe por una razón real
  y `--mode branch --base <base>` para el resultado acumulado de varios commits
  o de un PR.
- Antes de ejecutar cualquier comando de Clawpatch, leer completo y seguir
  `docs/project/audits/clawpatch/README.md`. Esa guía es el runbook operativo
  vigente; los documentos fechados son evidencia histórica y no reemplazan el
  estado actual ni el triage contra el código presente.
- Usar la CLI global `clawpatch` (`C:\Users\SANTI\AppData\Roaming\npm\clawpatch.cmd`) para auditorías/backlog de mantenimiento de FactuFlow, no para fixes rápidos ni cambios solo documentales. Seguir también la política compartida de `C:\Users\SANTI\Documents\Proyectos\AGENTS.md`. En este repo ya existen estados separados; preferir los scripts npm `clawpatch:<slice>:...` porque pasan `--root`, `--state-dir` y `--config` de forma coherente. Si se usa CLI directa, no alcanza con elegir `--state-dir`: pasar siempre el `--root` correspondiente.
  - Repo completo: `npm run clawpatch:repo:status` o `clawpatch --root . --state-dir .clawpatch/repo --config .clawpatch/repo/config.json status`
  - Backend: `npm run clawpatch:backend:status` o `clawpatch --root backend --state-dir ../.clawpatch/backend --config ../.clawpatch/backend/config.json status`
  - Frontend: `npm run clawpatch:frontend:status` o `clawpatch --root frontend --state-dir ../.clawpatch/frontend --config ../.clawpatch/frontend/config.json status`
- Mantener el mismo `--root`, `--state-dir` y `--config` durante cada ciclo.
  Ejecutar en etapas: preflight y `doctor`; tests de seeds; `map-all`; `status`;
  `dry-run`; review de `repo`; reporte y triage; backend en lotes; frontend; y
  consolidación final. No lanzar reviews de distintos slices en paralelo. En
  Windows usar `--jobs 1` y checkpoints entre lotes de hasta 50 features.
- Para reviews y revalidaciones nuevas, pasar explícitamente el modelo
  `gpt-5.6-sol` con `--reasoning-effort high` y registrar el modelo real. Si el modelo
  preferido no puede ejecutarse después de un reintento razonable, usar
  `gpt-5.5` con `high`. No depender silenciosamente del modelo predeterminado de
  Codex.
- Guardar reportes crudos y evidencia detallada solo en `.tmp/clawpatch/` u otra
  ruta ignorada. Para automatización usar `report --json` y leer `items`; el
  contador acumulado no representa bugs aceptados hasta verificar y triar cada
  finding contra el código actual.
- No crear otro `.clawpatch/` default, ejecutar `clawpatch init` ni limpiar o
  reconstruir un state dir sin decisión explícita. Antes de reconstruir,
  archivar el ledger en una ruta ignorada, generar inventario y SHA-256, y
  verificar el archivo antes de retirar el estado activo.
- `clawpatch fix --finding <id>` requiere worktree limpio, confirmación
  explícita y validaciones enfocadas. Usarlo solo para findings aceptados,
  localizados y de bajo riesgo relativo; para ARCA/CAE, fechas fiscales,
  idempotencia, reconciliación, lotes, migraciones, borrados, certificados, PDFs
  fiscales, reportes impositivos o aislamiento multiemisor, reparar manualmente
  con diseño, tests y revalidación posterior.
- Durante cada ciclo, incorporar en el runbook los aprendizajes operativos
  confirmados que mejoren seguridad, reproducibilidad, costo o interpretación.
  Actualizar `AGENTS.md` solo cuando el aprendizaje sea una regla obligatoria o
  una frontera de autorización; dejar procedimientos, comandos y workarounds en
  el runbook. No documentar como regla un workaround no verificado y nunca
  versionar secretos, evidencia privada ni findings crudos.
- La cadencia de reparación, interpretación de reportes acumulativos y cierre
  2026-07-10 están documentados en el runbook y en
  `docs/project/audits/clawpatch/2026-07-10-cierre-ciclo-v0.2.1.md`.

## Documentación operativa
- Visión canónica del producto: `VISION.md`
- Índice: `docs/agents/README.md`
- Pendientes temporales de alineación: `docs/agents/alignment-pending.md`
- Estado actual: `docs/agents/current-status.md`
- QA manual: `docs/agents/manual-qa.md`
- Resumen y arquitectura: `docs/agents/overview.md`
- Estructura del repo: `docs/agents/structure.md`
- ARCA y endpoints: `docs/agents/arca.md`
- Checklist de diseño fiscal crítico:
  `docs/agents/fiscal-change-checklist.md`
- Flujo de desarrollo, despliegue y auditoría productiva:
  `docs/agents/production-workflow.md`
- Documentación oficial ARCA WS: `https://www.arca.gob.ar/ws/` (índice y descargas locales en `docs/arca-ws/README.md`)
- Testing: `docs/agents/testing.md`
- Seguridad: `docs/agents/security.md`
- Manual de usuario: `docs/user-guide/README.md`
- Bitácora técnica histórica: `docs/project/notes/SESSION_2026-03-09.md`
- Cierre Clawpatch/v0.2.1:
  `docs/project/audits/clawpatch/2026-07-10-cierre-ciclo-v0.2.1.md`
- Contribución y commits: `CONTRIBUTING.md`
