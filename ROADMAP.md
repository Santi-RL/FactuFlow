# Roadmap de FactuFlow

Última actualización: 10/08/2026

Este roadmap traduce la visión estable del producto en prioridades, fases y
trabajo planificado. La visión canónica vive en `VISION.md` y no debe cambiarse
desde este archivo.

## Como leer este archivo

- `[x]` Hecho
- `[~]` En curso
- `[ ]` Pendiente

## Visión del producto

La visión canónica del producto está definida en `VISION.md`.

Todo ítem de este roadmap debe alinearse con esa visión. Si una prioridad,
fase, implementación o cambio deseado contradice `VISION.md`, primero debe
modificarse explícitamente la visión y recién después incorporarse al roadmap.

## Objetivo actual

Consolidar el MVP después del uso productivo real controlado, centrado en:
- emisión individual y masiva por Excel
- formatos de importación configurables para archivos externos
- uso administrativo no técnico
- homologación real y operación productiva inicial con ARCA
- multiemisor con un emisor activo explícito por vez
- instalación local o en VPS pequeño, con consumo eficiente de procesamiento,
  RAM y almacenamiento
- visibilidad administrativa del uso de almacenamiento por instalación, emisor
  y tipo de dato
- robustez operativa: backups, trazabilidad, observabilidad y soporte
- rediseño secuencial de carga masiva para reducir ruido operativo sin tocar
  garantías fiscales

## Decisiones de producto vigentes

- FactuFlow es una herramienta para facturar. El alcance central es
  facturación electrónica ARCA, emisión individual, emisión masiva, PDFs,
  reportes operativos y soporte administrativo del flujo de facturación.
- No está planificado incorporar manejo de cuentas corrientes, stock ni
  catálogos como módulos del producto.
- Las integraciones externas quedan para una etapa posterior, cuando la
  facturación este madura y productiva estable. Esas integraciones deben estar
  enfocadas en obtener datos desde otras fuentes o aplicaciones, o enviar datos
  hacia ellas, usando la API existente o su evolución.
- El modelo multiemisor vigente es el de una empresa/emisor activo por vez. Un
  contador independiente o estudio chico puede administrar varios CUITs, pero
  toda operación debe quedar scopiada al emisor activo seleccionado.
- El modelo vigente de usuarios es simple: el primer usuario de una instalación
  es administrador propietario; luego solo administradores crean, desactivan,
  reactivan, asignan alcances o resetean usuarios. La evolución aceptada mantiene
  dos roles y evita permisos finos: los administradores operan todos los
  emisores y conservan la administración global; los operadores tendrán una
  lista explícita de emisores autorizados y podrán recibir la única capacidad
  adicional `Puede crear y editar emisores`. Esa capacidad permitirá crear un
  emisor con autoasignación atómica y editar solo emisores ya autorizados; no
  incluirá borrado, gestión de usuarios, `Sistema` ni acceso global. Hasta que
  PF-06/PF-07/PF-08 implemente y cierre este diseño, la aplicación desplegada
  conserva el alcance singular actual.
- No se avanza por ahora hacia una plataforma multiempresa compleja con
  administración central completa, permisos finos por organización, reportes
  globales consolidados u operación simultánea entre emisores.
- La seguridad multiemisor es prioritaria: clientes, certificados, puntos de
  venta, comprobantes, lotes, PDFs, reportes, perfiles de carga y formatos de
  importación no deben mezclarse entre emisores.
- Las operaciones que pueden solicitar CAE deben ser idempotentes desde backend,
  no solo desde UI. Emisión individual, procesamiento de lotes y reintento de
  fallidos exigen `X-Idempotency-Key`, persisten una operación durable antes de
  ARCA y dejan intentos fiscales reconciliables si el resultado queda incierto.
- El despliegue local con launcher ya existe y está probado hasta nivel
  desarrollo/QA. La primera instalación privada en VPS con
  `docker-compose.prod.yml`, PostgreSQL y HTTPS ya quedó operativa; el siguiente
  hito de plataforma es robustecer operación, observabilidad, recuperación y
  mantenimiento.
- FactuFlow debe poder operar en instalaciones locales o VPS pequeños. Las
  decisiones de arquitectura, jobs, observabilidad, reportes, PDFs y
  almacenamiento deben priorizar sencillez y bajo consumo de procesamiento, RAM
  y disco sin perder funcionalidad fiscal u operativa.
- En VPS, la persistencia debe limitarse a los datos mínimos necesarios para
  operar, auditar y recuperar el sistema. PDFs, ZIPs, archivos observados y
  otros artefactos descargables no vitales deben generarse bajo demanda,
  descargarse a la PC del usuario y limpiarse del servidor después de cumplir su
  propósito.
- El gestor de almacenamiento administrativo queda incorporado como herramienta
  de diagnóstico y mantenimiento. Muestra cuánto espacio usa la instalación y lo
  desglosa por emisor, base de datos, lotes, archivos temporales, caché,
  certificados y logs. El cálculo es liviano, acotado a rutas y tablas
  conocidas, y no expone datos privados innecesarios. Las acciones de limpieza
  sobre lotes, logs y temporales exigen resguardo ZIP descargado antes de liberar
  espacio.
- La distribución comercial instalable queda para una etapa posterior, cuando
  el producto sea estable y repetible funcionando en VPS.
- La observabilidad operativa estándar es obligatoria antes de ampliar el uso
  productivo. Debe permitir diagnosticar emisiones, lotes, errores ARCA,
  reconciliaciones, estado del sistema y backups con lenguaje simple para
  usuarios no técnicos. No requiere todavía monitoreo complejo con herramientas
  externas.

## Foto actual del proyecto

### Producto y negocio
- [x] Objetivo principal redefinido: emisión masiva y UX administrativa simple
- [x] Modelo multiemisor base definido: varios CUITs por instalación y un emisor
  activo explícito por vez
- [ ] Operadores con varios emisores autorizados y capacidad opcional para crear
  y editar emisores asignados, según el diseño integrado PF-06/PF-07/PF-08
- [~] Criterios UX no técnicos parcialmente implementados
- [x] Login informa claramente cuando el servidor local no está disponible
- [x] Setup inicial cerrado cuando ya existe cualquier usuario y administración
  de usuarios disponible dentro de la aplicación
- [x] Producción real inicial utilizada con comprobantes autorizados
- [ ] Refuerzo continuo de aislamiento entre emisores antes de ampliar volumen
  o uso productivo

### Backend
- [x] FastAPI operativo con auth, clientes, empresa, puntos de venta, certificados, comprobantes, PDF, lotes y reportes
- [x] Integración WSAA + WSFEv1 operativa en homologación y producción inicial
- [x] Transporte SOAP con timeout efectivo para carga de WSDL y operaciones, y
  llamadas Zeep ejecutadas fuera del event loop con una firma compatible con
  todo el rango AnyIO admitido por Starlette
- [x] Emisión individual real validada con CAE
- [x] Emisión masiva por Excel implementada
- [x] Formatos de importación configurables para emisión masiva con alcance global y por emisor
- [x] Administrador visual de plantillas de carga masiva sobre
  `formatos_importacion`, con plantillas globales o por emisor, clonado de
  plantillas protegidas, versionado, compatibilidad con perfiles y descarga
  `.xlsx` generada bajo demanda.
- [x] Perfiles de carga masiva por emisor para precargar formato, punto de
  venta, concepto, descripción y fechas visibles antes de validar
- [x] Perfiles de carga masiva no permiten guardar fecha actual como regla de
  emisión fiscal
- [x] Perfiles de carga masiva validan calendario real en fechas personalizadas
  de emisión, período y vencimiento
- [x] Emisión masiva permite consumidor final desde Excel sin cliente precargado cuando la normativa no exige identificar receptor
- [x] Fecha de emisión explícita; no se asume fecha del día actual al emitir
- [x] Entradas de fechas fiscales validan calendario real y aceptan `DD/MM/AAAA`
  en bordes de usuario, además de formatos técnicos ISO/ARCA donde corresponde
- [x] Confirmación final obligatoria de fecha fiscal antes de solicitar CAE
- [x] Procesamiento de lotes exige token exacto de confirmación fiscal con
  fechas y puntos de venta validados, no un boolean genérico
- [x] La emisión valida que el punto de venta y el cliente opcional pertenezcan al
  emisor activo antes de solicitar CAE
- [x] Nueva factura, perfiles y emisión masiva ofrecen únicamente puntos
  técnicamente usables con acreditación RECE efectiva para el ambiente. La API
  bloquea numeración y toda continuación emitible antes de `FECAESolicitar`
  cuando falta la cabeza o el snapshot durable; Web Services genérico ya no
  acredita RECE
- [x] Emisión individual bloquea la vista previa hasta confirmar el próximo
  número, desacopla el cliente guardado si se editan sus datos y no informa
  fechas de servicio cuando el concepto fiscal es solo Productos
- [x] Uploads de lotes limitados por `BATCH_MAX_UPLOAD_BYTES` y XLSX
  malformados rechazados antes de validar
- [x] Uploads de certificados ARCA limitados por
  `CERTIFICATE_MAX_UPLOAD_BYTES` antes de persistir archivos nuevos
- [x] Claves privadas ARCA generadas por CSR creadas con permisos restrictivos
  desde la apertura del archivo y cifradas antes de persistirse
- [x] Concepto fiscal ARCA explícito; no se asume productos o servicios por defecto
- [~] Descripción/concepto facturado del ítem documentado como dato separado
  del concepto fiscal ARCA; debe venir del archivo o de un valor fijo confirmado
  para todo el lote, sin defaults ocultos
- [x] Numeración ARCA adelantada y fallos post-CAE quedan como
  `requiere_reconciliacion`, sin persistir respuestas no aprobadas como
  comprobantes emitidos
- [x] Cierre estructural de indisponibilidad de base alrededor de
  `FECAESolicitar`: pre-ARCA solo devuelve `503` cuando confirmó durablemente
  recuperación segura y cero intentos. La operación queda
  `interrumpida_pre_arca` y la misma clave reanuda por CAS con un único ganador;
  individual y lotes restauran el lote o grupo exacto. Con intento existente o
  recuperación no persistible responde `409 pre_arca_estado_bloqueado`, conserva
  la clave y exige revisar/esperar, sin reconciliación ARCA. El worker solo
  reencola sin intentos, conserva la operación `en_proceso` y corta el ciclo.
  Post-ARCA mantiene `409`, reconciliación y ausencia de retry. El cleanup no
  reemplaza la excepción primaria ni degrada un `409` a `503`; `IntegrityError`
  no cambia.
- [~] Auditoría Clawpatch 2026-07-12 completada sobre `repo`, `backend` y
  `frontend`, sin fixes ni llamadas ARCA. Los findings `high` ya fueron
  deduplicados, adjudicados por causa raíz y enrutados al portafolio. PF-01A.1,
  PF-01A.2, PF-01A.3 y el parche de seguridad de Pillow están publicados; la CI
  final quedó verde. El checkpoint integrado del 2026-07-13 revalidó R02, B03,
  B04 y B24 como `fixed` con `gpt-5.6-sol high`, sin `clawpatch fix` ni
  llamadas ARCA. El backlog restante continúa por causa raíz en
  `docs/agents/development-portfolio.md`.
- [x] PF-01B cerrado: vocabularios canónicos, constraints de
  estados/CAE/reservas y migración bloqueante sin normalización automática.
  SQLite, Alembic, PostgreSQL 16 efímero, concurrencia y backend completo
  quedaron verdes. El harness se publicó en `6625254`, cuya CI
  `29270728104` aprobó seguridad, backend, frontend y E2E; Clawpatch revalidó
  B10 y B17 como `fixed` con `gpt-5.6-sol high`.
- [x] **P1 fiscal - No bloquear emisiones legítimas por historia previa o
  actividad de otros sistemas.** El control original presuponía que la base local
  de FactuFlow contiene la secuencia fiscal completa y bloquea cuando
  `FECompUltimoAutorizado` informa un número diferente del último comprobante
  local. Esa diferencia puede ser normal: un emisor nuevo puede tener historia
  anterior y un emisor activo puede continuar facturando por otros sistemas.
  - La diferencia ARCA/FactuFlow debe mostrarse como información clara antes de
    emitir, con emisor, punto de venta, tipo, último local y último ARCA, pero no
    debe impedir la emisión por sí sola.
  - ARCA es la fuente de verdad para la numeración fiscal global; FactuFlow es
    la fuente de verdad de sus propios intentos, comprobantes, idempotencia y
    resultados inciertos. Si no existe una operación propia incierta, el próximo
    candidato debe calcularse desde `ultimo_arca + 1` en emisión individual y
    masiva.
  - Conservar el guardarraíl para causas reales: intentos propios `en_proceso` o
    `requiere_reconciliacion`, autorización propia sin persistencia local
    coherente, numeración local adelantada respecto de ARCA, replay conflictivo
    o respuesta ARCA ambigua.
  - La advertencia debe ofrecer la reconstrucción histórica opcional definida en
    el P2, sin convertirla en requisito para continuar.
  - No copiar el último número observado en ARCA a `numero_asignado` de un grupo
    sin reserva, intento fiscal ni CAE; exponerlo como dato diagnóstico separado.
  - Repetir el preflight inmediatamente antes de solicitar CAE. Como un sistema
    externo no comparte los locks de FactuFlow, tratar un rechazo explícito de
    consecutividad sin asumir éxito y nunca reintentar automáticamente una
    respuesta ambigua.
  - Criterios mínimos de aceptación: emisor nuevo con local `0` y ARCA `N`;
    emisión externa entre dos emisiones de FactuFlow; diferencia informada y no
    bloqueante; intento propio incierto; local adelantado; carrera con otro
    sistema; replay idempotente; flujo individual y lote; confirmación fiscal
    explícita; aislamiento por ambiente/emisor/punto/tipo; y garantía de que un
    bloqueo pre-ARCA no crea CAE ni comprobantes.
  - Antes de implementar, completar `docs/agents/fiscal-change-checklist.md`,
    documentar estados y orden de operaciones, definir la matriz de tests y
    revisar los caminos vecinos de idempotencia y reconciliación.
  - [x] **PF-02A — emisión individual:** diagnóstico local/ARCA, advertencia de
    historia externa, candidato `ultimo_arca + 1`, segundo preflight después de
    la reserva y aborto terminal con cero CAE si la numeración cambia o no puede
    reconfirmarse. Integrado mediante el PR `#15` (`c872497`). Diseño:
    `docs/agents/pf-02a-numeracion-individual-design.md`.
  - [x] **PF-02B — emisión masiva y worker:** aplicar la política a reservas de
    grupos y lotes sin copiar diagnósticos a `numero_asignado`, y cerrar la
    matriz de QA fiscal antes de considerar PF-02 completo.
    - [x] Primer corte integrado mediante el PR `#16` (`2c75fd2`): el núcleo
      batch acepta historia externa legítima, reserva un rango durable y repite
      `FECompUltimoAutorizado` antes de `FECAESolicitar`; un cambio o error
      aborta todo el sublote con cero CAE.
    - [x] Segundo corte integrado mediante el PR `#19` (`1a5e335`): ratificar y
      completar las transiciones de grupos y los reintentos manuales con
      cobertura específica. Admiten
      `arca_adelantada`, detienen la selección ante bloqueos, aborto del segundo
      preflight o incertidumbre post-ARCA, y preservan como reconciliable una
      autorización conocida aunque falle el cierre local.
    - [x] Tercer corte: la recuperación stale acepta diagnósticos `alineada` o
      `arca_adelantada` solo para pendientes realmente intactos, no asigna
      números ni crea intentos, conserva todo bloqueo propio y delega la reserva
      durable y el segundo preflight al procesamiento normal. PF-02 queda
      cerrado sin incorporar la reconstrucción histórica opcional de PF-05.
- [x] **PF-19 — Elegibilidad RECE, rechazo preautorización y cierre legacy
  seguro (P1 fiscal, Nivel 2).** La operación productiva sobre `v0.2.2`
  confirmó dos fallas de una misma frontera: FactuFlow puede considerar usable
  un punto cuyo sistema contiene `Web Services` sin demostrar que sea de tipo
  RECE, y un error global excluyente de `FECAESolicitar`, como `10005`, se
  degrada hoy a respuesta incierta aunque ARCA haya rechazado la cabecera antes
  de autorizar comprobantes. El resultado es doble: una solicitud evitable a
  ARCA y lotes/intentos bloqueados para reconciliación con un mensaje que no
  describe lo ocurrido.
  - **Prioridad y autoridad:** no hay evidencia de comprobantes incorrectos ni
    un P0, pero sí un P1 alcanzable en emisión individual y masiva. El manual
    oficial WSFEv1 clasifica `10005` entre las validaciones excluyentes de
    `FeCabReq` y exige que el punto de venta esté dado de alta y sea RECE. Esta
    evidencia productiva desplaza temporalmente PF-03B porque afecta una llamada
    fiscal real y deja estados operativos engañosos.
  - **Fronteras con líneas existentes:** PF-02 permanece cerrado y conserva sin
    cambios la numeración desde `ultimo_arca + 1`, las reservas y el segundo
    preflight. PF-03 continúa siendo dueño de la validez de entradas, ítems e
    importes. PF-09 provee constancias, sincronización y ambiente; PF-14 consume
    el contrato de error estructurado; PF-15 expone mensajes y trazabilidad; y
    PF-11 conserva la evidencia de backup y recuperación. PF-19 es dueño solo
    de la elegibilidad fiscal WSFE/RECE, la semántica de rechazos globales
    excluyentes y el cierre seguro de estados legacy creados por esta falla.
  - **Invariantes:** `es_webservice` no equivale a `compatible_rece`; un punto
    no verificado como RECE no puede alcanzar `FECAESolicitar`; una respuesta
    global solo puede tratarse como rechazo terminal cuando su código y contrato
    estén documentados como excluyentes; todo código desconocido, respuesta
    parcial, cardinalidad inconsistente, timeout o error de transporte continúa
    en `requiere_reconciliacion`; ningún saneamiento legacy inventa CAE,
    comprobantes ni historia; y todo diagnóstico permanece aislado por ambiente,
    emisor, punto de venta y tipo.
  - [x] **PF-19A — diseño y contención:** checklist fiscal, consumidores, tabla
    de estados y orden antes/durante/después de FECAE cerrados. Una lista JSON
    privada contiene tuplas explícitas por ambiente, emisor, ID/número de punto
    y tipo antes de crear intentos o solicitar CAE; el inventario legacy usa una
    transacción de solo lectura, salida sanitizada y ambiente histórico
    indeterminado. `10005` sigue siendo candidato incierto, no rechazo terminal,
    hasta PF-19C. No edita la base, no emite y no reemplaza PF-19B.
  - [x] **PF-19B — elegibilidad RECE end-to-end:** los cortes B.1, B.2 y B.3
    forman una única unidad cerrada en `main`. El ledger durable distingue
    `verificado_rece`, `no_rece` y `no_verificado`, conserva fuente, vigencia y
    revisión monotónica, migra legacy de forma fail-closed y aplica snapshots y
    guardas en individual, lotes, worker, fallback, reintentos y stale. Solo un
    administrador puede acreditar producción con una constancia fresca,
    confirmación explícita y señal exacta; la sincronización WSFE server-side
    nunca promueve RECE. API, badges, perfiles, Excel y selectores consumen el
    estado efectivo e invalidan confirmaciones obsoletas. Homologación permanece
    cerrada mientras no exista una fuente probatoria específica.
  - [x] **PF-19C — rechazo global y saneamiento legacy:** implementación, diseño
    y evidencia completos; la CI Nivel 2 aprobó PostgreSQL real, Runtime Smoke y
    los siete checks. La aceptación PF-16G fue registrada el 10/08/2026 y el
    candidato `7f7b3808` aprobó el ensayo privado de backup, restauración
    aislada, upgrade y rollback.
    El `autoreview` final autorizado cerró limpio con
    Codex `gpt-5.6-sol medium`. Solo `10005` entero exacto, una cabecera `R` estrictamente
    correlacionada, un único error y ausencia de detalle/CAE cierran un rechazo
    global. Lo desconocido, mixto, parcial o contradictorio queda en
    `requiere_reconciliacion`; no reintenta ni emite de nuevo. El cierre atómico
    inmoviliza el sublote enviado, detiene el lote y marca los remanentes como
    `no_enviado_por_rechazo_global`. El CAS liga cada publicación a su owner:
    una carrera `operacion_id A -> B` no permite que A publique o emita sobre B.
    La resolución legacy es `plan` read-only + `apply` con backup verificable,
    hash y journal append-only; consulta `FECompUltimoAutorizado` y solo usa
    `FECompConsultar` cuando corresponde. Ambiente legacy indeterminado obliga
    a contrastar ambos ambientes y cualquier duda conserva reconciliación.
  - **Matriz mínima:** punto RECE/no RECE/no verificable; constancia y
    sincronización con fuentes concordantes o contradictorias; punto fijo y por
    archivo; individual, batch y fallback unitario; error global `10005` antes
    de detalles; `R` por detalle; error global desconocido; respuesta parcial,
    timeout y caída de persistencia; replay idempotente; cambio de elegibilidad
    después de confirmar; aislamiento multiemisor; datos legacy; y comprobación
    explícita de cero CAE/comprobantes en todos los abortos preautorización.
  - **Criterio de cierre y release:** diseño, tests con dobles, migración/rollback
    cuando aplique, documentación, QA administrativa y revisión Nivel 2 deben
    quedar cerrados antes del próximo candidato productivo. No se probará el
    rechazo solicitando CAE real; la QA productiva se limita a lecturas seguras,
    estado visible y verificación de que solo aparecen puntos RECE confirmados.
- [ ] **P2 - Reconstrucción histórica opcional desde ARCA para informes con
  cobertura verificable.** Permitir consultar con `FECompConsultar` e importar
  snapshots fiscales de comprobantes emitidos fuera de FactuFlow. Esta función
  no solicita CAE, no emite y nunca es requisito para una nueva emisión.
  - No sincronizar automáticamente toda la historia al incorporar un emisor. El
    usuario debe elegir un alcance: último mes, desde el inicio del año, desde
    una fecha explícita, últimos `N` comprobantes o rango de números.
  - Aplicar un máximo configurable de consultas/importaciones por operación y
    mostrar una previsualización con rango candidato, cantidad máxima, campos
    disponibles, costo operativo aproximado y limitaciones de detalle. Si se
    alcanza el límite, guardar progreso y permitir continuar por tramos.
  - Las selecciones por fecha requieren una estrategia de exploración hacia
    atrás con límites; no asumir que consultar desde el número `1` es aceptable
    ni descargar miles de comprobantes sin confirmación explícita.
  - Persistir un journal durable e idempotente por ambiente, emisor, punto de
    venta, tipo y número, con estados de consulta/importación, concurrencia
    configurable, reanudación y bloqueo ante respuestas inconsistentes.
  - Guardar solo el snapshot fiscal devuelto por ARCA, con origen
    `arca_importado`, fecha fiscal original y
    `detalle_comercial_disponible=false`; no inventar ítems, descripciones,
    cantidades, precios ni PDFs.
  - Incluir los snapshots importados en informes fiscales y permitir filtrarlos
    por origen. Mostrar siempre la cobertura sincronizada por período y
    combinación fiscal, indicando si el informe es completo, parcial o tiene
    pendientes; nunca presentar como completa una historia que no fue consultada.
  - Criterios mínimos de aceptación: alcance temporal y por números; límite por
    operación; previsualización; cancelación y reanudación; importación repetida
    sin duplicados; comprobante existente igual o distinto; respuestas no
    encontradas o ambiguas; consumidor final sin documento; reportes sin ítems;
    cobertura parcial visible; y prueba controlada con rangos grandes sin
    crecimiento ilimitado de memoria o almacenamiento.
- [x] Idempotencia fiscal obligatoria para emisión individual, procesamiento de
  lotes y reintento de fallidos mediante `X-Idempotency-Key`, hash estable de
  payload y respuesta persistida.
- [x] Intentos de emisión fiscal durables antes de ARCA, con reserva de
  numeración, snapshot mínimo, CAE cuando exista y bloqueo de reintentos
  inciertos hasta reconciliar.
- [x] Intentos fiscales `en_proceso` vencidos se verifican con
  `FECompConsultar` antes de liberar numeración o vincular un comprobante
  autorizado.
- [x] Sincronización manual de puntos de venta ARCA validada desde UI y resuelta
  de forma transaccional por el servidor. WSFE crea o actualiza el estado
  técnico, pero nunca promueve elegibilidad RECE; la acreditación productiva
  exige la atestación administrativa separada de una constancia fresca
- [x] Validación de puntos de venta en emisión normaliza `Bloqueado=N`/`S` de ARCA
- [x] Factura C no informa objeto `Iva` en WSFE y bloquea ítems con IVA distinto de 0
- [x] Importes WSFE cuantizados con Decimal antes de solicitar CAE, evitando
  redondeo binario con float en totales, IVA, tributos y bases
- [x] Borrado físico de emisores restringido para preservar historial fiscal y
  operativo: usuarios quedan con `empresa_id` en `NULL`, y certificados,
  clientes, puntos de venta, comprobantes, lotes, formatos, perfiles e intentos
  fiscales quedan protegidos con claves foráneas `RESTRICT`, también en SQLite
  mediante `PRAGMA foreign_keys` por conexión
- [x] UI de puntos de venta valida el certificado activo del ambiente ARCA
  actual y la presencia de sus archivos locales antes de sincronizar WSFE
- [x] Emisor activo consistente por pestaña y API con rechazo de conflictos
  entre `X-Empresa-Id` y query legacy `empresa_id`
- [x] API `/api/usuarios` para administradores y `GET /api/auth/setup-status`
  para mostrar setup inicial solo si no hay usuarios
- [~] Endurecimiento de seguridad multiemisor para evitar mezcla de clientes,
  certificados, puntos de venta, comprobantes, lotes, PDFs, reportes, perfiles
  y formatos entre emisores
- [x] Excel observado de lotes escapa valores con forma de fórmula
- [x] Notas de crédito/débito informan comprobantes asociados en WSFE
  (`CbtesAsoc`) cuando corresponde
- [~] Alineacion limpia entre base legacy y Alembic
- [ ] Arquitectura de jobs robusta para procesos largos

### Frontend
- [x] Vue + Pinia + Router operativos
- [x] Dashboard, clientes, comprobantes, emisión masiva, reportes, certificados, puntos de venta y empresa operativos
- [x] Selector de emisor activo para operar varios CUITs desde un usuario
- [x] Selector de emisor activo visible con las opciones autorizadas para cada usuario activo
- [x] Pantalla `Usuarios` reservada a administradores para alta, edición,
  desactivación/reactivación y reseteo de claves
- [x] Integración visual controlada de identidad v01 cerrada en frontend
  público, acumulada en cortes pequeños y auditables hasta un checkpoint
  instalable en producción; no se despliegan microcortes estéticos por separado.
- [x] Diagnóstico UX específico de `/comprobantes/lotes` cerrado y rediseño
  secuencial documentado en `docs/agents/lotes-ux-redesign.md`. Cortes 1, 2,
  3 y 4 implementados en frontend: preparación/validación más directa, lote
  activo con resumen prioritario, detalles plegables, siguiente acción visible,
  resolución de pendientes como modo excepcional y navegación compacta de lotes
  recientes, sin tocar backend, ARCA, emisión, servicios, stores, rutas ni
  contratos.
- [ ] Cambio de contraseña propio para usuarios autenticados, sin intervención
  del administrador, validando contraseña actual y nueva contraseña
- [x] Secciones principales scopiadas por emisor activo y verificadas al
  cambiar el selector
- [x] Vistas sensibles descartan respuestas asincrónicas viejas al cambiar el
  emisor activo, incluyendo reportes, certificados, puntos de venta y
  numeración de nueva factura
- [x] El store de puntos de venta valida el emisor antes de mutar la lista tras
  un guardado tardío, incluso con ids locales coincidentes entre emisores
- [x] Certificados y puntos de venta no llaman endpoints scopiados sin emisor
  confirmado y cierran borrados/editores pendientes al cambiar de CUIT
- [x] Importación de constancias descarta notificaciones obsoletas al cambiar de
  emisor; la verificación de certificado bloquea reintentos concurrentes
- [x] Puntos de venta muestra badges `Verificado RECE`, `No RECE` y
  `No verificado`, procedencia y vigencia. La importación permite conservar la
  constancia sin acreditar o atestiguar expresamente su procedencia productiva;
  sincronizar con WSFE actualiza solo disponibilidad técnica
- [x] El selector de clientes cierra resultados anteriores cuando la búsqueda
  queda por debajo del mínimo o cambia mientras una request está en curso
- [x] Autodetección asistida de formato al subir Excel externo para emisión masiva
- [x] `Emisores > Carga masiva` incorpora subvista de `Plantillas` para crear,
  editar, clonar, desactivar, revisar compatibilidad y descargar Exceles
  visuales para usuarios no técnicos.
- [x] Nueva factura exige CUIT para Factura A y Notas A, y el refresco de lista
  posterior a CAE es no bloqueante
- [x] La emisión individual muestra un estado dedicado ante un `409` fiscal
  incierto, congela en memoria la clave y el payload, bloquea edición,
  cancelación, navegación y doble envío, conserva el pendiente ante un cambio de
  emisor y verifica exactamente la misma operación hasta un resultado final.
- [x] QA manual guiada de flujos reales
- [ ] Operaciones masivas de PDF desde listado

### Operación y plataforma
- [x] Arranque local simple con `run-local.ps1`
- [x] Launcher local Windows manual con icono en tray para desarrollo/QA
- [x] Perfiles Docker separados para local y producción
- [x] PostgreSQL definido como base recomendada para operación real
- [x] Comando administrativo para crear/promover usuario propietario
- [x] Alta inicial por UI solo cuando la instalación no tiene usuarios; altas
  posteriores desde menú `Usuarios`
- [x] Primera instalación privada en VPS con Docker producción, PostgreSQL y
  HTTPS validada
- [x] Herramienta privada de preparación de migración local a PostgreSQL/VPS con
  `preflight`, `export`, `import` y `validate`
- [x] Ensayo local de restauración en PostgreSQL con Docker: Alembic head,
  importación, validación de conteos/certificados/secuencias y healthcheck OK
- [x] Cierre operativo inicial del VPS: checkout limpio, configuración privada
  fuera de Git, servicios sanos y reverse proxy HTTPS funcionando
- [x] Backup manual inicial validado: dump PostgreSQL, certificados,
  configuración privada, copia cifrada fuera del VPS y restauración de prueba
  desde la copia cifrada
- [~] CI completo y confiable; despliegue productivo manual y explícito, sin
  CD automático
- [~] Observabilidad operativa estándar definida como requisito post-piloto
- [x] Gestor de almacenamiento administrativo para ver uso total y desglose por
  emisor, lotes, base, temporales, artefactos descargables, certificados y logs
- [x] QA visual local del gestor de almacenamiento con API mockeada, datos
  ficticios, E2E permanente y capturas privadas; no reemplaza la validación VPS
  con datos de prueba controlados
- [~] Observabilidad, backups manuales y políticas operativas iniciales
  parcialmente probadas; falta automatización, retención y recuperación a VPS
  nuevo

## Fase 0 - Fundacion y base técnica

Objetivo: tener un repo mantenible, ejecutable y documentado.

- [x] Repositorio, estructura base y guias para agentes
- [x] Backend y frontend levantables en local
- [x] Acceso local manual `FactuFlow Local.vbs` sin consola visible, con estado
  de backend, frontend y base de datos en tray
- [x] `.env.example` y configuración base
- [x] Documentación técnica inicial
- [~] Docker y compose alineados al estado real
- [x] Pipeline CI confiable para seguridad, backend, frontend y E2E
- [x] Corte versionado `0.2.0-mvp` y changelog como historial principal

## Fase 1 - Core funcional de negocio

Objetivo: poder operar una empresa y emitir comprobantes reales.

### Dominio principal
- [x] Empresa
- [x] Usuario y autenticacion
- [x] Clientes
- [x] Puntos de venta
- [x] Certificados
- [x] Comprobantes e ítems

### API y backend
- [x] Endpoints base para auth, clientes, empresa y comprobantes
- [x] Seguridad básica por empresa
- [x] PF-03A: el contrato superior de emisión individual rechaza claves
  desconocidas con `422` antes de idempotencia, intentos o ARCA; los snapshots
  batch no canónicos fallan cerrados al revalidarse
- [x] Generacion de PDF bajo demanda
- [x] PDF de comprobante con formato administrativo profesional, ubicación de
  elementos principales alineada a la factura oficial ARCA y QR ARCA testeado
  por payload decodificable
- [x] Reportes básicos de consulta
- [~] Consistencia documental completa de endpoints y contratos

### UX
- [x] Login
- [x] Dashboard
- [x] Formularios principales
- [~] Refinamiento de mensajes y ayudas contextuales
- [ ] Estados vacíos y recuperacion de errores totalmente pulidos

## Fase 2 - Integración ARCA real

Objetivo: dejar la emisión validada contra servicios reales.

### WSAA
- [x] Generacion de TRA
- [x] Firma y login CMS
- [x] Obtencion de Token y Sign
- [x] Cache persistente de tickets
- [x] Cache WSAA scopiado por certificado para que Token/Sign no se reutilicen
  entre certificados distintos del mismo CUIT y ambiente
- [ ] Política de invalidacion/rotacion mas robusta

### WSFEv1
- [x] `FECAESolicitar`
- [x] `FECAESolicitar` por sublotes usando `FECompTotXRequest.RegXReq`
- [x] `FECompUltimoAutorizado`
- [x] `FECompConsultar` útil para verificación
- [x] `FECompConsultar` acepta el número canónico `CbteNro` sin evaluar un
  fallback ausente y falla explícitamente si ARCA no devuelve ningún número
- [x] `FECompConsultar` usado para resolver intentos fiscales vencidos antes de
  liberar numeración o registrar una autorización pendiente.
- [x] El borde común de respuestas `FECAESolicitar` solo acepta `Resultado=A`
  con CAE ASCII de 14 dígitos y vencimiento calendario `YYYYMMDD`; rechaza
  parciales, estados desconocidos, errores globales y cardinalidades/rangos
  batch ambiguos. Un `R` completo permanece como rechazo verificable.
- [x] La emisión CAE individual retorna autorizaciones utilizables o rechazos
  `R` verificables; los resultados parciales y respuestas ambiguas quedan para
  reconciliación.
- [x] Toda excepción inesperada posterior a iniciar `FECAESolicitar`, individual
  o batch, produce una respuesta sanitizada `requiere_reconciliacion`. La API
  persiste el `409` idempotente cuando es posible y el replay con la misma clave
  no vuelve a emitir.
- [x] Validación de numeración y punto de venta en emisión: numeración,
  pertenencia, actividad, bloqueo, baja y elegibilidad RECE efectiva están
  cubiertos. Web Services genérico no acredita RECE y toda ruta emitible falla
  cerrado sin una cabeza/snapshot vigente.
- [x] Mapeo de `CondicionIVAReceptorId`
- [x] Validación local de ventana ARCA para fecha de emisión antes de emitir
- [~] Manejo fino de edge cases homologación vs producción

### Homologación
- [x] Certificado homologación emitido por WSASS
- [x] Autorización `wsfe` creada para CUIT representado
- [x] Smoke real individual
- [x] Smoke real masivo
- [x] QA manual completa desde UI
- [ ] Smoke repetible documentado como procedimiento de soporte

Los smokes marcados como hechos son evidencia histórica anterior a PF-19B. En
el estado actual de `main`, homologación no solicita CAE hasta incorporar una
fuente probatoria específica para ese ambiente.

### Producción
- [x] Piloto productivo real ejecutado con comprobantes autorizados
- [x] Certificado productivo cargado y prueba WSAA/ARCA exitosa
- [~] Certificados y proceso de producción
- [x] Certificados ARCA con paths gestionados dentro de `CERTS_PATH`, claves
  nuevas cifradas y un único certificado activo por emisor/ambiente
- [~] Checklist operativo post-piloto: fecha fiscal, punto de venta, backup,
  logs, restauración y evidencia sanitaria
- [ ] Validación sistemática de diferencias operativas entre homologación y producción

## Fase 3 - Emisión masiva como nucleo del producto

Objetivo: que FactuFlow sea realmente útil para operaciones administrativas de volumen.

### Lotes
- [x] Entidades de lote, grupo y filas
- [x] Plantilla Excel fija
- [x] Formatos de importación configurables por encabezado, columna o constante
- [x] Formato global para extractos bancarios con columnas `Fecha`, `Créditos`, `Leyendas Adicionales1`, `Leyendas Adicionales2` y `Pto Vta`
- [x] Formato particular local para emisor Responsable Inscripto privado
  (`Factura B IVA 21%`) con neto
  gravado como precio del ítem, total como referencia y consumidor final sin
  documento cuando corresponde
- [x] Formato particular local para emisor privado con Factura B IVA 21%,
  vinculado al perfil predeterminado del emisor, con `Imp. Neto Gravado` como
  neto del ítem e `Imp. Total` solo como control de consistencia
- [x] Validación de consistencia entre total informado por archivo externo y
  total calculado desde ítems e IVA antes de permitir emisión
- [x] Política explícita de fecha de emisión por lote: desde archivo o fecha fija confirmada
- [x] Fechas fijas de lote y reconciliación externa aceptan `DD/MM/AAAA` y
  rechazan calendarios inválidos antes de llegar a ARCA
- [x] Política explícita de concepto fiscal ARCA por lote: productos, servicios
  o definido por archivo
- [x] Lotes de productos no requieren fechas de servicio en el contrato
  multipart; servicios y conceptos definidos por archivo mantienen fechas
  explícitas cuando corresponde
- [x] Política explícita de descripción facturada del ítem por lote: desde
  archivo o valor fijo para todo el lote, independiente del concepto fiscal ARCA
- [x] Perfiles de carga masiva por emisor, con predeterminado, punto de venta y
  reglas relativas de fechas visibles, sin materializar fecha fiscal en emisión
  masiva sin una base explícita del usuario
- [x] Agrupacion por `comprobante_ref`
- [x] Prevalidacion por fila y por comprobante
- [x] Reintento seguro del mismo archivo cuando el lote previo no emitió CAE
- [x] Toma atómica del lote antes de emitir para evitar procesamiento concurrente
- [x] Fallos post-CAE quedan como `requiere_reconciliacion` y no habilitan
  reintentos automáticos
- [x] Cada grupo emitible de lote o reintento crea un intento fiscal durable
  asociado a la operación idempotente de usuario.
- [x] Duplicados lógicos de comprobantes se informan como advertencia con
  confirmación adicional; no son bloqueo automático ni forman parte del hash de
  idempotencia.
- [x] Gestión resolutiva de lotes parciales: reintento de fallidos con token de
  fecha fiscal, reconciliación externa verificada contra ARCA, descarte
  auditado de pendientes y cierre como `cerrado_reconciliado` o
  `cerrado_con_descartes`
- [x] Comprobantes emitidos fuera de FactuFlow pueden registrarse con
  `origen_emision = arca_web` solo después de validar tipo, punto de venta,
  número, receptor, fecha, total y CAE con `FECompConsultar`; un mismo
  comprobante no puede cerrar más de un grupo local
- [x] Compactación de lotes cerrados para ahorrar almacenamiento: elimina filas
  originales del Excel y conserva resumen, grupos, comprobantes y auditoría
- [x] Eliminación física permitida solo para lotes sin comprobantes emitidos ni
  incertidumbre fiscal; los eventos operativos quedan preservados
- [x] Confirmación fiscal final de lotes usa token exacto derivado de los grupos
  validados: fechas y puntos de venta concretos
- [x] Archivos XLSX malformados o por encima de `BATCH_MAX_UPLOAD_BYTES` quedan
  rechazados antes de crear o validar lotes
- [x] Snapshot fiscal del receptor en comprobantes
- [x] Persistencia de fechas de servicio y vencimiento de pago en comprobantes
  nuevos y backfill desde payloads históricos de lotes para reflejarlas en el
  PDF
- [x] Clientes precargados opcionales para lotes masivos
- [x] Emisión de lotes chicos desde UI observable por background/polling
- [x] Ejecución asincrónica para lotes grandes
- [x] Worker evita reencolar lotes activos y ya no reemite lotes `procesando`
  stale: primero intenta reconciliación local respaldada por un intento fiscal
  autorizado del mismo lote/grupo con comprobante, número, CAE y datos fiscales
  coherentes; luego solo reencola pendientes intactos si el diagnóstico por
  emisor, punto de venta y tipo es `alineada` o `arca_adelantada` y no existe
  incertidumbre propia. No asigna número ni crea reserva durante la recuperación;
  el procesamiento normal repite el preflight. Si hay evidencia fiscal, intento
  previo o preflight no concluyente, bloquea como
  `requiere_reconciliacion`. Si el bloqueo de un stale falla, no avanza con
  lotes `en_cola` en ese ciclo.
- [x] La API comprueba que el worker embebido esté disponible antes de crear
  idempotencia o mover un lote a `en_cola`; si no lo está responde `503` sin
  solicitar CAE
- [x] Emisión masiva por sublotes ARCA para grupos con mismo punto de venta y
  tipo, con fallback unitario explícito si `RegXReq` no está disponible
- [x] Contención frontend post-incidente productivo de lote grande: el
  seguimiento ya no presenta fallas temporales de resumen/detalle como lote
  inexistente, el polling evita ciclos solapados y baja frecuencia. No cambia
  emisión, ARCA, CAE, numeración, worker ni backend.
- [x] Robustez estructural post-incidente de lote grande: polling allowlist
  adaptativo y no solapado, sesiones API lazy, pool PostgreSQL API máximo `4`
  sin overflow, pool worker dedicado `1`, health administrativo sanitizado y
  prueba real de saturación PostgreSQL `4 + 1` sin datos fiscales ni ARCA. El
  despliegue y el registro concreto en el runbook privado siguen siendo acciones
  operativas explícitas, no parte de este cierre local.

### UX de lotes
- [x] Wizard de emisión masiva
- [x] Rediseño UX secuencial de `/comprobantes/lotes` documentado en
  `docs/agents/lotes-ux-redesign.md`: reducir onboarding persistente, agrupar
  configuración fiscal, acercar `Validar lote` al cierre de requisitos, tratar
  reconciliación como modo excepcional y compactar `Lotes recientes`. Cortes 1,
  2, 3 y 4 implementados como cambios frontend-only.
- [x] Preseleccion del formato sugerido con alta confianza antes de validar
  archivos externos
- [x] Confirmación de fecha de emisión y fechas de servicio antes de validar
- [x] Modal final de advertencia antes de emitir: confirma fecha fiscal y avisa
  que luego no se podran emitir comprobantes con fecha anterior para ese mismo
  punto de venta
- [x] Confirmación de concepto fiscal ARCA antes de validar; si viene del archivo, todas las filas deben indicar `Producto` o `Servicio`
- [x] Confirmación de descripción/concepto facturado del ítem antes de validar:
  desde archivo o texto fijo para todo el lote
- [x] Selector de perfil de carga masiva en emisión masiva, con aplicacion
  automática cuando el emisor tiene uno solo o uno predeterminado
- [x] Selector de punto de venta en perfiles y emisión masiva: usar el punto del
  archivo o fijar uno técnicamente usable y `verificado_rece` para el ambiente
  del emisor activo. Los puntos sin acreditación vigente quedan excluidos y la
  validación por archivo falla cerrado por grupo
- [x] Si el usuario modifica una configuración precargada por perfil de carga
  masiva, el lote se valida sin snapshot de perfil aplicado
- [x] Separacion clara entre validar lote y emitir comprobantes válidos
- [x] Resumen previo a emisión con neto, IVA 21%, IVA 10,5% y total de
  comprobantes listos para emitir
- [x] Detalle de lotes grandes con resumen completo y grupos paginados desde
  backend para evitar renderizar miles de comprobantes en una sola pantalla
- [x] Mensajes básicos de validación
- [~] Pulido de ayudas, tooltips y lenguaje administrativo
- [x] Descarga de archivo observado validada manualmente
- [x] PDF de comprobante rediseñado con ubicaciones principales similares a la
  factura oficial ARCA, sin copiar identidad visual oficial, con datos
  fiscales, CAE, QR, detalle y totales organizados profesionalmente
- [x] QA manual local del formato global de extracto bancario sin emitir
- [x] QA visual local del selector obligatorio de fechas fiscales en lotes
- [x] QA visual local de descripción/concepto facturado del ítem independiente
  del concepto fiscal ARCA, sin defaults ocultos
- [x] QA visual local de perfiles de carga masiva: crear, editar, eliminar,
  predeterminar, autoaplicar, modificar antes de validar y verificar modal final
  de fecha fiscal sin emitir
- [x] Preparacion y validación segura sin emisión de lote de Nota de Crédito C
  para anular duplicados productivos
- [x] Emisión y verificación por consulta ARCA de 19 Nota de Crédito C para
  anular duplicados productivos
- [x] Preparacion y validación segura sin emisión de 1113 Nota de Crédito B
  para corregir Factura B de un emisor privado emitidas con total usado como neto
- [~] QA manual especifica de formatos particulares por emisor
- [ ] Descarga de archivo observado con errores mas amigable
- [x] Progreso real de lotes con barra, timer, ETA, emitidos, fallidos y pendientes
- [x] Aviso visible cuando un lote degrada a modo unitario porque ARCA no
  informó `RegXReq`
- [x] Panel de resolución en lotes para reintentar fallidos, reconciliar
  comprobantes emitidos en ARCA Web, descartar pendientes visibles, compactar
  lotes cerrados o eliminar lotes sin emisión, con resolución excepcional
  agrupada visualmente bajo `Resolver pendientes`

### Operación masiva posterior a la emisión
- [ ] Descarga masiva de PDFs en ZIP generado bajo demanda y sin persistencia
  permanente en VPS
- [ ] Selección multiple en listado de comprobantes
- [ ] Preparación asincrónica de PDFs para lotes grandes con limpieza de
  temporales después de la descarga o vencimiento operativo
- [ ] Trazabilidad de tareas masivas iniciadas por usuario

## Fase 4 - UX administrativa no técnica

Objetivo: reducir al mínimo la necesidad de soporte técnico para operar.

- [x] Uso de espanol claro en pantallas core
- [x] Eliminacion de `alert()` y `confirm()` nativos en flujos principales
- [~] Mensajes accionables en errores de negocio
- [x] Mensaje claro en login cuando el backend local no responde
- [ ] **PF-17 — Conectividad consciente y recuperación segura:** informar de
  forma no invasiva cuando el navegador pierde red, el servidor de FactuFlow no
  responde o una vista diferida no puede cargarse. Debe combinar una señal
  global persistente con mensajes accionables al navegar, distinguir
  `Sin conexión`, `Servidor no disponible`, `Conexión inestable` y
  `Recuperando`, y confirmar cuando la comunicación se restablece.
  - Mantener un costo mínimo: reutilizar healthchecks livianos solo con la
    pestaña activa, pausar comprobaciones en segundo plano y aplicar backoff
    ante fallos; no incorporar servicios externos, telemetría pesada ni polling
    agresivo.
  - Tratar el estado del navegador solo como indicio y confirmar la
    disponibilidad de FactuFlow mediante su healthcheck y los errores reales de
    API o navegación.
  - No convertir FactuFlow en una aplicación offline: no cachear ni persistir
    formularios, payloads, CUITs, CAEs, comprobantes o evidencia privada; no
    crear colas locales ni service workers que reenvíen operaciones.
  - Prohibir reintentos automáticos de escrituras y de cualquier camino fiscal.
    Si una emisión pudo cruzar la frontera irreversible, conservar el flujo de
    verificación/reconciliación y no recomendar recargar, cerrar ni volver a
    emitir. Solo los healthchecks y lecturas expresamente seguras pueden
    reintentarse de forma controlada.
  - Reutilizar los avisos y el diseño actuales, contemplar accesibilidad para
    cambios de estado y cubrir pérdida/recuperación, `502/503/504`, timeout,
    fallo de chunk y ausencia de duplicación de avisos.
  - Pertenece a la banda C del portafolio y depende de PF-14/PF-15 y de las
    garantías fiscales vigentes. No forma parte de las prioridades inmediatas
    ni debe desplazar PF-03, PF-06/PF-07, PF-08 o PF-09.
- [~] Ayudas contextuales en pantallas sensibles
- [ ] Ayuda contextual para el constructor de plantillas de carga masiva:
  enlace visible, guía paso a paso, explicación de los orígenes y la
  compatibilidad, ejemplo completo, fechas en `DD/MM/AAAA` y preservación del
  formulario mientras se consulta la ayuda. Tratar como un corte PF-17
  posterior a estabilizar los contratos de plantillas y validación de PF-03,
  sin incorporarlo a las prioridades inmediatas ni ampliar el alcance fiscal de
  PF-03.
- [~] Pantalla de estado del sistema dentro del frontend
- [ ] Integración formal entre launcher local y UI web
- [ ] Tooltips y microcopy sistematizados en toda la app
- [ ] Checklists previos a la emisión
- [ ] Vistas vacías guiadas
- [ ] Confirmaciones claras para acciones sensibles
- [x] Checkpoint visual v01 instalable en producción cerrado: shell,
  componentes base/comunes, auth/setup, dashboard, clientes, usuarios, reportes
  y certificados quedaron alineados con identidad v01 sin tocar backend, ARCA,
  emisión ni lotes fiscales. El despliegue productivo sigue requiriendo decisión
  explícita contra un commit o tag identificable.
- [ ] Pantalla o sección `Mi cuenta` para que cada usuario cambie su propia
  contraseña
- [ ] Revision completa de accesibilidad y legibilidad

## Fase 5 - Datos, migraciones y estabilidad

Objetivo: que el proyecto soporte evolución sin deuda estructural peligrosa.

### Base de datos
- [x] Modelos principales definidos
- [x] Migración inicial de esquema creada
- [x] Modelos versionados de formatos de importación y trazabilidad del mapeo usado por lote
- [~] Estrategia de convivencia con DB local legacy
- [~] Stamping/migración limpia de instalaciones existentes
- [x] Export/import privado v2 desde SQLite quiescent a PostgreSQL limpio,
  preservando configuración, certificados, formatos, perfiles, comprobantes,
  ítems, elegibilidad RECE y operaciones terminales. Solo excluye
  intentos/guardas/lotes/eventos cuando el preflight demuestra que no hay estado
  no terminal, incierto o necesario para continuar.
- [ ] Política clara de seeds y datos de desarrollo

### Calidad y testing
- [x] Suite backend activa
- [x] E2E frontend con Playwright confiable para Chromium desktop local
- [x] Smoke real de homologación ejecutado manualmente
- [x] QA manual funcional cerrada
- [x] Script de lint frontend no destructivo `npm run lint:check`
- [x] Migrar el entorno de build/test del frontend y CI a Node.js 24 LTS,
  validando `npm ci`, `type-check`, `lint:check`, `build` y `test:unit`, y
  documentando la versión recomendada para desarrollo local. El corte actualizó
  de forma compatible Vite, Vitest, ESLint y `vue-tsc`, y dejó auditorías npm de
  producción y desarrollo sin vulnerabilidades; no se usó `npm audit fix --force`.
- [x] Reparaciones Clawpatch 2026-05-16/17 cerradas con
  backend/frontend/repo en `openFindings=0`
- [x] Auditoría Clawpatch 2026-07-05 cerrada nuevamente con repo completo,
  backend y frontend en `openFindings=0`, `autoreview` GPT-5.5 alto limpio y
  CI remoto aprobado
- [~] Ciclo Clawpatch 2026-07-07/10 cerrado para `v0.2.1`: 3 findings backend
  y 9 frontend objetivo revalidados como `fixed`, sin críticos/altos aceptados
  pendientes. El registro acumulativo local conserva repo 0, backend 85 y frontend 6 abiertos
  `medium`/`low`, con históricos, duplicados y contaminación de alcance; el
  triage manual continúa después del P1 fiscal vigente.
- [x] Reportes IVA calculan notas de crédito con signo negativo, incluyen
  comprobantes C con IVA cero como exentos, ítems A/B con IVA cero como no
  gravados y el detalle de subdiario incluye gravado e IVA 27%
- [x] Corregir setup E2E para que `npm run test:e2e` vuelva a ser evidencia
  confiable en auditorías locales de escritorio
- [ ] Cobertura más profunda sobre detalles de comprobantes, PDF y reportes
- [ ] Smoke automatizado de stack completo local

#### PF-16 — Programa transversal de garantía de calidad

Objetivo: que una persona contadora sin conocimientos de programación pueda
mantener, evaluar y eventualmente ofrecer FactuFlow a otros profesionales con
evidencia comprensible de que cada versión preserva la seguridad fiscal,
funcional y operativa. La cantidad de tests o la afirmación de un agente no son
garantía suficiente por sí solas: cada release debe demostrar los requisitos,
los fallos ensayados, los riesgos residuales y la recuperación disponible.

Los controles se aplican por **riesgo y momento de integración**, no solamente
por cantidad de líneas. Un cambio pequeño sobre fecha fiscal, numeración o
idempotencia puede ser crítico; una serie amplia de correcciones editoriales
puede requerir únicamente controles livianos.

##### Clasificación obligatoria del cambio

- **Nivel 0 — editorial o visual aislado:** documentación, textos, tildes,
  estilos sin comportamiento, metadatos y mantenimiento que no altere runtime.
  Requiere revisión del diff y validación enfocada; no exige suite completa,
  QA integral ni `autoreview`.
- **Nivel 1 — funcional no crítico:** CRUD administrativo, UX, reportes,
  transformaciones o servicios que no puedan emitir, mezclar emisores, cambiar
  permisos, perder evidencia fiscal ni modificar datos irreversiblemente.
  Requiere tests del área, lint/type-check/formato aplicable y smoke del flujo
  visible cuando corresponda. La suite completa se reserva para cerrar la
  unidad lógica o integrarla.
- **Nivel 2 — sensible o fiscal crítico:** ARCA/WSAA/WSFE, CAE, fecha fiscal,
  numeración, receptor, tipo o total del comprobante, idempotencia, reintentos,
  reconciliación, lotes, concurrencia, aislamiento multiemisor, autenticación,
  autorización, certificados, secretos, migraciones, borrados, backups,
  restauración o exportación de datos fiscales. Exige diseño de invariantes,
  checklist fiscal o de seguridad aplicable, matriz de errores y concurrencia,
  tests definidos antes o junto al código y revisión de cierre.

Si existe duda entre dos niveles, se usa el nivel superior hasta justificar por
escrito la clasificación menor. La clasificación debe quedar en el diseño,
commit, PR o dossier de release, según el tamaño de la unidad.

##### Puertas proporcionales

1. **Durante microcambios:** ejecutar solo pruebas y controles enfocados. No
   correr toda la suite, QA manual completa, Clawpatch ni `autoreview` por cada
   edición intermedia.
2. **Al cerrar una unidad lógica o antes de un push funcional relevante:**
   congelar alcance; ejecutar la suite completa de las áreas afectadas;
   comprobar lint, formato, tipos, build, archivos privados y documentación;
   y usar `autoreview` cuando el cambio sea importante o sensible, manteniendo
   la confirmación explícita vigente.
3. **Antes de crear una versión candidata:** ejecutar la matriz integral de CI,
   integración PostgreSQL, smoke de stack completo, controles de seguridad,
   cobertura y QA contable en lenguaje funcional. No puede quedar un P0 ni un
   P1 bloqueante conocido dentro del alcance.
4. **Antes de publicar o desplegar:** identificar commit y tag exactos, verificar
   backup/restauración y migraciones cuando apliquen, cerrar notas de release,
   documentar riesgos residuales y obtener autorizaciones separadas para tag,
   publicación y despliegue. Una prueba con CAE real requiere siempre decisión
   fiscal explícita.

##### Cortes de implementación

- [x] **PF-16A — Política ejecutable y evidencia simple:** la clasificación por
  riesgo, la evidencia comprensible para una persona contadora y la plantilla
  de PR quedaron vigentes en `docs/agents/change-quality-gates.md` y
  `.github/pull_request_template.md`.
- [x] **PF-16B — Protección de `main` sin burocracia innecesaria:** `main` exige
  PR y seis checks actualizados también al administrador, sin requerir un
  segundo aprobador. Force-push y borrado están deshabilitados; los cambios
  Markdown/`.gitignore` conservan jobs visibles mediante un recorrido Nivel 0
  liviano. La configuración quedó verificada el 2026-07-27 con el PR `#14`.
- [x] **PF-16C — CI como barrera real:** la barrera ejecuta Ruff,
  Black, tests backend, type-check, lint, build, unit tests frontend, tests de
  scripts, E2E y auditorías bloqueantes de dependencias productivas; también se
  retiró Pylint decorativo. La alineación documental agrega una revisión
  semántica antes del commit/PR y un control estructural que corre también en
  Nivel 0. La ejecución `30305581217` aprobó los seis jobs de la barrera básica.
  El toolchain Node.js 24, las auditorías npm, el resumen de cobertura y los
  artefactos de diagnóstico quedan incorporados. La evidencia CI del commit
  candidato sigue siendo una puerta de release, no una tarea pendiente de PF-16C.
- [x] **PF-16D — Cobertura medible y progresiva:** backend y frontend tienen una
  línea base con gates incrementales (`69%` total branch-aware backend;
  `56/50/43/57` frontend) y resúmenes/artefactos de CI. Los núcleos fiscales
  modificados conservan sus invariantes y pruebas específicas.
- [x] **PF-16E — Integración reproducible:** CI usa PostgreSQL 16 desechable con
  guard destructivo exacto para migraciones, constraints, concurrencia, pool,
  integridad PF-01/PF-19 y paquete VPS v2; incorpora Runtime Smoke de frontend,
  backend y base. ARCA se mantiene simulada o contractual. El smoke PostgreSQL
  real aprobó en la CI Nivel 2 del SHA funcional `e9c583a8174ea8edc6fe30845584033feab0394d`.
- [ ] **PF-16F — Pruebas avanzadas dirigidas por riesgo:** incorporar pruebas
  basadas en propiedades para fechas, importes, redondeos, archivos de entrada,
  idempotencia y máquinas de estados; pruebas de mutación acotadas a núcleos
  fiscales; entradas inesperadas y archivos malformados; y pruebas de carga y
  resistencia prolongada para lotes, worker y pools. Ejecutarlas de forma
  programada o en candidatos de release, no en cada microcambio.
- [x] **PF-16G — QA contable y dossier de release:** la matriz y el dossier de
  `v0.3.0` ya expresan escenarios de aceptación en español y términos contables,
  con datos sintéticos, resultados esperados, riesgos, migración y rollback.
  La CI Nivel 2 del SHA funcional y la aceptación funcional-contable del
  10/08/2026 ya aprobaron. La autoridad
  funcional-contable valida el resultado; los agentes y herramientas validan la
  implementación.
- [ ] **PF-16H — Puerta para ofrecer FactuFlow a terceros:** antes de anunciar
  una versión apta para otros contadores, cerrar auditoría multiemisor,
  autenticación/autorización, certificados y secretos, instalación limpia,
  actualización, backup, restauración hacia un entorno nuevo, observabilidad,
  soporte, compatibilidad y procedimiento de respuesta ante incidentes. Una
  release puede seguir siendo gratuita sin reducir estas garantías.

##### Secuencia y alcance de las puertas

- **Base previa al próximo cambio funcional no trivial:** PF-16A, PF-16B y la
  barrera básica de PF-16C quedaron cerradas el 2026-07-27 mediante el PR `#14`.
- **Candidato `v0.3.0`:** la CI Nivel 2 aprobó PostgreSQL/Runtime Smoke, la
  aceptación PF-16G fue registrada el 10/08/2026 y el ensayo privado de
  backup/restauración/upgrade/rollback quedó aprobado. El `autoreview`
  autorizado cerró limpio con Codex `gpt-5.6-sol medium`. Tag, publicación y
  despliegue siguen como decisiones separadas.
- **Antes de ofrecer una release a terceros:** cerrar PF-16F en los núcleos
  críticos y completar PF-16H junto con PF-06/PF-07, PF-08/PF-09, PF-11,
  PF-15 y PF-18 que correspondan.
- Los controles periódicos o de release no convierten cada commit en una
  auditoría total. Una unidad Nivel 2 sí conserva sus puertas fiscales aunque
  el diff sea pequeño.

### Robustez
- [x] Jobs de lotes persistidos en BD con ventana stale segura: la ventana ya
  no habilita reemisión automática, sino bloqueo y reconciliación; los grupos
  emitibles remanentes quedan marcados como inciertos.
- [x] Reintentos bloqueados cuando existe incertidumbre post-ARCA
- [ ] Reintentos controlados para otros procesos largos
- [x] Idempotencia fiscal obligatoria y visible para usuario final en caminos de
  CAE: misma clave y mismo payload no reemiten; misma clave con otros datos
  devuelve conflicto; clave ausente se rechaza.
- [ ] Auditoria de eventos operativos críticos

## Fase 6 - Multiemisor con emisor activo

Objetivo: permitir que contadores independientes o estudios chicos administren
varios emisores desde una misma instalación, operando siempre un emisor activo
explícito por vez. No incluye, por ahora, administración central compleja,
permisos finos por organización, reportes globales consolidados ni operación
simultánea entre emisores.

- [x] Header `X-Empresa-Id` para usuarios autenticados activos
- [x] Selector de emisor activo en frontend
- [x] Administradores operativos con acceso a todos los emisores configurados
- [x] Base vigente de usuarios comunes restringidos a un emisor asignado
- [x] Alta básica de nuevos emisores desde UI admin
- [x] Configuración de perfiles de carga masiva desde `Emisores > Carga masiva`,
  incluyendo punto de venta por archivo o punto fijo técnicamente usable del
  emisor, sin acreditar RECE ni activar una contención PF-19A no declarada
- [x] Precarga de emisor desde constancia de inscripcion ARCA en PDF,
  constancia de inscripción de persona física y constancia de opción de
  Monotributo, con provincia validada contra catálogo argentino
- [x] Importación de constancia ARCA de puntos de venta con domicilio y nombre fantasia
- [x] Re-scopeo de dashboard, clientes, comprobantes, emisión masiva,
  reportes, certificados, puntos de venta y nueva factura por emisor activo
- [x] Scoping backend de emisión contra punto de venta y cliente del emisor
  activo
- [~] Modelo multiemisor validado con mas de un emisor real de prueba
- [ ] Auditoria de aislamiento entre emisores en certificados, puntos de venta,
  clientes, comprobantes, lotes, PDFs, reportes, perfiles y formatos
- [ ] Tests de regresión multiemisor para operaciones críticas antes de ampliar
  volumen productivo
- [ ] Onboarding multiemisor mas claro para contadores y estudios chicos
- [ ] **PF-06/PF-07/PF-08 — operadores multiemisor y creación/edición
  delegada.** Implementar el diseño canónico de
  `docs/agents/pf-06-08-permisos-multiemisor-design.md` como una unidad Nivel 2
  end-to-end, sin introducir un tercer rol ni permisos por módulo.
  - **Alcance funcional:** cada operador tendrá cero, uno o varios emisores
    asignados. Un checkbox administrativo `Puede crear y editar emisores`
    habilitará crear nuevos emisores y editar únicamente los ya asignados. El
    borrado, la gestión de usuarios, `Sistema`, almacenamiento y plantillas
    globales seguirán reservados a administradores.
  - **Regla de creación:** crear empresa, conceder acceso operativo al creador y
    registrar auditoría será una sola transacción. Si cualquier paso falla, no
    quedará empresa ni asignación parcial. El administrador podrá revocar luego
    ese acceso; haber creado el emisor no generará propiedad permanente.
  - **Regla de edición:** un operador necesitará simultáneamente la capacidad y
    una asignación vigente al emisor. La autorización será backend, por objeto y
    releída desde base; la UI no será autoridad. Las restricciones actuales de
    identidad fiscal e historial continuarán aplicándose también al operador.
  - **Modelo y migración:** PF-06A incorporará una relación many-to-many
    usuario-emisor con constraint único y backfill desde `usuarios.empresa_id`.
    La nueva tabla será la única fuente de autorización; la columna legacy podrá
    sobrevivir transitoriamente solo como compatibilidad no autoritativa hasta
    retirar todos sus consumidores y ensayar rollback en SQLite/PostgreSQL.
  - **Concesión administrativa:** PF-08A ampliará contratos y pantalla `Usuarios`
    con selector múltiple, checkbox, asignación/revocación transaccional,
    previsualización al degradar administradores y eventos sanitizados. La
    opción `Seleccionar todos` materializará solo emisores actuales; no otorgará
    acceso automático a emisores futuros.
  - **Frontend y revocación:** PF-07A mostrará únicamente emisores devueltos por
    la API, conservará uno activo por vez y descartará estado o respuestas
    tardías cuando cambie o se revoque el alcance. Una sesión abierta no
    conservará autoridad por datos cacheados, Pinia, storage o JWT.
  - **Procesos fiscales:** la autorización se verificará al iniciar o confirmar
    la operación y otra vez antes de una transición diferida que aún pueda
    alcanzar ARCA. Una revocación pre-ARCA bloqueará sin CAE; una revocación
    posterior no inventará rollback y conservará PF-01, idempotencia y
    reconciliación.
  - **Concurrencia y auditoría:** edición, creación, cambios de capacidad y
    revocación deberán tener orden determinista mediante locks, versión de
    permisos o mecanismo equivalente. Registrar actor, usuario, emisor, origen
    y altas/bajas sin exponer CUIT completo ni datos privados.
  - **Matriz mínima:** migración legacy; cero/uno/varios emisores; acceso A/B y
    rechazo C por header, query, body e ID; creación y autoasignación atómicas;
    edición con capacidad más asignación; revocación al creador; borrado negado;
    promoción/degradación; carreras; sesión abierta; worker/lotes antes y
    después de la frontera ARCA; aislamiento de todos los recursos; UI y
    PostgreSQL/SQLite, siempre con datos sintéticos y sin CAE real.
  - **Propiedad y orden:** PF-06 será dueño del modelo y la autorización backend;
    PF-08 de la concesión administrativa; PF-07 del selector y estado frontend.
    Se ejecutará como primera unidad vertical de ese bloque después de PF-19 y
    PF-03B, sin solaparse con la validez fiscal de PF-03, la elegibilidad RECE de
    PF-19 ni las sesiones/cambio de contraseña restantes de PF-08.

## Fase 7 - Plataforma lista para despliegue serio

Objetivo: que FactuFlow pueda instalarse y operarse con menor riesgo técnico.

### Contenedores y despliegue
- [x] Dockerfiles y compose existentes
- [x] `docker-compose.yml` para local/desarrollo
- [x] `docker-compose.prod.yml` para VPS/producción con PostgreSQL
- [x] Instalación real en VPS con `docker-compose.prod.yml`
- [~] Variables de entorno cerradas por ambiente
- [~] Guía de despliegue local y servidor
- [x] Runbook de migración local a VPS documentado en
  `docs/setup/vps-migration.md`
- [x] Flujo público de desarrollo, versionado, despliegue manual y auditoría
  productiva documentado en `docs/agents/production-workflow.md`
- [x] Reverse proxy y TLS validados en una instalación privada

### Operación
- [ ] Logs operativos con identificador de seguimiento por emisor, usuario,
  lote/comprobante, job y error local o ARCA
- [ ] Retencion de logs privados definida por entorno
- [ ] Política de almacenamiento mínimo para VPS: temporales, PDFs, ZIPs,
  archivos observados y artefactos no vitales con limpieza controlada
- [x] Primera acción de limpieza segura sobre lotes: compactación de detalle de
  filas en lotes cerrados y borrado restringido de lotes sin emisión
- [x] Gestor de almacenamiento para administradores, con uso total de la
  instalación, desglose por emisor y tipo de dato, alertas simples de consumo y
  acciones seguras de limpieza sobre artefactos no vitales
- [~] Healthchecks claros para backend, base, worker, ARCA y certificado del
  emisor activo: worker y pools ya tienen diagnóstico administrativo sanitizado;
  faltan backup y consolidación de las señales restantes
- [~] Backup y restauración de base y certificados: prueba manual validada,
  automatización y retención pendientes
- [ ] Evidencia exacta de backup preoperación, enrutada a PF-11/PF-15: cada
  respaldo usado para una acción fiscal crítica debe registrar propósito,
  timestamp, estado/commit objetivo y ausencia o enumeración de escrituras
  intermedias. Un dump anterior o nombrado para otra operación no puede
  presentarse como snapshot inmediato sin esa trazabilidad.
- [ ] Automatización de backups cifrados con validación periódica, política de
  retención, destino externo y alertas de fallo
- [ ] Runbook completo de recuperación a un VPS nuevo desde repositorio limpio,
  backup cifrado y configuración privada
- [x] Definir si los certificados productivos se migran desde local al VPS o si
  se generan certificados nuevos para el servidor: se migran solo como reemplazo
  del entorno local, con preflight obligatorio, archivos completos en
  `CERTS_PATH` y re-cifrado de claves privadas para producción
- [ ] Política de manejo de secretos

### Diagnostico operativo simple
- [x] Decisión de observabilidad operativa estándar documentada en
  `docs/agents/operational-observability.md`
- [~] Pantalla `Estado del sistema` en la interfaz, con estados simples como
  `Correcto`, `Necesita atención` y `No disponible`: integra API, base, worker y
  pools, certificado local, ARCA manual, almacenamiento, guía rápida de soporte
  y ficha sanitizada; faltan backup y trazabilidad histórica más completa
- [x] Vista administrativa de almacenamiento integrada al diagnóstico operativo,
  sin escaneos pesados ni exposición innecesaria de datos privados
- [ ] Trazabilidad visible de lotes, reintentos, estados parciales y
  reconciliaciones, distinguiendo aborto antes de FECAE, rechazo ARCA explícito,
  autorización conocida e incertidumbre real; PF-19C define la taxonomía fiscal
  y PF-15 su exposición operativa.
- [ ] Mensajes de error con explicacion simple, impacto y próximo paso seguro
- [ ] Señal global liviana de conectividad y recuperación segura para usuarios,
  planificada en PF-17 y coordinada con los contratos de errores de PF-14 y la
  salud operativa de PF-15; no implica operación offline ni reintentos fiscales.
- [~] Runbook de diagnostico para soporte y usuarios administrativos: guía y
  ficha visibles en `Sistema > Estado`, más primer runbook público sanitizado en
  `docs/agents/support-runbook.md`; quedan pendientes la señal de backup y la
  documentación privada por instalación
- [ ] Metricas y alertas avanzadas, después de estabilizar VPS

## Fase 8 - Distribución, releases y adopción

Objetivo: profesionalizar la entrega del producto.

### Releases
- [x] Changelog operativo consistente como fuente principal de historial
- [x] Release estable `v0.2.1` definida como corte productivo anterior
- [x] Despliegue productivo de `v0.2.1` cerrado el 2026-07-10 con backup y
  restauración aislada, migración verificada, CI y smoke sanos, QA manual
  autenticada y emisión fiscal real satisfactoria
- [x] Resumenes de fases antiguas consolidados en changelog para evitar
  snapshots obsoletos
- [x] Primera release formal posterior al MVP publicada como `v0.2.1`
- [ ] Paquetes o imágenes publicables
- [x] Notas de release inauguradas con `v0.2.1`; mantenerlas en cada versión
  futura
- [x] Release `v0.2.2` publicada el 2026-07-23 como corte posterior a PF-01:
  versionado, dossier, CI, `autoreview`, backup cifrado recuperable, copia
  externa, restauración aislada, preflight, migración, constraints, pools,
  worker y smoke checks aprobados
- [x] Despliegue productivo separado de `v0.2.2` completado el 2026-07-23 desde
  el tag exacto, con backup final, preflight inmediato, migración única y QA
  post-deploy aprobados, sin emisiones ni solicitudes de CAE

#### Guía flexible de cortes

Los siguientes cortes son candidatos revisables, no fechas ni compromisos
inamovibles. El alcance solo cambia por decisión explícita del desarrollador:
un problema que impida un release seguro detiene el corte y se consulta; un
hallazgo no bloqueante se registra en el roadmap y no lo demora
automáticamente. No hace falta terminar todo el roadmap para publicar una
release: cada corte debe ser coherente, desplegable y reversible por sí mismo.

- **`v0.2.2` publicado y desplegado:** corte de estabilización cerrado después
  de PF-01 y antes de PF-02. Agrupa la integridad fiscal, la frontera DB/FECAE,
  el endurecimiento de pool/worker y las correcciones de seguridad aceptadas,
  sin mezclar el cambio de política de numeración global.
- **`v0.3.0`:** el alcance está congelado en PF-02, PF-03A y PF-19 con sus QA
  fiscales. PF-02 cambia el contrato operativo de numeración y PF-19 cierra la
  elegibilidad RECE y la semántica de rechazo descubiertas por evidencia
  productiva. PF-03B u otro trabajo solo pueden incorporarse si el desarrollador
  decide explícitamente reabrir el alcance; de lo contrario siguen después de
  `v0.3.0`.
- **Candidato `v0.3.0`:** el SHA `7f7b3808b3d4b8d5a129c193724955789a6ed4f2`,
  sobre `b5eefcd`, aprobó la CI Nivel 2 completa, PF-16G y el ensayo privado de
  backup, restauración aislada, upgrade y rollback. No existe tag, release ni
  despliegue, y la producción continúa en `v0.2.2`.
- **P2 posterior a `v0.3.0` — autenticidad de manifests VPS reatestiguados
  coordinadamente:** diseñar una firma externa verificable de manifests y la
  coordinación de la reatestación entre origen/destino. No se implementa en
  PF-19C ni permite revalidar, trasladar o reconstruir el journal legacy; se
  planificará con custodia privada de claves, rotación y rollback.
- **Patch extraordinario:** un fix urgente, aislado y compatible puede justificar
  una versión intermedia sin esperar al candidato siguiente.

Un candidato está listo para migrar a producción cuando el alcance quedó
congelado, no contiene P0 ni P1 bloqueantes conocidos, el commit exacto tiene CI
verde, las revisiones sensibles y revalidaciones aplicables están cerradas, las
migraciones fueron ensayadas sobre PostgreSQL desechable o una restauración
aislada, existen backup verificado y rollback, las notas y el procedimiento de
upgrade están actualizados y hay autorización explícita para desplegar. El tag y
el despliegue siguen siendo decisiones separadas de cada commit o push.

### Distribución
- [ ] Instalación simplificada para terceros, posterior a estabilizar VPS
- [ ] Plantillas de configuración por ambiente
- [ ] Demo controlada o entorno de evaluación
- [x] Upgrade `v0.2.1 -> v0.2.2` ensayado sobre una restauración privada
  aislada y ejecutado en producción el 2026-07-23 con QA post-deploy aprobada

### Soporte y adopción
- [ ] Runbooks de soporte
- [ ] Manuales de troubleshooting para usuarios administrativos
- [ ] Manuales técnicos para deploy y mantenimiento
- [ ] Política de compatibilidad y migraciones

## Fase 9 - Evolucion del producto

Objetivo: ampliar valor más allá del MVP.

- [x] Producción ARCA inicial
- [~] Operación productiva robusta y repetible
- [ ] Exportaciones de reportes
- [ ] Envio de comprobantes por email
- [ ] Integraciones externas de entrada/salida de datos via API, posteriores a
  la madurez productiva de facturación
- [ ] Dashboard de operación mas rico

## Prioridades inmediatas

1. Cerrar `v0.3.0` sin ampliar su alcance: desde el commit exacto aceptado en
   `main`, decidir tag y publicación, y autorizar el despliegue por separado
   mediante el flujo productivo. PF-16G, `autoreview`, PostgreSQL real
   y el ensayo privado de backup/restauración/upgrade/rollback ya están
   aprobados. No provocar un CAE ni `10005` real.
2. Retomar PF-03 con PF-03B después de publicar y desplegar `v0.3.0`:
   separar el DTO de ítem que serializa la UI, hacer estricto
   `ItemComprobanteCreate` y rechazar descuentos
   o valores no finitos antes de calcular totales. PF-03A está cerrado y PF-05
   continúa separado.
3. Conservar PF-16G aceptada el 10/08/2026; Node 24, auditorías, cobertura, CI
   y Runtime Smoke ya están implementados y validados en el SHA funcional. La
   firma externa de manifests VPS es P2 posterior y no bloquea
   `v0.3.0`.
4. Después de PF-03, ejecutar primero la unidad integrada PF-06A/PF-08A/PF-06B/
   PF-07A de operadores multiemisor y creación/edición delegada; cerrar su
   matriz Nivel 2 antes de continuar los restantes PF-06/PF-07, PF-08 y PF-09.
5. Mantener la custodia concreta del backup fuera del repo público y corregir
   su trazabilidad PF-11/PF-15: snapshot exacto, propósito, timestamp y
   escrituras intermedias. Automatización, retención y recuperación a un VPS
   nuevo siguen como trabajo separado.
6. Continuar el backlog Clawpatch `medium`/`low` en lotes pequeños, enrutado por
   causa raíz y sin tratar los contadores acumulativos como bugs confirmados.
7. Diseñar e implementar por cortes el P2 de reconstrucción histórica opcional,
   comenzando por selección de alcance, límites, journal y cobertura visible en
   informes; no acoplarlo como requisito del P1.
8. Completar observabilidad operativa: backup visible, trazabilidad, logs útiles
   y mensajes simples para soporte.
9. Definir y luego automatizar backups cifrados con validación, retención,
   destino externo y alertas.
10. Documentar y ensayar recuperación completa hacia un VPS nuevo.
11. Validar en VPS, con datos de prueba controlados, almacenamiento mínimo,
    resguardo ZIP, compactación y limpieza segura.
12. Agregar descarga masiva de PDFs sin persistencia permanente en el servidor.
13. Mantener la higiene del toolchain posterior a `v0.3.0`: seguir y retirar
    dependencias transitivas obsoletas, incluida `glob@10.5.0`, cuando sus
    productores publiquen una actualización compatible, sin `overrides`,
    `--force` ni relajación de `peerDependencies`; actualizar además el runbook
    de `autoreview` para resolver un binario local compatible por capacidad o
    versión, sin depender de un launcher histórico desactualizado.
14. Mantener notas de release y procedimiento de upgrade para cada versión
    futura, revisando los candidatos cuando cambien riesgos o alcance.

## Criterio de éxito del MVP

El MVP se considera cerrado cuando:

- una persona administrativa no técnica puede emitir un comprobante individual sin ayuda técnica
- una persona administrativa no técnica puede emitir un lote por Excel sin soporte técnico constante
- una persona administrativa no técnica puede revisar el formato detectado y confirmar antes de emitir
- los comprobantes quedan autorizados con CAE en homologación y la operación
  productiva inicial está documentada sin exponer datos privados
- el usuario puede consultar comprobantes, ver PDF y operar reportes básicos
- la documentación permite retomar el proyecto y operarlo sin reconstruir contexto desde cero

## Criterio de éxito de largo plazo

FactuFlow deja de ser "solo un MVP" cuando además:

- soporta despliegues reproducibles
- soporta varios emisores con aislamiento fuerte y emisor activo explícito
- tiene estrategia clara de migraciones, observabilidad, soporte y releases
- puede ser usado por muchos usuarios sin depender del conocimiento histórico de una sola persona
