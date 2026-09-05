# PF-18/PF-17 — dashboard mensual y fechas de emisión

Fecha: 05/09/2026.

Estado: alcance solicitado para implementación futura. Este documento define
el contrato propuesto a partir del pedido; no describe una capacidad desplegada
ni autoriza modificar código o producción.

## Objetivo y encaje

Permitir que una persona contadora identifique rápidamente actividad para el
mes actual y anterior del emisor activo. Una emisión realizada ahora puede
tener fecha de comprobante del mes anterior: un cero en el mes actual no
demuestra que nadie haya facturado recientemente.

El roadmap ya contiene dashboard en PF-18. Este corte concreta esa línea con
PF-17 para claridad y accesibilidad; PF-04 aporta moneda e historia, y PF-15
la procedencia temporal. Complementa el
[control de duplicados PF-13](pf-13-duplicados-lotes-design.md), sin reemplazar
sus comparaciones, checkbox, revalidación ni coordinación entre empleados.
Permanece en «Más adelante», sin agregar pasos obligatorios. El resumen mensual
y la cronología son P2 de claridad operativa; el ajuste del ícono del certificado
es P3 de presentación. Separar ambos alcances permite corregir el ícono sin
esperar el contrato nuevo de agregados o alterar validaciones de certificados.

## Base comprobada en el código

Referencias de implementación para retomar; contrastarlas con el código vigente
al comenzar. La observación de la pantalla abierta sólo verificó su presentación;
no se consultó el VPS ni se obtuvo evidencia de emisiones nuevas.

| Fuente | Comportamiento observado y consecuencia |
|---|---|
| [DashboardView.vue](../../frontend/src/views/dashboard/DashboardView.vue) | Muestra cantidad del mes y número del último comprobante. Obtiene el rango con el reloj/zona del navegador, consulta el reporte completo y convierte un fallo del reporte en cero. No muestra el mes/año, importe, mes anterior ni fechas del último comprobante. |
| [ReportesService](../../backend/app/services/reportes_service.py) | Filtra por emisor, estado autorizado y `fecha_emision`. Cuenta comprobantes y calcula `total_neto = facturas + ND - NC` sobre `total`; este nombre no significa neto gravado sin IVA. Carga comprobantes e ítems y suma valores sin convertir monedas. |
| [Listado de comprobantes](../../backend/app/api/comprobantes.py) | Ordena por fecha fiscal descendente y número descendente. El dashboard pide el primer resultado; ese orden no identifica necesariamente la última emisión real, y la consulta no filtra por autorizado. |
| [Modelo](../../backend/app/models/comprobante.py) y [schemas](../../backend/app/schemas/comprobante.py) | Conservan fecha fiscal, total, moneda/cotización y timestamps de creación/actualización. El listado no expone la fecha/hora efectiva de emisión. `created_at` y `updated_at` no son por sí solos prueba de ella. |
| [Servicio fiscal](../../backend/app/services/facturacion_service.py) | Guarda el comprobante tras obtener autorización y también interviene en recuperación/reconciliación. Debe verificarse la procedencia del instante antes de reutilizar timestamps como emisión real. |

No añadir sólo tarjetas que reproduzcan esos límites. El resumen debe resolver
la semántica de fechas, errores, moneda y orden antes de presentarse como evidencia.

## Indicadores y períodos

Mostrar dos grupos equivalentes y cercanos, con cantidad e importe juntos:

| Grupo | Indicadores |
|---|---|
| **Mes actual · junio de 2026** | Comprobantes del mes; Total emitido del mes |
| **Mes anterior · mayo de 2026** | Comprobantes del mes anterior; Total emitido del mes anterior |

Los nombres de mes y año son dinámicos. Añadir los rangos explícitos, por
ejemplo `01/06/2026 al 30/06/2026` y `01/05/2026 al 31/05/2026`, y la aclaración
visible: **«Según la fecha del comprobante. Importes finales con impuestos:
facturas + notas de débito − notas de crédito»**. Mostrar la moneda: pesos
argentinos (ARS). Esta definición evita confundir período fiscal con actividad
realizada durante ese mes o con el período de prestación del servicio.

- El mes actual es el mes calendario en Argentina al consultar; el anterior
  es el inmediatamente precedente, incluido diciembre al consultar en enero.
  Ambos usan su rango calendario completo y los comprobantes ya autorizados
  conocidos al momento de la consulta. No significa últimos 30 días ni un
  período cerrado/completo; tampoco excluir una fecha futura autorizada que
  pertenezca a ese mes.
- El reloj sirve exclusivamente para elegir el período informativo, usando
  `America/Argentina/Buenos_Aires`. No completa fechas de una factura, modifica
  el Excel ni altera ventanas o confirmaciones de emisión.
- Usar `Comprobante.fecha_emision` como fecha del comprobante. Una factura
  fechada el 31/05 y emitida el 02/06 integra mayo; la fecha de carga del lote,
  la de emisión efectiva y el período del servicio no cambian esa asignación.
- Mostrar sólo datos conocidos en FactuFlow del emisor activo y ambiente
  aplicable, de todos sus usuarios y puntos de venta. No filtrar por quien
  consulta ni consolidar emisores. Aclaración breve: «Comprobantes autorizados
  registrados en FactuFlow». No prometer totalidad de la historia en ARCA.

### Cantidad e importe

**Cantidad:** número de comprobantes autorizados únicos, facturas, notas de
débito y notas de crédito incluidas. Una nota de crédito suma una unidad al
conteo; no resta una factura del historial. Excluir borradores, pendientes,
rechazados e intentos inciertos aún no resueltos; no usar cantidad de filas de
Excel, lotes ni intentos de emisión. Una autorización reconciliada cuenta una
sola vez; dos comprobantes distintos efectivamente autorizados cuentan ambos,
aunque su contenido coincida.

**Total emitido:** suma del importe final de facturas y notas de débito menos
el importe final de notas de crédito. Incluye los impuestos contenidos en el
total autorizado; no equivale a neto gravado, base imponible ni cobros.

- Aplicar el signo según el tipo de comprobante, incluyendo sus letras
  compatibles, sin depender de la descripción ni aplicar el signo dos veces.
- Cada nota se atribuye al mes de su propia fecha. Una NC de junio asociada a
  una factura de mayo resta en junio; no reescribir el resumen de mayo.
- Conservar cero y valores negativos legítimos. Dos comprobantes que se
  compensan pueden dar importe cero y cantidad dos; cero pesos no equivale a
  ausencia de emisión.
- Trabajar con precisión decimal y redondeo documentado; mostrar dos decimales
  y formato argentino. Reutilizar la clasificación fiscal compartida cuando
  corresponda, sin cambiar silenciosamente el contrato de otros reportes.
- Para documentos en otra moneda, obtener el equivalente en pesos con la
  cotización histórica del comprobante, sin consultar una cotización actual ni
  sumar monedas diferentes como si fueran pesos. Confirmar en PF-04 unidades,
  precisión y redondeo de esa conversión. Si falta evidencia válida, mostrar
  «Total en pesos no disponible» y la causa; mantener la cantidad comprobada.
  No mostrar un subtotal incompleto bajo la etiqueta de total.

## Último comprobante y sus dos fechas

Mantener una tarjeta visible con identificación completa: tipo/letra, punto
de venta y número. Su objetivo es mostrar la emisión exitosa más reciente,
aunque la fecha del comprobante sea anterior o el número sea menor que el de
otro punto de venta o tipo. Incluir:

- **Fecha del comprobante:** `DD/MM/AAAA`, la fecha fiscal del documento.
- **Emisión realizada:** `DD/MM/AAAA HH:mm`, cuando el instante efectivo esté
  acreditado, con hora argentina explícita.

Ejemplo sintético: `NC B 0002-00000004`, fecha del comprobante `31/05/2026`,
emisión realizada `02/06/2026 10:35 (hora argentina)`. El número no determina
la cronología entre tipos y puntos de venta.

El contrato temporal debe distinguir emisión efectiva, confirmación local de
la autorización y creación/importación del registro. Si sólo se dispone del
instante en que el sistema confirmó el resultado, etiquetarlo **«Autorización
confirmada en FactuFlow»**. Una reconciliación posterior o la importación de
historia no debe presentarse como una nueva emisión realizada en ese instante.

Para registros antiguos sin evidencia suficiente, mostrar **«Fecha de emisión
efectiva no registrada»**; si se ofrece una fecha de registro, identificarla
como tal. No sustituirla por `updated_at`, hora de carga del Excel, vencimiento
del CAE ni la fecha actual. No asignar zona a timestamps históricos sin probar
su convención. La fecha fiscal se muestra como fecha de calendario, sin
desplazarla un día al convertirla entre zonas.

Antes de codificar, definir fuente durable, precisión, desempate estable y
cobertura histórica del orden. Si faltan fechas para garantizar cuál fue el
último, usar una etiqueta limitada como «Último comprobante con emisión
acreditada» y explicar la cobertura; no esconder registros ni afirmar una
cronología que la evidencia no permite. El panel no llama a ARCA ni modifica
el flujo fiscal para reconstruirla durante la consulta.

## Presentación y actualización

- Mantener cantidades e importes de ambos meses juntos, con jerarquía y orden
  equivalentes. Los períodos y las dos fechas deben leerse sin abrir un tooltip.
  Conservar clientes, certificado y accesos rápidos; evitar que los indicadores
  nuevos se confundan con acciones de emisión.
- Adaptar la grilla al ancho disponible. El tipo/número, los importes y las
  fechas no deben truncarse ni depender del color; verificar móvil, zoom,
  contraste y lectura asistida. No requiere gráficos ni otra pantalla.
- Diferenciar carga, cero confirmado, sin comprobantes y error. Un fallo de
  consulta muestra «No se pudo obtener el resumen» con reintento; nunca cero,
  «Sin emisiones» ni datos de otro emisor. Un fallo en un grupo no borra datos
  válidos de otro, siempre que su período y vigencia sigan identificados.
- Obtener un resumen coherente para ambos meses y el último comprobante, con
  instante de consulta visible. Actualizar al entrar/volver al dashboard, tras
  una emisión o reconciliación conocida y al cambiar de emisor; resolver el
  cambio de mes si la pantalla sigue abierta. Al recuperar foco/conectividad,
  refrescar sin exigir al usuario recordar que debe hacerlo.
- Descartar respuestas atrasadas y evitar reutilizar datos anteriores al cambiar
  de contexto. No introducir sondeos frecuentes ni suscripciones costosas como
  requisito de este corte; el resumen es informativo y no prueba ausencia de
  cambios posteriores ni sustituye la revalidación previa a emitir.

### Estado del certificado: texto, ícono y color coherentes

La tarjeta actual fija `ExclamationTriangleIcon` y los colores de advertencia
en `DashboardView.vue`, incluso cuando el estado mostrado es «Válido». El usuario
solicitó corregir esta contradicción visual en el mismo dashboard.

| Estado | Presentación futura |
|---|---|
| Válido | Tilde dentro de un círculo (`CheckCircleIcon`) y color de éxito; sin triángulo ni color de advertencia. |
| Por vencer | Ícono de advertencia y color de atención. |
| Vencido | Ícono de error y color de error. |
| Sin certificado | Ícono de ausencia o información, sin tilde de éxito. |
| Cargando o estado no disponible | Indicador de carga o estado desconocido; no mostrar un tilde que sugiera validez confirmada. |

Elegir texto, ícono y color desde el mismo estado, preservando la etiqueta
visible para no depender sólo del color. Al cambiar de emisor, no conservar
la señal de éxito del anterior. Es un ajuste de presentación: no cambia la
validación del certificado ni las alertas y controles previos a emitir.

## Implementación futura y aceptación

Preferir un resumen agregado en servidor, acotado e indexado por emisor,
estado y fechas, que devuelva ambos períodos, cantidades, totales con su
moneda/cobertura, última emisión con procedencia y momento de consulta. No
descargar dos reportes completos con clientes e ítems para calcular tarjetas
en el navegador. Cerrar el contrato HTTP y la consistencia de lectura en
SQLite/PostgreSQL; evaluar todos los consumidores si se comparte cálculo.

| Caso de prueba sintético | Resultado requerido |
|---|---|
| Consulta en junio; cuatro comprobantes de mayo emitidos en junio | Mayo muestra cuatro; junio cero. Último comprobante informa fecha de mayo y emisión de junio. |
| Mayo: dos facturas de $1.000, una ND de $300 y una NC de $100 | Cuatro comprobantes; total $2.200,00 con impuestos. |
| Factura y NC de igual total; mes sólo con NC | Cantidad positiva con importe cero; importe negativo permitido en el segundo caso. |
| NC fechada en junio asociada a factura de mayo | La NC resta en junio; mayo conserva la factura. |
| Cambios de mes/año, febrero bisiesto y navegador en otra zona | Meses/rangos argentinos correctos, sin modificar fechas fiscales. |
| Emisión real posterior con fecha fiscal anterior; distintos tipos/PV | La tarjeta selecciona la emisión más reciente acreditada, no el mayor número ni fecha fiscal. |
| Emisión individual, lote, autorización parcial y reconciliación | Mismo universo autorizado; cada comprobante único cuenta una vez. La reconciliación no inventa otra emisión. |
| Dos autorizaciones distintas con contenido duplicado | Ambas siguen visibles en cantidad e importe; el resumen no depura fiscalmente el historial. |
| Borradores/rechazos, otro emisor/usuario/ambiente | Sólo autorizados del contexto; incluye emisiones de todos sus usuarios, aunque su asignación haya cambiado, sin filtrar por operador actual. |
| Monedas distintas y cotización histórica ausente | Conversión válida y reproducible o total no disponible; nunca suma de monedas sin conversión. |
| Timestamp antiguo, registro importado y ausencia de emisiones | Etiquetas honestas, cronología limitada cuando corresponda; no fabricar fecha/hora. |
| Fallo parcial, respuesta vieja, cambio rápido de emisor y recuperación de red | Sin ceros falsos ni mezcla de contexto; datos vigentes y reintento claro. |
| Lote en curso por otro empleado mientras se consulta | Mostrar sólo lo confirmado al corte de consulta; no prometer datos en tiempo real ni un período completo. |
| Volumen alto, pantalla estrecha, zoom y teclado | Consulta acotada y tarjetas legibles, sin descargar todos los comprobantes ni sumar pasos obligatorios. |
| Certificado válido, por vencer, vencido, ausente y estado no disponible | Texto, ícono y color corresponden a la tabla; «Válido» tiene tilde de éxito. La carga y el cambio de emisor no muestran una validez anterior como vigente. |

Antes de implementar, cerrar procedencia temporal, conversión, contrato del
resumen y detalle visual. Actualizar manual/API/QA cuando cambie la conducta
efectiva. Aplicar [puertas de calidad](change-quality-gates.md): esta unidad
es documental (Nivel 0); una implementación que toque persistencia fiscal,
importes, aislamiento o el servicio de emisión requiere el
[checklist fiscal](fiscal-change-checklist.md) y evaluación de Nivel 2.
Conservar confirmaciones, idempotencia, numeración y reconciliación. Validar
con datos sintéticos, sin emisiones reales.
