# Runbook de diagnóstico operativo

Última actualización: 2026-06-28

Estado: primer corte público y sanitizado.

Este runbook guía diagnósticos operativos de FactuFlow sin exponer datos
privados. Los datos concretos de una instalación real, como dominio, IP, usuario
SSH, rutas del servidor, comandos exactos, backups, certificados, CUITs, CAEs,
logs y comprobantes, deben quedar en documentación privada del entorno.

## Principios

- Empezar por `Sistema > Estado` y `Sistema > Almacenamiento` cuando la UI esté
  disponible.
- Registrar siempre el emisor activo, el usuario, el lote o comprobante afectado
  y el momento aproximado, sin copiar datos privados al repositorio.
- Si pudo existir una llamada a ARCA, no reintentar automáticamente. Primero
  determinar si ARCA autorizó o no el comprobante.
- Usar consultas ARCA seguras de solo lectura, como `FECompUltimoAutorizado` o
  `FECompConsultar`, solo cuando corresponda y con decisión explícita.
- Separar evidencia privada de resumen público: el repo versiona método y estado
  sanitizado, no evidencia operativa real.
- En VPS, no cambiar código manualmente. Si el diagnóstico requiere un fix,
  llevarlo al repo local, probarlo, commitearlo y desplegarlo de forma
  controlada.

## Triaje inicial

1. Confirmar entorno: local, QA, VPS productivo o copia de restauración.
2. Confirmar si hay una operación fiscal en curso o reciente.
3. Identificar el emisor activo sin copiar CUIT completo.
4. Identificar el recurso afectado: login, certificado, lote, comprobante,
   PDF, almacenamiento, backup o despliegue.
5. Revisar `Sistema > Estado` si la UI responde.
6. Revisar logs privados solo desde el entorno correspondiente.
7. Clasificar el riesgo:
   - sin riesgo fiscal: login, pantalla caída antes de operar, almacenamiento.
   - riesgo fiscal bajo: certificado o ARCA no disponibles antes de emitir.
   - riesgo fiscal alto: lote parcial, timeout durante emisión, fallo post-CAE,
     comprobante incierto o reconciliación pendiente.

## Caso 1: la aplicación no inicia o no responde

Qué revisar:

- En local, el icono del launcher junto al reloj y la pantalla de login.
- En la UI, `Sistema > Estado`: `Aplicación` y `Base de datos`.
- En VPS, la documentación privada del servidor y sus healthchecks.

Próximo paso seguro:

- En local, usar `Reiniciar servicios` desde el launcher si está disponible.
- Si el launcher no aparece, volver a abrir `FactuFlow Local.vbs`.
- En VPS, usar el runbook privado del servidor y registrar el commit desplegado.

Detenerse si:

- Había una emisión o lote en curso cuando la aplicación dejó de responder.
- El usuario no sabe si la acción llegó a ARCA.

En ese caso, pasar al caso de incertidumbre post-ARCA antes de repetir la
operación.

## Caso 2: no se puede iniciar sesión

Qué revisar:

- Si el login muestra servidor no disponible o credenciales incorrectas.
- Si `GET /api/health` responde desde el entorno correspondiente.
- Si el usuario está activo o requiere reseteo por un administrador.

Próximo paso seguro:

- Resolver primero disponibilidad de backend/base.
- Si el servidor responde y el problema es de credenciales, usar la pantalla
  `Usuarios` con un administrador activo.
- Para recuperar el primer administrador, usar el comando administrativo
  documentado en entorno privado o local seguro.

Detenerse si:

- El problema aparece después de un despliegue o migración.
- Hay señales de base de datos no disponible.

No editar usuarios directamente en una base productiva sin backup y sin dejar
evidencia privada del motivo.

## Caso 3: ARCA no responde

Qué revisar:

- `Sistema > Estado`: ambiente ARCA y `Conexión ARCA`.
- Si el certificado del emisor activo está vigente.
- Si el error ocurrió antes de emitir o durante una operación fiscal.

Próximo paso seguro:

- Si no había emisión en curso, probar conexión manualmente desde la UI.
- Si el error ocurrió durante una emisión, revisar intentos fiscales y logs
  privados antes de cualquier reintento.
- Para numeración o comprobantes inciertos, usar consultas ARCA seguras de solo
  lectura.

Detenerse si:

- La UI no confirma claramente si ARCA fue llamada.
- El lote o comprobante quedó parcial, fallido después de CAE o en
  reconciliación.

## Caso 4: certificado vencido o no autorizado

Qué revisar:

- `Sistema > Estado`: `Certificado del emisor`.
- Listado de certificados del emisor activo.
- Autorización WSFE en ARCA para el certificado y CUIT representado.

Próximo paso seguro:

- Renovar o cargar un certificado usando el wizard existente.
- Verificar autorización WSFE antes de emitir.
- Ejecutar `Probar conexión` solo por acción explícita del usuario.

Detenerse si:

- El certificado activo no coincide con el emisor activo.
- El certificado está vencido, falta la clave privada o ARCA informa no
  autorizado.

## Caso 5: lote trabado, parcial o en reconciliación

Qué revisar:

- Estado visible del lote en `/comprobantes/lotes`.
- Si está `en_cola`, `procesando`, `completado parcial`, `fallido` o
  `requiere reconciliación`.
- Detalle de grupos, emitidos, fallidos, pendientes y mensajes visibles.
- Logs privados del backend o worker alrededor del horario del lote.

Próximo paso seguro:

- Si el lote está en espera normal, no intervenir hasta confirmar si el worker
  sigue activo.
- Si hay errores de archivo o validación, corregir datos y validar de nuevo
  solo cuando no exista incertidumbre fiscal.
- Si requiere reconciliación, usar el flujo de reconciliación y consultas ARCA
  seguras antes de reintentar.

Detenerse si:

- Algún grupo pudo haber solicitado CAE y no se sabe si ARCA autorizó.
- Hay comprobantes parciales o intentos fiscales inciertos.

Regla crítica: no reintentar automáticamente un lote con incertidumbre
post-ARCA.

## Caso 6: comprobante con incertidumbre post-ARCA

Qué revisar:

- Emisor activo, punto de venta, tipo de comprobante y fecha fiscal.
- Intento fiscal asociado e idempotencia.
- Último estado local del comprobante o grupo de lote.
- Logs privados del horario exacto.

Próximo paso seguro:

- Consultar ARCA en modo solo lectura con el identificador fiscal necesario.
- Comparar resultado ARCA contra estado local: número, tipo, punto de venta,
  fecha, total y CAE cuando exista.
- Clasificar el caso antes de cualquier acción: autorizado y no persistido,
  rechazado antes de CAE, timeout sin autorización confirmada o inconsistencia
  local.

Detenerse si:

- No se puede consultar ARCA.
- Los datos locales no alcanzan para identificar el comprobante con seguridad.
- El resultado ARCA no coincide con los datos esperados.

## Caso 7: almacenamiento, ZIPs y limpieza

Qué revisar:

- `Sistema > Almacenamiento`: uso medido, recuperable, categorías y emisores.
- Lotes compactables, logs antiguos, temporales y certificados huérfanos.
- Si existe backup reciente fuera del VPS cuando se trabaja en producción.

Próximo paso seguro:

- Preparar ZIP desde la UI.
- Descargar el resguardo a la PC del usuario.
- Verificar que el archivo quedó disponible localmente.
- Recién después confirmar `Ya lo descargué`.

Detenerse si:

- No se descargó el resguardo.
- El archivo corresponde a datos reales y no existe backup privado reciente.
- El elemento a limpiar no fue listado por el gestor de almacenamiento.

No limpiar rutas manuales ni artefactos fuera de carpetas administradas por
FactuFlow.

## Caso 8: backup o restauración requerida

Qué revisar:

- Última evidencia privada de backup.
- Si el backup incluye base, certificados, claves y configuración privada.
- Si la clave real del backup cifrado está guardada fuera de Git y fuera del
  VPS.
- Si ya existe una restauración de prueba documentada.

Próximo paso seguro:

- No improvisar restauración sobre producción.
- Restaurar primero en entorno controlado cuando sea posible.
- Validar que la aplicación levanta, permite login y puede consultar datos sin
  emitir.

Detenerse si:

- Falta la clave de cifrado.
- El backup no incluye certificados o configuración privada necesaria.
- La restauración requiere borrar o pisar un entorno productivo activo.

## Evidencia privada mínima

Para diagnósticos reales, registrar en documentación privada:

- fecha y hora aproximada
- entorno y commit desplegado
- usuario operador o rol
- emisor activo redactado
- lote, comprobante o recurso afectado
- acción iniciada
- estado antes y después
- si ARCA fue llamada o no
- resultado de consultas de solo lectura si se usaron
- decisión tomada y responsable

En documentación pública, registrar solo el resumen sanitizado y la mejora
general aplicada.

## Criterio de cierre de un diagnóstico

Un diagnóstico operativo queda cerrado cuando se puede responder:

1. Qué pasó.
2. Qué emisor y recurso estaban involucrados.
3. Si ARCA fue llamada.
4. Si existe incertidumbre fiscal.
5. Qué estado tiene ahora el sistema.
6. Qué acción se tomó o se decidió no tomar.
7. Dónde quedó la evidencia privada.
