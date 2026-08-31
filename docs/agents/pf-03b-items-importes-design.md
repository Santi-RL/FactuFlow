# PF-03B — contrato estricto de ítems e importes

Fecha de diseño: 31/08/2026.

Estado: contrato implementado; evidencia de validación y publicación en el
[`dossier v0.3.3`](../project/releases/v0.3.3-candidate.md).

## Alcance autorizado

Cerrar la validación de ítems e importes en emisión individual, importación,
formatos, perfiles que los consumen, lotes, worker, reintentos, recuperación
stale y reconciliación. Es un cambio fiscal Nivel 2. No modifica las políticas
de fecha, numeración, puntos de venta, IVA, idempotencia ni reconciliación.

El corte conserva descuentos de 0 a 100 inclusive, cantidad positiva, precio
no negativo y valores predeterminados vigentes. No introduce topes comerciales
ni nuevas alícuotas. Los importes deben ser finitos y calculables con la
aritmética decimal y el redondeo vigentes.

## Contrato y autoridad

- `ItemComprobanteCreate` rechaza propiedades desconocidas y números no finitos.
  El contrato superior sigue siendo `EmitirComprobanteRequest`.
- La interfaz separa los datos editables/de respuesta del DTO de escritura.
  Envía únicamente los campos declarados, con orden normalizado; no envía
  `subtotal`, IDs de respuesta ni propiedades auxiliares.
- El cálculo decimal conserva su algoritmo, orden de operaciones y redondeo.
  Un helper puro compartido permite comprobar la representabilidad de los
  totales al validar el request, antes de crear estado fiscal.
- Una entrada inválida no se convierte en cero. En importación se conserva el
  contenido inválido hasta informar el error de la fila/grupo. Los descuentos
  ausentes conservan el valor predeterminado cero.
- Un total informado inválido no se trata como un total ausente. Las constantes
  numéricas de formatos se comprueban antes de guardar y al consumir formatos.
- Los perfiles seleccionan versiones de formatos y políticas; no se inventa
  un contrato nuevo de importes dentro del perfil.

## Orden e invariantes

1. Autenticación y validación HTTP conservan su orden vigente. Un ítem inválido
   devuelve `422` antes del cuerpo del endpoint y antes de operación idempotente,
   intento, reserva, guarda fiscal o solicitud de CAE.
2. La UI valida antes de vista previa y vuelve a validar antes del envío. Un
   campo numérico vacío permanece inválido; el cero escrito es explícito.
3. Los mensajes identifican ítem y campo sin mostrar datos crudos de errores,
   secretos, rutas ni contenido del payload.
4. Los productores de lotes construyen el mismo modelo estricto y persisten
   `model_dump(mode="json")`. Un grupo inválido no conserva un payload emitible.
5. Worker, procesamiento unitario/batch y reintentos revalidan snapshots antes
   de cualquier escritura fiscal. No se eliminan claves para forzar aceptación.
6. Stale valida el conjunto antes de reencolar: un payload inválido impide
   reencolar los grupos intactos de ese conjunto.
7. Si ARCA pudo autorizar, un error de validación nunca libera numeración ni
   convierte incertidumbre en rechazo. Se conserva evidencia y reconciliación.
8. La verificación de una operación incierta reutiliza exactamente el DTO y la
   clave congelados, sin reconstruirlos desde datos editados ni exigir nuevas
   condiciones locales mutables.
9. Campos y valores canónicos válidos no cambian: dumps, hashes y replay
   idempotente conservan compatibilidad.
10. Se conserva el aislamiento por emisor, ambiente, punto y tipo. Las guardas,
    locks y compare-and-swap existentes no cambian.

## Compatibilidad, persistencia y rollback

No hay migración de esquema ni saneamiento de historia. Los snapshots válidos
ya proceden del dump Pydantic; el antiguo modelo descartaba campos de UI antes
de persistirlos. Deben seguir validando y mantener su hash exacto. Un snapshot
con propiedades desconocidas es inválido y no se reescribe automáticamente.

Las filas/grupos con errores de importación pueden persistir como trabajo
administrativo recuperable; esto no crea operaciones, intentos ni reservas
fiscales. Se conserva la atomicidad de los caminos existentes.

El rollback de este corte es de aplicación al SHA anterior, sin downgrade de
base. La publicación de una release no despliega. El rango desde producción,
backup/restauración, preflight y autorización de despliegue se registran por
separado; no se realizan mutaciones productivas durante este trabajo.

## Matriz de aceptación

| Frontera | Casos y evidencia requerida |
|---|---|
| Schema/API | Extras anidados, errata de descuento, límites, `NaN`, infinitos y desbordamiento; `422` y cero estado fiscal/CAE, incluso solicitudes concurrentes |
| DTO/UI | Campos exactos, orden, descuento preservado; vacío, no finitos y totales inválidos bloqueados; cero y 100 % válidos; corrección recuperable |
| Confirmación | Revalidación final, reset de confirmaciones/clave al editar, doble interacción y snapshot incierto idéntico |
| Importación | Formato canónico y personalizado, descuento ausente/cero/100/inválido, decimales argentinos y total informado inválido; error accionable sin sustituir valores |
| Formatos/perfiles | Constantes válidas e inválidas, formatos existentes consumidos desde perfiles, sin cambiar sus políticas |
| Servicio | Cálculo equivalente y rechazo sanitario de resultados no representables; snapshots/hash válidos compatibles |
| Worker/reintento | Payload anidado inválido falla antes de emitir, también fallback batch/unitario |
| Stale | Grupo mixto bloquea reencolado; autorización confirmada conserva CAE/evidencia en reconciliación |
| Reconciliación | Datos inválidos no reconstruyen comprobante ni autorizan reemisión; caminos válidos conservados |
| Cierre | Backend/frontend completos, cobertura, lint/formato/tipos/build, E2E y QA visual, PostgreSQL/Runtime Smoke, auditorías de dependencias, documentación y autoreview final |

Todas las pruebas usan datos sintéticos y dobles; ninguna solicita CAE real.
La implementación técnica no sustituye una decisión fiscal o de producto:
si aparece una incompatibilidad válida no resuelta, se consulta antes de avanzar.
