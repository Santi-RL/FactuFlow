# Docs para agentes

## Leer primero en cada sesión

- Pendientes temporales de alineación: `docs/agents/alignment-pending.md`
- Visión canónica y protegida del producto: `VISION.md`
- Estado operativo canónico y punto de reanudación: `docs/agents/current-status.md`
- Roadmap de prioridades y fases: `ROADMAP.md`
- Portafolio integrado y dependencias: `docs/agents/development-portfolio.md`
- QA manual, cuando la tarea lo requiera: `docs/agents/manual-qa.md`
- Changelog y corte versionado actual: `CHANGELOG.md`

## Fuente de verdad operativa

- `VISION.md` es la fuente canónica de la visión del producto. Bloquea cambios
  que la contradigan, salvo pedido explícito del usuario para modificar la
  visión primero.
- `docs/agents/current-status.md` es la fuente canónica para saber dónde está parado el proyecto hoy.
- `ROADMAP.md` solo debe resumir prioridades y avance macro alineado con
  `VISION.md`; no debe redefinir la visión ni repetir evidencia operativa
  detallada.
- `docs/agents/development-portfolio.md` integra roadmap y auditorías por causa
  raíz. No reemplaza la visión ni asigna prioridades definitivas sin
  adjudicación manual.
- `docs/agents/manual-qa.md` conserva el checkpoint aceptado y la QA todavía accionable; no reemplaza el estado canónico.
- `docs/user-guide/README.md` describe lo que ve y puede hacer un usuario final; no debe contener bitácora técnica.
- `docs/agents/arca.md` conserva detalles técnicos ARCA y procedimientos seguros.
- `docs/agents/production-workflow.md` define el flujo público y sanitizado de
  desarrollo local, versionado, despliegue manual al VPS y auditoría productiva.
- `CHANGELOG.md` resume el avance histórico y los cortes de versión. No crear
  snapshots largos si el cambio puede quedar cubierto por changelog, roadmap y
  documentos vivos.
- `docs/project/**` conserva auditorías y notas históricas puntuales. No es
  fuente canónica de estado actual salvo que un documento vivo lo cite
  explícitamente.

## Git y GitHub

- El flujo interno por defecto trabaja sobre `main`; no crear ramas nuevas salvo
  pedido explícito del usuario.
- Antes de empezar una implementación, revisar estado local y remoto con Git.
  Si hay commits locales sin push o cambios de una implementación anterior, hay
  que avisar y recomendar publicar/cerrar ese trabajo antes de seguir.
- Después de cada implementación verificada, recomendar commit y push. No hacer
  `git push` sin aprobación explícita del usuario.
- Usar commits chicos y con unidad lógica: una implementación por commit cuando
  sea posible; bugs chicos relacionados pueden agruparse si forman una misma
  corrección.
- Para GitHub, seguir el enfoque del plugin local: resolver primero repo/rama
  con Git, usar la app de GitHub para PRs/issues/metadatos cuando aplique, y
  usar `git`/`gh` para gaps como estado de rama, commits, push y checks.
- Para verificar CI, usar GitHub Actions/check-runs (`gh run list`,
  `gh run view` o la API de check-runs). No consultar el endpoint legacy de
  commit statuses (`/commits/{sha}/status`) salvo pedido explícito de auditar
  una integración antigua que dependa de ese endpoint.
- En Codex con sandbox activo, usar permisos elevados desde el inicio para
  comandos Git que escriben en `.git`, como `git add`, `git commit` y
  `git push`. Sin eso pueden fallar con
  `Unable to create .git/index.lock: Permission denied`. Los comandos de lectura
  como `git status`, `git diff` y `git log` pueden ejecutarse normalmente salvo
  bloqueo puntual del entorno.
- Antes de preparar un commit, aplicar la política de seguridad:
  no subir datos privados, CUITs reales, nombres reales de clientes/emisores,
  credenciales, CAEs reales, capturas privadas, Excel/PDF de clientes, bases,
  logs ni evidencia local. Ver `docs/agents/security.md`.

## Revision asistida

- No ejecutar `autoreview` automáticamente. El usuario puede pedirlo en
  cualquier momento; si no lo pidió, sugerirlo solo cuando el cambio sea
  importante o antes de cerrar un commit/PR no trivial, y pedir confirmación
  explícita antes de correrlo.
- Recomendarlo especialmente para cambios en autenticación, autorización,
  usuarios, permisos, roles, sesiones, certificados, ARCA/WSAA/WSFE, emisión
  fiscal, borrados, migraciones, datos fiscales, archivos locales, red,
  seguridad multiemisor o confirmaciones irreversibles.
- No insistir con `autoreview` para cambios chicos y de bajo riesgo, como texto,
  documentación simple o estilos menores, salvo pedido del usuario.
- Elegir el momento según costo y precisión: para cambios pequeños pero
  sensibles conviene revisarlo enseguida; para varios cambios relacionados puede
  convenir un único `autoreview` al cerrar el lote; si el diff mezcla temas
  independientes, sugerir separar commits o revisiones.
- Si el usuario confirma la revisión, ejecutar primero tests/lint/formato
  relevantes, revisar el diff real y verificar manualmente cada finding antes
  de aplicar fixes. Si se corrige código por hallazgos aceptados, repetir
  pruebas enfocadas y volver a correr `autoreview` hasta quedar limpio o hasta
  que el usuario decida detener el ciclo.
- Para cambios fiscales críticos, aplicar primero el checklist
  `docs/agents/fiscal-change-checklist.md`. Si el usuario confirma
  `autoreview`, usar `gpt-5.6-sol high` como revisión final preferida y
  `gpt-5.5 high` solo como fallback de disponibilidad. No ejecutar una escalera
  automática de tres modelos/niveles para un fix pequeño ya cubierto por tests.
- Los hallazgos son asesoramiento. Clasificar cada uno como aceptado, rechazado
  o diferido antes de modificar código. Corregir solo hallazgos que reduzcan un
  riesgo real o cubran un contrato roto dentro del alcance.

## Índice rápido por tema

- Visión del producto: `VISION.md`
- Portafolio integrado de desarrollo: `docs/agents/development-portfolio.md`
- Resumen y arquitectura: `docs/agents/overview.md`
- Pendientes temporales de alineación: `docs/agents/alignment-pending.md`
- Estructura del repo y ubicación de archivos: `docs/agents/structure.md`
- Integración ARCA y hallazgos de homologación: `docs/agents/arca.md`
- Checklist de diseño fiscal crítico:
  `docs/agents/fiscal-change-checklist.md`
- Documentación oficial ARCA WS curada: `docs/arca-ws/README.md`
- Notas prácticas ARCA: `docs/arca-ws/NOTAS.md`
- API REST: `docs/api/README.md`
- Launcher local Windows: `FactuFlow Local.vbs`, `FactuFlow Local.cmd`,
  `scripts/factuflow-local-tray.ps1`,
  `docs/agents/local-launcher-runbook.md`
- Runbook de diagnóstico operativo: `docs/agents/support-runbook.md`
- Formatos de importación para emisión masiva: `docs/api/README.md`,
  `backend/app/services/README.md`, `frontend/src/services/README.md`
- Perfiles de carga masiva por emisor: `docs/user-guide/README.md`,
  `docs/api/README.md`, `frontend/src/views/README.md`
- Rediseño UX de carga masiva: `docs/agents/lotes-ux-redesign.md`
- Certificados y wizard: `docs/certificates/README.md`, `docs/certificados-wizard.md`
- Instalación y setup: `docs/setup/README.md`
- Migración local a VPS: `docs/setup/vps-migration.md`
- Flujo de desarrollo, despliegue y auditoría productiva:
  `docs/agents/production-workflow.md`
- Manual de usuario: `docs/user-guide/README.md`
- Seguridad y certificados: `docs/agents/security.md`
- Observabilidad operativa estándar: `docs/agents/operational-observability.md`
- Guía de testing: `docs/agents/testing.md`
- Changelog y línea base actual: `CHANGELOG.md`
- Puesta a punto y reportes Clawpatch:
  `docs/project/audits/clawpatch/README.md`
- Bitácora histórica de 2026-03-09:
  `docs/project/notes/SESSION_2026-03-09.md`
- Cierre del ciclo Clawpatch y release `v0.2.1`:
  `docs/project/audits/clawpatch/2026-07-10-cierre-ciclo-v0.2.1.md`

## Regla de continuidad

Si el usuario dice algo como "quiero seguir donde quedamos", la secuencia correcta es:

1. Leer `docs/agents/alignment-pending.md`.
2. Si hay puntos pendientes, avisarlo brevemente. Si el estado es `COMPLETADO`,
   continuar sin inventar un conflicto.
3. Leer `VISION.md`.
4. Leer `docs/agents/current-status.md`, que contiene el handoff breve y el
   punto exacto para retomar.
5. Confirmar la prioridad en `ROADMAP.md`.
6. Consultar `docs/agents/manual-qa.md` si la tarea requiere QA, UI o deploy.
7. Si hay contradicciones entre docs vivas y evidencia local/código, separar
   hechos verificables de decisiones de producto abiertas. Corregir los hechos
   comprobables en documentos vivos y resumir el cambio en `CHANGELOG.md`
   cuando corresponda.

Si el usuario pregunta "cómo está el proyecto" o "qué es lo primero que debemos
solucionar", revisar `alignment-pending.md`. Si no hay pendientes, ir a
`current-status.md > Punto exacto para retomar` y a la primera prioridad del
roadmap.

No rearmar el contexto desde cero si esos archivos ya lo documentan.

Si una contradicción es verificable por código, tests o evidencia local segura,
corregir la documentación y marcar el estado como completado/histórico. Si la
contradicción depende de una decisión de producto futura, no resolverla por
cuenta propia: dejarla expuesta como decisión pendiente para el usuario.

## Como resolver dudas y errores

1. Buscar primero en esta documentación local con `rg`.
2. Si el tema es ARCA, revisar `docs/agents/arca.md` y `docs/arca-ws/NOTAS.md`.
3. Si el tema es emisión masiva o Excel externo, revisar también
   `docs/user-guide/README.md`, `docs/api/README.md` y los README de
   `backend/app/services/` y `frontend/src/services/`.
4. Si falta contexto histórico de trabajo, revisar `docs/project/notes/SESSION_2026-03-09.md`.
5. Si no alcanza con la documentación local, buscar en internet agregando `ARCA`.
6. Si con `ARCA` no aparece, repetir usando `AFIP` por compatibilidad legacy.
