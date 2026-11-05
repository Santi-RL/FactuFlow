# Auditoría de código sin consumidores — 05/11/2026

## Resultado y alcance

Se retiraron **163 líneas de código en 15 archivos**, sin borrar archivos
completos ni modificar pruebas. El diff de código de aplicación contiene
únicamente eliminaciones: 122 líneas del frontend y 41 del backend. Este informe
y la corrección de una descripción en el README de servicios se registran por
separado y no se descuentan de esos conteos.

La revisión partió del commit
`75022e74db4186e2d5efcd7b71a755b3e314aee2`, con árbol limpio y referencias
remotas actualizadas. Se preservó la rama anterior de planificación. El alcance
es código sin consumidores, alcanzabilidad, ramas estáticamente imposibles y
restos comentados; no modifica producción, datos, dependencias ni decisiones
de producto.

No apareció una pantalla, componente o módulo operativo completo cuya
eliminación pudiera justificarse. La limpieza reduce mantenimiento; no demuestra
una mejora perceptible de velocidad ni explica por sí sola una sensación de
interfaz pesada.

## Método y evidencia anterior a las eliminaciones

Se inventariaron los 598 archivos versionados de la base. Las búsquedas
incluyeron código, pruebas, documentación, scripts y configuración. Se
excluyeron del inventario los datos locales, credenciales, dependencias
instaladas y artefactos generados.

- Frontend: se siguieron importaciones estáticas, reexportaciones y los
  `import()` literales del router desde `src/main.ts`; también se revisaron
  las plantillas Vue y los usos de componentes dinámicos. Los 106 archivos
  fuente/estilo/asset operativos del mapa son alcanzables. `env.d.ts` se
  conserva por inclusión del compilador, no por importación de ejecución.
- Backend: se siguieron importaciones Python mediante AST desde FastAPI,
  scripts operativos y registro de modelos, incluyendo la ejecución implícita
  de inicializadores de paquetes. Los 109 módulos de `backend/app` tienen
  entrada o forman parte de esos paquetes. El worker nace del ciclo de vida
  de FastAPI. Alembic descubre revisiones por su propio mecanismo.
- Los candidatos se contrastaron con las referencias de símbolos TypeScript,
  búsquedas textuales y llamadas por cadena, decoradores y registros de Python.
  Un resultado automático aislado no autorizó una eliminación.
- Se buscaron terminadores seguidos por sentencias inalcanzables en 140
  archivos Python no destinados a pruebas. No surgieron casos confirmados.
  TypeScript también pasó con `--allowUnreachableCode false`. Las búsquedas de
  condiciones literales falsas, flags fijos y 219 comentarios de bloque,
  incluidos los de plantillas Vue, no produjeron otro lote seguro. Los estados
  mutables que empiezan en `false` se conservan.

Para reproducir una búsqueda sobre el contenido anterior:

```powershell
git grep -n -w SIMBOLO 75022e74db4186e2d5efcd7b71a755b3e314aee2 -- .
```

Las rutas y líneas de las siguientes tablas corresponden a esa base, no a las
líneas desplazadas después de limpiar. Las salidas completas y los mapas se
conservaron localmente en `.tmp/unused-audit/`: `evidence-head.json`,
`inventory.json`, `backend-graph.json`, `frontend-symbols.json` y
`qualified-consumers-before.txt`.

### Lote 1: frontend

| Símbolo y ubicación anterior | Resultado de búsqueda y alcanzabilidad | Pruebas y decisión |
|---|---|---|
| `arcaService.getPuntosVenta`, `services/arca.service.ts:24` | Una coincidencia para `getPuntosVenta`: la definición. Los consumidores de `arcaService` llaman `getStatus` y `testConnection`; no hay despacho por índice o enumeración. El módulo llega desde las vistas Sistema y Puntos de venta, pero este método no tiene llamadas. | Ninguna prueba invoca el método. Se elimina el cliente; el endpoint HTTP continúa disponible. |
| `PuntoVentaArca`, `types/punto_venta.ts:71` | Las cuatro referencias frontend pertenecen exclusivamente al método anterior y su importación. Las dos coincidencias Python son un alias de otro tipo, consumido por el endpoint. | Se retira sólo el tipo frontend que queda sin consumidor. El tipo Python se conserva. |
| `empresaService.delete`, `services/empresa.service.ts:45` | El análisis de símbolos encuentra sólo la declaración. La búsqueda global de `empresaService` muestra sus importaciones y llamadas a listar, consultar, crear, actualizar y extraer constancias; ninguna llamada a `delete`, alias, índice o reflexión. | Los dobles de pruebas no llaman a esta implementación. Se elimina únicamente el método web; no la ruta del backend. |
| `createPuntoVenta`, `stores/puntos_venta.ts:62` | Dos coincidencias en todo el repositorio: definición y exposición en el retorno del store. Ninguna pantalla ni plantilla la llama. | No aparece en pruebas. Se elimina la acción. |
| `deletePuntoVenta`, `stores/puntos_venta.ts:116` | Dos coincidencias: definición y retorno del mismo store. Sin consumidor desde el router o las plantillas. | No aparece en pruebas. Se elimina la acción. |
| `puntosVentaService.create` y `.delete`, `services/puntos_venta.service.ts:16,32` | Sus únicas llamadas de aplicación están dentro de las dos acciones anteriores, que carecen de consumidores. Se revisaron todos los importadores del objeto. | `puntos_venta.spec.ts` contiene dobles `create: vi.fn()` y `delete: vi.fn()`, pero no invoca las implementaciones. Se mantienen los casos y se retiran los dos métodos reales. |
| `PuntoVentaCreate`, `types/punto_venta.ts:45` | Las cinco referencias frontend forman la cadena tipo → servicio → acción sin consumidor. Las tres referencias Python pertenecen al contrato HTTP de compatibilidad y siguen vigentes. | Se elimina exclusivamente el tipo frontend. |
| `PDFDownloadOptions`, `services/pdf.service.ts:31` | Una coincidencia global: declaración de interfaz. La descarga y previsualización actuales reciben argumentos directos. | Sin referencias en pruebas; se elimina. |
| `ListParams`, `types/api.ts:13` | Una coincidencia global: declaración. Los servicios usan sus contratos específicos. | Sin referencias en pruebas; se elimina. |
| `ESTADOS_COMPROBANTE`, `types/comprobante.ts:306` | La declaración es la única referencia TypeScript. Las otras seis coincidencias globales pertenecen a Python y sus pruebas. Las vistas usan `ESTADOS_COMPROBANTE_NOMBRES`. | Se elimina sólo la constante frontend. Se conservan nombres visibles y estados/constraints Python. |
| `useUIStore.setLoading` y su estado `loading`, `stores/ui.ts:15,49` | `setLoading` tiene dos coincidencias: declaración y retorno. Todos los importadores del store usan notificaciones y sidebar; ninguno lee o escribe su `loading`. No hay mapeo de acciones o estado por cadena para esos campos. | Sin uso en pruebas. Se retiran acción, estado y exposición. |
| `limpiarError`, `stores/comprobantes.ts:299` | Dos coincidencias globales: declaración y retorno. Las acciones vigentes limpian sus errores dentro de sus recorridos actuales. | Sin referencias en pruebas; se retira únicamente la acción sin consumidor. |
| `useNotification.show` y `.hide`, `composables/useNotification.ts:43,47` | Todos los consumidores se revisaron por nombre de importación y desestructuración: solicitan `showSuccess`, `showError`, `showWarning` o `showInfo`. No solicitan los dos métodos genéricos ni transfieren el objeto completo a un consumidor dinámico. | Sin llamadas de pruebas; se retiran los dos wrappers y el import de tipo que sólo necesitaba `show`. El cierre de avisos sigue usando `uiStore.hideNotification` en el layout. |

Las coincidencias de nombres genéricos como `delete`, `show`, `hide` y `loading`
no se trataron como referencias equivalentes entre servicios. Se comprobó la
identidad del objeto y se revisaron sus consumidores, incluidas las plantillas.

### Lote 2: backend

Cada símbolo de esta tabla produjo exactamente una coincidencia global: su
propia definición. No aparece en importaciones, pruebas, documentación,
registros dinámicos ni contratos HTTP generados.

| Símbolo | Ubicación anterior | Evidencia de contrato y decisión |
|---|---|---|
| `CertificadoCreate` | `schemas/certificado.py:20` | Las rutas de certificados importan respuestas y contratos del wizard, no esta clase; se elimina. |
| `CertificadoUpdate` | `schemas/certificado.py:27` | Ninguna ruta, herencia o registro Pydantic la utiliza; se elimina. |
| `SubirCertificadoRequest` | `schemas/certificado.py:85` | La subida usa parámetros multipart `File`/`Form`, no este modelo JSON; se elimina. |
| `UsuarioUpdate` | `schemas/usuario.py:65` | La administración usa `UsuarioAdminUpdate`; el restablecimiento tiene su contrato específico. Se elimina el modelo anterior sin usuarios. |
| `COBERTURAS` | `services/duplicados_lotes_service.py:83` | Conjunto declarado, nunca leído ni usado como validador; se elimina. |
| `ESTADOS_RESERVADOS` | `services/duplicados_lotes_service.py:86` | Conjunto sin lecturas. Se conservan los conjuntos usados y las guardas efectivas; se elimina. |
| `DETALLE_ELEGIBILIDAD_RECE` | `services/elegibilidad_rece_service.py:48` | Texto sin consumidores; los mensajes y categorías realmente enviados se conservan. Se elimina. |

Se compararon los documentos OpenAPI completos y el inventario de tablas y
columnas registrados antes/después: **idénticos**. Las clases retiradas no eran
schemas publicados por los endpoints.

## Elementos conservados

### Sin consumidores internos demostrados, pero con contrato externo incierto

- `app.arca.crypto.get_certificate_info`: sólo aparece su definición. Es un
  helper público del módulo ARCA; no se puede descartar una importación desde
  herramientas privadas o manuales externas al repositorio.
- `WSAAClient.invalidate_cache`: sólo aparece su definición. Puede usarse en
  recuperación operativa y afecta tickets y certificados. No se retira una
  capacidad de invalidación por ausencia de llamadas de la aplicación web.
- `vps_migration.convert_row_for_table` y su helper `convert_value`: forman una
  cadena sin entrada interna identificada. Se conservan por la compatibilidad
  incierta con herramientas privadas de migración y recuperación.

Esas posibilidades no son prueba de uso. Son límites de la evidencia disponible
y justifican mantenerlos separados de las eliminaciones confirmadas.

### Falsos positivos o soporte que sí tiene una entrada

- `WSFEv1Client._parse_cae_response`: lo llama
  `tests/test_arca/test_wsfev1_correlacion.py`. El recorrido productivo usa el
  parser de lista; se conserva el wrapper cubierto por pruebas.
- `PDFService._fetch_recurso_pdf`: lo usan las pruebas que rechazan URLs externas
  y archivos fuera de templates. La generación usa el fetcher compartido;
  no se elimina ese soporte durante esta limpieza.
- `lotesComprobantesService.obtener`: la UI usa resumen, seguimiento y grupos
  paginados, pero `LotesComprobantesView.spec.ts` conserva un doble y comprueba
  expresamente que el método de detalle completo no se llame. Se mantiene el
  método y `LoteComprobanteDetalle` para no alterar ese contrato de prueba.
- `finalize` del agregado SQLite: SQLite lo invoca por convención al registrar
  `_SQLiteAmountSum` con `create_aggregate`. Su nombre no necesita una llamada
  Python explícita.
- Endpoints de compatibilidad deshabilitados, alta manual de puntos y parámetro
  antiguo de constancias: son contratos HTTP con respuestas y validación
  explícitas, no ramas muertas. Se conservan sus rechazos y dependencias.
- Decoradores FastAPI, validadores Pydantic, eventos SQLAlchemy, filtros Jinja,
  relaciones ORM declaradas por cadena, imports por efectos de registro,
  revisiones Alembic y comandos operativos: tienen entradas de framework,
  herramientas o consola. Tampoco se borran inicializadores de paquetes.
- `env.d.ts`, CSS/Tailwind, iconos usados mediante `<component>` y rutas Vue
  diferidas: no se decide su uso sólo contando imports estáticos o selectores.
- Flags configurables del worker y de emisión en bloques: los valores de
  entorno y los límites de configuración son parte de la operación vigente.
  Tampoco se retira la carpeta documental `app/afip` por su nomenclatura legacy.

## Invariantes y alcance fiscal

Se aplicó el checklist fiscal a las áreas sensibles alcanzadas. El resultado
del análisis es una retirada de definiciones y métodos sin consumidores
funcionales. Las declaraciones de clases y constantes sí se evaluaban al
importar sus módulos; esa ejecución, incluso si aparece cubierta por pruebas,
no demuestra su uso por una ruta u operación. No cambia el orden de validación,
emisión, almacenamiento o reconciliación.

| Comprobación | Resultado esperado y evidencia |
|---|---|
| Entrada de emisión y autorización humana | No se editan vistas, confirmaciones, requests fiscales, routers ni parsers. |
| Fechas, importes, numeración y CAE | No cambian cálculos, fechas, claves idempotentes, reservas ni llamadas ARCA. |
| Estados e incertidumbre | Las constantes retiradas no participaban en transiciones. Permanecen locks, constraints, estados efectivos y recuperación. |
| Permisos y aislamiento | Los esquemas usados por usuarios y certificados se conservan; OpenAPI y tablas son idénticos. |
| Error y concurrencia | Se mantienen todos los casos de prueba, incluidos PostgreSQL, reintentos, reconciliación y aislamiento. |
| Intercambio simplicidad/protección | No se agregan pasos ni se retiran protecciones visibles o fiscales. |
| Recuperación del cambio | Dos lotes separados en la evidencia local; no se revierte código ajeno. Un fallo atribuible a un lote obliga a restaurarlo antes de continuar. |

No es una modificación fiscal crítica del recorrido ejecutable y no se ejecutó
`autoreview` ni Clawpatch. No se hicieron llamadas reales a ARCA, emisiones,
accesos al VPS, push ni merge.

## Validación

La referencia del frontend pasó sus 329 pruebas y compiló antes de editar.
El backend nativo de Windows no inició por la advertencia de HarfBuzz-Subset
de WeasyPrint; se conservó el fallo y se pasó a Linux, sin filtrar warnings ni
modificar dependencias. Se interrumpieron también comprobaciones Black nativas
que no devolvían resultado; el formato se verificó en Linux con un solo proceso.
Se usó una imagen local de pruebas con Python 3.11.17,
pytest 9.1.1 y WeasyPrint 70.0, sobre copias de los archivos versionados.
Sus 42 requisitos Python aplicables se contrastaron con los dos archivos de
dependencias actuales: todos satisfechos, sin instalaciones ni actualizaciones.
Cada corrida completa dispuso de su propio PostgreSQL desechable, con base
exacta de integración, opt-in del harness, loopback y sin red externa ni
puertos publicados. Las dos corridas no compartieron base ni sesiones.

| Control | Resultado |
|---|---|
| Backend completo de referencia, con PostgreSQL | 2.100 pruebas aprobadas; cobertura 82,03 %, por encima del 69 % exigido. |
| Backend completo candidato, con PostgreSQL | 2.100 pruebas aprobadas; sin fallos, errores ni omisiones en JUnit; cobertura 82,01 %, conservando el umbral del 69 %. |
| Comparación detallada de cobertura | Sin pérdida de líneas ni ramas cubiertas del código restante, ajustando los desplazamientos de línea. |
| Frontend, después del lote 1 | 329 pruebas aprobadas en 45 archivos. |
| Chromium E2E, lote 1 estabilizado | 45 recorridos aprobados. |
| Compilación frontend después de cada lote | Aprobada en ambos; la última sin advertencias del build. |
| Compilación Python candidata | `compileall` aprobado. |
| Ruff, ESLint y tipos TypeScript | Aprobados; TypeScript también con código inalcanzable prohibido. |
| Black candidato | 192 archivos conformes, sin reformatear. |
| OpenAPI y registro de tablas/columnas | Comparación completa idéntica. |
| Integridad de pruebas y copia candidata | 140 archivos de pruebas iguales a la base; 262 archivos de código, pruebas, estilos y recursos candidatos iguales al árbol final, normalizando CRLF/LF. |
| Scripts de repositorio | 32 pruebas aprobadas antes y después; no se modifican esos scripts. |
| Alineación documental y revisión final | `docs:check`, privacidad, idioma y `git diff --check` aprobados. |

Una primera corrida E2E dentro del sandbox no pudo alcanzar su servidor local.
Una corrida inicial fuera de él coincidió con la edición del lote y terminó
44/45; no se tomó como referencia válida. La repetición completa sobre el lote
estabilizado aprobó los 45 casos. La compilación inicial del lote emitió
telemetría de tiempos de plugins; la repetición posterior terminó limpia.

Los logs detallados quedan en `.tmp/unused-audit/`, excluidos de Git. La CI
remota, los builds de imágenes de distribución y una prueba de producción no
se ejecutan en este alcance local sin publicación.
Los dos contenedores PostgreSQL desechables se retiraron al finalizar sus
corridas; los contenedores de ejecución se eliminaron automáticamente.

La variación de cobertura entre referencia y candidata corresponde a 20
sentencias de declaraciones retiradas que antes se ejecutaban al importar
módulos. Las líneas sin cubrir y las ramas cubiertas/sin cubrir conservan sus
conteos. `coverage-comparison.json` conserva el contraste con ajuste de líneas;
`source-integrity.json` registra la igualdad de fuentes y pruebas.

## Complejidad que esta limpieza no resuelve

Se observa concentración de responsabilidades en archivos grandes:
`vps_migration.py` (8.015 líneas), `lote_comprobantes_service.py` (7.191),
`facturacion_service.py` (4.952), `duplicados_lotes_service.py` (4.520),
`LotesComprobantesView.vue` (4.103) y `EmpresaConfigView.vue` (2.418), medidos
después de limpiar. El tamaño señala coste de comprensión y prueba; no prueba
por sí mismo lentitud ni justifica dividirlos sin estudiar sus contratos.

El chunk principal pasa aproximadamente de 159,70 kB a 159,54 kB sin comprimir,
y de 55,40 kB a 55,35 kB gzip, según Vite. Es una reducción pequeña. Parte del
código sin consumidores ya quedaba fuera del bundle por optimización del
compilador. No se midieron latencias, CPU, consultas o carga de producción.

Una mejora perceptible de fluidez requiere medir recorridos concretos y
proponer una unidad de simplificación con invariantes propias. Esta auditoría
no transforma ese diagnóstico en autorización para rediseñar, quitar guardas
o adelantar trabajos del roadmap.
