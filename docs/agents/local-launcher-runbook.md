# Runbook del launcher local

Ultima actualizacion: 2026-05-22

Este runbook documenta la experiencia local Windows de FactuFlow. El objetivo es
que una persona administrativa no tecnica pueda abrir el sistema, entender si
esta listo y saber que hacer si una parte local no responde.

## Etapa 1 - Login con servidor local no disponible

Estado: implementado.

- La pantalla de login consulta `GET /api/health` antes de enviar credenciales.
- Si el servidor local no responde, no intenta iniciar sesion y muestra:
  `FactuFlow no está listo para iniciar sesión`.
- El mensaje guia al usuario con pasos concretos: click derecho en el icono de
  FactuFlow junto al reloj, elegir `Reiniciar servicios`, esperar a que el icono
  quede verde y presionar `Reintentar`. Si no ve el icono, debe abrir
  nuevamente `FactuFlow Local.vbs`.
- El boton `Reintentar` vuelve a chequear la conexion con el servidor local.
- Los errores de credenciales quedan separados de los errores de conexion.

QA manual:

1. Levantar solo el frontend.
2. Abrir `/login`.
3. Completar correo y contrasena.
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
- worker de lotes como señal pendiente de healthcheck dedicado
- ambiente ARCA y conexion ARCA
- certificado activo y vencimiento del emisor seleccionado
- aviso de backup no verificado mientras no exista señal automática
- guía rápida de soporte con próximos pasos seguros

La pantalla no debe exponer puertos, stack traces ni detalles tecnicos como
primer mensaje. Debe usar estados simples como `Correcto`,
`Necesita atencion` y `No disponible`, con una explicacion corta y un proximo
paso seguro. El runbook público sanitizado asociado está en
`docs/agents/support-runbook.md`.

## Etapa 3 - Integracion launcher/UI

Estado: pendiente.

Definir una integracion mas formal entre el launcher local y la UI web. Opciones
a evaluar:

- archivo local de estado generado por el launcher
- endpoint local de estado del launcher
- accion de reinicio de servicios desde una app empaquetada

Esta etapa no debe asumirse disponible hasta que exista packaging o un canal
seguro para controlar servicios locales desde la UI.
