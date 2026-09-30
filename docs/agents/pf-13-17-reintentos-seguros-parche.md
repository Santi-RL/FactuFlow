# PF-13/PF-17 — parche de emisión parcial y reintentos seguros

Última revisión: 30/09/2026

Estado: IMPLEMENTADO; contrato de comportamiento vigente.
Prioridad del corte: P1 de continuidad operativa. La evidencia y recuperación
viven en el [dossier](../project/releases/pf13-17-reintentos-seguros.md).

## Objetivo y límite

Ante una interrupción de emisión masiva, el sistema debe conservar lo autorizado,
explicar qué ocurrió y permitir resolver desde el mismo lote los pendientes
seguros, sin intervención SQL ni creación de otro lote como procedimiento normal.
El reintento debe ser eficiente y mostrar progreso real hasta un resultado durable.

La evidencia del incidente justifica un corte correctivo independiente de la
eficiencia general P2 y del rediseño visual futuro. La recuperación operativa
puntual no corrige el código. Los detalles de la instalación y la evidencia
privada permanecen en `VPS Hostinger` / `vps-admin`; este contrato no los reproduce.

No es posible impedir todas las caídas de red o de ARCA. El parche debe evitar
que se conviertan en bloqueos residuales, reenvíos inseguros o mensajes engañosos.

## Alcance obligatorio

1. **Preparación de conexión.** Revisar la construcción de clientes WSAA/WSDL y
   su relación con la caché de autenticación: evitar inicializaciones y accesos
   de red redundantes por comprobante, con aislamiento por emisor, ambiente y
   certificado. Un fallo en esta fase debe registrarse como previo a CAE cuando
   la evidencia lo demuestre. No atribuirlo al Excel ni al rechazo fiscal de ARCA.
2. **Cierre y reservas.** Toda salida terminal debe persistir resultado y estado
   coherentes. Liberar únicamente reservas de duplicados propias que ya no
   correspondan a trabajo activo o incierto, con transacción y comparación de
   propietario. Resolver también operaciones rechazadas antes de emitir que
   queden abiertas y reservas residuales de operaciones terminadas. Conservar
   intentos, respuestas y trazabilidad; no liberar numeración fiscal ni alterar
   autorizados para desbloquear un reintento.
3. **Reintento eficiente y durable.** Procesar la selección explícita de fallidos
   seguros mediante el camino masivo y bloques compatibles donde corresponda,
   conservando sus validaciones. Evitar repetir toda la preparación por cada
   comprobante. La ejecución y su seguimiento no deben depender de mantener
   abierta una solicitud HTTP durante todo el lote ni de los tiempos del proxy.
   Reutilizar la infraestructura existente antes de agregar componentes.
4. **Progreso visible.** Barra y contadores de la operación actual: seleccionados,
   autorizados, fallidos verificados, pendientes e inciertos cuando existan.
   Mostrar actividad y estado terminal; no reutilizar el «100 %» de una emisión
   anterior. Al recargar o volver al lote, recuperar el seguimiento de la misma
   operación. Evitar un segundo envío por doble clic, desconexión o recarga.
5. **Errores accionables y persistentes.** Distinguir conexión no disponible,
   fecha inválida, cambio real de numeración, conflicto de operación y resultado
   incierto. No usar un aviso de fecha como fallback ni recomendar actualizar
   numeración si sólo falló su consulta. El motivo y el siguiente paso deben
   quedar consultables en el lote, aunque desaparezca un aviso temporal.

La optimización y la barra de progreso forman parte del parche P1; corregir sólo
la reserva no cierra esta unidad. Los ajustes de WSAA, contratos HTTP y señales
necesarios se incluyen de forma acotada, sin esperar las líneas generales
PF-09/PF-14/PF-15 ni incorporar plantillas, dashboard o rediseño completo.

## Invariantes y diseño previo

- Reintentar únicamente la selección autorizada del emisor activo. Preservar
  fecha explícita, punto de venta, tipo, receptor, importes y confirmación fiscal.
- Mantener idempotencia, replay durable, control de duplicados y guardas PF-19.
  Una clave repetida o una carrera no puede producir otro envío fiscal.
- Si ARCA pudo autorizar, conservar incertidumbre y reconciliar antes de cualquier
  nueva solicitud. Ni un timeout ni la antigüedad de una reserva prueban rechazo.
- No incorporar reintentos automáticos de CAE ni colas fiscales offline. Cualquier
  repetición técnica de consultas o preparación debe estar acotada, separada del
  envío fiscal y cubierta por pruebas.
- La recuperación de reservas históricas debe demostrar propietario, operación
  terminal y ausencia de trabajo activo o incierto. Si no puede demostrarlo,
  conservar el bloqueo y explicar la reconciliación o revisión necesaria.
- Antes de codificar, completar el [checklist fiscal](fiscal-change-checklist.md):
  consumidores UI/API/worker, estados y transiciones, locks y comparación de
  propietario, revocación de acceso, recuperación tras caída y límites de bloques.
  Precisar el contrato de inicio, consulta y replay de la operación durable.
- Preservar el [contrato de duplicados](pf-13-duplicados-lotes-design.md).
  Una mejora de velocidad no permite omitir preflights fiscales obligatorios.

## Aceptación y regresiones obligatorias

Usar datos sintéticos y servicios ARCA simulados; ninguna prueba de este parche
debe solicitar CAE real ni reutilizar datos privados del incidente.

| Escenario | Resultado exigido |
|---|---|
| Corte de conexión al preparar un bloque, antes de CAE | Clasificación verificable previa a CAE, resultado durable y pendientes recuperables; sin atribuir error de datos ni tocar lo autorizado |
| Operación parcial terminal con grupos no alcanzados | Reservas propias liberadas de forma segura; nuevo reintento desde el mismo lote sin SQL manual |
| Conflicto previo al envío | Operación coherente y replay del resultado; no queda falsamente en curso ni deja reservas propias bloqueantes |
| Reserva ajena, operación activa o resultado incierto | No liberar ni reenviar; mantener aislamiento y reconciliación aplicable |
| Timeout después de enviar a ARCA o fallo al persistir CAE | Estado incierto recuperable; ningún reintento ciego ni numeración liberada |
| Doble clic, replay, dos operadores, recarga o corte del proxy | Una sola ejecución fiscal y seguimiento recuperado; sin duplicados ni pérdida del resultado |
| Caída del worker antes y después de la frontera CAE | Recuperación conforme a evidencia durable; no confundir pendiente seguro con incierto |
| Reintento masivo con remanente mayor que un bloque | Sólo selección confirmada; envío agrupado cuando compatible, contadores exactos y autorizados anteriores preservados |
| Comparación de rendimiento | Misma carga sintética, latencia simulada y configuración para emisión normal y reintento; registrar tiempos, inicializaciones y llamadas. El caso agrupable usa bloques y no repite preparación WSAA/WSDL por comprobante |
| Progreso y errores en UI | Barra de la operación actual, actividad visible, resultado al recargar y motivo persistente; conexión fallida no se presenta como fecha o numeración incorrectas |
| Fecha/PV, permisos o contenido cambiados | Revalidación y rechazo/confirmación según contrato vigente; ninguna ampliación silenciosa de la autorización |
| Cierre correcto | Cada autorizado tiene CAE y vínculo coherente; cero duplicados fiscales, reservas residuales propias o operaciones falsamente activas |

Cubrir transacciones y concurrencia en PostgreSQL, además de los motores
soportados que correspondan, y el recorrido de UI con backend simulado. Registrar
el benchmark y los casos de error en el dossier del corte, sin prometer tiempos
absolutos frente a un servicio externo.

## Cierre y entrega

El parche se cierra con implementación, regresiones fiscales y de concurrencia,
medición de rendimiento y QA de progreso/errores aprobadas. El dossier debe
explicar compatibilidad con operaciones previas y rollback proporcional.

Publicación y despliegue requieren su autorización y el
[flujo de producción por SHA exacto](production-workflow.md). Los smoke checks
no emiten comprobantes reales. El estado desplegado se acredita en el plano de
control; este documento no lo presupone ni autoriza una nueva emisión fiscal.
