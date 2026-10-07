# Evaluación de Security Cloud y coordinación de PR

Fecha de contraste: 06/10/2026. Inventario de PR comprobado el 07/10/2026.

Estado: evaluación fechada y adjudicación para planificación. El estado activo
vive en el [portafolio](../../agents/development-portfolio.md); el orden aceptado
vive en [ROADMAP.md](../../../ROADMAP.md). Las prioridades de este dossier son
propuestas, no una modificación de ese orden ni una autorización de parches.

## Alcance y evidencia

Security Cloud examinó `bf79d101a808fce49c3e1c96b39ee9387d7afac7`.
Los 18 informes se contrastaron con código, configuración y documentación de
`main` en `509091d9c3879fe5fb8e59188b2b4248456631f2`, después de integrar A-01
mediante el [PR #82](https://github.com/Santi-RL/FactuFlow/pull/82).

Los informes declaran revisión estática independiente. Su etiqueta de
validación no acredita explotación dinámica ni una instalación productiva.
Cinco comprobaciones offline sobre funciones reales extraídas, con dependencias
y respuestas sintéticas, confirmaron: cabecera WSFE discordante aceptada,
rechazo con CAE tratado de forma distinta en individual/masivo, intercalación
de reset/login, corte temprano de filas XLSX y texto interno en reportes.
La simulación de login no sustituye concurrencia real entre sesiones PostgreSQL;
la de XLSX no mide descompresión ni carga.

La evidencia detallada de esos ensayos permanece privada. No se publican datos
de una instalación, archivos fiscales, credenciales, logs ni rutas privadas.
No se hicieron solicitudes ARCA/CAE, importaciones operativas ni ensayos de
agotamiento. Este dossier no acredita salud, exposición o retención productivas.

La lectura del código y el
[PR #61](https://github.com/Santi-RL/FactuFlow/pull/61) acreditan las correcciones
originales de SC-03/SC-14 y la parte PDF de SC-15. La prueba local existente de
PDF no pudo iniciar por la advertencia de HarfBuzz-Subset tratada como error;
no se presenta como integración aprobada ni se relajó la política de warnings.

## Inventario de los 18 casos

Los identificadores SC-01–SC-18 son etiquetas de esta evaluación en el orden de
los informes consultados, no IDs del servicio. «Alta», «media» y «baja» son la
severidad del escaneo; P1/P2 expresan impacto y condiciones de la propuesta.

La columna de estado describe el contraste del commit base. La corrección de
la receta SC-04 se documenta aparte para no conservarla como un segundo parche
futuro ni afirmar un cierre remoto de Security Cloud.

| Caso y problema | Severidad | Estado del contraste | Prioridad propuesta y dueño |
|---|---|---|---|
| SC-01: manifest del paquete de migración sin prueba externa de procedencia | Alta | Vigente; requiere sustitución del paquete importado, no acceso HTTP al runtime | P2, PF-11/PF-12; requisito antes de próxima importación |
| SC-02: presupuesto de expansión y lectura XLSX | Media | Parcial; carga acotada y corte máximo+1 de filas útiles ya existen | P2 preferente, PF-13; sólo presupuesto residual ZIP/XML/dimensiones/trabajo |
| SC-03: archivos privados copiados a capas Docker | Media | Problema original corregido por `backend/.dockerignore` con contexto `./backend` | Sin parche nuevo; cierre verificable contra revisión actual |
| SC-04: receta VPS construye desde rama mutable | Media | Vigente en el commit base; corrección documental en setup | P2 documental, atendido por selección/verificación de SHA |
| SC-05: argumentos reinterpretados por wrapper Windows | Media | Vigente en herramienta de auditoría | P2, PF-16; antes de Clawpatch con contenido no confiable |
| SC-06: enlaces/cambio de raíz durante exportación y limpieza | Media | Vigente; requiere escritura en almacenamiento gestionado | P2, PF-10; operación y propiedad de archivos |
| SC-07: constancias PDF leídas antes del límite y parseadas sin presupuesto | Media | Vigente; rutas autorizadas, no acceso anónimo demostrado | P2 preferente, PF-09; lectura y trabajo acotados |
| SC-08: login sin limitación de intentos | Media | Vigente en aplicación; protección de borde no comprobada | P1 propuesto, PF-12/PF-14; intentos y consumo bcrypt |
| SC-09: cabecera WSFE no correlacionada y respuesta contradictoria | Media | Vigente; protección individual ante rechazo con CAE ya conserva incertidumbre | P1 fiscal propuesto, PF-02/PF-04/PF-09 |
| SC-10: Compose de desarrollo accesible por red con valores conocidos | Media | Vigente en configuración de desarrollo; no demuestra exposición productiva | P1 condicionado, PF-16; comprobar accesibilidad antes de uso compartido |
| SC-11: login verifica credencial antigua y emite token tras reset concurrente | Media | Vigente; intercalación sintética, sin prueba PostgreSQL concurrente | P1 propuesto, PF-12/PF-14 |
| SC-12: importación materializa manifiesto y tablas sin presupuesto | Baja | Vigente en CLI privada | P2, PF-11/PF-12; coordinar con SC-01 |
| SC-13: SOAP sin presupuesto total ni concurrencia acotada | Baja | Brecha de robustez; explotación no demostrada | P2, PF-09; preservar incertidumbre y no reenviar CAE |
| SC-14: instrucciones de bugs solicitan evidencia sin redacción | Baja | Problema original corregido en instrucciones y campo de logs de CONTRIBUTING | Sin parche nuevo; verificar cierre contra revisión actual |
| SC-15: excepciones internas en respuestas de PDF/reportes | Baja | Parcial; PDF corregido, tres rutas de reportes pendientes | P2, PF-14/PF-15; frontera residual de errores |
| SC-16: datos fiscales duplicados en logs INFO | Baja | Vigente; acceso y retención productivos no comprobados | P2, PF-15; minimización con trazabilidad |
| SC-17: reportes materializados sin presupuesto de recursos | Baja | Vigente | P2, PF-04/PF-17; preservar precisión A-01 y autoridad A-03 |
| SC-18: RSA síncrono y ciclo pendiente de claves CSR | Baja | Vigente; cifrado/permisos y limpieza manual de huérfanos ya existen | P2, PF-09; concurrencia y propiedad durable |

En el contraste base, dos problemas ya estaban corregidos y dieciséis
conservaban trabajo, incluidos dos parciales. No se acreditó un incidente P0.
El hallazgo alto de migración tiene consecuencias importantes, pero depende
de un paquete sustituido y de una importación posterior. SC-09 merece propuesta
P1 por su frontera fiscal irreversible, aunque el escaneo lo clasifique medio.

### Corrección documental de SC-04

[Setup](../../setup/README.md#instalación-en-vps-producción) selecciona un SHA
completo aprobado, exige checkout limpio y revalida antes de construir/iniciar.
La creación de administrador por Compose reconstruye desde esa misma revisión.
Preflight, migraciones, backup, rollback y comprobación del runtime siguen en
el [flujo canónico](../../agents/production-workflow.md).
El provisionamiento global del host se distingue de actualizar la aplicación.

Este tratamiento corrige la receta. No prueba que una instalación anterior
la siguiera, no cambia producción y no cierra el finding en Security Cloud.
SC-04 no se incorpora como otro parche futuro de aplicación.

## Unidades propuestas, dependencias y aceptación mínima

Los cortes siguientes necesitan delimitación y autorización antes de codificar.
Compartir una fila o un PF no obliga a combinar reparaciones distintas.

| Unidad | Casos y dependencia | Aceptación mínima propuesta |
|---|---|---|
| Respuesta fiscal WSFE | SC-09; PF-02/PF-04/PF-09, separado de reconciliación integral P2 | Cabecera/contexto/detalle coherentes; pruebas de CAE con rechazo, campos ausentes/discordantes, parcial, individual/batch y replay. Contradicción conserva evidencia, reserva y reconciliación; nunca reenvío automático |
| Credencial y revocación concurrentes | SC-11; permisos y contrato de tokens actuales | Login/reset intercalados en dos sesiones PostgreSQL; sólo emite para la credencial/revisión verificada. Preservar revocación, usuarios desactivados y sesiones válidas |
| Protección de intentos de login | SC-08; separado de SC-11 y de política de contraseñas | Intentos existentes/inexistentes, concurrencia y recuperación legítima; presupuesto antes del costo bcrypt. Explicar cualquier bloqueo operativo nuevo antes de imponerlo |
| Uso seguro de desarrollo en red | SC-10; configuración de desarrollo, no Compose productivo | Verificar binds y acceso local/LAN previsto; secretos explícitos cuando corresponda. Acceso LAN requerido conserva decisión del usuario; no tocar firewall o host por esta unidad |
| Frontera común XLSX | SC-02; analizar/detectar/validar, PF-13 | Miembros/expansión/dimensiones/cadenas compartidas, filas vacías y trabajo con archivos sintéticos controlados; casos legítimos cercanos al máximo y varios usuarios. Conservar interpretación fiscal |
| Frontera de constancias PDF | SC-07; consumidores de emisor y puntos de venta | Lectura acotada antes de parsear, páginas/trabajo y concurrencia; permisos y extractores legítimos. La constancia sigue descriptiva y no habilita CAE |
| Importación de paquetes | SC-01/SC-12; PF-11/PF-12, próxima importación autorizada | Integridad/procedencia comprobable por un canal externo al paquete; rechazo de sustitución, tamaño y tablas antes de materializar. Compatibilidad v3/v4/v5, restauración aislada e invariantes fiscales; no reimportar una instalación existente |
| Ejecución Windows de auditoría | SC-05; PF-16, próxima ejecución afectada | Argumentos literales con metacaracteres y ruta con espacios; sin `CALL`/reconstrucción shell. Preservar ruta de herramienta, stdout/stderr y código de salida |
| Archivos gestionados | SC-06; PF-10, resguardo y propiedad vigentes | Enlaces/sustitución de directorio antes y durante operación en Windows/Linux; ningún acceso fuera de raíz, limpieza legítima y certificados activos intactos |
| Transporte SOAP | SC-13; PF-09, consumidores WSAA/WSFE | Deadline total, concurrencia, cancelación y respuestas tardías con dobles. Timeout posterior a envío conserva incertidumbre; no abandonar y repetir CAE |
| Errores de reportes | SC-15; frontera de errores ya registrada, PF-14/PF-15 | Tres rutas 500 con mensaje público controlado, sin excepción/ruta/datos internos; permisos y diagnóstico privado útil. No reabrir PDF corregido |
| Logs mínimos | SC-16; PF-15, trazabilidad compartida | Correlación de operación/resultado sin duplicar CAE, documento, importes o contenido de archivos. No borrar historial fiscal ni atribuir a este corte una retención productiva no verificada |
| Lecturas eficientes de reportes | SC-17; PF-04/PF-17, contratos A-01/A-03 | Volumen representativo, proyecciones/agregación/paginación pertinentes; igualdad decimal exacta, alcance por emisor y períodos válidos. No cerrar bases IVA/moneda por optimizar recursos |
| CSR y material pendiente | SC-18; PF-09, propiedad de certificados | Generación concurrente, interrupción, clave pendiente y cleanup legítimo con cifrado/permisos. Conservar material activo; vencimiento o borrado automático nuevo requiere decisión explícita |

Los nuevos límites que rechacen operatoria hoy válida, políticas de contraseña,
acceso LAN, períodos o eliminación de CSR conservan la regla de simplicidad
segura de `VISION.md`. No agregar pasos rutinarios ni reducir validaciones,
aislamiento, trazabilidad, idempotencia o reconciliación por este inventario.

Para cambios fiscales completar el
[checklist](../../agents/fiscal-change-checklist.md) antes de implementar.
Las pruebas de locks/commits usan el harness PostgreSQL desechable; las de
ARCA usan dobles sin salida fiscal. Cada reparación demuestra su defecto y
verifica los consumidores, error, concurrencia y recuperación aplicables.

## PR abiertos: fotografía y coordinación

El 07/10/2026 permanecen abiertos siete PR de Dependabot con los mismos heads
de la evaluación. Se leyeron diffs y jobs; seis tienen siete checks verdes en
sus ejecuciones evaluadas. #78 falla en backend y omite E2E. #75–#78 usan una
base anterior a A-01; #79–#81 ya parten del commit contrastado.
Refrescar base, head y CI antes de integrar; esta tabla no certifica su estado
futuro ni la compatibilidad de combinarlos.

**Ninguno de esos siete PR repara directamente los 18 hallazgos.** Auditoría
de dependencias verde no demuestra autenticidad de paquetes, correlación WSFE,
revocación concurrente, presupuestos de archivos o minimización de datos.

| PR y actualización | Evidencia evaluada | Adjudicación, dependencia y aceptación |
|---|---|---|
| [#75](https://github.com/Santi-RL/FactuFlow/pull/75), setup-python 6 → 7 | [CI verde](https://github.com/Santi-RL/FactuFlow/actions/runs/37308455147); base anterior a A-01 | P3, PF-16. Actualizar base y CI de los tres jobs. No cierra SC-04 ni SC-05 |
| [#76](https://github.com/Santi-RL/FactuFlow/pull/76), pytest 9.1.1 y asyncio 1.4.0 | [CI verde](https://github.com/Santi-RL/FactuFlow/actions/runs/37308456508); base anterior a A-01 | P3, PF-16. Validar A-01, scope de loops, warnings como errores y cobertura. No resuelve SC-11 |
| [#77](https://github.com/Santi-RL/FactuFlow/pull/77), psycopg2-binary 2.9.13 | [CI verde](https://github.com/Santi-RL/FactuFlow/actions/runs/37308463528); base anterior a A-01 | P2, PF-12/PF-16. Traslado A-01/v5 y PostgreSQL; coordinar SC-01/SC-12 sin atribuirles corrección. Las sesiones async usan asyncpg |
| [#78](https://github.com/Santi-RL/FactuFlow/pull/78), SQLAlchemy 2.1.2 | [CI roja](https://github.com/Santi-RL/FactuFlow/actions/runs/37308476548); dos fallas, base anterior a A-01 | P2, PF-12/PF-16. Resolver pools SQLite y restauración de `query_only`; comprobar codecs/listeners/agregados, migración/downgrade y ambos motores. No integrar mientras falle ni eliminar aserciones sin preservar el contrato |
| [#79](https://github.com/Santi-RL/FactuFlow/pull/79), Vitest/coverage-v8 5.0.3 | [CI verde](https://github.com/Santi-RL/FactuFlow/actions/runs/37520878661); base A-01 | P3, PF-16. Depende de cerrar el control efectivo de cobertura P2; conservar conjunto medido y revisar mocks. La actualización conjunta no repara ese defecto previo |
| [#80](https://github.com/Santi-RL/FactuFlow/pull/80), plugins Vue/TypeScript ESLint | [CI verde](https://github.com/Santi-RL/FactuFlow/actions/runs/37520866015); base A-01 | P3, PF-16. Candidato antes de #81; conservar reglas y warnings como errores. Solapamiento de manifests no prueba redundancia |
| [#81](https://github.com/Santi-RL/FactuFlow/pull/81), ESLint 10.12.0 | [CI verde](https://github.com/Santi-RL/FactuFlow/actions/runs/37520846462); base A-01 | P3, PF-16. Coordinar con #80; definir conservar reglas recomendadas 9 o adoptar 10, porque mantiene `@eslint/js` 9.39.5. Sin autofix masivo por este mantenimiento |

### Compatibilidad pendiente de #78

Los [logs](https://github.com/Santi-RL/FactuFlow/actions/runs/37308476548/job/111757866508)
registran 1540 tests aprobados y dos fallas: SQLite espera `NullPool` y recibe
`AsyncAdaptedQueuePool`; el inventario espera restaurar `PRAGMA QUERY_ONLY=1`
y observa `0`. SQLAlchemy documenta el cambio de pool por defecto desde 2.0.38.
El pooling es una explicación compatible que debe comprobarse para la segunda
falla; el log no demuestra una escritura efectiva ni autoriza a eliminar el
control de solo lectura. La actualización también debe validar los contratos
incorporados por A-01 después de esa base.

### Control de cobertura PF-16, separado de los 18 casos

[`frontend/vite.config.ts`](../../../frontend/vite.config.ts) anida métricas en
`coverage.thresholds.global`. La implementación de Vitest 4.1.11 interpreta
`global` como patrón de archivos; los umbrales globales reales quedan sin definir.
Los métodos reales de resolución/comprobación, con un mapa sintético de 0 %,
devuelven código 0 con esa estructura y código 1 con las métricas directamente
en `thresholds`. Es un ensayo del control, no la cobertura real del producto.

Propuesta P2: conservar statements 56 %, branches 50 %, functions 43 %, lines
57 % y `autoUpdate: false`; corregir sólo la estructura, demostrar rechazo
controlado y aprobar la suite real. En #79 la cobertura informada supera esos
porcentajes, pero su CI verde no demuestra que la barrera global funcione.
El defecto es previo a Vitest 5; su reparación tiene una unidad separada.

## Decisiones y cierre

- La recomendación P1 fiscal y de autenticación requiere decisión de posición
  respecto de A-03 y «Ahora». El orden vigente del roadmap se conserva.
- SC-10 sólo se adelanta por exposición comprobada; SC-01/SC-12 y SC-05 son
  requisitos antes de sus próximas operaciones afectadas. Los P2 no obligan a
  cerrar todo el repositorio antes de cualquier reparación fiscal.
- SC-03/SC-14 se verifican contra la revisión actual antes de cambiar su estado
  en Security Cloud; no se descartan como falsos positivos del SHA antiguo.
  SC-02/SC-15 permanecen abiertos por su brecha residual. Esta documentación
  no modifica estados del servicio.
- La limpieza de PR acompaña soluciones verificadas en `main`: integrar una
  propuesta autorizada o cerrar sólo la enteramente sustituida, con trazabilidad.
  No hay redundancia completa acreditada; ni #80 ni #81 sustituyen al otro.
  No ignorar dependencias o versiones mayores sólo para reducir la lista.
- Cierre, push, merge, eliminación remota, publicación y despliegue conservan
  la autorización aplicable. La preparación documental no los ejecuta.

Las puertas de [calidad](../../agents/change-quality-gates.md) y
[testing](../../agents/testing.md) gobiernan cada unidad. Los resultados de una
reparación posterior se registran en su PR/dossier, el estado activo se actualiza
en el portafolio y la evidencia concreta de instalación permanece en el plano
de control; este contraste fechado no se moderniza como estado permanente.

Referencias primarias de apoyo:
[flujo y parches de Security Cloud](https://learn.chatgpt.com/docs/security/setup),
[alcance de validación](https://learn.chatgpt.com/docs/security/faq),
[contexto Docker](https://docs.docker.com/build/concepts/context/#dockerignore-files),
[CALL de Windows](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/call),
[timeouts de Requests](https://requests.readthedocs.io/en/latest/user/quickstart/#timeouts),
[pooling SQLite](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#pooling-behavior),
[Psycopg](https://www.psycopg.org/docs/news.html),
[Vitest 5](https://main.vitest.dev/guide/migration/),
[umbrales Vitest](https://main.vitest.dev/config/coverage#coverage-thresholds) y
[ESLint 10](https://eslint.org/docs/latest/use/migrate-to-10.0.0).
