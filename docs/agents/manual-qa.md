# QA manual

Última actualización: 2026-08-05

Este documento conserva únicamente el checkpoint vigente y la QA todavía
accionable. El historial técnico está en `CHANGELOG.md` y en las auditorías
fechadas de `docs/project/**`.

## Último checkpoint aceptado

`v0.2.2` quedó validada en producción el 2026-07-23.

- El ciclo verificó previamente backup recuperable y restauración aislada; bajo
  mantenimiento repitió backup final, preflight, Alembic, constraints,
  invariantes, conteos, runtime, worker y logs sanitizados.
- Los smoke autenticados confirmaron acceso, lecturas, certificados, puntos de
  venta, reportes y PDF seguro.
- No se solicitaron CAE ni se realizaron emisiones o reintentos fiscales
  durante el despliegue. La emisión fiscal real ya había sido validada en el
  checkpoint productivo de `v0.2.1`.
- No queda QA bloqueante para mantener `v0.2.2` en producción.
- Los datos fiscales y la evidencia detallada permanecen en el entorno operativo
  privado.

El código aceptado en `main` avanzó después de ese tag: PF-02A, PF-02B.1 y
PF-02B.2 están integrados, pero todavía no pertenecen a una release publicada
ni al despliegue productivo. Sus escenarios se validaron con dobles
controlados, sin CAE reales ni llamadas ARCA de escritura.

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
- cambio de emisor limpia estado, modales y respuestas tardías;
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

## PF-02B — batch y reintentos manuales

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

La recuperación stale del worker conserva una puerta estricta antes de
reencolar: exige grupos intactos, ausencia de intentos y numeración alineada. El
procesamiento normal vuelve a diagnosticar después del reencolado. El contrato
de reintentos manuales quedó cerrado en PF-02B.2. La extensión de la
recuperación stale permanece como PF-02B.3 y no debe inferirse de estos casos.

## Punto de reanudación de QA

PF-01 está publicado y cerrado con CI verde: R02/B03/B04/B24/B10/B17 quedaron
`fixed` en Clawpatch. `v0.2.2` completó sus puertas privadas, quedó publicada y
superó el despliegue y la verificación post-deploy. El próximo foco de QA
acompaña PF-02 y los escenarios manuales controlados todavía enumerados. No
repetir como pendiente el setup productivo inicial, el despliegue `v0.2.2`, el
rediseño UX de lotes ni las validaciones ya cerradas.

Para conocer el estado de desarrollo y el orden exacto, usar
`docs/agents/current-status.md` y `ROADMAP.md`.
