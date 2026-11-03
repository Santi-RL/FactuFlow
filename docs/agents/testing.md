# Guía de testing

Última revisión: 03/11/2026

Estado: VIGENTE.

Esta guía contiene comandos, políticas y entornos reutilizables. Los conteos y
resultados de un corte pertenecen al PR, al changelog o a su dossier, no aquí.

## Puertas por alcance

La clasificación canónica vive en
[`change-quality-gates.md`](change-quality-gates.md):

- **Nivel 0:** Markdown o `.gitignore`; revisión del diff, privacidad,
  `docs:check` y CI liviana.
- **Nivel 1:** funcional no crítico; pruebas enfocadas y suite del área.
- **Nivel 2:** fiscal o sensible; diseño, errores, concurrencia, checklist, CI
  completa, revisión y QA proporcional.

Una duda usa el nivel superior hasta justificar lo contrario.

## Comandos desde la raíz

```bash
npm run lint
npm run test
npm run backend:format:check
npm run docs:check
```

La puerta local completa, cuando corresponde, es:

```powershell
./scripts/ci-local.ps1
```

El log se guarda en una ruta ignorada. Los comandos con `--fix` o `--write`
modifican archivos y no se usan como verificaciones pasivas.

La CI debe finalizar sin advertencias: ESLint aplica `--max-warnings 0` y
pytest convierte warnings en errores mediante `filterwarnings = error`.
Corregir la causa; no desactivar reglas ni añadir filtros para ocultarla.
El presupuesto del trabajo backend incluye la instalación y la suite completa;
su límite se define en el workflow. Conservar los casos, los umbrales y los
parámetros de seguridad al ajustar ese presupuesto.
La auditoría de npm abarca dependencias productivas y de desarrollo.
La auditoría Python usa `pip-audit -r requirements-dev.txt`, que también incluye
las dependencias productivas. Las herramientas de pruebas y formato conservan
versiones explícitas; no resolver alertas debilitando esta auditoría.
Los runners de CI usan Ubuntu 24.04 explícito. Cambiar su versión requiere
comprobar instalación, PDF, build, PostgreSQL y smoke; no depender del cambio
automático de `ubuntu-latest`.
Los cuatro grupos backend y su agregación fijan la misma versión completa de
Python, incluido el parche. Una referencia como `3.11` puede resolver parches
distintos según la caché del runner y no garantiza entornos comparables.
Los runners Linux instalan HarfBuzz-Subset para generar PDFs; en Windows,
usar un runtime compatible de WeasyPrint y sus bibliotecas nativas mediante
`WEASYPRINT_DLL_DIRECTORIES` y `PATH`, sin mezclar versiones de GTK/Pango.

## Backend

Desde `backend/`:

```bash
pytest
ruff check app/ tests/
black --check app/ tests/
```

Usar selecciones enfocadas antes de la suite completa:

```bash
pytest tests/ruta_relevante.py -q
pytest tests/ruta_relevante.py -k caso_relevante -q
```

Las pruebas deben usar fechas explícitas y datos sintéticos. Ninguna suite
normal llama a ARCA real ni solicita CAE.
Al sembrar una comprobación técnica con fecha fija, controlar también el reloj
que mide su antigüedad. Los ensayos específicos de vencimiento conservan sus
relojes y límites; no cambiar ventanas productivas para estabilizar las suites.
`pytest-asyncio` gestiona un único ciclo de eventos de sesión, tanto para pruebas
como para fixtures, mediante `pytest.ini`; conserva el alcance anterior sin
redefinir la fixture retirada `event_loop`. El aislamiento de datos sigue siendo
por prueba y el teardown restaura las claves foráneas de SQLite.

Los hashes de las contraseñas sintéticas de usuario y administrador se calculan
una vez por sesión con la función real y bcrypt de costo 12. Sólo se reutilizan
cadenas inmutables: usuarios, permisos, sesiones y tokens conservan aislamiento
por prueba, y los headers autenticados siguen obteniéndose mediante el login
real. Las pruebas específicas de generación, verificación y recuperación de
credenciales conservan sus operaciones criptográficas.

Las comparaciones locales puras de intento, comprobante y request usan objetos
transitorios y una sesión que rechaza cualquier acceso a base. Esto no cambia
los fixtures ni los recorridos que prueban persistencia, migraciones o
concurrencia.

### Evidencia de una ejecución completa

Para obtener una referencia secuencial completa se conserva el recolector
versionado:

```bash
python ../tools/ci/backend_report.py run --output-dir /ruta/nueva/reporte --source-sha SHA_COMPLETO
```

Ejecutar desde `backend/` con PostgreSQL desechable configurado como en CI.
El directorio de salida debe ser nuevo y quedar fuera de los archivos
versionados. El comando conserva la selección completa, los warnings como
errores y el umbral del 69%; registra inventario, resultados y duración de las
tres fases de cada caso, JUnit, entorno y cobertura nativa, XML y JSON. Un caso
omitido, con fallo esperado, duplicado o incompleto impide aprobar la evidencia.
El artefacto `backend-coverage` conserva esos archivos durante 14 días.

Para contrastar una simplificación sin cambios de aplicación ni migraciones:

```bash
python ../tools/ci/backend_report.py compare /ruta/referencia /ruta/candidata
python -m unittest discover -s ../tools/ci -p test_backend_report.py -v
```

La comparación exige los mismos casos aprobados y entornos, y rechaza la pérdida
de cualquier línea o rama previamente cubierta. No se limita a comparar el
porcentaje global. El contraste es una validación puntual de la optimización;
no fija un inventario que impida agregar pruebas nuevas. Los resultados
concretos pertenecen al PR o a una ruta de evidencia ignorada.

### Cuatro grupos independientes en CI

El workflow distribuye archivos completos entre cuatro runners, cada uno con
PostgreSQL y temporales propios. Dentro de cada grupo pytest sigue siendo
secuencial, incluidos los escenarios que prueban concurrencia. No se usa
paralelismo entre casos que comparta una base.

`tools/ci/backend-file-durations.json` conserva los pesos y la identidad de la
referencia completa. Cada peso suma las fases de preparación, ejecución y
limpieza del archivo. El reparto ordena por duración descendente y ruta, y
asigna al grupo menos cargado, desempatando por número. Un archivo nuevo entra
automáticamente con un segundo de peso inicial; el inventario se descubre de
nuevo en cada ejecución.

Desde `backend/`, los comandos usados por CI son:

```bash
python ../tools/ci/backend_shards.py run --group 1 --output-dir /ruta/nueva/grupos/grupo-1 --source-sha SHA_COMPLETO --run-id EJECUCION_INTENTO
python ../tools/ci/backend_shards.py aggregate --inputs /ruta/grupos --output-dir /ruta/nueva/combinado --source-sha SHA_COMPLETO --run-id EJECUCION_INTENTO
python -m unittest discover -s ../tools/ci -p 'test_backend*.py' -v
```

Repetir `run` con los números del 1 al 4 en entornos aislados. Cada salida
incluye selección, inventario completo, resultados, JUnit, tiempos, SHA,
ejecución e intento, versiones, huellas de los recolectores y cobertura nativa,
XML y JSON. Los artefactos `backend-group-*` duran 14 días.

`Backend Tests` se ejecuta después de los grupos incluso si fallan, se cancelan
o faltan. Exige su éxito y vuelve a descubrir la suite sin ejecutar fixtures;
rechaza casos faltantes, duplicados, omitidos o con fallo esperado, archivos
repartidos entre grupos e informes de otro código, ejecución o versión. También
comprueba la integridad y presencia de los artefactos. Ruff, Black y los
contratos de evidencia se ejecutan una vez, en esta comprobación final.

Los parciales miden cobertura sin aplicarles el umbral global. La comprobación
final usa `coverage combine --keep` sobre los cuatro archivos nativos y exige
el 69 % sobre la unión de líneas y ramas, nunca sobre un promedio. La
configuración compartida `backend/.coveragerc` guarda rutas relativas para
combinar runners distintos y declara `thread,greenlet`, porque la extensión
asíncrona de SQLAlchemy usa cambios de contexto greenlet. Sin esa declaración,
coverage puede atribuir líneas a otro contexto y producir resultados incorrectos,
como advierte su [documentación](https://coverage.readthedocs.io/en/latest/config.html#run-concurrency).
El recolector registra la huella de esa configuración y la comparación exige
que coincida; los reportes nativos con arcos fuera de los fuentes Python se
rechazan. Las plantillas compiladas de Jinja usan otra numeración y conservan
sus datos nativos. La referencia secuencial y los grupos usan la misma
instrumentación.
`pytest.ini` y los comandos secuenciales conservan su umbral habitual.
El artefacto `backend-coverage` contiene el resultado completo y permite usar
la comparación detallada descrita arriba.

E2E depende únicamente de `Change Scope` y corre en paralelo con backend y
frontend. Se conservan los siete checks obligatorios y la excepción de Nivel 0
para cambios exclusivamente documentales.

### Codificación de subprocesos en Windows

En Windows, ejecutar Python y sus subprocesos con UTF-8 para que las capturas de
mensajes de migración con tildes conserven la misma codificación. En PowerShell,
configurar estas variables en la sesión que ejecuta la suite:

```powershell
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
```

No cambiar las aserciones ni suprimir warnings para compensar una codificación
distinta entre el proceso de pruebas y sus subprocesos.

### PostgreSQL desechable

Las pruebas de migraciones, constraints o concurrencia deben usar el harness
versionado y una base descartable. Las barreras mínimas son:

- driver `postgresql` o `postgresql+asyncpg`;
- host loopback exacto;
- base exacta `factuflow_integration_test`;
- opt-in explícito `FACTUFLOW_TEST_POSTGRES_ALLOW_SCHEMA_RESET=1`;
- revalidación antes de cada operación destructiva;
- eliminación del entorno al finalizar.

Nunca apuntar el harness a producción, una base compartida o un nombre que sólo
“parezca” de prueba.

### Reutilización de Docker local

Mantener un único proyecto Compose de preview por copia local: actualizar o
reconstruir sus servicios para probar otro corte, sin acumular un proyecto por
ensayo. No confundir los servicios frontend/backend del mismo proyecto con
copias redundantes de la aplicación. Detenerlos cuando no se use la vista local.

Las pruebas PostgreSQL reutilizan un contenedor desechable durante la tanda,
con las barreras del harness; no crear uno por caso de prueba. Retirarlo al
terminar con `--rm` o limpieza explícita limitada a ese contenedor. Conservar
datos persistentes o carpetas bind salvo autorización específica para borrarlos;
eliminar un contenedor no implica eliminar esos datos. No usar una limpieza
global de Docker como cierre automático de las pruebas.

## Frontend

El contrato de navegadores y estilos vive en
[`frontend/README.md`](../../frontend/README.md#navegadores-compatibles).
Una migración mayor de estilos debe comprobar componentes, modales, foco y
colores forzados además de compilar. Los motores E2E actuales no prueban todas
las versiones mínimas declaradas.

La CI también construye `frontend/Dockerfile` con Node 24.15.0 y npm 11.12.1,
bloquea warnings del build y comprueba la configuración Nginx y los archivos
compilados. `frontend/.dockerignore` evita copiar dependencias y salidas locales
sobre las instaladas dentro de la imagen.
El control usa Node, disponible por `setup-node`, y falla si el log no se puede
leer. Los tests de scripts verifican logs limpios, advertencias y lectura fallida.

Los servicios PostgreSQL de CI y las bases Node/Nginx de su build usan las
imágenes oficiales de `docker.io/library`, conservando las etiquetas definidas
en el workflow y el Dockerfile. Los runners alojados por GitHub están exentos
del límite de descargas públicas de Docker Hub; no se agregan credenciales.
El Dockerfile conserva Docker Hub como origen predeterminado fuera de CI;
`IMAGE_REGISTRY` cambia únicamente el registro de sus bases. Al cambiar ese
origen, contrastar los digests de las etiquetas con las imágenes oficiales y
comprobar PostgreSQL, build, Nginx y smoke. La disponibilidad de un registro
externo no está garantizada; sus fallos deben mantenerse visibles.

Fuente: [límites documentados de los runners GitHub](https://docs.github.com/en/actions/reference/limits#docker-hubs-rate-limit-for-github-actions).

Desde `frontend/`:

```bash
npm run test:unit
npm run test:coverage
npm run test:coverage:gate
npm run lint:check
npm run type-check
npm run build
```

`npm run lint:fix` y `npm run format` son comandos de modificación; revisar el
diff después de usarlos.

`npm run test:coverage` comprueba primero la puerta con fixtures sintéticas y
la CLI real de Vitest, y después ejecuta la suite con cobertura. El control
reutiliza los umbrales de `vite.config.ts`: statements 56%, branches 50%,
functions 43% y lines 57%, directamente bajo `coverage.thresholds`, con
`autoUpdate: false`. Una cobertura insuficiente debe terminar con error; una
cobertura suficiente debe pasar sin reescribir la configuración. El comando
`test:coverage:gate` permite ensayar ese contrato de forma enfocada. Las fixtures
y sus reportes se crean en `frontend/.tmp/` y se eliminan al finalizar.

Las pruebas de stores y vistas con emisor activo deben cubrir respuestas tardías,
cambio de emisor, permisos y estados de carga cuando el contrato afectado lo
requiera.

## E2E

Desde `frontend/`:

```bash
npm run test:e2e
```

Desde la raíz, el comando equivalente es
`npm --prefix frontend run test:e2e`. El runner levanta su propio servidor Vite
local y lo cierra al terminar; no requiere una instalación operativa.

- Usar dobles y datos sintéticos.
- No reutilizar sesiones o credenciales productivas.
- No confirmar emisiones reales.
- Las capturas y reportes locales quedan en rutas ignoradas.
- Un cambio de UI sensible debe probar el camino feliz y la recuperación del
  error relevante.

## Fechas fiscales

Toda prueba nueva o modificada debe elegir fechas explícitas:

- UI y textos argentinos: `DD/MM/AAAA`;
- API y persistencia: contrato ISO aplicable;
- WSFE `CbteFch`: `YYYYMMDD`.

No usar la fecha actual como valor predeterminado ni generar expectativas que
dependan del día de ejecución.

## ARCA, idempotencia y estados inciertos

Los cambios capaces de llegar a WSAA/WSFE, numeración o CAE deben cubrir, según
el riesgo:

- éxito, rechazo y timeout;
- respuesta incompleta o contradictoria;
- concurrencia y replays idempotentes;
- segundo preflight y compare-and-swap;
- reconciliación cuando ARCA pudo autorizar;
- cero estado fiscal nuevo cuando el flujo debe abortar antes de ARCA.

Aplicar antes el
[`checklist fiscal`](fiscal-change-checklist.md). Las llamadas reales se reservan
a una autorización expresa y al runbook correspondiente.

## Evidencia

Cada PR registra comandos, escenarios y resultados de su propio rango. Una
release conserva la evidencia durable en su dossier. Esta guía no se actualiza
por nuevos conteos si los comandos y la política no cambiaron.

La evidencia histórica retirada de esta guía se conserva íntegra en
[`testing-through-v0.3.2.md`](../project/history/testing-through-v0.3.2.md).

## Antes de cerrar una unidad

1. Ejecutar primero pruebas enfocadas y luego la puerta proporcional.
2. Verificar que no hubo llamadas reales ni datos privados.
3. Revisar documentación contractual y QA aplicables.
4. Ejecutar `git diff --check` y revisar el rango completo.
5. Registrar riesgos residuales y recuperación en el PR.
6. Esperar los checks obligatorios antes de integrar.
