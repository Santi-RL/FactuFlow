# Estado actual

Ultima actualizacion: 2026-05-29

## Objetivo activo

Consolidar FactuFlow despues del piloto productivo real: documentacion
alineada, reglas fiscales criticas preservadas, operacion masiva controlada,
backups/restauracion y robustez de soporte antes de ampliar el uso.

## Estado real del producto

- Backend FastAPI operativo con auth, empresas, clientes, puntos de venta, certificados, comprobantes, PDF, lotes y reportes.
- Backend ya registra formatos configurables de importacion para lotes masivos, con formatos globales y particulares por emisor.
- Backend ya registra perfiles de carga masiva por emisor para precargar
  formato, punto de venta, concepto fiscal ARCA, descripcion facturada y reglas
  de fechas.
- Frontend Vue operativo con dashboard, clientes, comprobantes, emision masiva, reportes, certificados, puntos de venta y mi empresa.
- Launcher local Windows manual agregado para desarrollo/QA: `FactuFlow
  Local.vbs` inicia backend/frontend en segundo plano sin ventana de
  PowerShell, muestra estado en el tray y abre `http://localhost:8080` cuando
  el sistema queda listo.
- El uso local con launcher ya esta implementado y testeado hasta nivel
  desarrollo/QA. El siguiente hito de despliegue es instalar FactuFlow en un
  VPS con Docker produccion y PostgreSQL.
- La observabilidad operativa estandar queda definida como requisito antes de
  ampliar produccion: trazabilidad de lotes y comprobantes, estado del sistema,
  logs utiles para soporte, backup/restauracion y mensajes claros para usuarios
  no tecnicos.
- El login ya distingue servidor local no disponible de errores de credenciales
  y guia al usuario a usar click derecho en el icono del tray >
  `Reiniciar servicios`, o relanzar `FactuFlow Local.vbs` si el icono no
  aparece.
- Clawpatch backend/frontend/repo queda sin hallazgos abiertos despues del
  ciclo de reparaciones 2026-05-16/17.
- PDF de comprobantes actualizado con formato administrativo alineado a la
  ubicacion principal de la factura oficial ARCA, datos fiscales completos
  disponibles, QR ARCA testeable por payload y fechas de servicio/vencimiento
  persistidas en comprobantes nuevos.
- Emision masiva ahora puede usar plantilla oficial o formatos configurables con autodeteccion asistida.
- Emision masiva ahora puede aplicar perfiles de carga masiva visibles y
  editables antes de validar.
- Emision masiva muestra progreso real de emision para lotes chicos y grandes,
  con timer de tiempo transcurrido y estimacion restante.
- Selector de emisor activo implementado para que contadores independientes o
  estudios chicos operen varios emisores con un emisor activo explicito por vez.
- La decision de producto vigente evita una plataforma multiempresa compleja
  por ahora; el foco es reforzar que clientes, certificados, puntos de venta,
  comprobantes, lotes, PDFs, reportes, perfiles y formatos no se mezclen entre
  emisores.
- Emision individual y masiva funcionando en homologacion y validadas manualmente desde la interfaz.
- Produccion real ya fue utilizada con comprobantes autorizados y lotes
  productivos. La evidencia detallada vive en base/logs/archivos privados
  ignorados por Git y no debe copiarse a documentacion versionada.
- PDF generado bajo demanda y revalidado manualmente en preview y descarga.
- Se corrigieron riesgos previos de salida a produccion:
  - numeracion protegida con lock local, advisory lock PostgreSQL y constraint unico
  - idempotencia atomica de lote por hash de archivo, empresa y formato usado
  - validacion estricta de alicuotas IVA permitidas desde Excel
  - lotes grandes en cola persistente y reanudables por worker
  - perfiles Docker separados para desarrollo y produccion con PostgreSQL

## Lo mas importante que quedo hecho hoy

### Detalle paginado de lotes grandes 2026-05-29

- La pantalla `Emision masiva` ya no abre el lote trayendo y renderizando todos
  los grupos y filas. Ahora usa `GET /api/lotes-comprobantes/{lote_id}/resumen`
  para el resumen fiscal completo y
  `GET /api/lotes-comprobantes/{lote_id}/grupos` para una pagina de grupos.
- El resumen fiscal conserva el alcance completo del lote: totales listos para
  emitir, fechas de emision validas, puntos de venta validos y token exacto de
  confirmacion fiscal `fechas=...;puntos_venta=...`.
- La grilla de comprobantes carga 100 grupos por pagina y permite filtrar por
  estado. El Excel observado sigue siendo el camino para revisar el detalle por
  fila completo.
- Verificacion visual local con navegador integrado sobre un lote de 1432
  comprobantes: la vista inicial quedo en 100 filas renderizadas, `nodeCount`
  aproximado 2026 y `scrollHeight` aproximado 15371. Antes de este cambio la
  misma pagina tenia aproximadamente 24629 nodos y `scrollHeight` 165654.
- Verificacion tecnica: backend
  `python -m pytest backend/tests/test_lotes_comprobantes.py -q` OK
  (46 tests), `ruff check` OK, `ruff format --check` OK; frontend
  `npm run test:unit -- LotesComprobantesView`, `npm run type-check` y
  `npm run lint:check` OK. `black --check` quedo colgado localmente aun sobre
  archivos chicos; se aplico formato y se verifico con `ruff format --check`.

### Alineacion documental post-piloto 2026-05-22

- Se verifico evidencia local en modo solo lectura y se confirmo que la
  documentacion que todavia hablaba de "primera prueba real pendiente" estaba
  desactualizada.
- La operacion productiva real ya ocurrio. Los detalles privados de CUITs,
  CAEs, clientes, comprobantes, Excels y logs siguen fuera de Git.
- Se hizo un corte versionado en `CHANGELOG.md` para dejar `0.2.0-mvp` como
  linea base actual y resumir el avance historico sin sumar snapshots largos.
- Desde este punto, el foco operativo ya no es ejecutar el primer CAE real, sino
  consolidar el uso post-piloto: evidencia resumida, backups/restauracion,
  observabilidad, trazabilidad de lotes, descarga masiva de PDFs y mejoras de
  soporte administrativo.

### Launcher local Windows 2026-05-18

- Se agrego `FactuFlow Local.vbs` como acceso de doble click para iniciar el
  entorno local sin exponer ventanas tecnicas. `FactuFlow Local.cmd` queda como
  compatibilidad y delega en el mismo launcher oculto.
- Se agrego `scripts/factuflow-local-tray.ps1`, un launcher con icono en el
  tray que verifica backend, base de datos y frontend, inicia servicios faltantes
  con el flujo actual y muestra estados verde/amarillo/rojo.
- El menu del tray permite abrir FactuFlow, consultar estado del sistema,
  reiniciar servicios iniciados por el launcher, detenerlos, abrir logs y salir.
- Los logs quedan en `.tmp/local-launcher/` y no se versionan.
- Esta etapa no es un instalador, no empaqueta dependencias y no configura
  inicio automatico con Windows; sigue orientada a entorno local de desarrollo o
  QA.
- Verificacion: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File
  scripts\factuflow-local-tray.ps1 -SelfTest`, backend `pytest tests -q`,
  `ruff`, `black`; frontend `lint:check`, `type-check`, `build` y `test:unit`.

### Login con backend local no disponible 2026-05-18

- Se agrego chequeo de `GET /api/health` antes del login.
- Si el backend local no responde, la UI muestra
  `FactuFlow no está listo para iniciar sesión` y no envia credenciales.
- El mensaje indica hacer click derecho en el icono de FactuFlow junto al reloj,
  elegir `Reiniciar servicios`, esperar a que quede verde y presionar
  `Reintentar`. Si el icono no aparece, indica abrir nuevamente
  `FactuFlow Local.vbs`.
- Quedo documentado el runbook de etapas futuras en
  `docs/agents/local-launcher-runbook.md`.

### Puesta a punto Clawpatch 2026-05-16

- Se agrego estado local ignorado `.clawpatch/`, metadata minima
  `backend/pyproject.toml`, manifiesto operativo `backend/package.json` y
  scripts raiz para inicializar, mapear, consultar estado y revisar backend y
  frontend con `clawpatch@0.1.0`.
- La version actual de Clawpatch no trae mapper Python. Para que backend tenga
  entradas detectables sin tocar runtime, el manifiesto del backend expone los
  checks Python existentes contra `.venv`.
- Smoke ejecutado sin fixes: backend detecta 4 features y frontend detecta 6
  features. El estado interno queda fuera del historial Git en `.clawpatch/`.
- Ajuste posterior: se agrego una capa versionada de features manuales en
  `tools/clawpatch/` para cubrir codigo real de FactuFlow. El smoke actual con
  `npm run clawpatch:map-all` deja `repo=4`, `backend=10` y `frontend=10`
  features. El nivel `repo` cubre flujos end-to-end frontend/backend y no usa
  el mapper nativo de la raiz porque puede escanear carpetas locales ignoradas.
- Review ejecutado sobre `repo`: 4 features end-to-end revisadas, 21 findings
  abiertos, sin `fix`, sin CAE ni llamadas reales ARCA. Los reportes crudos
  quedan como evidencia local ignorada por Git porque detallan hallazgos de
  seguridad abiertos; el resumen publico debe ser sanitizado antes de subirse.
- Regresion tecnica posterior OK: backend `pytest tests -q`, `ruff`, `black`;
  frontend `lint:check`, `type-check`, `build` y `test:unit`.
- Reporte de cierre:
  `docs/project/audits/clawpatch/2026-05-16-puesta-a-punto.md`.

### Reparaciones Clawpatch 2026-05-16

- Primer ciclo cerrado: la emision individual y la emision desde lotes validan
  en `FacturacionService` que el punto de venta y el `cliente_id` opcional
  pertenezcan al emisor activo antes de solicitar CAE. Esto evita vincular
  comprobantes de un emisor con clientes o puntos de venta de otro CUIT.
- Verificacion focalizada sin llamadas ARCA reales:
  `pytest tests/test_facturacion_service.py tests/test_comprobantes_api.py -q`,
  `ruff check app/services/facturacion_service.py tests/test_facturacion_service.py`
  y `black --check app/services/facturacion_service.py tests/test_facturacion_service.py`.
- Segundo ciclo cerrado: certificados ARCA endurecidos. El upload ya no acepta
  `key_filename` con paths absolutos o traversal; los paths guardados deben
  resolver dentro de `CERTS_PATH`; las claves privadas nuevas se cifran con
  `ARCA_PRIVATE_KEY_PASSWORD` o, si no esta configurada, con `APP_SECRET_KEY`;
  los nombres de certificados/claves incluyen nonce para evitar colisiones; al
  subir una renovacion se desactivan certificados activos previos del mismo
  emisor/ambiente; y al borrar un certificado se eliminan archivos gestionados
  no compartidos.
- Se agrego migracion Alembic `a3b4c5d6e7f8` con indice parcial unico para
  permitir un solo certificado activo por emisor y ambiente.
- Verificacion focalizada sin llamadas ARCA reales:
  `pytest tests/test_certificados.py tests/test_certificados_scope.py tests/test_arca/test_arca_api.py -q`,
  `ruff check` y `black --check` sobre modulos de certificados/ARCA tocados.
- Tercer ciclo cerrado: lotes en `procesando` ya no pueden volver a
  reencolarse por API. El worker procesa lotes `en_cola` y solo retoma lotes
  `procesando` si no tuvieron actividad durante
  `BATCH_PROCESSING_STALE_MINUTES` minutos. Esto evita dobles tomas de lotes
  activos sin perder la posibilidad de recuperar procesos realmente trabados.
  La ruta `procesar_lote(..., reanudar=True)` tambien permite continuar esos
  lotes stale, que es el camino que usa el worker.
- Verificacion focalizada sin llamadas ARCA reales:
  `pytest tests/test_lotes_comprobantes.py::test_procesar_lote_background_encola_lote_chico tests/test_lotes_comprobantes.py::test_tomar_lote_para_procesamiento_es_atomico tests/test_lotes_comprobantes.py::test_procesar_background_no_reencola_lote_en_proceso tests/test_lotes_comprobantes.py::test_reanudar_lote_procesando_solo_si_esta_stale tests/test_lotes_comprobantes.py::test_procesar_lote_grande_encola_y_se_reanuda -q`,
  `ruff check` y `black --check` sobre lotes/worker.
- Cuarto ciclo cerrado: fallos posteriores a una respuesta ARCA con CAE ya no
  quedan ocultos como errores genericos ni como fallos reintentables. La
  respuesta conserva punto de venta, numero, fecha, total y CAE, marca
  `requiere_reconciliacion=true`, la API individual responde `409`, y los lotes
  pasan a estado `requiere_reconciliacion` para bloquear reintentos automaticos.
- Verificacion focalizada sin llamadas ARCA reales:
  `pytest tests/test_facturacion_service.py tests/test_comprobantes_api.py tests/test_lotes_comprobantes.py::test_procesar_lote_post_arca_requiere_reconciliacion -q`,
  `ruff check`, `black --check`, frontend `type-check` y `lint:check`.
- Quinto ciclo cerrado: Factura C queda bloqueada localmente con IVA distinto
  de 0 antes de pedir CAE. En emision individual, la UI limita las alicuotas a
  IVA 0 al elegir Factura C y normaliza items existentes; en lotes, la
  validacion rechaza grupos tipo C con IVA mayor a 0.
- Verificacion focalizada sin llamadas ARCA reales:
  `pytest tests/test_lotes_comprobantes.py::test_validar_lote_rechaza_factura_c_con_iva tests/test_facturacion_service.py::test_validar_datos_rechaza_factura_c_con_iva -q`,
  `ruff check`, `black --check`, frontend `type-check` y `lint:check`.
- Sexto ciclo cerrado: el emisor activo quedo consistente entre UI y API. El
  frontend usa `sessionStorage` como fuente por pestaña para `X-Empresa-Id` y
  conserva `localStorage` solo como preferencia inicial. El backend acepta el
  query legacy `empresa_id` solo si no contradice el header y rechaza conflictos
  explicitos. La UI dejo de mandar `empresa_id` redundante en listados y
  reportes.
- Septimo ciclo cerrado: la vista previa de nueva factura ya muestra el punto
  de venta seleccionado en lugar de usar siempre `0001`.
- Octavo ciclo cerrado: el Excel observado de lotes escapa textos que Excel
  podria interpretar como formulas, tanto desde datos originales como desde
  mensajes de resultado.
- Noveno ciclo cerrado: `Puntos de venta` consulta `GET /api/arca/status` y
  habilita `Sincronizar con ARCA` solo si existe certificado activo para el
  ambiente real configurado en backend (`ARCA_ENV`).
- Verificacion focalizada sin llamadas ARCA reales:
  `pytest tests/test_clientes.py::test_admin_puede_resolver_empresa_por_query_legacy tests/test_clientes.py::test_admin_rechaza_conflicto_header_y_query_empresa tests/test_clientes.py::test_usuario_no_admin_rechaza_empresa_query_ajena tests/test_comprobantes_api.py -q`,
  `pytest tests/test_lotes_comprobantes.py::test_archivo_observado_escapa_textos_con_formulas -q`,
  `pytest tests/test_arca/test_arca_api.py::TestArcaAPIEndpoints::test_status_informa_certificado_del_ambiente_actual -q`,
  `ruff check`, `black --check`, frontend `type-check`,
  `test:unit -- empresa-activa-storage` y `lint:check`.
- Ciclos extendidos cerrados: backend y frontend quedaron revalidados feature
  por feature con Clawpatch. Se corrigieron uploads XLSX malformados o grandes,
  confirmacion fiscal de lotes con token exacto `fechas=...;puntos_venta=...`,
  numeracion ARCA adelantada como reconciliacion, reportes IVA con signo de
  notas de credito, bootstrap concurrente, carreras async por cambio de emisor
  activo, Factura A solo con CUIT, orden estable de items, refresco post-CAE no
  bloqueante, IVA 27% en detalle de subdiario y enlaces externos ARCA con
  `noopener noreferrer`.
- QA en Chrome posterior: `Nueva factura` ya no selecciona puntos que no son
  usables por FactuFlow. El selector toma el primer punto Web Services activo,
  no bloqueado y sin baja; `/api/comprobantes/proximo-numero` devuelve 400 de
  negocio si alguien consulta un punto no usable, en lugar de filtrar como
  error interno.
- Cierre Clawpatch:
  - backend `openFindings=0`
  - frontend `openFindings=0`
  - repo `openFindings=0`
  - `clawpatch review --limit 50 --jobs 1` a nivel repo no encontro features
    pendientes ni hallazgos nuevos.

### PDF profesional y QR ARCA 2026-05-14

- Se rediseño el PDF de comprobante con una estructura mas cercana a la
  ubicacion de elementos principales de la factura oficial ARCA, sin copiar
  identidad visual ni depender de un formato ARCA editable.
- El PDF ahora organiza `ORIGINAL`, caja de letra/codigo, emisor, receptor,
  periodo, detalle, totales, CAE, vencimiento CAE, leyenda ARCA y QR en una
  hoja A4.
- Para consumidor final sin documento, el PDF no expone el `0` tecnico usado en
  WSFE/QR; muestra `Doc.: -`, consigna `Condicion frente al IVA: Consumidor
  Final` y solo deja el nombre vacio cuando la razon social tambien es generica
  (`A CONSUMIDOR FINAL`/`Consumidor Final`). Si el lote trae una razon social
  real del receptor, se muestra aunque el documento sea tecnico `0`.
- Se agrego `ingresos_brutos` al emisor para poder mostrar ese dato fiscal en
  el PDF cuando este cargado. Los emisores existentes pueden completarlo desde
  `Emisores`.
- Los comprobantes nuevos persisten `fecha_servicio_desde`,
  `fecha_servicio_hasta` y `fecha_vto_pago` para que el PDF muestre periodo
  facturado y vencimiento cuando el concepto fiscal sea servicios o ambos.
- Se agrego backfill por Alembic para comprobantes historicos emitidos por lote:
  si el comprobante no tenia fechas de servicio pero el `payload_json` del grupo
  las conservaba, se reconstruyen `fecha_servicio_desde`,
  `fecha_servicio_hasta`, `fecha_vto_pago` y `fecha_vencimiento`.
- El QR quedo separado en payload y URL testeables. La prueba decodifica el
  Base64 y verifica campos oficiales: `ver`, `fecha`, `cuit`, `ptoVta`,
  `tipoCmp`, `nroCmp`, `importe`, `moneda`, `ctz`, `tipoDocRec`,
  `nroDocRec`, `tipoCodAut` y `codAut`.
- Verificacion tecnica focalizada: `pytest tests/test_pdf_service.py
  tests/test_facturacion_service.py -q`, `ruff check app tests alembic`,
  `black --check app tests alembic` y `npm run type-check` OK.

### Formato privado Factura B IVA 21% 2026-05-11

- Se creo en la base local un formato particular de Factura B IVA 21% para un
  emisor privado.
- El formato mapea `Imp. Neto Gravado` como `item_precio_unitario` y `Imp.
  Total` solo como total informado para control de consistencia. Esto evita
  repetir el error de usar el total final como neto y volver a agregar IVA.
- El Excel privado contiene 1432 filas utiles, todas `Factura B`, fecha de
  origen `28/02/2026`, receptor sin documento ni denominacion y columna
  `Punto de Venta` vacia.
- El perfil predeterminado local del emisor privado quedo vinculado al formato,
  mantiene punto de venta fijo `5`, concepto fiscal `Servicios`, descripcion
  fija `Servicios` y reglas relativas existentes.
- QA segura sin emision real sobre copia de base local: deteccion de formato
  con confianza alta `1.0`; validacion con fecha de emision fija
  `30/04/2026`, periodo `01/04/2026 - 30/04/2026`, vencimiento `30/04/2026`
  y punto fijo `5`; resultado 1432 grupos validos, 0 con error, 0 emitidos.
- QA negativa sobre copia de base local: un formato deliberadamente incorrecto
  usando `Imp. Total` como neto dejo 1432 grupos con error por diferencia entre
  total calculado y total informado, 0 validos y 0 emitidos.
- En la pantalla de detalle del lote validado se agrego un bloque de totales
  listos para emitir: comprobantes, neto, IVA 21%, IVA 10,5% y total. El
  calculo se hace sobre grupos validados antes de presionar `Emitir
  comprobantes validos`, para comparar contra el Excel sin solicitar CAE.

### Constancias de emisores mas robustas 2026-05-10

- El parser de constancias ARCA de emisores ahora distingue formatos de
  inscripcion de persona juridica, inscripcion de persona fisica y opcion de
  Monotributo.
- La extraccion corrige cortes comunes introducidos por PDFs en nombre fiscal,
  domicilio y localidad, y evita usar lineas tecnicas como provincia.
- La provincia se valida contra un catalogo cerrado de provincias argentinas en
  backend y en la pantalla `Emisores`; ya no queda como texto libre en alta o
  edicion de emisor.

### Punto de venta en perfiles de carga masiva 2026-05-10

- Los perfiles de carga masiva ahora pueden precargar si el lote usa el punto de
  venta definido en el archivo o un punto fijo del emisor activo.
- Solo se puede guardar un punto fijo si esta cargado en `Puntos de venta` para
  ese emisor y es usable por FactuFlow: Web Services, activo, no bloqueado y sin
  fecha de baja.
- Si el emisor no tiene puntos usables cargados, la UI indica que primero deben
  completarse en `Puntos de venta`.
- En `Emision masiva`, la seleccion queda visible y editable antes de validar.
  Si se fija un punto, el backend sobrescribe el punto de venta de todas las
  filas antes de validar y guarda la politica en `metadata_json`.
  La barrera fiscal final no cambia: antes de solicitar CAE sigue apareciendo
  el modal irreversible con fecha fiscal y puntos de venta concretos.

### Sincronizacion de puntos WSFE 2026-05-10

- Se verifico un emisor privado: ARCA produccion devuelve puntos por
  `FEParamGetPtosVenta` con `Bloqueado=N` y sin fecha de baja.
- La base local los tenia creados solo con numero, sin `sistema` ni
  `es_webservice`, por lo que FactuFlow los mostraba como `Otro sistema`.
- Se ajusto `Sincronizar con ARCA` para que los puntos devueltos por WSFE se
  creen o actualicen como Web Services activos, no bloqueados y usables por
  FactuFlow.

### Progreso real de lotes con timer 2026-05-10

- `POST /api/lotes-comprobantes/{lote_id}/procesar` acepta
  `background=true`. La UI lo usa siempre para poder seguir tambien lotes
  chicos por polling.
- La confirmacion fiscal sigue siendo obligatoria: el endpoint rechaza la
  emision si falta `X-Confirmacion-Fecha-Fiscal` con el token exacto de fechas
  y puntos de venta validados.
- El procesamiento actualiza contadores del lote despues de cada grupo:
  emitidos, fallidos, validos restantes y mensaje de avance.
- La pantalla de emision masiva muestra avance real, estado `En cola`/
  `Procesando`, emitidos, fallidos, pendientes, tiempo transcurrido y estimado
  restante.
- Verificacion controlada sin emision real: se agregaron tests con
  `FacturacionService.emitir_comprobante` mockeado para lote chico background,
  contadores parciales, bloqueo sin confirmacion fiscal y toma atomica.
  Tambien se agregaron tests frontend para calculo de progreso, timer y ETA.

### Perfiles de carga masiva por emisor 2026-05-09

- Se agregaron perfiles de carga masiva por emisor activo, separados de los
  formatos de importacion. El formato interpreta columnas; el perfil precarga la
  pantalla de lotes con decisiones operativas visibles.
- Cada emisor puede tener varios perfiles de carga masiva. Si tiene uno solo,
  se aplica automaticamente en `Emision masiva`; si tiene varios, se aplica el
  predeterminado; si no hay predeterminado, no se aplica ninguno.
- `Emisores` ahora tiene pestaña `Carga masiva` para crear, editar, eliminar y
  marcar perfiles como predeterminados.
- Un perfil de carga masiva puede recordar formato de importacion opcional,
  punto de venta, concepto fiscal ARCA, descripcion facturada y reglas relativas
  de fechas como `ultimo_dia_mes_anterior`, `mes_anterior_completo`,
  `mismo_dia_emision` o `emision_mas_dias`.
- Por regla fiscal critica, el perfil de carga masiva no permite guardar
  `fecha_actual` como fecha de emision: no debe convertir la fecha del navegador
  en fecha fiscal.
- Las reglas relativas no se convierten usando la fecha del navegador al
  autoaplicar un perfil en `Emision masiva`. El usuario debe elegir una fecha
  exacta, tomarla del archivo o confirmar una base explicita antes de validar.
  El backend de lotes sigue recibiendo `archivo` o `fija` con fecha concreta, y
  guarda snapshot del perfil aplicado en `metadata_json` solo si el usuario no
  modifico la configuracion precargada antes de validar.
- No se modifico la barrera fiscal: el perfil no valida ni emite
  automaticamente, y el procesamiento de lote sigue exigiendo el modal final de
  fecha fiscal y el token exacto de `X-Confirmacion-Fecha-Fiscal`.
- QA visual local completada en `http://127.0.0.1:8080`: creacion, edicion,
  eliminacion, marcado predeterminado, autoaplicacion por emisor, cambio manual
  que anula snapshot, validacion de un Excel privado local y modal final
  `Confirmar fecha fiscal` con fecha `30/04/2026` y puntos de venta concretos.
  No se presiono la confirmacion de emision.

### Consistencia por emisor activo 2026-05-09

- Se corrigio el scoping multiemisor de Clientes: la API lista, crea, obtiene,
  actualiza y elimina clientes solo dentro del emisor activo resuelto por
  `X-Empresa-Id`; la UI recarga el listado al cambiar el selector.
- Se corrigio Comprobantes para listar contra el emisor activo y recargar al
  cambiarlo, evitando datos stale cuando un admin alterna entre CUITs.
- Se corrigieron los reportes `Ventas`, `IVA ventas` y `Ranking de clientes`:
  usan `empresaActivaId` como fuente unica y, si ya habia un reporte visible,
  lo regeneran al cambiar el emisor activo.
- Se corrigio `Nueva factura` para cargar puntos de venta, proximo numero,
  cliente y preview desde el emisor activo. Si cambia el emisor mientras se
  edita, se limpia el cliente seleccionado para evitar mezclar datos.
- QA visual con usuario local de desarrollo en `http://127.0.0.1:18082`: Dashboard,
  Clientes, Comprobantes, Emision masiva, Certificados, Puntos de venta, Nueva
  factura y los tres reportes vuelven a consultar con el `X-Empresa-Id`
  correspondiente al selector.

### Control explicito de fechas fiscales 2026-05-08

- Se detecto un riesgo critico antes de la primera prueba productiva: el backend
  usaba la fecha del dia como `CbteFch` y fecha persistida, lo que podia emitir
  comprobantes con periodo fiscal incorrecto al cargar extractos de otro mes.
- Se cambio el contrato de emision para exigir `fecha_emision` explicita; ya no
  se usa `date.today()` como fecha fiscal por defecto.
- La emision masiva ahora exige elegir antes de validar si la fecha de emision
  sale del archivo o si se fija una fecha para todo el lote.
- Para comprobantes de servicios, la pantalla tambien exige definir como se
  resuelven fecha desde, fecha hasta y vencimiento de pago: desde el archivo o
  como fechas fijas.
- La validacion de lotes marca como observados los comprobantes cuya fecha de
  emision queda fuera de la ventana ARCA antes de permitir emitir.
- La columna `Fecha` de extractos bancarios se conserva como fecha de origen y
  puede usarse como fecha de emision solo si el usuario lo confirma.
- La importacion reconoce fechas del archivo aunque Excel las entregue como
  serial numerico, caso detectado con evidencia local privada.
- Se agregaron pruebas automatizadas para impedir que un extracto con fecha fuera
  de ventana quede listo para emitir.
- Se corrigio una validacion critica de puntos de venta en emision: ARCA devuelve
  `Bloqueado=N`/`S` en `FEParamGetPtosVenta`, y FactuFlow ahora interpreta `N`
  como punto habilitado. El fallo anterior hacia que la emision rechazara puntos
  validos como `6`, `10` y `13` durante el procesamiento del lote.
- Se corrigio el armado WSFE para Factura C: ARCA rechaza el objeto `Iva` en
  comprobantes tipo C, incluso si la alicuota es 0. FactuFlow ya no envia ese
  bloque para tipos `11`, `12` y `13`, y valida que esos comprobantes no tengan
  items con IVA distinto de 0.
- Se ajusto la idempotencia de lotes para reintentos seguros: si un lote previo
  quedo `fallido` o `con_errores` y no emitio ningun comprobante, el mismo
  archivo puede volver a validarse sin borrar historial. Si el lote ya esta
  validado para emitir o emitio al menos un comprobante, el duplicado sigue
  bloqueado.
- Primera emision productiva real ejecutada: lote `11` con 20 grupos autorizados
  y CAE. Se detecto concurrencia durante el procesamiento local que genero
  comprobantes adicionales no asociados al lote, por lo que quedaron 39
  comprobantes productivos autorizados en total. Se agrego transicion atomica
  para que un lote no pueda tomarse dos veces para emision.
- Se preparo la correccion operativa de los 19 comprobantes productivos
  duplicados: FactuFlow ya soporta notas de credito/debito con comprobante
  asociado informado a WSFE como `CbtesAsoc`.
- Se genero un Excel privado local con 19 Nota de Credito C, una por cada factura
  duplicada a anular. El archivo se valido contra una copia de la base local,
  sin emitir ni registrar el lote en la base operativa: `19` grupos validos,
  `0` errores y `0` emitidos. Los importes quedan en evidencia local privada.
- El usuario proceso ese archivo privado en produccion. Verificacion posterior
  solo lectura: lote `12` quedo `completado`, `19` grupos autorizados,
  `0` fallidos y `0` con error.
- Se consultaron en ARCA produccion por `FECompConsultar` las 19 Nota de Credito
  C emitidas. Todas devolvieron `Resultado=A`, CAE coincidente, fecha
  `20260508`, importe coincidente y `CbtesAsoc` apuntando a la Factura C
  duplicada esperada.
- Incidente critico: esas 19 Nota de Credito C quedaron emitidas con fecha de
  emision `08/05/2026`. Para evitar que vuelva a ocurrir, la regla del proyecto
  queda reforzada: nunca usar la fecha del dia como default fiscal y mostrar
  siempre una confirmacion final antes de solicitar CAE:
  `Está seguro que quiere emitir comprobantes con fecha XX/XX/XX? Recuerde que luego no podrá emitir comprobantes con fecha anterior para ese mismo punto de venta.`
- La confirmacion final ya no queda solo en la UI: `POST /api/comprobantes/emitir`
  exige `confirmacion_fecha_fiscal=true` y
  `POST /api/lotes-comprobantes/{lote_id}/procesar` exige
  `X-Confirmacion-Fecha-Fiscal` con el token exacto
  `fechas=AAAA-MM-DD,...;puntos_venta=N,...`.
- Se corrigio el parser local de `FECompConsultar`: ARCA devuelve
  `CbteDesde`/`CbteHasta` en la consulta de comprobante, no `CbteNro`.
- Regla critica nueva de alineacion documental: FactuFlow no debe asumir
  productos ni servicios por defecto. Antes de emitir, el usuario debe elegir
  `Productos`, `Servicios` o `Definido por archivo`.
- Si el concepto se define por archivo, el Excel debe traer una columna valida
  con `Producto` o `Servicio` en todas las filas. Si la columna falta o algun
  valor es invalido, se informa al usuario y el lote no queda listo para emitir.
- Alineacion documental agregada: el `tipo de concepto fiscal ARCA` no es la
  descripcion facturada del item. `Productos`/`Servicios` define reglas WSFE,
  ventanas de fecha y fechas de servicio; textos como `Honorarios`,
  `Zapatillas` o `Servicio mensual` son descripcion/concepto facturado del
  item.
- Ambos datos deben quedar definidos antes de validar o emitir un lote: pueden
  venir de columnas del archivo o fijarse como valor unico para todo el lote.
  No debe haber defaults ocultos de concepto fiscal ni de descripcion de item.
- Los lotes validados antes de guardar la politica explicita de concepto quedan
  bloqueados al procesar y deben revalidarse antes de emitir.
- Los lotes validados antes de guardar la politica explicita de descripcion
  facturada tambien quedan bloqueados al procesar y deben revalidarse antes de
  emitir.
- Si la fecha tomada del archivo queda fuera de la ventana ARCA, el usuario debe
  elegir por pantalla una fecha permitida por el web service antes de emitir.

### Alineacion de formatos de importacion 2026-05-08

- Se documento la nueva capacidad de formatos de importacion configurables para
  emision masiva.
- El flujo soporta formatos globales y formatos particulares del emisor activo.
- La carga de Excel detecta encabezados y calcula candidatos. Si la coincidencia
  es de alta confianza, el formato sugerido queda preseleccionado para que el
  usuario solo lo cambie si no esta de acuerdo; si no hay sugerencia confiable,
  se exige elegir formato antes de validar.
- Si el analisis automatico de encabezados no ocurre por timing de la pantalla,
  la UI bloquea `Validar lote` y ofrece `Analizar encabezados` como reintento
  manual.
- Los mapeos soportan origen por encabezado, por columna fija o por constante.
- El lote persiste encabezados detectados, mapeo usado y version de formato para
  trazabilidad.
- El formato global inicial cubre extractos bancarios de creditos con columnas
  `Fecha`, `Créditos`, `Leyendas Adicionales1`, `Leyendas Adicionales2` y
  `Pto Vta`.
- Ese formato global usa Factura C e IVA `0`, pero no debe definir por defecto
  ni el concepto fiscal ARCA ni la descripcion facturada del item. El usuario
  debe elegir si cada dato sale del archivo o se fija para todo el lote antes de
  validar. Se valida solo para emisores Exento/Monotributo; un emisor
  Responsable Inscripto debe usar un formato particular con Factura A/B.
- Se configuro en la base local un formato particular para un emisor Responsable
  Inscripto privado: `Factura B IVA 21%`, version `5`. La muestra privada local
  se detecta con confianza alta y mapea
  `Fecha`, `Punto de Venta`, `Imp. Neto Gravado`, `Imp. Total` y
  `Nro. Doc. Receptor`. Como la muestra no trae numero de documento real, el
  receptor se trata como consumidor final sin documento cuando el importe queda
  bajo el umbral legal.
- El importador de formatos externos ahora permite mapear `item_precio_unitario`
  separado de `importe_total`. Esto permite usar neto gravado como precio del
  item y total solo como referencia para reglas de consumidor final, evitando
  recalcular IVA sobre un total ya incluido.
- Se agrego una validacion de consistencia para formatos externos: si el archivo
  trae un total informado, el total calculado por FactuFlow desde items e IVA
  debe coincidir con ese total. Si no coincide, el grupo queda con error y no se
  puede emitir. Esto bloquea el caso en que `Imp. Total` se use por error como
  neto gravado.
- Incidente con emisor Responsable Inscripto privado: se detectaron 1113
  Factura B emitidas con `Imp. Total` usado como neto y por lo tanto con 21%
  agregado de mas. Se preparo un Excel privado local
  con 1113 Nota de Credito B asociadas.
  El archivo se valido contra una copia de la base local: 1113 grupos validos,
  0 errores y 0 emitidos.
- La validacion del lote queda separada de la emision: revisar y confirmar
  `Emitir comprobantes validos` sigue siendo obligatorio antes de consumir
  numeracion fiscal.
- Quedo evidencia de QA visual local para este nuevo flujo con un extracto chico:
  deteccion del formato bancario, confirmacion obligatoria del formato,
  validacion de 3 comprobantes en puntos de venta `6`, `10` y `13`, y
  `Ya emitidos = 0`. Antes de produccion sigue faltando repetirlo con el lote
  definitivo y confirmar explicitamente la emision.

### Verificacion operativa segura 2026-05-07

- Se reviso la base local privada sin exponer claves ni
  certificados. Resultado:
  - emisor productivo privado cargado
  - certificado productivo activo para ese emisor, vencimiento `2028-05-04`
  - puntos Web Services usables `6`, `8`, `10`, `12`, `13` y `14`
  - puntos Web Services bloqueados `7` y `9`
  - lote QA privado en estado `validado`, no emitido
- Se verifico por API local, sin emitir comprobantes:
  - `POST /api/certificados/verificar-conexion/3` con `X-Empresa-Id: 2`
    devolvio `Conexion exitosa con ARCA`
  - `GET /api/arca/test-conexion` devolvio `status=ok`, ambiente
    `produccion` y servidores `OK`
  - `GET /api/arca/puntos-venta` devolvio `6`, `8`, `10`, `12`, `13` y `14`
    no bloqueados, y `7`, `9` bloqueados
  - `GET /api/arca/ultimo-comprobante/6/6` devolvio ultimo comprobante `0` y
    proximo `1` para Factura B en punto de venta `6`
- Conclusion operativa de ese momento: no faltaba configurar desde cero
  certificado productivo, autorizacion `wsfe` ni puntos de venta Web Services.
  Luego se avanzo a emision productiva real; este bloque queda como evidencia
  historica de preparacion segura previa.

### Verificacion automatizada 2026-05-07

- Backend:
  - `pytest tests -q`: 110 passed
  - `ruff check app tests`: OK
  - `black --check app tests`: OK
- Frontend:
  - `npm run lint:check`: 0 errores, 413 warnings de estilo Vue existentes
  - `npm run type-check`: OK
  - `npm run build`: OK
  - `npm run test:unit`: OK, sin archivos de test unitarios
  - Prueba visual local: OK en `http://localhost:8080/comprobantes/lotes`
    subiendo un Excel QA privado, seleccionando el formato
    global de extracto bancario y validando sin emitir
  - `npm run test:e2e`: no confiable en esta corrida; Playwright mostro la
    pantalla en blanco dentro del runner aunque `http://localhost:8080/login`
    cargo correctamente con un script Playwright directo. No usar esta corrida
    como evidencia funcional hasta corregir el setup E2E.

### Verificacion tecnica 2026-05-08 - fechas y concepto fiscal

- Backend:
  - `pytest tests -q`: 128 passed
  - `ruff check app tests`: OK
  - `black --check app tests`: OK
  - prueba real con Excel privado local: 20 filas, fecha de archivo
    `06/04/2026`; al elegir servicios el lote `id=7` queda observado con 20
    grupos con error por ventana ARCA; no se emitio ningun comprobante
  - prueba segura posterior con Excel privado local: al elegir descripcion
    desde archivo el backend rechaza la validacion porque el Excel no trae
    columna de descripcion facturada; al elegir descripcion fija de prueba
    `Honorarios`, el lote `id=8` queda con 20 grupos con error por ventana ARCA,
    0 validos, descripcion persistida `Honorarios` y 0 comprobantes emitidos
- Frontend:
  - `npm run lint:check`: 0 errores, 440 warnings de estilo Vue existentes
  - `npm run type-check`: OK
  - `npm run build`: OK
  - `npm run test:unit`: OK, sin archivos de test unitarios
  - Revision visual basica en navegador: la ruta
    `http://localhost:8080/comprobantes/lotes` carga correctamente; al subir un
    Excel privado local muestra los controles `Tipo de concepto fiscal ARCA
    obligatorio`, `Descripcion facturada obligatoria`, las opciones de
    descripcion desde archivo o fija, y la columna `Descripcion facturada` en la
    grilla previa a emision.

### Preparacion produccion 2026-05-04

- Se separo Docker local de Docker produccion.
- Se adopto PostgreSQL como base recomendada para operacion real.
- Se agregaron constraints de integridad para numeracion e idempotencia de lotes.
- Se agrego worker de lotes reanudable desde estados persistidos.
- Se endurecio la validacion de IVA en Excel.
- Se ampliaron limites default de lotes a `20000` filas y `5000` comprobantes.
- Se agrego el comando `python -m app.scripts.create_admin_user` para crear o
  promover un usuario propietario/administrador en la base configurada.
- Se ajusto la UI para hablar de `Emisor activo` / `Emisores` y se agrego
  alta de nuevos emisores desde la pantalla fiscal.
- El alta de emisores permite subir una constancia de inscripcion ARCA en PDF
  para precompletar los campos fiscales antes de guardar. Desde 2026-05-10
  tambien acepta constancias de opcion de Monotributo y constancias de
  inscripcion de persona fisica con layout distinto al societario.
- Se corrigio el listado/alta de puntos de venta para que usuarios admin operen
  solo sobre el emisor activo seleccionado.
- Se corrigio certificados para que usuarios admin solo vean, creen y verifiquen
  certificados del emisor activo seleccionado.
- El listado de certificados expone `Probar conexion` por certificado para
  validar el certificado productivo contra ARCA antes de emitir comprobantes
  reales.
- El wizard de certificados ahora agrega un paso previo a la verificacion para
  confirmar la autorizacion del servicio `wsfe` en ARCA. En produccion se hace
  desde `Administrador de Relaciones de Clave Fiscal`; sin esto ARCA devuelve
  "Computador no autorizado a acceder al servicio".
- El certificado productivo del emisor real privado quedo probado desde la UI
  con resultado `Conexion exitosa con ARCA`.
- El backend local se reinicio en `ARCA_ENV=produccion` para continuar con la
  prueba real. La sincronizacion productiva de puntos de venta devolvio `6`,
  `8`, `10`, `12`, `13` y `14` habilitados; `7` y `9` vinieron bloqueados y no
  se importaron.
- Se agrego transporte SOAP con TLS `SECLEVEL=1` para endpoints legacy de ARCA
  que en produccion pueden fallar con `DH_KEY_TOO_SMALL`.
- Se agrego importacion de constancia PDF de puntos de venta ARCA. La constancia
  privada importo los 14 puntos con sistema, domicilio y nombre
  fantasia; FactuFlow distingue usables Web Services de Factuweb, Comprobantes
  en Linea y Controlador Fiscal, e indica bloqueados.
- La emision masiva ahora toma el receptor desde el Excel sin exigir cliente
  precargado. Para consumidor final en comprobantes B/C de importe menor a
  `$10.000.000`, acepta documento y razon social vacios, normaliza a
  `A CONSUMIDOR FINAL`, tipo documento `99` y numero `0`, y no crea un cliente
  persistente.
- Los comprobantes guardan snapshot fiscal del receptor
  (`receptor_tipo_documento`, `receptor_numero_documento`,
  `receptor_razon_social`, `receptor_condicion_iva`, `receptor_domicilio`) para
  que PDFs, listados y reportes no dependan de editar un cliente luego de emitir.
- La base SQLite local privada fue ajustada manualmente por ser legacy; se dejo
  backup local ignorado por Git y `alembic_version` quedo en `e5f6a7b8c9d0`.

### QA homologacion 2026-04-10

- Se completo la QA manual de las pantallas pendientes.
- Se emitio un comprobante individual real desde la UI.
- Se emitio un lote real desde la UI.
- Se corrigieron bugs reales de integracion ARCA detectados durante la QA.
- Se reemplazaron placeholders visibles del dashboard y de `Mi Empresa`.
- Se dejaron verdes nuevamente los tests backend y frontend.

## Resultados reales de homologacion

### Smoke previo documentado (2026-03-09)

- Emision individual
  - Punto de venta: `5`
  - Tipo: `Factura B`
  - Numero: `1`
  - CAE: registrado en evidencia local privada
  - Vencimiento CAE: `2026-03-19`
- Emision masiva
  - Grupo `SMOKE-LOTE-001`
    - Numero: `2`
    - CAE: registrado en evidencia local privada
  - Grupo `SMOKE-LOTE-002`
    - Numero: `3`
    - CAE: registrado en evidencia local privada

### QA real ejecutada hoy (2026-04-10)

- Emision individual desde UI
  - Punto de venta: `5`
  - Tipo: `Factura B`
  - Numero: `4`
  - CAE: registrado en evidencia local privada
  - Vencimiento CAE: `2026-04-19`
- Emision masiva desde UI
  - Grupo `QA-LOTE-20260410-001`
    - Numero: `5`
    - CAE: registrado en evidencia local privada
  - Grupo `QA-LOTE-20260410-002`
    - Numero: `6`
    - CAE: registrado en evidencia local privada

## QA manual historica cerrada

Este bloque conserva recorridos previos a la operacion productiva real actual;
no define el punto vigente de reanudacion.

Quedo validado manualmente:

- Dashboard con metricas vivas:
  - `Total Clientes = 7`
  - `Comprobantes del Mes = 3`
  - `Ultimo Comprobante = 0005-00000006`
  - `Estado Certificado = Valido`
- Comprobantes:
  - listado con comprobantes reales
  - detalle correcto
  - `Ver PDF`
  - `Descargar PDF`
- Nueva factura:
  - preview
  - emision real con CAE
- Emision masiva:
  - descarga de plantilla
  - validacion de Excel
  - confirmacion antes de emitir
  - emision real
  - descarga de archivo observado
- Emision masiva productiva preparatoria:
  - lote QA privado validado desde API/UI para emisor real privado
  - receptor `A CONSUMIDOR FINAL`, documento `0`
  - punto de venta `6`, total estimado `$1.210,00`
  - no se emitio comprobante real; quedo listo para emitir como prueba visual
- Clientes:
  - listado correcto
  - clientes autocreados por lote visibles
- Reportes:
  - ventas por periodo
  - IVA ventas
  - ranking de clientes
- Certificados:
  - listado y vigencia correctos
- Puntos de venta:
  - listado correcto
  - sincronizacion con ARCA corregida y validada
- Mi Empresa:
  - formulario operativo
  - guardado real contra API

## Bugs resueltos en esta sesion

- Resolucion de paths legacy de certificados:
  - la base podia guardar `certs/...` y el runtime concatenaba `CERTS_PATH` de forma incorrecta
  - se corrigio para aceptar path absoluto, filename simple y valores legacy
- `GET /api/comprobantes/proximo-numero/...`:
  - fallaba en UI porque el certificado no se resolvia bien
  - impacto: bloqueaba `Nueva factura`
  - estado: corregido
- `GET /api/arca/puntos-venta`:
  - usaba el CUIT del certificado en lugar del CUIT de la empresa activa
  - impacto: `Sincronizar con ARCA` devolvia `500`
  - estado: corregido y revalidado manualmente
- Validacion de puntos de venta durante emision:
  - interpretaba `Bloqueado=N` de ARCA como valor truthy y rechazaba puntos
    validos en produccion
  - impacto: lotes con puntos `6`, `10` o `13` podian fallar al emitir aunque
    `GET /api/arca/puntos-venta` los mostrara no bloqueados
  - estado: corregido y cubierto con tests unitarios
- Sincronizacion visual de puntos Web Services:
  - `Sincronizar con ARCA` creaba puntos nuevos solo con numero, sin marcarlos
    como Web Services
  - impacto: emisores privados mostraban puntos devueltos por ARCA como
    `Otro sistema` aunque ARCA los devolviera habilitados para WSFE
  - estado: corregido en frontend; una nueva sincronizacion actualiza registros
    existentes incompletos
- Armado de IVA para Factura C:
  - el request ARCA enviaba `Iva: { AlicIva: [...] }` con alicuota 0
  - impacto: ARCA rechazaba con `[10071] Para comprobantes tipo C el objeto IVA
    no debe informarse`
  - estado: corregido y cubierto con tests unitarios
- Reintento de lotes sin CAE emitido:
  - el bloqueo por archivo duplicado tambien impedia revalidar el mismo archivo
    despues de un fallo tecnico en ARCA sin comprobantes emitidos
  - impacto: habia que limpiar historial manualmente para volver a intentar
  - estado: corregido; conserva el lote previo y libera el hash solo si no hubo
    grupos emitidos
- Concurrencia en procesamiento de lotes:
  - durante la primera prueba productiva quedaron procesos backend viejos y se
    disparo procesamiento concurrente del lote
  - impacto: se autorizaron comprobantes adicionales reales antes de que el lote
    terminara de reflejar el resumen correcto
  - estado: se agrego toma atomica de lote; si ya esta procesando o procesado,
    una segunda ejecucion queda bloqueada
- Estrategia de schema local:
  - `run-local.ps1` ahora ejecuta `alembic upgrade head` antes de levantar
    `uvicorn`
  - `backend/app/main.py` ya no ejecuta `create_all` en `development`; queda
    limitado a `test`/`testing`
  - estado: Alembic queda como camino normal de schema para arranque local y
    productivo
- Nomenclatura ARCA:
  - se corrigieron textos visibles y docstrings/comentarios conceptuales que
    todavia usaban AFIP
  - en la app actual quedan menciones solo como URLs oficiales heredadas,
    variables legacy `AFIP_*` o carpeta legacy `backend/app/afip/`
- Versionado:
  - la version de producto visible queda en `APP_VERSION` /
    `settings.app_version`: `0.2.0-mvp`
  - el frontend npm queda sincronizado a version tecnica semver `0.2.0`
  - la UI mantiene `FactuFlow v0.2.0-mvp` como version de producto
- Dashboard:
  - `Comprobantes del Mes`, `Ultimo Comprobante` y `Estado Certificado` estaban hardcodeados
  - estado: corregido
- `Mi Empresa`:
  - era una pantalla placeholder
  - estado: reemplazada por formulario operativo conectado a la API
- E2E frontend:
  - habia flakiness en Firefox por esperas de navegacion
  - estado: esa flakiness puntual fue corregida; el setup general de
    `npm run test:e2e` todavia no queda como evidencia vigente

## Verificacion automatizada vigente

- Backend:
  - `pytest tests -q` OK, 195 tests
  - `ruff check app tests` OK
  - `black --check app tests` OK
  - `alembic heads` OK, head `a3b4c5d6e7f8`
- Frontend:
  - `npm run lint:check` OK sin errores ni warnings
  - `npm run type-check` OK
  - `npm run build` OK
  - `npm run test:unit` OK, 47 tests
  - `npm run test:e2e` no queda como evidencia vigente hasta corregir el setup
    del runner; ver seccion `Verificacion automatizada 2026-05-07`

## Riesgos / pendientes inmediatos

- Revision Clawpatch 2026-05-16/17: los hallazgos reparados quedan resumidos en
  `docs/project/audits/clawpatch/2026-05-16-reparaciones.md`. Backend,
  frontend y repo quedan con `openFindings=0`.
- La base local privada sigue siendo evidencia legacy
  ajustada manualmente; para nuevas instalaciones y operacion real, el camino
  canonico de schema es Alembic.
- La documentacion anterior al 2026-05-22 mezclaba estado pre-piloto con
  evidencia productiva posterior. El corte `0.2.0-mvp` queda resumido en
  `CHANGELOG.md`; los documentos vivos son la fuente vigente.
- Para cada nueva emision productiva, seguir validando explicitamente punto de
  venta, fecha fiscal, concepto fiscal ARCA, descripcion facturada, totales y
  confirmacion irreversible antes de solicitar CAE.
- La evidencia privada de lotes productivos, CAEs, comprobantes, Excels y logs
  no debe versionarse. La documentacion publica debe registrar solo resúmenes
  operativos sanitizados.
- No existe todavia descarga masiva de PDFs en ZIP.
- Los emisores existentes deben completar `Ingresos Brutos` si quieren que ese
  dato figure informado en PDFs nuevos; mientras tanto el PDF lo muestra como
  `No informado`.
- Falta formalizar operacion productiva robusta:
  - instalacion en VPS con Docker produccion y PostgreSQL
  - decision tecnica sobre certificados ARCA: migrar/copiar los certificados
    productivos locales al VPS o generar certificados nuevos para el servidor
  - observabilidad operativa estandar segun
    `docs/agents/operational-observability.md`
  - backup/restauracion de PostgreSQL, certificados y logs
  - trazabilidad visible de lotes productivos y reintentos
  - pantalla `Estado del sistema` dentro del frontend con lenguaje simple
- Para nuevas instalaciones productivas usar `docker-compose.prod.yml`,
  PostgreSQL y `.env.production` basado en `.env.production.example`.

## Estado de salida

- Homologacion: lista y validada.
- Producto local: operativo para desarrollo/QA con launcher Windows y flujo
  tecnico alternativo.
- Despliegue: el siguiente paso es VPS con `docker-compose.prod.yml`,
  PostgreSQL, secretos productivos y estrategia definida para certificados.
- Produccion real: ya fue utilizada con certificado productivo, autorizacion
  `wsfe`, puntos Web Services y comprobantes autorizados. La siguiente etapa es
  consolidar operacion post-piloto, no ejecutar un primer CAE.

## Punto exacto para retomar

Para continuar desde el estado actual:

1. Mantener alineada la documentacion viva con el estado post-piloto productivo
   y conservar la historia como evidencia fechada.
2. Instalar FactuFlow en VPS con Docker produccion y PostgreSQL.
3. Resolver la pregunta tecnica de certificados ARCA para VPS: migrar/copiar
   certificados productivos locales existentes o generar certificados nuevos
   para el servidor.
4. Definir y probar backup/restauracion de base, certificados y logs antes de
   ampliar el uso productivo.
5. Implementar observabilidad operativa estandar: pantalla de estado del
   sistema, trazabilidad/reconciliacion de lotes, logs utiles para soporte,
   mensajes simples y runbook de diagnostico.
6. Priorizar mejoras operativas visibles restantes: descarga masiva de PDFs y
   E2E confiable.
7. Para cada nuevo lote productivo, validar formato, punto de venta, concepto
   fiscal ARCA, descripcion facturada, fechas fiscales permitidas, totales y
   confirmacion final irreversible antes de emitir.
