# PF-02/PF-04 — reconciliación fiscal integral

Fecha: 03/10/2026.

Estado: comparación legacy P1 implementada; recuperación moderna P2 pendiente. Refuerza garantías
existentes por cortes, sin reabrir numeración ni habilitar reemisión automática.

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
| Comparación y recuperación legacy | P1 fiscal, Ahora | Evitar reconstruir o vincular como coincidente una respuesta fiscal diferente |
| Snapshot y recuperación integral | P2 fiscal, Después con PF-04 | Evidencia mínima suficiente y reconciliación segura de caminos modernos, unitarios y masivos |

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
