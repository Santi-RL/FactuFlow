# SC-11 — sesión vinculada a la credencial verificada

## Alcance e invariantes

Corte P1 de autenticación, nivel 2, autorizado el 10/10/2026. Un login que
verificó una contraseña anterior no debe conceder acceso después de un
restablecimiento concurrente. No modifica políticas de contraseñas, permisos,
asignaciones, recuperación asistida ni datos fiscales; no alcanza ARCA ni CAE.

Preservar presupuesto previo a bcrypt, cancelación segura de SC-08, cuentas
inactivas, búsquedas legacy de correo y revocación temporal vigente. Las sesiones
válidas anteriores al despliegue conservan su compatibilidad.

## Contrato

Capturar el hash exacto antes de verificar bcrypt. Después de verificar, releer
la cuenta desde la base: una credencial distinta o una cuenta eliminada producen
el mismo `401` genérico; una cuenta inactiva conserva `403`.

Cada nuevo token de login contiene `pwdv`, un HMAC-SHA256 del hash verificado con
la clave de firma y un prefijo de dominio exclusivo. No contiene la contraseña
ni su hash bcrypt. No requiere columnas, migraciones ni secretos nuevos.
Los controles de autenticación obligatorio y opcional comparan esa versión con
la credencial vigente, en tiempo constante. Un valor presente inválido se rechaza.

La relectura permite rechazar la carrera habitual antes de emitir el token.
Si el reset confirma después de esa relectura, el vínculo inmutable conserva
la credencial realmente verificada: el token deja de conceder acceso desde el
siguiente control backend aunque su `iat` sea posterior al reset. El orden o la
precisión de los relojes no pueden sustituir ese vínculo. `ultimo_login` es un
dato administrativo; una respuesta concurrente puede contener un token ya revocado.

Los tokens legacy sin `pwdv` conservan el control de `iat` contra
`password_changed_at` y su vencimiento. No se fuerza un cierre general de
sesiones. Una sesión legacy que ya atravesó esta carrera antes del despliegue
no puede distinguirse retrospectivamente de otra sesión válida con esos campos;
ante un incidente se usa el restablecimiento existente. El cierre cubre tokens
nuevos generados por este login, no acredita revisión ni despliegue de producción.

## Pruebas y recuperación

- SQLite sintética: reset administrativo y por consola durante bcrypt, login
  con la contraseña nueva, ausencia de divulgación, cuenta desactivada y permisos.
- Ambos controles de autenticación: versión equivocada o malformada, token nuevo
  revocado aun con `iat` posterior y sesiones legacy válidas/revocadas.
- PostgreSQL descartable: sesiones independientes, reset confirmado durante
  bcrypt y reset confirmado después de la relectura/commit del login. Incluir
  reset con timestamp asignado antes del login y transacción todavía abierta.
- Regresión de autenticación, SC-08, administración y suite completa del backend.

No hay transformación de datos que revertir. Una reversión de código elimina la
comprobación adicional y reabre SC-11; preferir una corrección hacia adelante.
Conservar los procedimientos de reset y los datos de la instalación.
