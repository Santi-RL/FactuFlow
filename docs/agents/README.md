# Docs para agentes

## Leer primero en cada sesion

- Pendientes temporales de alineacion: `docs/agents/alignment-pending.md`
- Vision canonica y protegida del producto: `VISION.md`
- Estado operativo canonico y punto de reanudacion: `docs/agents/current-status.md`
- QA manual y ultimo checkpoint: `docs/agents/manual-qa.md`
- Roadmap de prioridades y fases: `ROADMAP.md`
- Changelog y corte versionado actual: `CHANGELOG.md`

## Fuente de verdad operativa

- `VISION.md` es la fuente canonica de la vision del producto. Bloquea cambios
  que la contradigan, salvo pedido explicito del usuario para modificar la
  vision primero.
- `docs/agents/current-status.md` es la fuente canonica para saber donde esta parado el proyecto hoy.
- `ROADMAP.md` solo debe resumir prioridades y avance macro alineado con
  `VISION.md`; no debe redefinir la vision ni repetir evidencia operativa
  detallada.
- `docs/agents/manual-qa.md` registra recorridos de QA y hallazgos manuales, no reemplaza el estado canonico.
- `docs/user-guide/README.md` describe lo que ve y puede hacer un usuario final; no debe contener bitacora tecnica.
- `docs/agents/arca.md` conserva detalles tecnicos ARCA y procedimientos seguros.
- `docs/agents/production-workflow.md` define el flujo público y sanitizado de
  desarrollo local, versionado, despliegue manual al VPS y auditoría productiva.
- `CHANGELOG.md` resume el avance historico y los cortes de version. No crear
  snapshots largos si el cambio puede quedar cubierto por changelog, roadmap y
  documentos vivos.
- `docs/project/**` conserva auditorias y notas historicas puntuales. No es
  fuente canonica de estado actual salvo que un documento vivo lo cite
  explicitamente.

## Git y GitHub

- El flujo interno por defecto trabaja sobre `main`; no crear ramas nuevas salvo
  pedido explicito del usuario.
- Antes de empezar una implementacion, revisar estado local y remoto con Git.
  Si hay commits locales sin push o cambios de una implementacion anterior, hay
  que avisar y recomendar publicar/cerrar ese trabajo antes de seguir.
- Despues de cada implementacion verificada, recomendar commit y push. No hacer
  `git push` sin aprobacion explicita del usuario.
- Usar commits chicos y con unidad logica: una implementacion por commit cuando
  sea posible; bugs chicos relacionados pueden agruparse si forman una misma
  correccion.
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
- Antes de preparar un commit, aplicar la politica de seguridad:
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
  `autoreview`, usar corridas escalonadas con `gpt-5.5`: primero `low`, luego
  `medium` cuando `low` quede limpio, y recién después `high`. No usar una
  revisión de alto razonamiento para encontrar errores básicos que debieron
  detectarse en diseño, tests o revisión temprana.
- Los hallazgos son asesoramiento. Clasificar cada uno como aceptado, rechazado
  o diferido antes de modificar código. Corregir solo hallazgos que reduzcan un
  riesgo real o cubran un contrato roto dentro del alcance.

## Indice rapido por tema

- Vision del producto: `VISION.md`
- Resumen y arquitectura: `docs/agents/overview.md`
- Pendientes temporales de alineacion: `docs/agents/alignment-pending.md`
- Estructura del repo y ubicacion de archivos: `docs/agents/structure.md`
- Integracion ARCA y hallazgos de homologacion: `docs/agents/arca.md`
- Checklist de diseño fiscal crítico:
  `docs/agents/fiscal-change-checklist.md`
- Documentacion oficial ARCA WS curada: `docs/arca-ws/README.md`
- Notas practicas ARCA: `docs/arca-ws/NOTAS.md`
- API REST: `docs/api/README.md`
- Launcher local Windows: `FactuFlow Local.vbs`, `FactuFlow Local.cmd`,
  `scripts/factuflow-local-tray.ps1`,
  `docs/agents/local-launcher-runbook.md`
- Formatos de importacion para emision masiva: `docs/api/README.md`,
  `backend/app/services/README.md`, `frontend/src/services/README.md`
- Perfiles de carga masiva por emisor: `docs/user-guide/README.md`,
  `docs/api/README.md`, `frontend/src/views/README.md`
- Certificados y wizard: `docs/certificates/README.md`, `docs/certificados-wizard.md`
- Instalación y setup: `docs/setup/README.md`
- Migración local a VPS: `docs/setup/vps-migration.md`
- Flujo de desarrollo, despliegue y auditoría productiva:
  `docs/agents/production-workflow.md`
- Manual de usuario: `docs/user-guide/README.md`
- Seguridad y certificados: `docs/agents/security.md`
- Observabilidad operativa estandar: `docs/agents/operational-observability.md`
- Guia de testing: `docs/agents/testing.md`
- Changelog y linea base actual: `CHANGELOG.md`
- Puesta a punto y reportes Clawpatch:
  `docs/project/audits/clawpatch/README.md`
- Bitacora tecnica de la ultima sesion: `docs/project/notes/SESSION_2026-03-09.md`

## Regla de continuidad

Si el usuario dice algo como "quiero seguir donde quedamos", la secuencia correcta es:

1. Leer `docs/agents/alignment-pending.md`
2. Si hay puntos pendientes, avisarlo brevemente antes de continuar
3. Leer `VISION.md`
4. Leer `docs/agents/current-status.md`
5. Leer `docs/agents/manual-qa.md`
6. Confirmar el siguiente paso en `ROADMAP.md`
7. Si hay contradicciones entre docs vivas y evidencia local/codigo, separar
   hechos verificables de decisiones de producto abiertas. Corregir los hechos
   comprobables en documentos vivos y resumir el cambio en `CHANGELOG.md`
   cuando corresponda.

Si el usuario pregunta "como esta el proyecto" o "que es lo primero que debemos
solucionar", ir directo al primer punto pendiente de
`docs/agents/alignment-pending.md`.

No rearmar el contexto desde cero si esos archivos ya lo documentan.

Si una contradiccion es verificable por codigo, tests o evidencia local segura,
corregir la documentacion y marcar el estado como completado/historico. Si la
contradiccion depende de una decision de producto futura, no resolverla por
cuenta propia: dejarla expuesta como decision pendiente para el usuario.

## Como resolver dudas y errores

1. Buscar primero en esta documentacion local con `rg`.
2. Si el tema es ARCA, revisar `docs/agents/arca.md` y `docs/arca-ws/NOTAS.md`.
3. Si el tema es emision masiva o Excel externo, revisar tambien
   `docs/user-guide/README.md`, `docs/api/README.md` y los README de
   `backend/app/services/` y `frontend/src/services/`.
4. Si falta contexto historico de trabajo, revisar `docs/project/notes/SESSION_2026-03-09.md`.
5. Si no alcanza con la documentacion local, buscar en internet agregando `ARCA`.
6. Si con `ARCA` no aparece, repetir usando `AFIP` por compatibilidad legacy.
