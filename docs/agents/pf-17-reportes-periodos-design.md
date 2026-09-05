# PF-17 — períodos rápidos en Reporte de ventas

Fecha: 05/09/2026.

Estado: mejora solicitada para implementación futura. Esta actualización es
documental; no implementa el selector ni modifica la aplicación desplegada.

## Objetivo y alcance

Consultar períodos habituales sin tener que elegir manualmente sus dos fechas.
El usuario pidió expresamente «Mes anterior», desde el primer día hasta el
último de ese mes. La primera versión contempla los dos meses más próximos y
mantiene la selección personalizada, sin agregar configuración ni confirmaciones.

La mejora pertenece a PF-17 y conserva su horizonte en el roadmap. Comparte
la definición de mes calendario del
[dashboard mensual](pf-18-dashboard-mensual-design.md), pero no requiere ampliar
el resumen del dashboard ni modificar los cálculos de ventas. Este corte se
limita a Reporte de ventas; no extiende automáticamente controles a IVA Ventas,
ranking de clientes o formularios de emisión.

## Base actual

La pantalla abierta y
[ReporteVentasView.vue](../../frontend/src/views/reportes/ReporteVentasView.vue)
muestran «Desde», «Hasta» y «Generar Reporte». La vista inicia con el mes actual
calculado con el reloj/zona del navegador y no ofrece atajos de período.
El [servicio de reportes](../../frontend/src/services/reportes.service.ts)
envía `desde` y `hasta` al endpoint de ventas. El resultado incluye el período
efectivamente consultado y se presenta sólo para el emisor activo.

## Selector y reglas de calendario

Añadir un selector compacto «Período» junto a las fechas, con estas opciones:

| Opción | Desde | Hasta |
|---|---|---|
| Mes actual | Primer día del mes actual | Último día del mes actual |
| Mes anterior | Primer día del mes calendario inmediatamente anterior | Último día de ese mes |
| Personalizado | Fecha elegida por el usuario | Fecha elegida por el usuario |

- Ambos extremos son inclusivos. «Mes anterior» no significa últimos 30 días.
  Ejemplo sintético: al consultar en junio de 2026 completa `01/05/2026` y
  `31/05/2026`. En enero apunta a diciembre del año anterior; contemplar febrero
  de 28 o 29 días y meses de 30 o 31 días.
- Resolver el mes en `America/Argentina/Buenos_Aires` al entrar o elegir el
  atajo. Mantener «Mes actual» como selección inicial. El reloj sólo define
  filtros de consulta: no asigna fechas fiscales a nuevos comprobantes.
- Una vez elegido el período, conservar las fechas visibles hasta una nueva
  elección o edición; no desplazarlas silenciosamente si cambia el mes con
  la página abierta. Si la etiqueta relativa deja de corresponder al rango,
  mostrar «Personalizado» sin cambiar sus fechas. Volver a elegir el atajo
  recalcula sus límites.
- Mostrar Desde/Hasta en `DD/MM/AAAA` y enviar fechas de calendario ISO a la API.
  Validar fechas reales sin conversiones que desplacen un día por zona horaria
  ni parsing ambiguo. Los meses completos son coherentes con el dashboard.

## Interacción y coherencia del resultado

- Elegir un atajo completa ambos campos a la vez. No genera el reporte ni
  cambia el emisor; se conserva la acción existente «Generar reporte».
- Desde/Hasta permanecen visibles y editables. Editar cualquiera activa
  «Personalizado». Elegir «Personalizado» conserva los valores para ajustarlos,
  sin borrar fechas ni imponer un paso adicional para la edición manual.
- Distinguir las fechas preparadas del período ya consultado. Si cambian los
  filtros y sigue visible el resultado anterior, conservar su rango real y
  señalar «Fechas modificadas. Generá el reporte para actualizar los resultados».
  No presentar resultados anteriores bajo el nombre del nuevo período.
- Capturar emisor y fechas al generar. Una respuesta atrasada no debe atribuirse
  a filtros posteriores ni a otro emisor. Preservar validaciones de rango,
  estados de carga/error y consulta autorizada; un fallo no significa cero ventas.
- Permitir uso con teclado y lector de pantalla; el período seleccionado y el
  rango no dependen sólo del color. En móvil el selector y los dos campos siguen
  legibles. Los atajos no agregan consultas ni descargas por cada selección.

## Aceptación e implementación futura

| Prueba sintética | Resultado esperado |
|---|---|
| Elegir Mes anterior desde cualquier fecha de junio | Desde 01/05 y Hasta 31/05 del mismo año, sin consulta automática. |
| Elegir Mes anterior en enero o marzo | Diciembre del año anterior, o febrero con su último día correcto, incluido año bisiesto. |
| Elegir Mes actual | Mes calendario completo, con el mismo criterio que el dashboard. |
| Navegador en otra zona; página abierta durante un cambio de mes | Límites argentinos al elegir; fechas ya preparadas estables hasta nueva elección. |
| Editar Desde/Hasta; elegir Personalizado | Conserva valores y permite cualquier rango válido; no queda un atajo marcado que contradiga la edición. |
| Cambiar atajo con un reporte visible o una consulta en curso | Período del resultado inequívoco; respuesta anterior no se atribuye al nuevo rango. |
| Rango incompleto/invertido, fallo de consulta o cambio de emisor | Validación y estados claros; no mezclar datos ni generar ceros falsos. |
| Teclado, lector de pantalla y ancho móvil | Opción y fechas accesibles, sin pasos obligatorios nuevos. |

Reutilizar un cálculo de rangos de calendario cuando sea compatible con el
dashboard; revisar consumidores si se extrae un helper compartido. El endpoint
puede seguir recibiendo `desde`/`hasta`: no necesita interpretar etiquetas como
«Mes anterior». No cambiar selección fiscal de comprobantes, fórmulas, moneda,
permisos ni generación de CAE por este ajuste.

Al implementar, cubrir cálculo de fechas e interacción con pruebas enfocadas y
QA visible, y actualizar el manual del reporte. Aplicar las
[puertas de calidad](change-quality-gates.md): esta unidad es Nivel 0 documental;
el selector aislado es funcional no crítico, sujeto a reevaluación si cambia
el alcance. No se requieren suites fiscales ni emisiones reales para documentarlo.
