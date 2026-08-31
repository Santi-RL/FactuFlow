# QA manual reutilizable

Última revisión: 31/08/2026

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

- cambio explícito de emisor;
- recursos, permisos y respuestas tardías aislados;
- revocación durante una sesión;
- perfiles, certificados, clientes, puntos y reportes no se mezclan;
- mensajes identifican la acción sin revelar datos de otro emisor.

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

## Puntos de venta vigentes en v0.3.2

Hasta implementar PF-19D, verificar:

- importación de constancia válida con resumen claro;
- comprobación técnica previa a los selectores cuando corresponde;
- puntos frescos conservados si ARCA no responde;
- pendientes y desactualizados no seleccionables;
- estados normales `Listo para emitir` / `Web Services activo` y
  `No disponible en FactuFlow` / `Otro sistema`;
- errores con una acción concreta;
- usuario autorizado puede ejecutar `Comprobar con ARCA`;
- no se crean operaciones, intentos, reservas ni CAE ante un fallo preflight.

PF-19D cambiará la autoridad y el uso local. Su QA se ejecutará contra el
[`diseño aceptado`](pf-19d-puntos-venta-authority-design.md) cuando se implemente;
no debe presentarse hoy como funcionalidad disponible.

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
