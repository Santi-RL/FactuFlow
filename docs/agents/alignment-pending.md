# Revision temporal de alineacion del proyecto

Estado general: COMPLETADO

Última actualizacion: 2026-05-07

Este archivo fue temporal y ordeno los conflictos detectados entre las
instrucciones del proyecto, la documentación viva y la implementacion real.
Todos los puntos quedaron completados el 2026-05-07. Se conserva como registro
de cierre; si se elimina en el futuro, reflejar esa decisión en `AGENTS.md`.

Nota 2026-05-22: este archivo es histórico. Algunos cierres mencionan el punto
de reanudacion vigente al 2026-05-07, antes de la operación productiva real
posterior. Para estado actual usar `docs/agents/current-status.md`,
`ROADMAP.md` y `CHANGELOG.md`.

## Uso obligatorio para agentes

- Al iniciar cualquier chat nuevo, leer este archivo después de `AGENTS.md`.
- Si existe al menos un punto sin completar, avisar al usuario que hay pendientes
  de alineacion antes de responder el pedido, aunque el pedido sea de otro tema.
- Si el usuario pregunta "como esta el proyecto", "que es lo primero que debemos
  solucionar" o una variante equivalente, responder directamente con el primer
  punto pendiente de esta lista y proponer avanzar sobre ese punto.
- Al resolver un punto, cambiar su estado a `[x] Completado`, agregar una nota
  breve de cierre y mantener la numeración estable.
- No reordenar los puntos ya existentes salvo decisión explícita del usuario.

## Pendientes priorizados

### 1. [x] Completado - Proteger artefactos sensibles y temporales que hoy son stageables

**Problema:** Hay archivos runtime/QA sin trackear dentro de `backend/data/` y
`output/playwright/`, incluyendo cache de token ARCA, PDFs, XLSX y CSR. Las
instrucciones dicen que `data/` y certificados deben ser gitignored, pero la
regla actual no cubre `backend/data/**`, `output/**` ni caches JSON.

**Riesgo:** Se puede commitear material sensible o artefactos de pruebas reales.
También ensucia cualquier revision porque mezcla código con evidencia local.

**Posible solucion:** Ajustar `.gitignore` para cubrir `backend/data/**`,
`data/**`, `output/**`, `logs/**`, caches ARCA y artefactos de Playwright,
preservando `.gitkeep` cuando haga falta. Luego limpiar el working tree de
artefactos no versionables sin borrar evidencia que el usuario quiera conservar.

**Criterio de completado:** `git status --short --untracked-files=all` no debe
mostrar artefactos runtime/QA ni caches sensibles; solo código, docs y archivos
de configuración intencionales.

**Cierre:** Se actualizó `.gitignore` para ignorar `backend/data/`, `data/`,
`output/`, reportes/resultados Playwright y caches runtime. Los artefactos ARCA,
PDF/XLSX/CSR locales dejaron de aparecer como untracked versionables.

### 2. [x] Completado - Unificar el estado real de producción en la documentación viva

**Problema:** `docs/agents/current-status.md` y `ROADMAP.md` dicen que el
certificado productivo, la autorización `wsfe` y los puntos Web Services reales
ya quedaron verificados. En cambio `docs/agents/manual-qa.md`,
`docs/agents/overview.md` y `docs/user-guide/README.md` todavía dicen que falta
configurar certificado, autorización y punto de venta productivos.

**Riesgo:** Un agente o una persona puede retomar desde un paso equivocado y
repetir trabajo ya hecho, o peor, asumir que falta algo externo cuando solo falta
confirmar el punto de venta y ejecutar la primera prueba real controlada.

**Posible solucion:** Elegir una única verdad operativa. Con la evidencia actual,
parece razonable tomar como canon `docs/agents/current-status.md` y `ROADMAP.md`,
y actualizar los documentos rezagados para indicar que falta la primera prueba
real controlada, no la configuración productiva base.

**Criterio de completado:** Todos los documentos de continuidad coinciden en el
mismo punto de reanudacion productivo y no hay contradicciones sobre certificado,
autorización `wsfe` ni puntos de venta productivos.

**Cierre:** Se definio `docs/agents/current-status.md` como fuente canónica del
estado operativo. Se revalido por base local y por API segura contra ARCA
producción que el emisor real tiene certificado productivo activo, conexión ARCA
OK, puntos Web Services `6`, `8`, `10`, `12`, `13` y `14` disponibles, `7` y
`9` bloqueados, y último comprobante Factura B en punto `6` igual a `0`. Se
actualizaron `current-status.md`, `manual-qa.md`, `overview.md`,
`user-guide/README.md`, `agents/arca.md`, `agents/testing.md`, `ROADMAP.md` y
`agents/README.md` para que el punto de reanudacion sea la primera prueba real
controlada, no la configuración productiva desde cero.

### 3. [x] Completado - Actualizar la documentación de API REST al contrato real

**Problema:** `docs/api/README.md` documenta endpoints `/api/v1/...`, Swagger en
`/docs`, ReDoc en `/redoc`, rate limiting y rutas antiguas. El backend real
registra `/api/...`, expone Swagger en `/api/docs`, ReDoc en `/api/redoc`, y ya
tiene lotes, PDF real, reportes y endpoints nuevos.

**Riesgo:** La documentación pública induce a usar rutas inexistentes y afirma
capacidades no implementadas, como rate limiting.

**Posible solucion:** Reescribir `docs/api/README.md` desde el estado real de
`backend/app/main.py` y `backend/app/api/*.py`. Eliminar `/api/v1`, corregir
docs URLs, documentar lotes, PDF, empresa activa por `X-Empresa-Id` y quitar
rate limiting salvo que se implemente.

**Criterio de completado:** Los ejemplos de `docs/api/README.md` coinciden con
los routers reales y no mencionan capacidades inexistentes.

**Cierre:** Se reescribio `docs/api/README.md` contra `backend/app/main.py` y
`backend/app/api/*.py`. Ahora documenta Swagger en `/api/docs`, ReDoc en
`/api/redoc`, rutas reales bajo `/api`, `X-Empresa-Id`, lotes, PDF, reportes,
checks ARCA seguros y advierte que no hay rate limiting implementado ni
versionado HTTP en la URL.

### 4. [x] Completado - Resolver la doble estrategia de schema: Alembic vs `create_all`

**Problema:** El README y Docker usan `alembic upgrade head`, pero el backend
ejecuta `Base.metadata.create_all` al iniciar en desarrollo/testing. Además
`run-local.ps1` levanta `uvicorn` sin correr Alembic. Esto convive con una base
SQLite local legacy que ya se reconoce como no alineada limpiamente.

**Riesgo:** Nuevas instalaciones locales pueden quedar con schemas creados por
SQLAlchemy directo en vez de migraciones, ocultando problemas de Alembic y
prolongando la deuda de la DB legacy.

**Posible solucion:** Definir Alembic como único camino de schema para entornos
normales. Ajustar `run-local.ps1` para ejecutar `alembic upgrade head` antes de
levantar el backend. Dejar `create_all` solo para tests controlados si realmente
hace falta, o mover los tests a migraciones/fixtures explícitas.

**Criterio de completado:** El arranque local documentado y automatizado aplica
migraciones antes de servir la API, y queda documentado que SQLite legacy no es
la base canónica para operación real.

**Cierre:** Se ajusto `run-local.ps1` para ejecutar `alembic upgrade head`
antes de `uvicorn`. Se limito `Base.metadata.create_all` en `backend/app/main.py`
a entornos `test`/`testing`, dejando Alembic como camino normal para desarrollo
y producción. Se actualizó `current-status.md` y `testing.md` para aclarar que
la SQLite local es evidencia legacy, no fuente canónica de schema.

### 5. [x] Completado - Completar la documentación de estructura interna con módulos nuevos

**Problema:** Existen módulos nuevos importantes que no aparecen o aparecen de
forma incompleta en indices internos: `lotes_comprobantes`, `lote_worker`,
servicios de constancias, `backend/app/arca/soap.py`, script
`create_admin_user`, schemas/types de lotes y servicio frontend de lotes.

**Riesgo:** La documentación guia a agentes hacia una arquitectura anterior y
hace mas probable duplicar lógica o ubicar nuevos cambios en lugares incorrectos.

**Posible solucion:** Actualizar `docs/agents/structure.md`,
`backend/app/api/README.md`, `backend/app/services/README.md`,
`backend/app/models/README.md`, `frontend/src/services/README.md` y cualquier
README de vistas/componentes que haya quedado incompleto.

**Criterio de completado:** Los indices de estructura listan todos los módulos
core actuales y explican donde va cada cambio nuevo.

**Cierre:** Se actualizaron `docs/agents/structure.md`,
`backend/app/api/README.md`, `backend/app/services/README.md`,
`backend/app/models/README.md`, `frontend/src/services/README.md` y
`frontend/src/views/README.md` para incluir lotes, worker, constancias ARCA,
SOAP ARCA, script `create_admin_user`, snapshot fiscal y tipos/servicios
frontend de lotes.

### 6. [x] Completado - Limpiar nomenclatura pública AFIP restante y dejar solo legacy real

**Problema:** La regla del proyecto exige usar ARCA en UI, textos y
documentación nueva. Todavía quedan menciones conceptuales a AFIP en docstrings
y comentarios de backend, y una referencia visible `ARCA (ex-AFIP)` en el wizard
de certificados. Las URLs `afip.gob.ar` si son legacy válido.

**Riesgo:** El producto mantiene lenguaje mixto y contradice la regla de
nomenclatura, especialmente en textos visibles para usuario.

**Posible solucion:** Reemplazar menciones conceptuales por ARCA. Mantener AFIP
solo en URLs oficiales, variables legacy `AFIP_*`, carpeta `backend/app/afip/`
documentada como compatibilidad y notas técnicas que expliquen endpoints legacy.

**Criterio de completado:** `rg -n "AFIP|Afip|afip"` solo devuelve URLs,
variables legacy, carpeta legacy o explicaciones técnicas intencionales.

**Cierre:** Se corrigieron textos visibles, docstrings y comentarios de la app
actual para usar ARCA. La busqueda en `backend/app` y `frontend/src` solo deja
URLs oficiales heredadas `afip.gob.ar`, variables legacy `AFIP_*`,
explicaciones técnicas intencionales y la carpeta legacy `backend/app/afip/`.

### 7. [x] Completado - Decidir si las convenciones Python son obligatorias de verdad

**Problema:** `AGENTS.md` declara type hints obligatorios y docstrings en
espanol. El código pasa `ruff` y `black`, pero hay funciones sin return type y
helpers/clases sin docstring. La regla existe en texto, pero no está reflejada
en tooling ni completamente cumplida.

**Riesgo:** La regla se vuelve decorativa: agentes futuros no saben si deben
corregir todo, mantener el estado actual o solo aplicarla a código nuevo.

**Posible solucion:** Elegir una política explícita: aplicar estrictamente a
código nuevo/modificado, o elevar mypy/ruff/pydocstyle gradualmente. Si se exige
globalmente, abrir una tarea técnica para normalizar firmas y docstrings.

**Criterio de completado:** La regla queda aclarada en `AGENTS.md` y, si aplica,
en tooling/documentación de testing; no quedan expectativas ambiguas.

**Cierre:** Se aclaro en `AGENTS.md` y `CONTRIBUTING.md` que type hints y
docstrings en español son obligatorios para código nuevo o modificado en
funciones, clases y helpers públicos. El código histórico se normaliza cuando se
toca o en tareas técnicas dedicadas; no se declara como deuda bloqueante global.

### 8. [x] Completado - Alinear versionado visible del backend, frontend y documentación

**Problema:** El backend y la UI muestran `0.2.0-mvp`, mientras
`frontend/package.json` mantiene `1.0.0`. La documentación también conserva
referencias históricas a `0.2.0`.

**Riesgo:** Las versiones visibles no sirven para diagnostico ni release porque
no representan una misma versión de producto.

**Posible solucion:** Definir una fuente de versión para el producto o una regla
clara: versión de producto en backend/config, versión npm solo técnica, o ambas
sincronizadas. Ajustar UI/documentación segun esa decisión.

**Criterio de completado:** La versión que ve el usuario, la API y la
documentación tienen una interpretacion consistente.

**Cierre:** Se definio como versión de producto `0.2.0-mvp` desde
`APP_VERSION` / `settings.app_version`, visible en API y UI. Se actualizó
`backend/app/__init__.py` a `0.2.0-mvp` y `frontend/package.json` /
`package-lock.json` a versión técnica semver `0.2.0`, equivalente a la versión
de producto sin sufijo.

### 9. [x] Completado - Ordenar la estrategia de verificacion frontend completa

**Problema:** La verificacion reciente confirma `type-check` y `build`, pero no
se ejecutó E2E en esta auditoria. Además `npm run lint` esta configurado con
`--fix`, por lo que no es un check puro y puede editar archivos durante una
auditoria.

**Riesgo:** El estado "frontend OK" puede significar cosas distintas segun quien
lo ejecute. Un check de lint puede modificar código sin que el agente lo espere.

**Posible solucion:** Agregar un script de lint no destructivo, por ejemplo
`lint:check`, y documentar un set de verificacion claro: `type-check`, `build`,
`test:unit`, `test:e2e` cuando el stack este levantado.

**Criterio de completado:** Hay comandos diferenciados para verificar y para
autoformatear/autocorregir, y la documentación de testing refleja esa diferencia.

**Cierre:** Se agregó `npm run lint:check` como ESLint no destructivo y se
documento la diferencia con `npm run lint`, que mantiene `--fix`. La guia de
testing ahora distingue `lint:check`, `type-check`, `build`, `test:unit` y
`test:e2e`, aclarando que E2E no es evidencia vigente hasta corregir el setup de
Playwright.

**Nota 2026-07-03:** la convención se reforzó después de la auditoría de
Clawpatch: `npm run lint` quedó como check no destructivo y el autofix quedó
reservado para `npm run lint:fix`.
