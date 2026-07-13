# Diseño PF-01A: integridad de autorización y estado incierto

Última actualización: 2026-07-13

Estado: COMPLETADO. PF-01A CERRADO; PF-01B QUEDA COMO CORTE POSTERIOR SEPARADO.

## Objetivo

Cerrar el primer corte de PF-01 en la capa de aplicación: una respuesta de ARCA
solo puede convertirse en autorización si contiene un CAE utilizable, y todo
resultado incierto posterior a iniciar `FECAESolicitar` debe quedar bloqueado y
reconciliable, nunca presentado como un error genérico apto para reintento.

Este corte precede a PF-02. No flexibiliza numeración ni resuelve todavía la
diferencia legítima entre el último número global de ARCA y la historia propia
de FactuFlow.

## Alcance

El corte PF-01A incluye:

- validación común de respuestas individuales y batch de `FECAESolicitar`;
- clasificación segura de excepciones antes y después de iniciar la llamada
  fiscal;
- persistencia de una respuesta idempotente estructurada cuando se requiere
  reconciliación;
- tratamiento explícito de ese estado en la pantalla de emisión individual;
- matriz negativa batch para resultados parciales, rechazados, incompletos,
  duplicados o cardinalidades incoherentes;
- pruebas de replay para garantizar que la misma operación no vuelva a pedir
  CAE.

Puede solicitar CAE indirectamente porque modifica el borde que interpreta la
respuesta de ARCA. Toca CAE, vencimiento, numeración planificada, operación
idempotente, intento fiscal, comprobante y UI de emisión. No cambia fecha
fiscal, punto de venta, tipo, receptor, ítems, totales ni comprobantes asociados.

## Fuera de alcance

- Restricciones y migraciones de estados/CAE/reservas: quedan para PF-01B.
- Flexibilización de numeración frente a historia externa: PF-02.
- Reconstrucción histórica desde ARCA: PF-05.
- Refactor general de lotes o del cliente SOAP.
- Cambios de fecha fiscal o de su confirmación irreversible.
- Llamadas reales a ARCA durante tests.

## Riesgo si falla

- aceptar como autorizado un comprobante sin CAE utilizable;
- permitir un reintento que vuelva a solicitar CAE después de una respuesta
  incierta;
- liberar o perder la reserva de un número ambiguo;
- persistir un comprobante incompleto o dejar un CAE sin representación local;
- permitir que la UI descarte la clave y el payload de la operación pendiente;
- asociar incorrectamente respuestas batch con números solicitados.

## Invariantes no negociables

1. `resultado == "A"` no alcanza: el CAE debe existir, tener exactamente 14
   dígitos y acompañarse de una fecha de vencimiento válida `YYYYMMDD`.
2. Una respuesta `P`, una aprobación incompleta, un error global o una
   cardinalidad ambigua nunca se transforma en éxito.
3. Un rechazo explícito y completo de ARCA es un fallo verificado; una respuesta
   incompleta o no interpretable requiere reconciliación.
4. Una vez iniciada `FECAESolicitar`, cualquier excepción que no demuestre un
   rechazo seguro queda como `requiere_reconciliacion`.
5. Misma clave y mismo payload nunca llaman dos veces a `FECAESolicitar`.
6. Misma clave con payload distinto responde conflicto.
7. La numeración de un intento incierto no se libera hasta que
   `FECompConsultar` demuestre que ARCA no registró el comprobante.
8. Un `Comprobante` autorizado solo se crea o vincula con CAE y vencimiento
   válidos y con emisor, punto, tipo, número, fecha y total coincidentes.
9. La UI conserva la clave y el snapshot del payload mientras la operación esté
   incierta; no permite editar, cancelar como si nada hubiera ocurrido ni crear
   silenciosamente otra operación equivalente.
10. El cambio de emisor o de datos fiscales no puede borrar el estado pendiente
    de reconciliación.
11. La fecha fiscal sigue siendo explícita y la confirmación irreversible sigue
    siendo obligatoria antes de cualquier solicitud de CAE.

## Tabla de estados

### Operación idempotente

| Estado origen | Evento | Estado destino | Efecto permitido |
|---|---|---|---|
| inexistente | clave y payload válidos | `en_proceso` | Crear operación durable antes de ARCA. |
| `en_proceso` | falla demostrablemente pre-ARCA | `interrumpida_pre_arca` | Permitir reclamo atómico con la misma clave. |
| `interrumpida_pre_arca` | replay idéntico gana CAS | `en_proceso` | Reanudar sin conflicto. |
| `en_proceso` | autorización válida y persistida | `finalizado` | Devolver siempre la misma respuesta. |
| `en_proceso` | rechazo ARCA explícito | `fallido` | Devolver el rechazo guardado; no marcar autorización. |
| `en_proceso` | resultado post-ARCA incierto | `requiere_reconciliacion` | Bloquear nuevo CAE y consultar ARCA de forma segura. |
| `requiere_reconciliacion` | ARCA confirma autorización y coincide | `finalizado` | Crear o vincular comprobante y guardar replay. |
| `requiere_reconciliacion` | ARCA confirma inexistencia | `fallido` | Liberar solo mediante transición verificada. |
| `requiere_reconciliacion` | consulta falla o no coincide | sin cambio | Mantener bloqueo y mensaje accionable. |

### Intento de emisión fiscal

| Estado origen | Evento | Estado destino |
|---|---|---|
| `en_proceso` | autorización válida persistida | `autorizado` |
| `en_proceso` | rechazo ARCA explícito | `rechazado_arca` |
| `en_proceso` | fallo local verificado antes de ARCA | `fallido_verificado` |
| `en_proceso` | respuesta o persistencia post-ARCA incierta | `requiere_reconciliacion` |
| `requiere_reconciliacion` | consulta coincidente con CAE válido | `autorizado` |
| `requiere_reconciliacion` | ARCA confirma inexistencia | `fallido_verificado` |

### Comprobante

En PF-01A solo se persiste como `autorizado` cuando CAE, vencimiento y snapshot
fiscal son válidos. Los constraints de base que prohíben otras combinaciones se
implementarán en PF-01B después de auditar datos heredados.

## Orden de operaciones

1. Validar emisor activo y pertenencia de punto de venta y cliente.
2. Validar payload fiscal, fecha explícita y confirmación irreversible.
3. Validar `X-Idempotency-Key`, calcular hash y resolver replay/conflicto.
4. Crear o reclamar operación idempotente.
5. Reservar el número en un intento fiscal durable.
6. Marcar el inicio real de la fase ARCA inmediatamente antes de
   `FECAESolicitar`.
7. Ejecutar `FECAESolicitar` una sola vez.
8. Validar estructura, cardinalidad, rango, resultado, CAE y vencimiento.
9. Si la respuesta es válida, persistir comprobante, intento y respuesta
   idempotente.
10. Si el rechazo es explícito, persistir el fallo verificado.
11. Si hay ambigüedad después del paso 6, persistir
    `requiere_reconciliacion` y responder `409` estructurado.
12. La UI conserva clave y payload; un replay idéntico consulta el estado
    durable y nunca vuelve automáticamente al paso 7.

El replay se resuelve antes de validaciones mutables que pudieran alterar el
payload. La pertenencia y la autenticación sí se revalidan en cada request.

## Contrato de respuesta incierta

La API debe responder `409` con un detalle sanitizado y estable que incluya:

- `requiere_reconciliacion: true`;
- `categoria_error` específica;
- mensaje que prohíba reintentar con otra clave;
- emisor, punto de venta, tipo y número planificado cuando estén disponibles;
- fecha fiscal y total del snapshot local;
- CAE y vencimiento solo si fueron recibidos y validados;
- próximo paso seguro: repetir la verificación con la misma operación.

No debe exponer payload SOAP, certificados, claves, tokens ni datos privados
innecesarios.

## Comportamiento de la UI

- Detectar el contrato `requiere_reconciliacion` antes del error genérico.
- Conservar la misma clave y una copia inmutable del payload enviado.
- Mostrar un estado dedicado y no un toast descartable como única evidencia.
- Bloquear edición y doble envío mientras la operación siga incierta.
- Ofrecer `Verificar estado`, que repite el mismo payload con la misma clave.
- No resetear clave por `watch(formData)`, cancelación o cambio de emisor mientras
  exista una operación pendiente.
- Desbloquear únicamente con respuesta final guardada: autorización
  reconciliada o fallo verificado que permita corregir datos.

La operación pendiente se conserva en memoria durante la vida de la vista y no
se escribe en `localStorage` ni `sessionStorage`, para no persistir payloads
fiscales ni datos privados en el navegador. La vista instala advertencia de
`beforeunload` y bloquea navegación interna. Una recarga forzada puede perder el
estado visual; el backend continúa siendo la autoridad durable y debe impedir un
segundo CAE. En ese caso la UI no autoriza una emisión nueva: corresponde auditar
o pedir soporte con el emisor original.

## Fallos intermedios esperados

| Falla | Estado esperado | Respuesta/acción |
|---|---|---|
| Doble click | una operación `en_proceso` | Una llamada fiscal; el segundo request recibe replay o conflicto en proceso. |
| Misma clave, payload distinto | sin cambio | `409` de idempotencia. |
| Validación o DB antes de ARCA | `interrumpida_pre_arca` o fallo verificable | Reclamable con misma clave; no reconciliar ARCA. |
| Transporte falla después de iniciar ARCA | `requiere_reconciliacion` | `409`; nunca `500` reintentable. |
| ARCA devuelve `R` completo | `rechazado_arca` | Fallo guardado, sin comprobante autorizado. |
| ARCA devuelve `P` | `requiere_reconciliacion` | No aceptar como autorización. |
| ARCA devuelve `A` sin CAE/vencimiento válido | `requiere_reconciliacion` | No crear comprobante. |
| Persistencia falla después de CAE válido | `requiere_reconciliacion` | Conservar reserva y datos conocidos para reconciliar. |
| Batch devuelve duplicados, faltantes o extras | ningún éxito ambiguo | Rechazar el conjunto como respuesta no confiable. |
| `FECompConsultar` no responde o discrepa | sin cambio | Mantener bloqueo. |
| UI recibe `409` estructurado | payload y clave congelados | Mostrar acción de verificación, no iniciar otra emisión. |

## Concurrencia y persistencia

- La clave idempotente y el hash protegen el replay.
- La reserva activa continúa protegida por el índice parcial vigente.
- El reclamo de una operación pre-ARCA debe conservar compare-and-swap.
- Ninguna excepción post-ARCA puede ejecutar una transición que libere el
  número.
- SQLite y PostgreSQL deben producir la misma semántica funcional en tests.
- PF-01B agregará constraints de dominio y cruzados después de auditar filas
  legacy; no se mezclará esa migración con PF-01A.

## Contratos ARCA

- `FECAESolicitar`: única operación que autoriza; no inferir éxito sin CAE.
- `FECompConsultar`: mecanismo seguro para reconciliar un número concreto.
- `FECompUltimoAutorizado`: no reemplaza la consulta del comprobante incierto y
  se reserva para el diseño posterior de PF-02.
- Las pruebas usan dobles locales y nunca llaman ARCA real.

## Matriz de tests previa a implementación

### Backend individual

1. Aprobación válida con CAE de 14 dígitos y vencimiento válido.
2. `A` sin CAE, CAE no numérico, longitud incorrecta o vencimiento inválido.
3. `R` explícito sin crear comprobante.
4. `P` tratado como incierto.
5. Error global o detalle incompleto tratado como incierto.
6. Excepción inesperada antes de iniciar ARCA conserva flujo pre-ARCA.
7. Excepción inesperada después de iniciar ARCA responde `409` estructurado.
8. Falla DB posterior a una respuesta válida conserva reconciliación.
9. Replay idéntico no vuelve a invocar `FECAESolicitar`.
10. Misma clave con payload distinto responde conflicto.
11. Reconciliación coincidente crea o vincula una sola vez el comprobante.
12. Consulta inexistente libera únicamente el intento verificado.
13. Consulta fallida o inconsistente mantiene la reserva.
14. Pertenencia multiemisor se revalida en replay y reconciliación.

### Backend batch

1. Todos los detalles aprobados y correctamente asociados.
2. Un detalle `P`.
3. Un detalle `R`.
4. Aprobación sin CAE utilizable.
5. Detalle duplicado para el mismo rango.
6. Detalle faltante.
7. Detalle extra o número no solicitado.
8. Error global de ARCA.
9. Respuesta fuera de orden válida.
10. Rangos o punto/tipo mezclados.

### Frontend

1. El `409` de reconciliación muestra estado dedicado.
2. La misma clave se conserva en `Verificar estado`.
3. Edición, cancelación y cambio de emisor no resetean silenciosamente una
   operación incierta.
4. Doble interacción produce una sola solicitud efectiva.
5. Reconciliación autorizada desbloquea y navega al comprobante.
6. Rechazo verificado permite corregir y generar una operación nueva.
7. Error genérico pre-ARCA no se presenta como reconciliación.

No se omite ningún invariante del corte sin cobertura automatizada. La
persistencia visual tras recargar el navegador puede quedar como prueba de una
segunda iteración solo si el backend demuestra bloqueo durable y se documenta
la limitación antes de implementar.

## Cortes de implementación previstos

1. [x] Validador ARCA común y matriz negativa de `WSFEv1Client`.
2. [x] Clasificación post-ARCA y respuesta idempotente estructurada en API/servicio.
3. [x] UI de reconciliación con clave y payload inmutables.
4. [x] Pruebas integradas individual/batch, publicación, CI, documentación viva
   y revalidación Clawpatch del conjunto.

Cada corte debe ser pequeño y revisable. PF-01B será un trabajo posterior con
auditoría de datos, migración, constraints y sus propias pruebas.

## Validación y cierre

Después de implementar:

- tests enfocados de WSFE, facturación, API e idempotencia;
- tests de la vista de emisión;
- lint, formato, type-check y build de las áreas tocadas;
- suites completas en el checkpoint lógico;
- `autoreview` con `gpt-5.5 high` solo con confirmación explícita del
  usuario;
- revalidación de los findings aceptados con Clawpatch;
- actualización de roadmap, estado, QA, ARCA y manual de usuario cuando cambie
  comportamiento visible.

No se usará `clawpatch fix` para este trabajo fiscal crítico.

## Cierre de implementación de PF-01A.1, PF-01A.2 y PF-01A.3

El 2026-07-13 se implementó el validador común y la matriz negativa de
`WSFEv1Client`, sin llamadas reales a ARCA y sin modificar servicio, API,
persistencia, UI ni migraciones. El backend completo aprobó `498` tests con `2`
omitidos por marcas preexistentes; Ruff y Black quedaron limpios. La revisión
efectiva fue `autoreview` con `gpt-5.5 high`, sin findings accionables y con
confianza `0,86`; `gpt-5.6-sol` no llegó a revisar porque el motor exigió una
versión más nueva del binario local de Codex.

PF-01A.2 conserva un `R` completo como rechazo verificado y transforma las
excepciones inesperadas posteriores al cruce ARCA en una respuesta sanitizada
`requiere_reconciliacion`, individual o batch. La API intenta persistir ese
`409` como replay idempotente y conserva CAE, vencimiento, número y total cuando
ya se conocen. El cierre automatizado aprobó `503` tests backend, con `2`
omitidos, y una regresión enfocada de `189` tests. Dos findings P2 intermedios de
`autoreview` se aceptaron, corrigieron y cubrieron; la revisión final efectiva
con `gpt-5.5 high` quedó limpia, con confianza `0,82`.

PF-01A.1 se publicó como `bd0d817`; GitHub Actions `29221936407` aprobó Frontend
Build, Backend Tests, Security Audit y E2E Tests. PF-01A.2 se publicó como
`ae18856`; GitHub Actions `29226385118` aprobó los mismos cuatro jobs.

PF-01A.3 implementa en la vista individual el estado dedicado de incertidumbre:

- detecta el `409` estructurado antes del error genérico y normaliza solo campos
  allowlist;
- congela en memoria el request y sus ítems junto con la clave idempotente;
- bloquea formulario, cancelación, navegación y doble interacción;
- conserva el estado ante un cambio de emisor y deshabilita la verificación
  hasta recuperar el emisor original;
- `Verificar estado` repite el mismo payload y la misma clave;
- autorización final navega al comprobante; rechazo final HTTP `400` desbloquea;
  `409`, red y fallos no concluyentes mantienen el bloqueo;
- no usa HTML crudo ni almacenamiento web para datos fiscales; advierte ante una
  salida o recarga.

La validación local de PF-01A.3 aprobó `17` tests unitarios enfocados, `127`
unitarios completos, un E2E enfocado y `33` E2E completos, además de ESLint,
type-check y build. `autoreview` con `gpt-5.5 high` detectó un P1 válido porque
el rechazo final real llega como HTTP `400`; se corrigió y cubrió con ese
contrato. La segunda pasada quedó limpia, sin findings accionables y con
confianza `0,80`. `gpt-5.6-sol` se intentó dos veces, pero no llegó a revisar por
la incompatibilidad del binario local. No hubo llamadas reales a ARCA ni se
ejecutó Clawpatch.

PF-01A.3 se publicó como `578a15a`. La primera CI `29244681533` aprobó
backend, frontend y E2E, pero la auditoría de seguridad detectó cinco avisos
nuevos de Pillow `12.2.0`. `82d4245` actualizó la dependencia a `12.3.0` y
`2c8ac72` sincronizó la documentación. El intento 2 de GitHub Actions
`29245900987` aprobó Security Audit, Backend Tests, Frontend Build y E2E
Tests; el intento 1 se canceló porque el runner quedó atascado durante la
descarga de Playwright, no por un fallo del código.

El checkpoint integrado revalidó R02, B03, B04 y B24 secuencialmente como
`fixed` con Clawpatch `0.7.0`, Codex `gpt-5.6-sol` y razonamiento `high`.
Los ledgers terminaron sin locks con 15 findings abiertos en `repo`, 98 en
`backend` y 29 en `frontend`. No se ejecutó `clawpatch fix`, no hubo resultados
inciertos y no se realizaron llamadas reales a ARCA.

PF-01A queda cerrado. PF-01B continúa separado por su auditoría legacy,
migración y constraints; no debe mezclarse con PF-02.
