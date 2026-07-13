# Checklist de diseño fiscal crítico

Este checklist es obligatorio antes de implementar una nueva funcionalidad,
corrección o mejora que pueda afectar emisión fiscal, ARCA/WSFE, CAE,
numeración, fechas fiscales, comprobantes, lotes, reintentos, reconciliación,
certificados, puntos de venta, migraciones fiscales o aislamiento entre
emisores.

El objetivo es detectar riesgos en el diseño, no al final del diff. FactuFlow
debe ser sólido, seguro y confiable porque un error puede emitir comprobantes
incorrectos con consecuencias impositivas y legales.

## 1. Alcance y riesgo

- Describir qué flujo cambia: emisión individual, lote, reintento,
  reconciliación, consulta, migración, UI, API o servicio.
- Indicar si el cambio puede solicitar CAE directa o indirectamente.
- Indicar si toca fecha fiscal, punto de venta, tipo de comprobante,
  numeración, receptor, total, ítems, comprobantes asociados, CAE,
  certificado, emisor activo o datos migrados.
- Identificar qué ocurriría si el cambio falla: comprobante duplicado,
  comprobante incorrecto, numeración reservada, CAE no persistido, mezcla de
  emisores, pérdida de trazabilidad, bloqueo operativo o exposición de datos.

## 2. Invariantes no negociables

Completar los invariantes específicos del cambio. Como mínimo, revisar:

- Nunca asumir la fecha actual como fecha fiscal.
- No solicitar CAE sin confirmación irreversible de fecha fiscal y punto de
  venta cuando aplique.
- No solicitar CAE sin `X-Idempotency-Key` en caminos fiscales.
- Misma clave idempotente y mismo payload no debe llamar dos veces a ARCA.
- Misma clave idempotente y payload distinto debe responder conflicto.
- Ningún flujo puede mezclar clientes, certificados, puntos de venta,
  comprobantes, lotes, PDFs, reportes, perfiles o formatos entre emisores.
- Todo resultado incierto post-CAE debe quedar reconciliable, no reintentable de
  forma automática.
- La numeración fiscal no se libera por errores ambiguos de ARCA.
- Un cambio de datos fiscales debe invalidar confirmaciones y claves de
  idempotencia vigentes.

## 3. Estados y transiciones

Para cada entidad afectada, documentar los estados relevantes y sus
transiciones permitidas.

Entidades habituales:

- operación idempotente;
- intento de emisión fiscal;
- comprobante;
- lote;
- grupo de lote;
- certificado;
- punto de venta;
- migración o job.

Para cada transición, responder:

- ¿Quién la ejecuta: UI, API, servicio, worker, migración o reconciliador?
- ¿Qué lock, constraint o validación la protege?
- ¿Qué pasa si falla antes de ARCA?
- ¿Qué pasa si falla después de ARCA pero antes de persistir?
- ¿Qué estado queda si el proceso se corta a mitad?
- ¿Puede reanudarse? ¿Debe reconciliarse antes?

## 4. Orden de operaciones

Definir el orden exacto antes de codificar. Para caminos que pueden solicitar
CAE, revisar especialmente:

- validación de emisor activo y pertenencia de entidades;
- validación de fecha fiscal explícita;
- confirmación irreversible;
- idempotency key y payload hash;
- locks o reservas de numeración;
- persistencia durable previa a ARCA;
- llamada ARCA;
- persistencia de CAE y comprobante;
- actualización de lote/grupo/contadores;
- respuesta idempotente persistida.

Si existe replay, definir si se evalúa antes o después de validaciones mutables
y justificarlo.

## 5. Fallos intermedios

Enumerar los fallos relevantes y el estado esperado:

- request duplicado en paralelo;
- doble click o retry de frontend;
- misma clave con payload diferente;
- operación existente sin respuesta persistida;
- intento `en_proceso` no stale;
- intento `en_proceso` stale;
- ARCA rechaza sin CAE;
- ARCA devuelve CAE y falla la persistencia;
- ARCA responde error ambiguo;
- worker encola pero no ejecuta;
- lote cambia de estado entre replay y procesamiento;
- migración encuentra datos legacy duplicados;
- frontend recibe error estructurado;
- usuario cambia datos fiscales después de confirmar.

## 6. Concurrencia y constraints

Verificar explícitamente:

- qué operaciones deben ser atómicas;
- qué actualización requiere compare-and-swap;
- qué constraint de base protege duplicados reales;
- qué índice parcial reserva numeración activa;
- cómo se comporta SQLite y PostgreSQL si ambos son relevantes;
- qué ocurre si dos procesos intentan tomar el mismo lote, grupo, operación o
  número planificado.

## 7. Contratos externos ARCA

Si el cambio depende de ARCA:

- documentar método involucrado: `FECAESolicitar`, `FECompConsultar`,
  `FECompUltimoAutorizado`, `FECompTotXRequest` u otro;
- no inferir autorización si no hay CAE;
- no liberar numeración por mensajes genéricos;
- preferir códigos explícitos y mensajes exactos cuando se interpreten errores;
- revisar documentación local en `docs/arca-ws/` y notas en
  `docs/arca-ws/NOTAS.md`;
- no hacer llamadas reales a ARCA en pruebas automatizadas.

## 8. Matriz mínima de tests

Antes de implementar, listar pruebas automatizadas esperadas. Para cambios
fiscales críticos, cubrir al menos:

- flujo feliz;
- clave ausente o confirmación ausente;
- replay con misma clave;
- conflicto con misma clave y payload distinto;
- carrera/concurrencia relevante;
- falla pre-CAE;
- falla post-CAE;
- estado incierto y reconciliación;
- validación multiemisor;
- migración con datos legacy cuando aplique;
- UI: generación, reutilización y reset de claves o confirmaciones.

Si un invariante no se testea, dejar una justificación explícita.

## 9. Uso de autoreview

`autoreview` no reemplaza el diseño ni el criterio del agente. Se usa para
encontrar contratos rotos, casos omitidos y riesgos que el autor no vio.

Antes de escribir código, aplicar esta misma rúbrica al diseño y a la matriz de
tests. Para un diseño amplio o incierto puede pedirse una revisión temprana,
pero un fix pequeño ya cubierto por regresiones no necesita una escalera
automática de niveles.

Para cambios fiscales críticos confirmados por el usuario:

1. Diseñar invariantes y tests antes o junto al código.
2. Corregir solo hallazgos aceptados después de verificarlos en el código real.
3. Ejecutar pruebas enfocadas y controles del área.
4. Hacer la revisión final directamente con `gpt-5.5` y `high`.
5. Si la revisión provoca cambios, repetir pruebas enfocadas y la revisión.
6. Cuando quede limpia, detenerse; no correr otra opinión redundante.

Comando Windows habitual para un diff sin commit:

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
$autoreview = Join-Path $env:USERPROFILE '.codex\skills\autoreview\scripts\autoreview'
$codexBin = Join-Path $env:LOCALAPPDATA 'OpenAI\Codex\bin\codex.exe'
python $autoreview --mode local --engine codex --model gpt-5.5 --thinking high --codex-bin $codexBin
```

Para un commit ya creado, reemplazar `--mode local` por
`--mode commit --commit HEAD`.

## 10. Manejo de hallazgos

Cada hallazgo debe clasificarse antes de tocar código:

- Aceptado: bug real, riesgo fiscal, regresión, contrato roto, carrera,
  pérdida de trazabilidad, fuga de datos, mezcla de emisores o test faltante
  relevante.
- Rechazado: edge case irreal, recomendación especulativa, refactor excesivo,
  cambio fuera de alcance o hallazgo basado en una premisa incorrecta.
- Diferido: riesgo real pero fuera del alcance seguro del cambio actual; debe
  quedar documentado en roadmap o estado operativo si corresponde.

Al aceptar un hallazgo:

- corregir el bug class completo dentro del alcance tocado;
- buscar casos hermanos en rutas vecinas;
- agregar o ajustar tests;
- repetir pruebas enfocadas;
- volver a correr `autoreview` en el nivel apropiado.

No corregir automáticamente todo lo que proponga `autoreview`. La corrección
debe reducir un riesgo concreto sin sobredimensionar el diseño.

## 11. Cierre

Antes de dar por terminado un cambio fiscal crítico:

- verificar tests backend y frontend relevantes;
- ejecutar formato/lint/type-check según el área tocada;
- confirmar que la documentación viva quedó actualizada;
- revisar `git status --short --untracked-files=all`;
- revisar que no haya datos privados, CAEs reales, CUITs reales ni evidencia
  local versionable;
- recomendar commit y push separados si el cambio está completo.
