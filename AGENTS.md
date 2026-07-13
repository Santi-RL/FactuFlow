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
- Después de cambios importantes en producto, UX, flujos core o ARCA, actualizar siempre:
  - `VISION.md` solo si el usuario pidió explícitamente cambiar la visión
  - `ROADMAP.md`
  - `docs/agents/current-status.md`
  - `docs/agents/manual-qa.md`
  - `docs/user-guide/README.md`
- Si el cambio impacta ARCA o homologación, actualizar también:
  - `docs/agents/arca.md`
  - `docs/arca-ws/NOTAS.md`
- `docs/user-guide/README.md` debe mantenerse al día cada vez que cambien pantallas, textos, pasos de uso o limitaciones funcionales visibles para usuarios.
- `docs/arca-ws/_extracted/` es material derivado. Si vuelve a generarse localmente, no tomarlo como fuente canónica.

## Git / Colaboración
- Rama de trabajo por defecto: `main`. No crear ramas nuevas salvo pedido
  explícito del usuario.
- Antes de empezar un cambio, revisar `git status --short --branch` y, si hace
  falta, comparar con `origin/main`. Si hay commits locales sin publicar o
  cambios listos de una implementacion anterior, avisar y recomendar cerrar ese
  ciclo con commit/push antes de acumular trabajo nuevo.
- Mantener cada implementacion relevante en su propio commit. Para ajustes
  chicos, bugs relacionados o correcciones de una misma verificacion, se puede
  agrupar un commit único si mantiene una unidad lógica clara.
- Después de implementar y verificar un cambio, recomendar commit y push para
  mantener `main` local y GitHub sincronizados.
- No ejecutar `git push` sin pedido explícito del usuario. Si hay cambios listos
  para publicar, preparar commit(s) y pedir confirmación antes de pushear.
- Preferir PRs para cambios no triviales cuando el usuario lo pida. En el flujo
  habitual sobre `main`, minimizar commits de ruido (formato/lint) y agruparlos
  con el cambio funcional correspondiente.
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
- Elegir el momento de la sugerencia según costo y precisión:
  - Para cambios pequeños pero sensibles, proponer `autoreview` inmediatamente después de implementar y antes de seguir acumulando trabajo, para que la revisión sea rápida, concreta y accionable.
  - Para varios cambios relacionados dentro de una misma unidad lógica, puede convenir terminar el lote coherente, ejecutar tests/lint/formato y luego proponer un único `autoreview` sobre todo el diff.
  - Si el diff empieza a mezclar temas independientes, sugerir cortar en commits o revisiones separadas para optimizar tiempo, tokens y calidad de hallazgos.
  - Antes de commit/PR de cambios no triviales, recordar la opción de `autoreview` si todavía no se ejecutó en ese ciclo.
- Antes de correr `autoreview`, ejecutar tests/lint/formato relevantes siempre que sea razonable. Después, revisar el diff real y verificar manualmente cada finding antes de aplicar fixes. Si se aceptan fixes que cambian código, repetir las pruebas enfocadas y volver a correr `autoreview` hasta que no queden hallazgos aceptados/accionables o hasta que el usuario decida detener el ciclo.
- Para cambios sensibles confirmados por el usuario, ejecutar directamente la
  revisión final con Codex `gpt-5.5` y `high`, y registrar el modelo realmente
  utilizado. No intentar previamente `gpt-5.6-sol` salvo que el usuario cambie
  explícitamente esta preferencia.
- No ejecutar automáticamente una escalera `low -> medium -> high` para un fix
  pequeño ya cubierto por tests. Reservar una revisión temprana adicional para
  diseños amplios, inciertos o que cambien contratos. Si una pasada encuentra
  hallazgos aceptados y se cambia código, repetir tests enfocados y volver a
  correr la revisión final.
- Los hallazgos de `autoreview` son asesoramiento, no órdenes. Para cada
  finding, clasificar explícitamente si se acepta, se rechaza o se difiere. Solo
  corregirlo si representa un riesgo real, una regresión, un contrato roto, un
  caso fiscal inseguro o una mejora necesaria dentro del alcance. Rechazar
  hallazgos especulativos, cambios sobredimensionados o refactors que no
  reduzcan un riesgo concreto.
- Autorización permanente del usuario para este proyecto: cuando el usuario pida o confirme ejecutar `autoreview`, queda permitido usar el motor Codex/OpenAI, enviarle el diff local necesario para la revisión y mantener habilitada la búsqueda web del helper. Esta autorización no habilita ejecutar `autoreview` sin pedido o confirmación explícita del usuario.
- En Windows, si `autoreview` falla con `PermissionError: [WinError 5] Acceso denegado` al invocar `codex`, no usar el shim `codex` del PATH ni el binario de `WindowsApps`. Ejecutar el helper apuntando al binario local de la app:
  `python C:\Users\SANTI\.codex\skills\autoreview\scripts\autoreview --mode local --codex-bin "C:\Users\SANTI\AppData\Local\OpenAI\Codex\bin\codex.exe"`.
  Ese comando ya funcionó en FactuFlow con motor `codex`, herramientas de solo lectura y búsqueda web habilitada.
- Elegir el modo de `autoreview` según el estado real: `--mode local` para diff
  sin commit, `--mode commit --commit HEAD` para un commit ya creado y
  `--mode branch --base <base>` para varios commits. Un `main` limpio después
  del push no se revisa con `--mode local` porque ese modo no tendría diff.
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
