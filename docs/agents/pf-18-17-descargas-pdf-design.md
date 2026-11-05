# PF-18/PF-17 — descarga directa y ZIP de comprobantes

Fecha: 04/11/2026.

Estado: contrato del corte implementado; publicación y despliegue separados.
Prioridad P3 administrativa, Ahora 1 por decisión explícita de Santi:
implementar este corte pequeño y preparar su salida a producción antes de
continuar PF-04/PF-02. Las operaciones de Git, publicación y despliegue conservan
sus autorizaciones propias. La implementación es nivel 2 por
selección masiva de documentos fiscales, aislamiento y generación de archivos.

## Objetivo y decisiones aceptadas

Obtener uno o varios PDF desde el listado de Comprobantes, sin abrir cada
detalle. Para pocos, descargar desde cada fila; para un conjunto, elegir
individualmente o seleccionar todos los resultados filtrados y descargar un ZIP.
El ZIP contiene un PDF independiente por comprobante, no un PDF combinado.

Decisiones de Santi del 04/11/2026:

- Conservar el ojo y agregar a su lado la descarga directa del PDF de esa fila.
- Ofrecer casillas individuales y selección de todos los resultados filtrados,
  incluidas las páginas que no están visibles, con cantidad explícita.
- Entregar el ZIP **sólo si se generaron todos los PDF seleccionados**. Si falta
  uno, no entregar ZIP, ni vacío ni parcial; identificar el problema sin omitir
  documentos silenciosamente. Los demás PDF siguen disponibles individualmente.
- Priorizar este corte para una próxima release pequeña, sin agregar otras
  capacidades del roadmap ni fijar todavía versión o fecha de despliegue.

## Base comprobada y límites

La base de partida ofrecía sólo `Ver detalle`, filtros y páginas de 20 resultados
en el listado, y `Ver PDF`/`Descargar PDF` en el detalle. Al volver se perdían los
filtros. Este corte extiende ese recorrido; el uso vigente se consulta en el
[manual](../user-guide/README.md#descargas-desde-el-listado).

| Consumidor | Responsabilidad del corte |
|---|---|
| [Listado](../../frontend/src/views/comprobantes/ComprobantesListView.vue) | Acciones por fila, selección, contador y ZIP; conservar estructura y estilos existentes |
| [Store](../../frontend/src/stores/comprobantes.ts) y [servicio de comprobantes](../../frontend/src/services/comprobantes.service.ts) | Contexto de filtros aplicados y página, selección entre páginas y descarte de respuestas atrasadas |
| [Detalle](../../frontend/src/views/comprobantes/ComprobanteDetalleView.vue) y [servicio PDF](../../frontend/src/services/pdf.service.ts) | Reutilizar descarga, mensajes sanitizados y liberación de blobs; conservar preview y retorno al listado |
| [API de comprobantes](../../backend/app/api/comprobantes.py) | Una sola semántica de filtros para listado y resolución de la selección; sin copiar predicados divergentes |
| [API PDF](../../backend/app/api/pdf.py) y [generador](../../backend/app/services/pdf_service.py) | Reutilizar autorización, guardas, lectura histórica, representación, QR y nombres; agregar composición ZIP sin otra plantilla fiscal |
| Almacenamiento PF-10 | Sólo temporales propios de esta petición; no activar resguardo ni limpieza administrativa |

Incluye comprobantes individuales y provenientes de lotes que ya estén en el
listado, y los tipos actualmente soportados por el PDF. No incorpora nuevos
tipos ni exige que un lote completo haya terminado para descargar un comprobante
ya autorizado. No cambia el contenido fiscal ni el diseño del PDF.

## Recorrido y selección

1. Trabajar con un emisor activo explícito y los filtros actuales de Comprobantes.
   La fecha del filtro es la fecha de emisión guardada, con extremos inclusivos;
   no el mes de servicio, creación técnica, descarga o autorización.
2. Junto al ojo, ofrecer `Descargar PDF`, con nombre accesible, ayuda y estado de
   trabajo por fila. La descarga no navega ni abre una ventana de preview.
   Evitar solicitudes repetidas de la misma fila mientras está trabajando.
3. Agregar casillas por fila. La cabecera selecciona o deselecciona **esta
   página** y representa selección parcial. Ofrecer por separado
   `Seleccionar los N resultados filtrados` y `Quitar selección`.
4. Mostrar siempre la cantidad seleccionada; el botón dice
   `Descargar N PDF en ZIP`. Sin selección no solicita archivos. Seleccionar uno
   por casilla conserva ZIP; el botón de la fila siempre descarga PDF.
   Mientras se genera, mostrar `Preparando ZIP…` y evitar repetir esa petición;
   no bloquear la navegación ni presentar una descarga fallida como exitosa.
5. Cambiar de página conserva la selección. En modo de todos los resultados,
   desmarcar una fila la excluye también del conjunto completo; volver a
   marcarla la reincorpora sin duplicados.
6. Aplicar o limpiar filtros invalida la selección anterior. Distinguir filtros
   escritos de filtros efectivamente aplicados: exportar corresponde al conjunto
   mostrado, nunca a una mezcla. Durante una carga no resuelta no ampliar una
   selección con filas de otra respuesta.
7. Al volver del detalle dentro del mismo emisor, conservar filtros aplicados,
   página y selección. Revalidar las filas al descargar. Una recarga completa
   puede limpiar la selección; no crear persistencia de datos fiscales en el
   navegador sólo para recuperarla.
8. Cambiar de emisor, cerrar sesión o perder el acceso limpia selección y
   contexto del listado. Una respuesta de una operación anterior no descarga
   archivos ni muestra avisos del emisor anterior, incluso tras cambiar A→B→A.

No agregar confirmación para una descarga de lectura ni forzar la carpeta de
destino o el diálogo de guardado del sistema operativo. Conservar navegación,
teclado, foco visible y nombres accesibles; el contador y los errores deben ser
comprensibles sin depender del color o del icono.

## Pertenencia exacta y contrato de aplicación

- Resolver todos los resultados en el backend con los mismos predicados del
  listado: emisor, desde/hasta, tipo, cliente y búsqueda cuando se reciban.
  No cambiar qué significa una búsqueda, agregar atajos de períodos ni trasladar
  al navegador todas las páginas con clientes, ítems o evidencia.
- Al seleccionar todos, obtener las identidades mínimas y el total efectivo en
  una lectura consistente; fijar ese conjunto para la selección. Nuevos
  comprobantes posteriores no se agregan solos. El total de selección proviene
  de esa resolución, no de multiplicar páginas ni de un contador anterior.
- La descarga recibe un conjunto concreto, único y sin IDs duplicados. No
  volver a ejecutar filtros abiertos al entregar el ZIP: eso incorporaría
  comprobantes no seleccionados. No usar números fiscales como identidad única.
- La selección es estado de interacción, no un permiso. Revalidar sesión,
  autorización por emisor, pertenencia y disponibilidad al descargar. Un ID
  ajeno o acceso revocado rechaza la petición completa, sin revelar nombres,
  números o existencia de documentos ajenos.
- La resolución y el ZIP serán contratos aditivos del dominio de lectura/PDF.
  Pueden usar POST para transportar selecciones, sin escritura fiscal. Conservar
  los endpoints individuales y su compatibilidad. No llamar a la propia API
  por HTTP desde el generador ni recorrer una URL arbitraria suministrada.
- El lote de PDF usa la misma proyección histórica y las mismas guardas que la
  descarga individual y el preview. Si se extraen helpers compartidos, mover
  juntos autorización, validación y tratamiento de errores; no llamar al
  renderizador saltándose las guardas de la API.

Los contratos aditivos son `GET /api/pdf/seleccion` y `POST /api/pdf/zip`;
su esquema y errores se consultan en la [guía API](../api/README.md#selección-completa-y-zip-pf-18pf-17).
La resolución mínima de identidades no crea una tabla, otra cola ni un job fiscal.
La selección y el estado de descarga viven en memoria del store: navegar al
detalle no cancela una descarga válida ni permite duplicarla al volver.
Cambiar sesión/emisor cancela las peticiones; invalidar selección cancela su
ZIP. Las respuestas tardías conservan además su comprobación de contexto.

## Invariantes fiscales, de aislamiento y privacidad

1. **Sólo lectura:** cero solicitudes CAE, WSAA, WSFE, padrón o consultas de QR;
   cero transiciones de comprobantes, intentos, grupos, lotes o reservas. No
   cambiar fechas, numeración, importes, redondeos, moneda, cotización, CAE,
   vínculos, hashes, idempotencia ni incertidumbre. Sin migraciones ni backfill.
2. **Misma elegibilidad:** conservar autorizado, CAE y vencimiento de CAE
   persistidos, y bloqueo por evidencia histórica presente no verificable.
   No exigir que el vencimiento de CAE siga siendo futuro ni que el certificado
   actual esté vigente para representar una autorización ya guardada.
3. **Historia conservada:** ausencia de snapshot conserva la disponibilidad
   vigente. La evidencia inválida no se trata como ausente. No completar
   originales desde fichas actuales ni quitar una guarda para terminar el ZIP.
   Fuente dueña: [lecturas históricas](pf-04-lecturas-historicas-design.md).
4. **Representación común:** encabezado, punto, número, QR y nombre pertenecen al
   mismo comprobante y emisor históricos. PDF en pesos sin bloque visible de
   moneda/cotización; datos y QR intactos. Conservar reglas vigentes para otras
   monedas y omisión de leyendas internas. Sin recálculo ni nueva plantilla.
5. **Aislamiento servidor:** no confiar en IDs, filtros, conteos, Pinia o
   selección web como autorización. Administradores y operadores conservan los
   permisos actuales, sin nueva capacidad global para exportar.
6. **Aislamiento cliente:** vincular cada operación al contexto de sesión,
   emisor y generación de selección que la inició. Descartar errores y
   resultados atrasados al invalidarlo; cancelar trabajo cuando sea posible.
7. **ZIP completo o ninguno:** antes de iniciar su respuesta descargable,
   verificar que cada seleccionado produjo exactamente un PDF. No empezar a
   transmitir un ZIP que después pueda resultar parcial, ni sustituir un PDF
   fallido por una página de error. Reintentar una descarga nunca emite.
8. **Nombres seguros:** reutilizar la identidad fiscal legible y ceros
   significativos; sanear nombres de archivo y cabeceras. Evitar rutas,
   entradas duplicadas o sobrescrituras dentro del ZIP, incluso con números
   visibles coincidentes. Resolver colisiones sin renumerar el comprobante.
9. **Datos privados:** respuestas no cacheables públicamente; sin enlaces de
   descarga públicos, certificados, claves, JSON de evidencia, logs ni originales
   Excel en el ZIP. La evidencia de QA usa datos sintéticos y rutas ignoradas.

## Errores y recursos

Si falla un documento, indicar en la pantalla los seleccionados afectados por
tipo y número, con motivo breve y acción posible. Ejemplos: PDF no disponible y
consulta al responsable; error de generación e intento posterior. Mantener
filtros y selección para corregirla, sin desmarcar fallidos automáticamente.
El usuario puede excluirlos explícitamente o descargar otros individualmente.
No atribuir una falla técnica a datos históricos dañados sin haberlo verificado.

Sin resultados o sin selección, no crear ZIP. Si ninguno puede generarse,
informar error y no entregar un archivo vacío. Sesión, autorización, pertenencia
o falla general de recursos rechazan toda la petición con un mensaje sanitizado;
no revelar documentos ajenos ni devolver trazas técnicas. No afirmar que un
archivo quedó guardado en la PC: sólo se conoce la entrega al navegador.

El [modelo de recursos de la visión](../../VISION.md#modelo-de-instalación-y-recursos)
exige generación bajo demanda y ausencia de archivo permanente en el VPS:

- Generar de forma secuencial o con concurrencia pequeña y acotada, sin una
  solicitud HTTP por PDF desde el navegador para construir el ZIP ni renders
  paralelos ilimitados. No usar el worker fiscal, otra infraestructura o caché
  permanente de documentos.
- Componer y validar el ZIP en un temporal privado por petición, o en un
  mecanismo equivalente de memoria acotada. No acumular todos los PDF y el ZIP
  simultáneamente en RAM; no mantener una transacción ni una conexión de base
  ocupada durante todo el render o la transferencia de red.
- La implementación serializa la preparación de ZIP por proceso y limita el
  renderizador nativo común a un cupo, fuera del bucle de la API. El temporal
  sin nombre persistente se elimina al cerrar su descriptor, también tras una
  caída del proceso; su respuesta lo cierra incluso si falla la transferencia.
- La generación nativa no debe bloquear salud/API ni desplazar al worker de
  emisión. Reutilizar las capacidades del monolito y presupuestar también
  solicitudes simultáneas, trabajo en espera, tiempo y espacio temporal.
- Liberar PDF intermedios, ZIP, descriptores y blobs al completar, fallar,
  cancelar o desconectarse. Limpiar sólo artefactos propios; delimitar la
  recuperación de temporales propios tras una caída sin borrar archivos ajenos.
- Antes de aceptar la implementación, medir tamaño, tiempo, RAM, temporales,
  concurrencia y límites efectivos HTTP/proxy en un ensayo local representativo.
  No prometer volumen ilimitado, truncar a la primera página ni imponer un tope
  numérico arbitrario. Si los resultados exigen partir descargas o agregar una
  espera/limitación visible, presentar el intercambio a Santi antes de fijarlo;
  no sustituir este corte por una plataforma de jobs de larga duración.

## Solapamientos y dependencias

| Línea relacionada | Tratamiento de este corte |
|---|---|
| PF-18, ZIP de PDF y selección múltiple P3 | Es el pendiente existente, ahora delimitado y adelantado. No crear otro pendiente equivalente. Incluye en el listado los comprobantes provenientes de lotes; un botón específico dentro de Lotes queda fuera de este corte |
| PF-17, UX y listas filtradas | Selección, estados y retorno al listado son parte del recorrido. No incorporar el rediseño completo de listas, Clientes, períodos rápidos o formato argentino general pendiente |
| PF-04/PF-02 | Reutiliza los dos cortes de evidencia/lectura ya implementados. No depende de implementar recuperación moderna ni la adelanta; conserva su preparación para continuar después |
| PF-10, ZIP de resguardo y limpieza | El ZIP de PDF no es un backup, no confirma resguardo ni habilita borrados/compactación. No usar su token o confirmación administrativa como requisito de esta descarga |
| PF-13, procesos largos | Comparte el principio de recursos acotados, no su cola fiscal, retries ni reconstrucción del lote. Una falla de descarga no toca grupos emitidos |
| PF-16/PF-17, preview bloqueado por navegador | Reutilizar descarga y tratamiento de errores; no corregir apertura de ventanas ni integrar ese pendiente P3 sin decisión separada |
| PF-18, correo, integraciones y MCP | Un futuro consumidor reutilizará el caso de uso autorizado. No enviar archivos a terceros, crear enlaces compartidos ni implementar estos canales ahora |

No contradice `VISION.md`: es operación de comprobantes, un emisor por vez y
artefactos bajo demanda. Conserva el orden relativo de las demás líneas y sus
prioridades. La prioridad P3 mide conveniencia; Ahora 1 fija la ejecución
adelantada solicitada por el usuario, sin declararlo incidente fiscal P0/P1.

## Matriz de aceptación y verificación

| Caso | Resultado exigido |
|---|---|
| Descarga de una fila autorizada | Un PDF de esa fila, misma representación que el detalle; filtros/página intactos, ojo conservado, sin preview ni envío fiscal |
| Doble clic, error y respuesta tardía de fila | Una operación por fila en curso, aviso sanitizado, estado liberado; otra fila no recibe su archivo o error |
| Selección individual en varias páginas | Cantidad exacta, sin duplicados; desmarcar y volver entre páginas conserva la pertenencia |
| Seleccionar todos con más de 20 resultados | Conjunto completo de IDs filtrados, no sólo página visible; exclusiones, cero resultados y selección vacía correctos |
| Filtros combinados y extremos del mes | Mismos resultados en listado/selección: tipo, búsqueda, cliente y fecha de emisión inclusiva; no confundir servicio/fecha técnica |
| Nuevo comprobante durante selección/exportación | No se incorpora a un conjunto ya fijado; orden estable y una entrada por seleccionado |
| Filtros nuevos, retorno del detalle, recarga | Aplicar/limpiar invalida selección; retorno conserva contexto del mismo emisor; recarga no restaura permisos desde almacenamiento web |
| Cambio A→B→A, logout, acceso revocado, IDs ajenos | Sin mezcla, descarga tardía, aviso ajeno ni existencia revelada; rechazo completo cuando corresponde |
| PDF con historia completa/incompleta/ausente/inválida | Misma disponibilidad, identidad histórica y guardas de individual/preview/ZIP; sin leyendas técnicas y sin cambio de evidencia |
| Selección de 19, falla del PDF 1, 10 o 19 | Ningún ZIP entregado; fallidos identificados de forma segura, selección intacta, PDF individuales válidos disponibles; temporales liberados |
| ZIP correcto, tipos y números coincidentes | Archivo íntegro, cada seleccionado una vez, nombres seguros y únicos; sin datos adicionales ni entradas de error |
| Fallo de render, disco, transferencia o desconexión | No ZIP parcial presentado como completo, sin residuos permanentes ni escrituras fiscales; liberación de recursos aun si termina después una tarea nativa |
| SQLite y PostgreSQL, concurrencia y volumen | Mismo conjunto/guardas; consultas acotadas, sin retener conexión durante render, salud y worker disponibles; presupuesto medido |
| Teclado, lector de pantalla y pantalla estrecha | Casillas, selección parcial, iconos, contador, foco y mensajes utilizables; controles sin depender del color |

Completar el [checklist fiscal](fiscal-change-checklist.md) con esta frontera:
estados de interacción y temporales únicamente; no hay transición fiscal,
reserva, llamada ARCA, replay de CAE ni migración. Probar que los adaptadores
fiscales no se invocan y que el estado persistido queda igual antes/después,
también en fallos y concurrencia. No crear nuevas claves idempotentes fiscales
para descargar. Un retry sólo repite lectura y generación de archivos.

Pruebas esperadas: backend de selección, filtros, API PDF/ZIP, aislamiento e
historia; frontend de listado, store, servicio PDF y regresión del detalle;
E2E con API simulada; comparación y apertura local de PDF/ZIP sintéticos; ensayo
de recursos y limpieza. Incluir los consumidores reales de cualquier helper
extraído, sin ampliar la lógica fiscal de worker/lotes/reconciliación.

## Cierre y salida a producción

Completar pruebas, controles del área, CI y QA local del recorrido antes de
integrar. Manual, API y changelog describen el contrato; no acreditan una
instalación productiva ni sustituyen la evidencia de cada ejecución.
Aplicar la [puerta nivel 2 y de release](change-quality-gates.md), con revisión
sensible proporcional y cualquier autorización de envío de contexto requerida.

Preparar una release pequeña con dossier y rollback por SHA exacto, sin acumular
otros pendientes. No fija número de versión ni autoriza commit, push, merge,
publicación o despliegue. Cada etapa conserva su autorización. Producción sigue
el [procedimiento vigente](production-workflow.md) y su plano de control, con
respaldo fresco, copia externa cifrada y verificaciones sin emisiones reales.
Sin migraciones previstas, el rollback de aplicación preserva datos posteriores;
un fallo de descarga no justifica restaurar una base ni reemitir comprobantes.
