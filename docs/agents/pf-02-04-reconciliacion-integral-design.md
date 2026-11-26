# PF-02/PF-04 — reconciliación fiscal integral

Fecha: 03/10/2026.

Última revisión: 26/11/2026.

Estado: comparación legacy P1 y recuperación moderna individual P2 implementadas.
La [recuperación moderna de lotes](#recuperación-moderna-de-lotes) tiene diseño
y criterios de aceptación. Su implementación está pendiente.

## Evidencia y cortes

Un ensayo con base efímera y `FECompConsultar` simulado recorrió la recuperación
legacy real: con los mismos identificadores, fecha, receptor y total, diferencias
de moneda/cotización o neto/IVA no impidieron marcar el intento como autorizado
y reconstruirlo desde el payload local. El flujo moderno tiene guardas RECE que
impiden ingresar por esa recuperación antigua; sus protecciones se verificaron
por separado. No se acredita que esa diferencia haya ocurrido en producción.

Evidencia, alcance y reproducción en la
[validación de planificación](../project/analysis/confiabilidad-arca-roadmap.md).

| Corte | Prioridad / horizonte | Resultado |
|---|---|---|
| Comparación y recuperación legacy | P1 fiscal, cerrado | Evitar reconstruir o vincular como coincidente una respuesta fiscal diferente |
| Snapshot y recuperación individual | P2 fiscal con PF-04, implementado | Evidencia previa y recuperación de facturas y notas individuales |
| Recuperación moderna de grupos | P2 fiscal con PF-04, pendiente | Cierre consistente de grupos y filas ante autorizaciones parciales |

## Invariantes y fuente de comparación

La fuente esperada es la solicitud fiscal congelada del intento, no el cliente,
emisor, perfil o plantilla actuales. Definir una representación mínima,
versionada y decimal de sus componentes; compartirla con
[preparación/importes](pf-03-04-importes-previsualizacion-design.md).

La comparación incluye, cuando el contrato y la evidencia lo permitan:
emisor, ambiente, punto de venta, tipo, número, fecha, receptor, concepto,
condición IVA, moneda/cotización, total y componentes, alícuotas, períodos de
servicio y asociados. Distinguir igualdad demostrable, diferencia e información
no disponible. No convertir un campo ausente en coincidencia inventada.

El cliente WSFE debe conservar los campos pertinentes de `FECompConsultar`,
sin perderlos al adaptar la respuesta. Revisar los importes actualmente leídos
como `float`; la comparación nueva necesita precisión decimal desde la entrada.
Normalizar sólo equivalencias contractuales, orden de colecciones y ceros
permitidos; no ocultar diferencias con una tolerancia global arbitraria.

## Corte legacy P1

1. Inventariar entradas reales al reconciliador y vínculos entre operación,
   intento, grupo, payload y comprobante. Mantener la clasificación legacy exacta
   y las guardas que inmovilizan el grafo moderno.
2. Contrastar los datos fiscales disponibles antes de vincular o reconstruir.
   Una diferencia queda en reconciliación y conserva la evidencia obtenida de
   ARCA, incluyendo una autorización conocida; no se presenta como rechazo.
3. Resolver cobertura de datos antiguos explícitamente. No enriquecer snapshots
   con datos actuales ni modificar hashes, fechas o payloads para hacerlos coincidir.
4. Conservar una recuperación legítima cuando pueda demostrarse su identidad.
   Si falta evidencia necesaria, documentar la salida de soporte y el efecto
   sobre la operatoria; un bloqueo permanente nuevo requiere la decisión de
   producto aplicable. No relajar la comparación para liberar numeración.

## Diseño previo del P1 — 09/10/2026

El usuario autorizó avanzar después de aceptar que diferencias o evidencia
insuficiente requieren revisión, conservando CAE y reserva. No se autoriza
despliegue ni se acredita incidencia productiva.

- Entradas: recuperación de operación individual y reservas stale usadas por
  emisión individual, lote, batch y reintento. Ambas invocan el mismo método.
  La clasificación legacy y sus locks antes/después de consultar se conservan;
  operaciones modernas, terminales, con varios intentos o guardas huérfanas no
  ingresan. La reconciliación externa de lotes es otro contrato.
- Fuente: grupo del mismo intento/lote/emisor, payload original cuyo hash
  coincide sin enriquecerlo; o comprobante autorizado parcialmente persistido,
  usando exclusivamente sus snapshots e ítems. Una nota sin payload asociado
  no puede reconstruir sus asociados desde el comprobante local. El vínculo sin
  grupo se limita a facturas A/B/C con snapshot e ítems completos. La empresa
  autentica la consulta; no aporta condición, moneda ni otros valores esperados.
  El ambiente histórico ausente permanece desconocido: no se le asigna el actual.
- Representación en memoria: comparación fiscal v1, decimales finitos sin
  tolerancia, componentes e IVA discriminados, moneda/cotización, concepto,
  períodos y asociados. Se reutiliza el constructor histórico WSFE, no la
  admisibilidad de nuevas emisiones. No hay migración ni cambio de hashes.
- El adaptador conserva precisión decimal internamente, incluyendo autorización
  atribuible cuando un componente está ausente o no es válido. La consulta HTTP mantiene
  sus números JSON existentes y agrega campos fiscales opcionales. Los consumidores
  HTTP y PF-05 exigen datos básicos completos como antes. El puerto mínimo PF-19C
  conserva el grafo ante toda consulta exacta, incluso parcial: no reconstruye ni
  libera una reserva desde esa respuesta. No se amplía PF-05 ni P2 moderno.
- Ausencia: concepto, tipo de emisión CAE y componentes necesarios ausentes
  impiden probar coincidencia. Colecciones opcionales ausentes equivalen a vacías
  sólo cuando no se enviaron elementos. Condición IVA y atributos opcionales de
  asociados se contrastan cuando ambos contratos los acreditan; la cobertura
  antigua desconocida no se inventa. Rango ausente se cubre sólo por el número
  canónico; un rango presente diferente no se ignora. Una diferencia conocida prevalece sobre
  campos no disponibles.
- Orden: guarda vigente, consulta de lectura, guarda vigente con locks, evidencia
  atribuible de CAE, carga protegida de fuente, comparación, creación/vínculo y
  actualización de grupo/filas/lote en la misma transacción. Las reservas activas
  e identidad única del comprobante mantienen sus constraints. Un fallo de
  persistencia no habilita otra solicitud de CAE.
- Transiciones: igualdad suficiente -> autorizado; diferencia -> reconciliación;
  evidencia insuficiente -> reconciliación. Ninguna borra payload, hash ni CAE
  conocido. «No existe» mantiene el contrato anterior y nunca descarta un CAE
  ya conocido. Soporte: verificar en el ambiente original y reunir evidencia
  privada; no editar payloads/hashes ni eliminar reservas para forzar un retry.
- Matriz: reconstrucción válida y vínculo parcial; moneda/cotización y neto/IVA
  con igual total; categoría, concepto, condición, fechas, asociados y tributos;
  respuesta incompleta/no finita; payload cambiado, inválido y de otro emisor;
  falta de payload con CAE; CAE contradictorio; guardas modernas/huérfanas,
  sesiones obsoletas y respuesta tardía. Dobles SOAP exclusivamente, sin CAE real.
  UI, confirmación e idempotencia de emisión no cambian; sus regresiones se
  verifican con la suite existente. Sin DDL nuevo; PostgreSQL aplica a locks y
  constraints existentes. Rollback de código no reescribe estados ni evidencia.

Contrato contrastado con el [manual WSFE oficial](https://www.arca.gob.ar/ws/documentacion/manuales/manual-desarrollador-ARCA-COMPG.pdf),
versión 4.7, consultado el 09/10/2026: `FECompConsultar` incluye los datos de
`FECAEDetRequest` y el tipo/código de autorización. La cobertura histórica
se distingue de los campos que devuelve una consulta actual.

## Corte integral P2 y PF-04

- Persistir antes del envío sólo los datos vitales para comprobar y recuperar
  la operación; no almacenar SOAP completo, Excels ni PDFs permanentes.
- Delimitar recuperación individual sin comprobante local y reconstrucción de
  grupos. La información disponible en ARCA no contiene necesariamente todos
  los detalles administrativos; distinguir evidencia fiscal de ítems originales.
- Reconciliar operación, intento, guarda RECE, grupo/filas y comprobante mediante
  transiciones atómicas, ownership, locks y comparación de estado vigente.
  Una consulta exitosa no autoriza a saltar las guardas modernas.
- Autorizar recuperación sólo con coincidencia suficiente y CAE acreditado;
  reconsultas son de lectura. La reconciliación nunca llama `FECAESolicitar`.
- Resultado incompleto, contradictorio o incierto conserva reserva y estado.
  «No existe» sólo libera conforme al contrato seguro de inexistencia y estado
  protegido; mantener las garantías de PF-02/PF-19 y reintentos cerrados.
- Probar caída entre consulta y commit, carreras, proceso reiniciado, respuesta
  tardía y replay terminal. Una autorización confirmada no vuelve a pendiente
  reintentable por fallar su persistencia administrativa.

## Primer corte P2: evidencia previa compartida

Preparación técnica del 14/10/2026; primer corte implementado. El objetivo del
primer corte es que cada intento nuevo conserve evidencia suficiente para
contrastar lo enviado y recuperar después sus datos originales, incluso sin
comprobante local. No declara terminada la recuperación moderna integral.
La preparación documental es nivel 0; la implementación es nivel 2 fiscal.

### Alcance y secuencia dentro de PF-04/PF-02

1. **Primer corte:** contrato versionado, persistencia previa al envío en los
   caminos individual y masivo, lectura independiente de datos actuales y
   comparación pura con consultas simuladas. Mantener las transiciones actuales.
2. **Continuación histórica:** consumir esa evidencia en comprobantes nuevos,
   PDF/QR y lecturas, con cobertura antigua explícita. Delimitar el vínculo y su
   conservación ante compactación antes de cambiar consumidores. El
   [segundo corte implementado](pf-04-lecturas-historicas-design.md) conserva emisor
   y punto de venta, su cobertura y la contención aceptada para evidencia inválida;
   no habilita recuperación moderna.
3. **Continuación de recuperación:** el
   [cierre moderno individual](#cierre-moderno-individual) precede al
   [cierre de grupos](#recuperación-moderna-de-lotes) y su matriz de concurrencia.

Son subcortes de PF-04/PF-02, en el orden del roadmap, sin adelantar WSAA,
padrón, notas, categorías de importes, ranking ni mejoras de UI.
PF-05 externo sigue siendo opcional.
Este primer corte no agrega endpoints, tareas periódicas, confirmaciones ni
acciones administrativas; tampoco habilita «No existe» para liberar un intento
moderno, reconstruye comprobantes o cambia la recuperación legacy P1.

### Base comprobada y consumidores

| Frontera actual | Hecho y consecuencia para el corte |
|---|---|
| `IntentoEmisionFiscal` e `IdempotenciaFiscalService.crear_intento_emision` | Conservan identidad, total, receptor básico, hashes y referencias RECE; la orquestación adjunta evidencia versionada dentro de la misma reserva |
| `FacturacionService._emitir_comprobante_locked` | Construye una vez `ComprobanteRequest` y congela evidencia dentro de la reserva, antes del commit |
| `FacturacionService._emitir_comprobantes_lote_locked` | Construye los requests dentro de la reserva del bloque; guardar una evidencia por intento y comprobar la correspondencia por número, sin depender del orden de respuesta |
| API individual y `resolver_operacion_idempotente_incompleta` | Mantener confirmación, permisos, conflicto de clave y replay; un replay no crea evidencia ni vuelve a enviar |
| `LoteComprobantesService.procesar_lote`, worker y `reintentar_grupos_fallidos` | Cubrir bloques, procesamiento individual alternativo y reintento síncrono; el reintento en cola vuelve por el procesamiento común, sólo para su selección |
| `_reconciliar_intento_stale`, recuperación stale de lotes y `_reconciliar_grupo_autorizado_existente` | Consumidores de regresión: la nueva evidencia no reclasifica como legacy ni abre guardas modernas o huérfanas |
| `_guardar_comprobante`, PDF/QR, consulta y reportes | Guardado exitoso conserva su conducta; el PDF/QR aún usa empresa y número del punto actuales. Capturar sus datos originales prepara la continuación histórica, pero no corrige todavía esas lecturas |
| PF-05 externo, scripts PF-19 y traslado SQLite/PostgreSQL | Los primeros conservan su contrato. El traslado debe preservar el nuevo esquema mediante una versión nueva, sin modificar los formatos históricos congelados |

`payload_hash` no permite reconstruir la solicitud. El payload del grupo es
evidencia del grupo, no una sustitución verificable de cualquier intento.
Conservar las implementaciones A-01/A-03, PF-03B, RG 5616, PF-13 y SC-09.

### Contrato de evidencia v1

Esquema implementado: tres columnas opcionales en
`intentos_emision_fiscal`: `evidencia_version`, `evidencia_json` y
`evidencia_hash`. Un CHECK admite las tres ausentes para antecedentes o las tres
presentes con versión `solicitud_fiscal/1` y hash hexadecimal SHA-256 de 64
caracteres. El lector valida estructura, versión, hash y pertenencia; un CHECK
de presencia no sustituye esa validación. No agregar una tabla de eventos ni
otro índice de numeración.

| Sección de `evidencia_json` | Contenido mínimo congelado |
|---|---|
| `contexto` | Empresa y CUIT representado, ambiente, operación/intento, punto ID/número, tipo/número planificado, grupo/lote si existen y referencias de guarda/revisión RECE y generación de duplicados aplicables |
| `solicitud_wsfe` | Todos los campos del `ComprobanteRequest` efectivamente enviado: identidad, fecha, concepto, condición IVA, moneda/cotización, seis componentes de importe, IVA con bases/alícuotas, tributos, períodos y asociados con sus atributos presentes |
| `presentacion` | Razón social, domicilio, localidad, provincia, condición IVA, ingresos brutos e inicio de actividades del emisor; tipo/número, nombre, condición y domicilio del receptor; observaciones e ítems originales con código, descripción, orden, cantidad, unidad, precio, descuento y tasa |
| `importes_guardado` | Resultados decimales ya calculados por PF-03B que utiliza el guardado del comprobante, incluidos subtotales de ítems; no calcularlos nuevamente al leer la evidencia |

La sección fiscal conserva ceros efectivamente enviados, listas vacías y
ausencias distintas; no habilita categorías nuevas. Los datos administrativos
no son campos acreditados por ARCA. No guardar el DTO HTTP completo, tokens,
certificados, SOAP, Excel, PDF, perfil, plantilla ni fichas completas.
Fecha y actor operativo reutilizan las columnas durables existentes.

Serialización canónica propia: JSON UTF-8, claves ordenadas, separadores
compactos, decimales finitos como strings sin exponente ni paso por `float`,
fechas de calendario técnicas explícitas e identificadores con su representación
contractual. Conservar el orden de ítems y asociados capturados. Incluir versión
y contexto en el hash; excluir sólo la propia columna hash. Mantener intactos
`payload_hash`, huellas lógicas, hashes RECE y de duplicados y sus normalizadores.
El hash detecta alteración accidental; no acredita autenticidad frente a quien
pueda reescribir la base completa.

Una sola construcción de solicitud alimenta evidencia y envío. La evidencia se
inserta con el intento dentro de su transacción y permanece inmutable: ningún
update de resultado, retry o lectura la reemplaza. El lector versionado no
revalida antecedentes mediante la admisibilidad de una emisión nueva ni los
enriquece desde empresa, cliente, padrón, perfil o configuración actuales.
CUIT representado y ambiente deben corresponder al cliente WSFE que realizará
el envío y al contexto RECE congelado, no sólo a la ficha que se leyó primero.

La comparación pura contrasta también el CUIT del emisor de la consulta con el
del contexto congelado. Otro emisor produce una diferencia; una identidad
ausente o inválida impide acreditar coincidencia. Una diferencia comprobada
prevalece sobre campos no disponibles, sin ejecutar transiciones fiscales ni
alterar el comparador legacy compartido.

### Invariantes y orden antes de CAE

1. Conservar emisor autorizado, ambiente explícito, fecha fiscal elegida y
   calendario válido; nunca asumir hoy. Preservar la confirmación irreversible
   vigente y la invalidación de revisión/clave cuando cambien datos fiscales.
2. Exigir `X-Idempotency-Key`: misma clave y payload produce replay sin segundo
   envío; misma clave con otro payload produce conflicto antes de reservar.
3. Mantener ownership, revalidación de duplicados, lock de numeración y snapshot
   RECE. No cambiar su orden ni usar la evidencia para superar una denegación.
4. Con número reservado, construir una vez el request decimal y la proyección
   mínima de guardado; insertar intento/evidencia con su guarda `pre_arca`.
   Verificar contexto, hash y correspondencia antes de confirmar la transacción.
5. Un fallo de construcción, serialización o commit previo impide enviar todo
   el bloque. Resolverlo por los cierres pre-ARCA existentes, sin CAE ni nueva
   incertidumbre inventada. Un commit ambiguo exige recarga durable y el flujo
   seguro existente; no supone que la reserva desapareció.
6. Conservar el preflight final y `_marcar_solicitud_arca_iniciada`. Comprobar
   desde el estado durable que cada request corresponde a su evidencia antes
   de llamar a WSFE. Después de un resultado de commit ambiguo no enviar.
7. Persistir CAE/comprobante y resultado con los mecanismos actuales. Si ARCA
   pudo autorizar o falla la persistencia posterior, conservar evidencia,
   autorización atribuible, reserva y reconciliación, sin otro envío automático.

En batch, todos los intentos del request deben tener evidencia confirmada; no
enviar un bloque parcialmente preparado. Un retry legítimo genera evidencia
para su nuevo intento, sin reemplazar la de intentos autorizados o inciertos.
La falta de evidencia de un antecedente no agrega un bloqueo nuevo a su replay,
consulta o recuperación vigente.

### Comparación y estados

Reutilizar `comparacion_fiscal.py` y los decimales de `FECompConsultar`; separar
la validación del sobre versionado de la comparación fiscal. Resultado puro:
`coincidente`, `diferente` o `no_disponible`, con campos/cobertura sin valores
privados. Una diferencia acreditada prevalece sobre ausencia de otros campos.
No usar tolerancia global ni confundir `null` con cero; colecciones se comparan
como multiconjuntos cuando su orden no tiene significado fiscal.

La v1 registra lo enviado, pero no promete que toda consulta histórica devuelva
condición IVA o atributos opcionales de asociados. Conservar cobertura explícita
del P1. La política suficiente para cerrar un intento moderno se define en su
continuación; un resultado puro coincidente no autoriza una transición.

| Entidad / situación | Conducta de este primer corte |
|---|---|
| Evidencia ausente en un antecedente | Permanece ausente; no completar retrospectivamente |
| Intento nuevo y guarda `pre_arca` | Evidencia completa confirmada antes del envío; si falla, cierre pre-ARCA existente |
| Guarda `arca_iniciada` o `requiere_reconciliacion` | Evidencia inmutable; no cerrar, liberar ni reenviar por compararla |
| Respuesta aprobada, rechazada o contradictoria | Mantener transiciones y correlación SC-09; evidencia original intacta |
| Operación terminal observada por una sesión antigua | Recargar y respetar CAS; no sobrescribir terminal ni respuesta durable |
| Lote/grupo/filas, autorizados parciales o guarda huérfana | Conservar estados, selección y contadores vigentes; no completar el grafo desde este corte |

La futura recuperación requiere CAE atribuible, coincidencia suficiente y
propiedad íntegra del grafo vigente, con locks/CAS antes y después de consultar;
cierre de operación, intento, guarda, comprobante y grupo/filas/contadores en su
transacción aplicable. CAE conocido, timeout, contradicción o consulta incompleta
mantienen reconciliación. La ausencia en una consulta nunca basta por sí sola
para liberar una guarda moderna. No invocar `FECAESolicitar` desde recuperación.

La revocación conserva el tratamiento vigente de trabajos ya aceptados; no
concede nuevas acciones ni acceso a evidencia de otro emisor. Una modificación
de esa política requiere su corte y decisión, no se introduce con el snapshot.

### Migración, concurrencia y recuperación del cambio

Migración Alembic aditiva, sin backfill ni reescritura de comprobantes, hashes o
estados. Antecedentes con y sin RECE quedan con las tres columnas nulas. Una
ausencia no prueba antigüedad ni clasificación legacy. Versionar el contrato
de traslado después de v5, manteniendo v3/v4/v5 congelados y su importación
compatible; una importación antigua deja evidencia ausente, sin inventarla.

Conservar las FK compuestas, unicidad del comprobante, reserva fiscal activa
y guarda RECE activa existentes. No añadir `ambiente` a sus índices ni cambiar
el dominio de numeración en este corte. La inserción de evidencia comparte la
reserva atómica; las actualizaciones de estado no la modifican. Probar SQLite
para estructura/compatibilidad y PostgreSQL desechable para locks, constraints,
dos procesos, sesiones obsoletas y commit fallido. Un lock Python no demuestra
exclusión entre API y worker.

Rollback de aplicación conservando columnas y evidencia, sin borrar reservas
ni convertir incertidumbre en fallo. El runtime anterior conserva sus garantías
aceptadas, pero los nuevos intentos vuelven a tener la cobertura previa: no
afirmar que produce evidencia v1. El downgrade de esquema debe rechazar eliminar
columnas con evidencia; ensayarlo sólo en bases desechables vacías. No restaurar
datos ni borrar evidencia como rollback.
La preparación no ejecuta migraciones, traslado ni operaciones productivas.

### Matriz y puertas de aceptación de la implementación

| Prueba esperada | Demostración exigida |
|---|---|
| Individual A/B/C y notas ya soportadas, servicios, monedas y decimales extensos | Evidencia igual a lo recibido por el doble WSFE; ítems y resultados PF-03B recuperables sin recalcular |
| Lote en bloques, camino individual alternativo, retry síncrono y en cola | Una evidencia por intento/número, sólo selección vigente; autorizados previos intactos |
| Clave o confirmación ausente; replay; misma clave con otro payload; doble click/carrera | Cero llamadas nuevas en rechazo/replay, un único envío cuando corresponde y sin evidencia duplicada |
| Fallo al preparar el segundo detalle o al confirmar reserva/guarda | Cero envíos parciales; recarga ante commit ambiguo y cierre seguro vigente |
| Caída tras reserva, tras marcar inicio, después de CAE y antes de guardar | Evidencia durable; incertidumbre/reserva preservadas y sin reemisión tras reinicio |
| Cambio de empresa/cliente/perfil/punto después de capturar | Lectura original estable; contexto cruzado o hash/versión inválidos rechazados como fuente de recuperación |
| Igual total con distinta moneda/cotización, neto/IVA, categoría, concepto, condición, períodos o asociados | Comparación identifica diferencia; no convierte datos ausentes en igualdad |
| Consulta sin campos, CAE conocido sin payload, valores no finitos y respuesta contradictoria | Cobertura insuficiente o diferencia explícita, CAE atribuible y reserva conservados |
| Legacy válido/incompleto, intento moderno sin evidencia, guarda huérfana y terminal tardío | Misma conducta P1 y RECE vigente; no abrir recuperación moderna ni sobreescribir terminales |
| Dos procesos y aislamiento por emisor/ambiente | Constraints reales impiden doble reserva y vínculos cruzados; mismos identificadores no mezclan evidencia |
| Migración y traslado nuevo/antiguo, ida y vuelta exacta, downgrade poblado | Nulos históricos conservados, evidencia íntegra, formatos congelados sin cambios y downgrade con pérdida rechazado |

Dobles de WSFE y bases desechables exclusivamente; sin WSAA/WSFE reales ni CAE
real. Una comparación simulada no acredita recuperación moderna productiva.
El constructor puro y su lector no deben efectuar consultas de red.
Medir tamaño de evidencia y memoria de un bloque sintético; persistir sólo los
campos anteriores, sin segunda copia de archivos ni materializar todo el lote.

Ejecutar pruebas enfocadas de idempotencia, facturación/batch, reconciliación
legacy, RECE, reintentos y traslado, más el harness PostgreSQL de
[testing](testing.md#postgresql-desechable). Completar lint, formato, suites,
auditorías y CI de nivel 2 según [calidad](change-quality-gates.md), sin rebajar
puertas ni mezclar actualizaciones de dependencias. La revisión fiscal final
sigue el runbook vigente una vez estabilizado el código; no corresponde una
pasada automática al preparar este documento.

QA sintética: guardar evidencia, simular caída, reiniciar la sesión y contrastar
el contenido original; comprobar que la operación incierta mantiene su estado
y que no hay segundo envío. Confirmación/UI no cambian: usar regresiones
existentes. PDF/QR y reportes conservan sus límites actuales y se validan al
abrir su continuación. Antes de cerrar, contrastar todos los consumidores de
la tabla, revisar idioma/privacidad y `docs:check`; registrar evidencia del
candidato fuera del contrato, sin declarar publicación ni despliegue.

Este apartado completa la rúbrica de alcance, invariantes, estados, orden,
fallos, concurrencia, ARCA, tests, revisión, hallazgos y cierre del
[checklist fiscal](fiscal-change-checklist.md) para preparar el primer corte.
La aceptación se contrasta con esta matriz; su evidencia concreta se conserva
fuera del contrato. Un hallazgo se acepta, rechaza o difiere tras contrastarlo,
sin ampliar automáticamente el corte. La publicación y el despliegue requieren
sus operaciones autorizadas por separado.

Referencia verificada: [manual WSFE v4.7](https://www.arca.gob.ar/ws/documentacion/manuales/manual-desarrollador-ARCA-COMPG.pdf),
revisión del 01/09/2026, consultado el 14/10/2026, sección `FECompConsultar`.
Devuelve datos fiscales y autorización; no sustituye el detalle administrativo
original. Esta preparación no depende de llamadas fiscales reales.

## Cierre moderno individual

Contrato implementado para facturas, NC y ND individuales. Ante
una interrupción posterior al envío, el operador puede verificar la
operación original y, si ARCA la autorizó, recuperar el mismo comprobante.
Los lotes, incluso los que procesan sus filas de a una, tendrán un corte
posterior por sus autorizaciones parciales, reservas compartidas y contadores.

### Verificación desde la aplicación

«Verificar estado» consulta y, cuando corresponde, cierra una **operación
ya registrada**. Al reabrir FactuFlow, el operador puede retomarla sin
volver a cargar el comprobante, incluso si se perdió la primera respuesta HTTP.
El servidor identifica el intento por una referencia persistente dentro del
emisor autorizado. Seleccionar otro emisor o perder el permiso impide consultar
los datos. Desde «Comprobantes» se listan las emisiones individuales pendientes
del emisor activo que llegaron a la frontera de ARCA. El formulario de emisión
verifica con su clave original y el listado retoma por identificador de operación.
Una referencia desconocida no crea una operación. La única operación de WSFE
que invoca la verificación es la consulta de comprobante `FECompConsultar`.

### Evidencia suficiente para el cierre

Validar la evidencia v1 y su pertenencia a la operación, intento y guarda.
Usar el CUIT representado y el ambiente originales al autenticar la consulta.
El cierre individual interpreta el resultado del
[comparador existente](../../backend/app/core/comparacion_fiscal.py) según la
evidencia exigida para cada caso.

| Caso | Evidencia exigida |
|---|---|
| Toda autorización | Resultado aprobado, tipo de emisión CAE, código y vencimiento válidos y atribuibles al mismo emisor, ambiente, punto de venta, tipo y número. Un CAE o vencimiento ya guardado debe coincidir. |
| Toda factura o nota | Identificación del receptor, fecha, concepto, moneda, cotización, importes y desglose de IVA y tributos según la solicitud congelada. Comparar decimales exactos y componentes, incluso cuando coincida el total. |
| Servicios o productos y servicios | Contrastar las fechas de servicio y de vencimiento enviadas. |
| NC o ND con factura asociada | Acreditar el tipo, punto de venta y número de cada asociado enviado. Contrastar también CUIT y fecha del asociado cuando estén disponibles. Dos originales distintos con igual importe siguen siendo una diferencia. |

El comparador puede devolver `coincidente` con `cobertura_desconocida`.
El número canónico acredita los extremos ausentes de una solicitud individual.
La condición IVA del receptor y el CUIT y la fecha de los asociados se
contrastan cuando están presentes. Su ausencia se admite sólo si coinciden
todos los datos exigidos en la tabla, incluida la identidad completa de cada
asociado. Conservar la falta de cobertura en el diagnóstico por campo. Un
campo malformado en la respuesta, cualquier otra falta de cobertura, una
diferencia, una consulta fallida o «no encontrado» conservan la reserva y
la reconciliación. La consulta nunca libera numeración.

### Cierre y reconstrucción

1. Identificar una operación individual con su intento y guarda correspondientes.
   Devolver el resultado durable si ya es terminal. Un envío todavía en curso
   conserva su protección. Para un intento recuperable, verificar la pertenencia
   antes de consultar a ARCA y hacer la llamada fuera de los bloqueos de escritura.
2. Al recibir la respuesta, recargar y bloquear los registros en el orden del
   flujo individual. Revalidar identidad, evidencia, fase y respuesta guardada.
   Si otro proceso ya cerró el intento, devolver su resultado. Una respuesta
   incierta publicada sólo podrá sustituirse si sigue siendo la del mismo intento
   y se acredita la autorización. Para pasar de `requiere_reconciliacion` a
   cierre terminal, condicionar la escritura a la fase y a la respuesta que se
   acaban de verificar. Una actualización concurrente exige releer el resultado.
3. Si ya existe un comprobante, verificar su identidad, CAE, detalle y vínculo
   antes de asociarlo. Si falta, reconstruirlo desde la evidencia congelada.
   Guardar en **una transacción** el comprobante y sus ítems, el intento
   autorizado, el cierre de la guarda y la respuesta de la operación. Ante un
   commit de resultado desconocido, releer el estado durable antes de actuar.
4. Usar los conceptos, cantidades, precios, descuentos, subtotales y datos del
   receptor originales. El guardado habitual también puede resolver o crear una
   ficha de cliente. Si la evidencia acredita la ficha original, conservar el
   vínculo. Si falta esa referencia, preservar los datos fiscales del receptor
   sin asignarle una ficha por coincidencia con el padrón actual. El detalle,
   PDF y QR deben reflejar los datos originales que les corresponden.
   Para NC/ND, el detalle y el PDF deben
   identificar la factura ajustada. Los informes de ventas e IVA deben contabilizar
   una sola vez el comprobante con su fecha fiscal, moneda e importes originales.

### Pruebas de aceptación del cierre individual

| Escenario con ARCA simulada | Resultado exigido |
|---|---|
| ARCA autoriza una NC. El servidor cae antes de guardar el CAE. Se reinicia, se reabre la aplicación y dos sesiones verifican a la vez. | Ambas recuperan el mismo número y CAE. Hay un único comprobante vinculado a la factura correcta, una autorización en la emisión original y cero solicitudes nuevas de CAE durante la recuperación. Probar la concurrencia con conexiones independientes a PostgreSQL. |
| La respuesta incierta ya está guardada, se perdió la respuesta HTTP o llega tarde la respuesta original. | La verificación puede recuperar el intento desde una nueva sesión. El cierre confirmado prevalece en todas las consultas posteriores. |
| Ya existe el comprobante o falla el commit al crearlo o vincularlo. | Verificar el registro existente. Tras recargar, hay un único cierre completo o continúa la reserva pendiente. |
| Mismo total con otro IVA o factura asociada, evidencia insuficiente, CAE contradictorio, guarda huérfana, timeout o «no encontrado». | Se conserva la evidencia atribuible y la reserva. El operador ve que la emisión sigue pendiente de verificación. |
| Cambio de emisor, ambiente o permisos. Cambio posterior de datos del cliente o del punto de venta. | Las consultas respetan el acceso y la identidad originales. Tras una recuperación válida, contrastar detalle, PDF, QR y reportes de ventas e IVA con la evidencia previa. |

### Límites de la implementación y recuperación del cambio

Los consumidores directos son la verificación del formulario, el listado de
comprobantes y el servicio individual. Se prueban como regresiones la emisión
normal, el replay idempotente y los caminos legacy y de lotes que comparten
reserva, consulta fiscal, persistencia y lectura histórica. El cierre nuevo
admite una guarda `arca_iniciada` vencida o explícitamente en reconciliación,
con un único intento, evidencia verificable y asociación RECE exacta. Un
antecedente sin evidencia, una guarda incompleta y una fase previa al envío
siguen el flujo de contención vigente. Ante revocación, la aplicación deja de
mostrar el intento al operador y vuelve a validar su acceso antes del cierre.
Conservar la auditoría del cierre y los instantes fiscales históricos. Los
índices y columnas actuales bastan para el corte y su reversión conserva los
resultados terminales y las reservas.

## Recuperación moderna de lotes

Diseño para implementación posterior, nivel 2 fiscal. Ante una interrupción,
la persona que opera el lote debe poder recuperar cada comprobante autorizado y
entender qué falta resolver. La verificación admite lotes procesados por bloques,
grupos emitidos de a uno y la selección original de un reintento síncrono o en cola.
Su única consulta fiscal es `FECompConsultar`, por número planificado y bajo el
emisor y ambiente originales. La acción realiza cero solicitudes de CAE.

### Lote de referencia y resultados visibles

Cada grupo representa un comprobante, aunque tenga varias filas de Excel.
En el ejemplo, B y C comparten una guarda RECE del punto de venta.

| Grupo y evidencia | Resultado de «Verificar estado» |
|---|---|
| A tiene una autorización, intento y comprobante local coherentes. | Conservar el comprobante y sus filas. Si falta el vínculo del grupo, repararlo sólo después de acreditar identidad y contenido. A cuenta una vez. |
| B fue enviado. ARCA confirma la autorización y falta el registro local. | Reconstruir desde la evidencia inmutable. Vincular el número, CAE, vencimiento, ítems y asociados originales. B figura como emitido por FactuFlow en el lote, PDF e informes. |
| C fue enviado. La consulta falla, informa «no encontrado» o devuelve evidencia incompleta o contradictoria. | Mantener el resultado pendiente, el CAE conocido si lo hubiera y la guarda compartida. B ya puede consultarse. |
| D pertenecía a la selección y se acredita que quedó sin enviar en esa operación. | Mostrar «Sin enviar». Mientras C esté pendiente, la verificación termina sin habilitar la emisión del remanente. |

Con A y B recuperados, el resumen muestra dos emitidos, uno pendiente de
verificación y uno sin enviar. Cuando C también se acredita como autorizado,
el lote queda parcial con tres emitidos y D disponible para una nueva selección
y confirmación fiscal. Un rechazo terminal ya acreditado conserva su motivo y
su propio tratamiento. La fecha y el punto de venta siguen siendo explícitos.

### Evidencia para distinguir un grupo sin enviar

Hoy el cierre por incertidumbre inmoviliza el sublote alcanzado y el remanente.
El conjunto de grupos procesados se calcula en memoria. Tras reiniciar, el
estado del grupo, el orden del Excel, la ausencia aislada de un intento y
«no encontrado» en ARCA son insuficientes para acreditar D.

Para interrupciones nuevas, registrar en el mismo commit de inmovilización el
ID de operación, la huella de la selección confirmada y la pertenencia de sus
grupos al sublote alcanzado y al remanente. Usar un evento durable del lote
ligado a esa operación. Bajo bloqueo, cotejar la partición con los grupos ya
procesados, cada guarda y sus intentos. Sólo clasificar D si el propietario ya
quedó impedido de enviar, la selección es íntegra, el envío exige un intento
durable previo y ningún intento de D cruzó la frontera en esa operación.
Contrastar las señales locales de número, CAE, comprobante, reservas y actividad
de otras operaciones. Un rechazo anterior de un reintento debe ser terminal y
atribuible a su propia operación.

Para operaciones anteriores, admitir la misma prueba mediante evidencia durable
equivalente o un cierre pre-ARCA comprobado del grupo. Una selección sobrescrita,
una guarda huérfana o una partición incompleta dejan al grupo pendiente de
revisión. No inferir historia ni rellenarla con una migración. D es una
clasificación operativa. En el cierre completo puede usar el estado de grupo
`fallido` que admite el circuito de reintentos, con motivo durable «Sin enviar»,
sin atribuirle un rechazo de ARCA ni contarlo dos veces en el resumen.

### Recuperación y cierre

1. Identificar la operación propietaria, emisor, lote, selección y generación de
   duplicados originales. Contrastar grupos, filas, intentos y revisiones RECE.
   Admitir operaciones inmovilizadas o cuya ejecución vencida ya quedó contenida
   mediante el flujo vigente. El trabajo activo del worker conserva su propiedad.
2. Verificar cada intento recuperable por su identidad fiscal. Reutilizar el
   lector, comparador y reglas de cobertura del corte individual, incluidos IVA,
   moneda y asociados. Consultar ARCA fuera de los bloqueos de escritura. Antes
   del cierre, revalidar el permiso del operador, la huella de evidencia, el
   propietario y el token y fase de la guarda.
3. Dentro de una transacción por resultado, tomar bloqueos en el orden del
   cierre post-ARCA del lote (operación, intentos, guardas, lote, grupos y filas,
   con orden estable dentro de cada conjunto). Crear o vincular un único
   comprobante idéntico, actualizar intento, grupo, filas y auditoría y
   recalcular contadores desde los grupos. Si corresponde publicar avance
   parcial, guardar en ese commit la respuesta todavía incierta con sus totales.
   Un vínculo con otro intento o grupo,
   o dos candidatos al mismo número, conservan la incertidumbre. Un commit
   ambiguo obliga a releer antes de volver a actuar.
4. Cerrar cada guarda sólo al acreditar la membresía completa de su sublote y
   el resultado terminal de **todos** sus intentos. Un rechazo exige evidencia
   terminal atribuible. Una guarda de otro punto u operación y una reserva de
   duplicados ajena quedan fuera del cierre. Liberar reservas propias sólo por
   el contrato aplicable a cada grupo. Un resultado parcial de B conserva la
   guarda de C y el bloqueo del lote.
5. Recalcular el estado global del lote y, por separado, el progreso sobre la
   selección original del reintento. Guardar junto al cierre la respuesta
   idempotente de esa operación con su formato de procesamiento o de acción.
   Condicionar la actualización al estado y respuesta observados. Una respuesta
   tardía del worker o un segundo operador deben releer el resultado ganador.
   Un replay terminal devuelve el resultado ya publicado. Al reabrir el lote,
   el detalle y los contadores leen el mismo avance durable.

### Acción en el detalle del lote

En el panel existente **Resolver pendientes del lote**, ofrecer **Verificar
estado** cuando el backend identifique una operación propia recuperable del
emisor activo. La disponibilidad y los totales corresponden a la operación
completa, también si el grupo pendiente está en otra página. El servidor resuelve
el número y el alcance a partir de la operación. Cada pulsación consulta una
porción acotada y conserva los resultados. Una continuación puede avanzar más
allá de un grupo inconcluso y una verificación posterior puede volver a consultarlo.
Mostrar el progreso, los comprobantes recuperados, los pendientes y los que
quedaron sin enviar. Si ARCA está indisponible, conservar el avance y permitir
volver más tarde, sin recargar el Excel.

La API y la pantalla deben aplicar la misma frontera con **Reconciliar ARCA
Web**. Esa acción conserva los casos externos legítimos y la compatibilidad
documentada para antecedentes sin un intento moderno propio en conflicto. Ante
un intento moderno pendiente o ambiguo, impedir que la vía externa registre el
grupo como `autorizado_externo` y deje abierta su guarda. Ofrecer la verificación
propia o indicar qué requiere revisión. Una revocación de acceso impide
consultar o publicar resultados para el operador revocado.

### Aceptación del corte de lotes

| Ensayo previsto con datos sintéticos | Evidencia que debe observarse |
|---|---|
| PostgreSQL, lote A/B/C/D, dos sesiones verifican el mismo grupo y grupos distintos de la misma guarda mientras llega una respuesta tardía del worker. | Un único B y una sola contabilización. C mantiene la guarda. Al resolver C, un solo cierre durable y D únicamente disponible mediante confirmación. Cero llamadas a `FECAESolicitar` durante la verificación. |
| Caídas antes del envío, después de la consulta, durante el commit y después de guardar antes de responder. Reabrir desde otra sesión. | Estado anterior completo o avance confirmado. Respeto del CAE conocido, las reservas, los resultados terminales y el replay. |
| Bloque con respuesta parcial, desordenada o incompleta, emisión unitaria dentro del lote, reintento síncrono y reintento por worker con selección parcial. | Asociación por número e identidad. Un rechazo probado conserva su alcance. Las filas no seleccionadas y los grupos ya autorizados conservan su historia. |
| Mismo total con otro IVA o asociado, permisos revocados, otro emisor o ambiente, selección o hash alterados, guarda sin membresía y D sin prueba suficiente. | Sin cierre indebido, liberación de números ni sobrescritura de evidencia. La reconciliación externa tampoco permite eludir el bloqueo. |
| Más grupos que una página, ARCA indisponible y regreso al detalle desde móvil y escritorio. | Avance recuperable, totales sin duplicación, acción accesible por teclado y grupos inconclusos visibles. Verificar detalle, PDF e informes de B aunque C siga pendiente. |

Se prevé usar el esquema actual de intentos, guardas, eventos y grupos. Si
resulta insuficiente para demostrar una transición, documentar la evidencia
faltante antes de ampliar el esquema. El retorno debe conservar comprobantes,
evidencia y reservas. Ensayar la lectura con la versión anterior en PostgreSQL
aislado, incluida la vía externa sobre pendientes modernos. Si la versión
anterior permite un cierre externo incompatible sobre un pendiente real,
resolver el riesgo en el plan de retorno antes de reabrir esa vía. La revisión
fiscal independiente y el QA se completan sobre la
implementación estabilizada.

## Dependencias y exclusiones

PF-12 acompaña constraints/migraciones necesarias; PF-15 registra procedencia
mínima y mensajes útiles. La recuperación de backups PF-11/PF-15 es un corte
distinto. La reconstrucción histórica externa PF-05 es opcional y no es requisito
para resolver un intento local ni para emitir.

Padrón actual no participa en la comparación de una emisión histórica. Notas y
nuevas categorías consumen el snapshot fiscal compartido sin cambiar intentos
inciertos ni interpretaciones históricas.

## Aceptación antes de implementar cada corte

- Coincidencia exacta, moneda/cotización distintas con igual total, cambio de
  neto/IVA y categoría, concepto, condición, fechas y asociados.
- CAE conocido sin payload, respuesta sin campos, legacy válido/incompleto,
  intento moderno, guarda huérfana y terminal observado desde una sesión antigua.
- Unitario, lote, batch, reintento y resultado parcialmente persistido; una sola
  atribución, sin solicitudes de CAE y sin cruzar emisor/ambiente.
- Definir esquema/versiones, igualdad, cobertura legacy, transiciones y rollback
  del corte; completar `fiscal-change-checklist.md` y probar constraints reales
  con el harness PostgreSQL cuando corresponda.

Referencia: [manual WSFE oficial](https://www.arca.gob.ar/ws/documentacion/manuales/manual-desarrollador-ARCA-COMPG.pdf),
consultado el 03/10/2026; verificar respuesta y campos vigentes al implementar.
