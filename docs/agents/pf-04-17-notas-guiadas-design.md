# PF-04/PF-17/PF-13 — notas de crédito y débito guiadas

Fecha: 03/10/2026.

Estado: planificación aceptada; implementación pendiente. P2 fiscal y de
usabilidad, Más adelante. Consume evidencia histórica mínima PF-04 y preparación
común; no espera importar toda la historia externa PF-05.

## Resultado

Desde un comprobante autorizado, «Crear nota de crédito» o «Crear nota de débito»
prepara el asociado y los datos compatibles del original. El usuario elige el
alcance/importe, indica una fecha explícita, revisa y confirma mediante el flujo
irreversible vigente. Reduce errores de referencia y carga repetida.

El backend ya admite comprobantes asociados. Esta iniciativa agrega un flujo
administrativo y validaciones compartidas, no un segundo motor de emisión.

## Contrato y límites

- Consultar el original local y su evidencia histórica, con autorización y emisor
  activo. Conservar identidad del receptor, clase, moneda/cotización y referencia
  del original como punto de partida, sin reconstruirlos desde la ficha actual.
- Definir con WSFE qué datos deben conservarse y cuáles corresponden a la nueva
  operación, incluida condición IVA efectiva cuando cambió la situación registral.
  La consulta al padrón no reescribe la factura original ni cambia en silencio
  la nota ya preparada.
- Validar tipo/clase de nota, emisor y receptor, punto de venta de emisión y
  referencia asociada. No confundir PV del original con PV de la nota; ambos
  tienen sus propias reglas. Original inexistente, no autorizado o de otro
  emisor no produce una nota confirmable.
- Para crédito, hacer explícita la selección total o parcial y qué componentes
  se corrigen. Para débito, pedir el ajuste nuevo; no copiar automáticamente un
  importe como devolución total ni aplicar un tope universal de crédito a débito.
- Recalcular con el dominio fiscal común; notas mixtas o parciales respetan bases,
  IVA, moneda, tributos y asociados soportados. Conservar fecha explícita,
  confirmación, numeración, idempotencia, duplicados e incertidumbre vigentes.
- Mostrar importe original y notas conocidas cuando exista evidencia suficiente.
  No prometer «saldo disponible» global si hay notas emitidas fuera de FactuFlow
  o historia incompleta. Una nota guiada no implementa cuentas corrientes,
  conciliación bancaria ni devoluciones de dinero.
- Crear una nueva solicitud y una nueva clave; la identidad del original no
  sustituye idempotencia de la nota. Una repetición detectada consume el control
  existente y una nota incierta se reconcilia, sin reemisión automática.

## Interacciones

| Línea | Relación |
|---|---|
| PF-04 | Snapshot mínimo del original y cobertura histórica; el primer consumidor implementa sólo lo necesario |
| [Importes/previsualización](pf-03-04-importes-previsualizacion-design.md) | Preparación y revisión compartidas; categorías adicionales se incorporan cuando tengan soporte completo |
| [Plantillas PF-13](pf-13-plantillas-contables-design.md) | Reutiliza la misma validación de NC/ND y asociados, aunque su entrada sea Excel |
| [Padrón](pf-18-09-padron-clientes-emisores-design.md) | Datos actuales separados de evidencia original; no es consulta obligatoria al solicitar CAE |
| PF-17/PF-14 | Acción desde historial, permisos, respuesta tardía y errores comprensibles |

## Aceptación antes de implementar

- Factura A/B/C, crédito parcial/total y débito; períodos y asociados correctos,
  moneda y desglose iguales al resultado preparado.
- Original de otro emisor, sin CAE, incompleto, modificado desde una sesión antigua
  y cliente cuya ficha/condición cambió; no mezclar historia con datos actuales.
- Dos preparaciones simultáneas, doble clic, replay y nota con resultado incierto;
  controles existentes activos y ninguna emisión de prueba real.
- Referencia correcta en pedido, persistencia, PDF e informes; notas de crédito
  conservan el tratamiento del dashboard existente.
- Cerrar reglas oficiales de asociación, alcance parcial/total, condición
  efectiva y cobertura antes de codificar; completar checklist fiscal y diseñar
  rollback. Un nuevo control obligatorio fuera de las garantías existentes
  conserva la decisión de producto de `VISION.md`.

Referencia: [manual WSFE oficial](https://www.arca.gob.ar/ws/documentacion/manuales/manual-desarrollador-ARCA-COMPG.pdf),
consultado el 03/10/2026; verificar reglas vigentes al delimitar el corte.
