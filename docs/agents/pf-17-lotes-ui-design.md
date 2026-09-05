# PF-17 — UI compacta de emisión masiva

Fecha: 05/09/2026.

Estado: dirección de cambio aceptada; implementación y revisión visual local
pendientes. Este documento prepara el trabajo futuro, sin modificar runtime.

## Objetivo y alcance

En `/comprobantes/lotes`, permitir preparar un Excel, identificar qué falta y
revisar el resultado con menos desplazamiento y sin confundirlo con otro lote.
Mantener las decisiones fiscales explícitas y el historial accesible como
contexto para prevenir duplicaciones. Usuarios administrativos y contables no
deben necesitar conocimientos de informática para interpretar la pantalla.

PF-17 es dueño de esta distribución, claridad y accesibilidad. Prioridad P2 de
usabilidad operativa, horizonte «Más adelante», sin cambiar el orden vigente.
La dirección está aceptada; medidas, disposición responsive y textos finales
se validarán con el usuario en una versión local de la aplicación antes de
subir la implementación al repositorio remoto. No se requiere Figma.

## Diagnóstico y relación con trabajo existente

La revisión de escritorio recorrió la pantalla con un archivo seleccionado,
configuración fiscal incompleta y un lote anterior completado. Observó:

- perfil y guía grandes incluso con la ayuda plegada; emisor repetido;
- checklist fuera de vista al bajar y una columna vacía junto al formulario;
- tarjetas de opciones y fechas estiradas hasta la altura del contenido vecino;
- pendiente genérico de fechas y textos sobre detalles internos de la interfaz;
- archivo nuevo y lote anterior presentados como una continuidad poco clara;
- totales pendientes en cero destacados en un lote ya completado;
- mantenimiento desplegado e historial largo que prolongan la página.

Es evidencia nueva para una evolución de UI, no un fallo fiscal demostrado.
Las capturas y datos reales permanecen privados y fuera del repositorio.
No se verificaron móvil ni accesibilidad completa durante ese recorrido.

| Fuente | Responsabilidad y coordinación |
|---|---|
| [Rediseño anterior](lotes-ux-redesign.md) | Sus cuatro cortes siguen cerrados. Este documento gobierna la evolución posterior; no repetir su implementación ni modificar su historia. |
| [Plantillas PF-13](pf-13-plantillas-contables-design.md) | Conserva interpretación del Excel, tipo/letra, precedencia de archivo/perfil/valores fijos y validaciones condicionales. Esta UI debe mostrar el origen efectivo sin crear otro constructor. |
| [Duplicados PF-13/PF-17](pf-13-duplicados-lotes-design.md) | Conserva comparación, advertencia, actores, retorno principal, checkbox, revalidación y coordinación de emisiones simultáneas. El historial compacto aporta contexto; no reemplaza el control. |
| [Actividad PF-17/PF-15](pf-17-actividad-lotes-design.md) | Conserva atribución de última emisión confirmada, límites históricos y apertura de actividad al seleccionar un lote. Ajustar la ubicación dentro de la nueva distribución, sin duplicar su contrato. |
| PF-10 y [QA manual](manual-qa.md) | Mantenimiento secundario conserva elegibilidad, consecuencias, resguardos y confirmaciones. Reubicarlo no cambia retención ni borra datos automáticamente. |

## Composición propuesta para revisar localmente

### Cabecera y preparación del archivo

- Mostrar el emisor de forma inequívoca y mantener ese contexto visible durante
  el trabajo mediante una cabecera compacta. Eliminar la tarjeta redundante a
  la derecha; conservar la selección explícita, permisos y comprobación del
  emisor. No extender este corte a un rediseño de toda la navegación global.
- Agrupar archivo seleccionado, formato del Excel y perfil en una zona breve.
  Después de elegir archivo, priorizar su nombre y una acción para cambiarlo;
  evitar conservar un área de carga grande sin utilidad en ese estado.
- Explicar el perfil como configuración habitual del emisor y la plantilla como
  formato del Excel. Evitar repetir título, etiqueta y nombre aplicado. Mantener
  visibles los valores efectivos y si fueron modificados respecto del perfil.
- Ofrecer administración de perfiles, descarga de plantilla y guía como acciones
  secundarias. La guía plegada no debe ocupar una tarjeta introductoria grande.
  La ayuda extensa queda disponible bajo demanda, sin onboarding obligatorio.
- Distinguir «Formato reconocido» de «Archivo validado». Una coincidencia de
  encabezados o un porcentaje de confianza no acredita la corrección fiscal de
  filas, importes, fechas ni receptores.

### Configuración fiscal y resumen que acompaña la carga

- En escritorio, dar la mayor parte del ancho al formulario y usar una columna
  lateral más estrecha para el resumen. Su contenido debe acompañar el scroll
  dentro de la preparación, sin una caja vacía estirada hasta el final.
- Mantener el estado de requisitos y «Validar lote» próximos y accesibles al
  completar campos. Su ubicación exacta y la conveniencia de conservar las dos
  posiciones actuales del botón se decidirán en la revisión local, siempre con
  el mismo handler y las mismas condiciones de habilitación.
- Priorizar pendientes concretos, con una acción que lleve al campo y gestione
  el foco. Ejemplo sintético: «Faltan período del servicio y vencimiento».
  No afirmar que falta elegir fecha de emisión si ya se eligió tomarla del
  archivo. Separar elección de origen de la validación posterior de sus valores.
- Conservar el resumen de valores efectivos: emisor, archivo/formato, punto,
  concepto, descripción y origen de fechas. Los completos pueden presentarse
  en filas breves; no ocultar decisiones fiscales detrás de la ayuda.
- Usar controles de altura natural. Evitar que opciones cortas y una fecha
  aislada hereden la altura de otra opción con varios campos.
- Presentar fecha de emisión en un grupo propio y, cuando correspondan, período
  desde/hasta y vencimiento del servicio en un grupo que aproveche el ancho.
  Mantener elecciones y fechas explícitas; nunca completar con el día actual.
- Usar superficies neutras para grupos normales. Reservar color de alerta e
  iconos para estados concretos, con texto que explique qué hacer. El título del
  checklist no debe conservar un triángulo de advertencia cuando todo esté
  completo. Un resumen completo significa «Configuración completa para validar»,
  no autorización fiscal ni permiso para omitir la revisión del lote.

### Archivo actual, resultado e historial

- Identificar sin ambigüedad «Archivo en preparación», resultado del lote
  validado y consulta de «Lotes anteriores». Un lote anterior no debe parecer
  el resultado del Excel recién seleccionado.
- Mantener acceso visible al historial y una selección claramente marcada.
  Al consultar otro lote, conservar archivo y opciones del borrador en el mismo
  emisor y permitir volver a su preparación. No agregar persistencia del Excel
  ni borradores cruzados entre emisores; preservar las reglas de cambio de
  contexto y revocación de permisos.
- Seleccionar una tarjeta abre el detalle y su actividad con ese mismo clic,
  según el contrato de actividad. No exige otra página ni un segundo clic.
  Carga automática y polling no abren la historia ni mueven el foco. Las
  respuestas atrasadas no pueden reemplazar el lote o emisor actualmente elegido.
- Adaptar la jerarquía al estado: preparado destaca alcance e importes por
  emitir; procesando destaca avance; completado destaca cantidad e importes
  efectivamente emitidos. Un parcial o incierto debe conservar su estado real
  y distinguir autorizado, pendiente y fallido; nunca aparentar finalización.
- En completados, «Totales listos para emitir: 0» no es el resumen principal.
  Usar resultados acreditados y etiquetas de alcance/moneda claras, conservando
  contratos de neto, IVA, total y tratamiento de notas. No confundir importe de
  comprobantes con ventas netas ni mezclar monedas sin un contrato existente.
  Un error o falta de datos históricos se informa como tal, no como cero.
- Verificar primero si la API conserva los agregados necesarios, incluidos
  lotes compactados. Si faltan, definir el contrato mínimo con PF-13/PF-14/PF-15
  antes de implementarlo; no sumar sólo la página visible, descargar todas las
  filas ni introducir un motor contable paralelo para completar la tarjeta.
- Dar protagonismo a la consulta del resultado de un lote completado. El estilo
  de acciones deshabilitadas no debe sugerir que se puede volver a emitir;
  conservar condiciones y garantías de las operaciones actuales.

### Acciones secundarias y lenguaje

- Ubicar limpieza/compactación dentro de «Otras acciones» o un bloque plegable
  equivalente. Mantener advertencias y confirmaciones al entrar en esa acción.
  No plegar por este motivo errores, incertidumbre o resolución necesaria.
- Mostrar inicialmente un historial breve con «Ver más», conservando acceso al
  resto y selección estable. Evitar cargas masivas o desplazamientos internos
  difíciles de operar. Validar el tamaño inicial en la aplicación local.
- Reemplazar «Métrica principal» por la cantidad con su significado. Conservar
  archivo, carga, estado y la línea «Última emisión por» del diseño de actividad;
  el resto del historial sigue apareciendo al consultar el lote.
- Retirar textos sobre cómo se implementó la pantalla, por ejemplo la explicación
  de que otro botón se agregó al final o «sin perder contexto técnico».
  Usar español completo, ARCA y fechas visibles `DD/MM/AAAA`.

## Límites e invariantes

Este alcance no crea un asistente de pasos obligatorios ni reduce controles.
Conservar confirmación irreversible con fecha y punto de venta, validación de
filas e importes, duplicados, aislamiento, idempotencia, reintentos seguros y
reconciliación. Compactar la UI no autoriza autoemitir ni aceptar excepciones.

Reducir contenedores, repeticiones y espacios vacíos; mantener legibilidad,
etiquetas y tamaños cómodos de interacción. El resumen persistente no debe
tapar controles, mensajes o foco. En pantallas bajas, estrechas o con zoom,
adaptarlo al flujo disponible; no forzar la columna de escritorio ni una barra
que cubra el formulario. La disposición móvil se revisará, no se presume
resuelta por esta auditoría.

## Implementación y revisión local con el usuario

1. Al iniciar el corte, revisar código vigente y contratos relacionados. Definir
   el alcance por componentes y la disponibilidad de totales acreditados. No
   mezclar una reorganización visual con cambios fiscales sin identificarlo.
2. Preparar la versión local real de FactuFlow siguiendo el
   [runbook local](local-launcher-runbook.md), con datos sintéticos y servicios
   fiscales simulados para la revisión. No conectar esa prueba a producción,
   reutilizar credenciales productivas ni solicitar CAE real.
3. Mostrar al usuario el recorrido funcionando: seleccionar archivo, revisar
   configuración, localizar pendientes, validar con datos de prueba y consultar
   estados/resultados e historial. Las capturas complementan esta revisión;
   no sustituyen el uso de la versión local.
4. **Antes del primer push de la implementación al repositorio remoto, obtener
   la conformidad explícita del usuario con el diseño probado localmente.**
   Aplicar los ajustes que solicite y volver a revisar lo afectado. La aceptación
   de este plan no equivale a aprobar de antemano el diseño implementado. No
   publicar una rama o PR de implementación para usarlo como primera revisión
   visual. Esta condición no impide preparar código y commits locales.
5. Completar las pruebas y documentación afectadas; luego seguir el flujo Git
   autorizado. La aprobación visual no autoriza por sí sola push, merge ni
   despliegue: respetar el alcance explícito del pedido vigente.

Registrar la conformidad y los ajustes en el cierre de la unidad, sin datos
privados. Este acuerdo añade una revisión de desarrollo, no otra confirmación
para quienes usan FactuFlow al emitir.

## Matriz de aceptación

| Escenario sintético | Resultado verificable |
|---|---|
| Sin archivo, con archivo y guía plegada/abierta | Ayuda y perfil compactos; archivo/formato identificables; origen de valores visible. |
| Scroll largo, ventana baja y zoom 200 % | Pendientes y validar accesibles sin volver al inicio; sin columna vacía estirada, foco tapado ni pérdida de controles. |
| Escritorio y móvil, nombres largos, teclado y lector de pantalla | Controles legibles, orden lógico, grupos/etiquetas identificables y contraste medido; acciones a pendientes llevan al campo correcto. |
| Fecha del archivo elegida, sin período ni vencimiento | Aviso identifica sólo las decisiones faltantes; ninguna fecha se completa automáticamente. |
| Todos los requisitos completos | Estado de preparación correcto, sin alarma fija ni afirmación de validación fiscal ya realizada. |
| Archivo nuevo junto a lote anterior completado | Contextos inequívocos; navegar por historial conserva el borrador del mismo emisor. |
| Validación con errores o advertencia de duplicación | Mensajes accionables, controles vigentes y retorno principal de duplicados conservados. |
| Preparado, procesando, completado, parcial e incierto | Resumen y acciones corresponden al estado; importes acreditados separados de pendientes, sin éxito anticipado. |
| Lote compactado, totales ausentes o error de consulta | Alcance y límite explícitos; nunca cero inventado ni suma de una página parcial. |
| Selección de lote, actividad, polling y respuestas atrasadas | Un clic abre la actividad correcta; consulta y refresco no pierden preparación ni cambian foco inesperadamente. |
| Cambio de emisor o revocación de acceso | Reglas vigentes de contexto y permisos; sin datos, borradores ni respuestas del otro emisor. |
| Historial largo y mantenimiento plegado | Ver más y acciones secundarias accesibles, sin cargar todo ni perder guardas de compactación. |
| Revisión local con el usuario | Diseño validado o ajustado antes de publicar la implementación en el remoto; conformidad registrada. |

Esta unidad documental es Nivel 0: diff, enlaces, idioma, privacidad y
`npm run docs:check`. Al implementar, aplicar
[puertas de calidad](change-quality-gates.md), [testing](testing.md) y
[QA manual](manual-qa.md). Completar previamente el
[checklist fiscal](fiscal-change-checklist.md) ante cambios que puedan alcanzar
emisión, fechas, importes, persistencia o aislamiento; una UI más compacta no
reduce el riesgo de esos caminos. Cubrir regresiones de los estados y acciones
afectados, además de lint, tipos, build y pruebas del área. Actualizar manual de
usuario, API si corresponde y changelog cuando exista conducta implementada.
