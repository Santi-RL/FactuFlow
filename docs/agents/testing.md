# Guía de testing

## Raíz

```bash
npm run lint
npm run test
npm run backend:format:check
```

Los scripts raíz `lint` y `test` agregan backend y frontend. El check de
formato backend queda explícito como `backend:format:check`. El comando
frontend `npm run format` escribe cambios y no se usa como verificación global
raíz mientras exista deuda histórica de Prettier en archivos no tocados.

## Puertas de CI por alcance

La política canónica está en `docs/agents/change-quality-gates.md`. GitHub
clasifica el diff antes de instalar dependencias:

- si solo cambian archivos Markdown o `.gitignore`, ejecuta el recorrido
  documental de Nivel 0: `Repository Checks` valida la alineación estructural y
  los demás jobs informan éxito sin suites de runtime;
- si cambia cualquier otro archivo, ejecuta controles de repositorio, Ruff,
  Black, backend completo, type-check, lint, build, unit tests, E2E Chromium y
  auditorías bloqueantes de dependencias productivas;
- un conjunto vacío o una clasificación dudosa activa la matriz completa como
  medida conservadora.

`npm run docs:check` se ejecuta en todos los niveles y comprueba versiones
publicada/productiva, presencia de `CHANGELOG.md > Unreleased` y marcadores
transitorios inequívocos en documentación viva. Es una protección mecánica; no
reemplaza la puerta semántica definida en
`docs/agents/change-quality-gates.md` ni la matriz documental del PR.

Al cerrar localmente una unidad funcional o sensible, ejecutar:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/ci-local.ps1
```

El script continúa después de cada fallo para entregar un diagnóstico completo,
pero devuelve código distinto de cero si falla alguna puerta. El log queda en
`.tmp/ci-local.log` y no se versiona.

## Backend

```bash
cd backend
python -m pip install -r requirements.txt -r requirements-dev.txt
pytest tests/ -q
ruff check app/ tests/
black --check app/ tests/
```

### Integración con PostgreSQL desechable

El marker `integration` está registrado en `backend/pytest.ini`. Las pruebas
que requieren infraestructura real deben llevar ese marker y omitir su
ejecución cuando no exista una configuración explícita.

Las pruebas requieren la variable de proceso `FACTUFLOW_TEST_POSTGRES_URL`, que
debe apuntar a una instancia PostgreSQL desechable. La URL y sus credenciales
son privadas: no deben escribirse en comandos versionados, documentación
pública, logs ni Git. Una vez configurada de forma segura, ejecutar:

```bash
cd backend
pytest -m integration tests/integration -q
```

El guard central vive en `backend/tests/postgresql_harness.py` y se revalida en
cada punto destructivo. Solo admite un driver `postgresql` o
`postgresql+asyncpg`, host loopback exacto `localhost`, `127.0.0.1` o `::1`,
base exacta `factuflow_integration_test`, sin query ni options, y el opt-in
destructivo exacto `FACTUFLOW_TEST_POSTGRES_ALLOW_SCHEMA_RESET=1`. Si falta una
condición, falla antes de tocar el schema. Nunca apuntar esta URL a una
instalación operativa.

La matriz cubre capacidad `4+1`, integridad PF-01, inventario PF-19A de solo
lectura, migración y concurrencia PF-19B —incluidos ambos ganadores de la carrera
entre cambio de CUIT y atestación—, y paquete VPS v2. GitHub Actions
provisiona PostgreSQL 16 Alpine con credenciales sintéticas exclusivas del job y
ejecuta el backend completo con esos guardarraíles. Una corrida local sin URL
explícita omite esas pruebas: ese skip no constituye evidencia PostgreSQL. En
este corte no se afirma una ejecución PostgreSQL local; la evidencia real debe
provenir del job de CI. Ninguna prueba solicita CAE ni usa certificados reales.

El corte `4+1` fue aprobado el 10/07/2026 y PF-01B.3 el 13/07/2026 contra
PostgreSQL efímero. Esa evidencia valida contratos locales, pero no demuestra ni
declara un despliegue.

Los archivos Python deben mantenerse con saltos de línea LF. El repo fija esta
política en `.gitattributes` para `*.py` y `*.pyi`, evitando que `core.autocrlf`
de Windows deje el working tree en CRLF o mixto. Para verificarlo:

```bash
git ls-files --eol '*.py' '*.pyi'
```

Si `black --check app tests` se cuelga localmente sin reportar errores, revisar
primero el cache local de Black. En Windows se confirmó que limpiar
`%LOCALAPPDATA%\black\black\Cache\23.12.1` resuelve el cuelgue; luego Black
regenera el cache y debe terminar normalmente.

## Frontend

```bash
cd frontend
npm install
npm run lint:check
npm run type-check
npm run build
npm run test:unit
npm run test:e2e
```

## Pruebas de fechas

FactuFlow es una aplicación argentina. Todo cambio que formatee, parsee,
importe, exporte, valide o muestre fechas debe cubrir explícitamente el formato
argentino `DD/MM/AAAA` además de los formatos técnicos que use el contrato
interno (`YYYY-MM-DD`, ISO datetime o `CbteFch` `YYYYMMDD`).

Cobertura mínima esperada cuando se toca lógica de fechas:

- `DD/MM/AAAA` válido, por ejemplo `31/12/2026`.
- `YYYY-MM-DD` válido recibido desde API/backend, por ejemplo `2026-12-31`.
- ISO datetime con zona horaria si el código lo acepta, verificando que no haya
  desplazamiento de día por timezone.
- Fechas con forma válida pero calendario inválido, por ejemplo `31/02/2026` o
  `2026-02-31`, sin normalizarlas silenciosamente.
- String vacío o valor faltante.
- Para flujos fiscales, confirmación irreversible visible en `DD/MM/AAAA` y
  conversión técnica correcta antes de ARCA.

No usar `new Date(string)` ni `Date.parse` como parser general de strings de
usuario. Validar por formato soportado y por calendario real.

## Puesta a punto Clawpatch

Para ejecutar `clawpatch`, usar los scripts raíz documentados en
`docs/project/audits/clawpatch/README.md`. El smoke mínimo es:

```bash
npm run clawpatch:test-seeds
npm run clawpatch:map-all
npm run clawpatch:repo:status
npm run clawpatch:backend:status
npm run clawpatch:frontend:status
```

No ejecutar comandos directos de slice sin `--root`. `--state-dir` define dónde
se guarda el estado, no qué árbol de archivos se audita. Para backend, usar
`npm run clawpatch:backend:*` o el equivalente directo con
`--root backend --state-dir ../.clawpatch/backend --config
../.clawpatch/backend/config.json`.

`clawpatch:map-all` ejecuta el mapper nativo de cada slice y luego agrega
features manuales versionadas para que la auditoría revise flujos reales de
FactuFlow. El nivel `repo` cubre slices end-to-end frontend/backend;
`backend` y `frontend` agregan slices focalizados por área.

La regresión mínima posterior es:

```bash
cd backend
python -m pytest tests/test_lotes_comprobantes.py tests/test_facturacion_service.py tests/test_comprobantes_api.py -q
ruff check app tests
black --check app tests

cd ../frontend
npm run lint:check
npm run type-check
npm run build
npm run test:unit
```

La puesta a punto no debe ejecutar `clawpatch fix`, no debe solicitar CAE ni
modificar lógica de emisión fiscal.

Nota 2026-07-05:

- Usar siempre la CLI global `clawpatch` sin fijar versión. En FactuFlow no se
  deben escribir scripts que llamen `clawpatch@<version>`.
- Si `clawpatch revalidate --finding <id> --include-dirty` no selecciona un
  finding que `show` todavía lista, revisar si es un duplicado de otro nivel de
  feature. Se puede usar una revalidación acotada por abiertos y hacer triage
  manual solo si el duplicado exacto ya fue revalidado como fixed, dejando nota.
- Después de aceptar un finding de `autoreview` y cambiar código, repetir los
  tests enfocados y volver a correr `autoreview` sobre el commit final con la
  misma configuración canónica `gpt-5.6-sol medium`.
- Para verificar CI remoto, usar `gh run list` y `gh run view` sobre el SHA del
  commit esperado; no usar el endpoint legacy de commit statuses.

Nota 2026-06-10:

- `npm run test:unit` incluye pruebas unitarias de perfiles de carga masiva y
  fechas relativas.
- `npm run test:e2e` es evidencia vigente para Chromium desktop local. El script
  levanta Vite en `127.0.0.1:18080`, ejecuta Playwright y corta el servidor al
  finalizar para evitar procesos colgados en Windows. Si el puerto está ocupado,
  detener el proceso existente o usar `E2E_PORT`.
- La matriz completa de navegadores/mobile queda opt-in con la variable
  `E2E_FULL_BROWSER_MATRIX=1`; no es el recorrido por defecto porque los flujos
  administrativos de plantillas y emisión masiva están pensados para PC. En
  PowerShell usar `$env:E2E_FULL_BROWSER_MATRIX='1'; npm run test:e2e`; en bash
  usar `E2E_FULL_BROWSER_MATRIX=1 npm run test:e2e`.
- `npm run lint` y `npm run lint:check` son checks no destructivos de ESLint.
- En Windows, ejecutar `npm run lint:check` separado de `npm run build` o de
  procesos Vite activos. Si se corre en paralelo, ESLint puede intentar leer un
  archivo temporal `vite.config.ts.timestamp-*.mjs` que Vite ya eliminó y dar un
  falso `ENOENT`.
- `npm run lint:fix` ejecuta ESLint con `--fix`; usarlo solo cuando se quiere
  autocorregir y revisar el diff posterior.

## Arranque local

La forma recomendada para QA manual local en Windows es:

```bash
.\FactuFlow Local.vbs
```

El launcher muestra estado en el tray sin dejar una ventana de PowerShell
abierta y deja logs en `.tmp/local-launcher/`.

El camino técnico alternativo es:

```bash
powershell -ExecutionPolicy Bypass -File .\run-local.ps1
```

Servicios esperados:
- Frontend: `http://localhost:8080`
- Backend: `http://localhost:8000`

`run-local.ps1` ejecuta `alembic upgrade head` antes de iniciar el backend. En
entornos normales no se crean tablas con `Base.metadata.create_all`; esa ruta
queda limitada a tests.

## Checklist antes de cerrar una tarea importante

- Si se toco backend: `pytest`
- Si se toco frontend: `npm run type-check`
- Si se tocaron perfiles de carga masiva: ejecutar
  `pytest tests/test_perfiles_carga_masiva.py` y
  `npm run test:unit -- perfiles-carga-masiva`
- Si se toco un flujo visible: smoke manual o Playwright
- Completar la matriz documental por impacto de
  `docs/agents/change-quality-gates.md`, incluidos `CHANGELOG.md > Unreleased`,
  estado, roadmap, QA, manual, diseño y documentos de dominio aplicables.
- Ejecutar `npm run docs:check`; después releer semánticamente las secciones
  afectadas y distinguir `main`, release publicada y producción.

## QA manual actual

El último checkpoint manual no está en este archivo sino en:

- `docs/agents/manual-qa.md`

Eso evita mezclar instrucciones permanentes con el estado puntual de una sesión.

## Evidencia de verificación

### PF-19B — cierre local del 09/08/2026

- Backend completo: `924` pruebas recolectadas; `905` aprobadas, `19` omitidas
  y `30` warnings en `403.90 s`. Los `19` skips corresponden a suites
  PostgreSQL/harness opt-in sin daemon ni `FACTUFLOW_TEST_POSTGRES_URL` local;
  esta corrida no constituye evidencia PostgreSQL real.
- Frontend completo: `30` archivos y `149` pruebas unitarias aprobadas en
  `12.65 s`; type-check y build aprobados, con `869` módulos transformados.
  `lint:check` terminó con código `0`, cero errores y las `13` advertencias
  históricas limitadas a `ComprobanteNuevoView.vue`.
- La puerta documental aprobó `npm run docs:check` y las `16` pruebas de
  `npm run test:scripts`.
- PF-19B cubre configuración estricta, modelo/ledger, migración y backup,
  atestación administrativa, snapshots, emisión individual, lotes, perfiles,
  selectores y migración VPS v2 mediante SQLite y dobles controlados. CI y la
  matriz PostgreSQL real todavía no se ejecutaron para este diff; tampoco se
  declara release ni despliegue.
- La matriz PostgreSQL cubre ambos ganadores de CUIT/atestación y de la
  degradación `activo=false` o `es_admin=false` frente a atestación. Sus casos se
  recolectaron dentro de la full, pero integran los `19` skips opt-in: solo CI
  con PostgreSQL real puede acreditarlos y todavía no se ejecutó. La
  revalidación frontend P1 enfocada `33/33`, incorporada luego a la full, cubre
  limpieza pre-`await`, empresa + generación en los tres loaders de Lotes,
  corte de la cadena obsoleta después de cada espera y la guarda agregada de
  EmpresaConfig.
- La reauditoría final no encontró hallazgos P0-P2. No equivale a `autoreview`,
  ni reemplaza esa puerta.
- El comando canónico de cierre
  `--mode local --engine codex --model gpt-5.6-sol --thinking medium` se intentó
  dos veces. Ambas corridas quedaron bloqueadas por TruffleHog antes de invocar
  el motor: el bundle reprodujo tres candidatos PostgreSQL sintéticos
  preexistentes en `HEAD`, reintroducidos por commits inversos del helper. El
  árbol objetivo contiene cero URLs de esos candidatos y las pruebas enfocadas
  del caso aprobaron `3/3`; un escaneo local sin verificación confirmó que no se
  trata de una credencial real. El usuario autorizó explícitamente la dispensa
  de `autoreview` el 09/08/2026. Esta dispensa permite continuar el cierre, pero
  no constituye ni debe presentarse como un `autoreview` limpio.

### Checkpoint anterior — 08/08/2026

- PF-19A: `15` pruebas de contención cubren configuración estricta, aislamiento
  por ambiente/emisor/punto/tipo, renumeración/recreación, selección
  determinística de reglas cruzadas, emisión individual, batch, intento stale y
  preflight stale. Los núcleos directos individual y batch demuestran cero
  WSAA/WSFE. El flujo completo `procesar_lote` demuestra una autenticación WSAA
  y una lectura segura `FECompTotXRequest` previas, pero cero `FECAESolicitar`,
  CAE, intentos y comprobantes. El replay HTTP conserva el aborto durable sin
  reabrir la emisión.
- Inventario PF-19A: `18` pruebas del inventario, incluidas `7` sobre SQLite,
  cubren firma global exacta frente a falsos positivos, deduplicación,
  contradicción con CAE de grupo, cadena lote/grupo/comprobante entre emisores y
  validación de la FK directa por emisor, punto, tipo y número planificado. Los
  casos incluyen referencia huérfana, número incorrecto, número ausente y vínculo
  válido; verifican salida privada sanitizada, diagnóstico CLI sin traceback,
  emisor obligatorio, aceptación exacta de `500`, aborto en `501` sin truncado,
  ambiente histórico indeterminado, `query_only`, DML rechazado, rollback y
  restauración del valor previo. El test PostgreSQL desechable quedó agregado y
  se omitió por falta de infraestructura explícita; no se conectó ninguna base
  real.
- Backend completo: `607` pruebas aprobadas y `5` omitidas por infraestructura
  opcional. Ruff y Black aprobaron los `120` archivos de `app/` y `tests/`.
- Compatibilidad PDF: `13` pruebas enfocadas aprobaron con `pypdf 6.15.0`.
  Ambas constancias usan PDFs sintéticos reales generados en memoria, sin
  reemplazar `PdfReader`: encadenan extracción y parseo de CUIT, condición o
  domicilio, y tabla/punto Web Services. Los dos formatos malformados devuelven
  errores de dominio controlados; no se persistieron archivos ni se usaron datos
  reales. `pip check` y `pip-audit -r requirements.txt` quedaron limpios.
- Frontend: `131` pruebas unitarias y `33` E2E Chromium aprobadas; type-check y
  build aprobados. ESLint conservó `13` advertencias históricas y cero errores.
- Frontend reproducible: `npm ci` con Node.js `24.15.0` y npm `11.12.1` dejó
  `postcss 8.5.23 -> nanoid 3.3.17`; `npm audit --omit=dev --audit-level=high`
  quedó sin vulnerabilidades y `package.json` permaneció intacto. La auditoría
  integral conserva `10` avisos exclusivos del toolchain de desarrollo (`5`
  moderados, `4` altos y `1` crítico), ya enrutados a la modernización PF-16C;
  no se ejecutó `npm audit fix` ni `--force`.
- Repositorio: `npm run lint`, `npm run backend:format:check` y `npm run test`
  aprobaron; este último reunió `607` backend, `131` frontend y `16` pruebas de
  scripts. `docs:check` también aprobó.
- Toda la evidencia de esta verificación usó datos sintéticos y, cuando
  correspondió, dobles controlados. No hubo acceso a VPS, consultas ARCA reales,
  solicitudes de CAE ni modificaciones de bases reales.

Fecha: 2026-08-06

- PF-03A: `9` casos enfocados cubren claves superiores desconocidas, ausencia
  de operación idempotente, compatibilidad transitoria del ítem UI,
  procesamiento sanitizado, reintento manual, preflight stale mixto y
  autorización stale preservada para reconciliación. Aprobaron además `29`
  pruebas de API, `50` del servicio de facturación, `118` de lotes y el backend
  completo con `566` aprobadas y `4` omitidas por infraestructura configurada.
  La puerta completa agregó `131` frontend, `16` de scripts, `5` de seeds y
  `33` E2E; Ruff, Black, type-check, build y `docs:check` quedaron verdes.
  ESLint conservó `13` advertencias históricas y cero errores; `pip-audit` y
  `npm audit --omit=dev` no encontraron vulnerabilidades productivas conocidas.
  Los escenarios usaron datos sintéticos y cero llamadas ARCA de escritura.
  `autoreview --mode local` con Codex `gpt-5.6-sol` y thinking `medium` pasó el
  preflight de TruffleHog y dos pasadas sin findings accionables; informó una
  probabilidad `0,99` de patch correcto y no activó fallback.
- PF-02B.3: `12` pruebas enfocadas de diagnóstico y recuperación stale, `164`
  de facturación/lotes y backend completo con `557` aprobadas y `4` omitidas.
  La puerta local agregó `131` frontend, `16` de scripts y `33` E2E; Ruff,
  Black, type-check, build y `docs:check` quedaron verdes. ESLint terminó sin
  errores y conservó `13` advertencias históricas de estilo. `pip-audit` y
  `npm audit --omit=dev` no encontraron vulnerabilidades productivas conocidas.
  La matriz cubre historia
  externa, grupos mixtos, ambos estados inciertos, doble recuperación, reclamo
  atómico, carrera con reintento manual, segundo preflight y metadatos
  sanitizados. No hubo emisiones reales, CAE ni llamadas ARCA de escritura.
- PF-02B.2: `11` escenarios específicos de reintento manual y `109` pruebas de
  lotes aprobadas; puerta global con `548` backend (`4` omitidas), `131`
  frontend, `16` de scripts y `33` E2E, además de Ruff, Black, type-check,
  build y `docs:check`. El PR `#19` y la CI post-merge de `main` aprobaron los
  seis checks obligatorios sobre `853e58b` y `1a5e335`, respectivamente.
  Los dobles controlados no solicitaron CAE ni realizaron llamadas ARCA de
  escritura.
- Actualización de `cryptography` a `50.0.0`: `47` pruebas enfocadas de
  criptografía, certificados, WSAA y migración aprobadas; backend completo con
  `540` aprobadas y `4` omitidas; Ruff, Black y `pip-audit` sin hallazgos. El
  PR `#20` aprobó los seis checks sobre `8ebf459`; su integración quedó en
  `712197d` y la CI post-merge volvió a aprobarlos.
- Tres tests batch con fecha fiscal explícita fija quedaron aislados del reloj
  de ejecución porque verifican numeración, no la ventana temporal. El helper
  productivo no cambió.

Fecha: 2026-07-30

- Puerta documental y tests de scripts: `npm run docs:check` aprobado y `16`
  pruebas aprobadas.
- Matriz local completa: `539` pruebas backend aprobadas con `4` omitidas,
  `131` frontend y `33` E2E; Ruff, Black, type-check, build y auditorías de
  dependencias productivas quedaron verdes. ESLint conservó `13` advertencias
  de estilo no bloqueantes y cero errores.
- La unidad solo modifica documentación, proceso y CI; no ejecutó emisiones,
  solicitudes de CAE ni llamadas ARCA de escritura.

Fecha histórica: 2026-07-29

- PF-02A: `68` pruebas enfocadas de servicio/API y `16` de vista; puerta global
  con `536` backend (`4` omitidas), `131` frontend, `7` de scripts y `33` E2E.
  El PR `#15` aprobó los seis checks de CI.
- PF-02B.1: `9` pruebas batch enfocadas, `147` de facturación/lotes y `539`
  backend (`4` omitidas). El PR `#16` aprobó los seis checks de CI.
- Ambos cortes usaron dobles controlados: no hubo emisiones reales, solicitudes
  de CAE ni llamadas ARCA de escritura.

Fecha histórica: 2026-07-10

- Evidencia histórica de la release `v0.2.1` / `8099b22`: backend `411` tests
  aprobados y `1` omitido; frontend `111` tests aprobados.
- Corte local P1 pool/worker: backend `443` tests aprobados y `2` omitidos.
- Integración PostgreSQL ejecutada aparte: aprobada con capacidad API `4`,
  overflow `0` y worker dedicado `1`; no creó lotes ni llamó a ARCA y no
  constituye evidencia de despliegue.
- Frontend del corte local: `121` tests aprobados; los `29` tests enfocados son
  un subconjunto y evidencia adicional, no una sumatoria. Lint, type-check y
  build limpios.
- Scripts raíz: 3 tests aprobados.
- GitHub Actions: Security Audit, Frontend Build, Backend Tests y E2E Tests
  aprobados para el tag y para el cierre documental `ece2bdf`.
- Clawpatch objetivo: 3 findings backend y 9 frontend revalidados como `fixed`.
- Estado local acumulativo: repo 0 abiertos, backend 85 y frontend 6. Los state
  dirs conservan históricos y duplicados; no interpretar esos contadores como
  bugs aceptados.
- QA manual productiva: login y emisión fiscal real satisfactoria.
- Cierre: `docs/project/audits/clawpatch/2026-07-10-cierre-ciclo-v0.2.1.md`.

Fecha histórica: 2026-07-05

- Clawpatch repo completo: `openFindings=0`, `features=27`, `findings=50`.
- Clawpatch backend: `openFindings=0`, `features=124`, `findings=19`.
- Clawpatch frontend: `openFindings=0`, `features=21`, `findings=18`.
- Frontend: `npm run lint:check` OK.
- Frontend: `npm run type-check` OK.
- Frontend: `npm run test:unit` OK, 83 tests.
- Frontend enfocado: `npm run test:unit -- useFormatters.spec.ts` OK, 6 tests.
- Frontend enfocado: `npm run test:unit -- pdf.service.spec.ts` OK, 2 tests.
- Clawpatch revalidate OK para los hallazgos de PDF preview, workflow E2E y
  `formatearFecha`.
- `autoreview` Codex/GPT-5.5 alto OK sobre los commits finales del ciclo.
- GitHub Actions CI remoto OK para `ebc176d`: `Frontend Build`, `Backend Tests`,
  `Security Audit` y `E2E Tests` en success.
- Cierre detallado: `docs/project/audits/clawpatch/2026-07-05-cierre-auditoria.md`.

Fecha: 2026-06-13

- Frontend E2E: `npm run test:e2e -- --reporter=list` OK, 31 tests en Chromium
  desktop.
- Frontend completo: `npm run test:unit` OK, 61 tests.
- Frontend: `npm run build` OK.
- Frontend: `npm run type-check` OK.
- Frontend: `npm run lint:check` OK.

Fecha: 2026-05-22

- Backend completo: `pytest tests -q` OK, 195 tests.
- Backend: `ruff check app tests` OK.
- Backend: `black --check app tests` OK.
- Launcher local: `scripts\factuflow-local-tray.ps1 -SelfTest` OK.
- Frontend completo: `npm run test:unit` OK, 47 tests.
- Frontend: `npm run type-check` OK.
- Frontend: `npm run build` OK.
- Frontend: `npm run lint:check` OK sin errores ni warnings.
- Clawpatch: backend, frontend y repo quedan con `openFindings=0`; la revision
  repo final no encontro features pendientes ni hallazgos nuevos.

Fecha: 2026-05-10

- Backend focalizado: `python -m pytest tests/test_lotes_comprobantes.py -q`
  OK, 30 tests. Cubre progreso real con emisión mockeada, sin solicitar CAE
  real, confirmación fiscal obligatoria y concurrencia de procesamiento.
- Backend: `ruff check app/api/lotes_comprobantes.py app/services/lote_comprobantes_service.py tests/test_lotes_comprobantes.py`
  OK.
- Backend: `black --check app/api/lotes_comprobantes.py app/services/lote_comprobantes_service.py tests/test_lotes_comprobantes.py`
  OK.
- Frontend focalizado: `npm run test:unit -- lote-progress` OK. Cubre calculo
  de porcentaje, tiempo transcurrido, estimacion restante y lotes en cola.
- Frontend: `npm run type-check` OK.
- Frontend: `npm run lint:check -- --quiet` OK.
- Frontend: `npm run build` OK.

Fecha: 2026-05-09

- Backend: `ARCA_ENV=homologacion pytest tests -q` OK, 141 tests.
- Backend: `ruff check app tests` OK.
- Backend: `black --check app tests` OK.
- Backend: la prueba
  `tests/test_lotes_comprobantes.py::test_validar_lote_rechaza_fecha_emision_fuera_de_ventana_arca`
  cubre fechas de extracto como serial numerico de Excel.
- Backend: se agregaron pruebas para rechazar emisión individual sin `concepto`,
  aceptar `Producto`/`Servicio` desde archivo y rechazar `Definido por archivo`
  cuando el Excel no mapea columna de concepto.
- Backend: `tests/test_perfiles_carga_masiva.py` cubre CRUD scopiado por
  emisor, predeterminado único, nombres por emisor, formatos accesibles,
  rechazo de `fecha_actual` como fecha fiscal y reglas incompletas.
- Frontend: `src/utils/perfiles-carga-masiva.spec.ts` cubre reglas relativas de
  fechas y selección automática de perfil de carga masiva.
- Frontend: `npm run test:unit` OK.
- Frontend: `npm run build` OK.
- Frontend: `npm run type-check` OK.
- Frontend: `npm run lint:check` OK sin errores; mantiene warnings de estilo
  Vue existentes.
- Browser: QA visual de perfiles de carga masiva en `http://127.0.0.1:8080`
  OK. Se verificó crear, editar, eliminar, predeterminar, autoaplicar, modificar
  antes de validar, validar Excel y abrir/cancelar el modal final de fecha
  fiscal sin emitir.
- API local: Excel privado local detectado como
  `Extracto bancario - creditos IVA exento`; al elegir servicios y
  `fecha_emision_modo=archivo` el lote `id=7` quedó con 20/20 grupos
  observados por fecha
  `06/04/2026` fuera de ventana ARCA. No se emitió ningún comprobante.

## Smoke real ARCA

El smoke real completado el 2026-03-09 quedó documentado en:

- `docs/project/notes/SESSION_2026-03-09.md`

Ese documento incluye:
- problemas encontrados
- como se resolvieron
- referencias privadas a CAEs emitidos; no copiarlas a documentación nueva
- pendientes operativos
