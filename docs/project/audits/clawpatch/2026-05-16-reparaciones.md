# Reparaciones Clawpatch - 2026-05-16

Este archivo registra el ciclo de reparaciones manuales derivadas de
`repo-2026-05-16.md`. No se usa `clawpatch fix` automatico porque los hallazgos
tocan flujos fiscales.

## Ciclo 1 - Scoping backend de emision

- Hallazgo cubierto: `Emission accepts tenant-scoped foreign keys without
  verifying ownership`.
- Reparacion: `FacturacionService` valida que `punto_venta_id` y `cliente_id`
  opcional pertenezcan a `empresa_id` antes de pedir CAE.
- Alcance: emision individual y procesamiento por lotes, porque ambos pasan por
  el servicio de facturacion.
- Verificacion:
  - `pytest tests/test_facturacion_service.py tests/test_comprobantes_api.py -q`
  - `ruff check app/services/facturacion_service.py tests/test_facturacion_service.py`
  - `black --check app/services/facturacion_service.py tests/test_facturacion_service.py`
- Resultado: OK, sin llamadas ARCA reales.

## Ciclo 2 - Certificados ARCA

- Hallazgos cubiertos:
  - `Untrusted key_filename can escape the certificate storage directory`
  - `CSR authorization failures are converted into generic 500 responses`
  - `Uploading a renewed certificate can leave multiple active certificates`
  - `ARCA private keys are persisted unencrypted and are not removed on certificate deletion`
  - `Second-level timestamp filenames can collide`
- Reparacion: paths de certificados contenidos en `CERTS_PATH`, validacion de
  `key_filename` como basename generado para CUIT/ambiente, CSR conserva 403,
  claves nuevas cifradas, filenames con nonce, borrado de archivos gestionados
  no compartidos y renovacion con desactivacion de activos previos.
- Migracion: `a3b4c5d6e7f8_certificado_activo_unico.py` agrega indice parcial
  unico por `empresa_id`/`ambiente` cuando `activo=true`, desactivando
  duplicados previos antes de crearlo.
- Verificacion:
  - `pytest tests/test_certificados.py tests/test_certificados_scope.py tests/test_arca/test_arca_api.py -q`
  - `ruff check app/api/certificados.py app/services/certificados_service.py app/arca/crypto.py app/api/arca.py app/services/facturacion_service.py app/services/lote_comprobantes_service.py app/core/config.py tests/test_certificados.py tests/test_certificados_scope.py tests/test_arca/test_arca_api.py alembic/versions/a3b4c5d6e7f8_certificado_activo_unico.py`
  - `black --check` sobre los mismos archivos
- Resultado: OK, sin llamadas ARCA reales.

## Ciclo 3 - Estado de lotes en procesamiento

- Hallazgo cubierto: parte de `Background lote state machine mishandles
  processing lots`.
- Reparacion: `encolar_lote` ya no convierte `procesando` en `en_cola`; la API
  responde que el lote ya esta en proceso y no vuelve a iniciar el worker para
  ese pedido. El worker selecciona lotes `en_cola` y solo retoma `procesando`
  si `updated_at` supera la ventana `BATCH_PROCESSING_STALE_MINUTES`.
  `procesar_lote(..., reanudar=True)` permite continuar esos lotes stale, que
  es la ruta usada por el worker.
- Verificacion:
  - `pytest tests/test_lotes_comprobantes.py::test_procesar_lote_background_encola_lote_chico tests/test_lotes_comprobantes.py::test_tomar_lote_para_procesamiento_es_atomico tests/test_lotes_comprobantes.py::test_procesar_background_no_reencola_lote_en_proceso tests/test_lotes_comprobantes.py::test_reanudar_lote_procesando_solo_si_esta_stale tests/test_lotes_comprobantes.py::test_procesar_lote_grande_encola_y_se_reanuda -q`
  - `ruff check app/api/lotes_comprobantes.py app/services/lote_comprobantes_service.py app/services/lote_worker.py app/core/config.py tests/test_lotes_comprobantes.py`
  - `black --check` sobre los mismos archivos
- Resultado: OK, sin llamadas ARCA reales.

## Ciclo 4 - Fallos post-ARCA

- Hallazgos cubiertos:
  - `Authorized CAE can be hidden by generic persistence failures`
  - `Post-ARCA uncertainty is treated as retryable batch failure`
- Reparacion: `EmitirComprobanteResponse` incorpora
  `requiere_reconciliacion` y `categoria_error`. Si ARCA devuelve CAE y falla
  `_guardar_comprobante`, la respuesta conserva punto de venta, numero, fecha,
  total, CAE y vencimiento. La API individual devuelve `409` con ese detalle.
  En lotes, el grupo/fila/lote pasan a `requiere_reconciliacion` y el lote no
  permite reintento automatico.
- Verificacion:
  - `pytest tests/test_facturacion_service.py tests/test_comprobantes_api.py tests/test_lotes_comprobantes.py::test_procesar_lote_post_arca_requiere_reconciliacion -q`
  - `ruff check app/schemas/comprobante.py app/services/facturacion_service.py app/api/comprobantes.py app/services/lote_comprobantes_service.py tests/test_facturacion_service.py tests/test_comprobantes_api.py tests/test_lotes_comprobantes.py`
  - `black --check` sobre los mismos archivos
  - `npm run type-check`
  - `npm run lint:check`
- Resultado: OK, sin llamadas ARCA reales.

## Ciclo 5 - Factura C con IVA

- Hallazgo cubierto: `Factura C can still be prepared with VAT before ARCA
  rejects it`.
- Reparacion: la emision individual limita la seleccion de IVA a 0 al elegir
  Factura C y normaliza items existentes. La validacion de lotes rechaza
  comprobantes tipo C con items de IVA distinto de 0 antes de dejarlos listos
  para emitir.
- Verificacion:
  - `pytest tests/test_lotes_comprobantes.py::test_validar_lote_rechaza_factura_c_con_iva tests/test_facturacion_service.py::test_validar_datos_rechaza_factura_c_con_iva -q`
  - `ruff check app/services/lote_comprobantes_service.py tests/test_lotes_comprobantes.py`
  - `black --check app/services/lote_comprobantes_service.py tests/test_lotes_comprobantes.py`
  - `npm run type-check`
  - `npm run lint:check`
- Resultado: OK, sin llamadas ARCA reales.

## Ciclo 6 - Emisor activo y empresa_id

- Hallazgos cubiertos:
  - `Multi-tab frontend can send requests with a different active issuer than
    the UI shows`
  - `empresa_id query parameters are accepted but ignored`
- Reparacion: el frontend usa `sessionStorage` por pestaña para enviar
  `X-Empresa-Id` y mantiene `localStorage` solo como preferencia inicial. La UI
  dejo de mandar `empresa_id` redundante en listados y reportes. El backend
  acepta el query legacy cuando no hay conflicto, rechaza diferencias con
  `X-Empresa-Id` y bloquea usuarios comunes que intenten operar otro emisor.
- Verificacion:
  - `pytest tests/test_clientes.py::test_admin_puede_resolver_empresa_por_query_legacy tests/test_clientes.py::test_admin_rechaza_conflicto_header_y_query_empresa tests/test_clientes.py::test_usuario_no_admin_rechaza_empresa_query_ajena tests/test_comprobantes_api.py -q`
  - `npm run test:unit -- empresa-activa-storage`
  - `npm run type-check`
- Resultado: OK, sin llamadas ARCA reales.

## Ciclo 7 - Preview de punto de venta

- Hallazgo cubierto: `Invoice preview always displays point of sale 0001`.
- Reparacion: `ComprobantePreview` recibe el numero del punto de venta
  seleccionado y lo usa para formar el numero completo previo.
- Verificacion:
  - `npm run type-check`
  - `npm run lint:check`
- Resultado: OK.

## Ciclo 8 - Excel observado seguro

- Hallazgo cubierto: `Observed batch Excel can preserve formula-like user
  input`.
- Reparacion: el archivo observado escapa strings que empiezan con `=`, `+`,
  `-`, `@`, tabulacion, retorno o espacios antes de esos prefijos, tanto en
  columnas originales como en mensajes de resultado.
- Verificacion:
  - `pytest tests/test_lotes_comprobantes.py::test_archivo_observado_escapa_textos_con_formulas -q`
  - `ruff check app/services/lote_comprobantes_service.py tests/test_lotes_comprobantes.py`
  - `black --check app/services/lote_comprobantes_service.py tests/test_lotes_comprobantes.py`
- Resultado: OK, sin llamadas ARCA reales.

## Ciclo 9 - Certificado del ambiente ARCA actual

- Hallazgo cubierto: `Point-of-sale sync readiness only checks any active
  certificate`.
- Reparacion: `GET /api/arca/status` informa el `ARCA_ENV` efectivo y si el
  emisor activo tiene certificado activo para ese ambiente. La pantalla de
  puntos de venta usa ese estado para habilitar `Sincronizar con ARCA`.
- Verificacion:
  - `pytest tests/test_arca/test_arca_api.py::TestArcaAPIEndpoints::test_status_informa_certificado_del_ambiente_actual -q`
  - `ruff check app/api/arca.py tests/test_arca/test_arca_api.py`
  - `black --check app/api/arca.py tests/test_arca/test_arca_api.py`
  - `npm run type-check`
- Resultado: OK, sin llamadas ARCA reales.

## Ciclo 10 - Revalidacion extendida backend

- Hallazgos cubiertos: certificados/ARCA, facturacion fiscal, lotes, formatos,
  reportes y multiemisor/auth detectados al revisar features backend.
- Reparacion:
  - Verificacion de certificados fuerza login WSAA nuevo y rechaza archivos
    faltantes aunque exista cache.
  - Upload de certificado limpia archivos guardados si falla validacion o
    persistencia.
  - Cache WSAA en disco se escribe con permisos restrictivos cuando el sistema
    operativo lo permite.
  - Emision individual no persiste respuestas ARCA sin CAE aprobado y marca
    `requiere_reconciliacion` si ARCA esta adelantada respecto de la numeracion
    local.
  - Lotes limitan tamano de upload por `BATCH_MAX_UPLOAD_BYTES`, rechazan XLSX
    malformados, exigen token de confirmacion fiscal con fechas y puntos de
    venta concretos y reconcilian grupos cuando el comprobante autorizado ya
    fue persistido.
  - Formatos de importacion validan configuraciones antes de guardar, preservan
    indices fisicos con headers vacios y limitan upload en deteccion.
  - Reporte IVA resta notas de credito en detalle y resumen.
  - Setup/auth y creacion inicial de emisores usan lock de bootstrap; valores
    `X-Empresa-Id` no positivos se rechazan.
- Verificacion:
  - `pytest tests -q`: 194 passed.
  - `ruff check app tests`: OK.
  - `black --check app tests`: OK.
  - `alembic heads`: `a3b4c5d6e7f8 (head)`.
  - `clawpatch backend status`: `openFindings=0`.
- Resultado: OK, sin llamadas ARCA reales.

## Ciclo 11 - Frontend lotes

- Hallazgos cubiertos: deteccion de formato stale, importes con separadores
  argentinos y perfiles relativos que materializaban fecha fiscal implicita.
- Reparacion:
  - `LotesComprobantesView` ignora respuestas viejas de deteccion de formato.
  - Totales previos parsean `1.234,56`, `$ 1.234,56` y `1234,56`, y avisan si
    queda un importe ambiguo en vez de convertirlo silenciosamente a cero.
  - Perfiles con reglas relativas ya no llenan fecha fiscal sin una fecha base
    explicita; el usuario debe elegir fecha exacta o politica de archivo antes
    de validar.
- Verificacion:
  - `npm run test:unit -- src/views/comprobantes/LotesComprobantesView.spec.ts src/utils/lote-totals.spec.ts src/utils/perfiles-carga-masiva.spec.ts`
  - `npm run type-check`
  - `clawpatch revalidate --feature feat_factuflow_frontend_lotes_ui`: `open=0`.
- Resultado: OK.

## Ciclo 12 - Frontend factura individual

- Hallazgos cubiertos: proximo numero stale, orden duplicado de items,
  refresco post-emision que podia ocultar un CAE exitoso y Factura A con
  receptor no CUIT.
- Reparacion:
  - La vista previa descarta respuestas viejas de `proximo-numero`.
  - Items se reindexan despues de agregar, editar, eliminar y antes de emitir.
  - El store no convierte una emision exitosa en error si falla el refresco del
    listado posterior.
  - Factura A/nota A exige receptor CUIT; DNI/Pasaporte quedan bloqueados en la
    UI y en la validez del formulario.
- Verificacion:
  - `npm run test:unit -- src/views/comprobantes/ComprobanteNuevoView.spec.ts src/components/comprobantes/ItemsTable.spec.ts src/stores/comprobantes.spec.ts`
  - `npm run type-check`
  - `clawpatch revalidate --feature feat_factuflow_frontend_factura_individual`: `open=0`.
- Resultado: OK.

## Ciclo 13 - Frontend certificados y puntos

- Hallazgos cubiertos: portal ARCA externo con `window.opener` y cargas stale al
  cambiar emisor activo.
- Reparacion:
  - El enlace al portal externo usa `target="_blank"` con
    `rel="noopener noreferrer"`.
  - Listado de certificados, estado ARCA de puntos y store de puntos de venta
    ignoran respuestas viejas si cambia el emisor activo.
- Verificacion:
  - `npm run test:unit -- src/components/certificados/WizardStep5AutorizarServicio.spec.ts src/views/certificados/CertificadosListView.spec.ts src/stores/puntos_venta.spec.ts src/views/puntos_venta/PuntosVentaView.spec.ts`
  - `npm run type-check`
  - `clawpatch revalidate --feature feat_factuflow_frontend_certificados_puntos`: `open=0`.
- Resultado: OK.

## Ciclo 14 - Frontend dashboard y reportes

- Hallazgos cubiertos: reportes/dashboard stale al cambiar emisor activo e IVA
  27% ausente del detalle del subdiario.
- Reparacion:
  - Dashboard, Reporte de ventas, Subdiario IVA y Ranking de clientes capturan
    `empresaActivaId` y descartan respuestas viejas.
  - El store de clientes tambien ignora listados stale porque el dashboard usa
    su paginacion.
  - Subdiario IVA muestra columnas `Gravado 27%` e `IVA 27%` en el detalle.
- Verificacion:
  - `npm run test:unit -- src/views/dashboard/DashboardView.spec.ts src/views/reportes/ReporteVentasView.spec.ts src/views/reportes/ReporteIvaView.spec.ts src/views/reportes/RankingClientesView.spec.ts`
  - `npm run type-check`
  - `clawpatch revalidate --feature feat_factuflow_frontend_multiemisor_reportes`: `open=0`.
- Resultado: OK.

## Cierre

- Backend: `clawpatch status` con `openFindings=0`.
- Frontend: `clawpatch status` con `openFindings=0`.
- Repo: `clawpatch review --limit 50 --jobs 1` sin features pendientes ni
  hallazgos nuevos, y `clawpatch:repo:status` con `openFindings=0`.
- Reejecucion final posterior a la alineacion documental:
  `20260517T011908-ab6f35`, `reviewed=0`, `findings=0`.
- Validacion completa final:
  - Backend `pytest tests -q`: 194 passed.
  - Backend `ruff check app tests`: OK.
  - Backend `black --check app tests`: OK.
  - Frontend `npm run test:unit`: 41 passed.
  - Frontend `npm run type-check`: OK.
  - Frontend `npm run build`: OK.
  - Frontend `npm run lint:check`: 0 errores, 465 warnings de estilo Vue
    existentes.
