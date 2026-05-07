# Estado actual

Ultima actualizacion: 2026-05-05

## Objetivo activo

Dejar FactuFlow listo para una primera prueba real controlada en produccion, con homologacion estable y flujos administrativos validados desde la UI.

## Estado real del producto

- Backend FastAPI operativo con auth, empresas, clientes, puntos de venta, certificados, comprobantes, PDF, lotes y reportes.
- Frontend Vue operativo con dashboard, clientes, comprobantes, emision masiva, reportes, certificados, puntos de venta y mi empresa.
- Selector de empresa activa implementado para admins.
- Emision individual y masiva funcionando en homologacion y validadas manualmente desde la interfaz.
- PDF generado bajo demanda y revalidado manualmente en preview y descarga.
- Se corrigieron riesgos previos de salida a produccion:
  - numeracion protegida con lock local, advisory lock PostgreSQL y constraint unico
  - idempotencia atomica de lote por hash de archivo y empresa
  - validacion estricta de alicuotas IVA permitidas desde Excel
  - lotes grandes en cola persistente y reanudables por worker
  - perfiles Docker separados para desarrollo y produccion con PostgreSQL

## Lo mas importante que quedo hecho hoy

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
  - `pytest` OK
  - `ruff check` OK
  - `black --check` OK
- Frontend:
  - `npm run type-check` OK
  - `npm run build` OK
  - `npm run test:unit` OK (sin casos definidos)
  - `npm run test:e2e` OK

## Riesgos / pendientes inmediatos

- La base local `backend/data/factuflow.db` sigue siendo legacy y no esta alineada de forma limpia con Alembic.
- No existe todavia descarga masiva de PDFs en ZIP.
- Falta el tramo operativo de cierre antes de la primera emision productiva:
  - confirmar punto de venta a usar para el primer CAE real
  - definir/importar el lote chico definitivo
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
3. Verificar backup/logs antes de emitir.
4. Ejecutar una prueba controlada de bajo importe con evidencia.
