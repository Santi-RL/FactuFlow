# PF-17/PF-15 — usuario e historial de actividad de lotes

Fecha: 05/09/2026.

Estado: decisión de presentación solicitada; implementación pendiente. Este
documento prepara el cambio sin modificar código ni producción.

## Objetivo y alcance

Identificar desde la aplicación quién realizó la emisión de un lote y consultar
su historia cuando haga falta. La vista habitual agrega únicamente el nombre
del usuario de la última emisión confirmada; el detalle histórico se despliega
al hacer clic en el lote. No añadir una tabla de auditoría permanente, otra
pantalla, confirmaciones ni pasos para emitir.

PF-17 es dueño de esta presentación y PF-15 de la procedencia y conservación
de la actividad. El corte permanece en «Más adelante» junto con PF-17; no
desplaza el trabajo vigente de recuperación/trazabilidad de «Ahora». Comparte
la fuente del actor con el
[diseño de duplicados PF-13](pf-13-duplicados-lotes-design.md), sin cambiar
advertencias, permisos ni guardas fiscales. La evolución general de la
distribución se concentra en el [diseño de UI de lotes](pf-17-lotes-ui-design.md);
este documento conserva la autoridad sobre atribución y apertura de actividad.

## Vista y comportamiento observados

La exploración de la sección de lotes verificó la disposición de escritorio,
la selección de otro lote completado y el despliegue del resumen operativo.
Se volvió al lote inicial. La observación fue sólo de consulta; la evidencia
privada y los datos reales de la pantalla no se incorporan a este documento.

En [LotesComprobantesView.vue](../../frontend/src/views/comprobantes/LotesComprobantesView.vue):

- «Lotes recientes» ocupa una columna lateral, con tarjetas que muestran archivo,
  fecha de carga, estado y una métrica principal. La tarjeta activa se resalta.
- Hacer clic llama a `cargarDetalleLote` y cambia el panel principal del lote
  en la misma pantalla. No abre un modal ni una página independiente.
- La cabecera principal muestra archivo, estado, mensaje, siguiente acción y
  fechas de carga/inicio/fin. Le siguen totales y avance.
- «Resumen operativo completo» despliega contadores; «Detalle de comprobantes»
  contiene el detalle fiscal. Ninguno muestra actualmente un historial de actores.

## Ubicación y apertura del detalle

Las ubicaciones siguientes parten de la vista actual. Al implementar la
evolución de UI, conservar su jerarquía: autor junto a los datos breves del lote
y actividad después del resultado/avance, antes de los detalles operativos.
La distribución exacta se revisa con el usuario en la aplicación local según
el diseño de UI enlazado, sin cambiar la atribución ni exigir un segundo clic
para abrir actividad.

| Lugar | Cambio solicitado |
|---|---|
| Cada tarjeta de «Lotes recientes» | Añadir una línea discreta **«Última emisión por: Nombre»**, debajo de «Cargado…» y antes de la métrica principal. Conservar archivo, estado y métrica; no listar aquí quién cargó, eventos, horarios adicionales ni varios participantes. |
| Cabecera del lote activo | Mostrar la misma línea junto a la información temporal existente, sin aumentar la jerarquía frente al archivo, estado o acciones. No añadir un bloque histórico abierto por defecto. |
| Panel principal del lote seleccionado | Incorporar **«Actividad del lote»** inmediatamente después de «Avance del lote» y antes de «Resumen operativo completo». Es una sección plegable propia, separada de contadores y comprobantes. |

La actividad comienza plegada, incluso si la pantalla selecciona un lote
automáticamente al cargar. **Un clic en una tarjeta selecciona el lote y abre
su actividad en el panel principal**, sin exigir otro clic para ver el historial.
Si ya estaba seleccionado, el clic abre o trae a la vista su actividad.
La cabecera «Actividad del lote» permite plegarla y volver a abrirla.

Actualizar automáticamente el lote o su progreso no abre secciones, mueve el
foco ni despliega la historia. Cambiar de lote descarta el historial anterior
y carga sólo el solicitado; conservar la preparación de un archivo y sus
opciones. Al pulsar una tarjeta con teclado o en móvil, llevar a la vista el
encabezado de actividad de forma accesible, sin enfocar botones de emisión.
Las tarjetas siguen siendo compactas; los nombres largos deben poder leerse
completos en el panel sin depender de hover ni mostrar correos.

## Qué usuario corresponde mostrar

«Última emisión por» identifica al usuario que **solicitó la operación que
produjo la última emisión confirmada del lote**. Si el procesamiento fue en
segundo plano, mostrar al solicitante, no al worker ni al usuario que consulta.
Validar o cargar el Excel no significa emitir.

| Situación | Regla |
|---|---|
| Una persona carga y otra confirma la emisión | Mostrar a quien confirmó la emisión que efectivamente autorizó comprobantes. La carga aparece en actividad. |
| Una persona emite una parte y otra emite el resto | Mostrar al actor de la última emisión confirmada. El historial conserva participantes, alcance y resultado de cada operación; no atribuir todo el lote al último. |
| Reintento posterior fallido, descarte o compactación por otra persona | No reemplaza al usuario de la última emisión exitosa. Registrar la acción en actividad. |
| Lote validado, en cola o procesando sin autorizaciones confirmadas | No mostrar «Última emisión por» ni atribuir éxito anticipadamente; conservar el estado operativo existente. |
| Lote con emisión parcial y otra operación pendiente o incierta | Conservar el actor de la última emisión confirmada si se conoce, junto al estado real del lote. No presentarlo como finalizado. |
| Emisión existente con actor o cronología no acreditados | Mostrar **«Usuario de emisión no registrado»**; explicar el límite dentro de actividad, sin inferirlo del creador o del usuario actual. |
| Reconciliación de una autorización previa o de emisión externa | Quien reconcilia no pasa a ser quien emitió. Conservar el actor original si está acreditado; separar «Reconciliado por» en la actividad. |

Derivar el último actor del orden acreditado de emisiones exitosas, con desempate
estable. No ordenar por la fecha fiscal, por el mayor número de comprobante ni
por una actualización de almacenamiento. Si no puede determinarse qué emisión
fue última, mostrar el límite en lugar de escoger un usuario arbitrario.

## Contenido de «Actividad del lote»

Presentar una lista breve, de lo más reciente a lo más antiguo, con **acción,
usuario, fecha/hora y resultado**. Agrupar los comprobantes de una misma
operación para evitar cientos de filas. Ofrecer «Ver anteriores» con paginado
cuando sea necesario y un detalle de alcance sólo bajo demanda.

Ejemplos sintéticos de acciones: «Emisión completada», «Emisión parcial»,
«Emisión solicitada», «Reintento fallido», «Archivo cargado y validado»,
«Comprobantes descartados», «Resultado reconciliado» y «Detalle compactado».
No afirmar que una solicitud de emisión tuvo éxito hasta conocer su resultado.
Las acciones automáticas se identifican como «Sistema», conservando por separado
la solicitud humana vinculada cuando exista.

Usar nombres legibles, fechas `DD/MM/AAAA` y horas argentinas. Si sólo se conoce
el momento de confirmación o registro, etiquetarlo como tal; no convertir una
reconciliación tardía en una emisión nueva. No inventar eventos o zonas horarias
para registros históricos incompletos. Mostrar «Historial parcial» cuando falte
evidencia; un fallo al consultar se muestra como error con reintento, no como
«Sin actividad» ni «Sin emisiones».

La lista no incluye claves internas, JSON, credenciales, CAEs, CUITs ni datos
de destinatarios innecesarios. Registra decisiones recibidas, no que una persona
leyó o ignoró un mensaje. Una cuenta compartida sólo identifica la cuenta usada.

## Fuentes y contrato para implementar

- [LoteComprobante](../../backend/app/models/lote_comprobante.py) conserva
  `usuario_id` de carga y eventos operativos. No reutilizar ese campo como
  autor de emisión; tampoco asumir que los eventos actuales cubren toda la vida
  de cada lote.
- [La API de lotes](../../backend/app/api/lotes_comprobantes.py) vincula el usuario
  solicitante a operaciones. Los [modelos fiscales](../../backend/app/models/idempotencia_fiscal.py)
  relacionan operación, intento y comprobante. Debe verificarse esa relación
  para atribuir una autorización concreta, incluidos reintentos y parciales.
- El [worker](../../backend/app/services/lote_worker.py) ejecuta en segundo plano;
  no basta leer el actor de un intento aislado, que puede no estar informado.
  Resolver la procedencia desde la operación humana vinculada, sin sustituirla
  por otro usuario. Inventariar caminos síncronos, agrupados, reintentos y recuperación.
- El listado debe entregar el resumen mínimo de autoría de forma eficiente,
  sin una consulta de usuarios ni de todo el historial por cada tarjeta.
  La actividad se obtiene bajo demanda para el lote seleccionado, con permisos
  del emisor y paginado estable. No exigir acceso a la administración de usuarios
  para leer los nombres pertinentes de un lote ya autorizado para consulta.
- Definir un contrato compartido de identidad/procedencia con la advertencia de
  duplicados. Aquella debe mostrar todos los actores pertinentes de sus
  coincidencias; esta tarjeta sólo resume el último. No reducir una a la otra.
- Conservar actor histórico, instante, acción, resultado y vínculo de evidencia
  mínimos frente a renombrado/desactivación de cuentas, finalización del lote,
  compactación y replays. No duplicar cada polling ni cada comprobante en la
  historia visible. Reutilizar registros durables y versionar la transición si
  faltan datos; no reescribir huellas fiscales ni inventar un historial retroactivo.
- Descartar respuestas de otro lote/emisor y mantener coherencia entre resumen
  y actividad. La consulta nunca modifica el lote, reintenta emisión ni llama a
  ARCA. Un error de actividad no debe disparar una operación fiscal.

## Matriz de aceptación

| Caso sintético | Resultado requerido |
|---|---|
| Carga inicial automática; tarjetas recientes | Sólo el último actor como dato nuevo visible; historial plegado, sin lista permanente. |
| Clic en otro lote o en el ya seleccionado | Se abre su actividad en el panel existente con ese mismo clic; sin modal, nueva pantalla ni pérdida de la preparación. |
| Actualización de progreso o listado | No abre actividad ni cambia foco; conserva el lote y la decisión de plegado del usuario. |
| Carga por Usuario A y emisión por Usuario B, en primer plano o worker | Resumen muestra B; actividad distingue A/B sin atribuir la emisión al proceso automático. |
| A emite una parte, B termina, C compacta o falla al reintentar | Resumen conserva B; actividad muestra alcance y resultado de A, B y C. |
| Pendientes, fallos, incertidumbre y reconciliación | No inventa un emisor exitoso ni sustituye al original por quien reconcilia. |
| Usuario renombrado/desactivado, actor ausente, hora incierta | Procedencia histórica conservada o límite explícito; nunca usuario actual como reemplazo. |
| Lote terminado/compactado y replay | Autoría y eventos siguen consultables, sin duplicarlos ni reemitir. |
| Cambio rápido de lote/emisor, permisos revocados y error de consulta | Sin filtraciones, historial anterior mezclado ni falsos estados vacíos. |
| Lote grande, nombres largos, móvil, teclado y lector de pantalla | Tarjetas compactas, nombres legibles, actividad agrupada/paginada y foco coherente. |
| Advertencia de duplicados y detalle del lote | Fuente de actor coherente; el resumen del último no elimina participantes del detalle ni de la advertencia. |

Antes de codificar, cerrar fuente y orden de autoría, cobertura histórica,
contratos de resumen/actividad, persistencia mínima y migración reversible si
corresponde. Aplicar [puertas de calidad](change-quality-gates.md) y el
[checklist fiscal](fiscal-change-checklist.md) si se modifican emisión,
aislamiento o persistencia fiscal. Conservar validaciones y confirmaciones
existentes; verificar con datos sintéticos sin CAE real. Manual/API/QA se
actualizan al implementar. Esta actualización documental es Nivel 0.
