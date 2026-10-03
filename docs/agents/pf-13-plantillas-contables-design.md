# PF-13 — plantillas contables e interpretación fiscal

Fecha: 04/09/2026.
Última revisión: 03/10/2026.

Estado: alcance incorporado al roadmap; implementación pendiente. Este documento
define el resultado futuro y las decisiones por cerrar, no capacidades actuales.

## Problema y encaje

Un Excel contable puede separar `Tipo de comp.` (`FC`, `NC`, `ND`) y `Letra`
(`A`, `B`, `C`), identificar al receptor y traer neto, IVA y total. El constructor
actual sólo resuelve un campo numérico de tipo de comprobante y no anticipa
todos los requisitos por fila. Configurar valores fijos sirve para archivos
homogéneos, pero no para un archivo mixto.

Este corte pertenece a PF-13, ya aceptado para formatos, perfiles y lotes;
PF-17 aporta claridad y accesibilidad. PF-14 acompaña los contratos y mensajes;
PF-12 sólo interviene si el diseño de persistencia lo necesita. No se crea un
constructor paralelo ni se retoma el rediseño de lotes cerrado en
[`lotes-ux-redesign.md`](lotes-ux-redesign.md). Se mantienen el horizonte «Más
adelante» y P2 para esta ampliación del constructor. El corte acotado P1 de
[fidelidad del receptor](pf-13-receptores-importacion-design.md) se ejecuta antes
y aporta la regla compartida, sin adelantar todo el rediseño.

La evolución posterior de la pantalla de carga se coordina con el
[diseño de UI de lotes PF-17](pf-17-lotes-ui-design.md). Aquel organiza la
presentación; este contrato conserva interpretación, precedencia y validación.

La evidencia y las limitaciones están en la
[`auditoría del proceso`](../project/audits/plantillas-2026-09-04.md).
La propuesta respeta [`VISION.md`](../../VISION.md): conocimientos contables,
sin programación, códigos internos ni nuevas confirmaciones rutinarias.

La garantía compartida de condición IVA válida se resuelve antes en el
[parche RG 5616](rg-5616-condicion-iva-receptor-parche.md). Este diseño la
reutiliza; la ampliación del constructor conserva su horizonte y alcance.

La revisión posterior del receptor confirmó pérdida de identificación y rechazo
de CUIT con consumidor final. Son defectos separados de la matriz RG 5616; su
corrección se concentra en el diseño P1. Este corte P2 reduce además correcciones
manuales de etiquetas equivalentes y permite detectar valores fijos o perfiles
que no representan el Excel antes de preparar una emisión.

## Resultado aceptado

1. Construir una plantilla reutilizable para facturas, notas de crédito y notas
   de débito, con tipo y letra en columnas separadas o con valores fijos
   explícitos cuando corresponda.
2. Leer CUIT y condición IVA del receptor desde columnas. Si la plantilla admite
   A, exigir la configuración de ambas columnas para este modo de archivo mixto;
   en cada fila A exigir un CUIT presente y válido y una condición admitida.
3. Mostrar, dentro del constructor, cómo se interpretará una muestra del archivo:
   comprobante resultante, receptor, fecha, punto, concepto, neto, IVA y total.
   La muestra no crea un lote ni requiere certificado o una conexión fiscal.
4. Distinguir datos del archivo, valores fijos y ajustes del perfil/lote. Una
   columna sin usar debe quedar identificada como tal; ningún valor de ejemplo
   completa datos fiscales.
5. Detectar errores antes de la confirmación de emisión, con mensajes contables
   que indiquen fila, encabezado y corrección necesaria.
6. Conservar nombre/documento y procedencia para el control de duplicados de
   emisión masiva. Las repeticiones anónimas internas y las coincidencias con
   lotes anteriores se tratan según el diseño específico enlazado abajo.
7. Aceptar alias inequívocos de condición fiscal, incluido «Monotributista» como
   «Monotributo», espacios redundantes y diferencias de mayúsculas. Normalizar
   vocabulario no autoriza inferir inscripción ni aceptar etiquetas desconocidas.

## Decisión de producto: duplicados y receptor identificable

El contrato completo se concentra en
[prevención de duplicados en lotes](pf-13-duplicados-lotes-design.md): identidad
por nombre o documento dentro del lote, coincidencia de conjuntos con historia
autorizada, presentación del usuario que solicitó la emisión, retorno principal
y excepción con checkbox. Incluye casos anónimos, revalidación y coordinación
simultánea.

Este diseño de plantillas conserva la responsabilidad de leer la identidad y
su procedencia sin pérdidas. La normalización que descarta documentos de
consumidores finales y el rechazo general de CUIT con CF se corrigen en el
[corte P1 de receptor](pf-13-receptores-importacion-design.md); el contrato de
duplicados conserva su comparación y la identidad de entrada. No inventar
identidad ni cambiar implícitamente el dato fiscal enviado a ARCA.
Las huellas históricas de idempotencia y reconciliación permanecen inmutables.

## Contrato contable

La [preparación fiscal común](pf-03-04-importes-previsualizacion-design.md) es dueña
del cálculo decimal y de sus categorías. La muestra de esta plantilla consume
sus importes y errores; no introduce otro cálculo ni cambia redondeos PF-03B.
Cuando exista [padrón](pf-18-09-padron-clientes-emisores-design.md), su consulta
anticipada/agrupada y procedencia registral se integran en preparación, sin
consultas obligatorias por fila o al solicitar CAE. Mantener datos explícitos y
solicitudes congeladas. Las [notas guiadas](pf-04-17-notas-guiadas-design.md)
comparten validación de asociados con esta entrada Excel.

### Tipo y letra

La persona elige «Tipo y letra en columnas separadas», «Tipo completo» o «Valor
fijo» según su archivo. Los nombres finales de los controles se validarán en QA.
La conversión al contrato canónico ocurre en el importador, antes de aplicar
opciones del lote y agrupar; el worker consume el tipo numérico ya resuelto.

| Tipo | A | B | C |
|---|---|---|---|
| FC / Factura | 1 | 6 | 11 |
| ND / Nota de débito | 2 | 7 | 12 |
| NC / Nota de crédito | 3 | 8 | 13 |

La tabla describe tipos ordinarios ya soportados. No habilita por sí sola a un
emisor ni incorpora facturas de crédito MiPyME, M, E u otros regímenes. `FC`
significa Factura en esta modalidad; no se interpreta como factura de crédito.
Se aceptan variantes documentadas de mayúsculas, espacios y acentos; valores
desconocidos, fraccionarios, vacíos requeridos o contradictorios dan error, sin
adivinar ni truncar. Si coexisten código completo y tipo/letra, deben coincidir;
no se establece una prioridad silenciosa.

### Receptor y notas

- La condición es la del **receptor**, distinta de la del emisor. Debe provenir
  de una columna explícita en el archivo mixto; no se deduce del CUIT ni de A/B.
  Si se configuró una columna fiscal por fila, un vacío requerido o valor
  desconocido no se sustituye por consumidor final. Una condición fija sigue
  siendo una elección explícita válida para archivos homogéneos.
- Consumidor final puede estar identificado con CUIT/CUIL o DNI. Reutilizar la
  regla P1: mantener documento y nombre, distinguir el tipo de identificación y
  mostrar diferencias reales entre dato aportado y configuración efectiva.
  No interpretar CUIT con CF como contradicción ni como receptor anónimo.
- A requiere documento CUIT, número válido, razón social y condición compatible.
  No imponer «A = sólo Responsable Inscripto»: también existen receptores
  monotributistas admitidos. La matriz se verifica con documentación y catálogos
  oficiales vigentes antes de implementar, respetando el dominio soportado.
- No convertir una fila A incompleta en B o consumidor final, ni descartar su
  CUIT. La obligatoriedad por fila funciona aunque el encabezado exista y la
  casilla genérica «Requerido» no esté seleccionada.
- B/C conservan las reglas aplicables de identificación y condición fiscal;
  una fila B no implica necesariamente consumidor final. Mantener los casos
  homogéneos existentes sin forzar nuevas columnas innecesarias.
- NC/ND exigen datos del comprobante asociado y su coherencia con emisor,
  receptor, tipo, punto, número y fecha cuando corresponda. No obligar a llenar
  esas celdas en las filas FC del mismo archivo.
- La autorización de uso de A/B/C depende del emisor; una columna C o un IVA
  fijo del 21 % no pueden eludir las restricciones de comprobantes C.

Fuentes verificadas el 04/09/2026: [clases de comprobantes ARCA](https://arca.gob.ar/facturacion/regimen-general/comprobantes.asp)
y [manual WSFEv1, versión 4.7](https://www.arca.gob.ar/ws/documentacion/manuales/manual-desarrollador-ARCA-COMPG.pdf).
Son referencias para el diseño, no autorización para consultar padrones o emitir
durante una auditoría. No sumar consultas externas por cada fila como requisito.

### Importes y fechas

Correspondencia del ejemplo contable aportado, sin datos personales ni filas
reales. Las letras indican posiciones de ese ejemplo, no columnas obligatorias
para todas las plantillas. Los encabezados efectivos se verifican al importar.

| Posición | Dato | Interpretación |
|---|---|---|
| A | Fecha | Fecha fiscal del comprobante, si se eligió usar el archivo |
| B | Razón social | Nombre del receptor; conservarlo para identificación y duplicados |
| C | CUIT | Documento del receptor; obligatorio cuando lo exige el tipo/condición |
| D | Tipo de comprobante | FC, NC o ND; resolver junto con la letra |
| E | Letra | A, B o C, conforme al emisor y receptor |
| F | Punto de venta | Usar el archivo o la opción fija explícita del lote |
| G | Descripción | Texto del ítem o reemplazo fijo explícito del lote |
| H | Importe neto | Base neta; confirmar el encabezado completo, truncado en la captura |
| I | Total IVA | Importe de IVA para control, no porcentaje de alícuota |
| J | Total final | Importe final informado para contrastar el cálculo canónico |

Para admitir filas A, el archivo mixto agrega una columna de condición IVA del
receptor. La alícuota del 21 % puede ser un valor fijo explícito de la plantilla
aplicable al caso; no se deduce del importe de la columna I ni se generaliza
a otros emisores. Las filas NC/ND requieren las columnas de asociado del
contrato anterior. La ampliación de columnas se muestra en la plantilla generada.

- H del ejemplo representa neto, I importe IVA y J total final. El nombre exacto
  del encabezado H debe leerse del archivo, no completarse desde una captura
  truncada. Admitir lectura por encabezado o posición con correspondencia visible.
- Para un comprobante resumido por fila, cantidad 1 y precio neto explícitos.
  IVA 21 % puede quedar fijo en la plantilla del emisor que utiliza esa alícuota.
  Distinguir porcentaje e importe: I no se mapea a «IVA %».
- Total final es control del cálculo; proponer importe IVA como control opcional
  cuando el archivo lo aporta. No reemplazar el cálculo canónico por los totales
  informados, ni usar automáticamente un total con IVA como precio neto.
- Conservar el contrato decimal PF-03B. Documentar precisión y tolerancias; no
  modificar el redondeo para hacer coincidir un ejemplo. Una fórmula sin valor
  calculado disponible no equivale a cero ni a un dato opcional ausente.
- Fecha fiscal desde archivo o elección explícita en el lote. Formato visible
  `DD/MM/AAAA`, validación de calendario y ninguna fecha actual predeterminada.
  Conservar controles de fechas de servicio y comprobantes asociados. Mostrar
  emisión, servicio desde/hasta y vencimiento como campos distintos, con su
  procedencia efectiva desde Excel, constante o perfil/lote. Su soporte existente
  no se presenta como una funcionalidad nueva; este corte facilita el mapeo y la
  revisión, sin reemplazar silenciosamente una fecha suministrada.

## Responsabilidades del flujo

| Etapa | Responsabilidad futura |
|---|---|
| Desde Excel | Mostrar hoja, encabezados, posiciones y una muestra acotada; proponer correspondencias sin inventar datos fiscales |
| Constructor | Separar columnas y valores fijos; controles contables para tipo, letra, IVA y condición; requisitos condicionales y vista interpretada |
| Guardado/API | Validar el mismo contrato estructural; rechazar duplicados, ambigüedad y combinaciones imposibles; conservar versiones |
| Lectura | Elegir la hoja configurada, resolver encabezados/posiciones inequívocos, conservar fila de origen y datos inválidos hasta informar el error |
| Normalización | Resolver tipo/letra y receptor con procedencia; generar datos canónicos sin sustituir información explícita incompatible |
| Perfil y lote | Aplicar sólo políticas explícitas vigentes; mostrar qué reemplazan y conservar el snapshot de opciones efectivo |
| Validación de grupos | Verificar receptor, fechas, punto, asociados, ítems e importes; un grupo inválido no queda listo para emitir |
| Confirmación y worker | Mantener confirmación irreversible, revalidación, aislamiento, idempotencia y reconciliación existentes |
| Resultado/corrección | Identificar fila y columna original; permitir corregir errores sin reconstruir la configuración ni repetir autorizados |

## Hallazgos que condicionan la implementación

Resolver dentro del corte los hallazgos de la auditoría que impiden cumplir el
contrato: tipo/letra, compatibilidad por fila, fidelidad de documento, enteros
fiscales estrictos, encabezados/posiciones inequívocos y trazabilidad de filas.
Cubrir celdas requeridas y controles de importes, ida y vuelta del Excel generado,
plantillas legacy y visibilidad de valores fijos. No basta con añadir un selector
de letra al frontend.

Las mejoras transversales de concurrencia CRUD, recursos, modal y recuperación
se coordinan con PF-14/PF-13/PF-17. Su auditoría no autoriza un refactor global.
No reabrir contratos cerrados sin necesidad demostrada para esta unidad.

## Compatibilidad e invariantes

- Mantener las plantillas de código numérico y de tipo fijo, incluida la variante
  B/consumidor final/21 %. Las nuevas reglas se incorporan por versión explícita;
  no reescribir todas las configuraciones guardadas al abrir el editor.
- Preservar campos legacy no editables sin presentarlos como opciones vacías.
  Cambiar una etiqueta visual no debe perder alias, defaults ni configuración
  que el usuario no modificó.
- Conservar formato/versiones, perfil efectivo, fuente y trazabilidad suficiente
  del lote. No duplicar indefinidamente el Excel ni evidencia privada; limitar
  muestras y recursos para VPS pequeño.
- Un lote ya validado conserva su snapshot. Cambiar la plantilla no lo reinterpreta
  ni altera hashes, confirmaciones o solicitudes inciertas. Nuevas importaciones
  usan la versión vigente según el contrato actual.
- Cero CAE, reservas o intentos fiscales por abrir el editor, previsualizar o
  guardar. Ningún error previo convierte incertidumbre fiscal en rechazo.
- La confirmación irreversible existente conserva fecha y punto; editar los datos
  relevantes invalida la confirmación anterior conforme a los contratos actuales.
- Rollback de aplicación/configuración definido antes del desarrollo; evitar
  migraciones destructivas y conservar lectura de snapshots existentes.

## Decisiones pendientes antes de implementar

1. Consumir el contrato P1 aceptado de documento y condición independientes,
   sin reabrir la validez de CF identificado. La transición legacy, consumidores
   y snapshots se resuelven en ese corte; cerrar aquí sólo su integración con
   columnas, constantes y vista interpretada del constructor.
2. Campos «requeridos»: separar obligatoriedad del encabezado, valor por fila y
   requisito fiscal condicional; definir transición para plantillas legacy que
   hoy permiten celdas vacías. No endurecer todos los archivos existentes por
   accidente.
3. Campos sin usar, fórmulas sin caché y controles de IVA: cerrar presentación y
   mensajes con un Excel sintético representativo. Confirmar nombres completos
   y estructura con el archivo real si se usa como caso de aceptación privado.
4. Resolver la división exacta de trabajo transversal con PF-14/PF-17 y confirmar
   el corte a ejecutar. La ampliación P2 mantiene su horizonte; la fidelidad P1
   se ejecuta aparte según el orden del roadmap.

## Matriz de aceptación obligatoria

| Área | Casos mínimos |
|---|---|
| Tipo/letra | Las nueve combinaciones; tipo o letra fijos; código legacy; mixto A/B; vacíos, desconocidos, contradictorios y fracciones |
| Receptor | A con CUIT válido/ausente/inválido; condición ausente/desconocida/incompatible; RI y monotributo admitidos; B/C con CF identificado o anónimo conforme al contrato P1, sin pérdida de documento |
| Alias de condición | «Monotributista» equivale a «Monotributo»; espacios y mayúsculas normalizados; desconocidos no se convierten en CF ni se interpretan por CUIT |
| Asociados | FC con celdas vacías; NC/ND completas e incompletas; asociado incompatible; notas mixtas con facturas |
| Mapeo | Encabezados duplicados tras normalizar; columnas sin nombre; posición fuera de archivo; hoja ausente; cambio de hoja; filas vacías y encabezado distinto de fila 1 |
| Importes | Neto/IVA/total separados, cantidad 1 explícita, IVA fijo/columna, C con IVA incompatible, total requerido vacío, fórmula sin caché, precisión y diferencias de centavos |
| Generación | Descargar, completar y reimportar produce la misma interpretación; posiciones fijas y columnas por nombre sin colisiones; etiquetas y ejemplos seguros |
| Perfiles/versiones | Overrides explícitos visibles, procedencia de documento/condición y emisión/servicio/vencimiento; versión reemplazada, clonación protegida, legacy sin pérdida, lote existente inalterado y rollback |
| Aislamiento/concurrencia | Otro emisor rechazado; cambios de contexto y respuestas tardías; guardado concurrente; doble validación/confirmación sin doble efecto fiscal |
| Emisión/errores | Error previo sin CAE; worker y caminos unitario/batch revalidan; incertidumbre/reconciliación conservan solicitud congelada y nunca se reemite por un error de importación |
| UX/accesibilidad | Usuario contable configura sin códigos; muestra explica el resultado; corrección por fila/columna; teclado, foco, lector de pantalla y zoom; sin confirmaciones nuevas rutinarias |

Antes de implementar completar el
[`checklist fiscal`](fiscal-change-checklist.md) y la puerta de Nivel 2 de
[`calidad`](change-quality-gates.md). Todas las pruebas usarán datos sintéticos
y dobles, sin llamadas reales de CAE. La revisión documental actual es Nivel 0;
no implementa ni despliega esta capacidad.
