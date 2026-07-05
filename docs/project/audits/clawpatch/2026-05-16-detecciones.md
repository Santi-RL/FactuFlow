# Revisión de detecciones - 2026-05-16

Objetivo: dejar expuestas detecciones para reparar más adelante. No se aplicaron
fixes ni cambios de lógica.

## Contexto

- Repo revisado: `FactuFlow`
- Rama: `main`
- Estado inicial: limpio y alineado con `origin/main`
- Herramienta evaluada: Clawpatch, con la versión instalada en ese momento. No usar esa versión histórica como pin operativo actual.
- Resultado práctico de `clawpatch`: la versión actual no mapea bien este
  monorepo. Desde la raíz detecta `0` features; desde `backend/` detecta `0`
  features porque el proyecto Python no tiene `pyproject.toml`; desde
  `frontend/` detecta solo scripts/configuración, no las pantallas ni servicios
  relevantes. Por eso esta revisión queda como auditoría focalizada asistida por
  lectura de código, con la limitación de `clawpatch` registrada.

## Alcance Revisado

- Emisión individual: `backend/app/api/comprobantes.py`,
  `backend/app/services/facturacion_service.py`,
  `frontend/src/views/comprobantes/ComprobanteNuevoView.vue`
- Emisión masiva: `backend/app/api/lotes_comprobantes.py`,
  `backend/app/services/lote_comprobantes_service.py`,
  `backend/app/services/lote_worker.py`,
  `frontend/src/views/comprobantes/LotesComprobantesView.vue`,
  `frontend/src/services/lotes-comprobantes.service.ts`
- Certificados: `backend/app/api/certificados.py`
- Importación Excel: `backend/app/services/formatos_importacion_service.py`

## Detecciones

### 1. Reanudación de lotes en `procesando` no funciona

- Severidad: alta
- Categoría: concurrencia / jobs
- Archivos:
  - `backend/app/services/lote_worker.py`
  - `backend/app/services/lote_comprobantes_service.py`
- Evidencia:
  - El worker busca lotes con estado `en_cola` o `procesando`.
  - `LoteWorker.procesar_pendientes()` llama `procesar_lote(..., reanudar=True)`.
  - `procesar_lote()` permite seguir si el lote está `procesando` y
    `reanudar=True`, pero luego llama `_tomar_lote_para_procesamiento()`.
  - `_tomar_lote_para_procesamiento()` solo actualiza lotes cuyo estado esté en
    `validado` o `en_cola`; excluye `procesando`.
- Riesgo:
  - Si el backend se detiene o se reinicia después de marcar un lote como
    `procesando`, el worker lo selecciona pero no puede retomarlo. El lote puede
    quedar trabado y repetir errores en cada ciclo.
- Reparación sugerida:
  - Permitir una ruta explícita de reanudación para estado `procesando`, sin
    volver a tomar el lock como si fuera un lote nuevo, o ajustar la transición
    atómica para aceptar `procesando` solo cuando `reanudar=True`.
  - Agregar test que cree un lote en estado `procesando` con grupos pendientes y
    verifique que `procesar_lote(..., reanudar=True)` lo completa.

### 2. Un segundo POST background puede reencolar un lote ya iniciado

- Severidad: alta
- Categoría: concurrencia / emisión fiscal
- Archivos:
  - `backend/app/api/lotes_comprobantes.py`
  - `backend/app/services/lote_comprobantes_service.py`
- Evidencia:
  - `POST /api/lotes-comprobantes/{lote_id}/procesar?background=true` llama
    directamente a `encolar_lote()`.
  - `encolar_lote()` solo evita estados terminales y lotes sin grupos válidos.
    No rechaza `procesando`.
  - Si el lote ya está en proceso pero todavía quedan grupos `validado`,
    `encolar_lote()` puede volver a poner `estado="en_cola"`.
- Riesgo:
  - En el flujo más sensible del sistema, una segunda llamada desde UI, reintento
    HTTP o doble click tardío puede alterar el estado de un lote ya tomado para
    emisión. Esto reabre una zona parecida al incidente histórico de
    procesamiento concurrente.
- Reparación sugerida:
  - Hacer `encolar_lote()` idempotente y restrictivo: aceptar solo `validado`;
    devolver el lote sin modificar si está `en_cola`; rechazar `procesando` con
    mensaje claro.
  - Cubrir con test: segundo POST background contra lote `procesando` no debe
    cambiarlo a `en_cola`.

### 3. El cliente frontend de lotes siempre envía confirmación fiscal

- Severidad: media
- Categoría: barrera fiscal / diseño defensivo
- Archivo:
  - `frontend/src/services/lotes-comprobantes.service.ts`
- Evidencia:
  - `lotesComprobantesService.procesar()` hardcodea
    `X-Confirmacion-Fecha-Fiscal: "true"`.
  - La pantalla actual llama ese método desde el modal de confirmación, pero el
    servicio queda disponible para cualquier llamada futura con la confirmación
    ya activada.
- Riesgo:
  - Un componente nuevo o refactor futuro podría llamar `procesar()` sin pasar
    por el modal y aun así superar la barrera backend. La protección queda
    acoplada a la disciplina de la vista actual, no al contrato del cliente.
- Reparación sugerida:
  - Cambiar el servicio para exigir un parámetro explícito, por ejemplo
    `procesar(id, { confirmacionFechaFiscal: true })`, y no enviar el header si
    no se recibió desde el handler del modal.
  - Agregar test unitario o de componente que garantice que el header solo sale
    después de confirmar el modal.

### 4. `key_filename` permite paths no normalizados al subir certificados

- Severidad: media
- Categoría: seguridad / manejo de certificados
- Archivo:
  - `backend/app/api/certificados.py`
- Evidencia:
  - El endpoint `subir_certificado` recibe `key_filename` por formulario.
  - Construye `key_path = service.certs_path / key_filename`.
  - No valida que `key_filename` sea solo nombre de archivo ni que el path
    resuelto quede dentro de `CERTS_PATH`.
- Riesgo:
  - Un usuario autenticado podría probar rutas relativas como `../...` y obtener
    diferencias observables entre "no existe" y "existe pero no valida". Aunque
    la validación criptográfica reduce el impacto, no conviene permitir path
    traversal en código que maneja claves privadas.
- Reparación sugerida:
  - Rechazar cualquier `key_filename` que no sea basename.
  - Resolver el path absoluto y verificar que esté dentro de `service.certs_path`.
  - Idealmente aceptar solo nombres devueltos por `/api/certificados/keys`.

### 5. Subida de Excel lee el archivo completo antes de aplicar límites

- Severidad: media
- Categoría: disponibilidad / validación de entrada
- Archivos:
  - `backend/app/api/lotes_comprobantes.py`
  - `backend/app/services/lote_comprobantes_service.py`
- Evidencia:
  - `validar_archivo_lote()` hace `contenido = await archivo.read()` apenas
    valida la extensión `.xlsx`.
  - El límite de filas se aplica después, dentro del servicio, cuando el archivo
    ya fue leído y abierto con `openpyxl`.
- Riesgo:
  - Un archivo `.xlsx` muy grande o especialmente costoso puede consumir memoria
    y CPU antes de que apliquen `BATCH_MAX_ROWS` o `BATCH_MAX_GROUPS`.
- Reparación sugerida:
  - Agregar límite de tamaño antes de leer o mientras se lee por chunks.
  - Documentar una variable de entorno tipo `BATCH_MAX_UPLOAD_MB`.
  - Cubrir con test que un archivo que supera el límite se rechaza antes de
    entrar al parser.

## Notas De Seguimiento

- No se detectó en código de producción un default directo de
  `date.today()`/`datetime.today()` para `fecha_emision` o `CbteFch`.
- Sí hay usos de fechas actuales en tests y utilidades no fiscales; revisar solo
  si se quiere endurecer la suite contra regresiones temporales.
- Actualizacion posterior 2026-05-16: se agregaron scripts raiz con `--root`
  explicito, estado local ignorado en `.clawpatch/`, metadata minima
  `backend/pyproject.toml` y un manifiesto operativo `backend/package.json`.
  Smoke sin fixes: backend detecta 4 features y frontend detecta 6 features.
