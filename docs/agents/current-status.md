# Estado actual

Ultima actualizacion: 2026-05-08

## Objetivo activo

Dejar FactuFlow listo para una primera prueba real controlada en produccion, con homologacion estable y flujos administrativos validados desde la UI.

## Estado real del producto

- Backend FastAPI operativo con auth, empresas, clientes, puntos de venta, certificados, comprobantes, PDF, lotes y reportes.
- Backend ya registra formatos configurables de importacion para lotes masivos, con formatos globales y particulares por emisor.
- Frontend Vue operativo con dashboard, clientes, comprobantes, emision masiva, reportes, certificados, puntos de venta y mi empresa.
- Emision masiva ahora puede usar plantilla oficial o formatos configurables con autodeteccion asistida.
- Selector de empresa activa implementado para admins.
- Emision individual y masiva funcionando en homologacion y validadas manualmente desde la interfaz.
- PDF generado bajo demanda y revalidado manualmente en preview y descarga.
- Se corrigieron riesgos previos de salida a produccion:
  - numeracion protegida con lock local, advisory lock PostgreSQL y constraint unico
  - idempotencia atomica de lote por hash de archivo, empresa y formato usado
  - validacion estricta de alicuotas IVA permitidas desde Excel
  - lotes grandes en cola persistente y reanudables por worker
  - perfiles Docker separados para desarrollo y produccion con PostgreSQL

## Lo mas importante que quedo hecho hoy

### Alineacion de formatos de importacion 2026-05-08

- Se documento la nueva capacidad de formatos de importacion configurables para
  emision masiva.
- El flujo soporta formatos globales y formatos particulares del emisor activo.
- La carga de Excel detecta encabezados, calcula candidatos y exige elegir o
  confirmar formato antes de validar cualquier archivo externo.
- Los mapeos soportan origen por encabezado, por columna fija o por constante.
- El lote persiste encabezados detectados, mapeo usado y version de formato para
  trazabilidad.
- El formato global inicial cubre extractos bancarios de creditos con columnas
  `Fecha`, `Créditos`, `Leyendas Adicionales1`, `Leyendas Adicionales2` y
  `Pto Vta`.
- Ese formato global usa Factura C e IVA `0`, por lo que se valida solo para
  emisores Exento/Monotributo; un emisor Responsable Inscripto debe usar un
  formato particular con Factura A/B.
- La validacion del lote queda separada de la emision: revisar y confirmar
  `Emitir comprobantes validos` sigue siendo obligatorio antes de consumir
  numeracion fiscal.
- Quedo evidencia de QA visual local para este nuevo flujo con un extracto chico:
  deteccion del formato bancario, confirmacion obligatoria del formato,
  validacion de 3 comprobantes en puntos de venta `6`, `10` y `13`, y
  `Ya emitidos = 0`. Antes de produccion sigue faltando repetirlo con el lote
  definitivo y confirmar explicitamente la emision.

### Verificacion operativa segura 2026-05-07

- Se reviso la base local `backend/data/factuflow.db` sin exponer claves ni
  certificados. Resultado:
  - emisor real `30716164175` cargado como `FUNDACION ESCUELA DE GIMNASIA FEDE
    MOLINARI`
  - certificado productivo activo para ese emisor, vencimiento `2028-05-04`
  - puntos Web Services usables `6`, `8`, `10`, `12`, `13` y `14`
  - puntos Web Services bloqueados `7` y `9`
  - lote `qa_lote_cf_sin_documento.xlsx` en estado `validado`, no emitido
- Se verifico por API local, sin emitir comprobantes:
  - `POST /api/certificados/verificar-conexion/3` con `X-Empresa-Id: 2`
    devolvio `Conexion exitosa con ARCA`
  - `GET /api/arca/test-conexion` devolvio `status=ok`, ambiente
    `produccion` y servidores `OK`
  - `GET /api/arca/puntos-venta` devolvio `6`, `8`, `10`, `12`, `13` y `14`
    no bloqueados, y `7`, `9` bloqueados
  - `GET /api/arca/ultimo-comprobante/6/6` devolvio ultimo comprobante `0` y
    proximo `1` para Factura B en punto de venta `6`
- Conclusion operativa: no falta configurar desde cero certificado productivo,
  autorizacion `wsfe` ni puntos de venta Web Services. Falta confirmar el punto
  de venta elegido, preparar el lote definitivo, verificar backup/logs y emitir
  la primera prueba real controlada.

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
    subiendo `qa_extracto_bancario_pv_6_10_13.xlsx`, seleccionando el formato
    global de extracto bancario y validando sin emitir
  - `npm run test:e2e`: no confiable en esta corrida; Playwright mostro la
    pantalla en blanco dentro del runner aunque `http://localhost:8080/login`
    cargo correctamente con un script Playwright directo. No usar esta corrida
    como evidencia funcional hasta corregir el setup E2E.

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
  para precompletar los campos fiscales antes de guardar.
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
- El certificado productivo del emisor real `FUNDACION ESCUELA DE GIMNASIA FEDE
  MOLINARI` quedo probado desde la UI con resultado `Conexion exitosa con ARCA`.
- El backend local se reinicio en `ARCA_ENV=produccion` para continuar con la
  prueba real. La sincronizacion productiva de puntos de venta devolvio `6`,
  `8`, `10`, `12`, `13` y `14` habilitados; `7` y `9` vinieron bloqueados y no
  se importaron.
- Se agrego transporte SOAP con TLS `SECLEVEL=1` para endpoints legacy de ARCA
  que en produccion pueden fallar con `DH_KEY_TOO_SMALL`.
- Se agrego importacion de constancia PDF de puntos de venta ARCA. La constancia
  del CUIT `30716164175` importo los 14 puntos con sistema, domicilio y nombre
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
- La base SQLite local fue ajustada manualmente por ser legacy; se dejo backup en
  `backend/data/factuflow.before_receptor_snapshot_20260505_053724.db` y
  `alembic_version` quedo en `e5f6a7b8c9d0`.

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
  - CAE: `86100017097127`
  - Vencimiento CAE: `2026-03-19`
- Emision masiva
  - Grupo `SMOKE-LOTE-001`
    - Numero: `2`
    - CAE: `86100017097274`
  - Grupo `SMOKE-LOTE-002`
    - Numero: `3`
    - CAE: `86100017097287`

### QA real ejecutada hoy (2026-04-10)

- Emision individual desde UI
  - Punto de venta: `5`
  - Tipo: `Factura B`
  - Numero: `4`
  - CAE: `86150042970986`
  - Vencimiento CAE: `2026-04-19`
- Emision masiva desde UI
  - Grupo `QA-LOTE-20260410-001`
    - Numero: `5`
    - CAE: `86150042971165`
  - Grupo `QA-LOTE-20260410-002`
    - Numero: `6`
    - CAE: `86150042971178`

## QA manual cerrada

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
  - lote QA `qa_lote_cf_sin_documento.xlsx` validado desde API/UI para emisor
    real
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
  - estado: corregido

## Verificacion automatizada vigente

- Backend:
  - `pytest tests -q` OK, 110 tests
  - `ruff check app tests` OK
  - `black --check app tests` OK
- Frontend:
  - `npm run lint:check` OK sin errores, con warnings de estilo Vue existentes
  - `npm run type-check` OK
  - `npm run build` OK
  - `npm run test:unit` OK, sin casos definidos
  - `npm run test:e2e` no queda como evidencia vigente hasta corregir el setup
    del runner; ver seccion `Verificacion automatizada 2026-05-07`

## Riesgos / pendientes inmediatos

- La base local `backend/data/factuflow.db` sigue siendo evidencia legacy
  ajustada manualmente; para nuevas instalaciones y operacion real, el camino
  canonico de schema es Alembic.
- El formato global de extracto bancario ya tiene QA visual local sin emision.
  Falta repetirlo con el lote definitivo antes de usarlo en produccion y falta
  QA manual de formatos particulares creados para un emisor.
- No existe todavia descarga masiva de PDFs en ZIP.
- Falta el tramo operativo de cierre antes de la primera emision productiva:
  - confirmar punto de venta a usar para el primer CAE real
  - definir/importar el lote chico definitivo, idealmente validando el formato
    de extracto bancario si ese sera el origen real
  - checklist de backup / logs / restauracion
- Para produccion usar `docker-compose.prod.yml`, PostgreSQL y `.env.production` basado en `.env.production.example`.

## Estado de salida

- Homologacion: lista y validada.
- Producto local: listo para un primer piloto controlado.
- Produccion real: certificado productivo, autorizacion `wsfe` y puntos de venta
  Web Services del emisor real quedaron verificados. Falta ejecutar la primera
  prueba controlada con lote chico.

## Punto exacto para retomar

Cuando se quiera avanzar a la primera prueba real en produccion:

1. Confirmar el punto de venta Web Services a usar en la primera prueba real.
2. Preparar un Excel chico definitivo, idealmente 10 a 20 comprobantes o menos.
3. Si el origen es bancario, repetir la validacion con el lote definitivo,
   confirmar el formato y revisar totales/puntos de venta antes de emitir.
4. Verificar backup/logs antes de emitir.
5. Ejecutar una prueba controlada de bajo importe con evidencia.
