# Runbook del launcher local

Última actualización: 2026-07-10

Este runbook documenta la experiencia local Windows de FactuFlow. El objetivo es
que una persona administrativa no técnica pueda abrir el sistema, entender si
está listo y saber qué hacer si una parte local no responde.

## Etapa 1 - Login con servidor local no disponible

Estado: implementado.

- La pantalla de login consulta `GET /api/health` antes de enviar credenciales.
- Si el servidor local no responde, no intenta iniciar sesión y muestra:
  `FactuFlow no está listo para iniciar sesión`.
- El mensaje guía al usuario con pasos concretos según el acceso usado. Si usó
  el acceso directo del escritorio que ejecuta `scripts\restart-local-dev.ps1`,
  debe relanzarlo y esperar `Backend OK` y `Frontend OK`; ese flujo no muestra
  ícono de bandeja. Si usó `FactuFlow Local.vbs`, puede hacer clic derecho en el
  ícono de FactuFlow junto al reloj y elegir `Reiniciar servicios`.
- El botón `Reintentar` vuelve a chequear la conexión con el servidor local.
- Los errores de credenciales quedan separados de los errores de conexión.

QA manual:

1. Levantar solo el frontend.
2. Abrir `/login`.
3. Completar correo y contraseña.
4. Presionar `Ingresar`.
5. Confirmar que aparece el mensaje de servidor local no disponible.
6. Levantar backend.
7. Presionar `Reintentar` y confirmar que el aviso desaparece.

## Etapa 2 - Estado del sistema dentro de la UI

Estado: primer corte implementado.

La pantalla `Sistema > Estado` dentro del frontend ya muestra, en lenguaje
administrativo, parte del diagnóstico mínimo definido en
`docs/agents/operational-observability.md`:

- servidor de FactuFlow
- base de datos
- worker de lotes mediante `GET /api/health/worker` para administradores
- estado sanitizado de los pools API y worker
- ambiente ARCA y conexión ARCA
- certificado activo y vencimiento del emisor seleccionado
- aviso de backup no verificado mientras no exista señal automática
- guía rápida de soporte con próximos pasos seguros

La pantalla no debe exponer puertos, stack traces, DSN, credenciales, rutas
privadas ni errores internos crudos. Debe usar estados simples como `Correcto`,
`Necesita atención` y `No disponible`, con una explicación corta y un próximo
paso seguro.

En el entorno local SQLite, API y worker comparten un único engine por diseño;
`separated=false` con `separation_required=false` no es degradación. Si la base
devuelve `503`, esperar unos segundos y reintentar el estado; si había una
emisión en curso, detenerse y seguir el runbook antes de repetirla. El runbook
público sanitizado asociado está en `docs/agents/support-runbook.md`.

## Etapa 3 - Integración launcher/UI

Estado: pendiente.

Definir una integración mas formal entre el launcher local y la UI web. Opciones
a evaluar:

- archivo local de estado generado por el launcher
- endpoint local de estado del launcher
- acción de reinicio de servicios desde una app empaquetada

Esta etapa no debe asumirse disponible hasta que exista packaging o un canal
seguro para controlar servicios locales desde la UI.
