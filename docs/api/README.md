# API REST de FactuFlow

Última actualización: 08/10/2026

Esta documentación resume el contrato real expuesto por `backend/app/main.py` y
`backend/app/api/*.py`.

## URLs

- Desarrollo local: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/api/docs`
- ReDoc: `http://localhost:8000/api/redoc`
- Todas las rutas funcionales usan prefijo `/api`. No hay versionado en la URL.

## Fechas e instantes operativos

Las fechas fiscales y de calendario usan `YYYY-MM-DD`, sin conversión de zona.
Los instantes operativos de lotes, CRUD, verificación de puntos de venta, salud
y almacenamiento se publican en ISO 8601 con zona UTC explícita (`Z`).
Por ejemplo, `2026-10-03T01:30:00Z` corresponde al `02/10/2026 22:30` argentino.
La web presenta siempre `America/Argentina/Buenos_Aires`, independientemente
de la región del equipo. Los campos históricos sin zona de esos contratos
producidos en UTC conservan esa procedencia; no se migra ni desplaza la base.
La evidencia histórica de duplicados mantiene `hora_confiable`; JSON arbitrario
y fechas sin procedencia acreditada no reciben una zona inventada. Contrato en
[instantes operativos](../agents/pf-12-15-17-tiempo-operativo.md).

## Autenticación

La API usa JWT Bearer.

`POST /api/auth/login` reserva presupuesto antes de consultar usuarios y
comprobar contraseñas. Puede responder `429` con un `detail` en español y
cabecera `Retry-After` en segundos. Esperar ese plazo antes de reintentar;
los rechazos no prolongan la ventana. Las credenciales incorrectas siguen
respondiendo `401` y las cuentas inactivas `403` cuando hay presupuesto.
Límites, origen y recuperación en el [contrato SC-08](../agents/sc-08-login-recuperacion-design.md).

Las sesiones nuevas se vinculan a la credencial verificada. Un restablecimiento
concurrente invalida el acceso con la contraseña anterior, incluso si el token
se genera después. Cuando el cambio se detecta durante el login, responde el
mismo `401` genérico. Los tokens legacy válidos conservan su compatibilidad;
alcance en [SC-11](../agents/sc-11-login-reset-design.md).

```http
POST /api/auth/login
Content-Type: application/json

{
  "email": "admin.local@example.test",
  "password": "CAMBIAR_EN_LOCAL"
}
```

Respuesta:

```json
{
  "access_token": "...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "admin.local@example.test",
    "empresa_id": null,
    "empresa_ids": [1, 2],
    "puede_crear_editar_emisores": false,
    "es_admin": true
  }
}
```

Para endpoints protegidos:

```http
Authorization: Bearer {token}
```

Para operar un emisor activo explícito, cualquier usuario autorizado agrega:

```http
X-Empresa-Id: 2
```

También se conserva el query legacy `empresa_id` para compatibilidad. Si se
envían `X-Empresa-Id` y `empresa_id` con valores distintos, la API rechaza el
pedido. `empresa_ids` informa las asignaciones explícitas actuales y
`puede_crear_editar_emisores` la capacidad delegada, pero el servidor vuelve a
consultar la base en cada autorización: no confía en el JWT ni en estos campos.
`empresa_id` se conserva temporalmente para compatibilidad y solo contiene un
valor cuando hay exactamente una asignación; nunca concede acceso.

Un administrador opera cualquier emisor. Un operador sin asignaciones puede
iniciar sesión, pero las rutas scopiadas responden `403`; con una asignación se
resuelve automáticamente y con varias debe enviar una selección explícita.

## Health

```http
GET /api/health
GET /api/health/db
GET /api/health/worker
GET /api/health/recovery
GET /
```

`GET /api/health/recovery` requiere administrador y proyecta evidencia externa
de instalación: `status=recorded|not_verified`, motivo, respaldo, propósito,
código de origen, creación y punto respaldado, componentes, integridad, ensayo,
copia externa y último cotejo. `current_coverage=unknown` siempre: ningún
resultado histórico garantiza cobertura actual. Sin evidencia utilizable
responde `200` con `not_verified`; nunca revela rutas, hashes privados, errores
crudos ni datos de emisores. Usa `Cache-Control: private, no-store`.
Contrato en [evidencia de recuperación](../setup/recovery-evidence.md).
No escribe datos ni ejecuta restauración o llamadas fiscales.

`GET /api/health/worker` requiere un usuario administrador y devuelve una
allowlist sanitizada con el estado del worker y métricas de los pools `api` y
`worker`. El contrato incluye `separation_required` y `separated`, pero no
expone el DSN, credenciales, SQL, rutas privadas ni errores internos crudos.

Con PostgreSQL, `separation_required=true`: el pool API usa por defecto y como
máximo `4` conexiones, sin overflow, y el worker usa un pool dedicado de `1`.
`DATABASE_API_POOL_SIZE` puede reducir la capacidad API dentro del rango
`1..4`; el timeout de adquisición predeterminado es `5 s` y una retención de
conexión de `10 s` genera un warning sanitizado. Con SQLite,
`separation_required=false` y ambos roles comparten el mismo engine por diseño;
`separated=false` no representa degradación en ese caso.

Las sesiones de la API adquieren conexión de forma lazy, recién al ejecutar el
primer SQL necesario —incluida la autenticación—, y no por el solo hecho de
crear la dependencia. Los timeouts del pool y las desconexiones de base se
traducen a `503` con un mensaje sanitizado y `Retry-After: 2`.

## Auth

```http
POST /api/auth/login
GET /api/auth/me
GET /api/auth/setup-status
POST /api/auth/setup
```

`GET /api/auth/setup-status` devuelve `{"setup_required": true}` solo cuando no
hay usuarios creados. `POST /api/auth/setup` crea el primer usuario
administrador propietario y queda cerrado en cuanto existe cualquier usuario.

## Usuarios

```http
GET /api/usuarios
POST /api/usuarios
PUT /api/usuarios/{usuario_id}
POST /api/usuarios/{usuario_id}/desactivar
POST /api/usuarios/{usuario_id}/reactivar
POST /api/usuarios/{usuario_id}/reset-password
```

Estos endpoints requieren un usuario con `es_admin=true`. `DELETE` físico de
usuarios no está expuesto: eliminar desde la interfaz significa desactivar
`activo=false`, conservando historial y trazabilidad. El backend impide que un
administrador desactive o degrade su propia cuenta, y también impide cambiar el
email propio desde la sesión actual porque el JWT vigente usa el email como
identificador.

Las altas y ediciones administrativas aceptan `empresa_ids: number[]` sin
duplicados y `puede_crear_editar_emisores: boolean`. Los IDs deben existir. El
campo legacy `empresa_id` se acepta únicamente si `empresa_ids` no fue enviado;
enviar ambos formatos responde `422`. Promover a administrador conserva las
asignaciones explícitas y al degradarlo vuelven a definir su alcance.

## Almacenamiento

```http
GET /api/almacenamiento/resumen
GET /api/almacenamiento/lotes-compactables
GET /api/almacenamiento/logs
GET /api/almacenamiento/temporales
GET /api/almacenamiento/certificados-huerfanos
POST /api/almacenamiento/exportaciones
GET /api/almacenamiento/exportaciones/{token}/descargar
POST /api/almacenamiento/exportaciones/{token}/confirmar-descarga
POST /api/almacenamiento/exportaciones/{token}/confirmar-liberacion
POST /api/almacenamiento/certificados-huerfanos/limpiar
```

Estos endpoints requieren `es_admin=true`. El gestor informa uso medido,
recuperable, límite configurado, disco real, categorías y desglose seguro por
emisor. No expone rutas absolutas, CUIT completo, CAEs, nombres de clientes ni
contenido privado.

`POST /api/almacenamiento/exportaciones` recibe una selección explícita:

```json
{
  "lote_ids": [12],
  "log_ids": ["factuflow.log.1"],
  "temporal_ids": ["lotes/tmp-observado.xlsx"]
}
```

La respuesta devuelve un token opaco, el nombre del ZIP y
`checksum_sha256`. Para liberar espacio, el cliente debe descargar primero
`GET /api/almacenamiento/exportaciones/{token}/descargar`, confirmar que el ZIP
llegó al cliente usando el header `X-FactuFlow-Download-Token`, y recién
después liberar:

```json
{
  "checksum_sha256": "...",
  "download_token": "..."
}
```

La confirmación de liberación usa:

```json
{
  "confirmacion": "YA_LO_DESCARGUE"
}
```

La liberación valida contra el manifest del ZIP que logs y temporales no hayan
cambiado desde el resguardo; si cambiaron, no los borra. Luego compacta lotes
cerrados seleccionados y elimina logs/temporales revalidados por el servidor.
Los certificados no se incluyen en el ZIP; la limpieza de certificados huérfanos
usa una acción separada y solo acepta archivos gestionados por FactuFlow que no
estén referenciados por la base.

## Empresas / Emisores

```http
GET /api/empresas
POST /api/empresas
POST /api/empresas/extraer-constancia
GET /api/empresas/{empresa_id}
PUT /api/empresas/{empresa_id}
DELETE /api/empresas/{empresa_id}
```

`POST /api/empresas/extraer-constancia` recibe una constancia ARCA en PDF y
devuelve datos fiscales detectados para precompletar el alta de emisor.

`GET /api/empresas` devuelve todos los emisores a administradores y solo las
asignaciones vigentes a operadores. Crear un emisor requiere `es_admin=true` o
`puede_crear_editar_emisores=true`. Si lo crea un operador, emisor, asignación
con origen `creacion_propia` y evento administrativo se confirman en una sola
transacción. Editar exige además una asignación vigente sobre ese emisor. La
creación anónima solo se admite durante el bootstrap, cuando todavía no hay
usuarios. El borrado físico queda siempre reservado a administradores.

`DELETE /api/empresas/{empresa_id}` solo se permite para emisores sin datos
operativos o fiscales asociados. Si existen comprobantes, lotes, intentos
fiscales, certificados, puntos de venta, clientes, perfiles o formatos de
importación del emisor, la API responde `409` y conserva el historial; borrar el
emisor tampoco borra cuentas de usuario.

Los emisores aceptan `ingresos_brutos` como campo opcional. Si está cargado, se
usa en el PDF de comprobantes. Cuando un emisor ya tiene datos operativos o
fiscales asociados, `PUT /api/empresas/{empresa_id}` rechaza con `409` cambios
en identidad fiscal (`razon_social`, `cuit`, `condicion_iva`,
`ingresos_brutos`, domicilio, localidad, provincia, código postal e inicio de
actividades). Los datos no fiscales, como email, teléfono y logo, pueden seguir
actualizándose.

## Clientes

```http
GET /api/clientes
POST /api/clientes
GET /api/clientes/{cliente_id}
PUT /api/clientes/{cliente_id}
DELETE /api/clientes/{cliente_id}
```

Listado:

- `page`: página, default `1`
- `per_page`: filas por página
- `search`: búsqueda por razón social o documento
- `activo`: filtro opcional

La respuesta de listado es paginada con `items`, `total`, `page`, `per_page` y
`pages`.

## Puntos de venta

```http
GET /api/puntos-venta
POST /api/puntos-venta
POST /api/puntos-venta/importar-constancia
POST /api/puntos-venta/sincronizar-arca
PUT /api/puntos-venta/{punto_venta_id}
DELETE /api/puntos-venta/{punto_venta_id}
```

`importar-constancia` y `DELETE` requieren administrador. `sincronizar-arca` y
`PUT` están disponibles para cualquier usuario autorizado del emisor activo.
Número, sistema, presencia, bloqueo, baja y demás señales técnicas no se editan
manualmente, tampoco por un administrador. El `POST` se conserva por
compatibilidad de ruta, pero responde `409`: el alta técnica debe iniciarse con
`Comprobar con ARCA`. `DELETE` no borra; deshabilita `usar_en_factuflow`.

Cada `PuntoVentaResponse` expone `revision_fiscal`, `usable_factuflow`,
`puede_intentar_emision`, `seleccionable_para_emision`,
`ultima_comprobacion_arca_en`, `usar_en_factuflow`, `domicilio_fuente`,
`nombre_fantasia_fuente`,
`comprobacion_arca_desactualizada` y el
objeto `elegibilidad_rece` con `ambiente`, `estado`, `estado_efectivo`, `fuente`,
`revision_id`, `revision`, `punto_revision_fiscal`, `verificado_en`,
`vigente_hasta` y `motivo`. `vigente_hasta` se conserva por compatibilidad y no
participa en la decisión. El servidor calcula `usable_factuflow`: exige el
filtro técnico (activo, CAE compatible, no bloqueado y sin baja), la preferencia
de uso y estado efectivo `verificado_rece` para el ambiente actual. El cliente no debe reconstruir esa
decisión desde `sistema` ni desde la marca técnica.
`seleccionable_para_emision` es el contrato estricto para selectores: exige
autoridad WSFE, estado técnico positivo, preferencia habilitada y una
comprobación con menos de 90 días. `puede_intentar_emision` se conserva por
compatibilidad, pero la UI no lo usa para ofrecer opciones.

`POST /api/puntos-venta/importar-constancia` recibe PDF de hasta `5 MB`. El form
booleano `confirmar_procedencia_produccion` continúa aceptándose por
compatibilidad, pero está deprecado y no tiene efecto. La constancia es
descriptiva: valida el CUIT cuando está presente, completa domicilio y nombre de
fantasía y conserva puntos de otros sistemas como información. No consulta
WSFE, no cambia elegibilidad, no invalida ausentes y no guarda el PDF. El parser
reconoce `PUNTO VENTA` y `P.VTA.`, con `ACTIVIDAD` opcional y encabezados
repetidos. La respuesta conserva por compatibilidad
`verificados_rece`, `pendientes_comprobacion`, `no_verificados_rece`,
`listos_para_emitir`, `no_disponibles_factuflow` y `requieren_revision`. Los
tres últimos son mutuamente excluyentes y resumen todos los puntos detectados.
También conserva
`documento_emitido_en`,
`vigente_hasta` —nulo para revisiones nuevas— y warnings sanitizados.

`POST /api/puntos-venta/sincronizar-arca` consulta
`FEParamGetPtosVenta` con las credenciales del emisor y acredita para el
ambiente configurado únicamente modalidades `CAE - …`. Crea, actualiza y marca
ausentes en una sola transacción, con una marca común `comprobado_en`. Puntos
nuevos compatibles quedan habilitados para uso por defecto; otras modalidades
quedan fuera. Una sincronización posterior conserva toda deshabilitación local.

Vacíos, duplicados, tipos ausentes, respuestas inconsistentes o timeouts
devuelven `503` y no cambian ningún punto. Después de la primera comprobación
manual, los puntos con 90 días pueden actualizarse antes de habilitar selectores
y mantienen el preflight final en individual, lote y worker. Un fallo previo no
crea operación, intento, reserva ni solicitud CAE.

## Certificados

```http
GET /api/certificados
GET /api/certificados/keys?cuit={cuit}&ambiente={homologacion|produccion}
GET /api/certificados/alertas-vencimiento
GET /api/certificados/{certificado_id}
DELETE /api/certificados/{certificado_id}
POST /api/certificados/generar-csr
POST /api/certificados/subir-certificado
POST /api/certificados/verificar-conexion/{certificado_id}
```

Flujo real:

1. `POST /api/certificados/generar-csr`
2. subir el CSR al portal ARCA correspondiente
3. autorizar el servicio `wsfe` para el CUIT representado
4. `POST /api/certificados/subir-certificado`
5. `POST /api/certificados/verificar-conexion/{certificado_id}`

`verificar-conexion` prueba WSAA/ARCA con el certificado y no emite
comprobantes ni consume numeración fiscal.

`subir-certificado` acepta `.crt`, `.cer` o `.pem` y rechaza archivos que
superen `CERTIFICATE_MAX_UPLOAD_BYTES` antes del parseo multipart y de la
persistencia. `key_filename` debe ser una clave privada administrada por
FactuFlow para el CUIT y ambiente del emisor activo.

## ARCA

La consulta de comprobante conserva números JSON en los campos de importes y
cotización y agrega detalle fiscal opcional: concepto, tipo de autorización,
rango, condición IVA, períodos, IVA, tributos y asociados. Si los datos básicos
están incompletos o inválidos responde 500, como error de consulta; nunca los
rellena con cero. El reconciliador interno conserva la autorización atribuible
y requiere revisión ante evidencia insuficiente o diferente. La recuperación
legacy no solicita CAE; contrato en
[PF-02/PF-04](../agents/pf-02-04-reconciliacion-integral-design.md).

```http
GET /api/arca/test-conexion
GET /api/arca/status
GET /api/arca/tipos-comprobante
GET /api/arca/tipos-documento
GET /api/arca/tipos-iva
GET /api/arca/tipos-concepto
GET /api/arca/tipos-monedas
GET /api/arca/cotizacion/{moneda_id}
GET /api/arca/puntos-venta
GET /api/arca/ultimo-comprobante/{punto_venta}/{tipo_cbte}
GET /api/arca/consultar-comprobante/{punto_venta}/{tipo_cbte}/{numero}
```

Endpoints seguros para verificar producción sin emitir:

- `GET /api/arca/status`
- `GET /api/arca/test-conexion`
- `GET /api/arca/puntos-venta`
- `GET /api/arca/ultimo-comprobante/{punto_venta}/{tipo_cbte}`

`POST /api/arca/solicitar-cae` es un endpoint legacy deshabilitado. Requiere
autenticación, pero responde `410 Gone` y no llama a ARCA. Para emitir se debe
usar `POST /api/comprobantes/emitir` o el flujo de lotes, que aplican
idempotencia, persistencia de intento fiscal y confirmación irreversible antes
de solicitar CAE.

## Revisión de importes P1

`POST /api/comprobantes/previsualizar` acepta el body de emisión sin exigir
`confirmacion_fecha_fiscal=true` ni `X-Idempotency-Key`. Usa los permisos y el
emisor activo de emisión, valida pertenencia de punto/cliente y reglas locales.
Responde `subtotal`, `iva_21`, `iva_10_5`, `iva_27`, `total`, `subtotales_items`,
`moneda`, `cotizacion` y `receptor` efectivo. Los importes son strings decimales;
errores de negocio usan 400 y errores de contrato 422. No consulta WSAA,
RECE, padrón o numeración ni escribe clientes, comprobantes u operaciones.
No solicita CAE ni reserva un número.

Nuevas emisiones admiten 0 %, 10,5 %, 21 % y 27 %. Tasas sin soporte requieren
corrección por ítem/fila; no se reinterpretan como cero. La emisión revalida
antes de CAE, también en worker/reintento. Lookup y replay existentes preceden
a las validaciones nuevas; snapshots históricos conservan su schema y hash.
Los resúmenes de pendientes incluyen `iva27` y suman los resultados fiscales de
cada comprobante, sin usar `total_estimado` como autoridad. Cero en A/B representa
tasa cero gravada; C conserva su regla sin IVA. Exento/no gravado/tributos siguen
fuera de la preparación actual. [Contrato P1](../agents/pf-03-04-importes-previsualizacion-design.md).

## Decimales fiscales y compatibilidad A-01

Las lecturas de comprobantes e ítems, totales de lotes y reportes representan
importes, cantidades, precios, porcentajes y cotización como strings decimales.
No convertirlos a `float`/`Number` para presentar o sumar: IDs, conteos y
paginación siguen siendo números. `GET /api/reportes/clientes` agrega
`total_general`, calculado exactamente en el servidor sobre el ranking devuelto.
La reconciliación externa acepta el total decimal sin conversión del navegador.

Los requests admiten decimales conforme al contrato vigente. La preparación
común verifica encodabilidad y orden técnico antes de reserva/CAE, sin imponer
los límites comerciales del esquema anterior. Los JSON e importes de replays
históricos conservan su forma original; los clientes deben admitir strings y
números en esas respuestas antiguas. PF-03B conserva cálculo y redondeos. A-03
define la lectura de bases y la separación nominal de monedas.

## Comprobantes

```http
GET /api/comprobantes/
GET /api/comprobantes/{comprobante_id}
POST /api/comprobantes/emitir
GET /api/comprobantes/proximo-numero/{punto_venta}/{tipo_comprobante}
```

`GET /api/comprobantes/proximo-numero/...` devuelve un diagnóstico con
`ultimo_local`, `ultimo_arca`, `proximo_local`, `proximo_arca`,
`proximo_numero`, `estado`, `emision_habilitada` y `advertencia`. Los estados
son `alineada`, `arca_adelantada` y `local_adelantada`. Una historia externa no
bloquea por sí sola; un intento propio incierto continúa devolviendo error y una
numeración local adelantada devuelve `proximo_numero=null` con emisión
deshabilitada.
`POST /api/comprobantes/emitir` emite a través del servicio de facturación y
puede consumir numeración fiscal si `ARCA_ENV=produccion`.

El vínculo administrativo `cliente_id` es independiente del snapshot receptor.
Sin ID y con `guardar_cliente=true`, una coincidencia exacta de emisor, tipo y
documento se reutiliza; sin coincidencias se crea una ficha como antes. Varias coincidencias
conservan el comprobante con vínculo vacío. No se fusionan fichas ni se altera
el receptor enviado. Un ID explícito conserva su validación previa a CAE.
Lotes, reconstrucción y registro externo comparten este
[contrato](../agents/pf-03-04-14-asociacion-cliente.md). Errores reales de base
mantienen el tratamiento de incertidumbre posterior a ARCA.

Para una operación nueva, `condicion_iva` debe ser válida y compatible con el
tipo: A (1/2/3), RI o Monotributo; B (6/7/8), Exento o CF; C (11/12/13), las
cuatro condiciones soportadas. Se aceptan sus nombres completos y aliases
inequívocos. Blanco, desconocido, RNI o incompatibilidad devuelve `400` antes
de crear operación o intento fiscal; no se infiere CF del documento 99. El
lookup de una clave existente conserva precedencia: replay terminal y
conflicto por cambio de payload mantienen su contrato. Importación, lotes y
worker validan toda nueva solicitud antes de CAE. Consultar o reconciliar una
solicitud histórica no reclasifica al receptor ni vuelve a emitirla.

Antes de crear una operación o intento nuevo y antes de `FECAESolicitar`, tanto
`proximo-numero` como la emisión exigen un contexto RECE vigente del punto para
el ambiente actual; la emisión lo persiste como snapshot durable. Si falta,
venció o cambió, responden `409` con
`categoria_error=elegibilidad_rece_no_verificada` y no solicitan CAE. Un replay
terminal durable se devuelve sin reevaluar la elegibilidad actual; una
continuación legacy, sin snapshot o desalineada queda bloqueada. En lotes, la
capa exterior puede haber autenticado WSAA o ejecutado una lectura WSFE segura
de capacidad; eso no crea una autorización ni habilita `FECAESolicitar`.

Este endpoint exige el header `X-Idempotency-Key`. El cliente debe generar una
clave nueva por confirmación fiscal final y conservarla para retries de la
misma operación. Misma clave con mismo payload devuelve la respuesta persistida
o el estado actual sin volver a llamar a ARCA; misma clave con datos distintos
devuelve `409`; clave ausente devuelve `400`.

El objeto superior del body es cerrado. Una clave no documentada devuelve
`422` con `type=extra_forbidden` antes de crear la operación idempotente,
reservar numeración o alcanzar el servicio fiscal. Esto incluye erratas de
campos con defaults como `moneda`, `cotizacion`, `guardar_cliente` y las
confirmaciones: el backend no elimina la clave ni completa silenciosamente otro
significado. Cada objeto de `items` también es cerrado: admite únicamente
`codigo`, `descripcion`, `cantidad`, `unidad`, `precio_unitario`,
`descuento_porcentaje`, `iva_porcentaje` y `orden`. No enviar `subtotal`, `id`,
`comprobante_id` ni auxiliares de interfaz.

Cantidad positiva, precio no negativo y descuento de 0 a 100 inclusive deben
ser números finitos. Un descuento omitido conserva cero; un descuento inválido
no se sustituye. Los totales deben ser calculables con la aritmética decimal
vigente. Un error devuelve `422` sin crear operaciones, intentos ni reservas.
Los detalles de validación exponen solo `type`, `loc` y `msg`, sin eco del body.
Los clientes deben asociar el error a `loc` y corregir el dato antes de emitir.

La importación aplica estas reglas a formatos oficiales y personalizados.
Rechaza constantes o defaults numéricos inválidos al consumir versiones
existentes; conserva filas inválidas como trabajo administrativo sin payload
emitible. Un total informado inválido no equivale a ausencia de total.

Si la tupla exacta está incluida en
`ARCA_PUNTOS_BLOQUEADOS_PREAUTORIZACION`, la emisión aborta localmente con
`categoria_error=punto_venta_bloqueado_preautorizacion`, número `0`, CAE nulo y
`requiere_reconciliacion=false`. No crea intento fiscal ni comprobante y no
invoca `FECAESolicitar`. La operación idempotente HTTP puede existir porque se
crea antes de entrar al núcleo. El replay de la misma clave conserva ese aborto
durable incluso si después cambia la configuración; retirar una regla no
convierte una operación ya cerrada en una emisión nueva.

Las fechas visibles que se muestran al usuario deben formatearse como `DD/MM/AAAA`. Los contratos técnicos de API pueden seguir usando `YYYY-MM-DD`, ISO datetime o `CbteFch` `YYYYMMDD` según corresponda, convirtiendo siempre en los bordes.

Una respuesta WSFE sólo puede cerrar la emisión cuando corresponde a la
solicitud. Cabecera o detalle ajenos, o resultados contradictorios, conservan
`requiere_reconciliacion`. Para contradicciones correlacionadas se publica
`categoria_error=arca_respuesta_incierta`; un CAE presente es evidencia para
verificar, no un éxito. Se conservan intento, guarda y reserva; repetir la misma
operación no vuelve a solicitar CAE. La fecha de respuesta es opcional y se
compara cuando ARCA la informa. El [contrato SC-09](../agents/sc-09-respuestas-wsfe-design.md)
delimita la semántica sin añadir campos HTTP.

El body debe incluir `fecha_emision`. FactuFlow no la completa con la fecha del
día. Para comprobantes de servicios o productos y servicios también deben
informarse `fecha_servicio_desde`, `fecha_servicio_hasta` y `fecha_vto_pago`.
El backend valida preventivamente que `fecha_emision` esté dentro de la ventana
ARCA aplicable antes de solicitar CAE.

La UI debe mostrar una confirmación final antes de invocar este endpoint en
producción: `Está seguro que quiere emitir comprobantes con fecha XX/XX/XX?
Recuerde que luego no podrá emitir comprobantes con fecha anterior para ese
mismo punto de venta.` El body debe enviar `confirmacion_fecha_fiscal=true`
después de ese modal; si no llega, la API rechaza la emisión.

Si el backend detecta un duplicado lógico probable, responde `409` con
`categoria_error=duplicado_logico`. El cliente puede volver a enviar el mismo
payload y la misma `X-Idempotency-Key` con `confirmacion_duplicado_logico=true`
después de mostrar una advertencia adicional al usuario. Esa confirmación no
forma parte del hash idempotente.

El body también debe definir explícitamente el concepto fiscal ARCA. No se debe
asumir productos ni servicios por default. Los valores operativos esperados son
productos, servicios o, en flujos masivos, definido por archivo. Este dato no es
la descripción del ítem: cada ítem debe traer su `descripcion` real, por ejemplo
`Honorarios` o `Zapatillas`, como texto facturado independiente del concepto
fiscal ARCA.

## Plantillas / Formatos De Importación

```http
GET /api/formatos-importacion
POST /api/formatos-importacion
GET /api/formatos-importacion/catalogo-campos
POST /api/formatos-importacion/analizar-excel
POST /api/formatos-importacion/compatibilidad
POST /api/formatos-importacion/detectar
GET /api/formatos-importacion/{formato_id}
PUT /api/formatos-importacion/{formato_id}
DELETE /api/formatos-importacion/{formato_id}
POST /api/formatos-importacion/{formato_id}/clonar
GET /api/formatos-importacion/{formato_id}/descargar
```

La UI habla de `Plantillas`. Internamente siguen siendo
`formatos_importacion` versionados para no duplicar dominio ni romper lotes
existentes. Todos respetan el emisor activo resuelto por `X-Empresa-Id`, por el
query legacy `empresa_id` o por la preferencia del usuario.

`GET /api/formatos-importacion` lista plantillas globales y plantillas
particulares del emisor activo. Cada una expone su `version_vigente`.

`POST /api/formatos-importacion` crea una plantilla. Los usuarios activos pueden
crear plantillas con `alcance=emisor`; `alcance=global` queda reservado a
administradores porque afecta a todos los emisores. Las plantillas internas del
sistema se marcan en `configuracion_json.plantilla_sistema_protegida=true`: se
pueden clonar, pero no editar ni desactivar directamente.

`PUT /api/formatos-importacion/{formato_id}` actualiza datos y, si cambia
`configuracion_json`, reemplaza la versión vigente por una versión nueva. No
borra versiones históricas usadas por lotes. Solo administradores pueden editar
plantillas globales o promover una plantilla de emisor a global.

`DELETE /api/formatos-importacion/{formato_id}` es soft-delete:
`activo=false`.

`POST /api/formatos-importacion/{formato_id}/clonar` crea una copia editable y
quita la marca protegida si venía de una plantilla del sistema.

`GET /api/formatos-importacion/{formato_id}/descargar` genera un `.xlsx` bajo
demanda con hoja `Comprobantes`, hoja `Instrucciones` y hoja oculta
`_factuflow` con metadatos no fiscales. La validación backend no confía en esos
metadatos para emitir.

`GET /api/formatos-importacion/catalogo-campos` devuelve los campos FactuFlow
disponibles para el constructor visual, agrupados por emisor, comprobante,
receptor, fechas, ítems, totales y comprobantes asociados.

Ejemplo mínimo de configuración:

```json
{
  "nombre": "Banco X - creditos",
  "descripcion": "Extracto mensual del banco X",
  "alcance": "emisor",
  "configuracion_json": {
    "tipo": "extracto_bancario_creditos",
    "header_row": 1,
    "modo_agrupacion": "fila",
    "plantilla": {
      "nombre_publico": "Banco X - créditos",
      "columnas": [
        {
          "campo_destino": "importe_total",
          "etiqueta": "Créditos",
          "origen": "header",
          "transformacion": "decimal",
          "requerido": true,
          "ejemplo": "10000.00"
        }
      ]
    },
    "campos": {
      "importe_total": {
        "origen": "header",
        "encabezados": ["Créditos", "Creditos"],
        "transformacion": "decimal",
        "requerido": true
      },
      "punto_venta_numero": {
        "origen": "columna",
        "letra_columna": "E",
        "transformacion": "entero",
        "requerido": true
      },
      "tipo_comprobante": {
        "origen": "constante",
        "valor": 11
      }
    }
  }
}
```

Origenes soportados en `campos`:

- `header`: busca encabezados o alias normalizados.
- `columna`: usa `letra_columna` o `indice_columna`.
- `constante`: usa `valor` para completar siempre el mismo dato.
- `empresa`: toma datos del emisor activo solo cuando el campo tiene resolvedor
  implementado; en esta versión se limita a `empresa_cuit`.

`POST /api/formatos-importacion/analizar-excel` recibe `multipart/form-data`
con `archivo` (`.xlsx`) y devuelve hoja, fila de encabezado y columnas
detectadas. Sirve para iniciar el constructor visual desde un Excel de ejemplo.

`POST /api/formatos-importacion/compatibilidad` recibe:

```json
{
  "configuracion_json": {},
  "perfil_configuracion_json": {}
}
```

Devuelve `estado` (`compatible`, `advertencia` o `incompatible`) y mensajes
separados en `faltantes`, `omitibles`, `advertencias` y `conflictos`. Cruza la
plantilla con el perfil y el emisor activo para detectar columnas faltantes,
datos omitibles porque el perfil fija valores, conflictos donde el perfil exige
datos desde archivo y la plantilla no los trae, incompatibilidades de
Responsable Inscripto/Monotributo/Exento con tipos A/B/C, productos/servicios y
notas de crédito/débito sin comprobante asociado.

`POST /api/formatos-importacion/detectar` recibe `multipart/form-data` con
`archivo` (`.xlsx`). El backend rechaza archivos que superen
`BATCH_MAX_UPLOAD_BYTES` o que no puedan abrirse como XLSX válido antes de
intentar detectar encabezados. Si el archivo es válido, devuelve:

```json
{
  "headers_detectados": [
    "Fecha",
    "Créditos",
    "Leyendas Adicionales1",
    "Leyendas Adicionales2",
    "Pto Vta"
  ],
  "candidatos": [
    {
      "formato_id": 1,
      "formato_version_id": 1,
      "nombre": "Extracto bancario - creditos IVA exento",
      "alcance": "global",
      "version": 1,
      "score": 1.0,
      "confianza": "alta",
      "columnas_detectadas": [
        "Fecha",
        "Créditos",
        "Leyendas Adicionales1",
        "Leyendas Adicionales2",
        "Pto Vta"
      ],
      "columnas_faltantes": [],
      "mensajes": ["Coincide con las columnas requeridas."]
    }
  ],
  "formato_sugerido_version_id": 1,
  "requiere_confirmacion": true
}
```

El cliente debe confirmar el formato antes de validar cualquier archivo externo.
La deteccion automática es una sugerencia: no crea lotes ni consume numeración.

La importación conserva tipo, número y nombre del receptor, incluidos CF con
CUIT/CUIL/DNI. `cliente_condicion_iva` debe mapear una columna o constante
explícita; un documento informado exige `cliente_tipo_documento`. No se infiere
CUIT por longitud ni se sustituye una celda fiscal inválida o ausente por un
default. Las contradicciones de columnas fiscales reconocidas se informan con
fila y campo antes de emitir. Un formato antiguo ambiguo requiere una versión
corregida; un formato protegido se clona. No se migran lotes, snapshots ni hashes
existentes. La identificación obligatoria se evalúa sobre el total del grupo.

Formato global inicial:

- Nombre: `Extracto bancario - creditos IVA exento`
- Columnas esperadas: `Fecha`, `Créditos`/`Creditos`,
  `Leyendas Adicionales1`, `Leyendas Adicionales2`, `Pto Vta`
- Requeridas: `Créditos`/`Creditos` y `Pto Vta`
- Cada fila genera un comprobante con Factura C (`tipo_comprobante=11`) e IVA
  `0`, y cliente no persistente. El formato no debe definir por defecto ni el
  concepto fiscal ARCA ni la descripción facturada del ítem: el usuario debe
  elegir productos, servicios o archivo para el dato fiscal, y archivo o valor
  fijo para el texto del ítem antes de validar.
- Si el extracto aporta documento, clonar el formato protegido y configurar
  `cliente_tipo_documento` desde una columna o constante explícita.
- Este formato global está pensado para emisores Exento o Monotributo. Si el
  emisor activo es Responsable Inscripto, la validación observa el lote para
  evitar emitir Factura C incorrectamente.

## Lotes De Comprobantes

```http
GET /api/lotes-comprobantes
GET /api/lotes-comprobantes/plantilla
POST /api/lotes-comprobantes/validar
POST /api/lotes-comprobantes/{lote_id}/procesar
POST /api/lotes-comprobantes/{lote_id}/reintentar-fallidos
GET /api/lotes-comprobantes/{lote_id}/seguimiento
GET /api/lotes-comprobantes/{lote_id}/resumen
GET /api/lotes-comprobantes/{lote_id}/grupos
GET /api/lotes-comprobantes/{lote_id}/coincidencias
GET /api/lotes-comprobantes/{lote_id}
GET /api/lotes-comprobantes/{lote_id}/resultados
GET /api/lotes-comprobantes/{lote_id}/archivo-observado
```

El flujo correcto es validar primero el Excel y procesar solo cuando el usuario
confirma. Lotes grandes pueden quedar en cola y continuar por worker. La UI usa
`POST /api/lotes-comprobantes/{lote_id}/procesar?background=true` también para
lotes chicos, para mostrar progreso real por polling.

Para el ciclo de polling de un lote activo, usar
`GET /api/lotes-comprobantes/{lote_id}/seguimiento`. Es una allowlist mínima:
devuelve identidad y estado operativo, modo de procesamiento, contadores,
mensaje resumido, timestamps y `operacion_progreso` opcional para el reintento
background (identificador, seleccionados, autorizados, fallidos, pendientes e
inciertos); no incluye filas, grupos, datos fiscales del
receptor ni el contrato de confirmación. Respeta el emisor activo igual que el
resto de los endpoints de lotes.

La UI mantiene una sola solicitud de seguimiento en vuelo. Consulta cada `3 s`
durante los primeros `30 s`, cada `5 s` hasta los `2 min` y cada `10 s` desde
entonces. Ante errores temporales aplica backoff exponencial hasta un máximo de
`15 s` y vuelve al intervalo base después de una respuesta satisfactoria.

Para abrir el lote o hacer el refresco final, usar
`GET /api/lotes-comprobantes/{lote_id}/resumen`; para el detalle paginado, usar
`GET /api/lotes-comprobantes/{lote_id}/grupos`. El resumen devuelve contadores,
totales listos para emitir, fechas/puntos validados y el token exacto de
confirmación fiscal para el lote completo. El endpoint de grupos acepta `page`,
`per_page` (máximo 200) y `estado` opcional, y devuelve la página con `items`,
`total`, `total_pages`, `page` y `per_page`.

`GET /api/lotes-comprobantes/{lote_id}` y `/resultados` conservan el contrato
legacy de detalle completo con `grupos` y `filas`. No deben usarse para abrir
lotes grandes en la UI porque pueden traer miles de registros.

`POST /api/lotes-comprobantes/validar` recibe `multipart/form-data`:

- `archivo`: Excel `.xlsx`.
  El backend rechaza archivos que superen `BATCH_MAX_UPLOAD_BYTES` o que no
  puedan abrirse como XLSX válido.
- `formato_version_id`: opcional. Si no se envía y el archivo coincide con la
  plantilla oficial, se usa la plantilla FactuFlow. Para archivos externos,
  enviar la versión confirmada por `POST /api/formatos-importacion/detectar`.
- `perfil_carga_masiva_id`: opcional. Si se envía, la validación guarda un
  snapshot del perfil de carga masiva aplicado. La UI debe omitirlo si el
  usuario modifica la configuración precargada antes de validar. El perfil no
  reemplaza las políticas fiscales del form; esas políticas deben llegar ya
  resueltas y visibles para el usuario.
- `punto_venta_modo`: opcional, default `archivo`. Valores: `archivo` o
  `fijo`. Si es `archivo`, se usa el punto de venta mapeado desde el Excel. Si
  es `fijo`, la validación sobrescribe el punto de venta de todas las filas con
  `punto_venta_numero`.
- `punto_venta_numero`: requerido cuando `punto_venta_modo=fijo`. Debe existir
  para el emisor activo y tener `usable_factuflow=true`, incluido estado efectivo
  `verificado_rece`. Si no está cargado o no es elegible, la API rechaza la
  validación. El mismo control se aplica por grupo cuando el número viene del
  archivo y el lote persiste el snapshot RECE usado.
- `fecha_emision_modo`: obligatorio. Valores: `archivo` o `fija`.
- `fecha_emision_fija`: obligatorio solo si `fecha_emision_modo=fija`.
- `concepto_modo`: obligatorio. Valores: `productos`, `servicios` o `archivo`.
- Si `concepto_modo=archivo`, el formato confirmado debe mapear una columna del
  Excel con `Producto` o `Servicio` en todas las filas. No se envia un nombre de
  columna aparte en el form; se toma del mapeo del formato/plantilla.
- `item_descripcion_modo`: requerido por contrato operativo para lotes
  externos. Valores esperados: `archivo` o `fija`.
- `item_descripcion_fija`: requerido cuando `item_descripcion_modo=fija`.
- Si `item_descripcion_modo=archivo`, el formato/plantilla debe mapear una
  columna con la descripción/concepto facturado del ítem. Este texto es
  independiente de `concepto_modo`: `Productos` o `Servicios` no son una
  descripción facturable suficiente.
- `fecha_servicio_desde_modo`, `fecha_servicio_hasta_modo` y
  `fecha_vto_pago_modo`: valores `archivo` o `fija` para comprobantes de
  servicios.
- `fecha_servicio_desde_fija`, `fecha_servicio_hasta_fija` y
  `fecha_vto_pago_fija`: obligatorias cuando el modo correspondiente es `fija`.

La validación persiste el lote, encabezados detectados, mapeo usado y versión de
formato. No emite comprobantes. La emisión ocurre solo con
`POST /api/lotes-comprobantes/{lote_id}/procesar`.

`POST /api/lotes-comprobantes/{lote_id}/procesar` acepta query param opcional:

- `background=true`: deja el lote en cola para procesamiento por worker aunque
  sea un lote chico. La respuesta devuelve `en_progreso=true`, estado `en_cola`
  y el cliente debe consultar
  `GET /api/lotes-comprobantes/{lote_id}/seguimiento` para actualizar progreso,
  contadores, `started_at`, `finished_at` y `mensaje_resumen` sin cargar el
  detalle completo.
- sin `background=true`: conserva compatibilidad con clientes existentes; lotes
  chicos se procesan en la misma request y lotes grandes se encolan según
  `BATCH_SYNC_LIMIT`.

Para cada sublote homogéneo por emisor, punto de venta y tipo, el procesamiento
revalida el snapshot RECE antes de la operación y nuevamente bajo guarda antes
de ARCA. Si falla una preparación o reserva local antes de `FECAESolicitar`, la
transacción completa se revierte: quedan cero guardas, intentos y reservas
nuevos, y cero `FECAESolicitar`. WSAA y lecturas seguras como
`FECompTotXRequest` o `FECompUltimoAutorizado` pueden haber ocurrido antes; no
debe describirse ese rollback como “cero contacto con ARCA”.

Cuando el batch ARCA está habilitado, el flujo exterior de `procesar_lote` y el
worker puede autenticar WSAA, construir WSFE y consultar de forma segura
`FECompTotXRequest` antes de formar los sublotes. Esa lectura solo determina la
capacidad del request: no inicia `FaseSolicitudArca`, no autoriza comprobantes
y no sustituye PF-19B. Para un contexto RECE inválido, el núcleo posterior
mantiene cero `FECAESolicitar`, CAE, intentos fiscales y comprobantes nuevos.

Si el pedido requiere procesamiento en segundo plano y el worker no está
disponible, la API responde `503` con
`categoria_error=worker_lotes_no_disponible`. Esa comprobación ocurre antes
de crear la operación idempotente o cambiar el lote a `en_cola`; no se
solicita CAE y el cliente puede volver a intentar con la misma clave cuando el
servicio esté disponible.

Este endpoint exige `X-Idempotency-Key`. La clave cubre lote, modo background y
confirmación fiscal; debe mantenerse para retries de la misma operación. Si el
lote requiere una excepción por coincidencias, la API responde `409` con
`categoria_error=duplicado_logico_lote`, `control_duplicados` y `aceptacion_id`.
El control versionado `duplicados_lotes/v2` distingue coincidencias internas por
receptor, contenido completo de otro lote, coincidencias parciales identificadas
y antecedentes individuales cubiertos por la protección vigente. Las ventas
anónimas que sólo repiten fecha e importe dentro del lote no generan un aviso
interno. La coincidencia histórica completa compara contenido y multiplicidad;
archivo, cantidad e importe total no bastan por sí solos.

El resumen anticipa evidencia, cobertura histórica y cantidades/importes, pero
no concede una aceptación. El cliente abre el diálogo accionable con el `409`
autoritativo, destaca «Volver a revisar» y sólo habilita la excepción tras el
checkbox específico. Para continuar reenvía la misma clave y
`X-Confirmacion-Duplicado-Logico: <aceptacion_id>`, junto con la confirmación
fiscal válida para ese material. El ID es opaco, pertenece a esa operación y
evidencia y no admite `true`. No caduca sólo por tiempo: la misma evidencia
reexpide el mismo ID; una modificación relevante lo invalida y exige revisar el
control actualizado antes de emitir. Los campos planos legacy permanecen como
proyección de compatibilidad; no habilitan un bypass del control v2.

`GET /api/lotes-comprobantes/{lote_id}/coincidencias` exige `evidencia_id` y
acepta `page>=1`, `per_page=50` por defecto y máximo 100. Devuelve `items`,
`page`, `per_page`, `total` y `total_pages`, conservando la selección del control,
también para un reintento parcial. Si la evidencia cambió, responde `409` con el
control actual; el cliente limpia la aceptación y el detalle anterior. El
detalle distingue origen lote/individual y coincidencia interna, sin inventar
referencias históricas. `comprobante_actual_ref` identifica el comprobante
actual mediante su referencia del archivo. Los resúmenes desglosan importes por
moneda, sin conversión implícita; el total escalar es nulo si mezcla monedas o
incluye componentes sin moneda acreditada. Estos últimos se cuentan por
separado. Los importes individuales son strings decimales; los actores e
instantes no acreditables son nulos y se presentan como desconocidos. No se
devuelven CAEs, documentos completos ni correos en esta consulta.

Una operación ajena coincidente reservada, activa o incierta responde `409` con
`categoria_error=duplicado_operacion_en_curso`, referencia consultable y
`aceptacion_habilitada=false`: no ofrece excepción. La reserva y la aceptación
se revalidan antes de la emisión; no sustituyen idempotencia, restricciones de
la misma importación, confirmación fiscal ni reconciliación. La selección
original y la evidencia mínima sobreviven a resultados parciales y compactación.
Los remanentes v1 no terminales con aceptación histórica no comprobable y
coincidencias actuales responden `409` con
`categoria_error=duplicado_legacy_no_reconfirmable`. No admiten una nueva
confirmación ni se habilitan cambiando la clave idempotente; conservan su
historia. El replay terminal y la reconciliación de resultados inciertos
mantienen sus contratos. Las pendientes v1 nunca aceptadas se evalúan con v2.
El contrato completo y la transición histórica se mantienen en el
[diseño PF-13/PF-17](../agents/pf-13-duplicados-lotes-design.md).

`POST /api/lotes-comprobantes/{lote_id}/reintentar-fallidos` comparte el mismo
contrato idempotente: exige `X-Idempotency-Key`,
`X-Confirmacion-Fecha-Fiscal` y, si corresponde,
`X-Confirmacion-Duplicado-Logico`. El body puede incluir `grupo_ids` para
acotar el reintento. Un grupo tomado para reintento que queda incierto debe
tratarse como reconciliable, no como fallido reintentable.

La pantalla envía `?background=true`: el servidor publica cola y recibo durable
junto con la selección en una transacción y retorna sin esperar la emisión. El
worker usa bloques compatibles y las mismas guardas del camino masivo. La misma
clave devuelve el estado existente sin otro envío; un worker deshabilitado impide
aceptar un trabajo nuevo. El progreso excluye autorizados previos y fallidos no
seleccionados; el resumen conserva esos contadores en
`metadata_json.operacion_progreso`, y seguimiento los proyecta explícitamente.
Los fallos verificables previos a CAE cierran pendientes propios con motivo durable;
las reservas históricas se liberan sólo con prueba de propietario terminal y
sin intentos ni guardas activos o inciertos. No se libera numeración fiscal.

Sin `background=true`, el contrato síncrono anterior reutiliza el núcleo
individual y admite `arca_adelantada`
con el mismo segundo preflight. PF-02B.2 cerró sus transiciones de grupo y
fallos intermedios: cada grupo se reclama mediante CAS antes de emitir; un
bloqueo propio, una numeración local adelantada, un cambio o error del segundo
preflight y cualquier incertidumbre post-ARCA detienen la selección. Solo un
rechazo ARCA explícito permite continuar con el grupo siguiente. Una respuesta
ambigua o una falla local posterior a una autorización conocida deja
grupo/lote en `requiere_reconciliacion`, conserva la evidencia fiscal y nunca
vuelve el grupo a `fallido`.

Cuando `FECAESolicitar` devuelve un error global estructurado, la API solo
publica `arca_rechazo_global_excluyente` para el entero exacto `10005` con
cabecera `R` correlacionada al request, un único error y ausencia de detalle o
CAE. La respuesta puede incluir el error sanitario global; no expone el mensaje
SOAP. El sublote enviado se cierra atómicamente y el lote detiene los grupos
posteriores como `no_enviado_por_rechazo_global`. Código desconocido o mezclado,
tipos no exactos, error global parcial, timeout, transporte, CAE o detalle dejan
la operación en `requiere_reconciliacion`; el replay de la misma clave devuelve
su estado durable sin realizar WSAA, WSFE ni una nueva FECAE. El contrato
forma parte del estado aceptado del repositorio. La evidencia de su cierre vive
en el dossier correspondiente; su disponibilidad en una instalación se
consulta en el plano de control.

SC-09 también impide cerrar un sublote ante una cabecera/detalle discordantes o
un rechazo acompañado por CAE/vencimiento. La contradicción correlacionada
inmoviliza toda la respuesta antes de guardar comprobantes, conserva los CAEs
atribuibles y detiene nuevos envíos para reconciliar. Una cabecera P coherente
con una mezcla A/R sigue aplicando la política vigente por detalle.

La recuperación stale del worker conserva una puerta previa más estricta: solo
reencola grupos intactos, sin intento, CAE, número, comprobante vinculado ni
comprobante autorizado candidato. El diagnóstico compartido admite
`alineada` o `arca_adelantada` si no existe incertidumbre propia, pero no asigna
el número ni crea reservas. El procesamiento normal posterior vuelve a
diagnosticar, persiste las reservas y ejecuta el segundo preflight antes de
FECAE. `local_adelantada`, un intento propio activo o incierto y cualquier
preflight no concluyente bloquean el lote. Los metadatos expuestos conservan
categorías estables como `numeracion_no_verificable`, no el texto interno de la
excepción.

Durante el procesamiento, el backend actualiza `grupos_emitidos`,
`grupos_fallidos`, `grupos_validos` y `mensaje_resumen` después de cada grupo,
para que la UI pueda mostrar avance real, tiempo transcurrido y estimación
restante sin usar SSE/WebSocket.

Regla fiscal crítica: FactuFlow no asume fecha de emisión del día actual. La
fecha de comprobante debe venir del archivo o de una fecha fija confirmada por
el usuario. La validación observa los comprobantes cuya fecha queda fuera de la
ventana admitida por ARCA antes de permitir emitir. Si la fecha del archivo
queda fuera de ventana, el usuario debe elegir una fecha permitida y revalidar.
Antes de llamar a `procesar`, el cliente debe mostrar la confirmación final de
fecha fiscal con el mismo texto usado en emisión individual y enviar el header
`X-Confirmacion-Fecha-Fiscal` con el token exacto derivado de los grupos
validados:

```http
X-Confirmacion-Fecha-Fiscal: fechas=YYYY-MM-DD,...;puntos_venta=N,...
```

La API recalcula ese token desde el lote validado y rechaza la emisión si falta
o no coincide. Esto evita confirmar un lote distinto al que el usuario revisó.

Regla fiscal crítica: FactuFlow tampoco asume si el lote corresponde a productos
o servicios. El usuario debe elegirlo antes de validar, o confirmar que el
archivo trae esa definición fila por fila. Si se usa `archivo`, la columna
configurada debe existir y todas las filas deben tener `Producto` o `Servicio`;
si falta o hay valores inválidos, la API debe devolver errores de validación
para informar al usuario y no dejar el lote listo para emitir.

Regla de ítem crítica: el concepto fiscal ARCA no es la descripción/concepto
facturado del ítem. El lote también debe definir la descripción del ítem antes
de validar o emitir, desde archivo o como valor fijo para todo el lote. No debe
haber defaults ocultos como descripción facturada.

## Perfiles De Carga Masiva

```http
GET /api/perfiles-carga-masiva
POST /api/perfiles-carga-masiva
PUT /api/perfiles-carga-masiva/{perfil_id}
DELETE /api/perfiles-carga-masiva/{perfil_id}
POST /api/perfiles-carga-masiva/{perfil_id}/predeterminado
```

Los perfiles de carga masiva pertenecen al emisor activo resuelto por JWT y
`X-Empresa-Id`. Permiten guardar una configuración visible para precargar
`Emisión masiva`: plantilla/formato opcional, punto de venta, concepto fiscal
ARCA, descripción facturada y reglas de fechas.

El payload usa `configuracion_json` versionado. Valores principales:
- `formato_importacion_version_id`: opcional; debe ser global o pertenecer al
  emisor activo.
- `punto_venta.modo`: `archivo` para usar el punto definido en el Excel o
  `fijo` para precargar un punto concreto del emisor.
- `punto_venta.numero`: requerido cuando `punto_venta.modo=fijo`; debe estar
  cargado con `usable_factuflow=true`, incluido estado efectivo
  `verificado_rece` para el ambiente actual. El perfil no crea evidencia ni
  evita la revalidación del lote.
- `concepto_modo`: `productos`, `servicios`, `archivo` o vacío para completar
  en la carga.
- `descripcion_item_modo`: `archivo`, `fija` o vacío.
- `fecha_emision.modo`: `archivo`, `manual` o `personalizada`.
- `periodo_servicio.modo`: `archivo`, `manual`, `mes_anterior_completo`,
  `mes_actual_completo` o `personalizado`.
- `fecha_vto_pago.modo`: `archivo`, `manual`, `mismo_dia_emision`,
  `emision_mas_dias` o `personalizada`.

Regla crítica: el perfil de carga masiva no valida ni emite. La fecha de emisión
del perfil debe quedar para completar manualmente, venir del archivo o ser una
fecha personalizada explícita válida (`DD/MM/AAAA`, `YYYY-MM-DD` o ISO técnico,
normalizada por la API a `YYYY-MM-DD`). No son válidos `fecha_actual` ni modos
relativos como último día del mes anterior para fecha de emisión. Todos los
controles deben quedar visibles y editables antes de validar. Si se marca un
perfil como predeterminado, la API desmarca cualquier otro predeterminado del
mismo emisor.

## PDF

```http
GET /api/pdf/comprobante/{comprobante_id}
GET /api/pdf/comprobante/{comprobante_id}/preview
```

El PDF fiscal se genera bajo demanda solo para comprobantes `autorizado` con
CAE y vencimiento de CAE persistidos; si faltan esos datos, la API responde
`409` y no genera un documento rotulado como autorizado. Incluye QR ARCA con
payload Base64 según la especificación oficial y muestra datos fiscales del
emisor/receptor, operación, detalle, totales, CAE y vencimiento CAE. En
comprobantes nuevos de servicios también muestra período facturado y vencimiento
de pago. Los datos libres renderizados en la plantilla se escapan como HTML.
Si falla la generación, descarga y preview responden `500` con un mensaje
genérico accionable; no devuelven excepciones, rutas internas ni credenciales.
El diagnóstico técnico queda en registros privados. La autorización y el alcance
por emisor se comprueban antes de generar el documento.

## Reportes

```http
GET /api/reportes/ventas
GET /api/reportes/iva-ventas
GET /api/reportes/clientes
```

Los reportes se calculan para el emisor activo.
`GET /api/reportes/iva-ventas` calcula notas de crédito/débito con signo
fiscal correspondiente y el detalle discrimina alícuotas 10,5%, 21% y 27%.

### Lecturas fiscales A-03

`GET /api/reportes/ventas` y `/iva-ventas` incluyen `por_moneda`, una lista de
resúmenes independientes; sus filas incluyen `moneda` y `cotizacion` decimal
conservada. Los campos monetarios de `resumen` son `null` en períodos mixtos;
en períodos de una moneda mantienen el valor escalar y acreditan `moneda`.
Conteos y período generales permanecen disponibles. No hay conversión a pesos.

IVA obtiene bases desde detalle contrastado con los importes guardados. Una
base no acreditada es `null`, también en el agregado que la incluye; `total_neto`
y `total_iva` usan importes conservados. `bases_acreditadas`, `origen_bases` y
`cantidad_bases_no_acreditadas` explican cobertura. `sin_clasificacion` identifica
la base con IVA cero sin categoría acreditada y `sin_iva_discriminado` el neto
C. `no_gravado` y `exento` son desconocidos mientras no exista evidencia fiscal
de esas categorías. NC aplica signo negativo a neto, bases, IVA y total.

`GET /api/reportes/clientes` aplica orden y límite dentro de cada moneda.
`por_moneda` contiene `moneda`, `clientes` y `total_general` de los clientes
mostrados. `clientes` superior conserva todas esas filas, identificadas por
moneda; `total_general` superior es nulo si mezcla monedas. No sumar esos
nominales ni comparar sus posiciones entre monedas. La lista de comprobantes
incorpora `moneda` y `cotizacion` exacta; detalle ya conserva ambos campos.

Contrato y límites históricos: [lecturas A-03](../agents/a03-lecturas-fiscales-design.md).

## Codigos De Error

| Código | Descripción |
| --- | --- |
| 200 | OK |
| 201 | Recurso creado |
| 204 | Sin contenido |
| 400 | Datos inválidos |
| 401 | No autenticado |
| 403 | Sin permisos |
| 404 | Recurso no encontrado |
| 409 | Conflicto fiscal, concurrencia, idempotencia o elegibilidad RECE |
| 422 | Error de validación |
| 500 | Error interno |
| 503 | Servicio externo no disponible |

## Notas

- El login tiene presupuesto por cuenta, origen y proceso, con respuestas
  `429` y recuperación temporal; los demás endpoints no incorporan una
  limitación global por este cambio. Alcance en el [contrato SC-08](../agents/sc-08-login-recuperacion-design.md).
- La versión visible de la API sale de `APP_VERSION`; el contrato HTTP no está
  versionado en la URL.
- Para el estado operativo actual, usar `docs/agents/current-status.md`.
