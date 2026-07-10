# Cierre del ciclo Clawpatch y release v0.2.1

Fecha: 2026-07-10

Este documento conserva el aprendizaje técnico y metodológico del ciclo largo de
endurecimiento que terminó en `v0.2.1`. Es un cierre sanitizado: no contiene
CUITs, CAEs, clientes, comprobantes, rutas privadas del VPS ni secretos.

## Resultado

Entre el 2026-07-07 y el 2026-07-10 se integraron cambios pequeños y revisables
sobre autorización, aislamiento multiemisor, lotes, certificados, WSAA/WSFE,
fechas fiscales, reportes, PDFs, migraciones, errores, SOAP y frontend.

El corte quedó:

- versionado como `v0.2.1`;
- taggeado en `8099b223f3be7342dbb29367d24c6209dee93a58`;
- aprobado por CI;
- desplegado con backup y restauración aislada;
- validado por smoke checks y QA manual autenticada;
- aceptado después de una emisión fiscal real satisfactoria.

El cierre documental posterior `ece2bdf` no cambió el código desplegado ni movió
el tag.

## Qué se corrigió

El ciclo cubrió, entre otros, estos riesgos:

- permisos de usuarios comunes y administración de emisores;
- validación de rangos y respuestas WSFE parciales o ambiguas;
- importes fiscales calculados y enviados con `Decimal`;
- preservación de historial ante borrado de emisores;
- fechas fiscales y de servicio con calendario real;
- idempotencia, lotes vencidos y estados inciertos;
- aislamiento de cache WSAA por certificado;
- límites de upload y permisos iniciales de claves privadas;
- disponibilidad real del material de certificados;
- sanitización de errores sin perder logs privados;
- timeout SOAP y ejecución fuera del event loop;
- disponibilidad del worker antes de encolar;
- cancelación de respuestas tardías al cambiar de emisor;
- numeración y confirmación segura de emisión individual.

El detalle funcional está en `CHANGELOG.md` y
`docs/agents/current-status.md`.

## Estado persistido de Clawpatch

Última revalidación del código del ciclo: `a1f0938`. Después solo se agregaron
versión y documentación para la release.

Hallazgos objetivo revalidados:

- backend: 3 en `fixed`;
- frontend: 9 en `fixed`.

Contadores locales observados al cierre:

- repo: 0 abiertos;
- backend: 85 abiertos, 57 `medium` y 28 `low`;
- frontend: 6 abiertos, todos `medium`.

No quedó un finding crítico o alto aceptado para bloquear `v0.2.1`.

### Por qué el reporte puede ser grande

`.clawpatch/` es un registro acumulativo persistente, no un reporte limpio de la última
corrida. Conserva:

- findings históricos;
- duplicados generados por features de distinto nivel;
- hallazgos ya corregidos bajo otro ID;
- rechazados o diferidos todavía abiertos;
- features ajenas al slice que entraron en backend durante la corrida del
  2026-07-06 con `--root` incorrecto.

Por eso un reporte grande no significa que aparecieron decenas de bugs nuevos.
El estado backend conserva contaminación histórica y `map` no purga por sí solo
todos los registros anteriores.

No borrar, reinicializar ni crear otro state dir para esconder este historial.
Primero filtrar por evidencia real, revisar `show`, comparar con el código
actual y triar cada finding. Una limpieza o reconstrucción del state dir requiere
decisión explícita del usuario.

## Triage aplicado

Todo finding se trata como hipótesis hasta verificarlo.

- Aceptado: riesgo real y alcanzable, contrato roto o test relevante faltante.
- Rechazado: premisa incorrecta, mitigación ya existente, decisión intencional o
  edge case no alcanzable.
- Diferido: riesgo real, pero necesita diseño o queda fuera del corte actual.

Que producción haya funcionado no refuta una carrera, un fallo intermedio o un
caso de recuperación. Tampoco convierte automáticamente todos los findings en
bugs.

## Metodología eficiente y segura

La metodología que mejor funcionó fue:

1. Congelar el alcance y leer solo el finding, el código propietario, rutas
   vecinas y tests pertinentes.
2. Triar antes de editar.
3. Para riesgos fiscales, seguridad, migraciones, borrados, lotes,
   idempotencia, reconciliación o multiemisor: un cambio sensible por commit.
4. Agrupar cambios chicos solo cuando comparten propiedad del código, causa y validación.
5. Escribir o ajustar primero la regresión enfocada.
6. Ejecutar tests enfocados, lint/formato del área y `git diff --check`.
7. Ejecutar suites completas en checkpoints lógicos, no después de cada cambio
   de pocas líneas.
8. Correr un `autoreview` sobre el commit o lote coherente ya probado.
9. Verificar manualmente cada finding de `autoreview`; no aplicar sugerencias a
   ciegas.
10. Si se acepta un cambio, repetir tests enfocados y el review.
11. Hacer push solo con autorización y después de quedar limpio.
12. Verificar GitHub Actions por SHA.
13. Revalidar Clawpatch después de varios cortes relacionados o antes de cerrar
    una candidata, no después de cada microcambio.

Esta cadencia redujo tiempo y consumo sin quitar controles: la seguridad provino
de alcance pequeño, regresiones enfocadas, revisión de propiedad del código, `autoreview` y
CI, no de repetir siempre la suite completa.

## Política de autoreview

Para nuevos ciclos de FactuFlow:

- modelo preferido: `gpt-5.6-sol`;
- razonamiento: `high`;
- alternativa: `gpt-5.5` con `high` solo si `gpt-5.6-sol` no puede ejecutarse
  después de un reintento razonable;
- registrar siempre el modelo realmente utilizado;
- no hacer automáticamente la escalera `low -> medium -> high` para un fix
  pequeño ya cubierto por tests;
- usar una revisión temprana adicional solo cuando el diseño sea amplio,
  incierto o cambie contratos.

Modo correcto:

- diff sin commit: `--mode local`;
- commit ya creado: `--mode commit --commit HEAD`;
- varios commits en una rama: `--mode branch --base <base>`.

En Windows usar el binario local de Codex documentado en `AGENTS.md` si el shim
del `PATH` falla con `WinError 5`.

## Uso de clawpatch fix

No se usó `clawpatch fix` para los cambios sensibles de este ciclo.

`fix` puede considerarse únicamente después del triage para un finding aceptado,
localizado y mecánico, con autorización explícita, worktree limpio y tests
enfocados. ARCA, CAE, fechas, lotes, migraciones, borrados, certificados, PDFs
fiscales, reportes e aislamiento multiemisor se corrigen manualmente.

## Aprendizajes de herramientas

- Usar la CLI global `clawpatch`, sin pin de versión.
- Preferir los scripts `npm run clawpatch:<slice>:...`.
- `--state-dir` elige almacenamiento; `--root` elige alcance.
- Mantener `--root`, `--state-dir` y `--config` coherentes durante todo el ciclo.
- En Windows, los scripts locales preservan el wrapper de Codex necesario.
- El incidente de permisos de `.tmp` y su resolución están documentados en
  `2026-07-06-lecciones-operativas.md`.
- Los estados crudos, reportes detallados y evidencia privada permanecen
  ignorados; solo se versionan cierres sanitizados.

## Aprendizaje del despliegue

El preflight inicial comparó el target con un commit reciente que no era el
commit realmente desplegado. Eso llevó a afirmar incorrectamente que no habría
migraciones, dependencias ni cambios de compose.

Reglas permanentes:

1. Registrar el SHA real de producción.
2. Comparar exactamente `<desplegado>..<objetivo>`.
3. Enumerar migraciones, dependencias, Docker/compose, configuración y esquema.
4. Si aparece una migración inesperada después de aplicarla, mantener
   mantenimiento y diagnosticar; no hacer downgrade automático.
5. Revisar `upgrade`, `downgrade`, efectos sobre datos, constraints, `current`,
   `heads` y restauración del backup.
6. Continuar solo si la migración pertenece al rango aprobado y las invariantes
   quedan sanas.
7. Revertir solo con una razón técnica comprobada y un procedimiento de datos
   seguro.
8. Un tag publicado y desplegado es inmutable. Una corrección de código requiere
   una versión nueva; una corrección solo documental puede avanzar en `main` sin
   redespliegue.

## Consolidación de bitácoras

`docs/agents/current-status.md` y `docs/agents/manual-qa.md` se redujeron a
estado y QA accionables para evitar que una sesión nueva cargue miles de líneas
históricas. Los microcheckpoints anteriores no son fuente vigente, pero siguen
disponibles en Git en el commit documental previo:

```powershell
git show ece2bdf:docs/agents/current-status.md
git show ece2bdf:docs/agents/manual-qa.md
```

Consultar ese material solo para investigación histórica; para decisiones
actuales usar los documentos vivos.
## Punto de reanudación

La primera tarea técnica recomendada es el P1 estructural de presión
UI/pool/worker en lotes grandes. Después se retoma el backlog Clawpatch
`medium`/`low` en lotes pequeños y triados manualmente.

La guía vigente para continuar es:

- `docs/agents/current-status.md`;
- `ROADMAP.md`;
- `docs/project/audits/clawpatch/README.md`;
- `docs/agents/fiscal-change-checklist.md`;
- `docs/agents/production-workflow.md`.