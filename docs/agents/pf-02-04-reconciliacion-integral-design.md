# PF-02/PF-04 — reconciliación fiscal integral

Fecha: 03/10/2026.

Estado: planificación aceptada; implementación pendiente. Refuerza garantías
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
| Comparación y recuperación legacy | P1 fiscal, Ahora 3 | Evitar reconstruir o vincular como coincidente una respuesta fiscal diferente |
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
