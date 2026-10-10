# PF-04 — representación del IVA guardado en PDF

Fecha: 10/10/2026. Riesgo: Nivel 2. Reparación autorizada por Santi durante
el QA de v0.3.8, ante IVA omitido en A/B y códigos superpuestos al detalle.

## Contrato e invariantes

El PDF A, incluidas notas, discrimina los componentes de IVA conservados por
alícuota y su suma exacta. El PDF B, incluidas notas, muestra el bloque inferior
izquierdo de transparencia fiscal e «IVA Contenido», sumando únicamente los
componentes guardados. No se deriva IVA del total ni se reconstruyen bases desde
ítems. Subtotal, otros tributos, total, moneda, cotización, fecha, receptor y
CAE conservan sus valores; una diferencia histórica de redondeo no se corrige.
Las notas conservan el signo guardado del documento; el signo negativo de los
reportes no se aplica al PDF. C no se declara exento ni recibe IVA inventado.

Autoridad: [RG 5614/2024, artículos 2 y 5](https://biblioteca.arca.gob.ar/search/query/norma.aspx?p=t:RAG%7Cn:5614%7Co:9%7Ca:2024%7Cf:12/12/2024),
consultada el 10/10/2026. Define discriminación y representación gráfica.
Este corte corrige esas omisiones; no acredita cumplimiento integral de todas
las leyendas o categorías fiscales posibles.

El modelo sólo conserva un agregado de otros tributos. Si es cero se muestra
0,00; si es distinto de cero, el bloque de impuestos nacionales indirectos
indica «No discriminados en los datos guardados». El agregado permanece visible
como «Importe Otros Tributos»: no se reclasifica como un impuesto nacional.
La clasificación completa pertenece al P2 de importes, sin bloquear nuevas
consultas ni imponer una reparación de datos históricos.

Códigos, descripciones y números extensos se ajustan al ancho de su celda,
sin truncar ni convertir a float. Los comprobantes corrientes conservan una
página A4 y QR/CAE legibles. Un detalle extenso puede ocupar más páginas;
este corte no rediseña la paginación ni su contador preexistente.

## Checklist fiscal y consumidores

Orden: API autentica y comprueba permiso del emisor, autorización y CAE;
servicio lee el comprobante; prepara importes de presentación; genera QR con
su contrato vigente; renderiza con escape HTML y fetcher restringido.
Consumidores: descarga y preview PDF desde API/UI. Emisión, importación,
worker, lotes, reintentos, reconciliación y scripts fiscales no consumen este
servicio para calcular ni persistir importes. No hay solicitudes a ARCA,
escrituras, transiciones, locks, nuevas reservas ni migraciones.

Fecha explícita, confirmación irreversible, idempotencia, numeración, estados
inciertos y aislamiento vigentes no cambian. Un fallo sigue produciendo el
error sanitizado de la API; no cambia un autorizado ni habilita reemisión.
Lecturas concurrentes son independientes: no requieren nuevas pruebas de
reservas o carreras pre/post-CAE en un camino que no las ejecuta.
Recuperación: volver al runtime anterior, sin restaurar ni degradar datos.

## Matriz de aceptación

- A/NC/ND: IVA 10,5 %, 21 % y 27 % guardado; varias tasas; sin ítems;
  diferencia de centavo conservada y sin bases inferidas.
- B/NC/ND: IVA Contenido exacto incluso con precisión decimal ambiental baja;
  otros tributos cero y no cero sin reclasificación falsa.
- C/NC/ND: sin IVA inventado ni exención supuesta.
- Render real: códigos ordinarios y de 101 caracteres, decimal ampliado dentro
  de sus celdas y completo; una página corriente, CAE y fechas conservados.
- API existente: autorización, aislamiento por emisor y error sanitizado;
  QR, snapshots del receptor, moneda/cotización y escape HTML preservados.
- Cierre: suite backend, formato/lint, documentación, revisión fiscal final
  canónica, CI completa y QA visual del candidato exacto. El ensayo previo
  no certifica el SHA que incorpore esta reparación.
