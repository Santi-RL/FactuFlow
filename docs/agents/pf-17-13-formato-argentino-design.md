# PF-17/PF-13 — formato argentino y precio unitario legible

Última revisión: 26/11/2026.

Estado: primer corte de precio unitario en comprobantes. El formato argentino
en las demás superficies continúa en el [roadmap](../../ROADMAP.md#1-pf-17pf-13--formato-argentino-y-claridad-visible).

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

La revisión, el detalle y el PDF de facturas, notas de crédito y notas de débito
A/B/C comparten la elección de precisión. La referencia es el subtotal de la
previsualización decimal o el subtotal guardado del comprobante. El importe de
bonificación del PDF se sigue obteniendo de la cantidad, el precio completo y
el porcentaje del renglón.

- Mostrar el precio con dos decimales si, con la cantidad y la bonificación
  del renglón, explica el subtotal visible y conserva el importe de bonificación
  visible cuando corresponda. Comparar con los importes guardados, bajo el
  redondeo vigente de presentación y con aritmética decimal.
- Si dos decimales no alcanzan, usar la menor cantidad de decimales adicionales
  que conserve esa correspondencia. Un precio positivo conserva por lo menos
  un dígito significativo: `0,004` sigue siendo `0,004` aunque el subtotal sea
  `0,00`. Antes de abreviar, comprobar el detalle original. Si difiere aun con
  la precisión completa, mostrar el precio guardado completo y conservar la
  discrepancia histórica. El ancho de la celda se resuelve sin cortar dígitos
  ni superponer columnas.
- Aplicar la regla al generar el PDF de cualquier comprobante, incluso
  histórico, en vista previa y en descarga individual o ZIP. En
  las vistas de lectura y revisión que muestran el precio junto con los
  importes del renglón, usar el mismo criterio con los importes de referencia
  de esa vista. El editor muestra el precio completo con coma decimal. Al abrir
  una factura para preparar una nota, se conservan los decimales del original
  en el pedido de revisión y en el de emisión, también si se editó otro campo.

Ejemplos sintéticos: con cantidad 1 y sin bonificación, el precio
`27.272,727272727272` puede mostrarse como `27.272,73` si el subtotal visible es
`27.272,73`. Con cantidad `1.000`, precio `0,123456` y subtotal `123,46`,
`0,12` sugeriría un subtotal distinto. El precio visible es `0,12346`. Con
dos unidades al mismo precio y bonificación del 100 %, se muestra `0,123`
para explicar la bonificación de `0,25` aunque el subtotal sea cero.

### Controles del primer corte

El selector es de lectura, sin escrituras ni llamadas a ARCA. Las respuestas
de revisión y detalle transportan el texto de presentación separado del precio
decimal. El PDF usa el mismo selector. El editor conserva el valor técnico
por separado y el DTO de emisión sólo admite los campos fiscales vigentes.
Para escribir un precio se usa coma decimal. Ante una entrada ambigua como
`1.234`, el editor conserva el texto y admite `1,234` o `1.234,00` según
el valor deseado.
Probar medio centavo, históricos discrepantes, precios positivos menores a un
centavo, bonificación total, precisión del original y revisión/confirmación de
una nota. Comparar QR, importes y geometría del PDF con datos sintéticos.
Los estados de emisión y las reservas no tienen transiciones en la lectura.

El segundo corte cubre fechas y sus controles, los demás números, reportes,
ayudas, constructor e instrucciones de Excel. Incluye pruebas en regiones
argentina y estadounidense y de equivalencia de celdas importables.

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
