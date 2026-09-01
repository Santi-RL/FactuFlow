# QA manual reutilizable

Última revisión: 01/09/2026

Estado: VIGENTE.

Este documento define escenarios manuales que pueden repetirse. La evidencia de
una versión, el resultado de un smoke concreto y los conteos de pruebas viven en
el PR, dossier o plano de control correspondiente.

El estado desplegado autoritativo vive en el plano de control `VPS Hostinger` /
`vps-admin`. Este documento no acredita una instalación.

## Preparación segura

- Usar entorno local o desechable y datos sintéticos.
- Confirmar emisor y ambiente antes de cualquier prueba ARCA.
- No guardar credenciales, CUITs, CAEs, PDFs, Excels, capturas o logs reales en
  el repositorio.
- No emitir ni solicitar CAE sin autorización explícita del usuario.
- Si la prueba sólo verifica UX, usar dobles y bloquear toda salida fiscal real.

## Matriz por tipo de cambio

### Fiscal o ARCA

- fecha visible y payload técnico correctos;
- confirmación irreversible con fecha y punto cuando corresponda;
- éxito, rechazo, timeout y respuesta incierta;
- replay con misma clave idempotente;
- ausencia de reintento automático si ARCA pudo autorizar;
- reconciliación y mensajes sanitizados;
- otro emisor, ambiente o punto no puede reutilizar el estado.

### Ítems e importes

- vaciar cantidad o precio: el mensaje identifica el campo y no muestra un
  total inventado; corregirlo permite continuar;
- precio cero y descuento 100 % explícitos conservan su significado;
- editar datos tras revisar cierra la vista previa y la confirmación anterior;
- comprobar fecha y punto en la confirmación irreversible;
- verificar que un estado incierto reutiliza la solicitud y clave congeladas;
- importar descuento vacío, decimal argentino, texto ilegible y fuera de rango
  con formato oficial y personalizado: sólo las entradas válidas son emitibles;
- un total informado inválido produce error, sin convertirse en ausencia;
- los detalles de error no exponen el body ni datos privados.

### Lotes y worker

- lote completamente válido;
- observaciones previas sin emisión;
- error parcial y reintento seguro;
- worker detenido, reiniciado y con claim concurrente;
- lote stale intacto frente a lote con evidencia fiscal;
- preservación de datos recuperables y cero duplicación.

### Multiemisor

- preparar un administrador, un operador asignado a A/B y un emisor C no
  asignado, todos sintéticos;
- comprobar cero, uno y varios accesos: login permitido sin accesos, selección
  automática con uno y elección explícita con varios;
- verificar A/B permitidos y C prohibido por header, query, body e ID directo;
- activar y desactivar `Puede crear y editar emisores`: la creación se asigna al
  creador en forma atómica y la edición requiere capacidad más acceso;
- comprobar que el operador nunca puede borrar emisores, administrar usuarios,
  entrar a `Sistema`, almacenamiento ni plantillas globales;
- promover y degradar conservando asignaciones; antes de degradar, revisar el
  alcance mostrado y confirmar conscientemente una lista vacía si corresponde;
- revocar el emisor activo durante una sesión: el siguiente request recibe
  `403`, se refresca la lista, se limpian selección y datos y no se cambia de
  emisor ni se cierra sesión automáticamente;
- cambiar o revocar mientras una respuesta está pendiente y confirmar que la
  respuesta tardía no actualiza stores ni pantallas;
- confirmar un lote sintético, encolarlo y revocar después: el worker puede
  terminarlo, pero cargas, confirmaciones, reintentos y consultas nuevas quedan
  bloqueadas;
- comprobar que clientes, certificados, puntos, comprobantes, lotes, PDFs,
  reportes, perfiles y formatos nunca cruzan emisores;
- verificar mensajes accionables que no revelen datos de C y cero solicitudes
  reales de CAE.

### UI administrativa

- lenguaje comprensible sin términos técnicos innecesarios;
- estados normales breves y errores accionables;
- toda acción requerida indica dónde y cómo realizarla;
- estados vacíos, carga, red y recuperación;
- teclado, foco, contraste y zoom razonables;
- no agregar confirmaciones o pasos que no mitiguen un riesgo concreto.

### Documentación

- el manual describe únicamente capacidades disponibles;
- API y ejemplos coinciden con rutas y contratos reales;
- roadmap, estado, changelog y diseños respetan sus responsabilidades;
- ningún documento vivo presenta historia o producción como estado actual;
- enlaces, idioma, privacidad y nomenclatura ARCA correctos.

## Puntos de venta desde PF-19D

Para un cambio que toque autoridad, preferencias o consumidores, verificar con
datos sintéticos y sin solicitudes CAE reales:

- primera comprobación manual con un punto `CAE - …`, otro sistema, un bloqueado
  y un dado de baja;
- puntos nuevos compatibles con uso habilitado por defecto, incluidos los
  temporalmente bloqueados o dados de baja;
- ausencia y reaparición sin perder ni reactivar una preferencia deshabilitada;
- rechazo atómico de respuesta vacía, duplicada, inconsistente, sin tipo o con
  timeout;
- aislamiento entre emisores y entre homologación y producción;
- usuario común y administrador pueden editar descripciones y uso, pero ninguno
  puede cambiar número, sistema, presencia, bloqueo o baja;
- confirmación explícita al cambiar `Usar en FactuFlow`, sin borrar formularios,
  perfiles ni lotes recuperables;
- constancia opcional que sobrescribe sólo descripciones presentes, muestra su
  procedencia, no consulta WSFE y no cambia elegibilidad ni revisión fiscal;
- vista habitual, `Mostrar todos`, contador y estados breves coherentes;
- individual, perfiles, lotes, worker, reintentos y continuaciones consumen
  `seleccionable_para_emision`;
- preflight agrupado al cumplir 90 días y guarda final antes del borde ARCA;
- cero operaciones, intentos, reservas y llamadas CAE ante un aborto previo;
- upgrade, rollback y reupgrade en SQLite y PostgreSQL; si existe evidencia WSFE
  nueva, el downgrade debe fallar cerrado.

El contrato completo vive en el
[`diseño PF-19D`](pf-19d-puntos-venta-authority-design.md).

## Smoke local de aplicación

1. iniciar backend, frontend y base según el setup vigente;
2. comprobar health y login con usuario sintético;
3. seleccionar emisor y recorrer la pantalla modificada;
4. confirmar que no hay errores inesperados en consola o logs;
5. verificar que no se creó estado fiscal ni se llamó a ARCA real;
6. detener el entorno y revisar artefactos temporales.

## Smoke posterior a despliegue

Sólo se ejecuta dentro de una operación productiva autorizada y coordinada por
`vps-admin`. El recorrido genérico incluye salud, login, emisor, worker, pools,
pantalla afectada, logs y servicios vecinos. No incluye emitir ni solicitar CAE
salvo autorización fiscal separada.

Consultar [`production-workflow.md`](production-workflow.md); la evidencia real
permanece fuera del repositorio.

La evidencia histórica retirada de este documento se conserva en
[`manual-qa-through-v0.3.2.md`](../project/history/manual-qa-through-v0.3.2.md).
