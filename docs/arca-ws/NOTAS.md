# ARCA WS - Notas prácticas

Última actualización: 10/08/2026

Este archivo resume lo que conviene recordar rápido sin volver a abrir todos los PDFs.

## Homologación - checklist operativo real

1. Adherir `WSASS - Autogestion Certificados Homologacion`
2. Generar CSR con el CUIT del titular del certificado
3. Crear DN y certificado en WSASS
4. Crear autorización al servicio `wsfe` para el CUIT representado
5. Verificar certificado, conexión y lecturas seguras
6. No solicitar CAE: PF-19B mantiene homologación cerrada hasta contar con una
   fuente probatoria específica para ese ambiente

## Lo que aprendimos hoy

### 1. Verificacion de homologación

- No confiar en QR como validación de homologación.
- El QR de PDF debe codificar la URL oficial heredada
  `https://www.afip.gob.ar/fe/qr/?p={base64}` con JSON de comprobante en
  Base64. En tests se decodifica el payload y se verifican campos ARCA:
  `ver`, `fecha`, `cuit`, `ptoVta`, `tipoCmp`, `nroCmp`, `importe`, `moneda`,
  `ctz`, `tipoDocRec`, `nroDocRec`, `tipoCodAut`, `codAut`.
- La verificacion correcta es por webservice, usando `FECompConsultar`.

### 2. Puntos de venta

- En el portal no se detectó una pantalla separada de "puntos de venta homologación".
- Hay que mirar la pantalla habitual `A/B/M de puntos de venta / emision`.
- La columna editable `Sistema`, una clasificación genérica Web Services y
  `FEParamGetPtosVenta` no acreditan RECE. PF-19B exige una cabeza durable con
  estado efectivo `verificado_rece`; PF-19A queda como denegación adicional.
- Solo un administrador en servidor productivo puede atestar una constancia
  completa, no ambigua y de hasta siete días. Únicamente la señal exacta
  `RECE para aplicativo y web services` promueve el ambiente `produccion`.
  Homologación no hereda esa evidencia.

### 3. `FEParamGetPtosVenta`

- En homologación puede responder `602 - Sin Resultados`.
- Eso no significa necesariamente que el punto de venta sea invalido.
- En esta sesión `FECompUltimoAutorizado` y la emisión real sí funcionaron.
- El campo `Bloqueado` llega como `N`/`S`. `N` significa no bloqueado; no debe
  evaluarse como booleano directo porque cualquier string no vacío es truthy en
  Python.
- Si `FEParamGetPtosVenta` falla durante una importación de constancia, no usar
  `{}` como si todos los puntos estuvieran activos: preservar el estado local de
  puntos existentes y dejar inactivos los puntos nuevos hasta sincronizar o
  revisar manualmente.
- Si el usuario cambia de emisor mientras se importa una constancia, la UI no
  debe mostrar el resultado bajo el nuevo contexto.
- La evidencia operativa privada confirmó que un punto técnicamente Web
  Services puede no pertenecer a RECE. Identificadores y fecha exacta quedan
  fuera del repositorio; la invariante es que `FEParamGetPtosVenta` y
  `Bloqueado=N` no prueban elegibilidad fiscal.
- PF-19B exige estado efectivo `verificado_rece` antes de crear una operación o
  intento nuevo y antes de `FECAESolicitar`. La capa exterior batch puede haber
  autenticado WSAA o hecho una lectura WSFE segura de capacidad; eso no autoriza
  ni permite saltear la compuerta. PF-19A mantiene la denegación adicional
  para tuplas declaradas, pero nunca promueve elegibilidad.

### 4. `CondicionIVAReceptorId`

ARCA exigió este campo en homologación.

Mapping aplicado en el proyecto:
- `RI` -> `1`
- `Monotributo` -> `6`
- `Exento` -> `4`
- `CF` -> `5`

### 4.b Consumidor final

- Para consumidor final, ARCA pública que el comprobante debe llevar la leyenda
  `A CONSUMIDOR FINAL`.
- Si el importe es igual o superior a `$10.000.000`, corresponde informar
  CUIT/CUIL/CDI/DNI, pasaporte u otro documento válido.
- FactuFlow usa tipo documento `99` y número `0` cuando el Excel no trae
  documento y el importe queda bajo ese umbral. No crea cliente persistente por
  defecto en ese caso; guarda snapshot del receptor en el comprobante.

### 4.c Fecha de emisión

- No asumir fecha del día actual para `CbteFch`.
- La prohibicion aplica a facturas, notas de crédito y notas de débito. No usar
  `date.today()`, `datetime.today()`, `new Date()` ni equivalentes como default
  de fecha fiscal.
- FactuFlow exige `fecha_emision` explícita en emisión individual y en lotes.
- Antes de solicitar CAE, la UI debe mostrar: `Está seguro que quiere emitir
  comprobantes con fecha XX/XX/XX? Recuerde que luego no podrá emitir
  comprobantes con fecha anterior para ese mismo punto de venta.`
- La API debe bloquear el pedido si no llega la confirmación fiscal explícita:
  `confirmacion_fecha_fiscal=true` para emisión individual o
  `X-Confirmacion-Fecha-Fiscal` con token exacto
  `fechas=YYYY-MM-DD,...;puntos_venta=N,...` para lotes. El token de confirmación de lotes usa fechas técnicas `YYYY-MM-DD`; el texto visible de confirmación debe mostrarlas en `DD/MM/AAAA`.
- Si ARCA ya devolvio CAE y falla la persistencia local posterior, conservar
  punto de venta, número, fecha, total y CAE, marcar
  `requiere_reconciliacion` y bloquear reintentos. Primero consultar ARCA y
  reconciliar.
- En lotes, el usuario debe elegir si la fecha de emisión sale del archivo o si
  se fija una fecha para todos los comprobantes antes de validar.
- Los perfiles de carga masiva no pueden definir la fecha de emisión con reglas
  relativas como último día del mes anterior. La fecha fiscal debe quedar para
  completar manualmente, venir del archivo o ser una fecha personalizada
  explícita válida. Las reglas relativas se reservan para período de servicios o
  vencimiento cuando dependen de una fecha de emisión ya explícita.
- Los perfiles de carga masiva pueden sugerir un punto fijo solo si el servidor
  devuelve `usable_factuflow=true`, incluido estado efectivo
  `verificado_rece`. El perfil no crea evidencia ni evita que el lote revalide
  el snapshot. Si el punto no está cargado o acreditado, hay que completar
  primero `Puntos de venta`.
- Para servicios también se deben resolver `FchServDesde`, `FchServHasta` y
  `FchVtoPago`.
- Para `Concepto=1` (Productos), no informar `FchServDesde`, `FchServHasta` ni
  `FchVtoPago`; FactuFlow bloquea esa combinación antes de `FECAESolicitar`.
- Validación preventiva usada por el proyecto:
  - productos: N-5 / N+5
  - servicios o productos y servicios: N-10 / N+10
  - N es la fecha de solicitud de autorización
- Si una fecha de extracto queda fuera de ventana, el lote debe quedar observado
  antes de emitir para que el usuario/contador defina el criterio fiscal.

### 4.d Concepto fiscal ARCA y descripción facturada

- No asumir productos ni servicios por defecto.
- Antes de emitir, el usuario debe elegir `Productos`, `Servicios` o
  `Definido por archivo`.
- Si se elige `Definido por archivo`, el Excel debe traer una columna válida con
  `Producto` o `Servicio` en todas las filas.
- Si la columna falta o una fila trae un valor distinto, se debe informar al
  usuario y bloquear la emisión del lote observado.
- Esto define el concepto fiscal ARCA del comprobante; no define el texto del
  ítem facturado. La descripción/concepto facturado del ítem, por ejemplo
  `Honorarios`, `Zapatillas` o `Servicio mensual`, debe venir de una columna del
  archivo o de un valor fijo confirmado para todo el lote.
- No usar defaults ocultos para la descripción del ítem antes de validar o
  emitir.
- Los perfiles de carga masiva pueden precargar punto de venta, concepto fiscal
  ARCA y descripción facturada solo como valores visibles/editables antes de
  validar.
- Si la fecha del archivo queda fuera de la ventana ARCA aplicable al concepto,
  el usuario debe elegir por pantalla una fecha permitida por el web service
  antes de emitir.

### 4.e Errores inesperados de emisión

- No devolver por HTTP el texto de una excepción inesperada durante emisión.
  Puede incluir credenciales, URLs internas o rutas de certificados.
- Registrar traceback y detalle solo en logs privados; responder un mensaje
  genérico también desde `FacturacionService`, incluidos sublotes y fallos
  post-CAE, y revisar idempotencia e intentos fiscales antes de reintentar.

### 4.e.2 Rechazo global excluyente PF-19C

- Solo el entero exacto `10005` puede cerrar un rechazo global, y únicamente
  cuando la cabecera de `FECAESolicitar` es `R`, coincide estrictamente con el
  request y no hay detalle ni CAE. No se infiere por texto, `1005`, strings,
  floats, booleanos, duplicados o códigos mezclados.
- Un error global desconocido, mixto, parcial, contradictorio o un timeout/Fault
  de transporte conserva `requiere_reconciliacion`. No se reintenta ni solicita
  otro CAE a ciegas. En un lote, FactuFlow cierra el sublote enviado y detiene
  los restantes como no enviados, sin atribuirles un rechazo ARCA.
- La resolución de candidatos legacy no invoca `FECAESolicitar`: planifica sin
  escribir y aplica solo con backup verificable, hash, actor y evidencia externa
  segura. Si el ambiente es indeterminado, compara producción y homologación;
  cualquier autorización o incertidumbre mantiene reconciliación. El journal
  append-only es evidencia privada sanitizada y el traslado a VPS lo omite sin
  reatestarlo.

### 4.e.1 Contrato estricto antes de ARCA

- El objeto superior de una emisión es cerrado. Una clave desconocida o mal
  escrita debe responder `422 extra_forbidden` antes de idempotencia, reserva,
  intento fiscal o `FECAESolicitar`.
- No limpiar automáticamente campos desconocidos de un snapshot batch legacy:
  pueden expresar una decisión fiscal que FactuFlow no comprende. El worker,
  reintento, stale y reconciliación deben fallar cerrados sin reemitir.
- Esta regla no cambia el contrato SOAP ni autoriza usar defaults de fecha,
  moneda o cotización como sustituto de una entrada mal escrita.

### 4.f Reconciliación externa de lotes

- Para comprobantes emitidos manualmente en ARCA Web, FactuFlow debe usar
  `FECompConsultar` antes de registrarlos localmente.
- La consulta debe coincidir con emisor activo, receptor, tipo, punto de venta,
  número, fecha fiscal, total, resultado autorizado y CAE.
- Un comprobante externo verificado no puede vincularse a más de un grupo local;
  la base lo refuerza con unicidad parcial sobre el `comprobante_id` del grupo.
- Esos comprobantes se guardan con `origen_emision = arca_web`.
- Si un lote quedó en `requiere_reconciliacion` o un grupo quedó
  `reintentando` por fallo posterior a ARCA, no reintentar. Primero consultar
  ARCA y reconciliar.
- Si un lote masivo queda `procesando` y supera la ventana operativa
  `BATCH_PROCESSING_STALE_MINUTES`, la ventana vencida no habilita reemisión
  automática. El worker solo puede vincular comprobantes locales ya autorizados
  sin pedir CAE si están respaldados por un intento fiscal `autorizado` del
  mismo lote/grupo, con comprobante, número planificado, CAE, fecha, receptor y
  total coherentes. Un comprobante local parecido pero sin ese intento no debe
  cerrar el grupo. Si quedan pendientes intactos, solo se reencolan cuando no
  tienen intento fiscal, CAE, número, comprobante vinculado ni comprobante local
  autorizado candidato, y la comparación con `FECompUltimoAutorizado` produce
  `alineada` o `arca_adelantada` sin incertidumbre propia. La recuperación no
  asigna número ni crea reserva; el procesamiento normal repite la consulta antes de FECAE.
  Si queda cualquier duda, el lote pasa a
  `requiere_reconciliacion` con evento `bloqueo_operativo_no_reemitir`; solo los
  grupos con evidencia fiscal se marcan `requiere_reconciliacion`.
- `Completado` queda reservado para comprobantes emitidos por FactuFlow.
  Cuando hubo emisión externa verificada, el cierre correcto es
  `cerrado_reconciliado`.

### 4.f.1 Numeración individual y batch compatible con otros sistemas

Estado 05/08/2026: PF-02A y los tres cortes de PF-02B están integrados en
`main`. Separan el último local del último ARCA; el núcleo batch, los reintentos
manuales y la recuperación stale pueden convivir con `arca_adelantada` cuando
no existe incertidumbre propia. FactuFlow no rellena huecos ni importa
comprobantes en este paso.

El manual WSFE exige que `CbteDesde` sea el siguiente al último autorizado y
puede devolver `10016` ante una consecutividad inválida. Como otros sistemas no
comparten locks con FactuFlow, se repite `FECompUltimoAutorizado` después de la
reserva individual o de todas las reservas durables del rango batch e
inmediatamente antes de `FECAESolicitar`.

- Si la segunda consulta cambió o falló, FECAE no comienza y el intento se
  cierra `fallido_verificado`.
- No se replantea el número ni se reintenta automáticamente bajo la misma
  confirmación.
- Un rechazo explícito posterior a FECAE sigue siendo rechazo ARCA verificable;
  una excepción ambigua sigue requiriendo `FECompConsultar` y reconciliación.
- El procesamiento batch normal y el reintento manual aplican el segundo
  preflight. En reintentos, un bloqueo o aborto detiene los grupos posteriores;
  solo un rechazo explícito permite continuar. Una respuesta ambigua o una
  falla local después de una autorización conocida exige rollback del registro
  incompleto y `requiere_reconciliacion`, nunca `fallido`.
- La recuperación stale del worker mantiene una puerta estricta antes de
  reencolar y no libera intentos inciertos. Solo mueve el lote a `en_cola`; el
  procesamiento normal crea reservas y repite `FECompUltimoAutorizado` antes de
  FECAE. Los errores persistidos usan categorías sanitizadas.
- La importación histórica para informes es PF-05 y nunca condiciona una nueva
  emisión.

### 4.f.2 PF-19: elegibilidad RECE y rechazo global preautorización

Estado 08/08/2026: PF-19A cerró el diseño fiscal, incorporó la contención
selectiva antes de `FECAESolicitar` y agregó un inventario legacy estrictamente
de solo lectura. No reabre PF-02 ni modifica su regla de numeración.

- PF-19A conserva los errores globales legacy como incertidumbre: la firma
  textual `10005` solo identifica candidatos y nunca autoriza transición,
  reparación o reemisión.
- PF-19B separa `verificado_rece`, `no_rece` y `no_verificado`, migra los datos
  existentes sin afirmar compatibilidad no demostrada y aplica la misma puerta
  en emisión individual, lotes, perfiles, reintentos y worker.
- PF-19C, ya integrado en `main`, estructura los errores globales WSFE. Solo
  códigos que el
  contrato oficial vigente identifique como rechazo excluyente preautorización
  pueden cerrar el intento como rechazo terminal; timeout, respuesta parcial o
  código desconocido conservan `requiere_reconciliacion`. El `autoreview` final
  cerró limpio y la CI Nivel 2 del SHA funcional aprobó PostgreSQL real y Runtime
  Smoke; la aceptación PF-16G y el ensayo privado de
  backup/restauración/upgrade/rollback quedaron aprobados el 10/08/2026; al
  cerrar el snapshot de `v0.3.0`, producción continuaba en `v0.2.2`.
- El inventario PF-19A no consulta ARCA, no infiere el ambiente histórico y no
  sanea registros. La política de contraste y resolución pertenece a PF-19C;
  mientras tanto, los lotes legacy no se reparan mediante edición directa ni
  reintento ciego.

### 4.g Idempotencia fiscal y CAE

Estado 2026-07-13: PF-01 está cerrado. PF-01B.3 validó en SQLite y PostgreSQL 16
efímero los constraints, la migración y la concurrencia, y Clawpatch revalidó
B10/B17 como `fixed`. El borde WSFE solo acepta
una autorización con `Resultado=A`, CAE ASCII de 14 dígitos y vencimiento
calendario válido `YYYYMMDD`; rechaza `P`, resultados desconocidos, errores
globales y respuestas batch ambiguas. Un `R` completo permanece como rechazo
verificable. Toda excepción inesperada posterior a iniciar `FECAESolicitar`
produce `requiere_reconciliacion`, intenta actualizar los intentos y conserva un
replay idempotente `409` cuando la base lo permite. La UI individual congela en
memoria la clave y el payload, bloquea cambios y verifica la misma operación
hasta un resultado final. No usa storage web; una recarga forzada no habilita
reemisión. PF-01B agrega checks persistidos de estados y coherencia CAE, con
preflight bloqueante y sin normalización de datos legacy. Diseños y tests:
`docs/agents/pf-01-authorization-integrity-design.md` y
`docs/agents/pf-01b-persistence-integrity-design.md`.

- La llave de idempotencia de una emisión no es el CAE. La llave operativa es
  `X-Idempotency-Key` junto con emisor, tipo de operación y hash del payload
  fiscal.
- El CAE confirma autorización fiscal y sirve para persistir, auditar y
  reconciliar; llega después de la llamada irreversible a ARCA, por eso no puede
  ser el primer control de duplicación.
- Emisión individual, procesamiento de lotes y reintento de fallidos deben
  rechazar pedidos sin `X-Idempotency-Key` antes de solicitar CAE.
- Misma clave y mismo payload debe devolver la respuesta ya persistida o el
  estado actual de la operación, sin volver a llamar a ARCA. Misma clave con
  datos distintos debe devolver conflicto.
- Antes de `FECAESolicitar`, FactuFlow debe crear intento fiscal durable con
  tipo, punto de venta, número planificado, fecha, total y receptor. Esa reserva
  bloquea reintentos inciertos.
- Pre-ARCA solo se responde `503` con `Retry-After: 2` cuando FactuFlow confirmó
  durablemente recuperación segura y cero intentos. La operación pasa
  `en_proceso -> interrumpida_pre_arca`; un replay con la misma clave hace CAS a
  `en_proceso`, con un único ganador.
- Individual, lote síncrono y reintento sin intentos restauran el lote a
  `validado` o el grupo exacto a `fallido`. Con intento existente o recuperación
  no persistible se responde `409 pre_arca_estado_bloqueado`, conservando la
  clave y sin afirmar reconciliación ARCA porque FECAE no comenzó.
- El worker pre-ARCA solo devuelve el lote a `en_cola` sin intentos, conserva la
  operación `en_proceso` e impide replay HTTP paralelo. Post-ARCA conserva `409`,
  reconciliación y ausencia de retry. `IntegrityError` no cambia.
- `get_db` preserva la excepción primaria aunque fallen `rollback` o `close`; un
  `409` post-ARCA no se degrada a `503` por cleanup.
- Si un intento queda `en_proceso` vencido, consultar `FECompConsultar` por
  tipo, punto y número planificado. Solo liberar numeración si ARCA confirma que
  el comprobante no existe. Si ARCA confirma CAE, vincular o reconstruir cuando
  haya datos locales suficientes; si no, dejar `requiere_reconciliacion`.
- Los duplicados lógicos son advertencias operativas: pueden requerir
  confirmación adicional, pero no reemplazan la confirmación fiscal ni bloquean
  automáticamente la emisión.

### 5. Estructura SOAP correcta en `FECAESolicitar`

El proyecto tuvo que corregir estas estructuras:

- `FeDetReq` debe enviarse como:
  - `{ "FECAEDetRequest": [ ... ] }`
- `Iva` debe enviarse como:
  - `{ "AlicIva": [ ... ] }`
- `Tributos` debe enviarse como:
  - `{ "Tributo": [ ... ] }`
- Para notas de crédito/débito con comprobante asociado, `CbtesAsoc` debe
  enviarse como:
  - `{ "CbteAsoc": [ ... ] }`
- Para comprobantes tipo C (`11`, `12`, `13`), no enviar el objeto `Iva`.
  ARCA rechaza con `10071` aunque se informe alícuota 0.
- FactuFlow debe bloquear localmente cualquier ítem tipo C con IVA distinto de
  0 antes de solicitar CAE.
- En emisión individual, solo `Resultado=A` habilita continuar. Un detalle
  parcial `P` o cualquier estado no aprobado debe rechazarse aunque el método
  SOAP haya respondido sin fault.
- En `FECompConsultar`, usar `CbteNro` si existe y evaluar `CbteDesde` solo
  como fallback real; no acceder al fallback anticipadamente.
- Los importes fiscales del request deben cuantizarse con Decimal a dos
  decimales y redondeo `ROUND_HALF_UP` antes de enviar el SOAP. Esto aplica a
  `ImpTotal`, `ImpTotConc`, `ImpNeto`, `ImpOpEx`, `ImpIVA`, `ImpTrib`, bases e
  importes de IVA y tributos. No usar `round(float(...), 2)`: casos como
  `2.675` pueden terminar en `2.67` por representación binaria. Los modelos
  internos de request ARCA deben conservar `Decimal` hasta el armado del payload.
- Antes de habilitar acciones WSFE desde la UI, FactuFlow debe verificar que
  haya certificado activo para el `ARCA_ENV` actual y que tanto el `.crt` como
  la `.key` sigan disponibles dentro de `CERTS_PATH`. Un registro de otro
  ambiente o con material local incompleto no sirve para esa operación.
- El cliente WSFE debe repetir esa comprobación inmediatamente antes de WSAA.
  Los rutas faltantes se registran solo en logs privados y no se incluyen en la
  respuesta HTTP.

### 5.a Sublotes en `FECAESolicitar`

- `FECAESolicitar` permite enviar un comprobante o un lote de comprobantes.
- `FeCabReq.CantReg` debe coincidir exactamente con la cantidad de detalles
  `FECAEDetRequest` enviados.
- Un request con mas de un detalle debe ser homogeneo: mismo `PtoVta` y mismo
  `CbteTipo`.
- La cantidad máxima no se debe hardcodear. Se consulta con
  `FECompTotXRequest`, que devuelve `RegXReq`.
- FactuFlow consulta `RegXReq` al procesar el lote y divide por sublotes de ese
  tamaño. Si ARCA no informa `RegXReq`, degrada al modo unitario y deja aviso
  explícito en el lote para el usuario.
- Los tipos FCE/MiPyME documentados por ARCA se fuerzan a modo unitario aunque
  `RegXReq` permita más registros.
- La respuesta de un sublote se correlaciona por `CbteDesde`, no por posición
  en la lista. La cantidad de detalles debe coincidir, no puede haber números
  duplicados y el conjunto de `CbteDesde` devuelto debe ser exactamente el de
  los comprobantes solicitados.
- Si falla la preparación o reserva local antes de `FECAESolicitar`, la
  transacción completa revierte: cero guardas, intentos y reservas nuevos, y
  cero FECAE. WSAA o lecturas seguras (`FECompTotXRequest`,
  `FECompUltimoAutorizado`) pueden haber ocurrido; no describirlo como “cero
  contacto con ARCA”.
- Si un sublote enviado no devuelve detalle confiable, el lote queda en
  `requiere_reconciliacion`; no se reintenta automáticamente y ningún grupo
  remanente debe seguir mostrándose como listo para emitir.
- Si el CAE fue autorizado y luego falla el cierre del intento fiscal local, el
  resultado conserva CAE/número y queda `requiere_reconciliacion`. No se debe
  devolver un error genérico que habilite reintento automático.

### 5.b Notas de crédito C por duplicados productivos

- Para Nota de Crédito C usar `tipo_comprobante = 13`.
- Si anula una Factura C, informar como asociado `tipo = 11`, punto de venta,
  número, fecha y CUIT del emisor de la factura duplicada.
- Los importes van positivos; el tipo de comprobante define que se trata de un
  crédito.
- La corrección productiva histórica se ensayó sobre una copia privada y luego
  se verificó en modo solo lectura con `FECompConsultar`. Identificadores,
  cantidades, CAEs y asociaciones exactas permanecen en evidencia operativa
  privada; la invariante pública es que cada crédito conservó el `CbtesAsoc`
  esperado.
- En la respuesta de `FECompConsultar`, usar `CbteDesde`/`CbteHasta` para el
  número; no depender de `CbteNro`.

### 6. Cache de tickets WSAA

- Antes el cache era solo en memoria.
- Ahora persiste en disco para evitar depender del proceso actual.
- Archivo actual: `backend/data/arca_token_cache.json`.
- La clave del cache incluye servicio, CUIT, ambiente y huella SHA-256 del
  certificado público. Un ticket obtenido con un certificado no debe
  reutilizarse con otro certificado del mismo CUIT y ambiente.

### 7. CUIT correcto para WSFE

- Si el certificado pertenece a un titular y opera para una empresa representada, no mezclar ambos CUIT.
- El helper de ARCA debe operar con el CUIT de la empresa activa representada.
- Este punto fue clave para corregir la sincronización de puntos de venta desde UI.
- Antes de solicitar CAE, el backend debe confirmar que el punto de venta y el
  `cliente_id` opcional sean del emisor activo. Un ID válido pero de otro CUIT
  se rechaza localmente para no mezclar comprobantes, clientes ni numeración.
- Las vistas de certificados y puntos de venta no deben iniciar consultas WSFE
  sin un emisor confirmado por pestaña ni conservar acciones pendientes cuando
  cambia el emisor activo.

### 8. Paths legacy de certificados

- La base local puede traer rutas tipo `certs/archivo.crt`.
- El runtime ahora acepta path absoluto dentro de `CERTS_PATH`, filename simple
  y valor legacy con prefijo `certs/`.
- El upload de certificados no acepta paths arbitrarios en `key_filename`: debe
  ser una clave generada por FactuFlow para el CUIT y ambiente activos.
- El upload de certificados rechaza archivos mayores que
  `CERTIFICATE_MAX_UPLOAD_BYTES` antes de guardar un `.crt` nuevo.
- Las claves privadas nuevas se cifran con `ARCA_PRIVATE_KEY_PASSWORD` o, si no
  está configurada, con `APP_SECRET_KEY`, y se crean con permisos restrictivos
  desde la apertura del archivo. Las claves legacy sin cifrar se pueden seguir
  leyendo para continuidad operativa.
- Este ajuste destrabo la consulta de próximo número y la emisión individual desde UI.

## Donde mirar en el código

- `backend/app/arca/cache.py`
- `backend/app/arca/models.py`
- `backend/app/arca/wsfev1.py`
- `backend/app/services/facturacion_service.py`
- `backend/app/services/lote_worker.py`

## Producción

- Usar certificado productivo y autorización `wsfe` productiva; los certificados
  de homologación no sirven para producción.
- Después de crear el certificado productivo, asociar el alias del computador al
  servicio `wsfe` desde `Administrador de Relaciones de Clave Fiscal`. Si falta
  esa asociacion, WSAA devuelve `Computador no autorizado a acceder al servicio`.
- Usar un punto de venta productivo cuya pertenencia a RECE haya sido revisada
  administrativamente y mantener numeración correlativa. La descripción
  genérica Web Services no basta. En PF-19B, el punto debe tener estado efectivo
  `verificado_rece`; una atestación vencida o ausente falla cerrado.
- La validación interpreta `Bloqueado=N` como señal técnica de punto no
  bloqueado, pero no como autorización RECE. La evidencia productiva detallada,
  incluidos organización, puntos, conteos y numeración, permanece en el entorno
  operativo privado.
- La lista completa de puntos con sistema, domicilio y nombre fantasia no vino
  por WSFEv1; se importo desde la constancia PDF de puntos de venta.
- El WSDL productivo de WSFEv1 requirio transporte TLS con `SECLEVEL=1` por
  compatibilidad con el handshake del endpoint.
- El transporte debe configurar timeout para carga del WSDL y
  `operation_timeout` para cada operación. Las llamadas síncronas de Zeep se
  ejecutan en threads de trabajo para no bloquear el event loop. El offload no
  debe depender de keywords posteriores a AnyIO 3.6.2 mientras Starlette admita
  `anyio>=3.6.2,<5`.
- Un timeout de `FECAESolicitar` no demuestra rechazo: conservar el intento
  fiscal y reconciliar antes de cualquier reintento.
- El perfil productivo del repo es `docker-compose.prod.yml` con PostgreSQL,
  un único proceso Uvicorn y `BATCH_WORKER_ENABLED=true` mientras el worker de
  lotes siga embebido.
- Antes de mover la operación a VPS, preparar el paquete con
  `python -m app.scripts.vps_migration`: el paquete v2 exige fuente quiescent,
  manifest estricto, barrera de idempotencia y estados migrables; `preflight`
  bloquea certificados incompletos o estados no terminales/inciertos, `export`
  re-cifra claves y `import` exige PostgreSQL limpio en el head exacto.
- La contraseña usada en `ARCA_MIGRATION_TARGET_KEY_PASSWORD` durante el export
  debe coincidir con `ARCA_PRIVATE_KEY_PASSWORD` en `.env.production`.
- La migración y el ensayo local no solicitan CAE ni emiten comprobantes.
- Al 2026-05-22, FactuFlow ya fue usado en producción real. No tratar la
  producción como pendiente de primer piloto; tratarla como operación
  post-piloto que requiere backup/restauración, trazabilidad, observabilidad y
  controles fiscales antes de cada nuevo lote.

## Dato histórico útil

Los smokes históricos de homologación cubrieron emisión individual, lote y
consulta posterior. Comprobantes, puntos, CAEs, cantidades y fechas exactas
permanecen en evidencia privada y no se replican en este repositorio público.

Este documento describe el snapshot de `main` congelado para `v0.3.0`. Al
cerrarlo, la release publicada y producción eran `v0.2.2`, que no incluye
PF-19A/B/C; tag, publicación y despliegue requieren checkpoints separados.
