# PF-13/PF-17 — emisión parcial y reintentos seguros

## Diseño fiscal previo (30/09/2026)

Nivel 2. El corte corrige reservas residuales y habilita reintentos durables por
bloques sobre la selección confirmada del mismo lote. No modifica importes,
receptores, fechas, puntos de venta, certificados ni la confirmación irreversible.

Consumidores: API de procesamiento/reintento y replay, servicio de lotes, worker
embebido, recuperación stale/pre-CAE, facturación individual y por bloques,
control de duplicados, seguimiento y pantalla de lotes. WSAA comparte la
preparación con consultas y certificados: su caché mantiene emisor, ambiente,
servicio y huella del certificado. Ninguna prueba llama a ARCA real.

Orden del reintento: autenticar y delimitar emisor; resolver payload e idempotencia;
devolver replay antes de validaciones mutables; validar confirmación exacta y
duplicados; bloquear puntos, operaciones, intentos, guardas y lote; acreditar que
el propietario anterior es terminal, sin guardas ni intentos activos/inciertos;
comparar material fiscal y selección; pasar solamente los fallidos seleccionados
a pendientes y publicar cola y respuesta durable en una transacción. El worker
reutiliza el camino masivo, con preflights, intentos y guardas durables antes de
FECAESolicitar. Conservar compatibilidad de la API síncrona existente; la UI usa
el contrato background y su seguimiento no depende del proxy.

Estados: cola → procesando → terminal o requiere_reconciliacion. La operación
permanece en_proceso con respuesta background verificable hasta publicar su
resultado. Doble clic, replay y carrera no crean otro envío. Un fallo previo al
CAE deja pendientes seguros; un fallo tras la frontera durable queda incierto,
sin liberar numeración ni reintentar. La caída del worker conserva las guardas y
usa la recuperación vigente, ampliada al reintento. Los trabajos ya aceptados
conservan su autorización durable cuando se revoca un acceso; las nuevas acciones
exigen el acceso actual, igual que la emisión background vigente.

Reservas: liberar únicamente las del propietario terminal acreditado, con
comparación de propietario bajo coordinación del emisor/ambiente. La antigüedad
no acredita cierre; cualquier guarda o intento activo/incierto impide liberar.
No borrar intentos, evidencias ni respuestas. La nueva admisión vuelve a evaluar
duplicados; esta recuperación no sustituye la aceptación de coincidencias.

Progreso: guardar selección y contadores de la operación actual; consultar una
proyección allowlist desde seguimiento. Emitidos anteriores y fallidos ajenos a
la selección no cuentan en el porcentaje. Reiniciar tiempos de operación, no
fecha fiscal. Mostrar seleccionados, autorizados, fallidos, pendientes e inciertos.

Matriz: preparación WSAA con ticket cacheado sin acceso WSDL; fallo de conexión
pre-CAE; terminal con reservas residuales; propietario ajeno/activo/incierto;
selección parcial y mayor a un bloque; replay/doble clic/concurrencia; caída antes
y después de CAE; permisos/emisor/material modificado; respuesta y progreso tras
recarga; errores de conexión sin indicación de cambiar fecha/numeración; comparar
tiempos e inicializaciones en carga sintética normal y reintento. Ejecutar SQLite,
PostgreSQL desechable, controles del área, CI completa y autoreview fiscal final.

## Compatibilidad y recuperación

No hay migraciones nuevas, dependencias, lockfiles, cambios Docker/compose ni
variables de configuración nuevas. Se mantiene el head Alembic existente. La
API sin `background=true` conserva el reintento síncrono; los recibos terminales
previos y sus respuestas se conservan. El código nuevo reconoce recibos durables
de emisión y reintento background en las guardas de ownership y recuperación.

Antes de desplegar, comparar el rango desde el origen productivo observado;
conservar imágenes de ese origen y un backup recuperable reciente, con prueba
de restauración en destino desechable. El rollback vuelve al código anterior
sólo cuando no quedan reintentos background aceptados activos. Drenar los
trabajos seguros y conservar o reconciliar incertidumbre; el código anterior
no debe reclamar recibos de la nueva modalidad. No restaurar automáticamente
la base ni borrar historia fiscal para volver atrás. El parche no repara
incertidumbres históricas mediante SQL ni emite comprobantes de smoke.

## Validación sintética reproducible

- `pytest tests/test_reintentos_background.py -q -s -o addopts=`: diez casos
  aprobados; selección parcial y total, conflicto previo con replay, timeout
  posterior al envío y reservas de propietario terminal/activo/incierto y aislamiento del cliente WSFE.
- `pytest tests/test_facturacion_service.py tests/test_reintentos_background.py`:
  91 casos aprobados, con identidad completa de certificados simulados y
  distinción de errores internos sanitizados frente a fallos de conexión.
- Las regresiones de lotes, duplicados y ARCA cubren autorización durable,
  ownership, permisos, material fiscal, rechazos, recuperación y aislamiento.
- `npm --prefix frontend run test:unit -- --run`: 225 pruebas aprobadas. La vista
  recupera tres pendientes y cero autorizados de la operación actual aunque
  existan 97 autorizados anteriores, sin un POST de reintento al recargar.
- Lint y tipos, build frontend, alineación documental y 28 pruebas de scripts
  aprobados. El benchmark no usa red real ni datos privados.

Carga agrupable sintética, límite dos por bloque, latencia simulada 5 ms por
consulta/envío, mismos preflights y configuración:

| Camino | Seleccionados | Bloques CAE | Clientes WSFE | Duración observada |
|---|---:|---:|---:|---:|
| Reintento parcial | 3 | 2 | 1 | 0,564 s |
| Reintento completo | 4 | 2 | 1 | 0,591 s |
| Emisión normal | 4 | 2 | 1 | 0,557 s |

La comparación demuestra envío por bloques y una preparación por operación;
no promete tiempos absolutos frente a ARCA. El ticket WSAA cacheado se prueba
sin inicialización WSDL; la separación de caché por certificado permanece.

La prueba `test_reintentos_reservas_postgresql.py` usa el harness de PostgreSQL
desechable: recuperación terminal y reserva de nuevo propietario comparten
coordinación, y la segunda sesión espera el commit. La matriz remota completa
incluye esa prueba, capacidad 4+1, migraciones, cobertura, runtime smoke, E2E y
seguridad. La evidencia de CI y revisión fiscal final se vincula en el PR; no
se reemplaza por el resultado local de SQLite.

QA de progreso y fallos se ejecuta con backend simulado y servicios ARCA falsos;
ninguna prueba solicita CAE real. La aceptación fiscal conserva fecha/PV,
selección confirmada, numeración, idempotencia y reconciliación. Permanece como
riesgo externo la indisponibilidad de ARCA: se informa su fase y se conserva
el resultado incierto cuando corresponda.

## Alineación documental y entrega

Actualizados changelog, contrato, roadmap, portafolio, handoff, índices, API,
manual de usuario, integración ARCA y recorrido QA. Visión, arquitectura,
políticas de prueba y procedimientos productivos se revisan sin modificarlos:
no hay cambios de producto, stack, comandos, permisos ni topología.

La publicación e integración requieren los siete checks obligatorios y la
revisión fiscal canónica `gpt-5.6-sol medium`. El origen y resultado productivos
se registran en el plano de control privado, con despliegue por SHA exacto,
backup/restauración, rollback verificable y smoke sin CAE. Este dossier no
acredita por sí solo una instalación ni fija su versión desplegada.
