# PF-17/PF-13 — formato argentino y precio unitario legible

Última revisión: 19/11/2026.

Estado: diseño del corte previsto en el [roadmap](../../ROADMAP.md#2-pf-17pf-13--formato-argentino-y-claridad-visible).

## Alcance

El corte reúne la corrección de fechas y números visibles y la legibilidad del
precio unitario. Aplica la [regla transversal de formato argentino](../../AGENTS.md#formato-argentino-en-contenido-visible)
en interfaz, PDF, reportes y documentos de uso administrativo. Incluye las
ayudas, los ejemplos iniciales y los de plantillas existentes o clonadas en el
constructor de emisión masiva, así como su hoja de instrucciones. Las
etiquetas de IVA y almacenamiento usan las tildes y separadores que
correspondan al dato, como «IVA 10,5 %».

Fechas de calendario en `DD/MM/AAAA`, coma decimal y punto de miles en
cantidades e importes cuando corresponda, con independencia de la región del
navegador. Los instantes conservan la
[hora argentina establecida](pf-12-15-17-tiempo-operativo.md). CUIT, CAE,
códigos, documentos y números de comprobante conservan sus ceros y su formato
de identificador. La atribución de receptores sin documento se rige por su
pendiente específico, registrado por separado en el
[portafolio](development-portfolio.md#trabajo-agrupado-por-línea).

El corte actúa en la presentación. Las entradas, API, base, ARCA y archivos de
intercambio conservan su contrato técnico. En Excel, dar formato a la
presentación sin cambiar el tipo, valor o interpretación de las celdas que
consume la importación. La mejora usa el constructor existente y es
independiente del rediseño y la ampliación de plantillas contables.

## Precio unitario en comprobantes

La plantilla común de facturas, notas de crédito y notas de débito A/B/C muestra
hoy la precisión completa del precio unitario, lo que puede partir un importe
en varias líneas aun cuando dos decimales bastan para leerlo. El subtotal se
presenta con dos decimales a partir del valor guardado.

- Mostrar el precio con dos decimales si, con la cantidad y la bonificación
  del renglón, explica el subtotal visible y conserva el importe de bonificación
  visible cuando corresponda. Comparar con los importes guardados, bajo el
  redondeo vigente de presentación y con aritmética decimal.
- Si dos decimales no alcanzan, usar la menor cantidad de decimales adicionales
  que conserve esa correspondencia. Si el detalle histórico difiere aun con
  la precisión completa, mostrar el precio guardado completo y conservar la
  discrepancia histórica. El ancho de la celda se resuelve sin cortar dígitos
  ni superponer columnas.
- Aplicar la regla al generar el PDF de cualquier comprobante, incluso
  histórico, en vista previa y en descarga individual o ZIP. En
  las vistas de lectura y revisión que muestran el precio junto con los
  importes del renglón, usar el mismo criterio con los importes de referencia
  de esa vista. En los campos de edición se conserva el valor editable.

Ejemplos sintéticos: con cantidad 1 y sin bonificación, el precio
`27.272,727272727272` puede mostrarse como `27.272,73` si el subtotal visible es
`27.272,73`. Con cantidad `1.000`, precio `0,123456` y subtotal `123,46`,
`0,12` sugeriría un subtotal distinto. En ese caso deben aparecer los
decimales adicionales necesarios.

La regla sustituye únicamente la exigencia de mostrar siempre el precio
unitario completo del [corte original de PDF](pf-04-pdf-representacion-fiscal-design.md),
a partir de la implementación de este diseño. La cantidad, las alícuotas, los
porcentajes de bonificación y la cotización conservan su precisión. El PDF
en pesos sigue omitiendo el bloque visible de moneda y cotización.

## Invariantes y aceptación

La comparación del renglón sirve sólo para elegir cómo mostrar el precio.
Los valores guardados, las bases, el IVA, los subtotales, el total, los signos,
la moneda, la cotización, el QR, el CAE y las fechas fiscales conservan sus
fuentes vigentes, incluida la [precisión fiscal A-01](pf-03-04-14-persistencia-fiel-design.md).
El valor mostrado se usa exclusivamente para lectura. Se conservan
importación, exportación técnica, confirmación, idempotencia, reconciliación y
permisos por emisor.

| Verificación | Resultado esperado |
|---|---|
| Factura, NC y ND, incluida una nota de origen externo | Precio claro y consistente en revisión, detalle y PDF. El PDF conserva IVA, QR, fechas y valores históricos. |
| Cantidad grande o fraccionaria, importes pequeños y bonificación | Se conservan los decimales necesarios para explicar los importes visibles. Una diferencia histórica mantiene el valor original completo. |
| PDF en A4, vista previa, descarga individual y ZIP | Misma presentación por comprobante, sin pérdida de dígitos ni superposición. Se conservan permisos, errores y entrega completa del ZIP. |
| Interfaz, reportes, ejemplos de plantillas y hoja de instrucciones | Formato argentino en distintas regiones del navegador. Identificadores conservados. Las planillas siguen interpretándose igual. |

La implementación toca la representación de comprobantes fiscales e incluye
el [checklist fiscal](fiscal-change-checklist.md), pruebas con datos sintéticos
y revisión independiente según la [política vigente](change-quality-gates.md).
El retorno recupera la presentación anterior mediante el código con los
mismos datos y documentos fiscales conservados.
