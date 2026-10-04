# Auditoría integral del estado actual de FactuFlow

Fecha: 03/10/2026.

Estado: evidencia de auditoría y limpieza local; no acredita integración,
publicación, despliegue ni resolución de los hallazgos fiscales pendientes.

## Conclusión

El proyecto mantiene una lógica coherente con su visión: operación multiemisor
explícita, dominio fiscal con evidencia durable, procesamiento recuperable y
una instalación pequeña. La futura operación mediante agentes encaja como otra
interfaz de esos mismos casos de uso. La base permite evolucionar sin una
reescritura, pero todavía hay inconsistencias que impiden describir el estado
actual como completamente limpio o abrir indiscriminadamente nuevas capacidades.

La revisión corrigió deriva documental, código sin uso y defectos de
presentación/contexto, y confirmó problemas de persistencia y lecturas fiscales
que deben resolverse en cortes propios. Una suite verde no elimina estos
problemas: los ensayos específicos muestran situaciones que la suite previa
no cubría. La puerta de estabilización y los cortes futuros viven únicamente en
[`ROADMAP.md`](../../../ROADMAP.md).

## Alcance y método

- Base de código aceptada: `4623647c809f8fbb40216f2c67ebf68b3d03d990`.
  Planificación documental precedente:
  `2a956e7ad8288af797830a693b9e98f4aa135f78`; no cambia runtime.
- Lectura de visión, instrucciones, índices y gobierno; contraste de manuales,
  API, diseños vigentes, setup, runbooks, contratos y scripts de calidad.
- Revisión en paralelo de backend y frontend, dependencias y fronteras de
  autorización, importes, persistencia, estado incierto, contexto y lectura.
- Búsqueda AST/grafo de imports más consumidores y pruebas antes de retirar
  código. La ausencia de cobertura no se trató como prueba de código muerto.
- Suites y ensayos sintéticos, con PostgreSQL desechable protegido por el
  harness. La copia Docker se construyó sólo con archivos públicos versionados;
  los procesos de pruebas rechazaron conexiones externas mediante un guard de
  sockets. No se usaron certificados ni datos de una instalación.
- La consulta productiva autorizada se delegó al plano de control en solo
  lectura. Su evidencia y estado concretos permanecen allí y en la conversación
  privada, fuera de este dossier público. No se ejecutó ningún cambio productivo.

La auditoría cubre áreas y contratos del proyecto completo; no constituye una
prueba formal de ausencia de errores. No se ensayó autorización real de ARCA,
ni se validaron todas las combinaciones normativas mediante comprobantes reales.
La evidencia previa de planificación sigue en
[`confiabilidad-arca-roadmap.md`](confiabilidad-arca-roadmap.md).

## Limpieza realizada

| Área | Corrección y motivo |
|---|---|
| Documentación de dominio | READMEs de backend/servicios, estructura e integración describen PF-19D; dejan de instruir promoción mediante el contrato PF-19B sustituido |
| Autoridades y continuidad | Índices y manual dejan de fijar despliegue o release obsoletos; se conserva el plano de control como autoridad productiva |
| Testing y contribución | Comandos E2E, umbrales reales, scripts y alcance de auditoría de dependencias coherentes; pruebas PostgreSQL correctamente marcadas |
| Setup y certificados | Entorno relativo al directorio real, WSASS frente a producción, CSR correcto y claves gestionadas; se retira la receta de borrar WAL/SHM de SQLite |
| Historia | Manifiesto con hashes canónicos UTF-8/LF sin BOM, conservando los hashes declarados anteriormente y sin modificar snapshots |
| Código frontend sin uso | Se retira `lote-totals.ts` y su prueba exclusiva; el lote consume totales del backend. El catálogo de herramientas apunta a consumidores vigentes |
| Código backend sin uso | Se retiran `get_current_active_user`, `_validar_sin_bloqueo_preautorizacion` y `_obtener_grupos_lote`; sin llamadas actuales ni contratos públicos documentados |
| Fechas visibles | Cuatro consumidores usan el formateador de calendario existente; una fecha ISO de certificado no retrocede un día en Argentina |
| Contexto visual | Detalles de clientes/comprobantes y formulario de cliente limpian el contexto anterior y descartan respuestas tardías; se preservan emisión, snapshots e incertidumbre |
| Errores PDF | Descarga y preview dejan de devolver la excepción técnica cruda; mensaje público accionable y diagnóstico privado |
| Construcción Docker | Exclusiones de backend y frontend para entorno, claves y evidencia; el backend también excluye bases y runtimes locales. `.gitignore` permite versionar la barrera del backend. Git ignore por sí solo no gobierna `COPY . .` |
| Ejemplos y privacidad | El placeholder de clave usa `CUIT_homologacion_AAAAMMDD_HHMMSS.key`; fixtures de rutas usan el identificador sintético compartido. Se retiran ejemplos numéricos sin procedencia sintética documentada |
| CI local | La auditoría npm usa el mismo árbol completo y umbral que la CI; no se oculta tooling de desarrollo |

No se eliminaron migraciones, APIs de fixtures, caminos de recuperación legacy
ni helpers públicos sólo porque tengan pocos consumidores. Se preservaron
cálculo decimal, solicitud ARCA, numeración, confirmación fiscal, permisos de
backend y contratos de reconciliación. `VISION.md` permanece intacto.

## Hallazgos fiscales confirmados y tratamiento

### A-01 — admisión y persistencia no describen los mismos datos, P1

[`ItemComprobanteBase`](../../../backend/app/schemas/comprobante.py) admite un
código de más de 50 caracteres y cantidades/precios sin límites compatibles con
[`ComprobanteItem`](../../../backend/app/models/comprobante_item.py).
[`Comprobante`](../../../backend/app/models/comprobante.py) limita totales y
cotización con `Numeric`. El cálculo representable no garantiza persistencia.

Con los tipos reales clonados en tablas TEMP de PostgreSQL, el DTO acepta:

| Entrada sintética | Resultado de persistencia |
|---|---|
| Código de 51 caracteres | Rechazo `22001` |
| Cantidad/precio `1,00005` | Almacenados como `1,0001` |
| Cantidad `1000000` | Rechazo `22003` |
| Precio `100000000` | Rechazo `22003` |
| Total `10000000000` | Rechazo `22003` |
| Cotización `10000` | Rechazo `22003` |

Los ejemplos son pruebas de frontera, no afirmaciones de incidentes reales.
El código del ítem no viaja a WSFE; puede fallar su almacenamiento después de una
autorización. La protección del estado incierto evita un reenvío ciego, pero no
el atasco ni la pérdida de precisión del detalle.

**Tratamiento:** PF-03/PF-14, contrato común de admisibilidad y persistencia antes
de CAE, con precisión preservada en preparación, solicitud, ítems e historia.
Evaluar capacidad de almacenamiento y compatibilidad antes de introducir límites
que bloqueen operatoria válida; no cuantizar entradas silenciosamente ni cambiar
redondeos PF-03B. API, Excel, lotes, worker, reintentos y recuperación son
consumidores obligatorios del corte.

### A-02 — dependencia administrativa después de CAE, P1

El CRUD y el modelo permiten clientes con igual documento dentro del emisor.
[`_guardar_comprobante`](../../../backend/app/services/facturacion_service.py)
intenta resolverlos con `scalar_one_or_none()` después de recibir autorización.
Dos clientes sintéticos iguales se guardan; la persistencia fiscal simulada
falla con `MultipleResultsFound`. El ensayo usó SQLite nueva en memoria y una
respuesta sintética: cero solicitudes externas.

**Tratamiento:** PF-04/PF-14, resolver asociación antes de la frontera
irreversible o independizar el guardado fiscal del alta administrativa.
Conservar snapshot del receptor y recuperación. No fusionar clientes o historia
automáticamente, ni imponer una constraint única sin estudiar anónimos,
duplicados existentes y concurrencia. El futuro padrón consume esta solución;
no la reemplaza ni requiere esperar a su implementación.

### A-03 — lecturas fiscales inconsistentes, P1 para corrección

[`ReportesService`](../../../backend/app/services/reportes_service.py) reconstruye
bases dividiendo un IVA ya redondeado por la tasa. Un comprobante con neto
`0,03`, IVA `0,01` y total `0,04` devuelve base/neto `0,047619…`.
Ventas y ranking agregan nominales de distintas monedas: PES `100` y DOL `100`,
con cotización histórica `1500`, producen total `200`. Las filas omiten moneda y
cotización. Métodos reales confirmaron ambos resultados con vouchers sintéticos.

La entrada individual web fija PES, pero el contrato HTTP acepta otras monedas;
detalle y reportes de la UI presentan ARS incondicionalmente. La exposición no
depende de que el usuario introduzca divisas desde esa pantalla.

**Tratamiento:** PF-03/PF-04/PF-17, lecturas desde hechos fiscales conservados y
moneda explícita, separando moneda nominal de cualquier proyección en pesos.
Cerrar la política de agrupación/conversión con autoridad funcional antes de
codificar; utilizar cotización histórica aplicable, jamás la actual por defecto.
No deducir bases exactas de IVA redondeado ni inventar categorías legacy.
La corrección actual no necesita esperar a la importación histórica PF-05 ni al
dashboard mensual o a categorías fiscales nuevas.

### A-04 — identificación, tasas y reconciliación ya planificadas, P1

Permanecen los problemas demostrados en el dossier anterior: identificación de
CF descartada en importación, CUIT/CF rechazado indiscriminadamente, tasas sin
soporte convertidas a IVA cero, revisión decimal divergente y comparación legacy
insuficiente. Esta auditoría no los convirtió en implementaciones terminadas.

También se confirmó que `clean_cuit()` se usa para documentos distintos de CUIT:
`AB12345678` termina como `12345678`. La aceptación PF-13 debe incluir esta
transformación inválida y la representabilidad de otros tipos según WSFE, sin
alterar las huellas o el contenido de intentos congelados.

**Tratamiento:** ampliar aceptación de los cortes dueños ya existentes, evitando
una segunda tarea de receptor, otra calculadora o un reconciliador paralelo.
Las guardas modernas y la conservación de incertidumbre continúan siendo
invariantes; el gap legacy no demuestra que esas guardas se puedan eludir.

## Otros hallazgos abiertos

| Hallazgo | Prioridad y dueño | Alcance necesario |
|---|---|---|
| Excepciones técnicas en respuestas ARCA/certificados (`e.mensaje`/`str(e)`) | P2, PF-09/PF-12 | Frontera pública controlada frente a diagnóstico privado; conservar códigos fiscales accionables y revisar logs/SQL sin parámetros sensibles |
| `null` explícito en updates de campos obligatorios de clientes/emisores | P2, PF-12/PF-14 | Distinguir ausencia de `null`, validar antes del commit y conservar constraints; incluir rollback y consumidores |
| Paso del wizard de certificados dirige al portal productivo aunque se eligió homologación | P2, PF-09/PF-17 | Propagar ambiente a guía/enlaces de todos los pasos y probar ambos recorridos; documentos ya distinguen WSASS |
| Instantes sin zona se interpretan distinto entre actividad y progreso | P2, PF-12/PF-15/PF-17 | Contrato UTC explícito con compatibilidad histórica; no confundir instantes con fechas fiscales ni asumir la zona de todos los registros antiguos |
| Alertas de dependencias de build | P1 de integración, PF-16 | Resolver la cadena vulnerable sin rebajar la puerta ni aplicar `--force`; comprobar compatibilidad visual de una eventual migración mayor |

`npm audit` completo informó cinco entradas de severidad alta de una misma
cadena de tooling: `braces`, `chokidar`, `micromatch`, `fast-glob` y `tailwindcss`.
El árbol productivo auditado aparte no reportó vulnerabilidades conocidas. El
registro oficial consultado ofrece `braces` 3.0.3 y Tailwind 3.4.19 como últimas
versiones de esas líneas; no existe una corrección menor evidente de la cadena.
El [aviso upstream](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm)
indica ausencia de versión parcheada para `braces` y describe agotamiento de pila
con patrones profundamente anidados. No se afirma que el frontend estático
productivo exponga esa herramienta. La puerta de CI completa sigue fallando ante
estas alertas; su migración debe ser una unidad técnica verificada.

## Arquitectura y futuro

La fortaleza es la existencia de dominio fiscal, evidencia y recuperación; el
riesgo de evolución está en tener reglas parciales distribuidas entre routers,
servicios, importación y vistas. Los routers contienen permisos, replay y CAS:
exponer un servicio interno como herramienta MCP no reutilizaría automáticamente
esas garantías.

La [dirección de arquitectura](../../agents/architecture-direction.md) define
responsabilidades comunes, extracción gradual y operación asistida. La relación
con los cortes actuales es concreta:

| Corte actual | Pieza reutilizable futura |
|---|---|
| Fidelidad de receptor y padrón anticipado | Identidad y procedencia de datos, sin inferencias fiscales del modelo |
| Admisibilidad, precisión y previsualización | Preparación determinística que web y chat pueden revisar |
| Persistencia fiscal independiente de CRUD | Ejecutar y recuperar una operación sin depender de un alta posterior |
| Evidencia/reconciliación y lecturas | Consultar el resultado durable sin reinterpretar historia ni reenviar |
| Autorización, contexto y trazabilidad | Alcance explícito de cada agente/usuario y revisión humana verificable |

La futura autorización humana debe vincularse a usuario, emisor y datos exactos.
Un booleano o un token de resumen enviado por un cliente autorizado no prueba por
sí solo intervención humana frente a un agente capaz de enviar esos parámetros.
Esta limitación afecta la exposición futura; no se usa para desactivar la
confirmación o agregar fricción a la UI actual.

No se recomienda una reescritura, microservicios, persistir conversaciones,
delegar cálculos a un LLM ni exigir una plataforma completa antes de reparar
un contrato. Extraer fronteras al trabajar el dominio con todos sus consumidores
y pruebas; el tamaño de un archivo es una señal de concentración, no evidencia
suficiente para refactorizarlo.

## Validación y límites de cierre

Resultados sobre la limpieza final:

| Control | Resultado |
|---|---|
| Backend completo, SQLite y PostgreSQL | 1497 pruebas aprobadas; cobertura 73,33 %, por encima de la puerta del 69 % |
| Fixtures sintéticos de certificados/ARCA, después del último cambio de ejemplos | 41 pruebas aprobadas sin red; Black aprobado |
| Frontend unitario | 241 pruebas aprobadas en 38 archivos; cobertura de statements 63,86 %, branches 58,03 %, functions 51,55 % y lines 65,35 %, con todas sus puertas aprobadas |
| Chromium E2E | 36 recorridos aprobados; backend simulado y cero solicitudes fiscales reales |
| Lint, formato y tipos | Ruff, Black, ESLint y TypeScript aprobados |
| Herramientas del repositorio | 28 pruebas de scripts y cinco del catálogo de herramientas aprobadas |
| Build del frontend y Nginx | Imagen final construida; configuración, archivos y GET estático aprobados |
| Arranque backend con PostgreSQL | Migración en `a1b2c3d4e5f6` y GET de salud, base y setup con HTTP 200; worker deshabilitado y conexiones externas bloqueadas |
| Contratos no cubiertos previamente | Ensayos sintéticos reprodujeron A-01, A-02 y A-03; no se confunden con reparaciones ni emisiones reales |
| Exclusiones Docker | Marcadores sintéticos de entorno, claves anidadas, evidencia y datos excluidos en ambos contextos; código y ejemplo público conservados |
| Privacidad del código | TruffleHog 3.97.0 sobre la copia de archivos públicos: cero detecciones, con verificación externa deshabilitada; revisión adicional del diff y ejemplos |
| Documentación | `docs:check` aprobado; revisión de destinos y anclas de 119 Markdown, 14 hashes históricos canónicos e idioma español |
| Dependencias Python | `pip-audit` sobre `requirements.txt`: sin vulnerabilidades conocidas |
| Dependencias npm | Árbol completo: cinco alertas altas y puerta pendiente; `--omit=dev` sin alertas, únicamente como diagnóstico de exposición |

La ejecución backend definitiva utilizó la estructura completa del repositorio
y el entorno esperado por los tests. Los fallos de un primer harness incompleto
(archivos de raíz ausentes y configuración de worker sobrescrita) se corrigieron
en el harness antes de repetir la suite; no se ocultaron ni se flexibilizaron
aserciones, warnings o umbrales. La cobertura de una suite enfocada no se usó
para sustituir la puerta global. Un aviso de tiempos de plugins de una primera
compilación no volvió a aparecer en la construcción final.

### Clasificación y checklist proporcional

La unidad se considera **Nivel 2 por contexto multiemisor**, aunque no modifica
reglas ni transiciones fiscales. Sus consumidores activos modificados son las
vistas de clientes/comprobantes, stores compartidos, cuatro presentaciones de
fechas de calendario y descarga/preview PDF. Los helpers retirados carecen de
consumidores; el catálogo y los mocks E2E se actualizaron. API de emisión,
worker, lotes, replay, reintentos y reconciliación se revisaron como fronteras
que deben conservarse; la suite completa cubrió su comportamiento vigente.

Invariantes de esta limpieza: no mostrar datos ni resolver respuestas tardías
del emisor anterior; no enviar una edición desde un contexto obsoleto; conservar
fecha fiscal explícita, confirmación irreversible, payload congelado,
idempotencia y estado incierto; no cambiar cálculos, permisos de backend o
persistencia fiscal; no filtrar una excepción PDF en HTTP. No hay una nueva
transición de emisión ni un nuevo contrato ARCA. Los fallos de peticiones,
cambios de ruta/emisor y respuestas fuera de orden se cubren con pruebas de
componentes reales; la invalidación al desmontar la vista se revisó en el código,
sin atribuirle una aserción específica. La revisión independiente backend/frontend
contrastó consumidores y diff; no se aplicó `autoreview` de cambio fiscal crítico
porque esta unidad no modifica ese comportamiento.

La QA de contexto y fechas se ejecutó con componentes y Chromium sintéticos;
no se probó emisión manual ni autorización externa, fuera del alcance permitido.
El smoke consultó únicamente GET locales sin credenciales operativas. La consulta
productiva no acredita los cambios locales. Para recuperar esta limpieza bastaría
revertir su commit y reconstruir las imágenes: no hay migración propia ni cambio
de datos que revertir. No se ejecutó CI remota, push, merge o despliegue.

La aplicación queda preparada para ejecutar los cortes de estabilización
delimitados. La puerta de dependencias bloquea integración de runtime hasta
resolver sus alertas. Después, cada reparación puede integrarse con su propio
contrato, evidencia y CI; no se exige cerrar todos los hallazgos en un único
cambio. Las capacidades nuevas esperan los P1 de sus consumidores. La auditoría
no declara ausencia de defectos. Una limpieza reversible no reemplaza diseño,
autoridad funcional ni checklist de una reparación fiscal.
