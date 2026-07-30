# PF-02A — Numeración individual compatible con historia externa

Fecha de diseño e implementación: 2026-07-27
Estado: cerrado e integrado en `main` mediante el PR `#15` (`c872497`).

## Objetivo y alcance

PF-02A permite que una emisión individual continúe cuando ARCA registra
comprobantes anteriores que no existen en FactuFlow. ARCA conserva la autoridad
sobre la secuencia fiscal global y FactuFlow conserva la autoridad sobre sus
propios intentos, idempotencia y resultados inciertos.

Incluye:

- diagnóstico `alineada`, `arca_adelantada` o `local_adelantada` por emisor,
  punto de venta y tipo;
- candidato individual calculado como `ultimo_arca + 1` cuando no hay un intento
  propio bloqueante;
- panel previo con emisor, punto, tipo, último local, último ARCA y próximo
  número;
- segunda consulta `FECompUltimoAutorizado` después de la reserva durable e
  inmediatamente antes de `FECAESolicitar`;
- aborto terminal pre-ARCA si el número cambia o no puede reconfirmarse.

No incluye emisión masiva, reanudación del worker, importación histórica,
`FECompConsultar` por rangos, cambios de reportes, migraciones ni QA con CAE real.
La reconstrucción histórica permanece en PF-05 y no es requisito para emitir.

## Invariantes verificables

1. ARCA es la fuente de verdad del siguiente número fiscal global.
2. FactuFlow nunca ignora un intento propio `en_proceso` o
   `requiere_reconciliacion`.
3. `arca_adelantada` sin intento propio incierto informa la diferencia y permite
   únicamente la emisión individual con `ultimo_arca + 1`.
4. `local_adelantada` no ofrece candidato y bloquea la emisión.
5. El diagnóstico se limita al emisor activo, punto de venta y tipo solicitados.
6. La reserva fiscal se persiste antes de la segunda consulta a ARCA.
7. `FECAESolicitar` solo comienza si la segunda consulta confirma exactamente el
   número reservado.
8. Un cambio o error en la segunda consulta produce cero solicitudes de CAE,
   cero comprobantes nuevos e intento `fallido_verificado`.
9. Un fallo posterior a iniciar `FECAESolicitar` conserva las reglas de
   reconciliación de PF-01; no se convierte en fallo pre-ARCA.
10. No hay replanificación ni reintento automático. La UI invalida número y
    clave, y exige una actualización manual y una nueva confirmación fiscal.
11. La confirmación irreversible de fecha fiscal permanece sin cambios.
12. Al cerrar PF-02A, lotes y worker mantenían el control estricto previo hasta
    PF-02B; ningún número diagnóstico se copiaba a `numero_asignado`. PF-02B.1
    extendió posteriormente el núcleo batch sin alterar esta invariante.

## Estados y decisiones

| Estado observado | Candidato | Emisión individual | Acción |
|---|---:|---|---|
| `alineada` | `ultimo_arca + 1` | habilitada | reservar y repetir preflight |
| `arca_adelantada` | `ultimo_arca + 1` | habilitada con advertencia | no importar historia; reservar y repetir preflight |
| `local_adelantada` | ninguno | bloqueada | revisar historia fiscal |
| intento propio activo o incierto | ninguno | bloqueada | reconciliar el intento propio |
| segundo preflight estable | reservado | habilitada | iniciar `FECAESolicitar` |
| segundo preflight cambió | ninguno | abortada antes de ARCA | cerrar intento y exigir actualización |
| segundo preflight no disponible | ninguno | abortada antes de ARCA | cerrar intento y exigir actualización |
| respuesta ambigua después de FECAE | reservado | bloqueada | reconciliación PF-01 |

## Orden de operaciones

1. Validar request, emisor, punto de venta, receptor, fecha y totales.
2. Tomar locks propios y verificar intentos bloqueantes.
3. Consultar último local y `FECompUltimoAutorizado`.
4. Rechazar `local_adelantada`; aceptar `alineada` o `arca_adelantada`.
5. Crear el intento fiscal durable con el número candidato.
6. Construir el request local sin efectuar I/O fiscal.
7. Repetir `FECompUltimoAutorizado`.
8. Si cambió o falló, cerrar el intento como `fallido_verificado` y terminar.
9. Solo con coincidencia exacta, marcar la frontera ARCA e invocar
   `FECAESolicitar`.
10. Aplicar las transiciones post-ARCA de PF-01.

## Concurrencia y fallos intermedios

Los locks de FactuFlow no coordinan con otros sistemas. La segunda consulta
reduce la ventana y evita enviar un número ya obsoleto. Aun así, ARCA puede
rechazar explícitamente la consecutividad después de la consulta; ese rechazo
sigue siendo un resultado verificable, nunca un motivo de reintento automático.
Una excepción después de iniciar FECAE sigue siendo ambigua y requiere
reconciliación.

Si falla la persistencia del cierre pre-ARCA, el intento durable puede permanecer
bloqueante, pero no existe riesgo de CAE porque la frontera fiscal no se cruzó.
No se libera de forma optimista.

## Migraciones y compatibilidad

PF-02A no cambia tablas, constraints ni datos existentes. El contrato del
endpoint de próximo número se amplía y la UI se actualiza en el mismo corte. Se
asume un único `ARCA_ENV` configurado por instalación/base; compartir una misma
base simultáneamente entre homologación y producción queda fuera de alcance.

## Matriz automatizada

- alineación local/ARCA;
- historia local parcial con emisión del siguiente número ARCA;
- cambio externo entre ambos preflights, con cero FECAE;
- error del segundo preflight, con cero FECAE;
- numeración local adelantada, sin candidato;
- intento activo o incierto, incluida reconciliación de intentos vencidos;
- fallos ambiguos y de persistencia posteriores a FECAE;
- contrato API del diagnóstico y estado terminal pre-ARCA;
- respuesta frontend obsoleta, advertencia de historia externa, bloqueo local;
- invalidación de número y clave después de un aborto pre-ARCA;
- aislamiento por emisor ya cubierto por las dependencias y consultas existentes.

La puerta global aprobó `536` pruebas backend con `4` omitidas por harness
condicionado, `131` frontend y `7` de scripts, además de Ruff, Black,
type-check y build. ESLint terminó sin errores y conservó `13` advertencias de
estilo no bloqueantes. La revisión final única con Codex `gpt-5.6-sol medium`
quedó limpia, sin findings, con confianza `0,87`.

## QA manual permitida

Solo con dobles, homologación segura o consultas de lectura autorizadas. Este
corte no autoriza emisiones reales ni solicitudes de CAE. Antes de cualquier QA
con escritura ARCA se requiere autorización explícita y el modal de fecha fiscal.
