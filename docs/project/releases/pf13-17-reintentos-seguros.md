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

No hay migraciones nuevas, cambios de Compose ni variables de configuración
nuevas. La imagen de construcción del frontend alinea Node y npm con el
proyecto, según la ampliación autorizada descrita más abajo. Se mantiene el
head Alembic existente. La
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

## Ampliación autorizada: seguridad y cero advertencias

El 30/09/2026 Santi autorizó corregir las dependencias que bloqueaban la CI y
exigió que termine sin warnings antes de integrar o desplegar. La CI previa
aprobó los caminos funcionales y PostgreSQL (1390 pruebas), pero registró 666
advertencias de Python, 158 de Vue y alertas de dependencias. Esa corrida no
habilita el despliegue del candidato ampliado.

PyJWT pasa a 2.15.1 y WeasyPrint a 70.0. Los claims JWT malformados y el JSON
profundamente anidado se rechazan sin error interno. WeasyPrint usa un
`URLFetcher` restringido a datos embebidos y archivos dentro de templates;
las hojas de estilo pasadas como parámetros respetan ese mismo filtro.
Se verifican fecha, importes, CAE sintético, página y presentación del PDF.

La auditoría completa corrige también Axios y dependencias transitivas de
construcción mediante actualizaciones compatibles; Vitest y coverage-v8 pasan
a 4.1.11. `js-beautify` 2.0.3 elimina glob obsoleto mediante un override acotado
a `@vue/test-utils`; no se usa `audit fix --force` ni se excluye tooling.

El adaptador Passlib importaba `crypt` obsoleto en Python 3.11. Se usa la misma
biblioteca bcrypt 3.2.2 directamente, conservando costo 12, prefijos anteriores,
UTF-8, límite de entrada y truncamiento histórico de 72 bytes; pruebas con
hashes sintéticos previos acreditan compatibilidad sin regenerar contraseñas.

Pydantic conserva atributos y aliases mediante `ConfigDict`; FastAPI migra a
lifespan con inicio único del worker y liberación de pools tras su cierre,
incluso ante errores. La relación del emisor en el journal administrativo queda
de lectura: sus IDs y FK compuesta siguen siendo la autoridad de escritura.
Sólo el teardown de SQLite desechable elimina tablas individualmente con FK
suspendidas; las valida reactivadas antes de devolver la conexión.

ESLint bloquea cualquier advertencia; pytest las convierte en errores. La CI
usa PostgreSQL 16 Bookworm con locales y autenticación SCRAM explícita, añade
HarfBuzz-Subset y actualiza la acción de artefactos a v7, sin cambiar el VPS.
Se mantienen los siete checks, cobertura, auditorías y revisión fiscal final
del rango completo. El rollback conserva las imágenes previas con sus
dependencias; no requiere migrar hashes ni restaurar datos.

## Alineación documental y entrega

El preflight detectó Node 20 en el Dockerfile del frontend frente a Node
24.15.0 y npm 11.12.1 exigidos por el proyecto y usados en CI. Santi autorizó
alinear la imagen el 30/09/2026. Se fija Node 24.15.0 Alpine y npm 11.12.1
en la etapa de construcción; Nginx y su configuración se conservan. El contexto
excluye dependencias y salidas locales. La CI construye la imagen real, falla
ante advertencias y comprueba Nginx y los archivos compilados. No se actualizan
Node, npm ni paquetes base del host productivo.

Actualizados changelog, contrato, roadmap, portafolio, handoff, índices, API,
manual de usuario, integración ARCA y recorrido QA. Visión, arquitectura,
procedimientos productivos se revisan sin modificarlos. Testing y seguridad
registran las nuevas puertas sin advertencias y dependencias compatibles.
No hay cambios de producto, permisos ni topología.

La publicación e integración requieren los siete checks obligatorios y la
revisión fiscal canónica `gpt-5.6-sol medium`. El origen y resultado productivos
se registran en el plano de control privado, con despliegue por SHA exacto,
backup/restauración, rollback verificable y smoke sin CAE. Este dossier no
acredita por sí solo una instalación ni fija su versión desplegada.
