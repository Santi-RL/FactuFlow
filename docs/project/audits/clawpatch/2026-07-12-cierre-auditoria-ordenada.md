# Cierre sanitizado de auditoría Clawpatch — 2026-07-12

## Alcance

Se ejecutó una auditoría completa y secuencial de `repo`, `backend` y
`frontend` con Clawpatch `0.7.0`, proveedor Codex, modelo `gpt-5.6-sol` y
razonamiento `high`. No se ejecutó `clawpatch fix`, no se modificó código de
producto, no se solicitaron CAE y no se hicieron llamadas reales a ARCA.

El orden aplicado fue:

1. preflight de Git, versión y proveedor;
2. validación de seeds y regeneración de mapas;
3. `repo` con `jobs=1`, reporte y triaje;
4. primer lote backend con `jobs=1`, reporte y triaje;
5. lote backend controlado con `jobs=2`;
6. cierre de backend y frontend con `jobs=2`;
7. consolidación sanitizada y actualización del runbook.

## Resultado operativo

- `repo`: 27 features registradas; la pasada revisó 15 y produjo 22 findings
  brutos. Después del triaje quedaron 16 abiertos: 5 `high`, 4 `medium` y 7
  `low`.
- `backend`: ledger reconstruido y limpio antes de revisar; 128 features
  revisadas en lotes de 50, 50 y 28. Se registraron 137 findings brutos y,
  después de retirar 36 duplicados o falsos positivos, quedaron 101 abiertos:
  25 `high`, 52 `medium` y 24 `low`.
- `frontend`: 21 features registradas; 19 requerían revisión nueva. El ledger
  acumulativo quedó con 30 findings abiertos: 6 `high`, 20 `medium` y 4 `low`.
- Los tres slices terminaron sin locks y con `review --dry-run` igual a cero
  features pendientes.

Los 147 registros abiertos no equivalen a 147 bugs independientes. Persisten
duplicados entre slices y findings de cobertura o contrato que deben agruparse
por causa raíz antes de planificar reparaciones. El triaje realizado sí retiró
duplicados exactos dentro de cada slice y alertas refutadas por código, tests,
migraciones o decisiones explícitas del repositorio.

## Familias que requieren decisión priorizada

Sin publicar detalles explotables ni convertir el informe en plan de fixes, los
hallazgos de mayor riesgo se concentran en:

- invariantes posteriores a respuestas de ARCA, CAE y reconciliación;
- preservación histórica de PDFs y reportes fiscales;
- concurrencia e integridad en certificados, archivos y cache WSAA;
- aislamiento y transición segura del emisor activo;
- consistencia de exportaciones, backups y liberación de almacenamiento;
- bootstrap, autenticación y autorización administrativa;
- validación fiscal y cobertura de emisión individual y masiva.

Estas familias deben cruzarse con el P1 fiscal ya planificado y dividirse en
cortes verticales pequeños. No corresponde reparar por severidad automática ni
usar el contador global como backlog ejecutable.

## Evidencia local

Los reportes crudos quedaron únicamente bajo
`.tmp/clawpatch/2026-07-12/`. El archivo del ledger backend anterior quedó en
`.tmp/clawpatch/archive/backend-ledger-2026-07-12.zip`, con SHA-256
`F4F02FDF83A6DFFFB7FF99AC301869B90D369BE2D11F64F1E75025C69633D49D`.

Toda esa evidencia está ignorada por Git. Este documento conserva solo el
resumen operativo sanitizado.

## Rendimiento observado

- Backend, 50 features, `jobs=1`: 1881,1 s.
- Backend, 50 features, `jobs=2`: 645,6 s.
- Backend, 28 features, `jobs=2`: 396,8 s.
- Frontend, 19 features, `jobs=2`: 459,0 s.

La comparación no es un benchmark homogéneo porque las features tienen costos
distintos. Sí demuestra que `jobs=2` fue estable en este entorno: no produjo
timeouts, errores del proveedor ni locks. El runbook conserva una escalada
controlada y no generaliza automáticamente el resultado.

## Punto de reanudación

1. No ejecutar `clawpatch fix` ni empezar reparaciones en masa.
2. Elegir una familia prioritaria y volver a validar cada finding contra código,
   tests, visión y checklist fiscal.
3. Para cambios fiscales o de datos sensibles, diseñar invariantes, estados,
   fallos intermedios, migraciones y matriz de tests antes de editar.
4. Implementar un corte pequeño, ejecutar validaciones enfocadas y usar
   `autoreview` solo con confirmación explícita.
5. Revalidar con Clawpatch después de varios cortes coherentes, no después de
   cada ajuste trivial.
