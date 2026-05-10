# Guía para Agentes de IA - FactuFlow

## Alcance
- Este archivo define cómo trabajar en el repo.
- La documentación operativa extendida está en `docs/agents/README.md`.
- Antes de responder cualquier chat nuevo, leer `docs/agents/alignment-pending.md`. Si ese archivo tiene puntos sin completar, avisar que hay conflictos de alineación pendientes antes de continuar con el pedido.
- Antes de retomar una sesión, leer `docs/agents/current-status.md`, `docs/agents/manual-qa.md` y `ROADMAP.md`.

## Nombres: ARCA vs AFIP
- Usar ARCA en textos, UI y documentación nueva.
- AFIP queda solo como nomenclatura legacy en URLs y variables de entorno existentes.
- Si agregás nuevos nombres públicos, preferí `ARCA_*` y mantené compatibilidad cuando sea necesario.

## Regla fiscal critica: fecha de emision
- Nunca jamas asumir la fecha de hoy como fecha fiscal de un comprobante.
- Ningun flujo de emision, individual, masivo, factura, nota de credito o nota
  de debito, puede usar `date.today()`, `datetime.today()`, `new Date()` ni
  equivalentes como default de `fecha_emision`/`CbteFch`.
- La fecha de emision debe ser un dato explicito definido por el usuario o
  tomado del archivo solo cuando el usuario eligio esa politica.
- Antes de emitir comprobantes reales debe mostrarse un modal de confirmacion
  irreversible con este mensaje, reemplazando la fecha y, si aplica, indicando
  el punto de venta:
  `Está seguro que quiere emitir comprobantes con fecha XX/XX/XX? Recuerde que luego no podrá emitir comprobantes con fecha anterior para ese mismo punto de venta.`
- Si se agrega o modifica cualquier camino que pueda solicitar CAE a ARCA, hay
  que verificar esta regla en UI, API, servicios, tests y documentacion antes de
  darlo por terminado.

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
- Python: PEP8, `black` (88). En codigo nuevo o modificado, type hints y
  docstrings en español son obligatorios para funciones, clases y helpers
  publicos. El codigo historico se normaliza cuando se toca o en tareas
  tecnicas dedicadas.
- FastAPI: imports absolutos desde `app/`.
- Vue: Composition API con `<script setup>`, TypeScript recomendado, componentes en PascalCase, events en kebab-case.
- Tailwind: priorizar utilidades sobre CSS custom.
- UI y mensajes para usuarios en español (Argentina).

## Continuidad y documentación viva
- Si el usuario pregunta "cómo está el proyecto", "qué es lo primero que debemos solucionar" o una variante equivalente, ir directo al primer punto pendiente de `docs/agents/alignment-pending.md`.
- Si el usuario dice "seguir donde quedamos", arrancar por `docs/agents/current-status.md` y `docs/agents/manual-qa.md`.
- Después de cambios importantes en producto, UX, flujos core o ARCA, actualizar siempre:
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
  explicito del usuario.
- Antes de empezar un cambio, revisar `git status --short --branch` y, si hace
  falta, comparar con `origin/main`. Si hay commits locales sin publicar o
  cambios listos de una implementacion anterior, avisar y recomendar cerrar ese
  ciclo con commit/push antes de acumular trabajo nuevo.
- Mantener cada implementacion relevante en su propio commit. Para ajustes
  chicos, bugs relacionados o correcciones de una misma verificacion, se puede
  agrupar un commit unico si mantiene una unidad logica clara.
- Despues de implementar y verificar un cambio, recomendar commit y push para
  mantener `main` local y GitHub sincronizados.
- No ejecutar `git push` sin pedido explicito del usuario. Si hay cambios listos
  para publicar, preparar commit(s) y pedir confirmacion antes de pushear.
- Preferir PRs para cambios no triviales cuando el usuario lo pida. En el flujo
  habitual sobre `main`, minimizar commits de ruido (formato/lint) y agruparlos
  con el cambio funcional correspondiente.

## Comandos
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
- Ver detalles en `docs/agents/security.md`.

## Documentación operativa
- Índice: `docs/agents/README.md`
- Pendientes temporales de alineación: `docs/agents/alignment-pending.md`
- Estado actual: `docs/agents/current-status.md`
- QA manual: `docs/agents/manual-qa.md`
- Resumen y arquitectura: `docs/agents/overview.md`
- Estructura del repo: `docs/agents/structure.md`
- ARCA y endpoints: `docs/agents/arca.md`
- Documentación oficial ARCA WS: `https://www.arca.gob.ar/ws/` (índice y descargas locales en `docs/arca-ws/README.md`)
- Testing: `docs/agents/testing.md`
- Seguridad: `docs/agents/security.md`
- Manual de usuario: `docs/user-guide/README.md`
- Bitácora técnica reciente: `docs/project/notes/SESSION_2026-03-09.md`
- Contribución y commits: `CONTRIBUTING.md`
