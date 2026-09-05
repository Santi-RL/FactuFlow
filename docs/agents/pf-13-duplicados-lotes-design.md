# PF-13/PF-17 — prevención de duplicados en emisión masiva

Fecha: 04/09/2026.
Última revisión: 05/09/2026.

Estado: decisión de producto aceptada; implementación pendiente. Este diseño
es la fuente del comportamiento futuro y de su aceptación. No describe una
capacidad desplegada ni autoriza modificar código o producción.

## Problema, alcance y encaje

Repetir fecha e importe entre consumidores finales anónimos es habitual. Un
aviso extenso por esas coincidencias favorece que se confirme sin atención.
El mismo mensaje genérico tampoco permite distinguir esa situación de volver
a emitir el contenido de un lote anterior. El objetivo es reducir los avisos
irrelevantes y explicar la coincidencia que requiere una decisión contable.

PF-13 es dueño de la comparación y del flujo masivo; PF-17, de la presentación
y accesibilidad; PF-14/PF-12 acompañan contratos y garantías de concurrencia.
PF-15 aporta trazabilidad. Se conservan PF-01/PF-03 y el aislamiento multiemisor.
Implementar la procedencia mínima del actor y las garantías necesarias con este
corte; no esperar el historial visual completo, la ampliación tipo/letra del
constructor ni la totalidad de PF-12/PF-14/PF-15. Compartir sus contratos sin
crear una dependencia circular.
La identidad leída del Excel se coordina con el
[diseño de plantillas](pf-13-plantillas-contables-design.md). No hay otro motor
de duplicados ni se reabre el rediseño de lotes cerrado.

Por decisión del usuario, este corte tiene **prioridad P1 fiscal y operativa**
y ocupa el **primer lugar de «Ahora»** en el [roadmap](../../ROADMAP.md), antes
de recuperación/trazabilidad. Se mantienen los requisitos de respaldo y
recuperación aplicables a cada operación. No se fijó una fecha de implementación.

La evolución posterior de la distribución se define en el
[diseño de UI de lotes PF-17](pf-17-lotes-ui-design.md). Compactar la pantalla
o separar el historial no puede ocultar ni sustituir esta advertencia, su
retorno principal, la excepción explícita o la revalidación previa a emitir.

El [resumen mensual del dashboard](pf-18-dashboard-mensual-design.md), a cargo
de PF-18/PF-17, aporta contexto previo: cantidades, importes y dos fechas del
último comprobante. Es una señal informativa; no sustituye esta comparación
ni permite deducir que un período está completo o libre de duplicados.

La investigación del caso productivo queda en la evidencia privada del plano
de control. Los ejemplos de este documento son sintéticos. No copiar nombres,
archivos, números, importes ni registros reales al repositorio público.

## Decisiones aceptadas

1. Dentro de un lote, no advertir por igual fecha e importe entre consumidores
   finales sin identidad definida. Advertir por nombre definido **o** documento
   coincidente, con igual fecha e importe, para el mismo emisor.
2. Comparar el contenido con lotes anteriores del emisor, independientemente
   del usuario. La coincidencia completa requiere una advertencia aunque los
   receptores sean anónimos. Nombre de archivo, cantidad y total son contexto;
   por sí solos no justifican bloquear ni exigir una excepción.
3. Mostrar qué coincide, el lote anterior, archivo, cantidad, importe, fecha y
   hora de emisión y nombre del usuario que solicitó esa emisión.
4. **«Volver a revisar» tiene el mayor énfasis visual y el foco inicial.**
   La alternativa de emisión tiene menor énfasis y permanece deshabilitada
   hasta marcar un checkbox específico, inicialmente vacío.
5. Permitir una excepción consciente mediante «Emitir como operaciones nuevas».
   No exigir un segundo aprobador ni un motivo escrito en esta versión. No
   bloquear definitivamente por similitud de contenido.
6. Revalidar la comparación antes de la emisión y coordinar solicitudes
   simultáneas. Mantener los bloqueos de la misma operación y de resultados
   inciertos, junto con la confirmación fiscal irreversible existente.

La aceptación del usuario cubre esta fricción excepcional y la eliminación
de avisos anónimos internos. Cumple la decisión explícita requerida por
[VISION.md](../../VISION.md); no autoriza otros intercambios entre seguridad y
usabilidad. Sin coincidencias relevantes, el flujo no agrega pasos.

## Reglas de comparación

### Receptor identificable dentro del lote

Para facturas comparables del mismo emisor, con igual fecha de emisión e importe
total, usar nombre definido **o** documento identificatorio. No exigir que
ambos coincidan. Ser consumidor final no equivale a ser anónimo.

| Receptores con igual fecha e importe | Advertencia interna |
|---|---|
| Ambos sin nombre definido ni documento, aunque coincidan los ítems | No |
| «Consumidor final» o «A consumidor final», sin documento | No |
| Nombres definidos distintos y ningún documento coincidente | No |
| Mismo nombre definido, sin documento | Sí |
| Mismo documento, aunque difieran o falten los nombres | Sí |
| Mismo nombre definido y documentos distintos | Sí; señalar coincidencia de nombre, no afirmar identidad |
| Receptor coincidente, pero distinta fecha o distinto importe | No por esta regla |

Vacíos, etiquetas genéricas y documento de relleno `0` no identifican clientes.
Comparar documentos por tipo y número normalizado; en nombres, ignorar
mayúsculas y espacios redundantes sin búsqueda aproximada ni unificación de
personas. Conservar el original para presentar evidencia. Los ítems idénticos
no sustituyen la identidad; cambiar la descripción tampoco debe anular una
coincidencia por receptor, fecha e importe.

### Comparación contra lotes anteriores

Comparar los comprobantes interpretados después de aplicar plantilla y opciones.
Reconocer archivos renombrados y filas reordenadas. Comparar conjuntos con
multiplicidad: dos apariciones de un comprobante no equivalen a una sola.
La igualdad completa debe considerar todos los datos fiscales e ítems,
incluidos tipo/letra, punto de venta, concepto, moneda, fechas, receptor e
importes; excluir nombre del archivo, posición de fila, IDs de lote/grupo,
numeración/CAE generados y marcas operativas. Documentar la normalización antes
de implementarla; no ignorar campos fiscales para forzar una coincidencia.

| Evidencia encontrada | Conducta futura |
|---|---|
| Igual nombre de Excel, cantidad y total, con contenido distinto | Contexto informativo; sin bloqueo ni checkbox obligatorio sólo por esos indicios |
| Contenido completo igual al de un lote ya emitido, incluso anónimo | Advertencia explícita de coincidencia completa y excepción condicionada al checkbox |
| Coincidencias parciales de receptores identificados con igual fecha e importe | Resumen de afectados y detalle; no afirmar que todo el lote está repetido |
| Coincidencias aisladas de consumidores anónimos por fecha/importe | No convertirlas en una advertencia de duplicación de todo el lote |
| Misma operación fiscal ya emitida o en curso | Conservar el flujo idempotente vigente; mostrar/continuar la operación existente |
| Resultado fiscal incierto | Conservar la reconciliación previa; el checkbox no habilita otra emisión |

Una repetición completa se evalúa por el conjunto, aunque la regla interna
silencie sus ventas anónimas. No aplicar esa excepción interna como filtro que
elimine todos los consumidores finales de la comparación entre lotes.

Consultar únicamente el emisor y ambiente correspondientes. En lotes parcialmente
emitidos, distinguir los comprobantes autorizados, pendientes y fallidos; no
atribuir emisión a todo el archivo. El detalle debe indicar el origen de cada
coincidencia, incluso si corresponde a varios lotes. No eliminar filas ni
excluir coincidencias de la emisión automáticamente.

## Mensaje y acciones

Ejemplo sintético de coincidencia completa:

> **Este lote coincide por completo con otro ya emitido**
>
> Los 50 comprobantes coinciden con el lote 18, emitido el 15/04/2026 a las
> 10:35, por un total de $250.000,00.
> Archivo anterior: Ventas abril.xlsx.
> Usuario que solicitó la emisión: Usuario de ejemplo.
>
> Continuar generará otros 50 comprobantes; no reemplazará los anteriores.

Debajo del resumen, ofrecer «Ver lote emitido» y acceso al detalle de las
coincidencias, sin una enumeración interminable de referencias. Para coincidencia
parcial usar «X de Y comprobantes coinciden» y distinguir importe afectado,
total del lote actual y total del anterior. Para coincidencias internas usar
un título referido al mismo receptor, sin inventar un lote anterior.

Acciones y comportamiento obligatorios:

- **«Volver a revisar»**: botón principal, mayor énfasis visual, foco inicial.
  Cierra la confirmación, conserva los datos y devuelve al lote sin emitir ni
  encolar. Su prioridad visual se mantiene después de marcar el checkbox.
- **«Ver lote emitido» / «Ver coincidencias»**: acciones de consulta que no
  implican confirmar ni perder la preparación actual.
- Checkbox vacío por defecto para coincidencias históricas:
  «Confirmo que estos comprobantes corresponden a operaciones nuevas, distintas
  de las del lote anterior». Adaptar el plural si hay varios lotes.
  Para coincidencias internas: «Confirmo que los comprobantes señalados
  corresponden a operaciones distintas».
- **«Emitir como operaciones nuevas»**: acción secundaria, deshabilitada hasta
  marcar el checkbox. Marcarlo no emite, no mueve el foco a ese botón y no abre
  otro diálogo genérico. Activar el botón sí solicita continuar bajo las
  confirmaciones fiscales y de duplicados vigentes.
- Escape, cerrar y el retorno predeterminado llevan a revisar. Enter desde el
  diálogo o sus campos no debe enviar por una acción implícita de formulario;
  la emisión por teclado requiere activar deliberadamente su botón habilitado.
  La barra espaciadora sobre el checkbox sólo cambia su estado.
- Al cerrar o cambiar lote/emisor, datos fiscales, selección o evidencia de
  coincidencias, limpiar checkbox y autorización de excepción. No heredar una
  aceptación de otro lote ni habilitar la emisión por una respuesta atrasada.
- No ocultar las advertencias existentes detrás de «Listo para emitir» ni
  mostrar simultáneamente que no hay observaciones y que falta confirmarlas.
- Usar etiquetas accesibles, orden de foco coherente, contraste y estado
  deshabilitado perceptible. El énfasis no depende sólo del color; probar zoom,
  teclado y lector de pantalla. No cambiar globalmente todos los diálogos.

### Usuario y fecha de la emisión anterior

La consulta general de esa procedencia se diseña en
[actividad de lotes PF-17/PF-15](pf-17-actividad-lotes-design.md). Compartir la
fuente de atribución; su tarjeta resume la última emisión, mientras que esta
advertencia debe identificar todos los actores pertinentes de las coincidencias.

Mostrar el nombre del usuario que **solicitó la emisión**, aun cuando el worker
la haya ejecutado. El creador del lote, último editor y usuario actual no son
sustitutos válidos. Si hay emisiones parciales de varios usuarios, mostrar esa
situación y el detalle por operación; no atribuirlas a una única persona.

Conservar ID de actor y nombre histórico suficiente para auditoría, respetando
permisos del emisor y sin exponer correos u otros datos innecesarios. Para
historia incompleta, mostrar «Usuario de emisión no registrado»; no inventar
una atribución. Una cuenta compartida no prueba qué persona estaba operándola.

Usar fecha/hora de emisión, distinguiéndola de la carga. Guardar zona/offset o
una referencia temporal inequívoca para nuevas operaciones y mostrar el formato
argentino. Si la hora histórica no puede interpretarse con certeza, indicarlo
sin corregir silenciosamente la evidencia ni afectar la fecha fiscal.

## Contrato técnico que debe completar la implementación

| Etapa | Responsabilidad |
|---|---|
| Importación | Conservar identidad y procedencia del archivo, plantilla y opciones; no perder un nombre/documento explícito que la comparación necesita |
| Validación/resumen | Clasificar origen y alcance de coincidencias; entregar cantidades, importes y vínculos, sin concatenar miles de filas en un string |
| UI de confirmación | Mostrar evidencia actual, retorno principal y checkbox; conservar confirmación fiscal de fecha/PV |
| API de emisión/reintento | Recalcular coincidencias y validar una aceptación ligada a la operación, datos y conjunto de coincidencias presentados |
| Coordinación/worker | Revalidar al ejecutar, incluidos envíos unitarios y agrupados; resolver carreras antes de una nueva solicitud de CAE |
| Resultado/auditoría | Conservar qué se detectó y qué excepción se aceptó, actor, instante y procedencia; distinguir aceptación de prueba de lectura humana |

La aceptación no debe ser un booleano general que autorice nuevos duplicados
no presentados. Si cambia el conjunto relevante después de confirmar, actualizar
la evidencia y exigir la decisión sobre ese conjunto; no repetir confirmaciones
cuando no cambió. Mantener el replay seguro de operaciones ya aceptadas.

Cubrir explícitamente la carrera en la que dos empleados validan antes de que
ninguno emita: la consulta, comprobación y reserva previa deben coordinarse de
forma que ambos no avancen basándose en una ausencia de antecedentes ya obsoleta.
Si la otra operación está en curso, mostrar su estado y acceso, sin permitir
usar el checkbox para eludir incertidumbre. Cuando termine, mostrar el resultado
real antes de decidir una excepción. No bloquear trabajo no relacionado de
otros emisores ni convertir esto en una reserva manual del emisor.

Inventariar consumidores: importador, API, resumen, servicio fiscal compartido,
worker, envío agrupado/unitario, reintentos y recuperación. Los caminos del lote
no deben reintroducir el aviso anónimo interno ni omitir el control histórico.
La política de emisión individual queda fuera de este corte; preservar su
comportamiento aunque comparta helpers.

## Compatibilidad e invariantes

- Separar el criterio de advertencia de las huellas durables usadas por
  idempotencia/reconciliación. No sustituir hashes históricos ni reescribir
  solicitudes confirmadas o inciertas para incorporar la comparación nueva.
- Conservar el bloqueo vigente de la misma carga, las reservas de numeración,
  aislamiento y confirmación irreversible. La excepción por similitud no
  permite volver a ejecutar una operación fiscal ya autorizada.
  «Misma carga» se refiere a la huella compuesta de importación por emisor,
  distinta de la similitud de comprobantes y de una solicitud fiscal repetida.
  El control actual puede impedir registrar el segundo lote antes de llegar al
  diálogo; este corte no ofrece el checkbox para eludir esa restricción. No
  recomendar cambios artificiales al Excel para sortearla. Un futuro flujo de
  nueva operación desde una carga idéntica requeriría una decisión específica.
- El comparador es local: no necesita llamadas a ARCA ni conservar indefinidamente
  Excels/PDF. Los hashes de carga compuestos no prueban por sí solos igualdad
  binaria; registrar la procedencia suficiente sin prometer reconstruir archivos
  originales que no se guardaron.
- Versionar el contrato de comparación/aceptación y definir transición para
  lotes existentes. Si faltan datos históricos, mostrar el límite; no inferir
  ausencia de duplicación o de confirmación por ausencia de registros.
  Cubrir lotes compactados: la comparación y su evidencia deben sobrevivir con
  una representación mínima verificable, sin conservar todo el Excel. En datos
  antiguos sin esa representación, declarar cobertura parcial; no prometer
  detección completa ni equiparar «No comprobable» a «Sin coincidencias».
- La excepción no altera receptor, fecha, importes ni tipo del comprobante.
  Resolver la pérdida de documento en importación sin inventar identidad ni
  cambiar implícitamente la política fiscal de consumidor final.
- Persistir evidencia mínima de la advertencia y su aceptación sin que el
  resultado final la sobrescriba. No registrar que el usuario «leyó» o «ignoró»
  el aviso: registrar la decisión recibida. Protegerla frente a compactación.
- Fallos previos a CAE y respuestas atrasadas no habilitan una emisión; fallos
  posteriores conservan incertidumbre y requieren el flujo de reconciliación.

## Matriz de aceptación

| Área | Casos obligatorios |
|---|---|
| Identidad interna | Todos los casos de la tabla; nombre sin documento; documento con nombre distinto; homónimos; placeholders; mayúsculas/espacios y separadores |
| Contenido | Excel renombrado; filas reordenadas; mismo nombre/cantidad/total con datos diferentes; multiplicidades distintas; cambio de descripción con receptor/fecha/total coincidentes |
| Historia | Lote completo anónimo repetido; coincidencia parcial identificada; varios antecedentes; lote parcialmente emitido; separación entre coincidencias internas e históricas |
| Caso sintético integral | Primer lote con ventas anónimas repetidas no advierte internamente; un segundo Excel con formato visual distinto, distinta huella de carga y el mismo contenido contable detecta el conjunto ya autorizado y exige la excepción informada |
| Usuario/horarios | Usuario que carga distinto del que solicita emitir; worker; cuenta renombrada; actor ausente; varios actores; hora histórica sin zona; no atribuir emisión al usuario actual |
| Acciones | Retorno es el botón más destacado antes/después del checkbox; foco inicial seguro; checkbox vacío; marcar no emite; excepción secundaria sólo habilitada tras marcar |
| Navegación/accesibilidad | Enter implícito no emite; Escape/cierre vuelven; teclado deliberado funciona; foco al volver del detalle; móvil/zoom/lector de pantalla; no pérdida de archivo/opciones |
| Invalidación | Cambio de lote, emisor, selección, datos o coincidencias borra aceptación; respuesta vieja no habilita; datos sin cambios no agregan confirmaciones repetidas |
| API/worker | Sin confirmación válida no hay CAE; validación de servidor aunque se omita UI; mismo control en cola, reintentos y envío unitario/agrupado |
| Concurrencia | Dos lotes validados en paralelo; uno emite mientras otro confirma; dos workers; mismo request duplicado; la segunda operación no usa evidencia obsoleta |
| Invariantes | Replay sin nuevo CAE; misma clave/payload distinto en conflicto; misma carga bloqueada; incertidumbre no eludible; aislamiento por emisor/ambiente; emisión individual preservada |
| Persistencia/recursos | Detección y excepción siguen auditables tras finalizar/compactar; datos legacy explícitos; consultas acotadas, índices y detalle paginado para VPS pequeño |

## Detalles por cerrar antes de codificar

- Normalización exacta de nombres genéricos, campos y precisión del comparador;
  tratamiento entre tipos/letras y puntos de venta para las coincidencias
  parciales. No sumar umbrales arbitrarios de similitud de consumidores anónimos
  como una nueva advertencia obligatoria.
- Contrato API, representación de coincidencias, invalidación y mecanismo
  atómico para consultas/reservas en SQLite/PostgreSQL y worker. Definir cómo
  se recupera la espera ante otro lote sin que un navegador decida el estado.
- Persistencia mínima del actor y evidencia, compatibilidad con datos históricos,
  paginado, índices, migración reversible y rollback. No elevar costes guardando
  archivos originales de forma permanente.
- Recorrido de pantallas con ejemplos sintéticos completos y parciales,
  conservando las etiquetas y jerarquía de acciones aceptadas. La aceptación de esta propuesta
  no incluye un panel de presencia, asignaciones obligatorias ni otro aprobador.

Antes de implementar completar el [checklist fiscal](fiscal-change-checklist.md)
y la puerta de Nivel 2 de [calidad](change-quality-gates.md): consumidores,
estados, errores, concurrencia, transición y rollback. Probar sólo con datos
sintéticos y dobles, sin CAE real. Al implementar se actualizan manual/API y QA
según su comportamiento efectivo. La actualización presente es documental,
Nivel 0, y no requiere ejecutar suites fiscales ni un despliegue.
