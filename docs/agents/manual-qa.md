# QA manual

Última actualización: 29/08/2026

Este documento conserva únicamente el checkpoint vigente y la QA todavía
accionable. El historial técnico está en `CHANGELOG.md` y en las auditorías
fechadas de `docs/project/**`.

## Estado productivo y referencia pública

El estado desplegado actual se consulta exclusivamente en el plano de control
`VPS Hostinger` / `vps-admin`. El despliegue de `v0.3.1` quedó registrado allí;
este documento no fija su SHA ni reemplaza esa evidencia privada.

La última evidencia productiva pública detallada conserva como referencia el
checkpoint de `v0.2.2`, validado el 23/07/2026:

- El ciclo verificó previamente backup recuperable y restauración aislada; bajo
  mantenimiento repitió backup final, preflight, Alembic, constraints,
  invariantes, conteos, runtime, worker y logs sanitizados.
- Los smoke autenticados confirmaron acceso, lecturas, certificados, puntos de
  venta, reportes y PDF seguro.
- No se solicitaron CAE ni se realizaron emisiones o reintentos fiscales
  durante el despliegue. La emisión fiscal real ya había sido validada en el
  checkpoint productivo de `v0.2.1`.
- Los datos fiscales y la evidencia detallada permanecen en el entorno operativo
  privado.

El candidato `v0.3.2` agrega la comprobación previa a la selección y la matriz
UX simple de puntos de venta. Su QA usa datos sintéticos y dobles controlados,
sin CAE reales ni llamadas ARCA de escritura; la QA productiva posterior se
registra únicamente en el plano de control.

## Preparación local

Para desarrollo o QA manual en Windows:

```powershell
.\FactuFlow Local.vbs
```

Camino técnico alternativo:

```powershell
powershell -ExecutionPolicy Bypass -File .\run-local.ps1
```

Entornos locales esperados:

- frontend: `http://localhost:8080`;
- backend: `http://localhost:8000`.

No reutilizar certificados productivos en local mientras el VPS sea el entorno
operativo. Usar datos ficticios, mínimos o anonimizados.

## Matriz mínima por tipo de cambio

### Fiscal o ARCA

Antes de probar, completar `docs/agents/fiscal-change-checklist.md`.

Verificar al menos:

- fecha visible en `DD/MM/AAAA` y payload técnico correcto;
- fecha calendario inválida rechazada;
- punto de venta y emisor activo;
- concepto fiscal y fechas de servicio aplicables;
- totales, IVA y comprobantes asociados;
- confirmación irreversible antes de CAE;
- idempotencia, replay con mismo payload y conflicto con payload distinto;
- falla pre-ARCA, respuesta ambigua, falla post-CAE y reconciliación;
- caída pre-ARCA: `503` con `Retry-After: 2` solo tras recuperación durable sin
  intentos fiscales;
- intento existente o recuperación no persistible: `409
  pre_arca_estado_bloqueado`, misma clave, sin operación nueva ni reconciliación
  ARCA;
- caída desde la frontera irreversible: `409`, sin retry, con evidencia conocida
  preservada y reconciliación obligatoria;
- excepción inesperada post-ARCA individual o batch: respuesta sanitizada,
  intento `requiere_reconciliacion` y replay con la misma clave sin nueva emisión;
- rechazo `R` completo: fallo verificado sin comprobante ni reconciliación;
- aislamiento entre emisores.

No solicitar CAE real durante QA salvo decisión fiscal explícita del usuario.

### Lotes y worker

Verificar:

- validación antes de encolar;
- `503` sin mutar el lote cuando el worker no está disponible;
- un único procesamiento efectivo por lote;
- reanudación de un lote vencido solo si los pendientes están intactos y la
  numeración ARCA/local fue comprobada;
- preservación como `validado` de grupos intactos cuando el lote se bloquea;
- reconciliación solo para grupos con evidencia fiscal o incertidumbre;
- polling sin ciclos solapados y sin mensajes falsos de lote inexistente;
- ausencia de reintentos automáticos cuando ARCA pudo haber autorizado;
- worker pre-ARCA: solo reencola sin intentos, conserva la operación
  `en_proceso`, impide replay HTTP paralelo y corta el ciclo;
- corte del ciclo del worker post-frontera, sin tomar ni procesar lotes
  posteriores.

### Multiemisor

Verificar con dos emisores ficticios:

- administrador: puede operar todos los emisores;
- usuario común: solo puede operar el emisor asignado;
- cambio de emisor invalida la selección y las acciones del contexto anterior;
  Lotes limpia formatos, perfiles y puntos antes de su primer `await`, y los
  loaders con guarda explícita descartan finalizaciones tardías sin implicar
  cancelación HTTP ni cobertura global;
- clientes, puntos de venta, certificados, comprobantes, lotes, PDFs, reportes,
  perfiles y plantillas particulares no se mezclan.

### UI y documentación

Para cambios visuales o de texto:

- `npm run lint:check`;
- `npm run type-check`;
- tests unitarios enfocados;
- build cuando cambia composición o routing;
- E2E solo cuando el flujo real lo justifica.

Los cambios solo documentales no requieren `autoreview` salvo pedido explícito.

## QA pendiente

### Regresión DB/FECAE — QA manual pendiente

La implementación tiene validación automatizada local. En una próxima QA
controlada, sin solicitar CAE real, simular:

1. pre-ARCA sin intentos: confirmar recuperación durable, `503`, transición
   `en_proceso -> interrumpida_pre_arca` y un único replay ganador por CAS;
2. individual/lote/reintento sin intentos: lote `validado` o grupo exacto
   `fallido`, con reanudación mediante la misma clave;
3. intento existente o recuperación no persistible: confirmar
   `409 pre_arca_estado_bloqueado`, misma clave, sin nueva operación ni
   reconciliación ARCA;
4. post-frontera: confirmar `409`, ausencia de retry y reconciliación;
5. cleanup: fallos de `rollback`/`close` no reemplazan la excepción primaria ni
   degradan un `409` post-ARCA a `503`;
6. worker pre-ARCA sin intentos: lote `en_cola`, operación `en_proceso`, replay
   HTTP paralelo impedido y corte del ciclo; post-ARCA conserva el bloqueo.

Estos casos quedaron cubiertos por el cierre automatizado local: `487` tests
backend aprobados y `2` omitidos, `120` pruebas de API aprobadas, Ruff, Black y
`git diff --check` limpios. El `autoreview` final con `gpt-5.6-sol` en `high`
quedó limpio, sin findings accionables, con probabilidad `0,87` de patch
correcto. La QA manual de fallos controlados continúa pendiente; la evidencia
productiva básica quedó cerrada con el despliegue seguro de `v0.2.2`.

Los commits `8b311b5` y `e175b77` ya fueron publicados en `main` y quedaron
incluidos en la versión productiva `v0.2.2`.

### PF-01A — QA manual pendiente

La cobertura automatizada usa dobles y no solicita CAE real. Para PF-01A.2, una
QA controlada debe provocar sin red una excepción inesperada después de marcar
la frontera fiscal y verificar:

1. respuesta `409` sanitizada con `requiere_reconciliacion`;
2. conservación de CAE, vencimiento, número y total cuando ya se conocían;
3. operación e intento bloqueantes;
4. replay con la misma clave y payload sin segunda ejecución;
5. rechazo `R` explícito como fallo verificado;
6. comportamiento equivalente en individual y batch.

PF-01A.3 agrega la matriz visual de emisión individual. Sin llamar a ARCA real,
simular desde el borde HTTP:

1. un `409` estructurado y confirmar el panel `Emisión pendiente de
   verificación`, el resumen fiscal visible y el formulario inerte;
2. presionar `Verificar estado` y comprobar que request y
   `X-Idempotency-Key` sean exactamente los mismos;
3. hacer doble interacción y comprobar una sola solicitud efectiva;
4. cambiar el emisor activo: el estado debe conservarse y la verificación quedar
   deshabilitada hasta volver al emisor original;
5. devolver red, `409` o `5xx`: el bloqueo debe continuar; devolver autorización
   final: debe navegar al comprobante; devolver rechazo final HTTP `400` con
   `{mensaje, errores}`: debe desbloquear para corregir datos;
6. intentar cancelar o navegar mientras está pendiente: la vista debe impedirlo;
7. intentar cerrar o recargar: debe aparecer la advertencia del navegador. Si se
   fuerza la recarga, el estado visual en memoria puede perderse, pero no se debe
   iniciar otra emisión; corresponde revisar el backend o pedir soporte con el
   emisor original.

El cierre automatizado de PF-01A.2 aprobó `503` tests backend, con `2` omitidos,
y una regresión enfocada de `189` tests. PF-01A.3 aprobó `17` pruebas unitarias
enfocadas, `127` unitarias completas, un E2E enfocado y `33` E2E completos;
ESLint, type-check y build quedaron limpios. `autoreview` con `gpt-5.5 high`
detectó un P1 válido sobre el rechazo final HTTP `400`; se aceptó, corrigió y
cubrió, y la segunda pasada quedó limpia con confianza `0,80`. `gpt-5.6-sol` no
llegó a revisar porque exige una versión más nueva del binario local.

No forzar este escenario con CAE real hasta autorizar explícitamente una QA
fiscal controlada. PF-01A.3 está publicado y desplegado, pero esta matriz manual
de fallos simulados continúa pendiente.

### PF-01B — validación histórica completada

PF-01B.2 tiene cobertura SQLite/Alembic y PF-01B.3 aprobó en PostgreSQL 16
efímero: upgrade, checks, estados, coherencia CAE, unicidad, dos transacciones
concurrentes, preflight bloqueante y downgrade. El backend completo aprobó
`531` pruebas y omitió `4`; Ruff y Black quedaron limpios. El commit
`6625254` tuvo CI completa verde y Clawpatch cerró B10/B17 como `fixed` con
`gpt-5.6-sol high`.

El 2026-07-23 el candidato repitió estas garantías sobre una restauración
aislada de un backup productivo reciente: preflight en cero, migración,
constraints, conteos, pools, worker y smoke checks aprobados, sin CAE ni cambios
productivos. El despliegue repitió después el preflight agregado inmediato con
las cinco categorías en cero, migró una sola vez y volvió a verificar
constraints, invariantes y conteos antes de reabrir.

### P1 pool/worker — cierre histórico

La implementación y la capacidad estructural quedaron validadas localmente:

1. pool API PostgreSQL máximo `4`, overflow `0` y pool worker dedicado `1`;
2. sesiones API lazy, instrumentación sanitizada y timeouts HTTP `503`;
3. polling allowlist adaptativo, no solapado y protegido por emisor;
4. prueba PostgreSQL efímera con saturación `4 + 1`, sin datos ni ARCA;
5. suites backend/frontend y regresiones fiscales vecinas aprobadas.

El despliegue confirmó en el entorno privado la configuración efectiva, salud
del worker, pools, logs sanitizados y cero trabajos elegibles. Todavía
corresponde medir los tiempos de un lote de prueba controlado y completar la QA
visual de `Sistema > Estado`. El runbook privado conserva el commit desplegado
y sus comandos concretos.

### Operación VPS

Queda pendiente, con datos de prueba controlados:

- QA visual del gestor de almacenamiento;
- resguardo ZIP y confirmación `Ya lo descargué`;
- compactación y limpieza segura;
- healthcheck de worker visible y coherente con el runtime desplegado;
- señal de último backup;
- trazabilidad histórica más completa;
- ensayo de recuperación hacia un VPS nuevo.

## Smoke posterior a futuros despliegues

La validación mínima debe cubrir:

- health público de frontend y backend;
- login;
- emisor activo;
- listado de comprobantes;
- certificados y puntos de venta;
- PDF;
- un único Uvicorn y worker iniciado;
- logs sin errores nuevos;
- servicios vecinos sin afectación.

Si hubo migraciones, comprobar `alembic current`, `heads`, constraints, conteos
básicos y restauración aislada. Seguir
`docs/agents/production-workflow.md`.

## PF-02A — numeración individual e historia externa

Este corte se valida sin emisiones reales ni solicitudes de CAE salvo
autorización explícita. Para carreras y errores usar dobles controlados.

1. Abrir `Nueva Factura` con un emisor, punto y tipo alineados. Verificar emisor,
   punto, tipo, último local, último ARCA y próximo número.
2. Simular local `76` y ARCA `77`. Debe mostrarse una advertencia, ofrecer el
   `78` y aclarar que la reconstrucción histórica es opcional y posterior.
3. Simular local adelantado. Debe verse `No disponible`; la vista previa y la
   emisión permanecen bloqueadas.
4. Simular un intento propio `en_proceso` o `requiere_reconciliacion`. La
   consulta no debe convertirlo en historia externa ni habilitar otro número.
5. Simular ARCA estable en el primer preflight y adelantada en el segundo. Debe
   haber cero llamadas a FECAE, cero comprobantes nuevos, intento
   `fallido_verificado`, número invalidado y botón `Actualizar numeración`.
6. Simular un error en el segundo preflight. Debe aplicar el mismo cierre seguro
   pre-ARCA y no mostrar el estado de operación incierta post-ARCA.
7. Pulsar `Actualizar numeración`, abrir nuevamente la vista previa y verificar
   que el modal irreversible conserva la fecha `DD/MM/AAAA`, el punto de venta y
   el texto fiscal obligatorio.
8. Cambiar de punto, tipo o emisor mientras una consulta anterior está pendiente.
   La respuesta anterior no debe reemplazar el diagnóstico de la selección
   actual.
9. Confirmar que el flujo individual no copia un número diagnóstico a campos
   persistidos sin reserva, intento y resultado fiscal.

Evidencia mínima: captura sanitizada del panel para los tres estados, resultado
de pruebas enfocadas, conteo cero de FECAE en abortos pre-ARCA y ausencia de
datos fiscales reales en el repositorio.

## PF-02B — batch, reintentos manuales y recuperación stale

Este corte se valida únicamente con dobles controlados. No autoriza solicitudes
de CAE reales.

1. Simular un sublote de dos comprobantes con local `0` y ARCA `5`. Debe
   reservar `6` y `7`, repetir `FECompUltimoAutorizado` y efectuar una sola
   llamada batch únicamente si ARCA continúa en `5`.
2. Simular ARCA alineada en el primer preflight y adelantada en el segundo.
   Debe haber cero FECAE, cero comprobantes y ambos intentos
   `fallido_verificado`.
3. Simular un error en el segundo preflight. Debe aplicar el mismo cierre
   terminal pre-ARCA sin presentar reconciliación post-ARCA.
4. Confirmar que `local_adelantada` y los intentos propios `en_proceso` o
   `requiere_reconciliacion` siguen bloqueando antes de crear nuevas reservas.
5. Confirmar que los números diagnósticos nunca se copian a
   `numero_asignado`; solo una autorización o reconciliación verificada puede
   completar ese campo.
6. Verificar que fecha fiscal y punto de venta permanecen visibles en
   `DD/MM/AAAA` dentro de la confirmación irreversible existente.
7. En `Reintentar fallidos`, simular historia local parcial y ARCA estable.
   Debe usar `ultimo_arca + 1`; un replay exacto con la misma clave no vuelve a
   consultar ni solicitar CAE, y la misma clave con otra selección responde
   conflicto.
8. Simular avance o error en el segundo preflight del primer grupo. Debe haber
   cero FECAE y los grupos posteriores deben permanecer intactos.
9. Simular respuesta ARCA ambigua. El primer grupo y el lote deben quedar
   `requiere_reconciliacion`; no debe reclamarse ningún grupo posterior.
10. Simular autorización seguida de una falla en la persistencia de lote. Debe
    hacerse rollback del comprobante incompleto, conservar número/CAE conocidos
    en el intento, sanitizar el error y bloquear toda reemisión.
11. Simular rechazo ARCA explícito y completo. Solo en ese caso el grupo puede
    quedar `fallido` y continuar la selección.
12. Confirmar que `local_adelantada` y los intentos propios `en_proceso` o
    `requiere_reconciliacion` detienen la selección sin nueva reserva ni FECAE.
13. Simular un lote stale parcial con un grupo autorizado respaldado por intento
    fuerte y otro intacto, con ARCA adelantada. Debe vincular el autorizado,
    reencolar el intacto sin número, CAE, comprobante ni intento nuevo y registrar
    el diagnóstico `arca_adelantada`.
14. Simular grupos intactos con combinaciones mixtas. Todas deben aprobar el
    preflight; si una queda `local_adelantada` o no puede verificarse, ningún
    grupo se reencola y el lote queda bloqueado para reconciliación.
15. Repetir la recuperación y simular dos reclamos del worker. La segunda
    recuperación no duplica el evento y solo un reclamo atómico puede pasar
    `en_cola -> procesando`. Un reintento manual sobre `en_cola`, `procesando` o
    `requiere_reconciliacion` debe rechazarse.
16. Hacer fallar el preflight con una excepción que contenga una ruta sintética.
    El lote y el evento deben guardar solo `numeracion_no_verificable`; el texto
    interno debe quedar fuera de la respuesta.

PF-02B.3 cierra esta matriz. La recuperación stale acepta historia externa solo
como diagnóstico de lectura; nunca asigna el número ni crea la reserva. El
procesamiento normal vuelve a diagnosticar, reserva y ejecuta el segundo
preflight antes de cualquier FECAE.

## PF-03A — contrato superior estricto de emisión

Este corte no cambia pantallas. Puede validarse con requests sintéticos y dobles;
no autoriza emisiones reales ni solicitudes de CAE.

1. Enviar un request individual válido con una clave superior adicional, como
   `monedaa`, `cotizaccion` o `guardar_clientee`. Debe responder `422` con
   `extra_forbidden` y localizar la clave incorrecta.
2. Omitir la clave correcta en esos casos. FactuFlow no debe continuar usando
   silenciosamente `PES`, cotización `1` o `guardar_cliente=true`.
3. Escribir mal `confirmacion_fecha_fiscal`. Debe responder `422`, no ejecutar
   la rama `400` de confirmación ausente y no crear una operación idempotente.
4. Repetir un request conocido y válido. La idempotencia, numeración, fecha
   fiscal explícita y comportamiento del servicio deben permanecer sin cambios.
5. Revalidar un snapshot batch canónico en procesamiento unitario, batch,
   worker, reintento y reconciliación. Debe continuar normalmente con dobles.
6. Agregar una clave superior desconocida al snapshot de un grupo `fallido` y
   ejecutar el reintento manual. El grupo debe conservarse sin número, CAE ni
   comprobante y debe haber cero llamadas de emisión.
7. Usar un lote stale mixto con un grupo canónico y otro con una clave superior
   desconocida. Debe devolver `payload_fiscal_invalido`, sin consultar
   numeración ni reencolar ningún grupo.
8. Confirmar que un ítem que la UI actual mantiene con `subtotal` derivado sigue
   aceptándose transitoriamente. La eliminación de ese campo del DTO y la
   validación estricta del ítem corresponden a PF-03B.
9. Simular `FECompConsultar` autorizado para un intento stale cuyo snapshot tiene
   una clave superior desconocida. Debe conservar CAE y vencimiento en
   `requiere_reconciliacion`, sin reconstruir comprobante ni habilitar FECAE.

Evidencia mínima: respuesta `422` estructurada, ausencia de operación idempotente,
cero emisión en reintento/stale y resultados de las suites enfocadas. No usar
datos fiscales reales.

## PF-19 — elegibilidad RECE y rechazo global excluyente

Estado del snapshot de cierre, 11/08/2026: PF-19A, PF-19B completo y PF-19C están
integrados; PF-19C ya tiene evidencia completa. El
`autoreview` final cerró limpio, la CI Nivel 2 aprobó PostgreSQL real y Runtime
Smoke, y la aceptación PF-16G y el ensayo privado de
backup/restauración/upgrade/rollback quedaron cerrados el 10/08/2026. El merge
funcional `2add308a` aprobó los siete checks completos y el cierre documental
`147693f2` aprobó su recorrido Nivel 0 y la preparación final `6fb2878` aprobó
el suyo en `31462387733`. Al cerrar el snapshot, tag y publicación todavía no se
habían ejecutado y la release publicada y producción eran `v0.2.2`, sin estos
cortes. Toda ejecución previa al checkpoint de
release usa datos sintéticos y dobles de WSFE. Esta matriz no autoriza pedir CAE
real para provocar errores ni editar registros fiscales.

### PF-19A — cobertura automatizada

1. Configurar una regla sintética de contención y repetir directamente los
   núcleos individual y batch. Esos núcleos deben abortar antes de WSAA/WSFE,
   intento, reserva, comprobante y CAE, con categoría pública sanitizada.
   Repetir además `procesar_lote`: puede autenticar y leer
   `FECompTotXRequest` antes de formar el sublote, pero debe mantener cero
   `FECAESolicitar`, CAE, intentos y comprobantes.
2. Repetir la misma regla cambiando, de a una, ambiente, emisor, punto y tipo.
   Solo la tupla exacta debe bloquear. Renumerar la fila local o recrear el
   número fiscal con otro ID tampoco puede evitar la regla; cambiar ambos debe
   quedar fuera de su alcance.
3. Confirmar en el mapa y las suites vecinas que worker, fallback unitario y
   reintento delegan en los mismos núcleos contenidos. La matriz PF-19A prueba
   directamente individual, batch, replay HTTP, intento stale y preflight stale
   de lote. La reconciliación manual puede consultar, pero no solicitar un CAE
   nuevo.
4. Ejecutar el inventario sobre una SQLite sintética. Debe reconocer únicamente
   la firma global canónica con token exacto `[10005]`, deduplicar por intento,
   dejar el ambiente histórico como `indeterminado` y no modificar ninguna
   tabla. Texto libre, `[100050]` o un detalle sin el prefijo global no califican.
5. Confirmar que un marcador con CAE o comprobante de referencia válida, un
   estado incompatible o una referencia huérfana/cruzada se informa en su clase
   separada. La FK directa y la de grupo solo son válidas si coinciden emisor,
   punto, tipo y número planificado; sin número planificado fallan cerrado. El
   inventario no sanea, no reconcilia, no consulta ARCA y no convierte
   incertidumbre en rechazo terminal.

Evidencia mínima PF-19A: diseño aprobado, mapa exhaustivo de consumidores,
cero `FECAESolicitar` y cero comprobantes/CAE en abortos preautorización,
aislamiento por ambiente/emisor/punto/tipo y transacción demostrablemente de solo
lectura. La salida está sanitizada, pero es evidencia privada: conserva IDs
operativos, punto y tipo; omite CUIT, receptor, importes, CAE, fechas fiscales,
marcas temporales de comprobantes/intentos, payloads y mensajes crudos. Conserva
únicamente `generado_el` en `DD/MM/AAAA`. Los logs privados pueden conservar
identificadores operativos mínimos para correlación, pero nunca secretos ni
contenido fiscal sensible.

### PF-19B — cobertura automatizada y QA segura

1. Importar constancias PDF sintéticas completas, parciales, antiguas, futuras,
   ambiguas, con CUIT distinto y con señales exactas, genéricas o fuera de
   allowlist. Solo administrador + servidor productivo + documento no futuro +
   una modalidad Web Services exacta admitida
   para Responsable Inscripto, Exento en IVA o Monotributo puede crear
   `verificado_rece`. Cubrir documentos de más de 7, 90 y 365 días aceptados, y
   una fecha futura rechazada; incluir `PUNTO VENTA`, `P.VTA.`, `ACTIVIDAD` y
   encabezados repetidos. La UI procesa una sola selección sin modal y el PDF
   no se persiste. Homologación queda cerrada.
2. Comprobar WSFE desde el endpoint server-side. Debe crear, actualizar o
   desactivar técnicamente en una transacción, sin promover RECE y conservando
   una acreditación positiva previa. Una primera importación sin ARCA queda
   pendiente; una comprobación posterior la habilita sin otro PDF. Respuesta
   vacía, inconsistente o fallida no modifica estados.
3. Verificar DTO y UI: los selectores consumen exclusivamente
   `seleccionable_para_emision`. Los estados normales muestran solo `Listo para
   emitir` / `Web Services activo` o `No disponible en FactuFlow` / `Otro
   sistema`. Los estados de error muestran `Comprobación necesaria`, `Falta
   validar` o `No disponible para emitir` con una acción concreta. No aparecen
   `Requiere atención`, “se comprobará al emitir”, procedencia, ambiente ni
   revisión fiscal.
4. Cambiar punto, ambiente o revisión después de validar/confirmar. El flujo
   individual, proceso batch, worker, fallback, reintento y recuperación stale
   deben abortar una continuación obsoleta antes de FECAE. Un replay terminal
   durable conserva su respuesta sin reevaluar el estado actual.
5. Forzar una falla local al reservar o preparar todos los grupos antes de
   `FECAESolicitar`. La transacción debe dejar cero guardas, intentos y reservas
   nuevos, y cero FECAE. WSAA o lecturas seguras como `FECompTotXRequest` y
   `FECompUltimoAutorizado` pueden haberse ejecutado: no exigir “cero contacto
   ARCA” en este caso.
6. Forzar punto pendiente, exactamente 90 días y fresco. Al abrir nueva factura,
   lotes y perfiles, el fresco no consulta; los otros consultan como máximo una
   vez por emisor, recargan el listado y recién entonces habilitan el selector.
   Durante la espera debe verse `Comprobando con ARCA…` sin preselección. Si ARCA
   no responde, conservar los puntos frescos, excluir pendientes y mostrar la
   acción de reintento. La guarda final debe devolver `503` con cero operaciones,
   intentos, reservas y `FECAESolicitar`; un replay terminal mantiene su
   respuesta durable sin reevaluación.
7. Ingresar como usuario común autorizado: `Comprobar con ARCA` debe estar
   disponible, mientras `Importar constancia` y la edición fiscal siguen
   reservadas al administrador. Repetir con dos emisores y confirmar que una
   respuesta tardía nunca reemplaza el listado del emisor actual.
8. Importar una constancia sintética con un punto listo, otro sistema y uno que
   requiere revisión. El resumen debe informar exactamente esas tres cantidades,
   ser mutuamente excluyente y no exponer warnings técnicos internos.
9. Ejecutar upgrade/downgrade SQLite solo con backup físico distinto y
   verificado; ante falla posterior a DDL, restaurarlo antes de reintentar. La
   matriz PostgreSQL se ejecuta en CI con el harness destructivo exacto; un skip
   local sin URL no acredita PostgreSQL.
10. Con un emisor sintético sin dependencias y una constancia que crearía su
   primer punto, intercalar cambio de CUIT y atestación en ambos órdenes. Si gana
   el update, debe quedar el CUIT nuevo y cero punto/evidencia de la constancia
   anterior. Si gana la atestación, deben quedar el CUIT original y su revisión
   positiva, mientras el update responde `409`. Nunca debe existir evidencia
   positiva asociada a otra identidad fiscal.
11. Sobre un punto sintético, intercalar la atestación con `activo=false` y con
   `es_admin=false`, en ambos órdenes. Si gana la degradación, no debe crearse
   evidencia positiva; si gana la atestación, la revisión se confirma bajo la
   autoridad todavía válida y el cambio del actor continúa después. Estos casos
   requieren PostgreSQL real en CI; un collect/skip local no los acredita.
12. Después de atestiguar, simular una divergencia legacy del CUIT y exigir el
   contexto RECE. Debe fallar cerrado por `empresa_cuit_snapshot` obsoleto antes
   de `FECAESolicitar`; no reparar el ledger ni promover automáticamente.
13. Demorar por separado formatos, perfiles y puntos de Lotes para el emisor A,
    y cambiar a B o C entre esperas. Antes del primer `await` del watcher deben
    quedar vacías las tres colecciones; cada respuesta/error tardío se descarta y
    la cadena obsoleta no inicia el loader siguiente. Repetir en EmpresaConfig
    con datos de A ya cargados y B pendiente o fallida: perfiles, formatos,
    puntos y catálogo quedan vacíos. Ningún `finally` obsoleto puede apagar el
    loading vigente. No exigir cancelación HTTP: alcanza con limpiar, revalidar
    después de cada espera y descartar el resultado.

QA manual posterior a una release candidate: navegar los estados y la carga
directa sin modal con PDFs sintéticos; probar homologación únicamente mediante
conexión y lecturas seguras, sin solicitar CAE. Una constancia productiva real,
sus identificadores y sus resultados pertenecen exclusivamente a evidencia
operativa privada y requieren autorización separada.

### PF-19C — matriz, evidencia y ensayo privado completos

Usar exclusivamente dobles WSFE, SQLite sintética y PostgreSQL desechable
habilitado por el harness. Esta QA no provoca `10005`, no solicita CAE real y
no emplea certificados, CUIT, backups ni datos operativos reales.

1. Simular `10005` como entero no booleano, único, con cabecera `R` que coincide
   exactamente en CUIT, punto, tipo y cantidad, rangos unitarios exactos y sin
   detalle/CAE. Debe cerrar solo el sublote enviado como
   `arca_rechazo_global_excluyente`, conservar su evidencia sanitaria y detener
   todos los grupos posteriores como `no_enviado_por_rechazo_global`, con cero
   `FECAESolicitar` adicional.
2. Repetir con `1005`, string, float, booleano, duplicado o mezclado; cabecera
   ausente, `A`, `P` o discordante; detalle/CAE; `R` por detalle, cardinalidad
   inconsistente, timeout, Fault, deserialización y corte de transporte. Ningún
   caso puede ser terminal: el grafo pertinente queda
   `requiere_reconciliacion`, el lote se inmoviliza y el procesador no continúa.
3. Repetir mismo payload y clave tras terminal e incertidumbre. El replay debe
   devolver la respuesta durable con cero WSAA, `FECompUltimoAutorizado`,
   `FECompConsultar` o `FECAESolicitar`. Forzar CAS perdedor y cambio de owner
   `operacion_id A -> B`: A no publica ni emite sobre B.
4. Inyectar una falla en cada frontera posterior a ARCA. Intento, guarda,
   grupo/fila, lote, respuesta idempotente y metadatos deben cerrar juntos o
   revertirse juntos; una persistencia no confirmable conserva reconciliación,
   nunca habilita retry.
5. Para legacy, ejecutar primero `plan` sobre un candidato sintético: debe ser
   read-only, determinista y hasheado. `apply` requiere backup sintético
   verificable, actor y confirmación. Con ambiente nulo debe consultar ambos
   ambientes; solo dos últimos autorizados menores cierran
   `legacy_sin_autorizacion_verificada`. Si hay autorización, timeout o duda,
   no muta ni agrega journal. El journal debe ser único, append-only y sanitizado.
6. Ensayar upgrade/downgrade de `c0d1e2f3a4b`: la evidencia/journal bloquea el
   downgrade. El paquete VPS solo valida y contabiliza los terminales PF-19C
   omitidos; no los transporta ni reatesta. Mantener dumps, hashes y rutas reales
   fuera del repositorio.

La evidencia local registró `1049 passed`, `22 skipped`, `31 warnings` en
`9m14s`, con los skips limitados a PostgreSQL sin URL/daemon local. La cobertura
backend fue `69.2278%` total branch-aware, `73.6741%` líneas y `55.1759%` ramas;
frontend aprobó `149` pruebas y registró cobertura `56.12/50.14/43.77/57.37`.
La CI Nivel 2 ya aprobó PostgreSQL real y Runtime Smoke sobre el SHA funcional;
la aceptación PF-16G y el ensayo privado de
backup/restauración/upgrade/rollback quedaron cerrados el 10/08/2026. El tag y
la release se publicaron el 11/08/2026; el despliegue continúa como decisión
separada.

## Punto de reanudación de QA

PF-01, PF-02, PF-03A, PF-19A, PF-19B y PF-19C están cerrados en el código
aceptado. El candidato `v0.3.2` agrega la selección estricta posterior a la
comprobación y la UX simplificada de puntos de venta; sus pruebas funcionales,
QA visual y `autoreview` están aprobados. El checkpoint siguiente es publicar el
tag inmutable y ejecutar el despliegue por SHA exacto desde `vps-admin`, sin CAE.
El estado productivo efectivo se consulta exclusivamente en ese plano de
control; no se fija en este documento. PF-03B queda después de `v0.3.2`.

Para conocer el estado de desarrollo y el orden exacto, usar
`docs/agents/current-status.md` y `ROADMAP.md`.
