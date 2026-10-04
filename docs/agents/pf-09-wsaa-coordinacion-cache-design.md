# PF-09 — coordinación WSAA y caché cifrada

Fecha: 03/10/2026.

Estado: planificación aceptada; implementación pendiente. P2 de confiabilidad,
Después 2; elevable ante un bloqueo operativo acreditado.

## Problema y resultado

El ensayo del cliente actual confirmó dos autenticaciones concurrentes ante una
caché vacía. El lock de `TokenCache` protege accesos individuales, no la secuencia
completa de obtener el ticket. La persistencia actual contiene Token/Sign en
texto legible, con protección por permisos.

Se busca una autenticación compartida por identidad cuando coinciden operaciones,
reutilización entre reinicios y persistencia cifrada, sin pasos nuevos del usuario.
La [validación de planificación](../project/analysis/confiabilidad-arca-roadmap.md)
no acredita indisponibilidad ni exposición productiva.

## Contrato aceptado

- Aislar por servicio, ambiente e identidad del certificado y respetar la
  representación autorizada. Conservar aislamiento entre emisores; un ticket
  válido para WSFE no sirve automáticamente para padrón.
- Coordinar cache miss y renovación como una operación completa. El segundo
  consumidor espera el resultado del primero y vuelve a comprobar su validez.
  Identidades distintas pueden trabajar concurrentemente.
- Cubrir API y worker/procesos que realmente comparten la instalación. Un
  `asyncio.Lock` no resuelve coordinación entre procesos; usar un mecanismo
  durable acotado o bloqueo de archivo adecuado al runtime, con expiración,
  recuperación del dueño caído y protección contra escritores antiguos.
  No incorporar Redis ni un nuevo servicio como requisito.
- Definir `force_new`, margen de expiración, cancelación, errores y política de
  retry. Un error «ya autenticado» sólo permite reutilizar un ticket válido,
  disponible y de la identidad correcta. Sin él, informar recuperación útil;
  no repetir logins a ciegas ni asumir credenciales a partir del mensaje.
- Evitar bloquear el event loop; mantener límites y timeouts. No mezclar el
  cambio con padrón, CAE, numeración o rotación general de certificados.

## Cifrado y recuperación

Cifrado autenticado con claves separadas por propósito, escritura atómica,
permisos restringidos y metadatos mínimos. Cerrar la gestión de clave antes de
implementar: provisionamiento local/VPS, separación del secreto JWT, backup,
restauración y rotación. No derivar una solución copiando sin revisión el esquema
del proyecto externo ni versionar secretos.

La transición desde la caché legible debe verificar identidad y vigencia,
escribir y comprobar la copia cifrada antes de retirar la anterior. No reutilizar
tickets incompletos, ajenos, corruptos o vencidos. El manejo de copias antiguas en
backups forma parte de privacidad y retención, no de una eliminación masiva.

Una caída o clave incorrecta no destruye certificados ni convierte una caché
ilegible en un ticket válido. Definir si corresponde autenticar de nuevo y cómo
tratar la negativa de ARCA cuando aún existe una sesión vigente. La recuperación
PF-11/PF-15 debe conocer qué material permite descifrar; automatizar todos los
backups no es dependencia de este corte.

## Dependencias y aceptación

La coordinación segura de sesiones es la base técnica del
[padrón de clientes/emisores](pf-18-09-padron-clientes-emisores-design.md).
La rotación de certificados y los contratos restantes PF-09/PF-12/PF-14 conservan
sus propios cortes; no se exige terminar una plataforma entera.

- Dos o más consumidores con caché vacía/vencida: una autenticación por identidad.
- Mismo CUIT con certificados distintos, servicios distintos y ambientes distintos.
- Dos procesos, caída del dueño, cancelación, renovación forzada y writer antiguo.
- Ticket vigente sin cargar WSDL; error de red/WSAA, ticket perdido y ya autenticado.
- Reinicio, corrupción, clave equivocada, rotación y restauración de copia cifrada;
  Token/Sign no legibles en archivo, logs ni errores.
- Completar checklist fiscal y definir mecanismo, clave, migración y rollback
  antes de codificar. Usar dobles; las pruebas no autentican en ARCA real.
