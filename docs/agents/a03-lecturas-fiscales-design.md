# A-03 — bases de IVA y monedas en lecturas actuales

Fecha de diseño: 07/10/2026.

Estado: contrato de la corrección de lecturas actuales A-03.

## Autoridad y alcance

Corrección P1 de PF-03/PF-04/PF-17, Nivel 2, desde la
[auditoría A-03](../project/analysis/auditoria-integral-2026-10.md#a-03--lecturas-fiscales-inconsistentes-p1-para-corrección).
Santi eligió separar totales y ranking por moneda el 07/10/2026. No hay
conversión automática ni consulta de cotizaciones. Cada comprobante conserva
sus importes nominales y su cotización histórica explícita.

Consumidores: servicio y API de ventas, IVA y ranking; sus tres pantallas;
consulta de comprobantes (lista y detalle) y PDF. El dashboard vigente sólo
cuenta comprobantes: no consume importes ni ranking. Emisión, importación,
workers, reintentos, reconciliación y duplicados no consumen estos reportes.
No modificar su calculador, solicitudes, hashes, estados o persistencia.

## Contrato de bases y cobertura histórica

Nunca dividir IVA redondeado por la tasa ni sumar subtotales de líneas ya
redondeadas para reconstruir una base fiscal. Ordenar los ítems conservados
por su orden y reutilizar `calcular_totales` con el contexto decimal vigente
(28 cifras, HALF_EVEN). Aceptar las bases reconstruidas sólo cuando subtotal,
cada componente de IVA, total y subtotal individual contrastado con su redondeo
de guardado coincidan con los importes conservados y las tasas estén soportadas
para ese tipo (C sólo IVA 0, conforme a la validación vigente). No sumar esos
subtotales individuales para formar una base. No presentar esta reconstrucción como una nueva
consulta o certificación de ARCA.

Si no hay detalle, hay una tasa sin soporte o los importes no coinciden,
devolver bases desconocidas (`null`), su procedencia y cobertura. Conservar
neto, IVA y total del comprobante. El resumen por tasa es desconocido si
incluye bases desconocidas; no mostrar una suma parcial como completa.
Un reporte consultable no bloquea emisión ni exige reparar historia.

El contrato actual no conserva categorías fiscales separadas para tasa cero,
exento y no gravado. Los importes con IVA cero se muestran como «Sin
clasificación fiscal acreditada», y los C como «Sin IVA discriminado»;
no deducir exención por letra ni por condición del receptor. Las categorías
completas permanecen en el corte P2 de importes. Los campos antiguos
`no_gravado` y `exento` quedan desconocidos cuando no existe evidencia.

Referencia primaria: [manual WSFEv1 v4.7, revisión 01/09/2026](https://www.arca.gob.ar/ws/documentacion/manuales/manual-desarrollador-ARCA-COMPG.pdf),
consultado el 07/10/2026: distingue `ImpNeto`, `ImpTotConc`, `ImpOpEx`,
`BaseImp` e `Importe`; una tasa numérica no acredita esas categorías.

## Monedas y compatibilidad HTTP

- Filas de ventas/IVA y clientes del ranking incluyen moneda; comprobantes
  incluyen cotización conservada, como cadenas decimales exactas.
- `por_moneda` conserva los resúmenes independientes. Campos escalares antiguos
  continúan disponibles en períodos de una moneda; en períodos mixtos son
  `null`, nunca una suma nominal heterogénea. Los conteos generales siguen
  disponibles. No inferir una moneda para datos que no la acreditan.
- El ranking aplica el límite y el orden dentro de cada moneda. Su total es el
  de los clientes mostrados, como en el contrato anterior, identificado como tal.
- Las pantallas seleccionan automáticamente una moneda disponible y permiten
  cambiarla para ver sus filas, resumen y posiciones. No agregan una acción
  obligatoria antes de generar el reporte. Nombres y códigos explícitos evitan
  atribuir pesos a divisas desconocidas.
- Lista, detalle y PDF muestran moneda nominal. Detalle y PDF muestran la
  cotización conservada, también disponible en la API de listado;
  no recalculan ni convierten importes.

## Checklist fiscal: orden, estados y recuperación

Aplicado antes de implementación. Orden: autenticación y emisor activo vigentes;
consulta sólo de autorizados del emisor/período; lectura de evidencia;
reconstrucción y contraste sin escritura; agrupación por moneda; serialización
decimal y presentación. No hay transiciones ni nuevas reservas, constraints,
migraciones o locks. Lecturas concurrentes conservan el aislamiento vigente
SQLite/PostgreSQL. No se alcanza WSAA, WSFE ni CAE.

Fecha, confirmación irreversible, idempotencia, numeración, incertidumbre y
reconciliación permanecen fuera del camino modificado. Pruebas fiscales de
emisión existentes cubren su conservación; no añadir replay artificial de un
reporte de lectura. Historia insuficiente produce cobertura desconocida, no
mutación ni rechazo de un autorizado. Rollback de aplicación al SHA anterior,
sin downgrade ni restauración de datos.

## Matriz de aceptación previa

| Frontera | Evidencia requerida |
|---|---|
| Bases | Neto 0,03 / IVA 0,01; varias tasas; líneas de medio centavo; descuentos; orden conservado; discrepancias; ausencia de detalle; tasas sin soporte |
| Historia | Bases desconocidas visibles, IVA/neto conservados, sin inventar exento/no gravado; C; NC negativas incluso en resúmenes de sólo créditos |
| Monedas | PES/DOL y código desconocido; cotización histórica exacta sin consulta; orden/límite independiente; sin total mixto; períodos vacíos y de una moneda |
| Precisión | Decimales amplios A-01, sumas y signos exactos; no float ni cálculos fiscales en frontend |
| Aislamiento | Período/emisor/estado autorizado; cambio de emisor y respuestas tardías en UI |
| Presentación | Tres reportes, lista/detalle y PDF; moneda explícita, desconocidos distintos de cero y NC visibles |
| Cierre | Tests del área, lint/formato/tipos/build, documentación, revisión fiscal final canónica; CI completa antes de integración |

No incluye dependencias abiertas, paginación SC-17, importación histórica PF-05,
dashboard futuro, nuevas categorías ni despliegue.
