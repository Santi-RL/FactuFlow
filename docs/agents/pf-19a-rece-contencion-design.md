# PF-19A — Diseño fiscal, contención RECE e inventario legacy

Fecha de diseño e implementación: 08/08/2026
Estado objetivo de `main`: cerrado en código y documentación al integrar este
corte; posterior a `v0.2.2`, todavía sin release ni despliegue productivo.

## Objetivo y límites

PF-19A contiene antes de `FECAESolicitar` únicamente los destinos fiscales
declarados explícitamente en la configuración privada, documenta la frontera
RECE completa y agrega un inventario legacy estrictamente de solo lectura. Una
omisión queda sin protección hasta PF-19B. El corte responde a evidencia
productiva en la que una descripción genérica `Web Services` alcanzó la
solicitud de CAE y ARCA devolvió el error global excluyente `10005`.

Incluye:

- una regla privada y explícita por ambiente, emisor, identidad local del punto,
  número fiscal y tipo de comprobante;
- una guarda común en emisión individual, batch, fallback unitario, worker,
  reintentos y preflight stale;
- abortos locales con cero `FECAESolicitar`, cero CAE, cero intentos y cero
  comprobantes;
- preservación del bloqueo al renumerar la fila local o recrear el número fiscal
  con otra fila;
- inventario de candidatos legacy deduplicado por intento fiscal, con salida
  sanitizada y privada, sin cambios de estado;
- tabla de estados, orden de operaciones, fallos intermedios, consumidores,
  concurrencia, idempotencia, rollback y matriz de pruebas para PF-19 completo.

No incluye:

- modelar `verificado_rece`, `no_rece` o `no_verificado` en la base;
- decidir precedencia durable entre constancia, WSFE y edición manual;
- presentar el texto mutable `sistema` como prueba de RECE;
- preservar nuevos errores globales ARCA en un contrato estructurado;
- convertir `10005` en rechazo terminal en runtime;
- resolver, reconciliar o editar registros legacy;
- migraciones de schema, llamadas ARCA reales, saneamiento productivo ni
  despliegue.

La elegibilidad RECE end-to-end pertenece a PF-19B. El rechazo global
estructurado y el cierre auditado legacy pertenecen a PF-19C.

## Autoridad fiscal y evidencia

Autoridad consultada el 08/08/2026: el
[índice oficial de factura electrónica de ARCA](https://arca.gob.ar/ws/documentacion/ws-factura-electronica.asp)
enlaza el
[Manual para el desarrollador WSFEv1 v4.6](https://www.arca.gob.ar/ws/documentacion/manuales/manual-desarrollador-ARCA-COMPG.pdf),
revisión 01/08/2026. La regla `10005` está en `FECAESolicitar` →
`Validaciones y errores` → `Controles aplicados al objeto <FeCabReq>` →
`Validaciones Excluyentes`, campo `<PtoVta>`, página 40 del PDF: el punto debe
estar dado de alta y ser RECE. Eso demuestra que un rechazo global con ese
código puede ocurrir antes de autorizar detalles, pero no autoriza a PF-19A a
reconstruir un código que el modelo legacy no preservó de forma estructurada.

Reglas de autoridad del corte:

1. `es_webservice` y `usable_factuflow` describen el filtro técnico actual; no
   equivalen a compatibilidad RECE.
2. `FEParamGetPtosVenta` confirma existencia y bloqueo técnico, pero no aporta
   la procedencia RECE requerida.
3. La frase editable `RECE para aplicativo y web services` es una señal textual
   actual, no evidencia histórica durable.
4. La firma textual legacy que contiene `[10005]` solo identifica un candidato
   para revisión; no cambia el estado persistido.
5. Un `R` completo por detalle continúa siendo rechazo terminal. Un error global
   desconocido, timeout, respuesta parcial, cardinalidad inconsistente o fallo
   de transporte continúa siendo incertidumbre.

## Mapa exhaustivo de consumidores

| Consumidor | Conducta anterior / riesgo | Contención PF-19A | Dueño del cierre definitivo |
|---|---|---|---|
| Importación de constancia | Detecta `Web Service(s)` por texto y puede marcar `es_webservice` | La guía prohíbe usar descripciones genéricas; solo queda contenida si su tupla se declara explícitamente | PF-19B modela fuente, fecha y estado RECE |
| Sincronización WSFE | El frontend crea o actualiza puntos técnicos como Web Services usables | No puede saltar la guarda central; `FEParamGetPtosVenta` no acredita RECE | PF-19B alinea sync, modelo y UI |
| Alta y edición manual | Permite cambiar número, sistema, fuente, actividad y marca Web Services | La regla coincide por ID local **o** número fiscal, evitando bypass por renumeración/recreación | PF-19B restringe contratos y resuelve contradicciones |
| Perfiles de carga | Punto fijo validado con el filtro técnico actual | La documentación no lo presenta como elegible; solo una regla explícita contiene la emisión final | PF-19B invalida perfiles no elegibles |
| Validación Excel | Punto fijo o por archivo puede pasar por `usable_factuflow` | El snapshot no otorga autoridad; el núcleo revalida la contención antes de FECAE | PF-19B falla cerrado durante validación |
| Emisión individual | La API puede recibir directamente un punto técnico usable | Guarda antes de certificado, WSAA, intento y FECAE | PF-19B mueve elegibilidad antes de idempotencia |
| Batch normal | El lote puede haber sido validado con un snapshot obsoleto | El flujo exterior puede leer `FECompTotXRequest`; la guarda del sublote homogéneo corre antes de intentos y FECAE | PF-19B alinea carga y procesamiento |
| Fallback unitario | Delega en `_emitir_comprobante_locked` | Usa la misma guarda central | PF-19B/C consumen el contrato final |
| Worker | Delega en `procesar_lote(..., reanudar=True)` | Puede compartir la lectura previa `FECompTotXRequest`; no existe otra llamada FECAE fuera de `FacturacionService` | PF-19B/C cubren estados visibles |
| Reintentos manuales | Invocan directamente el núcleo individual | La guarda se repite; una tupla contenida no reemite | PF-19C define cierre terminal legacy |
| Recuperación stale | Puede consultar numeración y luego reencolar un grupo intacto | El preflight falla antes de WSAA/WSFE para una tupla contenida | PF-19C habilita solo resolución probada |
| Resolución idempotente stale | `FECompConsultar` podría concluir inexistencia y habilitar replay | Una tupla contenida conserva reconciliación y no llega a esa liberación automática | PF-19C define consulta y transición auditadas |
| Reconciliación externa | Consulta `FECompConsultar` y puede vincular una autorización comprobada | No se convierte en camino de emisión; no llama FECAE | PF-19C revisa su uso para candidatos legacy |
| Endpoint ARCA histórico de emisión | Ya responde `410 Gone` | Permanece retirado | No aplica |

## Invariantes verificables

1. Una regla se aísla por `ambiente + empresa_id + tipo_comprobante` y coincide
   con el punto si coincide su `punto_venta_id` o su número fiscal.
2. Cambiar solo el ambiente, emisor, tipo o ambas identidades del punto no
   propaga el bloqueo.
3. Renumerar la misma fila no levanta el bloqueo por ID.
4. Recrear el número fiscal original con otra fila no levanta el bloqueo por
   número.
5. La configuración prohíbe campos desconocidos, valores inválidos, comodines y
   duplicados por ID o por número dentro del mismo ambiente, emisor y tipo. Si
   un runtime cruza dos reglas distintas, la selección es determinística:
   `ID+número > ID > número`; cualquiera de las coincidencias mantiene el
   bloqueo.
6. Los núcleos directos individual y batch abortan antes de construir
   WSAA/WSFE. En todos los consumidores, un destino contenido no crea intento
   fiscal, no invoca `FECAESolicitar`, no recibe CAE y no crea comprobante.
7. La fase monotónica `FaseSolicitudArca.iniciada` permanece en `False` ante el
   aborto.
8. El aborto local usa la categoría
   `punto_venta_bloqueado_preautorizacion`, número `0` y
   `requiere_reconciliacion=false`; no se presenta como rechazo ARCA.
9. Una operación idempotente HTTP puede existir antes de la guarda, pero no
   contiene reserva, intento ni comprobante. PF-19B debe adelantar la
   elegibilidad al borde anterior a idempotencia.
10. El batch puede consultar `FECompTotXRequest` antes de conocer el sublote; la
    garantía de PF-19A es cero FECAE/CAE, no cero lecturas ARCA en todo el flujo.
11. Un `R` por detalle conserva `rechazado_arca`; un error global no clasificado
    conserva `requiere_reconciliacion`.
12. PF-19A no reclasifica `10005` en runtime ni cambia los estados legacy.
13. El inventario no importa `FacturacionService`, WSAA, WSFE ni reconciliación;
    solo ejecuta una consulta allowlist y no devuelve señales de grupo hasta
    demostrar la cadena grupo → lote → empresa del intento y el alcance del
    comprobante asociado. Tampoco considera válida la FK directa del intento
    hasta resolverla y verificar emisor, punto, tipo y número planificado.
14. PostgreSQL confirma `REPEATABLE READ READ ONLY`; SQLite confirma
    `query_only=1`, restaura el valor previo de la conexión y siempre termina
    con rollback.
15. El reporte privado conserva identificadores operativos, punto de venta y
    tipo de comprobante. No expone CUIT, razón social, receptor, importes, fecha
    fiscal, CAE, número planificado, clave idempotente, hashes, archivo, payload
    ni mensajes crudos.
16. El ambiente histórico se informa `indeterminado`; `ARCA_ENV` es solo el
    contexto actual de lectura.
17. Una firma textual global `[10005]` se rotula
    `candidato_10005_no_confirmado`; nunca `rechazado_arca` ni reparado.
18. Un candidato cuyo intento o grupo tiene CAE o un comprobante vinculado con
    referencia válida, o cuyo estado es incompatible, se separa como
    inconsistencia y no se corrige. Una referencia inválida prevalece sobre esa
    evidencia.
19. Los enteros de reglas y filtros son estrictos: strings y floats no se
    coercionan a IDs, puntos o tipos fiscales.
20. Una referencia legacy ausente se informa `referencia_huerfana`; una
    operación, lote, grupo, comprobante directo o de grupo, o punto cruzado
    entre alcances se informa `referencia_fuera_de_alcance` y sus señales no se
    inspeccionan. Los comprobantes deben coincidir con emisor, punto, tipo y
    `numero_planificado`; sin número planificado no se consideran válidos.
21. La salida contiene IDs operativos para localizar candidatos y, por eso,
    siempre se trata como evidencia privada, no como reporte público.
22. `generado_el` usa `DD/MM/AAAA`; `ambiente_contexto_actual` rotula el entorno
    de lectura y nunca se presenta como ambiente histórico del intento.

## Contrato de contención

La variable privada `ARCA_PUNTOS_BLOQUEADOS_PREAUTORIZACION` recibe JSON. Cada
entrada exige:

- `ambiente`: `homologacion` o `produccion`;
- `empresa_id`: ID local positivo del emisor;
- `punto_venta_id`: ID local positivo de la fila;
- `punto_venta`: número fiscal positivo;
- `tipo_comprobante`: código positivo exacto, sin comodines;
- `motivo`: `punto_no_rece_confirmado`, `elegibilidad_no_verificada` o
  `revision_legacy_pendiente`.

Ejemplo exclusivamente sintético:

```dotenv
ARCA_PUNTOS_BLOQUEADOS_PREAUTORIZACION=[{"ambiente":"produccion","empresa_id":101,"punto_venta_id":202,"punto_venta":7,"tipo_comprobante":6,"motivo":"elegibilidad_no_verificada"}]
```

PF-19A contiene únicamente las tuplas declaradas explícitamente en
`ARCA_PUNTOS_BLOQUEADOS_PREAUTORIZACION`. La lista vacía o una omisión no
demuestran elegibilidad: dejan esa combinación sin protección hasta PF-19B.
Antes de operar una instalación con puntos genéricos o dudosos, el responsable
debe cargar cada tipo afectado en la configuración privada y reiniciar de forma
controlada. No se versionan valores reales. Tras migrar o recrear datos hay que
revalidar IDs y números; el matcher por ambos campos reduce, pero no reemplaza,
esa revisión.

## Estados y transiciones

| Hecho observado | Estado de intento | Grupo/lote | Operación | Reemisión |
|---|---|---|---|---|
| Bloqueo PF-19A antes de FECAE | no se crea | el flujo nuevo puede cerrar `fallido` | puede cerrar `fallido` | bloqueada mientras rija la regla |
| Segundo preflight aborta | `fallido_verificado` | `fallido` | terminal pre-ARCA | requiere nueva validación |
| `R` completo por detalle | `rechazado_arca` | `fallido` | `fallido`/finalizada | solo según política de rechazo explícito |
| Error global `10005` con contrato legacy actual | `requiere_reconciliacion` | `requiere_reconciliacion` | `requiere_reconciliacion` | bloqueada hasta PF-19C |
| Global desconocido, parcial, timeout o transporte | `requiere_reconciliacion` | `requiere_reconciliacion` | `requiere_reconciliacion` | bloqueada |
| `A` con CAE válido y persistencia correcta | `autorizado` | `autorizado` / `completado` | `finalizado` | no corresponde |
| `A` conocido y fallo de persistencia | `requiere_reconciliacion` con evidencia | `requiere_reconciliacion` | `requiere_reconciliacion` | bloqueada |
| Firma textual legacy hallada por inventario | sin cambios | sin cambios | sin cambios | sin cambios |

El inventario diferencia `candidato_10005_no_confirmado`,
`incertidumbre_sin_codigo_preservado`, `marcador_inconsistente_con_estado` y
`preautorizacion_con_cae_o_comprobante`, además de `referencia_huerfana` y
`referencia_fuera_de_alcance`. Son clasificaciones de reporte, no estados de
dominio.

## Orden antes, durante y después de FECAE

En el flujo exterior de `procesar_lote` o del worker, la resolución de capacidad
batch puede autenticar WSAA, construir WSFE y leer `FECompTotXRequest` antes de
conocer los sublotes. Esa lectura no autoriza comprobantes ni marca la fase
FECAE. Los pasos siguientes describen cada núcleo de emisión una vez formado el
request o sublote.

### Antes

1. Validar request canónico, fecha explícita, receptor, ítems y emisor.
2. Tomar lock local/advisory y calcular totales.
3. Cargar la fila del punto dentro del emisor.
4. Evaluar la contención por ambiente, emisor, ID/número y tipo.
5. Si coincide, devolver aborto local. No cargar certificado ni crear intento.
6. Si no coincide, continuar con certificado, WSAA, estado técnico WSFE y
   diagnóstico de numeración.
7. Crear reserva/intento durable y ejecutar el segundo preflight.

### Durante

8. Marcar `FaseSolicitudArca.iniciada` inmediatamente antes de
   `fe_cae_solicitar` o `fe_cae_solicitar_lote`.
9. No asumir que una excepción equivale a rechazo.
10. No continuar como si hubiera detalles cuando la cabecera invalida o vuelve
    incierto el sublote; el cambio estructurado queda para PF-19C.

### Después

11. `A` exige CAE ASCII de 14 dígitos y vencimiento válido antes de persistir.
12. `R` por detalle puede cerrar terminalmente si su persistencia también cierra.
13. Cualquier resultado ambiguo conserva reserva y reconciliación.
14. Un fallo local posterior a autorización conocida conserva la evidencia y
    prohíbe reemisión.

## Concurrencia, idempotencia y fallos intermedios

La contención se evalúa dentro del lock de numeración y nuevamente en todos los
núcleos que pueden emitir. No crea una ventana de autorización: cambiar la
configuración exige reiniciar el proceso y una emisión ya iniciada conserva las
reglas post-ARCA de PF-01.

El bloqueo por ID o número evita dos carreras administrativas locales: renumerar
la fila alcanzada y recrear el número original. La unicidad local por emisor y
número sigue vigente. PF-19B deberá invalidar confirmaciones y claves cuando
cambie la elegibilidad durable, algo que PF-19A no puede representar.

Si la base falla antes de FECAE, no hay CAE. Si falla al cerrar el aborto local,
la operación HTTP puede quedar interrumpida y la regla seguirá bloqueando un
nuevo intento. Cuando el aborto ya quedó guardado en la operación idempotente,
su replay devuelve esa respuesta durable incluso si luego se retira la regla.
Si falla después de FECAE, nunca se degrada a aborto local.

## Inventario legacy de solo lectura

Comando:

```bash
cd backend
.venv\Scripts\python.exe -m app.scripts.pf19_legacy_inventory --empresa-id <ID> --lote-id <LOTE_ID> --pretty
```

`--empresa-id` es obligatorio. Los filtros allowlist opcionales son
`--punto-venta`, `--tipo-comprobante` y `--lote-id`. La consulta solicita como
máximo `501` filas: si detecta más de `500`, aborta y exige filtros más estrechos;
nunca trunca silenciosamente. No se aceptan SQL, URL de base, ruta de salida ni
campos extra. Si se conserva el JSON, debe redirigirse a `.tmp/` u otra ruta
ignorada y tratarse como evidencia privada. En producción se filtra por el
emisor y el incidente investigado; un barrido amplio solo se admite sobre una
restauración aislada y descartable, donde puede usarse únicamente
`--empresa-id`. Un error interno devuelve código `2` por `stderr`, sin JSON,
traceback ni una promesa de logs generados por la CLI.

La unidad deduplicada es `IntentoEmisionFiscal`. La consulta parte de las
categorías legacy `arca_batch_sin_respuesta` y `arca_respuesta_incierta`, une en
modo lectura operación, grupo, lote y punto actual, y examina internamente solo
los campos de error conocidos y con alcance válido necesarios para reconocer la
firma global canónica. Nunca devuelve esos textos. Una relación ausente o
cruzada se clasifica antes de leer sus señales; el grupo solo es consumible si
su lote pertenece al emisor del intento y su comprobante asociado existe en el
mismo alcance fiscal. Tanto el comprobante directo como el de grupo deben
coincidir con emisor, punto, tipo y número planificado; la ausencia de número
planificado impide validarlos. Un CAE o comprobante con referencia válida en el
intento o grupo se informa como contradicción fiscal.

Limitaciones deliberadas:

- no se puede reconstruir cuántas llamadas FECAE existieron por falta de un ID
  durable de solicitud/sublote;
- no se puede atribuir ambiente histórico porque no se persiste en intento,
  operación, grupo, lote ni comprobante;
- `sistema` y `fuente` actuales son mutables y no prueban el estado histórico;
- una fila de punto ausente o renumerada se informa, no se descarta;
- no se consulta ARCA, no se crea comprobante y no se cambia ningún estado.

## Migración, rollback y operación

PF-19A no agrega tablas, columnas, constraints ni revisión Alembic. El rollback
de código consiste en retirar la guarda y la variable, pero una reversión
operativa no debe hacerse mientras existan destinos dudosos: primero hay que
conservar la contención equivalente o cerrar PF-19B.

Retirar una entrada de la lista es una decisión fiscal, no una corrección de
formato. Requiere evidencia administrativa, revisión exacta de ambiente,
emisor, punto y tipo, y una nueva confirmación fiscal. PF-19A no autoriza editar
la base ni resolver lotes reales.

## Matriz automatizada y QA permitida

Cobertura nueva:

- configuración estricta, campos desconocidos, enteros sin coerción, reglas
  repetidas por identidad local o fiscal y precedencia determinística de cruces;
- aislamiento por ambiente, emisor, punto y tipo;
- renumeración de la misma fila y recreación del número con otra fila;
- núcleos directos individual y batch con cero WSAA/WSFE, cero intentos, cero
  FECAE, cero CAE y cero comprobantes;
- `procesar_lote` con una autenticación WSAA y una lectura segura
  `FECompTotXRequest` previas, pero cero FECAE, CAE, intentos y comprobantes; el
  worker queda cubierto por su delegación probada a ese flujo con `reanudar=True`;
- `FaseSolicitudArca.iniciada=false` en abortos;
- replay HTTP durable, intento stale y preflight stale de lote sin reemisión;
- inventario deduplicado y sanitizado;
- firma global canónica frente a texto libre, `[10005]` sin prefijo, campos no
  vinculados y falsos positivos `100050`;
- contradicción persistida en grupo y corrupción cruzada de lote, grupo y
  comprobante entre emisores, sin consumir `10005` ni CAE ajenos; la FK directa
  cubre emisor ajeno, huérfano, número incorrecto, número planificado ausente y
  vínculo válido, y el comprobante grupal también exige el número planificado;
- emisor obligatorio y máximo duro de `500` registros con detección por
  `máximo + 1`, aceptación explícita de `500`, aborto en `501` y cero truncado
  silencioso;
- ambiente histórico indeterminado y ausencia de saneamiento;
- SQLite `query_only` verificado, DML rechazado, restauración previa y rollback;
- test de integración PostgreSQL desechable para `transaction_read_only=on` y
  DDL rechazado, omitido si falta infraestructura explícita.

Cobertura vecina que permanece vigente:

- batch abortado por segundo preflight con cero FECAE;
- `R` explícito frente a incertidumbre;
- global desconocido, parcial, cardinalidad, timeout y transporte;
- reintentos que continúan solo después de rechazo explícito;
- stale sin asignar número ni solicitar CAE;
- aislamiento multiemisor e idempotencia.

La QA de PF-19A usa exclusivamente datos sintéticos y dobles. No solicita CAE
real para provocar `10005`, no accede al VPS y no modifica bases reales.

## Riesgos residuales y decisiones abiertas

1. La lista es contención operativa explícita, no descubrimiento automático.
   Una tupla omitida no queda protegida; PF-19B debe hacer fail-closed por modelo.
2. El frontend todavía puede mostrar `Usable` con el filtro técnico histórico.
   La documentación lo corrige, pero la UI end-to-end pertenece a PF-19B.
3. El ambiente histórico legacy es indeterminado; debe persistirse en el modelo
   futuro antes de una reparación definitiva.
4. El código global no está estructurado. PF-19C debe conservar código, alcance
   de cabecera y relación con el sublote antes de clasificar `10005`.
5. La firma textual exacta puede orientar una auditoría, pero no basta para
   sanear. La autoridad de cierre se decide en PF-19C con backup y consultas
   seguras.
6. Grupo y lote colapsan varios abortos terminales en `fallido`; PF-14/PF-15
   consumirán una taxonomía final después de PF-19C.

## Próximo corte preciso

PF-19B debe agregar la elegibilidad RECE durable en modelo y migración, con
`verificado_rece`, `no_rece` y `no_verificado`, fuente, fecha, ambiente y
evidencia; hacer fail-closed todos los puntos legacy; alinear constancia,
sincronización, API, edición, perfiles, Excel, selectores, individual, lotes,
worker y reintentos; e invalidar confirmación/idempotencia ante cambios. No debe
absorber todavía la clasificación global `10005` ni el saneamiento legacy de
PF-19C.
