# Auditoría del constructor de plantillas y la importación de lotes

Fecha: 04/09/2026.

## Dictamen y alcance

El proceso tiene protecciones valiosas de versionado, aislamiento, validación
de lotes y confirmación fiscal. El constructor, sin embargo, obliga a conocer
códigos internos, no permite tipo y letra separados y no anticipa varias
incompatibilidades de las filas. Agregar sólo una columna «Letra» no resuelve el
problema: también debe revisarse la fidelidad de lectura y la coherencia entre
plantilla, perfil, validación local y comprobante resultante.

Se auditó la cadena desde creación/edición y descarga hasta detección, lectura,
normalización, opciones del lote, validación, datos persistidos, fronteras de
emisión y corrección. Se combinaron inspección visual, código, pruebas existentes
y comprobaciones sintéticas en memoria. No se modificó código de aplicación,
la plantilla guardada, perfiles ni lotes; tampoco se solicitó CAE.

Base local examinada: `c2bff45c5e0e9472d9b3358107f8388514779db0`.
La observación de la interfaz no acredita que ese SHA sea el desplegado. El
estado productivo autoritativo pertenece al plano de control externo.

La captura de Excel aportada por el usuario fundamenta la estructura de
columnas, no la totalidad del archivo ni sus fórmulas. El Excel original no se
recibió. No se incluyen nombres, identificadores ni importes privados en este
informe versionado; los ejemplos siguientes son sintéticos.

## Encaje previo en roadmap y visión

| Fuente revisada | Resultado |
|---|---|
| Roadmap y portafolio anteriores | PF-13 ya contiene formatos, perfiles y lotes; no hay una iniciativa explícita de tipo/letra separados |
| PF-17 | Comparte claridad administrativa, accesibilidad y recuperación; no debe crear otro constructor |
| Rediseño UX de lotes | Los cuatro cortes están cerrados; no planifican esta extensión del formato |
| PF-03B | Contrato implementado de ítems/importes: conservar decimales, errores explícitos y snapshots válidos |
| PF-01 y multiemisor | Preservar idempotencia, reconciliación, aislamiento y confirmaciones existentes |
| Visión | La persona usuaria entiende contabilidad; el producto debe absorber códigos, transformaciones y detalles técnicos |

Adjudicación: ampliar PF-13 con apoyo de PF-17, sin alterar el horizonte «Más
adelante» ni desplazar «Ahora»/«Después». El
[`diseño futuro`](../../agents/pf-13-plantillas-contables-design.md) es dueño del
alcance y la aceptación. Este informe conserva los hechos de la auditoría;
sus hallazgos no autorizan cambios adicionales ni fijan prioridades nuevas.

## Cómo se construye hoy cada comprobante

1. **Nueva plantilla / Desde Excel.** `resetPlantillaForm` inicia tipo 11 e IVA 0.
   «Desde Excel» lee encabezados y crea filas sin campo destino; no interpreta
   datos de muestra ni el significado contable de las columnas.
2. **Edición.** Una fila del constructor define destino, encabezado o posición,
   constante, transformación, requerido y ejemplo. Se reconstruyen `plantilla`
   y `campos` al guardar; los ejemplos sólo sirven para la descarga explicativa.
3. **Guardado y versiones.** La UI consulta compatibilidad. El servicio valida
   estructura/constantes y crea una versión si cambia la configuración. Conserva
   versiones anteriores; las reemplazadas no sirven para nuevas importaciones.
4. **Generación y detección.** La descarga arma un Excel y metadatos no fiscales.
   La detección compara encabezados/posiciones, no contenido de filas, y evita
   sugerir entre candidatos empatados con constantes fiscales diferentes.
5. **Lectura configurable.** Se elige hoja y fila de encabezado, se resuelve el
   mapeo y se aplican transformaciones. Cada fila no vacía genera un comprobante
   `FILA-...`; el camino configurable no permite agrupar varios ítems por una
   referencia elegida como sí permite el formato oficial.
6. **Normalización.** Se construyen campos canónicos: tipo numérico, receptor,
   fechas, ítem y asociados. Se infiere tipo de documento; el total puede actuar
   como precio si éste no fue configurado. Hay defaults de cantidad/unidad/CF.
7. **Perfil y opciones.** El perfil precarga controles; el servidor aplica las
   opciones explícitas de concepto, descripción, fechas y punto antes de validar.
   Pueden reemplazar valores leídos, y quedan registradas en metadatos del lote.
8. **Validación y persistencia.** Se comprueban emisor, punto, certificado,
   grupos, fechas, receptor, ítems y asociados. Se compara el total informado
   cuando existe; diferencias mayores que un centavo producen error. Se
   conservan versión, mapeo, opciones y payload canónico del grupo.
9. **Emisión y corrección.** Confirmación irreversible, guardas y revalidaciones
   protegen el paso a CAE. El observado exporta columnas canónicas y errores,
   no el mismo diseño del Excel externo que el usuario cargó.

### Fuentes de implementación

| Fuente | Puntos inspeccionados |
|---|---|
| [EmpresaConfigView.vue](../../../frontend/src/views/empresa/EmpresaConfigView.vue) | `resetPlantillaForm`, `columnasDesdeConfiguracion`, `construirConfiguracionPlantilla`, `procesarExcelPlantilla`, compatibilidad, guardado y tabla del modal |
| [formatos_importacion.py](../../../backend/app/api/formatos_importacion.py) | Catálogo, análisis, compatibilidad, detección, permisos de alcance, CRUD y descarga |
| [formatos_importacion_service.py](../../../backend/app/services/formatos_importacion_service.py) | `evaluar_compatibilidad` (893), generación (1161), importación (1304), validación (1785), detección (1963), lectura/mapeo (2070), fila canónica (2186) |
| [lote_comprobantes_service.py](../../../backend/app/services/lote_comprobantes_service.py) | Opciones y persistencia (395), observado (5410), lectura (5459), `_validar_grupo` (5664), total informado (5961), parsers (6692) |
| [facturacion_service.py](../../../backend/app/services/facturacion_service.py) | Validación y `normalizar_receptor` (2090–2230); fronteras de emisión y revalidación |
| [comprobante.py](../../../backend/app/schemas/comprobante.py) | DTO fiscal, ítems estrictos, asociados y fechas |
| [BaseModal.vue](../../../frontend/src/components/ui/BaseModal.vue) | Semántica, cierre y gestión de foco del componente compartido |

Las ubicaciones corresponden al SHA auditado, no a un compromiso de líneas
inmutables después de la implementación.

## Hallazgos

La criticidad expresa impacto potencial dentro del flujo auditado. No equivale
a una autorización de arreglo urgente ni a evidencia de un CAE incorrecto.
«Reproducido» significa probado localmente con datos sintéticos; «inspección»
identifica evidencia de código o interfaz sin ensayo integral del caso.

### H01 — Tipo y letra no tienen representación contable separada

**Alta para el objetivo; interfaz y código.** El catálogo sólo ofrece
`tipo_comprobante`, transformado a entero. No existe letra ni composición de
`FC + A`, `NC + B` o `ND + C`. La persona debe saber que 6 significa Factura B.
Una constante puede ocultar discrepancias con las columnas originales, que no
se usan. Incorporar modos contables y conservar código numérico legacy.

### H02 — Compatibilidad del constructor incompleta para receptor y filas

**Alta; reproducido.** Una configuración de Factura A sin documento ni condición
IVA obtiene `advertencia`, sin faltantes ni conflictos de receptor. Se miran
campos resueltos y tipo constante, no combinaciones reales de filas; las notas
detectadas sólo por columna tampoco activan los requisitos estáticos de asociado.
El lote sí comprueba CUIT para A. La mejora es anticipar los requisitos y
aplicarlos por fila, no declarar inexistentes las protecciones posteriores.

### H03 — «Listo para emitir» puede preceder a una incompatibilidad fiscal

**Alta; reproducido en `_validar_grupo`.** Una fila A con CUIT sintético válido,
razón social, IVA 21 y condición `EXENTO` retorna `validado` y «Listo para
emitir». RI y monotributo también retornan válidos. El ensayo aisló la ventana
temporal de emisión para probar la combinación fiscal, sin base ni ARCA.
No prueba que ARCA autorice el caso exento. Incorporar una matriz compartida
emisor/tipo/letra/documento/condición antes de declarar el grupo listo.

La [tabla oficial de ARCA](https://arca.gob.ar/facturacion/regimen-general/comprobantes.asp)
asigna A a ventas de RI a RI/monotributista y B a consumidor final/exento.
Por eso sería incorrecto solucionar el problema exigiendo únicamente RI para A.

### H04 — El documento configurado puede no ser el documento resultante

**Alta; reproducido.** `_armar_fila_canonica` ignora el tipo de documento explícito
y lo infiere por el número. En el ensayo, tipo `DNI` con número de estructura
CUIT terminó como `CUIT`; con CF y total bajo el umbral implementado se eliminó
el documento. La regla actúa antes de validar A/B/C y no explica la modificación
al usuario. La condición ausente también se completa como CF.

Para A se debe conservar y validar el CUIT, nunca transformar la fila a CF.
El tratamiento general de B/CF y documentos informados requiere decisión
expresa sobre la política vigente; la auditoría no la modifica.

### H05 — La transformación entera trunca datos fiscales inválidos

**Alta; reproducido.** `_aplicar_transformacion('6.9', 'entero')` devuelve 6.
Esto permite transformar una entrada inválida en un tipo o punto diferente
pero aceptado. Las constantes tienen un parser más estricto, por lo que la
garantía no es uniforme. Rechazar fracciones en campos enteros y conservar
el valor problemático para ubicarlo; no redondear ni truncar.

### H06 — Encabezados y posiciones pueden resolverse ambiguamente

**Alta; reproducido.** `Total final` y `Total Final` colisionan al normalizar;
el mapeo elige la última columna sin advertencia. La columna H se considera
encontrada incluso en un archivo con una sola columna. Una posición configurada
no comprueba su existencia ni si cambió su significado. Detectar duplicados,
límites reales y mostrar encabezado/posición/muestra antes de usar el mapeo.

### H07 — «Requerido» no garantiza un valor por fila

**Alta para controles; reproducido.** Se exige que la columna exista, pero una
celda de total de control vacía se importa como vacía. Con precio, IVA y demás
datos válidos, `_validar_grupo` la acepta y no compara ese total. Otros campos
tienen validaciones posteriores; no todos los vacíos se comportan igual.
Separar encabezado requerido, dato requerido y condición fiscal por fila,
con transición compatible de plantillas existentes.

### H08 — Hoja elegida y fórmulas necesitan señales fiables

**Media/alta; fallback reproducido, fórmulas por inspección.** Si se configuró una
hoja que no existe, el lector cae en `Comprobantes` o la activa sin error. El
análisis visual usa fila 1 y no ofrece elegir hoja/fila; además no conserva en
el formulario la hoja devuelta por el análisis. `data_only=True` lee valores
cacheados, no calcula fórmulas: una fórmula sin caché aparece vacía. No afirmar
que el Excel se recalculó; identificar el caso y dar una corrección clara.

### H09 — Los números de fila pueden perder correspondencia con el Excel

**Media; lectura reproducida y persistencia inspeccionada.** La importación
configurable omite filas vacías y conserva la fila física sólo en `FILA-...`.
Con datos en filas 2 y 4 produce esas referencias, pero el creador del lote
vuelve a enumerar la lista compacta desde 2. Lo mismo afecta encabezados fuera
de fila 1. Las observaciones pueden señalar otra fila. Propagar la fila física
explícita y usarla en mensajes, metadatos y archivos de corrección.

### H10 — Neto, porcentaje IVA, importe IVA y total están poco diferenciados

**Alta para configuración; interfaz y código.** No hay campo de control de
importe IVA y `importe_total` es fallback de precio unitario. Con IVA distinto
de cero, usar un total final como precio suma IVA nuevamente; el control de
total puede detectarlo después. El nombre «Total de control» no explica ese
fallback. Ofrecer una interpretación contable clara y un ejemplo sintético
neto 100, IVA 21, total 121, sin cambiar la aritmética fiscal vigente.

### H11 — Edición y descarga no garantizan ida y vuelta de la configuración

**Media; inspección y colisión reproducida.** El frontend reconstruye detalles
desde lo visible y pierde alias/defaults no representados. Mezcla campos legacy
fuera del catálogo con filas editables: en el modal se observó un selector vacío
para `guardar_cliente`. En generación, una columna por nombre anterior a una
columna fija A ocupa A y luego produce conflicto. Preservar datos no editados,
reservar posiciones antes de distribuir otras columnas y verificar
descargar/completar/reimportar. El formato externo actual sigue siendo un
comprobante por fila; no prometer agrupación por el campo `modo_agrupacion`.

### H12 — La corrección de notas puede convertirse en una excepción genérica

**Media/alta; reproducido.** Un asociado con número negativo llega a
`ComprobanteAsociadoCreate` dentro de `_validar_grupo` y lanza
`pydantic_core.ValidationError` en lugar de devolver mensajes del grupo. El
ensayo no recorrió HTTP, por lo que no atribuye un status concreto. Cubrir
asociados inválidos con errores sanitizados por fila/campo, igual que los ítems.

### H13 — Inicio y presentación aumentan la carga del usuario

**Media; captura actual y código.** «Nueva plantilla» fija Factura C/IVA 0 incluso
con emisor RI y abre con conflicto antes de que la persona decida nada. El modal
muestra códigos y términos como «Transformación», muchos desplegables y scroll
en ambos ejes. A 1265 × 712 varios textos y columnas no se ven completos.
Separar columnas del archivo de valores fijos, usar selectores contables y
ayuda contextual. No reemplazar C por A/B automáticamente: pedir la elección
dentro del campo que la necesita, sin agregar un paso de confirmación.

### H14 — Compatibilidad y opciones efectivas pueden resultar confusas

**Media; inspección.** La UI evalúa compatibilidad con debounce, sin descartar
respuestas antiguas de esa evaluación; guardar hace una revisión nueva, lo que
reduce el riesgo del resultado visual desactualizado. No se ensayó una carrera.
El perfil precarga opciones que pueden sustituir fecha, concepto, descripción o
punto. La pantalla ya expone esas opciones; falta una vista de su efecto sobre
la fila interpretada. No añadir confirmaciones redundantes ni cambiar la
precedencia vigente sin una decisión explícita.

### H15 — Accesibilidad y recuperación necesitan una revisión acotada

**Media; DOM/código, sin certificación WCAG.** Los controles repetidos de la tabla
carecen de nombres accesibles que identifiquen campo/fila. `BaseModal` no declara
rol de diálogo ni `aria-modal`; no implementa trampa de foco, retorno de foco o
cierre por Escape. La X no tiene nombre accesible. No se ensayó lector de
pantalla, zoom ni navegación completa por teclado. Coordinar con PF-17, sin
convertir este corte en una modificación global de todos los modales.

### H16 — Límites de recursos y corrección del archivo deben conservarse

**Media; inspección.** Los endpoints limitan bytes y el lector es `read_only`,
pero las filas configurables se materializan antes de aplicar `batch_max_rows`.
El observado cambia a columnas técnicas canónicas, lo que dificulta volver al
Excel original. No se midió consumo ni se probó un archivo de tamaño extremo.
Aplicar límites durante lectura y estudiar corrección con correspondencia al
origen, conservando los estados autorizados/inciertos y sin crear otra copia
permanente del archivo. Adjudicar recursos a PF-13 y mensajes a PF-14/PF-17.

## Protecciones verificadas que se deben conservar

- Alcance global/emisor, restricciones de administración y plantillas de sistema
  protegidas; clonación y versiones históricas separadas.
- Rechazo de nuevas importaciones con una versión reemplazada y registro de la
  versión/mapeo/opciones usados por un lote.
- Detección de ambigüedad fiscal entre candidatos empatados y confirmación de
  formato antes de importar archivos externos.
- Fecha de emisión explícita, validación de calendario y controles de servicios.
- CUIT para A, campos mínimos de asociados, IVA permitido, ítems estrictos y
  control de total cuando está informado.
- Neutralización de fórmulas en textos exportados y límites de tamaño de subida.
- Snapshots y revalidación en emisión/worker, idempotencia, aislamiento,
  confirmación irreversible y conservación de estados inciertos según PF-01/PF-03.

## Evidencia visual y límites de recorrido

| Paso | Estado observado | Evidencia privada de esta corrida |
|---|---|---|
| 1. Acceso y catálogo | Acciones distinguibles; lectura de instrucciones extensa y catálogo bajo el primer pliegue | `01-catalogo.png` |
| 2. Editar plantilla | Funcional, con densidad elevada, campos legacy y advertencia genérica | `02-constructor.png` |
| 3. Nueva plantilla | Conflicto inicial por C/IVA 0 con emisor RI; no requiere haber ingresado datos | `03-nueva-plantilla.png` |
| 4. Preparación del lote | Perfil visible y separación validar/emitir; opciones deben contrastarse con la fila efectiva | `04-lotes.png` |

Las cuatro capturas se guardaron e inspeccionaron en
`private/plantillas-audit-2026-09-04/`, fuera de Git. El informe visual privado
contiene las imágenes en orden. El paso «Desde Excel», la descarga/reimportación,
los errores por fila y la confirmación final se evaluaron por código/pruebas;
no se subieron archivos ni se crearon lotes en producción para capturarlos.
No se auditó visualmente cada estado fiscal ni se emitieron comprobantes.

## Validación ejecutada

- Backend: `test_formatos_importacion.py` y `test_perfiles_carga_masiva.py`:
  **71 pruebas aprobadas**.
- Backend: `test_lotes_comprobantes.py`, selección
  `formato or extracto or pf03b or nota_credito or tipo_a`:
  **45 aprobadas, 152 no seleccionadas**.
- Frontend: `EmpresaConfigView.spec.ts` y `perfiles-carga-masiva.spec.ts`:
  **14 aprobadas**.
- Total: **130 pruebas enfocadas aprobadas**. No es cobertura completa del
  sistema ni acredita ausencia de los casos nuevos reproducidos.
- Ensayos adicionales en memoria: encabezado duplicado, posición fuera de
  archivo, entero fraccionario, tipo de documento ignorado, documento eliminado
  bajo CF, A sin requisitos en compatibilidad, A/exento validado localmente,
  hoja inexistente, total vacío, salto de fila, colisión de descarga y asociado
  negativo. Sin cambios al código ni conexiones fiscales.

No se ejecutaron pruebas de producción, carga, PostgreSQL, carreras reales,
auditoría exhaustiva de seguridad ni nuevos casos de CAE. Los tests existentes
usan datos sintéticos y dobles. Las decisiones de política quedan en el diseño
futuro; esta auditoría no las aplica de forma unilateral.
