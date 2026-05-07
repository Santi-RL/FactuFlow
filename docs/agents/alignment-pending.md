# Revision temporal de alineacion del proyecto

Estado general: ACTIVO

Ultima actualizacion: 2026-05-07

Este archivo es temporal y existe para ordenar los conflictos detectados entre
las instrucciones del proyecto, la documentacion viva y la implementacion real.
Debe eliminarse solo cuando todos los puntos esten marcados como completados y
esa decision quede reflejada en `AGENTS.md`.

## Uso obligatorio para agentes

- Al iniciar cualquier chat nuevo, leer este archivo despues de `AGENTS.md`.
- Si existe al menos un punto sin completar, avisar al usuario que hay pendientes
  de alineacion antes de responder el pedido, aunque el pedido sea de otro tema.
- Si el usuario pregunta "como esta el proyecto", "que es lo primero que debemos
  solucionar" o una variante equivalente, responder directamente con el primer
  punto pendiente de esta lista y proponer avanzar sobre ese punto.
- Al resolver un punto, cambiar su estado a `[x] Completado`, agregar una nota
  breve de cierre y mantener la numeracion estable.
- No reordenar los puntos ya existentes salvo decision explicita del usuario.

## Pendientes priorizados

### 1. [x] Completado - Proteger artefactos sensibles y temporales que hoy son stageables

**Problema:** Hay archivos runtime/QA sin trackear dentro de `backend/data/` y
`output/playwright/`, incluyendo cache de token ARCA, PDFs, XLSX y CSR. Las
instrucciones dicen que `data/` y certificados deben ser gitignored, pero la
regla actual no cubre `backend/data/**`, `output/**` ni caches JSON.

**Riesgo:** Se puede commitear material sensible o artefactos de pruebas reales.
Tambien ensucia cualquier revision porque mezcla codigo con evidencia local.

**Posible solucion:** Ajustar `.gitignore` para cubrir `backend/data/**`,
`data/**`, `output/**`, `logs/**`, caches ARCA y artefactos de Playwright,
preservando `.gitkeep` cuando haga falta. Luego limpiar el working tree de
artefactos no versionables sin borrar evidencia que el usuario quiera conservar.

**Criterio de completado:** `git status --short --untracked-files=all` no debe
mostrar artefactos runtime/QA ni caches sensibles; solo codigo, docs y archivos
de configuracion intencionales.

**Cierre:** Se actualizo `.gitignore` para ignorar `backend/data/`, `data/`,
`output/`, reportes/resultados Playwright y caches runtime. Los artefactos ARCA,
PDF/XLSX/CSR locales dejaron de aparecer como untracked versionables.

### 2. [ ] Unificar el estado real de produccion en la documentacion viva

**Problema:** `docs/agents/current-status.md` y `ROADMAP.md` dicen que el
certificado productivo, la autorizacion `wsfe` y los puntos Web Services reales
ya quedaron verificados. En cambio `docs/agents/manual-qa.md`,
`docs/agents/overview.md` y `docs/user-guide/README.md` todavia dicen que falta
configurar certificado, autorizacion y punto de venta productivos.

**Riesgo:** Un agente o una persona puede retomar desde un paso equivocado y
repetir trabajo ya hecho, o peor, asumir que falta algo externo cuando solo falta
confirmar el punto de venta y ejecutar la primera prueba real controlada.

**Posible solucion:** Elegir una unica verdad operativa. Con la evidencia actual,
parece razonable tomar como canon `docs/agents/current-status.md` y `ROADMAP.md`,
y actualizar los documentos rezagados para indicar que falta la primera prueba
real controlada, no la configuracion productiva base.

**Criterio de completado:** Todos los documentos de continuidad coinciden en el
mismo punto de reanudacion productivo y no hay contradicciones sobre certificado,
autorizacion `wsfe` ni puntos de venta productivos.

### 3. [ ] Actualizar la documentacion de API REST al contrato real

**Problema:** `docs/api/README.md` documenta endpoints `/api/v1/...`, Swagger en
`/docs`, ReDoc en `/redoc`, rate limiting y rutas antiguas. El backend real
registra `/api/...`, expone Swagger en `/api/docs`, ReDoc en `/api/redoc`, y ya
tiene lotes, PDF real, reportes y endpoints nuevos.

**Riesgo:** La documentacion publica induce a usar rutas inexistentes y afirma
capacidades no implementadas, como rate limiting.

**Posible solucion:** Reescribir `docs/api/README.md` desde el estado real de
`backend/app/main.py` y `backend/app/api/*.py`. Eliminar `/api/v1`, corregir
docs URLs, documentar lotes, PDF, empresa activa por `X-Empresa-Id` y quitar
rate limiting salvo que se implemente.

**Criterio de completado:** Los ejemplos de `docs/api/README.md` coinciden con
los routers reales y no mencionan capacidades inexistentes.

### 4. [ ] Resolver la doble estrategia de schema: Alembic vs `create_all`

**Problema:** El README y Docker usan `alembic upgrade head`, pero el backend
ejecuta `Base.metadata.create_all` al iniciar en desarrollo/testing. Ademas
`run-local.ps1` levanta `uvicorn` sin correr Alembic. Esto convive con una base
SQLite local legacy que ya se reconoce como no alineada limpiamente.

**Riesgo:** Nuevas instalaciones locales pueden quedar con schemas creados por
SQLAlchemy directo en vez de migraciones, ocultando problemas de Alembic y
prolongando la deuda de la DB legacy.

**Posible solucion:** Definir Alembic como unico camino de schema para entornos
normales. Ajustar `run-local.ps1` para ejecutar `alembic upgrade head` antes de
levantar el backend. Dejar `create_all` solo para tests controlados si realmente
hace falta, o mover los tests a migraciones/fixtures explicitas.

**Criterio de completado:** El arranque local documentado y automatizado aplica
migraciones antes de servir la API, y queda documentado que SQLite legacy no es
la base canonica para operacion real.

### 5. [ ] Completar la documentacion de estructura interna con modulos nuevos

**Problema:** Existen modulos nuevos importantes que no aparecen o aparecen de
forma incompleta en indices internos: `lotes_comprobantes`, `lote_worker`,
servicios de constancias, `backend/app/arca/soap.py`, script
`create_admin_user`, schemas/types de lotes y servicio frontend de lotes.

**Riesgo:** La documentacion guia a agentes hacia una arquitectura anterior y
hace mas probable duplicar logica o ubicar nuevos cambios en lugares incorrectos.

**Posible solucion:** Actualizar `docs/agents/structure.md`,
`backend/app/api/README.md`, `backend/app/services/README.md`,
`backend/app/models/README.md`, `frontend/src/services/README.md` y cualquier
README de vistas/componentes que haya quedado incompleto.

**Criterio de completado:** Los indices de estructura listan todos los modulos
core actuales y explican donde va cada cambio nuevo.

### 6. [ ] Limpiar nomenclatura publica AFIP restante y dejar solo legacy real

**Problema:** La regla del proyecto exige usar ARCA en UI, textos y
documentacion nueva. Todavia quedan menciones conceptuales a AFIP en docstrings
y comentarios de backend, y una referencia visible `ARCA (ex-AFIP)` en el wizard
de certificados. Las URLs `afip.gob.ar` si son legacy valido.

**Riesgo:** El producto mantiene lenguaje mixto y contradice la regla de
nomenclatura, especialmente en textos visibles para usuario.

**Posible solucion:** Reemplazar menciones conceptuales por ARCA. Mantener AFIP
solo en URLs oficiales, variables legacy `AFIP_*`, carpeta `backend/app/afip/`
documentada como compatibilidad y notas tecnicas que expliquen endpoints legacy.

**Criterio de completado:** `rg -n "AFIP|Afip|afip"` solo devuelve URLs,
variables legacy, carpeta legacy o explicaciones tecnicas intencionales.

### 7. [ ] Decidir si las convenciones Python son obligatorias de verdad

**Problema:** `AGENTS.md` declara type hints obligatorios y docstrings en
espanol. El codigo pasa `ruff` y `black`, pero hay funciones sin return type y
helpers/clases sin docstring. La regla existe en texto, pero no esta reflejada
en tooling ni completamente cumplida.

**Riesgo:** La regla se vuelve decorativa: agentes futuros no saben si deben
corregir todo, mantener el estado actual o solo aplicarla a codigo nuevo.

**Posible solucion:** Elegir una politica explicita: aplicar estrictamente a
codigo nuevo/modificado, o elevar mypy/ruff/pydocstyle gradualmente. Si se exige
globalmente, abrir una tarea tecnica para normalizar firmas y docstrings.

**Criterio de completado:** La regla queda aclarada en `AGENTS.md` y, si aplica,
en tooling/documentacion de testing; no quedan expectativas ambiguas.

### 8. [ ] Alinear versionado visible del backend, frontend y documentacion

**Problema:** El backend y la UI muestran `0.2.0-mvp`, mientras
`frontend/package.json` mantiene `1.0.0`. La documentacion tambien conserva
referencias historicas a `0.2.0`.

**Riesgo:** Las versiones visibles no sirven para diagnostico ni release porque
no representan una misma version de producto.

**Posible solucion:** Definir una fuente de version para el producto o una regla
clara: version de producto en backend/config, version npm solo tecnica, o ambas
sincronizadas. Ajustar UI/documentacion segun esa decision.

**Criterio de completado:** La version que ve el usuario, la API y la
documentacion tienen una interpretacion consistente.

### 9. [ ] Ordenar la estrategia de verificacion frontend completa

**Problema:** La verificacion reciente confirma `type-check` y `build`, pero no
se ejecuto E2E en esta auditoria. Ademas `npm run lint` esta configurado con
`--fix`, por lo que no es un check puro y puede editar archivos durante una
auditoria.

**Riesgo:** El estado "frontend OK" puede significar cosas distintas segun quien
lo ejecute. Un check de lint puede modificar codigo sin que el agente lo espere.

**Posible solucion:** Agregar un script de lint no destructivo, por ejemplo
`lint:check`, y documentar un set de verificacion claro: `type-check`, `build`,
`test:unit`, `test:e2e` cuando el stack este levantado.

**Criterio de completado:** Hay comandos diferenciados para verificar y para
autoformatear/autocorregir, y la documentacion de testing refleja esa diferencia.
