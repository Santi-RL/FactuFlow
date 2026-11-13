# PF-04/PF-17/PF-13 — notas de crédito y débito guiadas

Última revisión: 13/11/2026.

Estado: contrato del corte individual. Ahora 1, P1 por bloqueo operativo y máxima
prioridad de ejecución por decisión del usuario. Consume evidencia histórica
mínima PF-04 y preparación común; no espera importar toda la historia externa
PF-05 ni terminar la reconciliación moderna. La prioridad no omite las puertas
fiscales, de revisión, release y despliegue vigentes.

## Resultado

Desde un comprobante autorizado, «Crear nota de crédito» o «Crear nota de débito»
prepara el asociado y los datos compatibles del original. El usuario elige el
alcance/importe, indica una fecha explícita, revisa y confirma mediante el flujo
irreversible vigente. Reduce errores de referencia y carga repetida.

Desde «Nuevo comprobante», que reemplaza «Nueva factura», el usuario elige
factura, nota de crédito o nota de débito. Para una nota se identifica el original
y se continúa por la misma preparación que desde la factura. El selector ofrece
las clases compatibles con el emisor y el original; no exige códigos de ARCA.
La emisión masiva conserva su acceso y alcance actuales.

El backend ya admite comprobantes asociados. Esta iniciativa agrega un flujo
administrativo y validaciones compartidas, no un segundo motor de emisión.

## Encuadre de interfaz

- Tarea y audiencia: emitir un comprobante puntual para personal administrativo
  y contable; modo Operate, conservando componentes y jerarquía existentes.
- Acceso general: «Nuevo comprobante» mantiene la acción principal del listado.
  En el formulario, el tipo determina si corresponde identificar una factura.
- Acceso contextual: desde el detalle de una factura autorizada, «Crear nota de
  crédito» y «Crear nota de débito» llevan al mismo formulario con el original
  preparado. No solicitan CAE ni confirman una emisión al navegar.
- Preparación: mostrar el original, receptor e importe; para NC elegir alcance
  total o parcial y revisar el detalle. Para ND ingresar el ajuste nuevo. La
  fecha de la nota queda vacía hasta que el usuario la indique.
- Revisión: conservar vista previa, totales y confirmación irreversible vigentes,
  incluyendo el asociado. Verificar carga, vacío, error, éxito, cambio de emisor,
  teclado, foco y adaptación a tamaños de escritorio y móvil.

El alcance nuevo se declara en la solicitud individual. Los consumidores
técnicos anteriores sin `alcance_nota` conservan su contrato y las validaciones
existentes; no se agrega un campo obligatorio a lotes o a esas integraciones.
El campo ausente se omite al serializar para no alterar sus hashes idempotentes.

## Originales externos y preparación fiscal

- La primera salida incluye facturas externas por decisión del usuario. Se
  identifican por clase, punto de venta y número bajo el CUIT del emisor activo.
  Consultar el original con FECompConsultar sin insertarlo en el historial local.
  La consulta no acredita nombres, domicilios ni descripciones comerciales:
  esos datos se completan explícitamente y no se inventan desde importes.
- Se conserva la condición IVA como dato explícito, compatible con la clase de
  la nota. No se consulta el padrón al emitir ni se cambia la factura histórica.
  El checklist siguiente identifica consumidores, errores e incertidumbre.

## Checklist fiscal del corte

- Alcance: preparación y emisión individual NC/ND A/B/C en pesos, desde original
  local autorizado o externo verificable por WSFE. No modifica los consumidores
  batch, reintentos masivos, certificados, reservas ni recuperación moderna.
  Mantiene el dominio de importes soportado; no reclasifica exento/no gravado.
- Autoridad: manual WSFE v4.7 del 01/09/2026, revalidado el 13/11/2026,
  asociación 10040 y 10197, y RG 4540/2019, artículos 2 y 3. El plazo desde el
  hecho que motiva el ajuste no se calcula desde la fecha de la factura.
- Invariantes: mismo emisor, receptor identificable y clase del original;
  moneda/cotización conservadas; fecha explícita no anterior al original;
  referencia asociada exacta, revisión y confirmación irreversible vigentes.
  El PV de emisión se elige entre los habilitados, separado del PV original.
- Orden: preparar original; completar ajuste; revisar; confirmar; resolver replay
  antes de consultas mutables; validar nuevamente la asociación para una operación
  nueva; continuar por la reserva durable y el motor existente. Preparar/consultar
  nunca solicita CAE ni reserva números.
- Concurrencia: conserva el lock y la unicidad de operación/intento existentes.
  Doble clic o misma clave/payload retorna el resultado previo; payload diferente
  produce conflicto. El cambio de original, tipo, alcance, receptor o importe
  invalida revisión/confirmación. Respuestas tardías se descartan tras cambio de
  emisor, original o desmontaje.
- Fallos: original ausente, no autorizado, incompleto o distinto impide preparar
  la nota y no solicita CAE. Un error de consulta no significa rechazo del
  comprobante. Después de una posible autorización se conserva incertidumbre y
  se verifica con la misma operación; no se reemite automáticamente.
- Persistencia y consumidores: el asociado forma parte de la solicitud WSFE y
  de la evidencia previa ya versionada; detalle y PDF leen esa misma evidencia.
  No se reescribe ni completa artificialmente la historia legacy. Reportes
  conservan el tratamiento vigente de NC/ND y monedas.
- Pruebas: A/B/C locales/externos, crédito total/parcial y débito; originales
  ajenos, desconocidos o incompletos; receptor/referencia adulterados; mismo
  total con IVA diferente; cambio de emisor y respuestas tardías; replay,
  concurrencia e incertidumbre por el motor vigente; asociado en WSFE y PDF.
- Recuperación: sin nueva migración ni importación histórica; rollback por SHA
  con conservación de evidencia/notas ya autorizadas, sin repetir emisiones.
  Cerrar suites, QA visual sintética, autoreview y puertas de release antes de
  declarar el candidato listo. No se realizan pruebas con CAE real.

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

## Aceptación antes de publicar

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

Referencias revalidadas el 13/11/2026:
[manual WSFE oficial v4.7](https://www.arca.gob.ar/ws/documentacion/manuales/manual-desarrollador-ARCA-COMPG.pdf)
y [RG 4540/2019](https://biblioteca.arca.gob.ar/search/query/norma.aspx?p=t:RAG%7Cn:4540%7Co:3%7Ca:2019%7Cf:31/07/2019).
