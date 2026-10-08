# SC-08 — intentos de acceso y recuperación asistida

Decisión autorizada por Santi el 08/10/2026 para el candidato v0.3.8. Riesgo:
Nivel 2, autenticación. No modifica política de contraseñas ni resuelve SC-11.

## Contrato

- Antes de consultas de usuario y bcrypt, reservar presupuesto por correo
  normalizado, origen y proceso. Usuarios inexistentes consumen el mismo
  presupuesto de intentos; capitalización y cambio de origen no eluden el
  límite por cuenta. Conservar búsqueda exacta y compatibilidad legacy.
- Ventanas de 60 segundos desde el primer intento: hasta 5 intentos fallidos
  o pendientes por cuenta, 30 solicitudes admitidas por origen y 60 totales.
  Los accesos correctos descuentan únicamente su reserva por cuenta; siguen
  consumiendo presupuesto de origen y total. Son parámetros de este contrato,
  no valores exigidos por OWASP.
- Como máximo 2 logins admitidos simultáneos. Bcrypt se ejecuta fuera del ciclo
  de eventos; una cancelación no libera capacidad mientras ese trabajo siga
  ejecutándose. No crear una cola de espera de logins.
- Responder `429` con `Retry-After` y una espera explícita en segundos. Los
  rechazos no prolongan la ventana. No bloquear permanentemente ni alterar
  el estado activo de una cuenta. Las sesiones existentes siguen disponibles.
- Estado efímero por aplicación, protegido frente a concurrencia y limitado a
  4096 claves con caducidad; no expulsar claves activas para admitir nuevas.
  Guardar huellas de cuenta/origen, nunca contraseñas ni tokens.

## Instalación y límites

El contrato operativo vigente usa un solo proceso Uvicorn. El presupuesto se
reinicia al reiniciar ese proceso y no coordina varias réplicas; ampliar el
runtime requiere diseñar el presupuesto compartido antes. No añadir Redis ni
una migración para este corte.

El origen es `request.client.host`, resuelto por el servidor ASGI; la aplicación
no interpreta `X-Forwarded-For` ni `X-Real-IP`. Sólo se deben confiar proxies
identificados por la configuración privada de la instalación. Cuando ASGI
ve únicamente el proxy, éste comparte el presupuesto de origen: la protección
por cuenta y total sigue activa, pero no distingue a cada cliente detrás de él.
Los usuarios de una oficina también pueden compartir el límite de 30 por minuto.

Una campaña sostenida puede consumir ventanas sucesivas e impedir temporalmente
un nuevo login, aun con la contraseña correcta. El límite reduce abuso y costo,
no acredita protección completa contra ataques distribuidos. Las pruebas deben
demostrar recuperación al cesar el abuso; no prometer acceso durante un ataque.

## Recuperación sin pérdida

El administrador conserva el restablecimiento en Usuarios. Si todos pierden el
acceso, el responsable con acceso autorizado a la instalación puede ejecutar
`python -m app.scripts.reset_user_password` en el entorno del backend, contra
la base existente. Pedir correo y nueva contraseña con confirmación oculta;
no aceptar la contraseña como argumento ni imprimirla en errores.

Modificar sólo el hash y `password_changed_at`, conservando identidad, nombre,
activación, rol, capacidad de editar emisores, asignaciones y datos fiscales.
No crear una cuenta si no existe; rechazar correos legacy ambiguos. Una cuenta
inactiva permanece inactiva. Usar transacción y conservar la revocación de tokens
anteriores. Una espera de login vigente expira automáticamente; el reset no
desactiva los límites de origen/total ni crea una excepción pública.

`create_admin_user` conserva su función de alta/promoción, que puede modificar
rol, activación y asignaciones. No sustituye a este comando de recuperación.
No restaurar ni recrear una base por una contraseña olvidada.

La recuperación autónoma «Olvidé mi contraseña» permanece como indicación en
el roadmap sin prioridad; canal verificado, códigos de un solo uso y diseño
posterior. No agregarla a esta release.

## Aceptación y recuperación del cambio

Probar usuarios existentes/inexistentes/inactivos, correos legacy, cambios de
origen, cabeceras falsificadas, varios usuarios de una oficina, límite total,
capacidad de memoria, ventanas y concurrencia/cancelaciones. Verificar que
un `429` no alcanza bcrypt y que la UI permite reintentar tras el error.
Ensayar reset de administrador y operador, cuenta ausente/ambigua, permisos
conservados, revocación y login con nueva contraseña después de la espera.
Usar datos sintéticos; nunca ensayar fuerza bruta contra cuentas productivas.

No hay DDL ni transformación de datos. Un rollback de código elimina el límite
de login, por lo que debe ser una decisión operativa explícita y proporcional.
El cambio de una contraseña no se revierte recuperando hashes antiguos.

Referencia: [OWASP, limitación de intentos de autenticación](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html#login-throttling).
