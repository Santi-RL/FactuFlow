# PF-18/PF-09 — padrón ARCA para clientes y emisores

Fecha: 03/10/2026.
Última revisión: 09/10/2026.

Estado: alcance aceptado para planificación; implementación pendiente. P2 fiscal
y administrativa, Después 3, tras la capacidad WSAA necesaria. ARCA es la fuente
autoritativa de la situación registral conocida; la caché conserva una observación
fechada, no una garantía de vigencia instantánea.

## Objetivo y fuentes

Reducir clasificaciones por desconocimiento y detectar cambios de régimen de
clientes; completar el alta de clientes y emisores por CUIT con los datos que
ARCA realmente proporciona. Mantener operación ágil y la instalación pequeña.
En archivos Excel, ofrecer esta capacidad como una opción explícita para
completar receptores; no consultar automáticamente cada archivo procesado.

El [manual oficial de constancia de inscripción](https://www.arca.gob.ar/ws/WSCI/manual_ws_sr_ws_constancia_inscripcion.pdf)
documenta `getPersona_v2`, credenciales WSAA por ambiente, representación y
consultas `getPersonaList_v2` de hasta 250 claves. El
[catálogo oficial](https://www.arca.gob.ar/ws/documentacion/catalogo.asp) identifica
el servicio `ws_sr_constancia_inscripcion`; el antiguo alcance 5 está deprecado.
Fuentes consultadas el 03/10/2026 y el 09/10/2026; verificar versión y habilitación
al implementar. El contrato actual de consulta recibe CUIT y devuelve razón
social o nombre/apellido e información de impuestos y estados registrales.

La [validación de planificación](../project/analysis/confiabilidad-arca-roadmap.md)
incluye simulaciones de deduplicación/caché. Sus tiempos no miden ARCA ni prueban
una integración ya implementada.

## Autoridad, condición fiscal y procedencia

1. Conservar situación registral, datos obtenidos, fuente, ambiente, identidad
   consultada, fecha/hora de consulta y cobertura/errores. Persistir sólo datos
   necesarios, con aislamiento y acceso autorizado; no una copia del padrón.
2. Resolver condición desde impuestos y estados vigentes y la respuesta completa
   aplicable. Ausencia, baja, respuesta parcial, error o ambigüedad significan
   «sin verificación suficiente»; nunca un default a consumidor final.
3. Distinguir situación registral de condición efectiva del comprobante y de
   identificación. Tener CUIT/CUIL no implica inscripción ni vuelve inválido por
   sí solo un consumidor final identificado. La consulta registral no prueba la
   naturaleza de una operación. Preservar el
   [contrato P1 del receptor](pf-13-receptores-importacion-design.md).
4. Para nuevas preparaciones, proponer la situación comprobada por ARCA como base
   y hacer visibles cambios respecto de datos locales/Excel/configuración.
   «Monotributo → RI» o una inscripción hallada donde había una clasificación
   manual CF requieren resolver los datos efectivos antes de confirmar, usando
   la revisión existente. No sobrescribir una condición explícita de operación
   ni cambiar letra, importes o configuración silenciosamente.
5. Una diferencia real se trata según normativa y compatibilidad del comprobante;
   no se agrega una confirmación rutinaria sólo por «CUIT + CF». Las excepciones
   válidas mantienen procedencia explícita. Definir el mapeo y esos casos con
   fuentes oficiales antes de codificar; la ficha registral sigue reflejando ARCA.
6. Un cambio de padrón actual no modifica comprobantes, PDFs, snapshots, hashes,
   replays, lotes confirmados ni intentos activos/inciertos del pasado. Preparar
   datos nuevos exige la validación y confirmación aplicables.

## Completar receptores desde Excel: opción bajo demanda

Decisión de producto del 09/10/2026: permitir cargar un Excel con una columna de
CUIT, sin razón social ni condición frente al IVA, y elegir **Completar datos con
ARCA** para obtener los datos disponibles. También debe servir para un archivo
de facturación que tenga esos campos incompletos o nombres cuya escritura se
quiera comprobar. Un listado que sólo contiene CUIT sirve para cargar receptores;
para emitir siguen siendo necesarios los demás datos de facturación, aportados
por el archivo, la plantilla, el perfil o la preparación admitida.

- La opción queda desactivada para cada archivo nuevo. Cargar o validar un Excel
  no inicia consultas de padrón, tampoco en segundo plano. Sin elegirla, el flujo
  conserva la carga manual y las validaciones fiscales habituales; no completa
  datos desconocidos por suposición ni agrega espera de padrón.
- Al elegirla, validar los CUITs, consultar cada identidad distinta una sola vez
  por preparación y reutilizar los resultados en todas sus filas. Usar caché y
  agrupación según la política siguiente; mostrar progreso y resultados sin
  prometer un tiempo de respuesta fijo.
- Completar campos faltantes con razón social o nombre/apellido y condición
  registral que pueda determinarse de la respuesta. Si ya hay datos, mostrar las
  diferencias en la revisión del lote y permitir incorporar los obtenidos de
  ARCA. No sobrescribir silenciosamente una condición efectiva de operación,
  cambiar la letra del comprobante ni ajustar importes.
- Las plantillas que consuman esta opción deben distinguir datos faltantes que
  pueden completarse por consulta de los datos efectivos exigidos para emitir.
  Revisar y validar el resultado completo antes de confirmar la emisión; la
  consulta no solicita CAE ni autoriza comprobantes.
- Guardar los datos incorporados con su fuente y fecha en la preparación y, al
  emitir, en el snapshot del receptor. Los reportes y el PDF de ese comprobante
  deben consumir esos mismos datos aceptados. La ficha de cliente, cuando se
  guarde o actualice mediante el flujo correspondiente, conserva su procedencia;
  consultar no crea o modifica clientes silenciosamente por cada fila.
- No reescribir el Excel original ni comprobantes, PDFs o reportes históricos
  con una consulta posterior. Una actualización registral se aplica a nuevas
  preparaciones y no reemplaza el receptor preservado de una emisión anterior.
- Una respuesta incompleta, CUIT inexistente, falta de permisos o caída del
  servicio deja visibles los campos pendientes y permite completarlos manualmente.
  No interpretar ausencia de inscripción o de respuesta como consumidor final;
  la posibilidad de emitir depende de las validaciones de los datos efectivos.
- Alcance inicial por CUIT. No tratar DNI, pasaporte, CUIL o CDI como CUIT ni
  deducirlo del número de documento. Ampliar la consulta a otros tipos exige un
  contrato oficial y habilitación comprobados; mientras tanto, conservarlos como
  identificación y admitir la carga manual de los datos que correspondan.

El [manual oficial de WSFEv1](https://www.arca.gob.ar/ws/documentacion/manuales/manual-desarrollador-ARCA-COMPG.pdf)
no incluye razón social en la solicitud de CAE, su respuesta ni la consulta del
comprobante. Se obtiene por el servicio de padrón y se conserva para confeccionar
el PDF y los registros de FactuFlow.
La situación registral observada sigue separada de la condición efectiva de
la operación: una persona inscripta puede actuar como consumidor final en una
compra para consumo privado, según la normativa y evidencia aplicables
([reglamentación del IVA, artículo 71](https://www.argentina.gob.ar/normativa/nacional/norma-51323/actualizacion)).

## Consultar antes, emitir con datos preparados

- En alta/edición, consultar tras CUIT completo y validado, con debounce y
  cancelación; permitir seguir completando el formulario. Mostrar qué campos se
  obtuvieron y confirmar su incorporación al guardar, sin otro asistente obligatorio.
- Al seleccionar un cliente fuera de la importación Excel, reutilizar la
  observación disponible y renovar anticipadamente cuando corresponda al flujo
  de clientes. En Excel, consultar o renovar sólo al elegir la opción anterior;
  iniciar un lote no dispara una consulta de padrón. Deduplicar CUITs por contexto
  autorizado, agrupar hasta el límite oficial y acotar concurrencia, memoria,
  timeouts y retries. No consultar
  una vez por fila.
- Objetivo técnico inicial de renovación: 24 horas, configurable y a ajustar con
  evidencia del servicio. No es vigencia legal ni una fecha que bloquee al usuario.
  Renovar sólo registros utilizados o solicitados dentro del flujo habilitado;
  un Excel con la opción desactivada no dispara renovaciones. Sin barridos
  permanentes de todos los clientes ni polling por factura.
- Mantener «verificado en ARCA el …», «actualizando» o «sin verificación» con
  lenguaje administrativo. Conservar último resultado bueno ante un error sin
  anunciarlo como consulta actual. La antigüedad sola no crea un bloqueo.
- La emisión consume el snapshot preparado: **cero consultas obligatorias de
  padrón en el tramo confirmación → solicitud de CAE**. La primera verificación
  puede requerir espera durante preparación si faltan datos fiscales necesarios;
  no esconder esa latencia ni convertir desconocimiento en CF para evitarla.
- Una respuesta tardía comprueba CUIT, emisor, revisión y edición actual antes
  de aplicarse. Cambios materiales anteriores a confirmar se revisan; después
  de congelar la solicitud se usan en futuras preparaciones, sin alterar la actual.
- Un circuito de fallos acotado evita saturar un servicio caído. Consultas
  registrales no reintentan emisiones ni comparten su cola irreversible.

Esta política reduce llamadas y evita esperas añadidas al CAE, pero admite que
un cambio ocurrido después de la última consulta todavía no sea conocido. Una
garantía de vigencia instantánea exigiría otra política y no se promete aquí.

## Alta de emisores y credenciales iniciales

- Reutilizar el mismo adaptador para proponer razón social/nombre, domicilio y
  condición registral del CUIT del emisor. No completar desde padrón datos que
  no acredita: email, teléfono, inicio de actividades exigido por otro contrato,
  puntos de venta, certificados, delegación o elegibilidad RECE.
- Consultar con una identidad existente autorizada para ese servicio y ambiente.
  No asumir que un certificado WSFE tiene habilitación de padrón ni que el nuevo
  CUIT autoriza su propia consulta sin credenciales disponibles.
- En una instalación sin identidad habilitada, conservar alta manual o constancia
  PDF; verificar desde ARCA una vez configurada la capacidad. No hacer depender
  el primer certificado de una consulta que necesita ese mismo certificado.
- Una consulta exitosa completa datos, pero no otorga permisos sobre el nuevo
  emisor, lo activa para facturar ni acredita propiedad del CUIT o sus puntos de
  venta. Preservar PF-06/PF-08/PF-19 y el rol que puede dar de alta emisores.
- Mantener los caminos actuales manual/PDF como alternativas con procedencia
  y cobertura visibles, sin eliminar el flujo por falta de habilitación o caída.
  No usar scraping, intermediarios públicos ni servicios de terceros como fallback.

## Interacciones y división de implementación

| Corte | Resultado y dependencia mínima |
|---|---|
| Adaptador y evidencia registral | Contrato SOAP, errores por persona, mapeo fiscal, aislamiento y caché limitada; usa WSAA coordinado PF-09 y persistencia PF-12 |
| Clientes y preparación | Alta/actualización, cambio de régimen y diferencias explícitas; consume receptor P1 y preparación común |
| Emisores | Reutiliza adaptador y evidencia; conserva bootstrap manual/PDF, permisos y validación de certificados/PV |
| Lotes y UX | PF-13/PF-17 consume consulta opcional agrupada, completa receptores desde CUIT y conserva los datos aceptados para reportes/PDFs, sin otro motor ni dependencia de terminar todo el rediseño |

Los cortes comparten servicio y semántica; su división permite demostrar errores
y permisos antes de ampliar consumidores. PF-05 histórico y una infraestructura
de jobs general no son dependencias.

## Aceptación y preparación antes de implementar

- Excel de receptores con sólo CUIT y archivo de facturación sin razón social ni
  condición: la opción completa datos disponibles, con revisión y validación
  antes de emitir; el listado de CUITs por sí solo no constituye una factura.
- Opción desactivada, incluso tras haberla usado en otro archivo: cero consultas
  o renovaciones de padrón por esa importación, sin espera de ese servicio.
- Nombre mal escrito y condición distinta de la observada: diferencias visibles,
  incorporación explícita y ninguna sustitución silenciosa de la operación.
- Datos aceptados coincidentes en preparación, registros, reportes y PDF del
  comprobante; consulta posterior sin cambios en emisiones históricas.
- CF manual sin conocimiento frente a monotributo acreditado; monotributo local
  frente a RI actual; baja, exento, estados no activos, datos ambiguos y parciales.
- CUIT válido/incorrecto, documento CUIL/DNI sin conversión automática, cliente
  anónimo permitido y CF identificado con operación explícita válida.
- Caché fría/caliente, renovación, cambios posteriores, caída, falta de permisos
  del servicio y error individual en consulta agrupada; cero fallback fiscal.
- Lote grande con CUITs repetidos y faltantes: llamadas proporcionales a sujetos
  faltantes únicos, resultados por persona y límites de memoria/tiempo.
- Respuesta después de editar/cambiar CUIT o emisor, después de confirmar y durante
  reintento/reconciliación; ninguna modificación del payload congelado.
- Primer emisor sin certificados, emisor adicional con identidad autorizada,
  aislamiento de roles/caché y datos incompletos sin inventarlos.
- Congelar contrato de mapeo, actualización/revisión, clave/retención de caché,
  disponibilidad de servicio y rollback por corte. El TTL inicial se ensaya con
  servicio autorizado al implementar; no fijar un SLA con simulaciones.
- Completar checklist fiscal; pruebas normales con dobles y datos sintéticos.
