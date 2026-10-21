# PF-04/PF-02 — lecturas históricas de emisor y punto de venta

Fecha y última revisión: 15/10/2026.

Estado: segundo corte preparado; implementación pendiente. Prioridad P2 fiscal,
dentro de Ahora 1. Preparación documental de nivel 0; implementación de nivel 2.
Consume el [primer corte de evidencia previa](pf-02-04-reconciliacion-integral-design.md#primer-corte-p2-evidencia-previa-compartida).
No habilita todavía recuperación moderna ni modifica producción.

## Objetivo y alcance

Un comprobante con evidencia verificable debe conservar los datos originales
del emisor y el número original del punto de venta al consultarlo, representarlo
en PDF/QR o incluirlo en informes, aunque después cambien sus fichas.
Reutilizar `solicitud_fiscal/1`; no capturar una segunda copia ni crear otro
registro histórico. El comprobante autorizado, su CAE y sus datos ya guardados
siguen siendo hechos persistidos, no el resultado de recalcular una solicitud.

Incluye listado y detalle de comprobantes; PDF descargado y preview; identidad
del QR y nombre de descarga; número completo en ventas e IVA; consumidores web
de esas respuestas y una indicación breve de cobertura histórica. No agrega
endpoints, acciones administrativas, confirmaciones ni consultas fiscales.

Se excluyen recuperación moderna individual/masiva, reconstrucción o vínculo de
comprobantes, liberación por «No existe», cambios de guardas/estados y emisores
autorizados, WSAA, padrón, notas guiadas, nuevas categorías, ranking, rediseño o
corrección general del paginado PDF, búsqueda/filtros P3 y dependencias.
No amplía PF-05 ni PF-10. La recuperación moderna individual precederá a la de
grupos en su preparación posterior, según el diseño integral.

## Base comprobada y consumidores

| Frontera | Situación vigente y responsabilidad del corte |
|---|---|
| `IntentoEmisionFiscal` / `evidencia_fiscal.py` | Conservan v1 inmutable, contexto y validación pura; reutilizar sin cambiar serialización, versión ni hashes |
| `IdempotenciaFiscalService.actualizar_intento_desde_respuesta` | Ya vincula el intento autorizado mediante `comprobante_id`; no necesita otro vínculo por número |
| `FacturacionService._guardar_comprobante` | Conserva receptor, ítems, importes, moneda, fechas y autorización; no cambiar sus escritores ni los cierres individual/batch/retry |
| `api/comprobantes.py` | Listado y detalle usan el número actual del punto; aplicar una proyección común después de seleccionar la página |
| `PDFService` / `api/pdf.py` / template | Emisor, CUIT, punto del encabezado, QR y descarga usan relaciones actuales; deben consumir la misma proyección histórica |
| `ReportesService` | Ventas e IVA usan el punto actual; cambiar sólo identidad/procedencia, conservando importes, signos, moneda y bases A-03 |
| Web de comprobantes, dashboard y reportes | Reutilizar número devuelto y presentar cobertura; conservar permisos, descarte de respuestas de otro emisor y contratos numéricos |
| `LoteComprobantesService.compactar_lote` / almacenamiento | Compactan filas detalladas, conservando grupos y resumen; demostrar que la fuente histórica y su vínculo sobreviven |
| Traslado v6 | Conserva evidencia de intentos incluidos y vínculos terminales; demostrar lectura equivalente tras traslado sin modificar formatos congelados |

El ranking puede compartir la carga de comprobantes de reportes: comprobar su
regresión, sin cambiar claves, atribución, posiciones ni pendientes propios.
Lotes, worker, reintentos, replay, reconciliación legacy y PF-05 son consumidores
de regresión; no se vuelven entradas al nuevo lector para emitir o cerrar estados.

## Fuente, vínculo y cobertura

1. Autorizar primero el acceso al emisor actual de la petición. El snapshot no
   concede permisos ni habilita una acción fiscal.
2. Buscar por el vínculo durable `IntentoEmisionFiscal.comprobante_id`, dentro
   del emisor del comprobante. No buscar por «último intento», sólo por número,
   nombre, fecha o configuración de ambiente actual. Detectar vínculos ajenos
   mediante identidades, sin cargar ni exponer su documento privado.
3. Exigir un único intento autorizado atribuible al comprobante para usar v1.
   Contrastar emisor ID, punto ID, tipo, número reservado, fecha, receptor básico,
   total, CAE y vencimiento contra los hechos guardados. Validar versión, JSON,
   hash y contexto contra la fila del intento mediante el lector existente.
   No reemplazar el número histórico por el número actual del punto.
4. El ambiente se toma del contexto congelado y se contrasta con el intento;
   `settings.arca_env`, certificados vigentes, fichas o revisiones actuales no
   seleccionan ni enriquecen historia. Un grupo en curso con un comprobante ya
   autorizado no necesita esperar que toda la operación del lote sea terminal.
5. Proyectar emisor desde `presentacion.emisor`, CUIT desde `contexto.cuit` y
   punto desde `contexto.punto_venta_numero`. Un campo original nulo permanece
   sin dato histórico; no se rellena con la ficha actual ni con valores supuestos.
   El resto de la representación conserva los datos del comprobante y sus ítems.

La comparación con el comprobante es de identidad y valores conservados, sin
admisibilidad de nueva emisión, ventana de fecha actual, tolerancia global,
conversión monetaria o recálculo de bases, IVA, subtotales e ítems.
Los intentos rechazados anteriores no sustituyen al autorizado. Dos fuentes
autorizadas ambiguas, vínculo cruzado, autorización contradictoria o evidencia
presente no verificable no se resuelven eligiendo la primera.

| Cobertura | Conducta |
|---|---|
| V1 verificable y atribuible | Usar emisor y punto originales. Si un dato de presentación era nulo, mostrar su ausencia sin enriquecerlo |
| Sin snapshot | Conservar la lectura y disponibilidad previas, incluidas las fuentes legacy actuales que ya se usan; indicar que los datos del emisor/punto no tienen snapshot acreditado |
| Evidencia presente no verificable | Consultas e informes disponibles con aviso; no generar PDF ni QR desde esa fuente ni sustituirla silenciosamente por fichas actuales |

La ausencia puede corresponder a un antecedente, importación externa o cobertura
parcial: **no prueba antigüedad ni habilita clasificación legacy**. Esta lectura
no cambia la elegibilidad de un intento, replay, recuperación o nueva emisión.
Una versión presente no soportada se comunica como no verificable, sin atribuir
al usuario una alteración ni tratarla como snapshot ausente.

## Decisión de producto e interfaz

Santi aceptó el 15/10/2026 mantener consultas e informes con aviso y rechazar
únicamente PDF/QR cuando la evidencia esté alterada, cruzada o contradiga al
comprobante. Los antecedentes sin snapshot conservan la operación previa con
cobertura indicada. Esta es una contención concreta para una representación
fiscal no verificable, no un requisito de reparación periódica de antecedentes.

Metadatos aditivos de lectura: cobertura y origen de emisor/punto, separados de
`bases_acreditadas` y `origen_bases`. No exponer JSON, hashes, IDs de operación,
guardas o diagnósticos internos. Las claves y tipos existentes conservan su
contrato; con fuente válida, el número visible corresponde al histórico.
En una fila no verificable, no presentar un valor de ficha actual como acreditado:
identificar su procedencia y advertirlo en la presentación. Conteos e importes
del informe siguen disponibles y sin cambios.

La web y el PDF deben expresar «Datos originales incompletos», «Sin snapshot
histórico» o «Datos históricos no verificados» según corresponda, con lenguaje
administrativo y sin mostrar versiones o hashes. No agregar modales ni pasos.
En antecedentes sin snapshot, el PDF indica que usa datos de ficha actual
cuando los utilice; esa leyenda no acredita su originalidad.
Ante fuente no verificable, la API PDF responde conflicto 409 sanitizado y la
web explica que el PDF no está disponible y que se consulte al responsable de
la instalación. La guarda existente de autorizado/CAE y el aislamiento siguen
siendo requisitos previos. No producir un QR vacío, con ceros o con otro emisor.

Conservar formato argentino, identificadores y ceros significativos, escape
HTML y fetcher PDF restringido. Encabezado, QR, número visible y nombre de
descarga deben compartir el mismo emisor/punto histórico; CAE, vencimiento,
receptor, fecha y moneda mantienen su representación contractual.

## Invariantes, orden y estados

- **Sólo lectura:** ninguna inserción, backfill, actualización de evidencia,
  comprobante o grafo fiscal. Cero llamadas WSAA/WSFE/padrón; el QR se construye
  localmente y su URL no se visita en tests.
- **Un solo origen acreditado:** versión, integridad, pertenencia y vínculo
  inequívoco antes de proyectar. No mezclar datos actuales con campos originales
  ausentes para aparentar una instantánea completa.
- **Hechos fiscales conservados:** no cambiar fecha, confirmación, numeración,
  CAE, importes, moneda, redondeos, hashes, idempotencia, SC-09 ni reservas RECE.
  Un error al leer o renderizar no convierte un autorizado en rechazado o pendiente.
- **Sin rehabilitación:** igualdad suficiente del comparador puro no cierra
  intentos modernos, no reconstruye comprobantes y no habilita otro envío.
- **Aislamiento:** mismo número en otro emisor o ambiente no aporta evidencia.
  No validar historia contra ficha, cliente, plantilla o certificado actuales.
- **Consistencia entre consumidores:** compartir proyección; no corregir sólo
  el encabezado dejando QR, descarga, listado o informe con otro punto.

Orden: autorización y comprobante permitido → página/período existente → carga
acotada de fuentes → validación/clasificación → proyección → respuesta/render.
El lector no llama a servicios de emisión ni incorpora sus locks o preflights.
Fuente o render fallidos devuelven cobertura/error sanitizados; no dejan un
estado fiscal nuevo ni escriben una reparación automática.

## Conservación, recursos y rollback

La evidencia continúa en el intento, enlazado al comprobante autorizado.
La compactación vigente no la sustituye por el payload del grupo ni por filas
del Excel. Probar que conserva documento/hash, vínculo y resultado de lectura.
No añadir caducidad, retención, limpieza o eliminación de operaciones/intentos.
Una futura liberación PF-10 debe preservar esta dependencia antes de borrar la
única fuente; su política no se implementa aquí.

No se prevé DDL, nueva tabla, columna, índice o formato de traslado. V1 y
v3/v4/v5/v6 permanecen congelados. Comprobar v6 con fuentes individual y masiva;
paquetes antiguos mantienen cobertura ausente, sin inventar intentos o snapshots.
Si el relevamiento de implementación muestra que una fuente necesaria no se
conserva o exige cambiar esquema/traslado, revisar el alcance antes de ampliar
estos contratos; no modificar un formato congelado para hacerlo pasar.

Seleccionar comprobantes y conteos antes de adjuntar evidencia: el join no debe
multiplicar filas, alterar orden/páginas ni omitir comprobantes sin snapshot.
Cargar fuentes en conjuntos acotados por página/período, sin una consulta por
fila, sin cargar todos los intentos del emisor ni conservar sus JSON completos
en una caché nueva. Medir consultas, memoria y coste de un período sintético;
no introducir una reescritura general de reportes o paginación.

Rollback de aplicación: volver al lector anterior conservando evidencia y datos;
sus representaciones vuelven a tener la cobertura previa. No afirmar que el
runtime anterior conserva las nuevas lecturas. Sin downgrade, restauración,
eliminación de reservas ni cambios de producción.

## Matriz y puertas de aceptación antes de implementar

| Caso | Resultado exigido |
|---|---|
| A/B/C y notas soportadas; cambio de razón social, CUIT, domicilio, IVA, ingresos brutos, inicio y número del punto | PDF/QR/descarga, lista/detalle e informes conservan emisor/punto originales; demás hechos fiscales iguales |
| Campos originales nulos | Ausencia explícita, sin completar desde ficha actual ni inventar condición/fecha |
| Legacy, PF-05 y traslado antiguo sin snapshot | Misma disponibilidad previa, cobertura explícita; sin nueva clasificación fiscal ni backfill |
| Hash/JSON/versión inválidos, vínculo cruzado, doble fuente y contradicción con comprobante/CAE | Aviso en consultas e informes; PDF y QR bloqueados con 409 sanitizado; estados e importes intactos |
| Igual número en dos emisores/ambientes; cambio de emisor durante carga y permiso revocado | Ninguna fuente, respuesta tardía o mensaje filtra datos de otro emisor; autorización vigente respetada |
| Individual, bloque, camino alternativo y retries; lote aún parcial con autorización persistida | Misma proyección para comprobantes ya autorizados; sin esperar un cierre adicional del lote ni tocar su grafo |
| Timeout, intento incierto sin comprobante o guarda huérfana | No crear vínculo, reconstrucción, transición o segundo envío para completar una lectura |
| Compactación de lote cerrado y traslado v6 SQLite→PostgreSQL | Evidencia/hash y vínculo conservados; lectura, número y cobertura equivalentes |
| Listas mixtas, varias fuentes y página máxima existente; ventas/IVA por moneda | Conteos/orden/páginas correctos, consultas acotadas sin N+1, totales y signos A-03 sin cambios |
| PDF real, QR decodificado localmente, códigos extensos y página corriente | Identidad coherente, escape/fetcher preservados, sin recortes ni superposición; página corriente conserva legibilidad |

Tests unitarios del lector/proyección y pruebas API/PDF/reportes; regresión de
facturación, idempotencia, RECE, replay, legacy, retries, almacenamiento y traslado.
SQLite y PostgreSQL desechable para vínculo, sesiones concurrentes y compactación;
no hacen falta nuevas carreras de reserva para un lector que no reserva ni envía.
Comprobar que lectura, error y rollback no cambian filas antes/después.

La implementación deberá completar lint, formato, tipos, suites, auditorías,
CI nivel 2, revisión fiscal final y QA visual sintética. Sin certificados,
credenciales, bases ni datos fiscales reales en Git. No ejecutar autoreview
preliminar por preparar el diseño ni presentar esta matriz como pruebas realizadas.
Resultado y evidencia del candidato quedan en PR o rutas privadas, no en este
contrato. El [checklist fiscal](fiscal-change-checklist.md) gobierna consumidores,
errores, concurrencia, revisión y cierre; [calidad](change-quality-gates.md)
gobierna las puertas. Publicación, integración y despliegue son operaciones
separadas de esta preparación.
