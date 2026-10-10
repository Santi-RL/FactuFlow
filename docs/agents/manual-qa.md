# QA manual reutilizable

Última revisión: 09/10/2026

Estado: VIGENTE.

Este documento define escenarios manuales que pueden repetirse. La evidencia de
una versión, el resultado de un smoke concreto y los conteos de pruebas viven en
el PR, dossier o plano de control correspondiente.

El estado desplegado autoritativo vive en el plano de control `VPS Hostinger` /
`vps-admin`. Este documento no acredita una instalación.

## Preparación segura

### Evidencia de recuperación PF-11/PF-15

En entorno sintético, abrir Sistema con resumen completo y cambiar a uno parcial,
fallido, sin cotejo o sin instante exacto del snapshot. Distinguir componentes,
fechas y alcance; la cobertura actual debe seguir desconocida. No hay llamadas
fiscales ni controles de restore. Retirar/inutilizar el archivo y actualizar:
descartar éxito anterior, sin exponer rutas o errores crudos. Un usuario común
no puede leer la API; una respuesta atrasada no debe sobrescribir la nueva.
Verificar hora argentina cerca de medianoche UTC. La recuperación real del
candidato requiere su ensayo aislado y evidencia privada, no una prueba de UI.

- Usar entorno local o desechable y datos sintéticos.
- Confirmar emisor y ambiente antes de cualquier prueba ARCA.
- No guardar credenciales, CUITs, CAEs, PDFs, Excels, capturas o logs reales en
  el repositorio.
- No emitir ni solicitar CAE sin autorización explícita del usuario.
- Si la prueba sólo verifica UX, usar dobles y bloquear toda salida fiscal real.

## Matriz por tipo de cambio

### Lecturas fiscales A-03

1. Usar comprobantes sintéticos autorizados, sin emitir: A/B con neto 0,03 e
   IVA 0,01; varias tasas/descuentos; NC; C; detalle ausente o contradictorio.
2. Verificar base 0,03, notas negativas visibles y base no acreditada cuando
   falta evidencia. Neto e IVA deben conservarse; C no debe llamarse exento.
3. Incluir PES y DOL, con cotizaciones distintas; alternar moneda en ventas,
   IVA y ranking. Totales y posiciones pertenecen sólo a esa moneda y el límite
   del ranking se aplica por moneda. Un código desconocido no se rotula pesos.
4. Cambiar emisor durante la carga: descartar la respuesta anterior. Revisar
   lista/detalle y PDF: moneda nominal y cotización histórica, sin conversión;
   PDF corriente de una página mantiene CAE, fechas e importes legibles.

### Instantes operativos y hora argentina

- Abrir el mismo lote con navegadores configurados en Argentina, UTC y otra
  región: carga, inicio, fin y actualización deben mostrar el mismo horario
  argentino; duración y progreso conservan el mismo intervalo.
- Comparar último ingreso de usuario y actualización del emisor; verificar un
  instante cercano a medianoche UTC que pertenezca al día argentino anterior.
- Comprobar que fecha fiscal y vencimiento del certificado no cambian de día.
  La evidencia antigua sin hora confiable conserva su indicación de cobertura.
- Preparar y validar un lote sintético con mocks, sin pulsar emisión ni llamar
  a ARCA. No inventar una hora para campos vacíos o inválidos.

### Fiscal o ARCA

- Simular recuperación legacy con mismo total y distinta moneda/cotización,
  neto/IVA, concepto, períodos o asociados: no reconstruye ni vincula; conserva
  CAE atribuible y reserva. Con evidencia original completa y coincidente,
  reconstruye o vincula una sola vez. No usar datos actuales del cliente.
- Devolver una consulta incompleta con CAE: conserva el código y requiere
  revisión. Un CAE ajeno o CAEA no se atribuye como CAE local; «no existe» no
  libera un intento que ya conserva autorización. Una resolución concurrente
  o guarda moderna impide sobrescribir el grafo. Usar sólo dobles locales.

- Con el simulador SOAP local, devolver cabecera de otro emisor/punto/tipo o
  detalle con otro receptor/rango: no se atribuye un CAE ajeno y la operación
  conserva reconciliación. No realizar llamadas fiscales reales.
- Simular cabecera contradictoria y R con CAE/vencimiento en individual y
  sublote. No deben guardarse comprobantes; CAE atribuible, intento, guarda y
  reserva permanecen recuperables. Repetir la operación no genera otro FECAE.
- Simular A/R legítimos, mezcla A/R con cabecera P y fecha opcional ausente:
  conservan el tratamiento vigente. Si la fecha llega discordante, se bloquea
  el cierre. El [contrato SC-09](sc-09-respuestas-wsfe-design.md) delimita los casos.

- Con dobles locales, preparar dos clientes del mismo emisor y documento.
  La carga manual conserva receptor y comprobante autorizado sin elegir una ficha;
  elegir explícitamente una conserva su vínculo. Repetir en lote y recuperación.
  Un error real posterior a autorización debe seguir reconciliable, sin reemisión.

- Condición IVA del receptor: comprobar opciones compatibles A (RI/Monotributo),
  B (Exento/CF) y C (las cuatro); un cliente legacy RNI debe quedar visible y
  permitir corrección sin sustitución automática. Un lote con IVA vacío o
  incompatible informa el comprobante afectado; un formato con condición fija
  válida sigue funcionando sin columna adicional. Usar dobles sin salida CAE.
- fecha visible y payload técnico correctos;
- confirmación irreversible con fecha y punto cuando corresponda;
- éxito, rechazo, timeout y respuesta incierta;
- replay con misma clave idempotente;
- ausencia de reintento automático si ARCA pudo autorizar;
- reconciliación y mensajes sanitizados;
- otro emisor, ambiente o punto no puede reutilizar el estado.

### Fidelidad del receptor PF-13

Con Excel sintético y dobles sin salida CAE:

- Importar CF con CUIT, CUIL y DNI explícitos, también bajo el umbral: comprobar
  número, nombre y tipo efectivo en revisión y request; snapshot PDF/QR fiel.
- Usar columna o valores fijos válidos en archivos homogéneos; una condición
  vacía/desconocida o contradictoria y un DNI con letras deben identificar el
  error antes de reservar numeración o enviar.
- Un formato antiguo sin tipo de documento debe pedir corregir configuración;
  clonar uno protegido y comprobar que el original y los lotes anteriores siguen
  intactos. Un tipo fraccionario no se convierte en un código entero.
- CF anónimo permitido bajo el umbral; sumar varios ítems hasta identificación
  obligatoria y comprobar rechazo previo. Cero no permite saltar ese control.
- Reimportar contenido identificado con nombre/representación equivalentes:
  mantener avisos de duplicados, confirmaciones específicas y aislamiento;
  replay y resultado incierto conservan datos congelados.

### Ítems e importes

- Revisar 0 %, 10,5 %, 21 % y 27 % con fracciones y descuentos; mitad de
  centavo `1,005` debe mostrar `1,00` en la revisión, sin cambiar el cálculo.
- La revisión HTTP no lleva confirmación ni clave y no consulta ARCA ni crea
  estado fiscal; sólo se llama al revisar, no al escribir cada valor.
- Simular respuesta tardía, error HTTP, edición de importe y cambio de emisor:
  no habilitar una confirmación vieja; repetir la revisión permite recuperarse.
- Usar tasas 2,5 %, 5 % o desconocidas en API, Excel y pendientes anteriores:
  error por ítem/fila antes de CAE, sin convertir a cero. Históricos autorizados
  e inciertos conservan payload, clave y reconciliación.
- Comparar resumen de dos comprobantes con mitad de centavo y uno con IVA 27 %:
  sumar los importes fiscales por comprobante; no usar estimados antiguos.
- vaciar cantidad o precio: el mensaje identifica el campo y no muestra un
  total inventado; corregirlo permite continuar;
- precio cero y descuento 100 % explícitos conservan su significado;
- editar datos tras revisar cierra la vista previa y la confirmación anterior;
- comprobar fecha y punto en la confirmación irreversible;
- verificar que un estado incierto reutiliza la solicitud y clave congeladas;
- importar descuento vacío, decimal argentino, texto ilegible y fuera de rango
  con formato oficial y personalizado: sólo las entradas válidas son emitibles;
- un total informado inválido produce error, sin convertirse en ausencia;
- los detalles de error no exponen el body ni datos privados.

### Lotes y worker

- lote completamente válido;
- observaciones previas sin emisión;
- error parcial y reintento seguro;
- worker detenido, reiniciado y con claim concurrente;
- lote stale intacto frente a lote con evidencia fiscal;
- preservación de datos recuperables y cero duplicación.

### Prevención de duplicados en lotes PF-13/PF-17

Usar el [diseño de duplicados](pf-13-duplicados-lotes-design.md) como contrato.
Preparar fechas fiscales explícitas, dos emisores, dos usuarios y archivos
sintéticos; la API y el worker deben usar servicios fiscales simulados y una
base aislada. Registrar por separado los resultados técnicos y la revisión
visual/contable de la persona usuaria.

- Validar ventas anónimas que repiten fecha e importe dentro del mismo lote:
  no aparece una advertencia interna. Repetir con nombre definido o documento
  coincidente y comprobar que se explica la coincidencia por receptor.
- Procesar el primer lote con el simulador. Importar otro Excel con el mismo
  contenido completo, filas reordenadas y distinta huella de carga: aparece la
  coincidencia histórica, también para receptores anónimos. La misma importación
  conserva su restricción propia.
- Usar el mismo nombre de archivo, cantidad e importe total con contenido
  distinto: esos agregados no bastan para afirmar duplicación. Un comprobante
  anónimo que coincide con uno de un lote anterior de cien tampoco constituye
  por sí solo una coincidencia de lote completo.
- Comprobar coincidencia parcial identificada y lote anterior parcialmente
  emitido: distinguir cantidad e importe afectados, totales de ambos lotes y
  resultados autorizados, fallidos o pendientes, sin atribuir emisión total.
- Consultar importes de una moneda, monedas diferentes y moneda histórica
  desconocida: mostrar unidades y desgloses, sin suma mixta ni conversión
  implícita. El detalle identifica el comprobante actual por su referencia.
- Verificar archivo y lote anterior, fechas y usuario que solicitó emitir.
  Cargar con un usuario y emitir con otro, incluido el worker. La historia
  incompleta debe indicar la ausencia de actor u hora confiable. Un antecedente
  individual se presenta como comprobante, sin inventar lote ni archivo.
- Abrir la advertencia y verificar que «Volver a revisar» tiene mayor énfasis
  y foco inicial. El checkbox empieza vacío; marcarlo sólo habilita la acción
  secundaria y no cambia el foco ni emite. El retorno conserva archivo y opciones.
- Recorrer el diálogo con teclado: Enter implícito no emite, espacio sólo marca
  el checkbox y Escape/cierre vuelven a revisar. Comprobar etiquetas accesibles,
  orden y restauración de foco, zoom y ancho móvil.
- Consultar el lote anterior y el detalle paginado sin perder la preparación.
  Si aparece evidencia relevante nueva, se actualiza el aviso, se desmarca el
  checkbox y el foco vuelve al retorno. Cambiar emisor, lote o selección con una respuesta
  pendiente no debe reutilizar esa respuesta ni su aceptación.
- Un cambio sólo de testigos conserva la clave y la confirmación fiscal del
  mismo material; un cambio de datos fiscales las invalida. Consultar el detalle
  nunca concede una aceptación ni envía automáticamente una solicitud fiscal.
- Confirmar la excepción y comprobar que se conserva la misma operación y la
  confirmación fiscal correspondiente a los datos revisados. Doble clic,
  respuesta repetida y reenvío de la misma solicitud no producen una segunda
  solicitud fiscal simulada.
- Con dos sesiones, pausar un lote mientras otro equivalente intenta emitir:
  la operación ajena en curso impide la excepción. Repetir después de autorizar
  sólo parte del primer lote; el conjunto original sigue siendo reconocible.
- Ensayar rechazo, fallo anterior al envío e incertidumbre posterior: sólo los
  grupos seguros pueden reintentarse, sin reemitir los autorizados. La
  incertidumbre permanece bloqueada hasta reconciliarla con el simulador.
- Compactar un lote cerrado y volver a consultar su coincidencia y aceptación:
  la evidencia mínima permanece disponible. Repetir consultas desde otro emisor
  y ambiente para comprobar aislamiento.
- Ensayar el paquete de migración en PostgreSQL descartable: conservar selección,
  multiconjunto, actor y detalle; regenerar coordinación. Un paquete v3 conocido
  conserva su cobertura legacy y nunca se convierte en aceptación v2.
- Intentar continuar y reintentar un lote antiguo con aceptación no comprobable
  y coincidencias actuales, usando la clave original y otra nueva: debe quedar
  bloqueado sin transformar su aceptación ni perder historia. Comprobar también
  que se conserva el replay terminal, que una aceptación pendiente puede
  evaluarse con v2 y que la incertidumbre sólo se resuelve por reconciliación.

Las carreras reales de base de datos, migraciones y errores intermedios deben
demostrarse además con la matriz automatizada del diseño; un recorrido visual
con respuestas HTTP simuladas no reemplaza esas pruebas.

### Multiemisor

- Con cuentas sintéticas, iniciar sesión, restablecer la contraseña desde un
  administrador y comprobar que la sesión anterior queda rechazada. Entrar con
  la nueva contraseña y verificar los mismos permisos y emisores. Repetir el
  procedimiento por consola en una instalación aislada. No usar cuentas reales
  para ensayar las carreras SC-11: se demuestran con PostgreSQL descartable en
  la matriz automatizada de su [contrato](sc-11-login-reset-design.md).
- preparar un administrador, un operador asignado a A/B y un emisor C no
  asignado, todos sintéticos;
- comprobar cero, uno y varios accesos: login permitido sin accesos, selección
  automática con uno y elección explícita con varios;
- verificar A/B permitidos y C prohibido por header, query, body e ID directo;
- activar y desactivar `Puede crear y editar emisores`: la creación se asigna al
  creador en forma atómica y la edición requiere capacidad más acceso;
- comprobar que el operador nunca puede borrar emisores, administrar usuarios,
  entrar a `Sistema`, almacenamiento ni plantillas globales;
- promover y degradar conservando asignaciones; antes de degradar, revisar el
  alcance mostrado y confirmar conscientemente una lista vacía si corresponde;
- revocar el emisor activo durante una sesión: el siguiente request recibe
  `403`, se refresca la lista, se limpian selección y datos y no se cambia de
  emisor ni se cierra sesión automáticamente;
- cambiar o revocar mientras una respuesta está pendiente y confirmar que la
  respuesta tardía no actualiza stores ni pantallas;
- confirmar un lote sintético, encolarlo y revocar después: el worker puede
  terminarlo, pero cargas, confirmaciones, reintentos y consultas nuevas quedan
  bloqueadas;
- comprobar que clientes, certificados, puntos, comprobantes, lotes, PDFs,
  reportes, perfiles y formatos nunca cruzan emisores;
- verificar mensajes accionables que no revelen datos de C y cero solicitudes
  reales de CAE.

### UI administrativa

- lenguaje comprensible sin términos técnicos innecesarios;
- estados normales breves y errores accionables;
- toda acción requerida indica dónde y cómo realizarla;
- estados vacíos, carga, red y recuperación;
- teclado, foco, contraste y zoom razonables;
- no agregar confirmaciones o pasos que no mitiguen un riesgo concreto.

### Documentación

- el manual describe únicamente capacidades disponibles;
- API y ejemplos coinciden con rutas y contratos reales;
- roadmap, estado, changelog y diseños respetan sus responsabilidades;
- ningún documento vivo presenta historia o producción como estado actual;
- enlaces, idioma, privacidad y nomenclatura ARCA correctos.

## Puntos de venta desde PF-19D

Para un cambio que toque autoridad, preferencias o consumidores, verificar con
datos sintéticos y sin solicitudes CAE reales:

- primera comprobación manual con un punto `CAE - …`, otro sistema, un bloqueado
  y un dado de baja;
- puntos nuevos compatibles con uso habilitado por defecto, incluidos los
  temporalmente bloqueados o dados de baja;
- ausencia y reaparición sin perder ni reactivar una preferencia deshabilitada;
- rechazo atómico de respuesta vacía, duplicada, inconsistente, sin tipo o con
  timeout;
- aislamiento entre emisores y entre homologación y producción;
- usuario común y administrador pueden editar descripciones y uso, pero ninguno
  puede cambiar número, sistema, presencia, bloqueo o baja;
- confirmación explícita al cambiar `Usar en FactuFlow`, sin borrar formularios,
  perfiles ni lotes recuperables;
- constancia opcional que sobrescribe sólo descripciones presentes, muestra su
  procedencia, no consulta WSFE y no cambia elegibilidad ni revisión fiscal;
- vista habitual, `Mostrar todos`, contador y estados breves coherentes;
- individual, perfiles, lotes, worker, reintentos y continuaciones consumen
  `seleccionable_para_emision`;
- preflight agrupado al cumplir 90 días y guarda final antes del borde ARCA;
- cero operaciones, intentos, reservas y llamadas CAE ante un aborto previo;
- upgrade, rollback y reupgrade en SQLite y PostgreSQL; si existe evidencia WSFE
  nueva, el downgrade debe fallar cerrado.

El contrato completo vive en el
[`diseño PF-19D`](pf-19d-puntos-venta-authority-design.md).

## Precisión fiscal A-01

En un entorno sintético con ARCA simulado, cargar cantidad `1.00005`, precio
`0.1234567890123456789012345678`, descuento `0.00123` y cotización con más de
seis decimales. Revisar un código superior a 50 caracteres y un total superior
a `9007199254740992`. Comprobar detalle, listado, lote, PDF y reporte: conservar
cifras recibidas, sin redondeo del navegador. Reconciliación externa envía el
mismo importe. La revisión previa conserva el contrato vigente; su unificación
funcional y las bases IVA/moneda tienen cortes separados.

Repetir la clave de una autorización y simular falla de guardado posterior a
CAE: una sola llamada, estado reconciliable y solicitud durable intacta. Para
migración, usar copias desechables: comparar lecturas legacy, JSON y reservas;
probar upgrade, downgrade compatible y rechazo previo al DDL con datos ampliados.
Detener/recrear conexiones después del cambio. No realizar estas pruebas como
emisiones reales ni sobre una instalación operativa.

## Smoke local de aplicación

1. iniciar backend, frontend y base según el setup vigente;
2. comprobar health y login con usuario sintético;
3. seleccionar emisor y recorrer la pantalla modificada;
4. confirmar que no hay errores inesperados en consola o logs;
5. verificar que no se creó estado fiscal ni se llamó a ARCA real;
6. detener el entorno y revisar artefactos temporales.

## Smoke posterior a despliegue

Sólo se ejecuta dentro de una operación productiva autorizada y coordinada por
`vps-admin`. El recorrido genérico incluye salud, login, emisor, worker, pools,
pantalla afectada, logs y servicios vecinos. No incluye emitir ni solicitar CAE
salvo autorización fiscal separada.

Consultar [`production-workflow.md`](production-workflow.md); la evidencia real
permanece fuera del repositorio.

La evidencia histórica retirada de este documento se conserva en
[`manual-qa-through-v0.3.2.md`](../project/history/manual-qa-through-v0.3.2.md).

## Reintento parcial en segundo plano

En entorno de prueba con ARCA simulado, preparar un lote parcial con autorizados
anteriores y más fallidos seguros que el límite de un bloque. Seleccionar sólo
parte y confirmar fecha/PV; comprobar inicio en cola, progreso desde cero sobre
esa selección y conservación del resto. Recargar y volver al lote: recuperar
la misma operación, sin otro POST fiscal.

Simular fallo WSDL antes de CAE: debe quedar el motivo de conexión, sin consejo
de cambiar fecha/número, y los pendientes seguros deben volver a revisión.
Simular timeout después del envío: conservar incertidumbre, bloquear reintento y
reconciliar antes de repetir. Repetir la misma clave y competir desde otra sesión:
una sola ejecución, sin liberar reservas ajenas, activas o inciertas. No ejecutar
estos fallos ni pedir CAE reales como smoke productivo.
