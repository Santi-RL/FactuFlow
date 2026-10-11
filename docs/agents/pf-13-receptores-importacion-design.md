# PF-13 — fidelidad del receptor en importación fiscal

Última revisión: 09/10/2026.

Estado: corte P1 implementado. La transición fue autorizada el 09/10/2026.
Este contrato no acredita publicación, emisiones ni un despliegue.

## Problema y justificación

La revisión confirmó dos reglas corregidas conjuntamente por este corte:

- `FormatosImportacionService._armar_fila_canonica` descarta el documento cuando
  la condición es consumidor final y el importe está bajo el umbral de
  identificación obligatoria.
- La validación de grupos de `LoteComprobantesService` rechaza CUIT con condición
  consumidor final. El camino individual de normalización conserva el documento
  informado, por lo que los caminos no tienen una conducta coherente.

Identificación y condición fiscal son datos diferentes. La combinación
CUIT/CUIL con consumidor final es válida; disponer de un documento no prueba
inscripción en IVA o monotributo. No estar obligado a identificar tampoco obliga
a borrar una identificación suministrada. Una plantilla con condición fija
puede ocultar la falta de una condición por fila y producir un resultado distinto
del esperado, aunque el comprobante sea autorizado.

La [RG 5866/2026, artículo 1°, inciso f](https://www.argentina.gob.ar/normativa/nacional/norma-427092/texto),
vigente desde julio de 2026 para ese inciso, contempla consumidores finales
identificados y exige CUIT sin considerar el importe cuando se solicita para
computar una deducción en Ganancias. El
[manual oficial WSFE](https://www.arca.gob.ar/ws/documentacion/manuales/manual-desarrollador-ARCA-COMPG.pdf)
separa tipo/número de documento y condición IVA del receptor. Fuentes consultadas
el 03/10/2026 y contrastadas el 09/10/2026. No convertir estas referencias en
consultas externas por cada fila.

La evidencia privada permanece fuera del repositorio público. No copiar datos
de clientes, archivos reales, comprobantes ni identificadores a este diseño.

## Prioridad y coordinación

**P1 fiscal cerrado:** el riesgo de perder identificación o rechazar una
combinación fiscal válida está demostrado. Se atiende antes de recuperación y
trazabilidad; no se clasifica como P0 porque esta planificación no acredita un
incidente activo. No requiere completar el constructor contable ni la UI compacta.

| Línea relacionada | Límite del corte |
|---|---|
| [Plantillas contables PF-13](pf-13-plantillas-contables-design.md) | Consume esta regla de receptor. Tipo/letra, controles de importes y alias de condición fiscal permanecen P2, Más adelante. |
| [Duplicados PF-13/PF-17](pf-13-duplicados-lotes-design.md) | Conserva identidad de entrada, comparación y excepciones. Preservar el documento fiscal no crea otro motor ni altera huellas históricas. |
| [Parche RG 5616](rg-5616-condicion-iva-receptor-parche.md) | Conserva condición válida y compatible con la clase. Este corte corrige la identificación; no elimina esa garantía ni reinterpreta su cierre. |
| [UI de lotes PF-17](pf-17-lotes-ui-design.md) | Presenta procedencia y valores efectivos; el rediseño P2 no es requisito para esta corrección fiscal. |
| [Padrón de clientes/emisores](pf-18-09-padron-clientes-emisores-design.md) | Incorporación posterior de evidencia registral ARCA, separada de identificación y condición de operación. Este P1 no espera padrón ni consulta por fila. |
| PF-04/PF-05 y PF-11/PF-15 | No reconstruye comprobantes históricos ni cambia políticas de backup. Conservar el respaldo y rollback proporcionados al cambio futuro. |

## Resultado aceptado e invariantes

1. Conservar tipo y número del documento informado y el nombre del receptor en
   importación, validación, solicitud fiscal y PDF, admitiendo combinaciones
   válidas de consumidor final identificado.
2. Distinguir CUIT de CUIL y DNI. Un número de once dígitos no basta para decidir
   entre CUIT y CUIL. Resolver el tipo desde el archivo o una configuración
   explícita; no intercambiar códigos. Este corte no incorpora consultas de padrón.
3. Resolver condición IVA desde una columna o un valor fijo explícito para un
   archivo homogéneo. No inferirla por número, tipo de documento o letra del
   comprobante, ni sustituir una celda fiscal inválida por consumidor final.
   La integración posterior de padrón consume este contrato y trata diferencias
   con evidencia registral explícita; no agrega inferencias a este P1.
4. Señalar diferencias reales entre la condición aportada por el archivo y la
   configuración efectiva, con fila, campo y corrección accionable. No usar
   «CUIT + Consumidor Final» como criterio de contradicción ni agregar una
   confirmación rutinaria por esa combinación.
5. Mantener consumidor final sin documento cuando la normativa lo permita, e
   identificación obligatoria cuando corresponda. Evaluar el importe del
   comprobante resultante, no sólo una fila o precio unitario. El umbral no es
   una instrucción para eliminar datos; contemplar requisitos independientes del
   importe, incluido CUIT solicitado para deducción en Ganancias.
6. Mantener las condiciones soportadas y su compatibilidad con A/B/C, requisitos
   de A, asociados, fechas explícitas, importes, confirmación irreversible,
   aislamiento, idempotencia, reservas, concurrencia y reconciliación.
7. Conservar documentos inválidos hasta informar el error; no borrarlos para
   convertir una fila identificada en anónima o hacerla pasar una validación.
8. Ninguna previsualización, importación o prueba solicita CAE. Verificar con
   datos sintéticos la correspondencia del receptor hasta el PDF.

## Compatibilidad preservada

- Inventariar importación configurable y canónica, emisión individual, lote,
  worker, batch, reintentos y generación PDF. Usar una regla coherente de receptor
  sin ampliar el dominio fiscal soportado ni modificar numeración.
- Definir la transición para plantillas legacy que infieren CUIT y para columnas
  de condición con defaults o celdas vacías. Mantener versiones y mostrar el
  origen efectivo; no migrar todas las configuraciones silenciosamente.
- Reutilizar validaciones y procedencia existentes. Delimitar cómo detectar una
  columna fiscal ignorada o reemplazada sin inventar mapeos ni bloquear cualquier
  columna adicional. Un nuevo paso obligatorio o intercambio de protección
  requiere la decisión de producto prevista por `VISION.md`.
- Definir el tratamiento de lotes preparados con reglas antiguas: no corregir
  silenciosamente snapshots, hashes ni confirmaciones. Una corrección de datos
  exige validación y confirmación aplicables antes de una nueva operación.
- Replay terminal, autorizados, intentos activos o inciertos y reconciliación
  conservan la solicitud congelada. No modificar retrospectivamente identidad
  ni contenido fiscal para hacer coincidir nuevas normalizaciones.
- Diseñar rollback de aplicación y compatibilidad antes de codificar; no usar
  migraciones destructivas ni volver a emitir comprobantes históricos.

## Aceptación mínima del corte fiscal

| Caso sintético | Resultado esperado |
|---|---|
| B/C, consumidor final con CUIT válido | Conserva CUIT y condición CF; no hay rechazo por esa combinación. |
| B/C, consumidor final con CUIL o DNI | Conserva el tipo correcto y el número; no lo reclasifica como CUIT. |
| Consumidor final identificado bajo el umbral | Documento y nombre suministrados llegan a solicitud y PDF. |
| Consumidor final sin documento bajo el umbral, sin otro requisito | Conserva la operatoria anónima permitida. |
| Identificación obligatoria por importe o requisito independiente | Faltantes dan error antes de CAE; el importe se evalúa por comprobante. |
| Condición explícita desde columna o constante válida | Mantiene el valor y su origen; no infiere por documento. |
| Condición vacía requerida, desconocida o incompatible; documento inválido | Error por fila/campo, sin fallback CF ni pérdida del dato. |
| DNI con letras o caracteres inválidos, por ejemplo `AB12345678` | Conservar el error; no convertirlo silenciosamente en `12345678`. Verificar representación de otros tipos según WSFE antes de ampliar soporte. |
| Excel con condición distinta de una constante efectiva | Diferencia visible y corrección previa; no sustituye silenciosamente. |
| A, RI/monotributo; B, exento; C con condiciones soportadas | Conserva la matriz y requisitos fiscales vigentes. |
| Varias filas del mismo comprobante | Identificación obligatoria según total del grupo, sin inconsistencias entre ítems. |
| Plantillas legacy y lotes ya preparados | Transición explícita; historial, snapshots y huellas conservados. |
| Duplicados, concurrencia, reintento parcial y resultado incierto | Mantiene comparación, autorizados previos, reservas y reconciliación; nunca duplica CAE. |
| Otro emisor, cambio de contexto y respuestas tardías | No cruza datos ni aplica una configuración ajena. |

El corte aplica el [checklist fiscal](fiscal-change-checklist.md) y la
[puerta de calidad Nivel 2](change-quality-gates.md), incluida la matriz de
consumidores, errores/concurrencia y revisión final. QA, manual de usuario,
API y changelog describen la conducta resultante.

## Contrato implementado

- La importación configurable conserva datos y distingue CUIT, CUIL y DNI
  desde una columna o constante explícita. La condición IVA es obligatoria
  en la configuración; no se usa un default para sustituir una columna ausente.
- Las columnas fiscales reconocidas por encabezados canónicos y sus alias
  habituales no se sustituyen por una constante contradictoria. Una columna
  adicional desconocida no se interpreta automáticamente; debe mapearse para
  incorporarla al contrato del archivo.
- El helper de documento conserva caracteres inválidos hasta informar el error.
  Acepta representación numérica y separadores habituales de CUIT/CUIL y DNI;
  el tipo sin identificar admite sólo número vacío o cero. Excel numérico
  integral conserva sus dígitos; un tipo fraccionario no se trunca.
  `CI` conserva su significado legacy de código `99`, sólo sin identificación;
  no representa una cédula identificada ni permite descartar su número. Una
  cédula informada con ese alias ambiguo requiere corregir el tipo; este corte
  no incorpora ni infiere un código de cédula identificado.
- El grupo y la preparación común conservan CF identificado. La obligación por
  importe se evalúa sobre el total calculado del comprobante; no se descarta un
  documento bajo el umbral. El requisito por deducción se satisface suministrando
  explícitamente CUIT; no se añade un nuevo selector de deducción.
- Lotes, snapshots y huellas persistidos no se migran. La normalización histórica
  usada para verificar hashes permanece separada de las nuevas preparaciones.
  La identidad explícita de nuevas importaciones informa el tipo numérico al
  comparador existente; sus controles de nombre, contenido y reservas continúan.
- PDF y QR consumen el snapshot vigente: número y nombre visibles, tipo correcto
  en el QR. No se modifica su presentación ni se consulta ARCA durante las pruebas.
- El código `99/0` no cambia una condición Exento explícita a CF. Se conserva
  esa compatibilidad; para CF anónimo, cero tampoco permite evitar el umbral.
- No hay cambios de esquema, dependencias ni configuración operativa. Un rollback
  de aplicación no restaura archivos ni reescribe historia y reintroduciría las
  limitaciones originales; preferir una corrección hacia adelante.

## Decisión de transición y checklist del corte del 09/10/2026

Santi autorizó implementar este P1 y exigir corregir una configuración ambigua
antes de una nueva importación. El tipo de documento y la condición IVA se
declaran mediante columna o constante; un documento ausente sigue permitido
para CF cuando corresponde. Una plantilla protegida se clona para configurarla.
No se agregan consultas de padrón, confirmaciones rutinarias ni columnas para
archivos homogéneos que puedan declarar valores fijos.

Checklist fiscal previo a código:

- **Alcance y consumidores:** importación configurable y canónica, validación
  de grupos, preparación individual y masiva, worker y reintentos que consumen
  ese request, PDF y comparación de duplicados. Cambia receptor; no cambia
  fecha, numeración, importes, certificados ni reglas de autorización del emisor.
  El riesgo es perder identificación o transformar un dato inválido en anónimo.
- **Invariantes:** conservar identificación explícita, separar condición IVA,
  respetar compatibilidad A/B/C y total agrupado. Mantener fecha explícita,
  confirmación, idempotencia, aislamiento y reservas; cero llamadas reales a ARCA.
  No alterar hashes, snapshots ni respuestas terminales históricos. La
  normalización histórica usada para hashes conserva exactamente su conducta.
- **Estados y orden:** archivo/configuración → filas normalizadas → validación
  del grupo → request preparado → flujo fiscal vigente. Los errores de receptor
  se detectan antes de crear solicitudes o reservar numeración. Lotes existentes,
  autorizados, intentos activos/inciertos y reconciliación mantienen su evidencia;
  no se reimportan ni corrigen silenciosamente. La UI conserva invalidaciones y
  confirmación vigentes; un archivo corregido requiere una nueva validación.
- **Fallos y concurrencia:** faltantes, contradicciones o documentos inválidos
  producen mensajes por fila/campo. Las carreras, bloqueos de numeración, fallos
  pre/post-CAE y reconciliación siguen en sus servicios; se ejecutan sus pruebas
  de regresión. Esta unidad no crea otro estado ni introduce I/O en normalización.
- **Recuperación:** no hay DDL ni migración de datos. El rollback de código no
  recupera identificación descartada anteriormente; conserva registros y
  evidencia fiscal. Revertir hacia el código anterior reintroduce los defectos,
  por lo que requiere decisión proporcional antes de volver a importar.
- **Autoridad:** RG 5866/2026 y manual WSFE consultados el 09/10/2026. WSFE separa
  DocTipo/DocNro y CondicionIVAReceptorId. Los códigos ya soportados se conservan;
  no se amplía el dominio documental ni se infiere CUIT frente a CUIL.
- **Tests y revisión:** casos de la matriz anterior, Excel real sintético hasta
  request/PDF, origen de campos, plantilla legacy inmutable, documentos inválidos,
  total de varias filas, anónimo, compatibilidad A/B/C, aislamiento, duplicados,
  reintentos e incertidumbre. Suite backend, controles frontend y CI Nivel 2;
  revisión final `autoreview` Codex `gpt-5.6-sol medium` cuando el diff esté estable.

El cambio de presentación argentino P3 y la consulta opcional de padrón recién
planificados mantienen su horizonte; no se incorporan a este P1.
