# SC-09 — correlación y coherencia de respuestas WSFE

Fecha: 07/10/2026. Corte P1 fiscal autorizado por Santi antes de A-03.

## Objetivo y autoridad

Una respuesta de `FECAESolicitar` sólo acredita un resultado terminal cuando
corresponde a la solicitud y sus resultados son coherentes. El corte corrige
el parser compartido y su consumo individual y masivo; no cambia requisitos de
emisión, fechas, importes, receptor, numeración ni solicitudes enviadas.

Autoridad: [manual oficial WSFEv1](https://www.arca.gob.ar/ws/documentacion/manuales/manual-desarrollador-ARCA-COMPG.pdf),
[catálogo ARCA](https://www.arca.gob.ar/fe/ayuda/webservice.asp) y
[distinción oficial entre cabecera y detalle](https://servicioscf.afip.gob.ar/publico/abc/consultas_detalle.aspx?id=14558517).
La cabecera resume todos los detalles: A significa todos aprobados, R todos
rechazados y P una combinación. P en un detalle no acredita un terminal.
Se verificó el manual de producción v4.7, revisión del 01/09/2026. `CbteFch`
es opcional en la respuesta; los identificadores del emisor, receptor y rango
son obligatorios. La ausencia de fecha no introduce una restricción adicional.

## Checklist fiscal previo

**Riesgo Nivel 2.** El código interpreta respuestas posteriores a una solicitud
de CAE. Una atribución incorrecta podría guardar una autorización ajena; un
rechazo contradictorio podría liberar una reserva y habilitar una repetición.

Consumidores: cliente WSFE unitario y batch, parser individual legacy,
`FacturacionService.emitir_comprobante` y `emitir_comprobantes_lote`, API de
comprobantes, servicio de lotes, worker, continuaciones y reintentos. El replay
consume estado durable; la reconciliación consulta `FECompConsultar`. Esta
unidad no modifica el contrato de esa consulta ni amplía reconciliación legacy.

Invariantes:

- Fecha fiscal explícita y confirmación irreversible vigentes.
- Idempotencia, locks, snapshot RECE y reservas durables anteriores a FECAE.
- Ningún CAE de una cabecera o detalle ajeno se asigna al comprobante solicitado.
- La contradicción no constituye rechazo ni libera numeración.
- No se vuelve a solicitar CAE para resolver una respuesta incierta.
- Los CAEs correlacionados permanecen como evidencia, sin crear comprobantes
  autorizados a partir de una respuesta contradictoria.
- Las emisiones legítimas, rechazos verificables y parciales de cabecera
  conservan el comportamiento vigente, sin pasos o confirmaciones nuevos.
- Aislamiento por emisor y ambiente, precisión A-01 y snapshots intactos.

## Contrato del parser

1. Conservar el tratamiento estructurado de errores globales: únicamente el
   contrato exacto de `10005` ya implementado permite rechazo excluyente.
2. Sin errores globales, exigir cabecera y correlacionar `Cuit`, `PtoVta`,
   `CbteTipo` y `CantReg` contra emisor/request. Son enteros SOAP exactos, sin
   aceptar booleanos, strings ni coerciones de valores discordantes.
3. Exigir cantidad y conjunto exactos de rangos; ordenar por rango, nunca por
   posición. Comparar concepto y documento del detalle con el request; comparar
   también la fecha fiscal cuando esté informada. Un dato obligatorio ausente,
   inválido o discordante vuelve incierto el sublote.
4. Validar cada aprobación mediante CAE y vencimiento calendario vigentes.
   Un detalle P o inválido conserva el camino de incertidumbre existente.
5. Comparar el resumen A/R/P de cabecera con los resultados A/R de detalles.
   Un resumen contradictorio, o un R acompañado por CAE/vencimiento, marca
   todo el sublote como incierto mediante una señal interna explícita.
6. Sólo después de correlacionar identidad y detalle se pueden transportar
   CAEs como evidencia de la solicitud. Identidad no comprobada genera error
   incierto sin atribuir esos CAEs: se conservan request, intento y reserva
   para consultar los números planificados mediante reconciliación.

La señal interna no añade campos a la respuesta HTTP. Los errores públicos
siguen indicando que se debe verificar el resultado antes de reintentar.

## Orden y estados

El orden previo a ARCA no cambia: validar contexto/confirmación/idempotencia,
tomar locks, reservar y persistir intento/guarda, marcar solicitud iniciada,
enviar FECAE, interpretar respuesta y persistir resultado.

| Respuesta | Comprobante | Intento y guarda | Continuación |
|---|---|---|---|
| A correlacionada, CAE válido | Persistencia vigente | Terminal autorizado | Replay durable |
| R correlacionada, sin señales CAE | Ninguno | Rechazo terminal vigente | Política vigente |
| P de cabecera con A/R coherentes | Tratamiento vigente por detalle | Cierre vigente del sublote | Sin cambiar política parcial |
| Identidad/rangos/datos obligatorios ausentes o discordantes | Ninguno | Requiere reconciliación, reserva activa | Consultar; nunca reenviar automáticamente |
| Resumen contradictorio o R con CAE | Ninguno en todo el sublote | Reconciliación; CAE correlacionado conservado | Consultar y reconciliar |
| Fallo al persistir después de FECAE | Sin éxito aparente | Guarda/intento durable o incertidumbre vigente | Recuperación existente |

El cierre individual y el batch deben seleccionar fase `reconciliacion` ante
la señal; no basta con cambiar el mensaje o un flag de la respuesta. El batch
no puede cerrar una guarda terminal mientras un detalle sea incierto.

## Errores, concurrencia y compatibilidad

Conservar rollback pre-ARCA, recuperación post-ARCA, compare-and-swap del
resultado, unicidad de reservas en SQLite/PostgreSQL y replays terminales.
No cambian tablas, índices, migraciones, transacciones ni adquisición de locks;
las pruebas existentes de concurrencia siguen siendo obligatorias. Una carrera
no debe transformar incertidumbre en resultado terminal.

Compatibilidad: las fixtures SOAP deben contener la cabecera y datos de detalle
del contrato oficial. Completar un doble sintético no autoriza a relajar el
parser real. Los dobles del servicio incluyen explícitamente la señal interna
cuando simulan una contradicción. No se reinterpreta historia persistida.

## Matriz de aceptación

- Cabecera ausente; cada identidad ausente, discordante o de tipo inválido.
- Resultado de cabecera ausente/inválido y A/R/P incoherentes con los detalles.
- Rangos faltantes, adicionales, repetidos, discordantes, booleanos y decimales.
- Concepto/documento ausentes o discordantes y fecha informada discordante.
- Fecha opcional ausente: preservar A, R y mezcla A/R legítimas.
- A válida, R sin CAE y P de cabecera con mezcla válida, unitario y batch.
- R con CAE y/o vencimiento: señal incierta y evidencia correlacionada.
- Individual/batch: cero comprobantes ante contradicción, CAE durable cuando
  está correlacionado, intento/guarda inciertos y reserva vigente.
- Replay/repetición de la misma operación no solicita otro CAE.
- Lotes/worker/reintentos mantienen la barrera de reconciliación; fallos
  post-ARCA no generan éxito ni borran evidencia.
- Error global 10005 exacto preservado; variantes no se vuelven terminales.
- Suites de consumidores, formato/lint, auditorías y revisión final exigidos.

Todas las pruebas usan datos sintéticos y dobles SOAP sin red fiscal. El QA
verifica estados administrativos existentes; no se hace una emisión real ni
se añade una pantalla. La evidencia de ejecución pertenece al PR, no al contrato.

## Alcance excluido y recuperación

Fuera del corte: SC-08/SC-11, A-03, presupuestos SOAP, dependencias, política
de contraseñas, nuevas reglas fiscales, release y producción. El riesgo residual
de otras fronteras se conserva en el portafolio. No se cierra Security Cloud
remotamente por haber reparado código.

Rollback de código por commit, sin restauración de datos. Los intentos inciertos
creados por esta protección se reconcilian mediante el flujo existente; un
rollback no autoriza a borrar reservas ni reenviar solicitudes.
