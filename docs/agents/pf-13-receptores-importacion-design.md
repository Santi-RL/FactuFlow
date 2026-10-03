# PF-13 — fidelidad del receptor en importación fiscal

Fecha: 03/10/2026.

Estado: alcance y prioridad aceptados para planificación; implementación
pendiente. Este documento no acredita una corrección aplicada ni autoriza
emisiones, acceso a producción o despliegue.

## Problema y justificación

La revisión del flujo confirmó dos reglas que deben corregirse juntas:

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
el 03/10/2026; verificar normativa, catálogos y versión aplicable antes de
implementar. No convertir estas referencias en consultas externas por cada fila.

La evidencia privada permanece fuera del repositorio público. No copiar datos
de clientes, archivos reales, comprobantes ni identificadores a este diseño.

## Prioridad y coordinación

**P1 fiscal, Ahora 1:** el riesgo de perder identificación o rechazar una
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

## Compatibilidad y preparación antes de implementar

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
| Excel con condición distinta de una constante efectiva | Diferencia visible y corrección previa; no sustituye silenciosamente. |
| A, RI/monotributo; B, exento; C con condiciones soportadas | Conserva la matriz y requisitos fiscales vigentes. |
| Varias filas del mismo comprobante | Identificación obligatoria según total del grupo, sin inconsistencias entre ítems. |
| Plantillas legacy y lotes ya preparados | Transición explícita; historial, snapshots y huellas conservados. |
| Duplicados, concurrencia, reintento parcial y resultado incierto | Mantiene comparación, autorizados previos, reservas y reconciliación; nunca duplica CAE. |
| Otro emisor, cambio de contexto y respuestas tardías | No cruza datos ni aplica una configuración ajena. |

Antes de implementar completar el [checklist fiscal](fiscal-change-checklist.md)
y la [puerta de calidad Nivel 2](change-quality-gates.md), incluida la matriz de
consumidores, pruebas de error/concurrencia y revisión exigida por el runbook.
Esta actualización de planificación es Nivel 0 y no constituye validación del
comportamiento futuro. Al implementar, actualizar QA, manual de usuario, API y
changelog según el cambio efectivo.
