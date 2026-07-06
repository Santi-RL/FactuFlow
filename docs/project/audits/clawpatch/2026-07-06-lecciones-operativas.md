# Lecciones operativas Clawpatch 2026-07-06

Este documento conserva el aprendizaje de la sesión del 2026-07-06 para evitar
repetir pruebas a ciegas al auditar FactuFlow con Clawpatch.

## Fuentes oficiales revisadas

- Repositorio upstream: `https://github.com/openclaw/clawpatch`
- README upstream: `https://github.com/openclaw/clawpatch/blob/main/README.md`
- Documentación upstream:
  - `docs/quickstart.md`
  - `docs/feature-mapping.md`
  - `docs/code-review.md`
  - `docs/findings.md`
  - `docs/reporting.md`
  - `docs/configuration.md`
  - `docs/safety.md`
  - `docs/providers.md`
  - `docs/initialization.md`
  - `docs/validation.md`
  - `docs/patching.md`
  - `docs/spec.md`

## Modelo mental correcto

- Clawpatch mapea un repositorio en features semánticas, revisa cada feature
  con un proveedor, persiste hallazgos y permite un ciclo de reparación
  explícito por finding.
- `status`, `report`, `next`, `show`, `map --dry-run` y `review` no editan
  código fuente. `review` sí puede llamar al proveedor configurado y enviarle
  contexto del código.
- `fix` es el único comando que puede editar el worktree y requiere
  `--finding <id>`. En FactuFlow no se ejecuta sin pedido explícito.
- Los findings no son una sentencia. Son hipótesis con evidencia que deben
  triagearse como `open`, `false-positive`, `fixed`, `wont-fix` o `uncertain`.
- `report --json` debe consumirse desde `items`. La clave `findings` es un
  contador de compatibilidad, no el arreglo de findings.
- `review --dry-run --json` sirve para ver qué features se revisarían sin llamar
  al proveedor.
- `--feature <id>` revisa exactamente una feature. `--feature-list <path>`
  revisa una lista exacta y ordenada de IDs.
- `--source agent` fuerza mapeo asistido por proveedor y puede agregar features
  más amplias. En FactuFlow no es el camino normal para auditorías de rutina.

## Error operativo detectado

No alcanza con usar el state dir correcto. Este comando parece auditar backend,
pero si se ejecuta desde la raíz sin `--root backend` el alcance real es el repo
completo:

```powershell
clawpatch --state-dir .clawpatch/backend --config .clawpatch/backend/config.json review --limit 50
```

Ese uso puede contaminar `.clawpatch/backend` con features de frontend o repo
general, porque `--state-dir` solo elige dónde guardar estado; no define por sí
solo el root de análisis.

La forma correcta en FactuFlow es usar los scripts npm:

```powershell
npm run clawpatch:backend:status
npm run clawpatch:backend:map
npm run clawpatch:backend:review
npm run clawpatch:backend:status
```

Si se necesita CLI directa, usar siempre `--root` junto con los paths de estado:

```powershell
clawpatch --root backend --state-dir ../.clawpatch/backend --config ../.clawpatch/backend/config.json status
clawpatch --root backend --state-dir ../.clawpatch/backend --config ../.clawpatch/backend/config.json map
clawpatch --root backend --state-dir ../.clawpatch/backend --config ../.clawpatch/backend/config.json review --limit 50 --jobs 1
clawpatch --root backend --state-dir ../.clawpatch/backend --config ../.clawpatch/backend/config.json report --status open
```

Equivalentes:

```powershell
clawpatch --root frontend --state-dir ../.clawpatch/frontend --config ../.clawpatch/frontend/config.json ...
clawpatch --root . --state-dir .clawpatch/repo --config .clawpatch/repo/config.json ...
```

## Procedimiento recomendado para próximas auditorías

1. Revisar `git status --short --branch`.
2. Usar el slice correcto: `repo`, `backend` o `frontend`.
3. Ejecutar `npm run clawpatch:<slice>:status`.
4. Ejecutar `npm run clawpatch:<slice>:map`.
5. Ejecutar `npm run clawpatch:<slice>:status`.
6. Antes de gastar proveedor, ejecutar:

```powershell
clawpatch --root backend --state-dir ../.clawpatch/backend --config ../.clawpatch/backend/config.json review --limit 50 --jobs 1 --dry-run --json
```

7. Ejecutar `npm run clawpatch:<slice>:review`.
8. Leer `npm run clawpatch:<slice>:status`.
9. Generar `report --status open --json` y resumir por severidad, categoría y
   archivos `backend/*`, `frontend/*` o repo según corresponda.
10. Triar manualmente antes de reparar. Para backend fiscal, priorizar ARCA,
    fecha fiscal, idempotencia, reconciliación, numeración, borrado de historial,
    PDFs fiscales e aislamiento multiemisor.

## Hallazgos y falsos positivos

- Un finding puede ser falso positivo si contradice una decisión explícita de
  `VISION.md`, `ROADMAP.md` o documentación viva.
- En FactuFlow, por ejemplo, que todos los usuarios activos puedan operar todos
  los emisores configurados es una decisión de producto vigente; no equivale por
  sí misma a un bug de permisos finos.
- Un finding sigue siendo importante si expone un camino no usado por la UI pero
  alcanzable por API, como endpoints legacy que solicitan CAE directo.
- Que producción haya funcionado no invalida findings sobre bordes: carreras,
  crashes entre ARCA y persistencia, borrados excepcionales, endpoints legacy o
  problemas de recuperación pueden no aparecer en el flujo feliz.

## Cuándo usar `clawpatch fix`

Usar `fix` solo como parche asistido para findings aceptados, localizados y con
validación clara. No usarlo como modo automático de reparación de hallazgos
fiscales críticos.

Buen uso de `fix`:

- healthchecks, scripts, checks de formato/lint o errores de contrato menores;
- validaciones locales simples;
- manejo de errores sin cambio de política de negocio;
- tests faltantes o refactors pequeños con bajo riesgo fiscal.

Preferir reparación manual:

- CAE, ARCA, WSFE, numeración, fechas fiscales, idempotencia o reconciliación;
- lotes, worker, emisión individual/masiva o estados inciertos;
- migraciones, borrados, certificados, PDFs fiscales, reportes impositivos o
  aislamiento multiemisor;
- cambios que requieren diseñar invariantes, tabla de estados o rollback.

## Incidente `.tmp\tmprdyi7u7w`

Durante esta sesión, `clawpatch map` falló porque Windows no permitía resolver:

```text
C:\Users\SANTI\Documents\Proyectos\FactuFlow\.tmp\tmprdyi7u7w
```

La carpeta estaba vacía, pero tenía permisos/propiedad que impedían `Get-Acl`,
`icacls`, `Remove-Item`, `rmdir` y `Rename-Item` desde el token normal de
Codex. Se resolvió lanzando PowerShell elevado por UAC, tomando propiedad,
concediendo permiso a `SANTIAGO\SANTI` y eliminando la carpeta.

El log local quedó en:

```text
C:\Users\SANTI\Documents\Proyectos\FactuFlow\.tmp\tmprdyi7u7w-admin-cleanup.log
```

Lección: si el repo tiene temporales ignorados inaccesibles, no cambiar el
alcance de Clawpatch a ciegas. Primero confirmar ruta absoluta, verificar que
está dentro de `.tmp/`, y solo entonces pedir autorización explícita para tomar
propiedad o eliminarla.

## Estado contaminado de la corrida 2026-07-06

La corrida directa sin `--root backend` dejó `.clawpatch/backend` con features
de frontend/repo además de backend. Por eso, los conteos de esa corrida no deben
interpretarse como auditoría backend pura sin filtrar.

Para continuar desde ese estado:

- usar `npm run clawpatch:backend:map` para resembrar el backend correcto;
- usar `report --json` y filtrar evidencia o feature title de `backend/*` antes
  de priorizar reparaciones backend;
- si se necesita estado limpio, archivar o eliminar `.clawpatch/backend` solo
  con decisión explícita del usuario y luego reconstruirlo con
  `npm run clawpatch:backend:init` y `npm run clawpatch:backend:map`.

