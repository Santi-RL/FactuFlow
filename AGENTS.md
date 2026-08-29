# Guía para agentes de IA — FactuFlow

## Alcance y fuentes de verdad

- Esta guía rige el repositorio `FactuFlow`; las reglas compartidas de
  `C:\Users\SANTI\Documents\Proyectos\AGENTS.md` se aplican cuando no haya
  conflicto.
- `VISION.md` es la fuente canónica y protegida de la visión. Solo se modifica por
  pedido explícito del usuario; si un cambio la contradice, detenerse hasta que
  el usuario autorice cambiar primero la visión.
- `ROADMAP.md` contiene únicamente prioridades futuras;
  `docs/agents/current-status.md` resume el estado aceptado y el handoff;
  `docs/agents/development-portfolio.md` conserva el inventario activo;
  `CHANGELOG.md`, dossiers y `docs/project/history/` conservan la historia.
- El estado desplegado autoritativo vive en el plano de control `VPS Hostinger` /
  `vps-admin`. No inferirlo desde `main`, una release, un tag ni estos documentos.
- `docs/agents/README.md` enruta cada tarea al mínimo de documentos necesario.
  No leer por defecto auditorías, snapshots ni todos los diseños cerrados. Para
  QA, seguridad, cambios fiscales y despliegue usar, según corresponda,
  `docs/agents/manual-qa.md`, `docs/agents/security.md`,
  `docs/agents/fiscal-change-checklist.md` y
  `docs/agents/production-workflow.md`.
- `docs/agents/documentation-governance.md` define responsabilidades, archivo y
  reglas para evitar duplicación documental.
- Cada unidad debe tener un objetivo concreto. No ampliar el alcance ni sumar un
  fix distinto sin decisión explícita. Un bloqueo que impida ejecutar o demostrar
  el objetivo de forma segura se informa antes de continuar.
- Usar ARCA en UI y documentación nueva. AFIP queda únicamente como nomenclatura
  técnica legacy cuando la compatibilidad existente lo requiera.

## Simplicidad segura y decisiones de producto

- La aplicación está dirigida a personal administrativo y contable no técnico.
  El sistema debe absorber detalles técnicos y mostrar sólo información útil y
  accionable.
- No agregar pasos, confirmaciones, bloqueos, vencimientos, comprobaciones
  recurrentes o jerga técnica sólo porque parezcan más seguros. Identificar el
  riesgo concreto y usar la menor carga operativa razonable.
- No reducir validaciones fiscales, trazabilidad, aislamiento, idempotencia,
  reconciliación o confirmaciones irreversibles para simplificar la interfaz.
- Si una alternativa aumenta fricción o reduce una protección vigente, explicar
  opciones y consecuencias y pedir una decisión explícita del usuario. El agente
  no elige unilateralmente ese intercambio.
- Mientras falte la decisión, preservar el comportamiento vigente. Un bloqueo
  fail-closed ante riesgo inmediato no autoriza a diseñar una política permanente
  ni ampliar el alcance por cuenta propia.

## Invariantes fiscales

- La fecha de emisión es siempre un dato explícito del usuario o del archivo
  cuando el usuario eligió esa política. Nunca usar la fecha actual como valor
  predeterminado (`date.today()`, `datetime.today()`, `new Date()` o equivalentes).
- Antes de cualquier solicitud real de CAE debe existir una confirmación
  irreversible que muestre fecha y, cuando corresponda, punto de venta. Conservar
  el mensaje vigente:
  `Está seguro que quiere emitir comprobantes con fecha XX/XX/XX? Recuerde que luego no podrá emitir comprobantes con fecha anterior para ese mismo punto de venta.`
- Fechas visibles y entradas argentinas: `DD/MM/AAAA`. API, base, ARCA y archivos
  técnicos usan el formato exigido por su contrato (`YYYY-MM-DD`, ISO o
  `CbteFch` `YYYYMMDD`). Validar el calendario; no normalizar fechas imposibles ni
  parsear strings ambiguos con `new Date(string)` o `Date.parse`.
- Si ARCA pudo haber autorizado una emisión, conservar el estado incierto y
  reconciliarlo antes de reintentar. Nunca convertir incertidumbre en rechazo ni
  repetir automáticamente una solicitud de CAE sin determinar primero el
  resultado mediante el flujo seguro aplicable.
- Todo cambio capaz de alcanzar ARCA/WSAA/WSFE, numeración, CAE, fecha fiscal,
  idempotencia, reintentos, reconciliación, comprobantes asociados, certificados
  o aislamiento por emisor debe completar antes el checklist de
  `docs/agents/fiscal-change-checklist.md`, definir invariantes y cubrir caminos
  de error, concurrencia y estados inciertos.

## Privacidad y certificados

- No versionar certificados, claves privadas, credenciales, tokens, CUITs o CAEs
  reales, nombres reales de clientes o emisores, comprobantes, PDFs, Excels,
  bases, logs ni evidencia privada de QA o producción.
- Mantener certificados y datos operativos en rutas ignoradas como `certs/`,
  `data/`, `backend/data/`, `.tmp/`, `private/`, `evidence/` u `output/`.
- Antes de un commit revisar `git status --short --untracked-files=all` y el diff
  staged. La evidencia concreta del VPS permanece fuera del repositorio público.

## Comandos principales

Desde la raíz:

```bash
npm run lint
npm run test
npm run backend:format:check
npm run docs:check
```

Validaciones enfocadas:

```bash
# backend/
pytest
ruff check app/ tests/
black --check app/ tests/

# frontend/
npm run test:unit
npm run lint:check
npm run type-check
```

`npm run format`, ejecutado desde `frontend/`, modifica archivos; usarlo solo
cuando se quiera aplicar formato. Los detalles y matrices vigentes viven en
`docs/agents/testing.md` y `docs/agents/change-quality-gates.md`.

## Git local y revisión

- `main` es la única rama permanente y la fuente canónica del código aceptado.
  Antes de editar, revisar `git status --short --branch` y comparar con
  `origin/main`.
- Por defecto, cada unidad nueva usa una rama temporal corta desde `main`
  sincronizada. Trabajar directamente sobre `main` solo cuando el usuario lo
  pida de forma explícita.
- Preservar cambios ajenos, mantener un commit por unidad coherente y no usar
  force-push, `git reset --hard` ni otras operaciones destructivas.
- No hacer push, merge ni eliminación remota sin autorización explícita. Una
  autorización puede cubrir el ciclo completo solo si su alcance lo dice con
  claridad.
- `autoreview` y Clawpatch se ejecutan únicamente cuando el usuario los pide o
  cuando el riesgo y el runbook aplicable realmente los exigen. Seguir sus
  runbooks vigentes; no incrustar aquí workarounds operativos extensos.

## Despliegue por SHA exacto

- `git push` no despliega. Producción solo cambia por una operación explícita
  contra un commit o tag inmutable identificado por su SHA completo.
- Un pedido explícito de despliegue autoriza publicar el commit coherente, sin
  forzar, y crear una tarea visible en `vps-admin` para desplegar exactamente ese
  SHA, conservar un rollback verificable y ejecutar smoke checks sin emisiones
  reales ni solicitudes de CAE.
- La tarea de despliegue debe registrar el SHA objetivo, preflight, backup y
  rollback aplicables, resultado de los smoke checks y SHA finalmente observado.
  Seguir `docs/agents/production-workflow.md` y la documentación privada de la
  instalación.
- Está prohibido editar código permanente directamente en producción. Todo fix
  debe implementarse y validarse en el repositorio local, quedar en un commit
  coherente y desplegarse después por su SHA exacto.
- No acceder al VPS ni desplegar fuera de una autorización explícita. El estado
  posterior se registra en `VPS Hostinger` / `vps-admin`, no como una versión
  productiva fija en la documentación viva del repositorio.
