# PF-03/PF-04/PF-14 — persistencia fiscal fiel

Última revisión: 05/10/2026.

Estado: DISEÑO DE IMPLEMENTACIÓN; A-01 CONTINÚA ABIERTO.

## Objetivo y alcance

Cerrar la diferencia entre admisión y persistencia de la
[auditoría A-01](../project/analysis/auditoria-integral-2026-10.md#a-01--admisión-y-persistencia-no-describen-los-mismos-datos-p1).
Una autorización no debe quedar sin detalle porque la base tenga menos capacidad
que la preparación fiscal. La regla pertenece a la aplicación, con adaptadores de
almacenamiento; no crear otro cálculo ni un motor por canal.

Esta unidad define representación, consumidores y transición. Los
[ensayos sintéticos](../project/analysis/a01-validacion-representacion-2026-10.md)
son preparatorios: no constituyen una migración Alembic ni una implementación
integrada. No modifican producción.

No imponer máximos comerciales para acomodar datos al esquema antiguo. Conservar
el contexto decimal, operaciones y redondeos PF-03B. A-03 conserva la autoridad
sobre bases de IVA y moneda; no se resuelve aquí ni se adelantan capacidades P2.

## Representación elegida

Los consumidores operan con `Decimal` e `int`, sin conocer el formato físico.

| Datos | PostgreSQL | SQLite | Regla |
|---|---|---|---|
| Cantidad, precio, porcentajes y cotización | Texto decimal compacto | Texto decimal compacto | Valor finito exacto, sin `float` ni cuantización de almacenamiento |
| Subtotal de ítem, componentes monetarios del comprobante, total del intento y total estimado | `NUMERIC` sin precisión/escala declaradas | Texto decimal compacto | Conservar el resultado del cálculo vigente |
| Centavos de duplicados | `NUMERIC` entero sin límite de int64 | Texto entero canónico | Entero exacto, sin multiplicación que redondee |
| Código de ítem y cotización conservada para duplicados | `TEXT` | `TEXT` | El valor no depende del tamaño de su clave de búsqueda |

Los campos variables usan texto porque exponentes compensados pueden producir
un total pequeño y exceder la capacidad de `NUMERIC` PostgreSQL. Los importes
calculados y cuantizados a centavos por PF-03B caben en `NUMERIC` sin typmod;
esto no vuelve ilimitado al motor ni autoriza cambiar la calculadora.

El subtotal de ítem conserva la cuantización explícita a centavos que aplica
`FacturacionService._guardar_comprobante`; almacenar ese resultado exactamente.
No retirar ese redondeo ni sustituir el total fiscal por una suma nueva de líneas
redondeadas. La historia conserva la lectura anterior efectiva.

### Codec, comparación y agregados

- Sólo valores finitos; no almacenar `NaN` o infinitos.
- Canonizar coeficiente/exponente sin `float`, cuantización ni `normalize()`
  dependiente del contexto. Eliminar ceros finales equivalentes, unificar cero
  y no desarrollar exponentes enormes a texto fijo.
- La fidelidad es numérica. El codec de base no reescribe JSON originales,
  solicitudes congeladas, respuestas idempotentes ni hashes históricos.
- Igualdad usa representación canónica; rangos y ordenación requieren comparación
  numérica, nunca orden lexicográfico. Probar igualdad y orden entre escalas.
- PostgreSQL agrega con `SUM(NUMERIC)`. SQLite usa un agregado monetario explícito
  de coeficientes enteros y escala acreditada; no `SUM(TEXT)` ni `REAL`.
- No reemplazar globalmente `SUM`: conteos y cardinalidades conservan su conducta.
  Registrar y probar adaptadores en conexiones API, worker, herramientas y tests,
  tanto síncronas como `aiosqlite`.

## Capacidad auxiliar

Ampliar el importe sin `total_centavos` deja un desborde posterior de int64.
El adapter devuelve `int` y verifica integralidad exacta al leer/escribir.

La cotización no depende de `String(100)` ni de índices B-tree que incluyan su
texto completo. Incorporar una clave de tamaño fijo derivada del valor canónico
y comparar después el valor exacto. Una clave coincidente sólo produce candidatos,
no prueba igualdad fiscal ni reemplaza una huella o decisión de duplicados.

Revisar índices compuestos y planes en ambos motores, manteniendo emisor y
ambiente. Esta clave física no modifica evidencia histórica ni requiere conservar
archivos originales. La preparación común verifica también encodabilidad de
campos técnicos no ampliados, como el orden del ítem, antes de CAE. No convertir
capacidades técnicas en topes administrativos; cualquier restricción de operatoria
válida o fricción nueva exige la decisión de producto de `VISION.md`.

## Consumidores obligatorios

| Consumidor | Aceptación |
|---|---|
| DTO y emisión individual | Datos encodificables antes de reserva/CAE; respuesta y detalle exactos |
| Importación y preparación del lote | Mismo contrato, sin `float` nuevo; error de grupo/fila antes de emitir |
| Worker, síncrono y reintento parcial | Misma preparación; no tocar autorizados ni reenviar ante falla de almacenamiento |
| Guardado compartido y asociación A-02 | Detalle/snapshot exactos; asociación opcional no impide conservar CAE |
| Replay e intentos; reconciliación moderna/legacy | Lectura antigua/nueva sin alterar solicitudes, respuestas, CAE, reservas o incertidumbre |
| Duplicados e historial de lotes | Centavos, cotización, índices y agregados exactos; huellas y decisiones vigentes |
| API de consulta y frontend | Serialización/presentación sin pérdida; no recalcular en el navegador |
| PDF y reportes | Eliminar pérdidas de representación en datos ampliados; sin reinterpretar bases o moneda A-03 |
| Alembic y herramientas de traslado | Origen congelado y destino nuevo explícitos; modelos nuevos no definen historia |

Incluir `subtotal`, `descuento`, IVA y otros impuestos, no sólo `total`. Cuando
una salida pública vigente use `float`, delimitar su transición a decimal exacto
junto con API/frontend. No afirmar fidelidad integral conservando esa pérdida
en un consumidor de datos ampliados.

## Checklist, orden y estados

Implementación Nivel 2, con [checklist fiscal](fiscal-change-checklist.md):

1. Resolver permisos, emisor, ambiente y pertenencia con el flujo vigente.
2. Validar datos, fecha explícita y encodabilidad antes de reserva/CAE;
   conservar confirmación irreversible e idempotencia.
3. Persistir solicitud durable y controles vigentes de numeración/concurrencia.
4. Usar WSFE sin ampliar por inferencia su contrato externo.
5. Guardar resultado, detalle y actualizaciones en sus transacciones vigentes.
6. Si ARCA pudo autorizar y falla la persistencia, conservar incertidumbre y
   reconciliar; no interpretar rechazo ni liberar numeración o reenviar.

No crear estados. Un replay terminal conserva respuesta durable y orden de
validaciones aplicable. Una solicitud congelada no se recalcula ni se transforma
en nueva emisión para satisfacer el codec. No reducir asociación, permisos,
compare-and-swap o guardas de recuperación.

## Migración y compatibilidad

La implementación incorpora Alembic posterior al head vigente y fixtures de
la cadena real. Los modelos nuevos no amplían por sí solos una base existente.
Separar lectores congelados de origen del codec de destino.

En PostgreSQL, la escala antigua ya está aplicada. Ampliar o trasladar a texto
conserva valores, IDs, relaciones, restricciones y reservas. No recuperar entradas
originales desde un cliente, Excel o perfil actual.

En SQLite, trasladar la lectura obtenida con el `Numeric.result_processor`
original de cada columna. `Decimal(str(REAL))` y `CAST(... AS TEXT)` no garantizan
esa lectura: un valor proveniente de `1.00005` puede haberse leído como `1.0001`.
Conservar lo leído sin inventar la entrada original ni reparar historia.

Preflight: finitud, coherencia, capacidad de campos técnicos e índices. Conflictos
por clase/cantidad, sin datos privados; no corregir filas ni borrar reservas.
En SQLite, ensayar rebuild, atomicidad, FKs/ciclos reales, índices y restauración
verificada de `foreign_keys`. Una tabla simple no acredita ese grafo.

Los paquetes v3/v4 y sus descriptores congelados no se reinterpretan con modelos
nuevos. Definir versión/adaptación explícita de destino al head ampliado con lector
antiguo, transformación equivalente y verificación. No cambiar evidencia ni hashes
de paquetes existentes. Actualizar una instalación con Alembic no exige repetir
un traslado entre motores.

Detener API/worker durante los cambios y recrear conexiones antes de reabrir:
los prepared statements de `asyncpg` pueden conservar tipos anteriores. No
desactivar su caché productiva ni reintentar una emisión por ese error.

### Downgrade y recuperación

Antes de cualquier DDL, demostrar round-trip al esquema anterior sin pérdida
para código, cantidad, precio, porcentajes, cotización, subtotal de ítem,
componentes y centavos. SQLite exige procesadores anteriores, no sólo escala
nominal. Si un valor no cabe, abortar conservando esquema/datos ampliados.

Preferir corrección hacia adelante. Restaurar datos requiere autorización y
verificar escrituras posteriores; nunca truncar para arrancar código antiguo.
El rollback de aplicación anterior exige compatibilidad demostrada de esquema.

## Matriz de aceptación de la implementación

- Más de cuatro decimales de cantidad/precio, dos de descuento, seis de
  cotización; códigos largos y ceros equivalentes, con round-trip exacto.
- Exponentes compensados, valores fuera de tipos antiguos y cálculo PF-03B
  inalterado, sin texto de tamaño exponencial.
- Todos los componentes, centavos fuera de int64, igualdad/rangos y agregados
  exactos por emisor, incluidos conjuntos vacíos y grandes.
- Cadena Alembic real en ambos motores, lectura anterior preservada,
  JSON/huellas/reservas intactos y downgrade compatible/incompatible.
- Importación, lote, worker, reintento, replay y guardado/recuperación con tipos
  nuevos; fallas pre/post-CAE sin reenvío automático.
- Confirmación y clave ausentes, conflicto, concurrencia, revocación e
  aislamiento multiemisor conforme a sus contratos vigentes.
- Consulta, PDF y frontend de datos ampliados sin pérdida; errores funcionales
  A-03 conservan su dueño y no se declaran corregidos.
- Suite completa, cobertura, PostgreSQL desechable, lint/formato/tipos/build,
  E2E, auditorías y revisión sensible/QA proporcionales antes de integración.

Los ensayos de diseño no satisfacen esta matriz integrada ni cierran A-01. No
implementar aquí padrón, tasas, reconciliación integral o nuevas pantallas.
