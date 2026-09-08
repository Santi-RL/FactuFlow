# PF-13/PF-17 — prevención de duplicados en emisión masiva

Fecha: 04/09/2026.
Última revisión: 08/09/2026.

Estado: contrato funcional y técnico vigente. Este diseño es la fuente del
comportamiento y de los criterios de aceptación del control de duplicados.
No acredita el estado de una instalación ni autoriza acceso a producción.

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

Este corte implementado responde a la **prioridad P1 fiscal y operativa**
acordada por el usuario. Su evidencia y publicación viven en el
[dossier de v0.3.6](../project/releases/pf13-duplicados-candidate.md).
El [roadmap](../../ROADMAP.md) conserva las próximas unidades; se mantienen los
requisitos de respaldo y recuperación aplicables a cada operación.

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
  Si se combinan coincidencias internas, lotes anteriores o comprobantes
  individuales anteriores, el único checkbox incluye todas las clases presentes
  y adapta sus referencias y plurales; no omite ninguna de las afirmaciones.
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

Para el primer release de este control, por decisión del usuario, la
verificación adicional con zoom real al 200 % y lector de pantalla y los
detalles visuales menores sin impacto operativo se siguen después del corte en
el [portafolio](development-portfolio.md). Esto no acredita pruebas pendientes
ni permite postergar un defecto que impida leer la evidencia, volver a revisar
o tomar una decisión consciente. Se mantienen las guardas fiscales, el foco y
la jerarquía de acciones, el checkbox y la confirmación irreversible.

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

## Contrato técnico cerrado

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

### Alcance técnico y consumidores

El comparador nuevo pertenece al flujo de lotes y usa el contrato versionado
`duplicados_lotes/v2`. Debe intervenir en:

- la plantilla oficial y los formatos configurables, antes de perder identidad
  de entrada;
- `validar_y_registrar_lote`, el resumen y el detalle paginado;
- `POST /procesar` y `POST /reintentar-fallidos`, incluida su idempotencia;
- el claim y la recuperación stale del worker;
- los caminos unitario y agrupado de `procesar_lote` antes de delegar en
  `FacturacionService`;
- la compactación, que elimina filas pero conserva grupos y evidencia;
- la reconciliación, únicamente para clasificar el resultado ya verificado, sin
  convertir similitud en prueba de ARCA.

`EmitirComprobanteRequest`, `buscar_duplicado_logico`,
`calcular_huella_logica` y los hashes de payload existentes no cambian de
significado. La confirmación nueva sigue excluida del hash idempotente. En los
caminos batch, el booleano interno que consume hoy `FacturacionService` sólo
puede establecerse después de validar `control_duplicados_json`; no es una
entrada general de usuario. Emisión individual conserva exactamente su política
y su DTO vigente.

### Identidad de entrada y normalización v2

La importación debe conservar por grupo dos representaciones distintas:

1. **Identidad de entrada para comparación:** tipo, número y nombre tal como
   resultaron del mapeo confirmado, junto con su forma normalizada v2.
2. **Receptor fiscal:** el `EmitirComprobanteRequest` estricto después de
   `normalizar_receptor`, que puede usar tipo `99`, número `0` y la leyenda de
   consumidor final sin alterar la identidad de entrada.

Esto corrige el borde actual de los formatos configurables: hoy
`_armar_fila_canonica` vacía el documento explícito de un consumidor final bajo
el umbral antes de `_validar_grupo`. La implementación debe capturarlo antes de
esa decisión. No debe reenviarlo a ARCA, crear un cliente ni cambiar la política
fiscal de consumidor final por este motivo.

La normalización exacta es:

- **nombre:** Unicode NFKC, `strip`, espacios Unicode consecutivos reducidos a
  uno y `casefold`; no se eliminan signos ni se aplica búsqueda aproximada;
- **nombre genérico:** sólo vacío, `CONSUMIDOR FINAL` y
  `A CONSUMIDOR FINAL`, evaluados después de la normalización anterior;
- **documento:** tipo reconocido por el contrato actual y número explícito
  normalizado con la limpieza vigente para el tipo; vacío, número compuesto
  sólo por ceros o tipo `99` con número `0` no identifican. Un tipo o número que
  el contrato fiscal vigente no pueda validar tampoco se promueve a identidad;
- **fecha:** fecha calendario ya validada, serializada `YYYY-MM-DD`;
- **importe para coincidencia parcial:** total obtenido por
  `_calcular_totales`, cuantizado a centavos con las reglas fiscales compartidas;
- **moneda y cotización:** código de moneda exacto y cotización Decimal canónica;
  `100 USD` no coincide con `100 PES`.

La clave parcial es `(empresa_id, ambiente, fecha_emision, total_centavos,
moneda, cotizacion, tipo_comprobante, punto_venta_numero, identidad)`. La
identidad coincide si es igual el hash del nombre definido **o** el hash del par
tipo+número; no se exige que ambos coincidan. En este corte, «facturas
comparables» exige el mismo tipo exacto —que ya incorpora letra y naturaleza
factura/NC/ND— y el mismo punto de venta. Esta es la compatibilidad mínima con
el control vigente: no equipara letras, una factura con su nota ni operaciones
de puntos distintos. Un futuro cruce entre letras o puntos necesitaría una
decisión de producto específica. No se crean advertencias por aproximación ni
por consumidores anónimos.

### Contenido fiscal completo y multiconjunto

La huella completa v2 se construye desde el request validado y el número real
del punto de venta. Incluye:

- tipo de comprobante, punto de venta, concepto, fecha fiscal, fechas de
  servicio y vencimiento;
- tipo y número de documento, razón social, condición IVA y domicilio del
  receptor;
- moneda, cotización y observaciones;
- comprobantes asociados completos: tipo, punto, número, fecha y CUIT;
- todos los ítems: código, descripción, cantidad, unidad, precio unitario,
  descuento e IVA.

Se excluyen `empresa_id` —porque es parte del scope—, IDs internos de empresa,
punto, cliente, lote, grupo o fila, `guardar_cliente`, las dos confirmaciones,
`items[].orden`, nombre de archivo, posición, número fiscal asignado, CAE y todo
estado operativo. No se omite ningún otro dato del request fiscal.

Los textos usan NFKC, espacios reducidos y `casefold`, conservando puntuación.
Los decimales se validan como `Decimal` finito y se serializan en forma canónica
sin ceros finales; cantidades, precios, descuentos, IVA y cotización no se
redondean más allá de sus reglas vigentes. Fechas usan ISO. Ítems y asociados se
ordenan por su representación canónica y se comparan como multiconjuntos: el
orden operativo no importa y la multiplicidad sí. El lote se compara como
multiconjunto de huellas completas, también con multiplicidad.

Contenido y resultado de emisión son dimensiones separadas. Para cada lote
anterior se forma un único conjunto delimitado con **todos** sus grupos
comparables; la coincidencia completa exige igualdad exacta entre ese
multiconjunto y la selección actual, incluida la multiplicidad. Varios lotes
anteriores pueden cumplir esa igualdad por separado y se muestran como varios
antecedentes; nunca se suman filas de lotes distintos ni se usa un subconjunto o
superset histórico para fabricar igualdad completa.

«Todos» no permite descartar un grupo legacy que carezca de huella: si no puede
reconstruirse cada grupo del lote anterior, la igualdad completa queda
`no_comprobable` o `parcial_legacy` y no se afirma a partir del subconjunto sano.

Después se clasifica el resultado de cada grupo de ese lote anterior. Los
estados persistidos reales, verificados en el servicio, son `autorizado` para un
grupo emitido por FactuFlow y `autorizado_externo` para uno reconciliado; el
`Comprobante` asociado usa `autorizado`. `grupos_emitidos` y
`grupos_reconciliados_externos` son nombres de contadores, no estados de grupo.
Los grupos fallidos, pendientes, descartados o inciertos siguen formando parte
del multiconjunto de contenido anterior, pero nunca se presentan como emitidos.

Una igualdad completa con un lote anterior parcialmente avanzado muestra por
separado cuántos grupos están autorizados, fallidos, sólo validados, reservados
en curso o inciertos y calcula el importe afectado sólo con los autorizados. Si
existe al menos un autorizado, exige la excepción informada incluso para
contenido anónimo. Sólo una reserva de otra operación aceptada que sigue activa,
un intento fiscal en curso o un resultado incierto deshabilitan la excepción
hasta conocer el resultado. Un grupo meramente `validado` en un lote cargado,
sin `duplicados_reserva_operacion_id` ni intento, no bloquea. Un lote anterior
sin autorizaciones, reservas activas ni incertidumbre aporta contexto, pero no
exige checkbox. Una venta anónima nueva que sólo coincide con una de las cien
filas de un lote anterior no es igualdad completa y permanece silenciosa.

Las coincidencias parciales v2 se informan sólo para receptores identificables y
pueden provenir de varios lotes. Por separado,
`historica_individual_legacy` preserva exactamente el predicado que hoy ejecuta
`buscar_duplicado_logico` sobre `Comprobante` autorizado, incluidos los matches
exactos anónimos que ese control vigente ya alcanza. No le agrega comparación
por nombre, fecha o importe ni modifica la emisión individual. Se expone con
`origen="comprobante_individual"`, referencia consultable y lote, grupo y
archivo nulos; actor e instante se informan sólo si pueden acreditarse. Esta
clase no se denomina coincidencia completa de lote y no reintroduce advertencias
anónimas internas. La coincidencia completa anónima nueva sigue exigiendo un
lote anterior delimitado; un comprobante individual aislado no la fabrica.

Se excluyen de antecedentes la operación actual y todos los grupos del mismo
lote que ésta continúa. Una autorización parcial propia actualiza su progreso,
pero no crea evidencia nueva contra sí misma ni repite el checkbox. Una mera
carga o validación ajena tampoco modifica la evidencia fiscal relevante. Sí la
modifican una autorización ajena o una reserva, intento fiscal o incertidumbre
ajenos que coincidan bajo las reglas anteriores.

### Persistencia mínima e índices

La migración agrega, sin reescribir `payload_json`, `archivo_hash`,
`payload_hash`, `huella_logica` ni respuestas idempotentes:

- en `lotes_comprobantes_grupos`: versión y cobertura del comparador, huella
  fiscal completa, hashes separados de nombre y documento, identidad de entrada
  original mínima, fecha normalizada y `duplicados_reserva_operacion_id`
  nullable;
- en `operaciones_idempotentes`: `control_duplicados_json`, separado de
  `response_json`, con versión, operación raíz, hashes de datos y selección,
  IDs y huellas de la selección original completa e inmutable, evidencia
  presentada, decisión, solicitante congelado,
  `solicitud_emision_at` y tiempos conocidos;
- en `intentos_emision_fiscal`: nombre histórico del solicitante y
  `solicitud_arca_at`/`resultado_fiscal_at` con zona. El `usuario_id` del intento
  es siempre el solicitante congelado de la operación, incluido el worker; no es
  el ejecutor técnico. `solicitud_arca_at` se fija inmediatamente antes de
  cruzar a `FECAESolicitar` y `resultado_fiscal_at` cuando se obtiene o
  reconcilia un resultado. Se persisten en UTC; la UI los convierte a la zona
  configurada y nunca corrige un legacy sin zona. El snapshot de nombre permite
  mostrar al solicitante histórico si la cuenta se renombra o elimina.

Los índices mínimos son `(empresa_id, ambiente, lote_id,
huella_fiscal_completa)`, dos índices equivalentes para `(empresa_id, ambiente,
tipo_comprobante, punto_venta_numero, fecha, moneda, cotizacion, total,
nombre_hash)` y `documento_hash`, y uno para
`duplicados_reserva_operacion_id`. El detalle primero delimita lotes candidatos,
verifica igualdad de conteo y multiconjunto, y pagina en base; no carga ni
deserializa todo el historial. Los hashes no sustituyen los payloads estrictos:
antes de afirmar coincidencia se verifica versión, scope, multiplicidad y
material canónico.

`control_duplicados_json` conserva la proyección vigente y el puntero a su
generación durable. Las generaciones preservan la evidencia y aceptación usada
por cada intento, incluso cuando la operación publica después otro control.
`metadata_json` del lote conserva sólo el puntero de operación raíz necesario
para el worker; el booleano antiguo deja de ser autoridad. Los grupos, payloads,
huellas y evidencia compacta sobreviven a la compactación. No se guardan
Exceles, PDFs ni copias completas adicionales del payload.

### Relación compacta, generaciones y recursos

El formato interno es `duplicados_relacion/1`; no cambia el DTO HTTP v2 ni la
aceptación opaca. Una codificación desconocida falla cerrada. La representación
persistida contiene bloques y miembros, sin una fila por cada pareja del
producto cartesiano. Resumen, digest y detalle usan esa misma relación.

| Tabla | Campos y responsabilidad |
|---|---|
| `lotes_duplicados_evidencias` | Cabecera: `id`, `operacion_id`, `empresa_id`, `ambiente`, `lote_id`, `generacion`, `formato`, `evidencia_id` nullable, `snapshot_hash`, `control_snapshot_json`, `aceptacion_id` nullable, actor/nombre/instante de aceptación, `aceptacion_origen_generacion_id` nullable y `created_at` UTC |
| `lotes_duplicados_coincidencias` | Bloque: `id`, `generacion_id`, scope de emisor/ambiente/lote, `bloque_clave`, `clase`, `antecedente_clave`, `snapshot_json` |
| `lotes_duplicados_coincidencias_miembros` | Pertenencia: `id`, `bloque_id`, `lado`, `miembro_clave`, `grupo_id` o `comprobante_id`, hashes de nombre/documento, `ordinal` nullable, `relevancia`, `snapshot_json` |

`control_snapshot_json` conserva resumen, selección original, delimitaciones y
manifiesto, sin duplicar miembros. Los snapshots de miembros conservan
referencias legibles, importes/unidades, estados, actores e instantes
acreditados. Se admite repetir un miembro en varios bloques: el coste se mide
en pertenencias, no en parejas. Las claves autoincrementales de almacenamiento
no intervienen en el digest ni en el orden público.

Las clases de bloque son `interna_nombre`, `interna_documento`, `completa`,
`parcial_nombre`, `parcial_documento` e `individual_legacy`. La clave del
antecedente delimita lote, raíz y selección original; no identifica una
continuación por ser el último retry leído. Se colapsan selecciones iguales de
la misma raíz; se conservan raíces y selecciones distintas. La procedencia sale
del intento fiscal correspondiente al resultado, con desempate temporal e ID
explícitos; una reserva se atribuye a su operación propietaria.

Constraints mínimos: únicos `(operacion_id,generacion)`,
`(generacion_id,bloque_clave)` y `(bloque_id,lado,miembro_clave)`; lados
`actual/anterior`, ordinal no negativo y único por lado dentro del bloque
completo. Se valida scope exacto, coherencia conjunta de los campos de
aceptación y pertenencia de cada miembro. Índices de consulta por
emisor/ambiente/lote/evidencia y por bloque/lado/ordinal o nombre. Las FKs y el
borrado preservan las restricciones fiscales y el permiso vigente de eliminar
lotes sin emisión; una nueva evidencia pendiente no introduce otro bloqueo
operativo de borrado por sí sola.

Construcción de la relación:

- Completa: acreditar primero la igualdad de las selecciones completas por
  multiconjunto fiscal. Por cada huella, ordenar todos los actuales y anteriores
  por ID y emparejar por ordinal original. Después conservar sólo parejas cuyo
  anterior sea autorizado, reservado ajeno o incierto, sin renumerar huecos.
  El bloque conserva huella, multiplicidad total y delimitación completa. Debe
  existir un actual y un anterior por ordinal conservado, de igual huella y
  dentro de la multiplicidad acreditada.
- Parcial: bloques por clave fiscal comparable y nombre o documento, sólo con
  miembros que tengan contraparte. La rama nombre incluye ambos campos cuando
  también coincide documento; la rama documento excluye esas parejas para no
  duplicarlas. Expresar los nulos explícitamente en SQL.
- Interna: bloques con al menos dos actuales por identidad; una fila por miembro
  y campo coincidente, sin expandir pares internos.
- Individual: agrupar por firma equivalente de todos los argumentos y la
  huella del predicado legacy. Consultar una vez por firma, preservando su
  comparación y fallback; no sustituirlo por la clave parcial v2.

Los estados sin autorización, reserva ni incertidumbre permanecen como contexto
agregado del resumen y de la delimitación completa, fuera del detalle ligado
al digest. Así un borrador ajeno no desplaza páginas con la misma evidencia.
Un conjunto actual/anterior de 100/100 con 20 autorizados conserva clasificación
completa y contexto de 100, pero aporta 20 filas relevantes y afectados por
autorización. Reservas e incertidumbre aumentan detalle/bloqueo, sin aumentar
autorizados. Una huella repetida conserva sus parejas originales aunque los
estados autorizados y fallidos estén intercalados.

El digest decisorio usa SHA-256 con separación de dominio del formato, claves
ordenadas, listas canónicas y nulos explícitos. Incluye material/selección
actual, delimitaciones necesarias y todos los miembros y bloqueantes relevantes.
Excluye orden de consulta, IDs de almacenamiento, borradores, revisión del
coordinador y progreso propio. La presentación de un bloqueo se elige
determinísticamente; nunca reemplaza el conjunto de bloqueantes del digest.

`snapshot_hash` acredita el contenido durable inmutable, incluidos actores,
instantes y referencias de los antecedentes. No incluye estado de transporte,
marcas técnicas, estado de aceptación ni progreso propio: emitir X no debe
crear una generación por el solo cambio de su estado. La aceptación tiene sus
columnas de auditoría separadas. Material actual estable y snapshots históricos
relevantes sí integran la acreditación.

Publicación bajo el coordinador existente:

- Mismos digest decisorio y snapshot: reutilizar la generación.
- Mismo digest, snapshot distinto: nueva generación; una aceptación válida
  conserva exactamente token, actor e instante y referencia su generación de
  origen. Sólo se hereda con igual material, selección y evidencia, dentro de la
  misma operación o continuación raíz acreditada; no agrega otro checkbox.
  Si la decisión sigue pendiente en la misma operación, conserva el token
  reexpedible para esa evidencia, sin atribuir una aceptación que no ocurrió.
- Evidencia/material/selección decisoria distinta: nueva generación pendiente,
  sin heredar aceptación. Una pendiente recibe aceptación una sola vez; después
  sus datos quedan inmutables. El puntero vigente puede avanzar, pero las
  generaciones publicadas y referenciadas se conservan durante la operación.
- Persistir miembros mediante lotes Core acotados; no acumular la expansión ni
  miles de objetos ORM. No mantener locks del coordinador durante WSAA/WSFE.

`IntentoEmisionFiscal.duplicados_generacion_id` referencia la generación validada
antes del envío, con protección de borrado `RESTRICT`. Es obligatorio en nuevos
intentos de lote v2, incluso sin coincidencias; queda nulo en individual y
legacy. Si X se autorizó bajo G1 y aparece evidencia nueva antes de Y, X sigue
vinculado a G1 con su decisión intacta; G2 pendiente no habilita Y. No modificar
retroactivamente esa asociación ni declarar incierto el resultado de X.

La revalidación acredita la integridad del snapshot durable, sus miembros y
su origen de aceptación frente al emisor y ambiente esperados; no toma ese
ambiente del propio registro que debe verificar. Distingue esa integridad de
la vigencia de la evidencia decisoria recalculada. Un cambio sólo descriptivo
de contexto no invalida la decisión ni exige otro checkbox. La publicación de
nuevas generaciones corresponde al coordinador; la segunda lectura fiscal
no publica ni reemplaza generaciones dentro de la transacción de emisión.
La consulta del detalle durable también valida esa integridad antes de devolver
la página, tomando el ambiente de los grupos actuales de la selección.

La consulta de página usa ramas compatibles unidas por `UNION ALL`, sobre
identificadores, antes de hidratar snapshots. COUNT interno cuenta miembros;
COUNT completo cuenta el join actual/anterior por bloque y ordinal; parciales e
individuales usan productos de conteos. En documento se resta la intersección
por nombre no nulo, calculada con agregados, para contar una vez cada pareja.
La página completa aplica el orden público común y `OFFSET/LIMIT` en base.
Construye como máximo `per_page` DTOs; resumen y revalidación construyen cero.

Sin generación durable, GET construye la misma relación compacta desde CTEs o
subconsultas de miembros vivos, verifica la evidencia y pagina sin crear una
operación ni aceptación. Respetar los límites de parámetros de ambos motores;
si se particiona, medir el buffer y combinar identificadores ordenados, nunca
una lista de parejas hidratadas. Un OFFSET profundo puede recorrer u ordenar
muchas filas en base: no se promete coste constante. Lo eliminado es el trabajo
cuadrático de DTOs y persistencia bajo el lock, no la lectura necesaria de
miembros relevantes.

La búsqueda histórica procesa cada lote y selección por separado, con lecturas
en ventanas; no acumula los grupos, operaciones ni intentos ORM de toda la
historia. La página viva recorre sus consultas con un solo cursor abierto y un
búfer fijo de identificadores, independiente del OFFSET y de la cantidad de
ramas. La relación compacta necesaria conserva su tamaño proporcional a las
pertenencias, sin truncar antecedentes ni cambiar el orden o los digest.

Verificar en SQLite y PostgreSQL: COUNT contra expansión sintética de referencia;
nombre/documento sin duplicación; nulos y ordinales con huecos; orden y digest
invariantes al permutar consultas; páginas iguales antes/después de persistir y
compactar; cero DTOs en resumen y límite real de página; máximo buffer de
inserción proporcional a pertenencias; G1/X y G2/Y; snapshot distinto con igual
aceptación; parámetros y páginas profundas. Una assertion de longitud final no
demuestra por sí sola esta puerta de recursos.

### DTO HTTP y errores estructurados

`LoteComprobanteResumenResponse` reemplaza el mensaje plano como autoridad por
un `control_duplicados` cerrado. Todos sus campos están presentes, aunque su
valor sea `null`, cero o una lista vacía:

```text
version: Literal["duplicados_lotes/v2"]
cobertura: Literal["completa", "parcial_legacy", "no_comprobable"]
estado: Literal[
  "sin_coincidencias", "requiere_confirmacion", "aceptada",
  "operacion_en_curso"
]
evidencia_id: str | null
datos_hash: str
seleccion_hash: str
tipos_coincidencia: list[Literal[
  "interna_receptor", "historica_completa", "historica_parcial_receptor",
  "historica_individual_legacy"
]]
cantidad_actual: int
cantidad_afectada: int
importe_actual: DecimalString | null
importe_afectado: DecimalString | null
importes_actuales: DuplicadosImportes
importes_afectados: DuplicadosImportes
antecedentes_resumen: list[DuplicadosAntecedenteResumen]
aceptacion_requerida: bool
aceptacion_habilitada: bool
bloqueo_operacion_ajena: DuplicadosBloqueo | null
detalle_url: str | null
```

Este resumen anticipa la evidencia para revisión, pero no emite una aceptación
reutilizable ni cambia estado. El diálogo accionable se abre con la evidencia
autoritativa de la operación idempotente; así el usuario decide una sola vez.
`evidencia_id` tiene forma `v2.<digest>`, donde `digest` es el SHA-256 base64url
sin padding del sobre canónico compuesto por versión, emisor, ambiente,
`datos_hash`, `seleccion_hash` y antecedentes relevantes con sus estados. La
revisión del coordinador se audita, pero no integra el digest: una operación no
relacionada no debe invalidar la evidencia. El ID es opaco para el cliente y
cambia sólo ante evidencia relevante.

`DuplicadosAntecedenteResumen` exige los siguientes campos y tipos:

```text
origen: Literal["lote", "comprobante_individual"]
lote_id: int | null
nombre_archivo: str | null
comprobante_ref: str | null
tipo_coincidencia: Literal[
  "historica_completa", "historica_parcial_receptor",
  "historica_individual_legacy"
]
cobertura: Literal["completa", "parcial_legacy", "no_comprobable"]
cantidad_lote_anterior: int | null
cantidad_coincidente: int
cantidad_autorizada: int
cantidad_solo_validada: int
cantidad_reservada_en_curso: int
cantidad_fallida: int
cantidad_incierta: int
importe_lote_anterior: DecimalString | null
importe_lote_actual: DecimalString | null
importe_afectado: DecimalString | null
importes_lote_actual: DuplicadosImportes
importes_lote_anterior: DuplicadosImportes | null
importes_afectados: DuplicadosImportes
emitido_desde: DateTimeISO | null
emitido_hasta: DateTimeISO | null
hora_confiable: bool
solicitantes: list[DuplicadosSolicitante]
```

`DuplicadosImportes` contiene `por_moneda`, una lista ordenada por código de
`{moneda: str, importe: DecimalString, cantidad: int}`, y
`cantidad_sin_moneda_acreditada: int`. Se suman centavos exactos únicamente
dentro de la misma moneda, sin conversión implícita por cotización. Los grupos
sin moneda acreditada se cuentan y quedan fuera de las sumas; sus importes
individuales pueden consultarse en el detalle. El desglose de lote anterior es
`null` para antecedentes individuales. Los escalares de importe sólo se pueblan
si todos sus componentes tienen una única moneda acreditada; mezcla o moneda
desconocida devuelve `null`. Un conjunto vacío permite `0.00` y desglose vacío.
La UI presenta los importes con su moneda y explicita los datos no acreditados.
Esto no habilita plantillas mixtas ni modifica la política de emisión.

Cada `DuplicadosSolicitante` exige `{usuario_id: int | null, nombre: str |
null, estado: Literal["registrado", "no_registrado"]}`. Los importes viajan
como strings decimales de dos posiciones. Los desconocidos conservan valores
nulos y la UI muestra «Usuario de emisión no registrado». No se atribuye el
lote al usuario actual ni al usuario que lo cargó. `DuplicadosBloqueo` exige
`{referencia: str, estado: Literal["reservada", "intento_en_curso",
"incierta"], cantidad_afectada: int, detectado_at: DateTimeISO | null}`; la
referencia es opaca y consultable dentro del mismo emisor, no un ID fiscal.
Para `origen="comprobante_individual"`, `lote_id`, `nombre_archivo`,
`cantidad_lote_anterior` e `importe_lote_anterior` son `null`,
`comprobante_ref` identifica el antecedente y los contadores describen ese único
comprobante. Para `origen="lote"`, ocurre lo inverso: `lote_id` y los agregados
del lote están presentes, y `comprobante_ref` es `null` en el resumen.

El detalle `GET /api/lotes-comprobantes/{lote_id}/coincidencias` exige
`evidencia_id`, usa `page>=1`, `per_page=50` por defecto y `1..100` como rango.
Ordena por grupo actual, lote anterior, grupo anterior, rango de origen/tipo,
comprobante anterior, clave de antecedente y clave de bloque. Los nulos van
primero mediante orden explícito; los desempates son constantes versionadas,
comunes al detalle vivo y durable, sin IDs autoincrementales de almacenamiento.
Devuelve obligatoriamente `items`, `page`, `per_page`, `total` y `total_pages`.
Cada ítem exige:

```text
grupo_actual_id: int
comprobante_actual_ref: str
origen: Literal["lote", "comprobante_individual"]
tipo_coincidencia: Literal[
  "interna_receptor", "historica_completa", "historica_parcial_receptor",
  "historica_individual_legacy"
]
campos_coincidentes: list[Literal[
  "nombre", "documento", "contenido_completo",
  "predicado_individual_vigente"
]]
lote_anterior_id: int | null
grupo_anterior_id: int | null
comprobante_anterior_ref: str | null
operacion_anterior_ref: str | null
estado_grupo_anterior: Literal[
  "cargado", "validado", "en_cola", "procesando", "autorizado",
  "autorizado_externo", "fallido", "requiere_reconciliacion"
] | null
importe: DecimalString
moneda: str | null
cotizacion: DecimalString | null
solicitantes: list[DuplicadosSolicitante]
solicitud_emision_at: DateTimeISO | null
solicitud_arca_at: DateTimeISO | null
resultado_fiscal_at: DateTimeISO | null
hora_confiable: bool
```

`comprobante_actual_ref` conserva la referencia del archivo del grupo actual,
incluida su materialización para consulta tras compactación; nunca se fabrica
desde un ID interno ni desde numeración fiscal. Una moneda o cotización histórica
no acreditada es `null`, sin sustituirla por `PES` o `1`.

Instantes e IDs que no puedan acreditarse son `null`; los demás campos siempre
están presentes. No devuelve CAE, documento completo ni correos; usa el
enmascarado permitido por la UI.

Una coincidencia interna usa `tipo_coincidencia="interna_receptor"` y
`origen="lote"`: `grupo_actual_id` identifica el grupo del lote consultado y
las referencias de lote/grupo/comprobante/operación anteriores son `null`. No
se la presenta como historia ni se inventa un lote anterior. El detalle
autoritativo conserva la selección vinculada a `evidencia_id`, también en un
reintento parcial; no la reemplaza por todos los grupos válidos o fallidos.
El contenido devuelto y el ID deben corresponder a la misma evidencia comprobada.

La evidencia autoritativa se publica desde `POST /procesar` o
`POST /reintentar-fallidos` bajo la clave idempotente. Si requiere decisión, la
operación existente pasa al estado ya vigente
`requiere_confirmacion_duplicado` y conserva la categoría HTTP vigente
`categoria_error=duplicado_logico_lote`. Responde `409` con el mismo
`control_duplicados` y un `aceptacion_id` opaco con forma `v2.<random>`, donde
`random` contiene 256 bits aleatorios en base64url sin padding. El ID se guarda
de forma durable dentro del control de esa operación, junto con `payload_hash`,
selección, versión y `evidencia_id`, para poder reexpedir exactamente el mismo
valor. Es correlación de una evidencia, no autenticación ni prueba de lectura;
la API sigue exigiendo sesión, emisor y clave idempotente válidos. Para la misma
operación y evidencia se devuelve el mismo ID: no vence sólo por tiempo ni
genera otra confirmación. Si cambia el material, se reemplaza durablemente y el
ID anterior deja de validar. La UI reenvía la misma `X-Idempotency-Key` y el
valor en
`X-Confirmacion-Duplicado-Logico` sólo después del checkbox. El header no acepta
`true`, un token de otro lote ni evidencia de resumen vencida. Así se conserva
el transporte existente sin introducir un booleano universal.

Si la evidencia cambió, la API mantiene la operación en
`requiere_confirmacion_duplicado`, invalida el ID recibido, devuelve uno nuevo y
no encola. `GET .../coincidencias` con un `evidencia_id` anterior responde
`409` con `categoria_error=duplicado_logico_lote` y el control actual; la UI
desmarca el checkbox,
reemplaza resumen/detalle y devuelve el foco a «Volver a revisar». Si existe una
operación ajena relevante en curso, responde `409` con
`categoria_error=duplicado_operacion_en_curso`, referencia consultable y
`aceptacion_habilitada=false`; no ofrece checkbox. Errores de coordinación o
persistencia responden una categoría pre-ARCA sanitizada y dejan cero intentos,
reservas fiscales y llamadas `FECAESolicitar` nuevas.

Durante una versión de transición el backend mantiene los campos planos
`confirmacion_duplicado_logico`, `mensaje_confirmacion_duplicado_logico` y
`cantidad_duplicados_logicos` como proyección compatible para clientes viejos;
en el `409` autoritativo el primer campo contiene el mismo `aceptacion_id` y en
el resumen v2 queda vacío. El frontend nuevo consume `control_duplicados` y
acepta ambas respuestas. Un token v1 sólo continúa una operación v1 ya
demostrable. Ningún cliente v1 puede encolar una operación v2 convirtiendo el
nuevo control en booleano. La proyección se retira únicamente en un corte
posterior con sus consumidores actualizados.

### Orden transaccional y exclusión de carreras

La sección crítica usa una tabla mínima
`lotes_duplicados_coordinacion(empresa_id, ambiente, revision, updated_at)`, una
fila por emisor y ambiente. Es necesaria porque un lock sobre el lote no
coordina dos lotes distintos y un lock sólo en memoria no cubre procesos. Tiene
PK/FK compuesta por emisor y ambiente, `CHECK` del ambiente admitido y se crea en
la expansión para ambos ambientes de cada emisor; el alta futura de emisores la
inicializa en la misma transacción.

El punto de entrada es después de que la operación idempotente y su snapshot
RECE quedaron comprometidos, y antes de escribir estado `en_cola`, tomar el
lote, crear intentos/reservas fiscales o consultar capacidad batch. La ruta
cierra cualquier transacción implícita de sólo lectura en ese punto; no hace
commit de intentos, guardas ni estado fiscal parcial. Luego inicia una
transacción corta y su primera escritura incrementa `revision`:

- PostgreSQL bloquea esa fila con `SELECT ... FOR UPDATE` y hace CAS de la
  revisión;
- SQLite abre `BEGIN IMMEDIATE` mediante un helper de coordinación y ejecuta
  `UPDATE revision = revision + 1` como primera operación de esa transacción
  nueva. Antes, la ruta termina con `rollback` cualquier transacción implícita
  que sólo haya leído; si la sesión tiene escrituras pendientes distintas del
  snapshot RECE ya comprometido, falla antes de abrir el helper en vez de
  confirmarlas. El helper usa la conexión de la sesión y devuelve el control a
  la misma sesión; no abre una segunda conexión, requisito que preserva los
  tests SQLite con conexión compartida. El lock de escritor de SQLite puede ser
  global, pero se mantiene sólo durante esta consulta/indexación y el CAS;
  nunca durante WSAA, WSFE, lectura de Excel ni espera de usuario. Un `busy`
  agota reintentos acotados y falla antes de CAE.

La ausencia de objetos nuevos o modificados en la sesión no acredita sólo
lecturas: un `flush` o `UPDATE` Core previo puede dejar escrituras pendientes.
La procedencia se conoce desde el inicio de la transacción raíz, registra DML
ORM/Core y SQL no acreditado, persiste después de `flush` y se limpia al cerrar.
Escrituras ajenas, procedencia desconocida o transacciones anidadas impiden abrir
la coordinación; no se resuelven con un commit genérico en el helper o su caller.
La coordinación rechaza esa sesión antes de apropiarse de ella y no ejecuta
commit ni rollback sobre la transacción ajena; el llamador conserva el control
de cerrarla. El rollback previo automático se limita a lecturas acreditadas.
Antes del rollback de lecturas se capturan IDs y DTO necesarios; después no se
accede a ORM expirado ni se abre un SELECT antes de `BEGIN IMMEDIATE`. Los
objetos requeridos se recargan explícitamente tras el commit propio. La revisión
del coordinador se escribe antes de comparar, también con `autoflush=False`.

Bajo ese lock se ejecuta, en este orden:

1. validar emisor, ambiente, pertenencia, operación idempotente, material RECE,
   datos y selección;
2. buscar por índices lotes candidatos y reservas de otras operaciones; para
   cada candidato cargar el conjunto delimitado completo y sus estados, sin
   unir grupos de antecedentes distintos; buscar también el borde vigente de
   comprobantes individuales autorizados; excluir operación y lote propios;
3. recalcular la evidencia v2;
4. rechazar una reserva o intento fiscal ajeno activo, o una operación ajena
   incierta; una mera carga `validado` no entra en este bloqueo;
5. si falta aceptación o cambió la evidencia, persistirla en
   `control_duplicados_json`, publicar por CAS
   `requiere_confirmacion_duplicado` y terminar sin reserva;
6. si no hay advertencia o la aceptación coincide exactamente, publicar por CAS
   la decisión y asignar `duplicados_reserva_operacion_id` a los grupos
   seleccionados;
7. para background, dejar en la misma unidad el ownership durable que permite
   `en_cola`; para síncrono, comprometer la reserva y continuar después.

El lock se libera antes de cualquier llamada externa. La reserva durable hace
visible la selección delimitada completa —incluidos anónimos— por sus huellas y
operación, y las claves parciales identificadas por sus índices, sin leer JSON
histórico. Para decidir el conflicto siempre combina esa selección original
inmutable con el estado actual de cada grupo: que una operación ya haya
autorizado `x` y conserve pendiente `y` no reduce su conjunto reservado de
`{x,y}` a `{y}`. Una reserva ajena sólo bloquea anónimos si ese multiconjunto
original completo es igual; una superposición aislada no alcanza. Dos lotes
iguales que validaron ausencia pueden competir, pero sólo uno publica primero
su reserva; el segundo observa `duplicado_operacion_en_curso`.

Al autorizar un grupo, su estado fiscal se vuelve evidencia histórica y deja de
ser una mera reserva. Un rechazo ARCA verificable o un aborto pre-ARCA probado
libera sólo ese grupo. Una autorización parcial ajena mantiene autorizados los
grupos logrados y reevalúa los restantes; una autorización parcial propia no
se enfrenta consigo misma. Un intento `en_proceso`, un resultado incierto o
una falla posterior a CAE conserva la reserva y bloquea el checkbox hasta
reconciliar. Un retry readquiere bajo el coordinador la reserva de sus grupos
liberados; la aceptación previa nunca sustituye esa reserva. Los grupos propios
ya autorizados permanecen fuera del retry y no vuelven a emitirse.

Los preflights unitario, batch y de reintento recalculan la relevancia v2 sobre
la selección original completa. Los grupos enviables determinan qué se emite,
no reemplazan esa selección después de un resultado parcial. Una consulta
plural exclusiva del consumidor de lotes conserva el predicado individual
vigente y clasifica todos sus resultados por origen: un testigo de lote no
puede ocultar uno individual. La ruta individual conserva su helper, DTO,
huella y política sin cambios.

Además del control temprano, se revalida dentro de la frontera fiscal existente,
después de readquirir numeración y RECE y antes de crear guarda e intentos. Esta
lectura no abre otra coordinación ni confirma DML ajeno. Encontrar un
antecedente nuevo obliga a evaluar su relevancia: una superposición anónima
aislada, el progreso propio, el orden de consulta y una mera carga ajena no
invalidan aceptación ni agregan una confirmación. Los antecedentes sólo
validados pueden figurar como contexto fuera del digest que gobierna la
decisión. Los testigos relevantes se ordenan canónicamente antes de calcularlo.

Un cambio relevante devuelve una señal tipada al orquestador del lote, que
publica evidencia estructurada bajo coordinación y termina el paso antes de
`FECAESolicitar`. Los manejadores genéricos no convierten esa señal en rechazo
ni incertidumbre fiscal. Se preservan las autorizaciones ya comprometidas;
sólo se restauran o liberan mediante CAS los claims y reservas del paso
demostrablemente no enviado. No se fuerza todo el lote a `validado` ni se
interpreta una autorización previa de `x` como incertidumbre de `y`. No existe
un bypass general del origen lote ni una lista durable de descartes que
sustituya la revalidación de relevancia.

Una reserva stale sólo puede liberarse mediante recuperación server-side que
demuestre operación pre-ARCA recuperable, ausencia de intento, guarda RECE, CAE,
número y comprobante, y CAS al estado seguro vigente. El navegador nunca decide
su liberación. El worker ejecuta la misma sección crítica antes de tomar un lote
o reintento; caminos unitarios y agrupados consumen la decisión ya validada.
Recupera la aceptación durable sin exigir el header del navegador ni renovar
su actor o instante; sólo la reutiliza si operación, material, selección y
evidencia siguen coincidiendo. Si requiere otra decisión, publica el control
estructurado y deja el lote fuera de la cola automática, conservando una
continuación verificable para la UI. El lock del coordinador se libera antes
de cualquier llamada externa.

### Replay, actor y revocación de acceso

Un replay terminal durable se devuelve antes de validaciones mutables y nunca
crea otra confirmación. Un replay no terminal usa la misma operación raíz. Una
aceptación anterior cubre sólo los mismos grupos y huellas bajo la misma
evidencia; un reintento de grupos fallidos puede reutilizar esa cobertura si es
una continuación demostrable del mismo lote y no apareció evidencia ajena.

La API congela al solicitante y `solicitud_emision_at` al crear la operación; la
aceptación de excepción agrega `aceptada_por_usuario_id`, nombre snapshot y
`aceptada_at`, sin afirmar lectura humana. El worker carga `usuario_id` y nombre
desde esa operación aunque se ejecute sin usuario; no usa el creador del lote ni
un actor de preflight RECE. Cada intento conserva ese solicitante, por lo que un
lote con reintentos de varias personas muestra todos los solicitantes
pertinentes. La advertencia usa `resultado_fiscal_at` como instante de emisión y
distingue ese dato de la solicitud y la aceptación.

Crear la operación, aceptar una excepción, reintentar o reconciliar exige acceso
vigente al emisor. Una revocación posterior no cancela un trabajo que ya quedó
aceptado y encolado con datos inmovilizados; el worker puede terminarlo bajo su
actor congelado. Sí bloquea nuevas operaciones, cambios, excepciones y
reintentos. Una incertidumbre ya iniciada conserva reconciliación y nunca se
reinterpreta como rechazo por la revocación.

### Transición legacy, despliegue y rollback

La migración es aditiva y nullable. El backfill sólo calcula huellas cuando el
`payload_json` existente pasa el `EmitirComprobanteRequest` estricto y conserva
emisor/ambiente/PV coherentes. En ese caso puede acreditar contenido fiscal
normalizado y multiconjunto, y recuperar los hashes y originales de nombre o
documento que todavía estén presentes en el payload para la comparación, sin
modificar el receptor fiscal. No puede acreditar la identidad de entrada que el
importador configurable borró, actor histórico ni hora inequívoca: marca esa
cobertura como `parcial_legacy`. Payload inválido, ambiente indeterminado o
campos faltantes quedan `no_comprobable`; nunca se traducen a ausencia.

El booleano antiguo no se copia como una aceptación v2. El token v1 sólo hashea
las huellas de los grupos actuales afectados y su cantidad; no contiene IDs ni
orígenes de los testigos históricos. Además, el `response_json` del `409` se
borra al reclamar la operación. En `metadata_json`, `duplicados_logicos`
corresponde al cálculo realizado durante la importación, mientras
`confirmacion_duplicado_logico` es el booleano que se fija al encolar o procesar.
Ninguno prueba cuáles fueron los testigos históricos. Por ello token, selección
y metadatos no permiten demostrar qué evidencia ajena se aceptó ni afirmar que
sigue igual.

Antes del corte se drenan las operaciones v1 ya aceptadas bajo las reglas
vigentes. Las pendientes de confirmar no son aceptaciones: después del corte se
evalúan y deciden con v2. Un remanente terminal conserva replay exacto. Un
remanente no terminal pre-ARCA sin coincidencias actuales puede continuar; uno
incierto debe reconciliar. Si tiene coincidencias actuales y sólo consta una
aceptación histórica no comprobable, el servidor conserva payload, hash,
respuesta y estado, y bloquea su continuación y reintento de emisión conforme a
la decisión de producto que figura abajo. La UI no atribuye evidencia, lectura,
usuario ni hora que no estén guardados.

La admisión de un remanente v1 aceptado sin coincidencias actuales debe unir
clasificación, creación o reclamo de operación y reserva en una misma
transacción coordinada. Si aparece un antecedente antes de adquirir la
coordinación o falla la reserva, no puede quedar un commit parcial que altere
la historia o deje otra operación creada. Las comprobaciones externas se
preparan fuera de esa frontera; el replay terminal se resuelve antes de las
validaciones mutables.

No se admite ejecución simultánea de productores v2 con workers v1: un worker
viejo no entiende la reserva ni la aceptación estructurada. El despliegue debe
drenar o detener el worker embebido, comprobar que no queden lotes
`en_cola`/`procesando` ni aceptaciones v1 no terminales sin la clasificación
anterior, aplicar la expansión y el backfill, y recién entonces iniciar todos
los procesos v2. No es un rolling upgrade entre contratos.

El rollback detiene primero productores y workers v2. La aplicación anterior no
puede arrancar si existen operaciones, reservas o evidencia v2; se conserva el
schema expandido y se usa una versión compatible que las lea o bloquee. El
downgrade físico sólo elimina columnas/tabla cuando una comprobación sanitizada
demuestra cero registros v2 y existe backup verificable. Si hay evidencia nueva,
aborta sin borrarla. No se hace backfill inventado ni se degradan aceptaciones o
incertidumbre a booleanos.

## Compatibilidad e invariantes

### Paquete del migrador local

El traslado local SQLite a PostgreSQL debe conservar la evidencia necesaria
para continuar este control. El formato técnico del paquete evoluciona a v4;
esto no fija la versión de release de FactuFlow. Las tablas previamente
incluidas se conservan, mientras una selección verificable agrega la evidencia
requerida por PF-13 y por la coherencia de los replays terminales incluidos:

- operaciones v2, sus raíces, selecciones originales y testigos;
- lotes históricos con grupos autorizados o autorizados externamente cuya
  representación comparable v2 puede intervenir en futuras coincidencias;
- todos los grupos de cada lote alcanzado, para conservar su multiconjunto
  completo y no confundir un subconjunto con un lote idéntico;
- intentos terminales y guardas RECE requeridos por esos grupos;
- generaciones publicadas y origen de sus aceptaciones, bloques y miembros;
- vínculo de cada intento con la generación que habilitó su envío.

La selección conserva además los lotes de rechazos batch PF-19C exactos, con
sus grupos y relaciones históricas requeridas, y los intentos y guardas durables
de operaciones individuales terminales. Así los validadores pueden contrastar
el replay con su evidencia fiscal. Cuando existe una revisión RECE histórica,
el número del punto de venta se coteja contra su snapshot, aunque el número
vigente haya cambiado. Esto no modifica la política de emisión individual ni
reconstruye evidencia ausente.

Filas del Excel, eventos, archivos y demás historia ajena al control siguen
excluidos. Las operaciones cuyo lote se preserva mantienen `lote_id`; las
operaciones legacy cuyo lote se omite conservan la normalización anterior a
`null`, con atestaciones distintas y mutuamente excluyentes.

El coordinador por emisor/ambiente se valida, pero no se copia como evidencia:
el importador regenera los dos ambientes exactos por empresa con revisión cero.
El manifest distingue tablas completas, filtradas, regeneradas y excluidas;
atestigua raíces, clausura y cantidades fuente/exportadas/omitidas. La barrera
incluye control, aceptación, selección, actor, tiempos, huellas, reservas,
intentos, guardas, generaciones, bloques y miembros. Verifica formatos,
ordinales, ambos hashes y herencias de aceptación, incluida la clausura recursiva
de generaciones origen. El preflight y el postflight verifican pertenencia,
FKs y coherencia de esos vínculos, sin omitir filas necesarias para preservar
la comparación y sin trasladar operaciones activas o inciertas.

El exportador genera v4. La lectura de un paquete v3 usa su schema, partición y
head conocidos con validación estricta congelada, sin aceptar campos extra ni
versiones arbitrarias. Un adaptador deja las columnas v2 nuevas en `null`,
conserva los pares normalizados y regenera coordinadores. No inventa historia
de lotes omitida por v3 ni transforma booleanos/tokens v1 en aceptación v2. Las
limitaciones de cobertura histórica permanecen explícitas.

La verificación incluye roundtrip PostgreSQL, multiconjunto completo, operación
legacy normalizada, paquete v3 sintético, destino sucio y manipulación de raíz,
huella, actor, tiempo, reserva o detalle. El procedimiento reutilizable vive en
[`docs/setup/vps-migration.md`](../setup/vps-migration.md). No autoriza una
migración de instalación ni acceso a producción.

### Garantías del control

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
| Contenido | Excel renombrado; filas reordenadas; mismo nombre/cantidad/total con datos diferentes; multiplicidades distintas; cambio de descripción con receptor/fecha/total coincidentes; moneda/cotización distinta; tipo/letra o PV distinto no es parcial comparable |
| Historia | Lote completo anónimo repetido contra un antecedente delimitado igual; nuevo 1 vs anterior 100 con una fila anónima igual permanece silencioso; nuevo 100 vs anterior 100 igual pero parcialmente emitido distingue cada resultado y no atribuye emisión total; varios antecedentes iguales por separado; coincidencia parcial identificada; separación entre coincidencias internas e históricas |
| Caso sintético integral | Primer lote con ventas anónimas repetidas no advierte internamente; un segundo Excel con formato visual distinto, distinta huella de carga y el mismo contenido contable detecta el conjunto ya autorizado y exige la excepción informada |
| Usuario/horarios | Usuario que carga distinto del que solicita emitir; worker; cuenta renombrada; actor ausente; varios actores; hora histórica sin zona; no atribuir emisión al usuario actual |
| Acciones | Retorno es el botón más destacado antes/después del checkbox; foco inicial seguro; checkbox vacío; marcar no emite; excepción secundaria sólo habilitada tras marcar |
| Navegación/accesibilidad | Enter implícito no emite; Escape/cierre vuelven; teclado deliberado funciona; foco al volver del detalle; móvil/zoom/lector de pantalla; no pérdida de archivo/opciones |
| Invalidación | Cambio de lote, emisor, selección, datos o coincidencias borra aceptación; respuesta vieja no habilita; datos sin cambios no agregan confirmaciones repetidas |
| API/worker | Sin confirmación válida no hay CAE; validación de servidor aunque se omita UI; mismo control en cola, reintentos y envío unitario/agrupado |
| Concurrencia | Dos lotes validados en paralelo; uno emite mientras otro confirma; dos workers; mismo request duplicado; la segunda operación no usa evidencia obsoleta |
| Invariantes | Replay sin nuevo CAE; misma clave/payload distinto en conflicto; misma carga bloqueada; incertidumbre no eludible; aislamiento por emisor/ambiente; emisión individual preservada |
| Persistencia/recursos | Detección y excepción siguen auditables tras finalizar/compactar; datos legacy explícitos; consultas acotadas, índices y detalle paginado para VPS pequeño |

### Matriz automatizada de aceptación

Esta matriz es normativa: define responsabilidades y casos obligatorios, pero
la presencia de un archivo no acredita que sus pruebas se hayan ejecutado o
superado.

| Archivo | Casos que debe demostrar la implementación |
|---|---|
| `backend/tests/test_duplicados_lotes_v2.py` y consumidores de `backend/tests/test_lotes_comprobantes.py` | Preservación separada de identidad de entrada y receptor fiscal; tabla completa de nombres/documentos; consumidor final 99/0; igualdad exacta de centavos, moneda y cotización; tipo y PV exactos para parcial; multiconjunto de ítems y comprobantes; archivo renombrado, filas reordenadas y distinta huella de carga; nuevo 1 vs anterior 100 anónimo; nuevo 100 vs anterior 100 parcialmente emitido; antecedentes completos evaluados por separado; `origen=lote` y `origen=comprobante_individual`; el individual mantiene exactamente el predicado vigente, incluido su match anónimo actual, con lote/grupo/archivo nulos y sin inventarlos; resumen, 409 y detalle paginado; selección e invalidación; una revisión ajena irrelevante no cambia `evidencia_id`; misma evidencia reexpide el mismo `aceptacion_id`; actor de operación; lote parcial propio; compactación; legacy parcial y no comprobable |
| `backend/tests/test_lotes_comprobantes.py` — worker/recovery | Cola con selección original completa visible; pausa tras autorizar `x` antes de `y` conserva `{x,y}`; rechazo de `y` y retry readquieren sólo `y` y jamás reemiten `x`; worker sin usuario usa el solicitante congelado; caminos unitario y batch del lote, cola y retry revalidan ambos orígenes; una emisión individual entre preflight y envío invalida cobertura; retry continúa la operación raíz; stale pre-ARCA libera sólo con evidencia cero; una mera validación ajena no bloquea; reserva, intento en curso e incertidumbre ajenos sí bloquean; autorización parcial propia no repite y la ajena cambia evidencia |
| `backend/tests/test_facturacion_service.py` | `EmitirComprobanteRequest` y emisión individual permanecen iguales; el batch sólo activa el bypass interno con control v2 válido; `calcular_huella_logica`, `buscar_duplicado_logico`, payload SOAP, segundo preflight, rechazo e incertidumbre no cambian |
| `backend/tests/test_comprobantes_api.py` | Emisión individual conserva DTO estricto, booleano vigente, hash y replay; campos o headers v2 de lotes no amplían su contrato |
| `backend/tests/integration/test_pf13_duplicados_postgresql.py` | Migración expandida y downgrade fail-closed, índices, FKs/CAS y dos sesiones que compiten por emisor+ambiente; sólo una publica reserva y la otra ve operación ajena; emisores/ambientes distintos no se bloquean entre sí |
| Regresiones en `backend/tests/integration/test_integridad_fiscal_postgresql.py` y `backend/tests/integration/test_pf19c_runtime_postgresql.py` | La coordinación PF-13 no altera integridad fiscal, rechazo global, reservas fiscales, incertidumbre, reconciliación ni replay durable bajo PostgreSQL |
| Harness PostgreSQL | Sólo loopback, base exacta `factuflow_integration_test`, opt-in de reset y destrucción revalidada; nunca credenciales ni base productiva |
| `frontend/src/components/comprobantes/DuplicadosLoteDialog.spec.ts` | Jerarquía visual del diálogo; retorno principal y foco; checkbox vacío; Enter/Escape; aceptación secundaria; actor/hora desconocidos; contenido completo/parcial; operación ajena; detalle paginado y vuelta con foco |
| `frontend/src/views/comprobantes/LotesComprobantesView.spec.ts` | Resumen completo/parcial; retorno principal y foco; checkbox vacío; Enter/Escape; aceptación secundaria; respuesta atrasada; cambio de lote/emisor/selección/evidencia; espera por operación ajena; actor/hora desconocidos; detalle paginado y vuelta con foco |
| `frontend/src/services/lotes-comprobantes.service.spec.ts`, `frontend/src/services/lotes-comprobantes.service.ts` y `frontend/src/types/lote-comprobante.ts` | DTO cerrado, consulta paginada, `aceptacion_id` opaco, mismo idempotency key, categorías 409 y ausencia de booleano universal v2 |
| `frontend/e2e/lotes-comprobantes.spec.ts` | Caso sintético integral; navegación por teclado; doble click/replay; carrera simulada; error pre-CAE recuperable; incertidumbre no reintentable; ninguna llamada real a ARCA |

La matriz debe incluir además pruebas explícitas de aislamiento por emisor y
ambiente, misma clave con payload distinto, confirmación fiscal ausente, pérdida
de conexión antes de la reserva, fallo al persistir la reserva, caída después de
CAE, cuenta revocada después de encolar y respuesta de aceptación atrasada. En
todos los abortos anteriores a ARCA se verifica cero intento fiscal nuevo y cero
`FECAESolicitar`; los dobles distinguen las lecturas WSFE seguras para no afirmar
«cero contacto con ARCA» cuando no corresponde.

### Checklist fiscal completado para iniciar código

| Sección del checklist | Resolución de diseño |
|---|---|
| Alcance y riesgo | Cambian importación, lote, UI, API, worker, retry, recuperación, persistencia y migración. Puede alcanzar CAE indirectamente. El fallo crítico sería duplicar comprobantes, atribuir a otra persona, usar evidencia obsoleta, mezclar emisores o liberar incertidumbre. Emisión individual queda excluida y preservada. |
| Invariantes | Fecha/PV explícitos y confirmación irreversible siguen obligatorios. Idempotencia, payload hashes, numeración, RECE, aislamiento, estados inciertos y restricción de misma carga no se reducen. La excepción de similitud nunca autoriza una operación fiscal ya emitida o incierta. |
| Estados y transiciones | Se reutiliza `requiere_confirmacion_duplicado`; la evidencia/decisión vive separada de la respuesta. Lote validado espera sin encolar; reserva aceptada habilita sync/cola; autorización se vuelve historia; rechazo o aborto pre-ARCA probado libera; incertidumbre bloquea y reconcilia. |
| Orden | Emisor/pertenencia → fecha/PV/RECE → operación idempotente → sección crítica de duplicados → confirmación fiscal y ownership vigentes → reservas/segundo preflight → `FECAESolicitar` → persistencia de resultado. Replay terminal precede validaciones mutables. |
| Fallos | Están definidos doble request, payload conflictivo, aceptación ausente/vencida, operación ajena, DB busy/timeout, worker caído, stale, rechazo, autorización parcial y fallo post-CAE. Sólo la ausencia durable de evidencia fiscal permite recuperación pre-ARCA. |
| Concurrencia | Coordinador por emisor+ambiente, transacción corta, CAS y reserva por grupo en ambos motores. No hay lock durante ARCA ni reserva manual del emisor. |
| Contrato ARCA | El comparador es local. No agrega llamadas ni interpreta respuestas ARCA. Conserva `FECompUltimoAutorizado`, `FECAESolicitar`, `FECompConsultar` y sus reglas de incertidumbre actuales. |
| Migración y rollback | Expansión nullable, backfill sólo determinista, cobertura legacy explícita, productor/worker de una misma versión y downgrade que no borra evidencia v2. |
| Tests y privacidad | La matriz anterior cubre feliz, error, concurrencia, replay, legacy, compactación y motores. Sólo usa datos sintéticos, documentos enmascarados y dobles; no solicita CAE real. |

Con esto quedan cerrados para las operaciones v2 de este corte los contratos de
normalización, precisión, comparabilidad parcial, campos completos, DTO,
persistencia, coordinación, actor y rollback. Para los remanentes no terminales
v1 que tengan coincidencias actuales y una aceptación histórica imposible de
reconstruir, la decisión del usuario es conservar el bloqueo de continuación y
reintento de emisión. Esos lotes permanecen disponibles como historia, sin
reutilizar su aceptación ni habilitarlos mediante una reconfirmación. El trabajo
nuevo se prepara en lotes creados con la nueva versión, sujetos a los controles
vigentes de contenido, misma importación, idempotencia y aislamiento.

Esta decisión corresponde a la categoría consultada: no elimina la consulta,
el replay terminal ni la reconciliación de resultados inciertos, ni exige
emitir esos remanentes bajo la versión anterior como condición del despliegue.
Se conservan las demás reglas de clasificación y drenaje de la transición;
crear un lote nuevo no permite eludir una emisión incierta o ya autorizada.
Las alternativas anteriores de reconfirmación excepcional y cierre previo bajo
la versión anterior quedan descartadas para esta categoría.

El corte mantiene este bloqueo sin degradar ni borrar la aceptación legacy.
Ampliar la lista de nombres genéricos, cruzar letras o puntos de venta, permitir una carga
idéntica como operación nueva, agregar otro aprobador, un motivo, un panel de
presencia o cambiar la política individual también requeriría una decisión de
producto nueva; nada de eso es necesario para implementar el resto del contrato
aceptado.

La implementación de este contrato es Nivel 2 y debe completar las pruebas y
puertas de [calidad](change-quality-gates.md) antes de integrarse. La matriz
define los criterios de aceptación; sus resultados técnicos y la validación
visual/contable se registran por separado. Este diseño no acredita un despliegue.
