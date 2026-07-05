# QA manual

Última actualización: 2026-07-05

Este archivo registra el avance real de la prueba manual de la interfaz. Si una sesión queda a mitad de camino, se retoma desde acá.

## Preparación

Levantar el proyecto con la UX local recomendada para Windows:

```bash
.\FactuFlow Local.vbs
```

El launcher queda en el tray de Windows sin dejar una ventana de PowerShell
abierta y muestra estado verde, amarillo o rojo. Desde el menú del ícono se
puede abrir FactuFlow, consultar `Estado del sistema`, reiniciar servicios,
detener servicios y abrir logs.

Camino técnico alternativo:

```bash
powershell -ExecutionPolicy Bypass -File .\run-local.ps1
```

También puede existir un acceso directo de escritorio que ejecute
`scripts\restart-local-dev.ps1`. Ese flujo muestra `Backend OK` y `Frontend OK`
en PowerShell, pero no muestra ícono de bandeja junto al reloj.

Entornos esperados:
- Frontend: `http://localhost:8080`
- Backend: `http://localhost:8000`

Logs del launcher local:
- `.tmp/local-launcher/launcher.log`
- `.tmp/local-launcher/backend.log`
- `.tmp/local-launcher/frontend.log`

## Criterio transversal de recursos

La visión vigente asume instalaciones locales o VPS pequeños. En cualquier QA
que toque lotes, PDFs, ZIPs, archivos observados, reportes o procesos largos,
verificar que la solución no dependa de almacenar artefactos no vitales de forma
permanente en el servidor. Los archivos descargables deben generarse bajo
demanda, descargarse a la PC del usuario y limpiarse cuando cumplan su propósito
operativo.

En el gestor de almacenamiento, la QA debe verificar que un administrador pueda
ver uso total, desglose por emisor y desglose por tipo de dato sin exponer
nombres de clientes, CUITs, CAEs, PDFs privados ni rutas internas sensibles.

Estado del sistema implementado como primer corte:

1. Iniciar sesión con un usuario administrador.
2. Verificar que el menú `Sistema` aparece y que un usuario común no lo ve.
3. Abrir `Sistema > Estado`.
4. Confirmar que se muestran `Aplicación`, `Base de datos`, `Certificado del
   emisor`, `Conexión ARCA`, `Almacenamiento`, `Worker de lotes`, `Logs de
   soporte` y `Último backup`.
5. Confirmar que la carga de la pantalla no dispara la prueba externa de ARCA.
   La acción `Probar conexión` debe ejecutarse solo por decisión explícita del
   usuario.
6. Confirmar que las señales no instrumentadas todavía quedan explicadas como
   pendientes: healthcheck de worker, evidencia automática de backup y acceso a
   logs según entorno.
7. Confirmar que los estados usan lenguaje simple: `Correcto`, `Necesita
   atención` y `No disponible`.
8. Confirmar que `Guía rápida de soporte` muestra casos de aplicación/base,
   ARCA/certificado, lote detenido o incierto y almacenamiento/backup, con un
   próximo paso seguro y una condición para detenerse.
9. Confirmar que `Ficha para soporte` muestra datos mínimos para diagnóstico:
   entorno y versión, emisor activo, recurso afectado, estado visible, ARCA y
   evidencia privada, sin pedir copiar CUIT completo en documentación pública.

Gestor de almacenamiento implementado:

1. Iniciar sesión con un usuario administrador.
2. Verificar que el menú `Sistema` aparece y que un usuario común no lo ve.
3. Abrir `Sistema > Almacenamiento`.
4. Confirmar que se muestran uso medido, recuperable, límite configurado,
   espacio libre de disco, categorías y uso por emisor.
5. Confirmar que las etiquetas de emisor no exponen CUIT completo, clientes,
   CAEs ni rutas internas.
6. Seleccionar un lote cerrado compactable, preparar el ZIP, descargarlo a la
   PC y recién después confirmar `Ya lo descargué`.
7. Verificar que el lote queda compactado: conserva resumen, grupos,
   comprobantes, totales y auditoría, pero deja de tener filas originales para
   regenerar observado.
8. Repetir con logs antiguos o temporales de prueba ubicados en rutas
   administradas por FactuFlow.
9. Verificar que el log activo no aparece como limpiable.
10. Verificar que certificados activos o referenciados no aparecen como
    huérfanos; si se usa un archivo huérfano de prueba gestionado por
    FactuFlow, confirmar que la limpieza no toca archivos manuales ni rutas
    externas.

Caso local con frontend activo y backend caido:

1. Levantar solo el frontend.
2. Abrir `/login`.
3. Completar correo y contrasena.
4. Presionar `Ingresar`.
5. Verificar que aparece `FactuFlow no está listo para iniciar sesión`.
6. Levantar backend y presionar `Reintentar`.
7. Confirmar que el aviso desaparece y el login vuelve a operar.

## Acceso local usado

Solo para entorno local de desarrollo:
- Usuario QA automatizable: definido en la base local privada.
- Contrasena QA local: definida en la base local privada.

Para crear o promover un usuario propietario local, usar:

```bash
cd backend
.venv\Scripts\python.exe -m app.scripts.create_admin_user
```

Si deja de funcionar, validar la base local o resetear la clave con el mismo comando.
Con la aplicación ya configurada, las altas habituales se hacen desde
`Usuarios` con un usuario administrador.

## Recorrido ejecutado y validado

### Sistema > Estado - ficha para soporte 2026-06-29

- Alcance revisado: nueva sección `Ficha para soporte` dentro de
  `Sistema > Estado`, con datos mínimos para diagnosticar incidentes sin copiar
  evidencia privada al repositorio: entorno y versión, emisor activo, recurso
  afectado, estado visible, acción ARCA y evidencia privada.
- El cambio es frontend-only: no agrega endpoints, no dispara llamadas ARCA
  automáticas y no toca backend, emisión, lotes fiscales, servicios, stores,
  rutas ni contratos.
- La verificación automatizada asociada cubre que la ficha sea visible y que
  `Sistema > Estado` siga sin ejecutar `Probar conexión` automáticamente.

### Sistema > Estado - guía rápida de soporte 2026-06-28

- Alcance revisado: nueva sección `Guía rápida de soporte` dentro de
  `Sistema > Estado`, con pasos seguros para aplicación/base no disponible,
  ARCA o certificado con error, lote detenido o incierto, y almacenamiento o
  backup pendiente.
- El cambio es frontend-only: no agrega endpoints, no dispara llamadas ARCA
  automáticas y no toca backend, emisión, servicios, stores, rutas ni contratos.
- La verificación automatizada asociada cubre que la guía sea visible y que
  `Sistema > Estado` siga sin ejecutar `Probar conexión` automáticamente.

### Gestor de almacenamiento - QA visual local 2026-06-27

- Alcance revisado: `Sistema > Almacenamiento`, incluyendo métricas de uso,
  categorías, lotes compactables, archivos administrados, uso por emisor,
  preparación de ZIP, descarga simulada y confirmación `Ya lo descargué`.
- La prueba visual usó frontend local real con API mockeada, sesión ficticia,
  emisores ficticios y artefactos ficticios. No se usaron credenciales reales,
  datos reales, CUITs reales, CAEs, PDFs privados, Excels privados, logs reales
  ni rutas internas sensibles.
- El E2E permanente verifica que el contenido principal del gestor no exponga
  CUIT completo ni rutas internas tipo `C:\` o `/var/`, y que el flujo de
  resguardo permita preparar ZIP, descargar y habilitar la liberación recién
  después de la descarga.
- Capturas privadas:
  `private/brand-lab/exports/almacenamiento-qa-2026-06-27/`. El smoke verificó
  pantalla principal, resguardo preparado y vista mobile con dimensiones y
  variedad de píxeles suficientes para descartar una pantalla en blanco.
- Esta QA no reemplaza la validación pendiente sobre VPS con datos de prueba
  controlados; solo cierra una prevalidación local segura de UI y flujo.

### Rediseño UX de carga masiva - Corte 4 2026-06-27

- Alcance revisado: navegación compacta de `Lotes recientes` en
  `/comprobantes/lotes`, con estado, fecha, métrica principal y lote activo
  resaltado.
- La prueba visual usó frontend local real en
  `http://127.0.0.1:8080/comprobantes/lotes` con API mockeada, sesión ficticia,
  emisor ficticio, punto de venta ficticio y lotes ficticios en estados
  `validado` y `con_errores`. No se usaron credenciales reales, datos reales,
  Exceles privados, CAEs, CUITs reales ni llamadas ARCA.
- Capturas privadas:
  `private/brand-lab/exports/lotes-ux-corte-4-2026-06-27/`. El smoke verificó
  lista compacta en desktop/mobile, ausencia de contadores densos y capturas con
  dimensiones y variedad de píxeles suficientes para descartar una pantalla en
  blanco.
- Resultado funcional: la selección de un lote reciente conserva el mismo flujo
  de carga de detalle y el refresco de lista sigue usando la acción existente.
- Verificación automatizada asociada: `git diff --check`, `npm run lint:check`,
  `npm run type-check`, `npm run build`, `npm run test:unit`,
  `npm run test:e2e -- --project=chromium` y test unitario enfocado de
  `LotesComprobantesView` quedaron OK.

### Rediseño UX de carga masiva - Corte 3 2026-06-27

- Alcance revisado: modo `Resolver pendientes del lote` en
  `/comprobantes/lotes`, con `Reintentar fallidos`, `Descartar visibles` y
  `Reconciliar ARCA Web` agrupados en un panel desplegable.
- La prueba visual usó frontend local real en
  `http://127.0.0.1:8080/comprobantes/lotes` con API mockeada, sesión ficticia,
  emisor ficticio, punto de venta ficticio y un lote ficticio en estado
  `requiere_reconciliacion`. No se usaron credenciales reales, datos reales,
  Exceles privados, CAEs, CUITs reales ni llamadas ARCA.
- Capturas privadas:
  `private/brand-lab/exports/lotes-ux-corte-3-2026-06-27/`. El smoke verificó
  panel cerrado, panel abierto, acciones deshabilitadas para lote incierto y
  capturas con dimensiones y variedad de píxeles suficientes para descartar una
  pantalla en blanco.
- Resultado funcional: las acciones sensibles conservan handlers,
  confirmaciones y condiciones existentes. Las acciones sobre comprobantes
  visibles siguen bloqueadas hasta abrir el detalle de comprobantes.
- Verificación automatizada asociada: `git diff --check`, `npm run lint:check`,
  `npm run type-check`, `npm run build`, `npm run test:unit`,
  `npm run test:e2e -- --project=chromium` y test unitario enfocado de
  `LotesComprobantesView` quedaron OK.

### Rediseño UX de carga masiva - Corte 2 2026-06-27

- Alcance revisado: lote activo en `/comprobantes/lotes`, totales listos para
  emitir, avance del lote, siguiente acción, resumen operativo plegable y
  detalle de comprobantes plegable.
- La prueba visual usó frontend local real en
  `http://127.0.0.1:8080/comprobantes/lotes` con API mockeada, sesión ficticia,
  emisor ficticio, punto de venta ficticio y lotes ficticios en estados
  `validado`, `con_errores` y `procesando`. No se usaron credenciales reales,
  datos reales, Exceles privados, CAEs, CUITs reales ni llamadas ARCA.
- Capturas privadas:
  `private/brand-lab/exports/lotes-ux-corte-2-2026-06-27/`. El smoke verificó
  que existen tres capturas, tienen tamaño suficiente y no quedaron vacías.
- Resultado funcional: las acciones sensibles del lote conservan los mismos
  handlers y confirmaciones. Las acciones sobre comprobantes visibles quedan
  disponibles solo con el detalle de comprobantes abierto; el cambio reduce ruido
  visual y prioriza el resumen del lote activo.
- Verificación automatizada asociada: `git diff --check`, `npm run lint:check`,
  `npm run type-check`, `npm run build`, `npm run test:unit`,
  `npm run test:e2e -- --project=chromium` y test unitario enfocado de
  `LotesComprobantesView` quedaron OK.

### Rediseño UX de carga masiva - Corte 1 2026-06-27

- Alcance revisado: `/comprobantes/lotes`, guía rápida compacta, guía
  desplegable, carga de archivo, configuración fiscal previa a validar,
  checklist de requisitos y acción final `Validar lote`.
- La prueba visual usó frontend local real en
  `http://127.0.0.1:8080/comprobantes/lotes` con API mockeada, sesión ficticia,
  emisor ficticio, punto de venta ficticio, formato ficticio y lote ficticio.
  No se usaron credenciales reales, datos reales, Exceles privados, CAEs, CUITs
  reales ni llamadas ARCA.
- Capturas privadas:
  `private/brand-lab/exports/lotes-ux-corte-1-2026-06-27/`. El smoke verificó
  que las capturas existen, tienen tamaño suficiente y no quedaron vacías.
- Resultado funcional: el botón final `Validar lote` queda habilitado cuando el
  checklist está completo y dispara el mismo servicio de validación existente.
  Después de validar, la vista carga el resumen ficticio del lote sin cambiar
  contratos.
- Verificación automatizada asociada: test unitario enfocado de
  `LotesComprobantesView`, `npm run lint:check`, `npm run type-check`,
  `npm run build` y `npm run test:unit` quedaron OK.

### Diagnóstico UX de carga masiva 2026-06-26

- Alcance revisado: `/comprobantes/lotes`, incluyendo carga de archivo,
  formato detectado, configuración fiscal previa a validar, lote validado,
  acciones de emisión, reconciliación y lotes recientes.
- Se usó frontend local real en `http://127.0.0.1:8080/comprobantes/lotes` con
  API mockeada, sesión ficticia y datos sanitizados. No se usaron credenciales
  reales, datos reales, Exceles privados, CAEs, CUITs reales ni llamadas ARCA.
- Capturas privadas: `private/brand-lab/exports/lotes-ux-audit-2026-06-26/`.
  Se verificó que existen, tienen dimensiones esperadas y no están vacías; el
  visor local de imágenes siguió bloqueado por ACL para `private/`.
- Resultado: diagnóstico documentado en
  `docs/agents/lotes-ux-redesign.md`. No se implementaron cambios de UI ni se
  tocó backend, ARCA, emisión, servicios, stores, rutas o contratos.

### Estado del sistema - primer corte operativo 2026-06-25

- Alcance revisado: pestaña `Sistema > Estado`, cards de estado general, última
  actualización y ambiente ARCA, lista de señales operativas, acción manual
  `Probar conexión` y pestaña `Almacenamiento` conservada.
- Se usaron servicios existentes del frontend para consultar API, base,
  certificado local del emisor activo y resumen de almacenamiento. No se agregó
  ni modificó backend.
- La prueba externa de ARCA no se ejecuta al cargar la pantalla; queda detrás
  del botón manual `Probar conexión`.
- Verificación automatizada asociada: test unitario de `SistemaView` cubre que
  la pestaña de estado no llama a ARCA automáticamente y que el flujo de
  resguardo de almacenamiento sigue funcionando al entrar en la pestaña
  `Almacenamiento`. También quedaron OK `git diff --check`, `npm run
  lint:check`, `npm run type-check`, `npm run build` y `npm run test:unit`
  (64 tests). No se repitió E2E en este corte.

### Checkpoint visual v01 instalable en producción - cierre 2026-06-24

- Alcance consolidado: shell común, componentes base/comunes, login/setup,
  dashboard, clientes, usuarios, reportes y certificados/listado/wizard.
- Controles de cierre: barrido estático sin hardcodes visuales bloqueantes en el
  alcance, revisión por agentes sobre documentación y frontend, aplicación local
  levantada en `http://localhost:8080` para inspección visual del usuario,
  `git diff --check` OK, `npm run lint:check` OK, `npm run type-check` OK,
  `npm run build` OK, `npm run test:unit` OK (63 tests) y
  `npm run test:e2e -- --reporter=list` OK (31 tests en Chromium desktop).
- El cierre usó datos ficticios, mocks locales o revisión visual segura. No se
  usaron datos reales nuevos, no se llamó a ARCA, no se verificaron certificados
  reales, no se solicitó CAE y no se tocó backend.
- Las capturas privadas de microcortes permanecen en
  `private/brand-lab/exports`, fuera de Git. Este cierre no copia evidencia
  privada a documentación versionada.

### Integración visual controlada - verificación del wizard de certificados 2026-06-24

- Alcance revisado: estado inicial `Probá la conexión`, acción `Probar conexión`, resultado `Conexión exitosa`, panel `Estado de servidores ARCA`, resultado `No se pudo conectar`, posibles soluciones y navegación `Anterior`/`Finalizar` en `WizardStep5Verificar`.
- Se usó frontend local en `http://127.0.0.1:5173` con sesión ficticia, empresa ficticia y respuestas API simuladas. `POST /api/certificados/generar-csr` y `POST /api/certificados/subir-certificado` respondieron datos ficticios solo para avanzar hasta el paso 6. `POST /api/certificados/verificar-conexion/101` respondió una verificación ficticia exitosa y una fallida. No se usaron datos reales, no se llamó a ARCA, no se probó ningún certificado real y no se tocó backend.
- Capturas sanitizadas:
  - `private/brand-lab/exports/corte-certificados-wizard-verificar-inicial-desktop.png`
  - `private/brand-lab/exports/corte-certificados-wizard-verificar-exito-desktop.png`
  - `private/brand-lab/exports/corte-certificados-wizard-verificar-error-desktop.png`
  - `private/brand-lab/exports/corte-certificados-wizard-verificar-exito-mobile.png`
- Controles realizados: Playwright verificó avance hasta el paso 6, ausencia de `Finalizar` antes de probar conexión, aparición de resultado exitoso mockeado, botón `Finalizar` habilitado tras éxito, aparición del estado fallido mockeado, ausencia de `Finalizar` tras error, ausencia de errores de consola y ausencia de requests API no mockeadas. Se verificó por script que las capturas existen, tienen dimensiones esperadas y no están vacías; no hubo inspección visual manual directa por ACL de `private/`.
- Verificación automatizada asociada: `git diff --check` OK, `npm run lint:check` OK, `npm run type-check` OK, `npm run build` OK y `npm run test:unit` OK (63 tests).

### Integración visual controlada - autorización WSFE del wizard de certificados 2026-06-24

- Alcance revisado: instrucciones para autorizar WSFE, acción `Ir al portal de ARCA`, checkbox `Ya autoricé el servicio...` y navegación `Anterior`/`Siguiente` en `WizardStep5AutorizarServicio`.
- Se usó frontend local en `http://127.0.0.1:5173` con sesión ficticia, empresa ficticia y respuestas API simuladas. `POST /api/certificados/generar-csr` y `POST /api/certificados/subir-certificado` respondieron datos ficticios solo para avanzar hasta el paso 5. No se usaron datos reales, no se abrió el portal externo, no se llamó a ARCA, no se autorizó WSFE real y no se tocó backend.
- Capturas sanitizadas:
  - `private/brand-lab/exports/corte-certificados-wizard-autorizar-wsfe-desktop.png`
  - `private/brand-lab/exports/corte-certificados-wizard-autorizar-wsfe-confirmado-desktop.png`
  - `private/brand-lab/exports/corte-certificados-wizard-autorizar-wsfe-mobile.png`
- Controles realizados: Playwright verificó avance hasta el paso 5, presencia de instrucciones y acción del portal, enlace ARCA con `target="_blank"` y `rel="noopener noreferrer"`, `Siguiente` deshabilitado antes de confirmar, habilitación después de marcar autorización, ausencia de errores de consola y ausencia de requests API no mockeadas. Se verificó por script que las capturas existen, tienen dimensiones esperadas y no están vacías; no hubo inspección visual manual directa por ACL de `private/`.
- Verificación automatizada asociada: `git diff --check` OK, `npm run lint:check` OK, `npm run type-check` OK, `npm run build` OK y `npm run test:unit` OK (63 tests).

### Integración visual controlada - certificado cargado del wizard 2026-06-23

- Alcance revisado: estado `Certificado cargado correctamente`, panel `Información del certificado`, CUIT, fechas, días restantes y navegación `Siguiente` en `WizardStep4SubirCert`.
- Se usó frontend local en `http://127.0.0.1:5173` con sesión ficticia, empresa ficticia y respuestas API simuladas. El endpoint `POST /api/certificados/generar-csr` respondió un CSR ficticio para avanzar y `POST /api/certificados/subir-certificado` respondió un certificado ficticio. No se usaron datos reales, claves reales ni certificados reales; no se llamó a ARCA y no se tocó backend.
- Capturas sanitizadas:
  - `private/brand-lab/exports/corte-certificados-wizard-subir-cert-cargado-desktop.png`
  - `private/brand-lab/exports/corte-certificados-wizard-subir-cert-cargado-mobile.png`
- Controles realizados: Playwright verificó avance hasta el paso 4, carga de archivo `.crt` ficticio contra endpoint mockeado, aparición del estado de éxito, datos de certificado ficticio, botón `Siguiente` habilitado, ausencia de errores de consola y ausencia de requests API no mockeadas. Se verificó por script que las capturas existen, tienen dimensiones esperadas y no están vacías; no hubo inspección visual manual directa por ACL de `private/`.
- Verificación automatizada asociada: `git diff --check` OK, `npm run lint:check` OK, `npm run type-check` OK, `npm run build` OK y `npm run test:unit` OK (63 tests).

### Integración visual controlada - carga inicial de certificado 2026-06-22

- Alcance revisado: encabezado `Subí tu certificado`, alerta `Usando clave privada`, dropzone de archivos `.crt/.cer/.pem`, estado drag activo, spinner de validación y navegación `Anterior` en `WizardStep4SubirCert`.
- Se usó frontend local en `http://127.0.0.1:5173` con sesión ficticia, empresa ficticia y respuestas API simuladas. El endpoint `POST /api/certificados/generar-csr` respondió un CSR ficticio solo para avanzar hasta el paso 4. No se usaron datos reales, no se seleccionó archivo, no se subió certificado, no se llamó a ARCA, no se cargaron certificados y no se tocó backend.
- Capturas sanitizadas:
  - `private/brand-lab/exports/corte-certificados-wizard-subir-cert-inicial-desktop.png`
  - `private/brand-lab/exports/corte-certificados-wizard-subir-cert-drag-desktop.png`
  - `private/brand-lab/exports/corte-certificados-wizard-subir-cert-inicial-mobile.png`
- Controles realizados: Playwright verificó avance hasta el paso 4, presencia de clave privada ficticia, ausencia del botón `Siguiente` antes de subir certificado, estado drag activo, ausencia de errores de consola y ausencia de requests API no mockeadas. Se verificó por script que las capturas existen, tienen dimensiones esperadas y no están vacías; no hubo inspección visual manual directa por ACL de `private/`.
- Verificación automatizada asociada: `git diff --check` OK, `npm run lint:check` OK, `npm run type-check` OK, `npm run build` OK y `npm run test:unit` OK (63 tests).

### Integración visual controlada - portal ARCA del wizard de certificados 2026-06-22

- Alcance revisado: instrucciones del portal ARCA, acción `Ir al portal de ARCA`, ayuda `Ver guía detallada`, checkbox `Ya tengo el certificado .crt descargado` y navegación `Anterior`/`Siguiente` en `WizardStep3PortalArca`.
- Se usó frontend local en `http://127.0.0.1:5173` con sesión ficticia, empresa ficticia y respuestas API simuladas. El endpoint `POST /api/certificados/generar-csr` respondió un CSR ficticio solo para avanzar desde el paso 2. No se usaron datos reales, no se abrió el portal externo, no se llamó a ARCA, no se generó CSR real, no se buscaron claves reales, no se cargaron certificados y no se tocó backend.
- Capturas sanitizadas:
  - `private/brand-lab/exports/corte-certificados-wizard-portal-arca-desktop.png`
  - `private/brand-lab/exports/corte-certificados-wizard-portal-arca-confirmado-desktop.png`
  - `private/brand-lab/exports/corte-certificados-wizard-portal-arca-mobile.png`
- Controles realizados: Playwright verificó avance hasta el paso 3, presencia de instrucciones y acción del portal, `Siguiente` deshabilitado antes de confirmar, habilitación después de marcar el certificado descargado, ausencia de errores de consola y ausencia de requests API no mockeadas. Se verificó por script que las capturas existen, tienen dimensiones esperadas y no están vacías; no hubo inspección visual manual directa por ACL de `private/`.
- Verificación automatizada asociada: `git diff --check` OK, `npm run lint:check` OK, `npm run type-check` OK, `npm run build` OK y `npm run test:unit` OK (63 tests).

### Integración visual controlada - CSR generado del wizard de certificados 2026-06-22

- Alcance revisado: alerta `CSR generado exitosamente`, aviso de clave privada, acción `Descargar CSR nuevamente`, panel `Clave privada generada`, acción `Copiar nombre` y navegación `Siguiente` habilitada en `WizardStep2GenerarCSR`.
- Se usó frontend local en `http://127.0.0.1:5173` con sesión ficticia, empresa ficticia y respuestas API simuladas. El endpoint `POST /api/certificados/generar-csr` respondió un CSR ficticio y un nombre de clave ficticio. No se usaron datos reales, no se llamó a ARCA, no se generó CSR real, no se buscaron claves reales, no se cargaron certificados y no se tocó backend.
- Capturas sanitizadas:
  - `private/brand-lab/exports/corte-certificados-wizard-csr-generado-desktop.png`
  - `private/brand-lab/exports/corte-certificados-wizard-csr-generado-mobile.png`
- Controles realizados: Playwright verificó avance desde el intro al paso 2, respuesta mockeada de generación, aparición del estado de éxito, nombre de clave ficticio, botón `Siguiente` habilitado, ausencia de errores de consola y ausencia de requests API no mockeadas. Se verificó por script que las capturas existen, tienen dimensiones esperadas y no están vacías; no hubo inspección visual manual directa por ACL de `private/`.
- Verificación automatizada asociada: `git diff --check` OK, `npm run lint:check` OK, `npm run type-check` OK, `npm run build` OK y `npm run test:unit` OK (63 tests).

### Integración visual controlada - CSR inicial del wizard de certificados 2026-06-22

- Alcance revisado: encabezado del paso 2, bloque de archivos `.key`/`.csr`, selector `Ya tengo el CSR`, formularios inicial/manual, ayuda de ambiente, acción `Buscar claves en servidor` y navegación `Anterior`/`Siguiente` en `WizardStep2GenerarCSR`.
- Se usó frontend local en `http://127.0.0.1:5173` con sesión ficticia y respuestas API simuladas para layout, empresa activa y alertas. No se usaron datos reales, no se llamó a ARCA, no se generó CSR, no se buscaron claves reales, no se cargaron certificados y no se tocó backend.
- Capturas sanitizadas:
  - `private/brand-lab/exports/corte-certificados-wizard-csr-inicial-desktop.png`
  - `private/brand-lab/exports/corte-certificados-wizard-csr-manual-desktop.png`
  - `private/brand-lab/exports/corte-certificados-wizard-csr-inicial-mobile.png`
- Controles realizados: Playwright verificó avance desde el intro al paso 2, carga de formulario inicial, activación de modo manual, ausencia de errores de consola y ausencia de requests API no mockeadas. Se verificó por script que las capturas existen, tienen dimensiones esperadas y no están vacías; no hubo inspección visual manual directa por ACL de `private/`.
- Verificación automatizada asociada: `git diff --check` OK, `npm run lint:check` OK, `npm run type-check` OK, `npm run build` OK y `npm run test:unit` OK (63 tests).

### Integración visual controlada - intro del wizard de certificados 2026-06-21

- Alcance revisado: icono principal, título del paso, tarjeta de explicación,
  bloque `Vas a necesitar`, checklist, tiempo estimado y acción `Comenzar` en
  `WizardStep1Intro`.
- Se usó frontend local en `http://127.0.0.1:5173` con sesión ficticia y
  respuestas API simuladas para layout, empresa activa y alertas. No se usaron
  datos reales, no se llamó a ARCA, no se generó CSR, no se cargaron
  certificados reales, no se emitieron comprobantes y no se tocó backend.
- Capturas sanitizadas:
  - `private/brand-lab/exports/corte-certificados-wizard-intro-desktop.png`
  - `private/brand-lab/exports/corte-certificados-wizard-intro-mobile.png`
- Controles realizados:
  - Playwright verificó carga del wizard, textos del paso introductorio, acción
    `Comenzar`, avance al paso 2, ausencia de errores de consola y ausencia de
    requests API no mockeadas.
  - Se verificó por script que las capturas existen, tienen dimensiones
    esperadas y no están vacías. El visor local de imágenes sigue bloqueado por
    ACL para `private/`, por lo que no se registra inspección visual manual
    directa de esas capturas en este corte.
- Verificación automatizada asociada: `git diff --check` OK,
  `npm run lint:check` OK, `npm run type-check` OK, `npm run build` OK y
  `npm run test:unit` OK (63 tests).
### Integración visual controlada - shell del wizard de certificados 2026-06-20

- Alcance revisado: encabezado de `CertificadoWizardView`, subtítulo, stepper de
  `WizardProgress`, línea de progreso y estados activo/completado/pendiente.
- Se usó frontend local en `http://127.0.0.1:5173` con sesión ficticia y
  respuestas API simuladas para layout, empresa activa y alertas. No se usaron
  datos reales, no se llamó a ARCA, no se generó CSR, no se cargaron
  certificados reales, no se emitieron comprobantes y no se tocó backend.
- Capturas sanitizadas:
  - `private/brand-lab/exports/corte-certificados-wizard-shell-paso1-desktop.png`
  - `private/brand-lab/exports/corte-certificados-wizard-shell-paso2-desktop.png`
  - `private/brand-lab/exports/corte-certificados-wizard-shell-paso1-mobile.png`
- Controles realizados:
  - Playwright verificó carga del wizard, encabezado, paso 1, avance a paso 2,
    ausencia de errores de consola y ausencia de requests API no mockeadas.
  - Se verificó por script que las capturas existen, tienen dimensiones
    esperadas y no están vacías. El visor local de imágenes sigue bloqueado por
    ACL para `private/`, por lo que no se registra inspección visual manual
    directa de esas capturas en este corte.
- Verificación automatizada asociada: `git diff --check` OK,
  `npm run lint:check` OK, `npm run type-check` OK, `npm run build` OK y
  `npm run test:unit` OK (63 tests).
### Integración visual controlada - cards de certificados 2026-06-19

- Alcance revisado: tarjeta de certificado, icono principal, badge de estado,
  icono de advertencia, datos de CUIT/ambiente/vencimiento, barra de vigencia,
  acciones `Probar conexión` / `Renovar` / `Eliminar` y resultado de prueba de
  conexión en `CertificadoCard` y `CertificadoEstado`.
- Se usó frontend local en `http://127.0.0.1:5173` con sesión ficticia y
  respuestas API simuladas para empresa, alertas, certificados y prueba de
  conexión. No se usaron datos reales, no se llamó a ARCA, no se verificaron
  certificados reales, no se emitieron comprobantes y no se tocó backend.
- Capturas sanitizadas:
  - `private/brand-lab/exports/corte-certificados-card-desktop.png`
  - `private/brand-lab/exports/corte-certificados-card-verificacion-desktop.png`
  - `private/brand-lab/exports/corte-certificados-card-mobile.png`
- Controles realizados:
  - Playwright verificó carga de listado, textos esperados, llamada mockeada a
    `Probar conexión`, ausencia de errores de consola y ausencia de requests API
    no mockeadas.
  - Se verificó por script que las capturas existen, tienen dimensiones
    esperadas y no están vacías. El visor local de imágenes quedó bloqueado por
    ACL para `private/`, por lo que no se registra inspección visual manual de
    esas capturas en este corte.
- Verificación automatizada asociada: `git diff --check` OK, test enfocado de
  `CertificadosListView` OK, `npm run lint:check` OK,
  `npm run type-check` OK, `npm run build` OK y `npm run test:unit` OK
  (63 tests).

### Integración visual controlada - listado de certificados 2026-06-18

- Alcance revisado: encabezado, botón `Agregar certificado`, alerta de
  certificados por vencer, grilla/listado y estado vacío en
  `CertificadosListView`.
- Se usó frontend local en `http://127.0.0.1:5173` con sesión ficticia y
  respuestas API simuladas para empresa, alertas y certificados. No se usaron
  datos reales, no se llamó a ARCA, no se verificaron certificados reales, no se
  emitieron comprobantes y no se tocó backend.
- Capturas sanitizadas:
  - `private/brand-lab/exports/corte-certificados-listado-desktop.png`
  - `private/brand-lab/exports/corte-certificados-listado-mobile.png`
  - `private/brand-lab/exports/corte-certificados-empty-desktop.png`
- Controles visuales realizados:
  - escritorio: encabezado, acción principal, alerta y grilla legibles con
    tokens de marca, sin duplicación de íconos en la alerta
  - mobile: encabezado y acción principal apilados, alerta contenida, cards en
    una columna y sin superposición de textos
  - estado vacío: mensaje y acción central alineados con `BaseEmpty` y
    `BaseButton`
- Verificación automatizada asociada: `git diff --check` OK, test enfocado de
  `CertificadosListView` OK, `npm run lint:check` OK,
  `npm run type-check` OK, `npm run build` OK y `npm run test:unit` OK
  (63 tests).

### Integración visual controlada - éxito de certificado 2026-06-18

- Alcance revisado: icono de éxito, título, subtítulo, tarjeta de resumen,
  aviso de vencimiento y acciones `Ir al Dashboard` / `Ver certificados` en
  `CertificadoExitoView`.
- Se usó frontend local en `http://127.0.0.1:5173` con sesión ficticia y
  respuesta API simulada para el certificado. No se usaron datos reales, no se
  llamó a ARCA, no se verificaron certificados reales, no se emitieron
  comprobantes y no se tocó backend.
- Capturas sanitizadas:
  - `private/brand-lab/exports/corte-certificado-exito-desktop.png`
  - `private/brand-lab/exports/corte-certificado-exito-mobile.png`
- Controles visuales realizados:
  - escritorio: tarjeta centrada, resumen, aviso y acciones inferiores
    alineados con la identidad v01
  - mobile: jerarquía legible, datos del certificado sin desbordes y acciones
    apiladas en ancho completo
- Verificación automatizada asociada: `git diff --check` OK,
  `npm run lint:check` OK, `npm run type-check` OK, `npm run build` OK y
  `npm run test:unit` OK (63 tests).

### Integración visual controlada - ranking de clientes 2026-06-18

- Alcance revisado: encabezado, botón `Volver`, filtros `Desde`/`Hasta`,
  selector `Límite`, acción `Generar Reporte`, período, total facturado, top 3,
  resto del ranking y estados vacíos en `RankingClientesView`.
- Se usó frontend local en `http://127.0.0.1:5173` con sesión ficticia y
  respuestas API simuladas. No se usaron datos reales, no se llamó a ARCA, no se
  emitieron comprobantes, no se modificaron reportes ni se tocó backend.
- Capturas sanitizadas:
  - `private/brand-lab/exports/corte-ranking-clientes-inicial-desktop.png`
  - `private/brand-lab/exports/corte-ranking-clientes-resultados-desktop.png`
  - `private/brand-lab/exports/corte-ranking-clientes-resultados-mobile.png`
- Controles visuales realizados:
  - estado inicial: filtros, selector de límite, acción principal y mensaje
    vacío legibles en escritorio
  - resultados desktop: cards del top 3, período, total facturado y resto del
    ranking alineados con la identidad v01
  - resultados mobile: filtros y cards en una columna; resto del ranking
    contenido dentro de la tarjeta, sin desborde de página del corte visual
- Verificación automatizada asociada: `git diff --check` OK, test enfocado de
  `RankingClientesView` OK, `npm run lint:check` OK,
  `npm run type-check` OK, `npm run build` OK y `npm run test:unit` OK
  (63 tests).

### Integración visual controlada - reporte IVA ventas 2026-06-16

- Alcance revisado: encabezado, botón `Volver`, filtros `Mes`/`Año`, acción
  `Generar Reporte`, período, cards de alícuotas, totales, tabla de
  comprobantes y estados vacíos en `ReporteIvaView`.
- Se usó frontend local en `http://127.0.0.1:5173` con sesión ficticia y
  respuestas API simuladas. No se usaron datos reales, no se llamó a ARCA, no se
  emitieron comprobantes, no se modificaron reportes ni se tocó backend.
- Capturas sanitizadas:
  - `private/brand-lab/exports/corte-reporte-iva-inicial-desktop.png`
  - `private/brand-lab/exports/corte-reporte-iva-resultados-desktop.png`
  - `private/brand-lab/exports/corte-reporte-iva-resultados-mobile.png`
- Controles visuales realizados:
  - estado inicial: filtros, acción principal y mensaje vacío sin duplicación
    de íconos ni texto en escritorio
  - resultados desktop: período, alícuotas, totales y tabla alineados con la
    identidad v01
  - resultados mobile: filtros y cards en una columna; tabla contenida dentro
    de la tarjeta, sin desborde de página del corte visual
- Verificación automatizada asociada: `git diff --check` OK, test enfocado de
  `ReporteIvaView` OK, `npm run lint:check` OK, `npm run type-check` OK,
  `npm run build` OK y `npm run test:unit` OK (63 tests).

### Integración visual controlada - reporte de ventas 2026-06-16

- Alcance revisado: encabezado, botón `Volver`, filtros de fecha, acción
  `Generar Reporte`, cards de resumen, período, aviso read-only, tabla de
  comprobantes y estado vacío en `ReporteVentasView`.
- Se usó frontend local en `http://127.0.0.1:5173` con sesión ficticia y
  respuestas API simuladas. No se usaron datos reales, no se llamó a ARCA, no se
  emitieron comprobantes, no se modificaron reportes ni se tocó backend.
- Capturas sanitizadas:
  - `private/brand-lab/exports/corte-reporte-ventas-inicial-desktop.png`
  - `private/brand-lab/exports/corte-reporte-ventas-resultados-desktop.png`
  - `private/brand-lab/exports/corte-reporte-ventas-resultados-mobile.png`
- Controles visuales realizados:
  - estado inicial: filtros, acción principal y mensaje vacío legibles en
    escritorio
  - resultados desktop: resumen de totales, período, aviso de consulta y tabla
    alineados con la identidad v01
  - resultados mobile: filtros y cards en una columna; tabla con scroll
    horizontal interno, sin desborde de página
- Verificación automatizada asociada: `git diff --check` OK, test enfocado de
  `ReporteVentasView` OK, `npm run lint:check` OK, `npm run type-check` OK,
  `npm run build` OK y `npm run test:unit` OK (63 tests).

### Integración visual controlada - índice de reportes 2026-06-15

- Alcance revisado: encabezado, tarjetas de `Ventas por Período`, `Subdiario
  IVA Ventas`, `Ranking de Clientes`, iconografía, estados de foco/hover y aviso
  informativo en `ReportesView`.
- Se usó frontend local en `http://127.0.0.1:5173` con sesión ficticia y
  respuestas API simuladas para el layout. No se usaron datos reales, no se
  llamó a ARCA, no se abrieron reportes con datos y no se tocó backend.
- Capturas sanitizadas:
  - `private/brand-lab/exports/corte-reportes-desktop.png`
  - `private/brand-lab/exports/corte-reportes-mobile.png`
- Controles visuales realizados:
  - escritorio: tres tarjetas de navegación alineadas, legibles y con jerarquía
    visual consistente
  - mobile: tarjetas en una columna, textos sin desbordes y aviso informativo
    legible
  - navegación: las tarjetas quedan como enlaces de router con foco visible,
    conservando las mismas rutas de destino
- Verificación automatizada asociada: `git diff --check` OK,
  `npm run lint:check` OK, `npm run type-check` OK, `npm run build` OK y
  `npm run test:unit` OK (63 tests).

### Integración visual controlada - usuarios 2026-06-15

- Alcance revisado: encabezado, acción `Crear usuario`, tabla de usuarios,
  acciones inline, badges existentes, checkboxes y modales de creación y
  restablecimiento de contraseña en `UsuariosView`.
- Se usó frontend local en `http://127.0.0.1:5173` con sesión administradora
  ficticia y respuestas API simuladas. No se usaron datos reales, no se llamó a
  ARCA, no se emitieron comprobantes, no se enviaron formularios y no se tocó
  backend.
- Capturas sanitizadas:
  - `private/brand-lab/exports/corte-usuarios-listado-desktop-v3.png`
  - `private/brand-lab/exports/corte-usuarios-crear-modal-desktop-accent.png`
  - `private/brand-lab/exports/corte-usuarios-clave-modal-desktop-accent.png`
  - `private/brand-lab/exports/corte-usuarios-listado-mobile-v3.png`
- Controles visuales realizados:
  - escritorio: tabla, acciones `Editar`/`Clave`, botón principal y badges
    legibles y alineados con la identidad v01
  - modales: campos, checkboxes con acento de marca y acciones inferiores
    legibles, sin superposición
  - mobile: encabezado, selector de emisor, acción principal y tabla con scroll
    horizontal interno, sin desborde de página
- Verificación automatizada asociada: `git diff --check` OK,
  `npm run lint:check` OK, `npm run type-check` OK, `npm run build` OK y
  `npm run test:unit` OK (63 tests).

### Integración visual controlada - dashboard 2026-06-15

- Alcance revisado: encabezado, alerta de certificados, cards de métricas,
  accesos rápidos y comportamiento responsive en `DashboardView`.
- Se usó frontend local en `http://127.0.0.1:5173` con sesión ficticia y
  respuestas API simuladas. No se usaron datos reales, no se llamó a ARCA, no se
  emitieron comprobantes y no se tocó backend.
- Capturas sanitizadas:
  - `private/brand-lab/exports/corte-dashboard-desktop.png`
  - `private/brand-lab/exports/corte-dashboard-mobile.png`
- Controles visuales realizados:
  - escritorio: grid completo de métricas, alerta de certificados y accesos
    rápidos alineados con la identidad v01
  - mobile: cards en una columna, bienvenida sin superposición, alerta legible
    y botón de certificados en ancho completo
- Verificación automatizada asociada: `git diff --check` OK, test enfocado de
  `DashboardView` OK, `npm run lint:check` OK, `npm run type-check` OK,
  `npm run build` OK y `npm run test:unit` OK (63 tests).

### Integración visual controlada - setup inicial 2026-06-15

- Alcance revisado: wordmark, subtítulo, tarjeta de configuración inicial,
  indicador de progreso, paso de usuario administrador, paso de datos de empresa
  y acciones inferiores en `SetupView`.
- Se usó frontend local en `http://127.0.0.1:5173` con respuesta API simulada
  para `setup_required=true`. No se usaron datos reales, no se llamó a ARCA, no
  se emitieron comprobantes, no se envió el formulario y no se tocó backend.
- Capturas sanitizadas:
  - `private/brand-lab/exports/corte-setup-usuario-desktop.png`
  - `private/brand-lab/exports/corte-setup-empresa-desktop.png`
  - `private/brand-lab/exports/corte-setup-usuario-mobile.png`
  - `private/brand-lab/exports/corte-setup-empresa-mobile.png`
- Controles visuales realizados:
  - escritorio: wordmark centrado, progreso activo en tokens de marca y tarjeta
    legible
  - paso empresa: formulario de datos fiscales sin envío, con grid desktop
    conservado para localidad/provincia
  - mobile: campos en una columna y acciones inferiores en ancho completo, sin
    superposición
- Verificación automatizada asociada: `git diff --check` OK,
  `npm run lint:check` OK, `npm run type-check` OK, `npm run build` OK y
  `npm run test:unit` OK (63 tests).

### Integración visual controlada - login 2026-06-15

- Alcance revisado: wordmark, subtítulo, tarjeta de inicio de sesión, enlace de
  primera instalación y aviso de servidor local no disponible en `LoginView`.
- Se usó frontend local en `http://127.0.0.1:5173` con respuestas API
  simuladas. No se usaron datos reales, no se llamó a ARCA, no se emitieron
  comprobantes y no se tocó backend.
- Capturas sanitizadas:
  - `private/brand-lab/exports/corte-login-desktop.png`
  - `private/brand-lab/exports/corte-login-mobile-setup.png`
  - `private/brand-lab/exports/corte-login-servidor-no-disponible.png`
- Controles visuales realizados:
  - escritorio: wordmark centrado, tarjeta legible, inputs y acción principal
    alineados con la identidad v01
  - mobile: enlace `Configurar sistema` visible sin desbordes ni superposición
  - aviso operativo: mensaje de servidor no disponible y acción `Reintentar`
    conservados y legibles
- Verificación automatizada asociada: `git diff --check` OK, test enfocado de
  `LoginView` OK, `npm run lint:check` OK, `npm run type-check` OK,
  `npm run build` OK y `npm run test:unit` OK (63 tests).

### Integración visual controlada - formulario de cliente 2026-06-15

- Alcance revisado: título, subtítulo, secciones de información básica,
  domicilio, contacto, textarea `Notas` y acciones inferiores en
  `ClienteFormView`.
- Se usó frontend local en `http://127.0.0.1:5173` con sesión ficticia y
  respuestas API simuladas. No se usaron datos reales, no se llamó a ARCA, no se
  emitieron comprobantes y no se tocó backend.
- Capturas sanitizadas:
  - `private/brand-lab/exports/corte-cliente-form-nuevo-desktop.png`
  - `private/brand-lab/exports/corte-cliente-form-editar-desktop.png`
  - `private/brand-lab/exports/corte-cliente-form-editar-mobile.png`
- Controles visuales realizados:
  - alta: campos vacíos, placeholders y acciones visibles en escritorio
  - edición: datos ficticios precargados, textarea y selects legibles en
    escritorio
  - mobile: acción principal `Guardar Cambios` y `Cancelar` visibles en ancho
    completo, sin superposición con campos
- Verificación automatizada asociada: `git diff --check` OK,
  `npm run lint:check` OK, `npm run type-check` OK, `npm run build` OK y
  `npm run test:unit` OK (63 tests).

### Integración visual controlada - detalle de cliente 2026-06-15

- Alcance revisado: título, acciones `Volver` y `Editar`, secciones de
  información básica, domicilio y contacto en `ClienteDetailView`.
- Se usó frontend local en `http://127.0.0.1:5173` con sesión ficticia y
  respuestas API simuladas. No se usaron datos reales, no se llamó a ARCA, no se
  emitieron comprobantes y no se tocó backend.
- Capturas sanitizadas:
  - `private/brand-lab/exports/corte-cliente-detalle-desktop.png`
  - `private/brand-lab/exports/corte-cliente-detalle-mobile.png`
- Controles visuales realizados:
  - escritorio: acciones alineadas arriba a la derecha, secciones legibles y
    separadores sutiles
  - mobile: botones `Volver` y `Editar` ocupan el ancho disponible, sin
    superposición con el contenido
  - contenido: etiquetas, valores, badges y notas visibles con datos ficticios
- Verificación automatizada asociada: `git diff --check` OK,
  `npm run lint:check` OK, `npm run type-check` OK, `npm run build` OK y
  `npm run test:unit` OK (63 tests).

### Integración visual controlada - Clientes 2026-06-15

- Alcance revisado: encabezado de pantalla, botón `Nuevo Cliente`, buscador,
  celdas principales, email e íconos de acción en `ClientesListView`.
- Se usó frontend local en `http://127.0.0.1:5173` con sesión ficticia y
  respuestas API simuladas. No se usaron datos reales, no se llamó a ARCA, no se
  emitieron comprobantes y no se tocó backend.
- Capturas sanitizadas:
  - `private/brand-lab/exports/corte-clientes-listado-desktop.png`
  - `private/brand-lab/exports/corte-clientes-confirm-dialog.png`
  - `private/brand-lab/exports/corte-clientes-listado-mobile.png`
- Controles visuales realizados:
  - escritorio: título, buscador, tabla e íconos de acción legibles y alineados
    a tokens de marca
  - diálogo: se abrió desde la acción `Eliminar` y conservó el componente común
    `ConfirmDialog`
  - mobile: botón `Nuevo Cliente` ocupa el ancho disponible y los controles de
    paginación siguen visibles; la tabla mantiene desplazamiento horizontal por
    densidad, comportamiento preexistente fuera de este corte
- Verificación automatizada asociada: `git diff --check` OK,
  `npm run lint:check` OK, `npm run type-check` OK, `npm run build` OK y
  `npm run test:unit` OK (63 tests).

### Integración visual controlada - componentes comunes 2026-06-15

- Alcance revisado: `ConfirmDialog` y `Pagination`, usados desde pantallas
  comunes como `Clientes` y desde flujos que abren confirmaciones reutilizables.
- Se usó frontend local en `http://127.0.0.1:5173` con sesión ficticia y
  respuestas API simuladas. No se usaron datos reales, no se llamó a ARCA, no se
  emitieron comprobantes y no se tocó backend.
- Capturas sanitizadas:
  - `private/brand-lab/exports/corte-2c-componentes-comunes-clientes-desktop.png`
  - `private/brand-lab/exports/corte-2c-componentes-comunes-confirm-dialog.png`
  - `private/brand-lab/exports/corte-2c-componentes-comunes-clientes-mobile.png`
- Controles visuales realizados:
  - escritorio: paginación visible con estado activo teal, borde sutil y texto
    de totales legible
  - diálogo: icono y énfasis visual alineados a tokens de estado y marca,
    botones conservados mediante `BaseButton` y overlay existente
  - mobile: botones `Anterior` y `Siguiente` visibles y usables; se observó
    overflow horizontal propio de la tabla de `Clientes`, preexistente y fuera
    de este corte
- Verificación automatizada asociada: `git diff --check` OK,
  `npm run lint:check` OK, `npm run type-check` OK, `npm run build` OK,
  `npm run test:unit` OK (63 tests) y `autoreview` Codex `gpt-5.5 high` limpio.

### Integración visual controlada - shell común 2026-06-15

- Alcance revisado: layout principal autenticado, header, selector de emisor,
  sidebar, navegación activa, footer y menú móvil.
- Se usó frontend local en `http://127.0.0.1:5173` con sesión ficticia y
  respuestas API simuladas. No se usaron datos reales, no se llamó a ARCA, no se
  emitieron comprobantes y no se tocó backend.
- Capturas sanitizadas:
  - `private/brand-lab/exports/app-shell-corte-2a-desktop.png`
  - `private/brand-lab/exports/app-shell-corte-2a-mobile.png`
  - `private/brand-lab/exports/app-shell-corte-2a-mobile-menu.png`
- Controles visuales realizados:
  - escritorio: wordmark visible, navegación activa en teal/mint, header y
    footer sin cambios funcionales, sin overflow horizontal
  - mobile cerrado: menú lateral oculto por defecto, botón de menú visible,
    header sin superposición con el selector de emisor
  - mobile abierto: menú lateral visible, botón de cerrar sin pisar el
    wordmark, overlay aplicado y navegación usable
- Verificación automatizada asociada: `npm run lint:check` OK,
  `npm run type-check` OK, `npm run build` OK, `npm run test:unit` OK
  (61 tests), `npm run test:unit -- Sidebar.spec.ts` OK y `git diff --check`
  OK.

### Plantillas de carga masiva - QA visual ejecutada 2026-06-10

- Entorno: backend `http://localhost:8000`, frontend `http://localhost:8080`,
  navegador Playwright Chromium headless en viewport de escritorio.
- Se inició sesión con un usuario administrador local de QA y se seleccionó un
  emisor activo de prueba compatible con comprobantes C.
- Se abrió `Emisores > Carga masiva > Plantillas` y se confirmó que la pantalla
  lista plantillas del emisor, globales y del sistema.
- Se verificó que una plantilla protegida del sistema no permite edición ni
  desactivación directa desde la UI, y que sí permite clonarse como copia
  editable del emisor.
- Se creó una plantilla desde cero, se revisó el panel de compatibilidad, se
  agregaron, quitaron y reordenaron columnas, y se guardó correctamente.
- Se descargó el `.xlsx` de la plantilla creada y se inspeccionó con
  `openpyxl`: hojas `Comprobantes`, `Instrucciones`, hoja oculta `_factuflow`,
  columnas visibles esperadas y fila superior congelada.
- Se subió un Excel de ejemplo con encabezados y se confirmó que el constructor
  inicia filas editables con esos encabezados.
- Se cambió de emisor activo y se confirmó que la plantilla exclusiva del
  emisor anterior no aparece mezclada en el nuevo emisor.
- Se creó un perfil temporal local que recuerda la plantilla creada, se abrió
  `Emisión masiva`, se aplicó el perfil y se confirmó que `Descargar plantilla`
  descarga esa plantilla.
- Se inició sesión con un usuario común local de QA y se confirmó que el
  constructor no ofrece alcance global. También se verificó que las plantillas
  protegidas siguen bloqueadas para edición y desactivación.
- No se emitió, no se validó ningún lote para CAE y no se llamó a ARCA durante
  esta QA.
- Artefactos visuales y descargas quedaron solo en `output/playwright/`, ruta
  ignorada por Git porque puede contener datos privados del entorno local.

Cobertura no visual complementaria ya verificada por pruebas automatizadas:
versionado en edición, scoping global/emisor, validaciones fiscales de
compatibilidad, notas de crédito/débito y contratos de importación.

### Idempotencia y deduplicación fiscal segura 2026-06-04

- La API de emisión individual, procesamiento de lotes y reintento de fallidos
  rechaza solicitudes sin `X-Idempotency-Key`. Esa validación debe ocurrir antes
  de solicitar CAE.
- En emisión individual, confirmar una factura genera una clave de idempotencia
  por confirmación fiscal final. Si la llamada se repite con la misma clave y
  los mismos datos, no debe solicitar CAE por segunda vez.
- Si el usuario cambia fecha fiscal, punto de venta, receptor, ítems,
  comprobantes asociados o cancela definitivamente la operación individual, la
  UI debe resetear la clave y exigir una nueva confirmación final.
- En emisión masiva, `Emitir comprobantes válidos` genera una clave para ese
  procesamiento de lote y la conserva mientras el mismo lote siga en retry de
  la misma acción. Cambiar lote, archivo, emisor o selección debe resetearla.
- En `Reintentar fallidos`, la clave idempotente se genera al confirmar el
  reintento y debe mantenerse si aparece una advertencia de duplicado lógico
  para esos mismos grupos.
- Si FactuFlow detecta duplicados lógicos, debe mostrar advertencia y pedir
  confirmación adicional. Esa confirmación no cambia la clave idempotente ni
  reemplaza la confirmación fiscal de fecha/punto de venta.
- Si un intento fiscal queda `en_proceso` vencido, la QA técnica debe verificar
  que FactuFlow consulta `FECompConsultar` antes de liberar la numeración. Si
  ARCA confirma autorización pero no hay datos locales completos para
  reconstruir el comprobante, el estado correcto es `requiere_reconciliacion`.
- La columna `Ref` del detalle de lotes no participa como llave fiscal: solo
  agrupa filas del archivo en un comprobante local. La idempotencia fiscal se
  controla por clave de request, payload hash, intento fiscal y numeración.
- Verificación automatizada enfocada: backend cubre clave ausente, replay con
  misma clave, conflicto por payload distinto, constraint de puntos de venta e
  intento stale consultando ARCA antes de liberar. Frontend cubre envío de clave
  en emisión individual y procesamiento de lote.
- Pendiente de QA visual local: abrir `Nueva factura` y `Emisión masiva`,
  disparar una advertencia de duplicado probable con datos de prueba, confirmar
  que aparece el segundo modal, que el retry usa la misma clave y que no hay
  doble solicitud fiscal.

### Migración local a VPS - verificación técnica 2026-06-04

- Se agregó la herramienta privada `python -m app.scripts.vps_migration` con
  `preflight`, `export`, `import` y `validate`.
- El alcance de QA de migración incluye emisores, usuarios, clientes, puntos de
  venta, certificados, formatos, perfiles, comprobantes e ítems.
- La QA debe confirmar que quedan excluidos lotes, filas, temporales, PDFs,
  Excel, logs, cachés, eventos de sistema y exportaciones de almacenamiento.
- Verificación automatizada segura:
  `pytest tests/test_vps_migration.py -q` OK (9 tests),
  `ruff check app/scripts/vps_migration.py tests/test_vps_migration.py` OK y
  `black --check app/scripts/vps_migration.py tests/test_vps_migration.py` OK.
- El preflight real bloqueó inicialmente por un certificado demo activo con
  archivos `pendiente.crt` / `pendiente.key` inexistentes. Se hizo backup
  privado de la SQLite y se desactivó solo ese placeholder demo; luego el
  preflight quedó OK con 9 certificados activos.
- Ensayo local completado: se exportó paquete privado, se levantó PostgreSQL
  local limpio con Docker, se ejecutó `alembic upgrade head`, se importó el
  paquete regenerado con contraseña consistente y `validate` quedó OK.
- Controles adicionales del ensayo: 10 emisores, 2 usuarios, 39 puntos de
  venta, 10 certificados, 5795 comprobantes y 5795 ítems restaurados; tablas de
  lotes/eventos/exportaciones excluidas en cero; secuencias PostgreSQL por
  encima del mayor ID; 9 `.crt` y 9 `.key` restaurados; `/api/health` respondió
  200 contra un backend temporal.
- Durante la preparación y el ensayo no se solicitó CAE ni se emitió ningún
  comprobante.

### VPS privado - QA no destructiva 2026-06-09

- Se restauró en el VPS un paquete privado validado sobre PostgreSQL limpio ya
  migrado con Alembic.
- `python -m app.scripts.vps_migration validate` quedó OK contra la base,
  certificados restaurados y health público HTTPS.
- La URL HTTPS de la instalación respondió `HTTP 200`.
- `/api/health` respondió
  `{"status":"healthy","message":"FactuFlow API funcionando correctamente"}`.
- HTTP redirige a HTTPS.
- `GET /api/auth/setup-status` devolvió `setup_required=false`, por lo que la
  instalación ya tiene usuarios y no expone el setup inicial.
- Smoke de navegador headless: la app redirigió a `/login?redirect=/`, mostró
  la pantalla de inicio de sesión y no produjo errores de consola ni requests
  fallidos.
- Los servicios existentes del host siguieron sanos después de recargar el
  reverse proxy.
- No se solicitó CAE, no se emitieron comprobantes y no se probaron endpoints
  ARCA que puedan consumir numeración fiscal.
- En esa etapa quedó pendiente la QA autenticada por credenciales: iniciar
  sesión, revisar emisor activo, emisores, usuarios, clientes, puntos de venta,
  certificados, comprobantes, PDFs y reportes básicos. Ese punto fue superado
  después por uso autenticado real y auditoría post-emisión; la evidencia
  sensible queda fuera de Git.

### VPS privado - cierre post-emisión, backup y restauración 2026-06-10

- La instalación VPS ya fue usada con login real y emisión productiva real por
  decisión operativa del usuario. La evidencia sensible queda fuera de Git.
- Se ejecutó una auditoría posterior segura con llamadas ARCA de solo lectura:
  `FECompUltimoAutorizado` para revisar numeración y `FECompConsultar` para
  contrastar el último comprobante local por combinación consultable.
- La auditoría no solicitó CAE, no emitió comprobantes, no modificó datos y no
  reinició servicios.
- Resultado sanitizado: numeración local alineada con ARCA para combinaciones
  operativas consultables, últimos CAE/totales consultados coincidentes,
  secuencias PostgreSQL correctas y sin inconsistencias internas bloqueantes.
- Se generó un backup manual privado del VPS y se validó con checksums,
  inspección de `pg_restore` y restauración en una base temporal.
- Se creó una copia cifrada fuera del VPS y se probó restaurarla desde cero en
  un PostgreSQL local efímero. La prueba confirmó que el dump cifrado puede
  recuperarse sin depender del servidor original.
- Queda pendiente por decisión operativa no automatizar backups todavía. Antes
  de hacerlo hay que definir frecuencia, retención, almacenamiento externo,
  monitoreo de fallos y runbook completo de recuperación.

### Gestión de usuarios - verificación técnica 2026-06-03

- `GET /api/auth/setup-status` devuelve setup requerido solo cuando no hay
  usuarios. El enlace `Configurar sistema` en login queda oculto en
  instalaciones ya configuradas.
- La pantalla `Usuarios` queda visible solo para administradores y permite alta,
  edición, desactivación/reactivación y reseteo de contraseña.
- Los usuarios comunes no ven el menú `Usuarios`, pero pueden seleccionar y
  operar cualquier emisor configurado desde `Emisor activo`.
- El backend bloquea login de usuarios inactivos y evita que un administrador
  desactive, degrade o cambie el email de su propia cuenta desde la sesión
  activa.
- Verificación automatizada segura:
  backend `pytest tests/test_auth.py tests/test_usuarios_api.py tests/test_clientes.py tests/test_empresas.py -q`
  OK; frontend
  `npm run test:unit -- --run src/views/auth/LoginView.spec.ts src/stores/empresa.spec.ts src/components/layout/Sidebar.spec.ts`
  OK; `npm run type-check` OK.
- Pendiente de QA visual local: iniciar con un administrador real, abrir
  `Usuarios`, crear un usuario común de prueba, verificar que puede ingresar,
  cambiar de emisor activo y no ver el menú `Usuarios`; luego desactivarlo y
  confirmar que ya no puede iniciar sesión.

### Emisión masiva por sublotes ARCA - verificación técnica 2026-06-03

- Se agregó emisión por sublotes WSFE para lotes elegibles: FactuFlow consulta
  `FECompTotXRequest.RegXReq`, agrupa por punto de venta y tipo de comprobante,
  y envía `FECAESolicitar` con `CantReg` mayor a 1 cuando corresponde.
- Si la consulta de `RegXReq` falla, el lote degrada a modo unitario y muestra
  aviso explícito al usuario en el detalle del lote.
- La verificación fue automatizada y segura con mocks. No se hicieron llamadas
  reales a ARCA, no se solicitaron CAEs y no se emitieron comprobantes.
- Pruebas focalizadas ejecutadas:
  `python -m pytest backend/tests/test_arca/test_wsfev1.py backend/tests/test_facturacion_service.py::test_emitir_comprobantes_lote_usa_un_request_arca_y_persiste_numeracion backend/tests/test_lotes_comprobantes.py::test_procesar_lote_usa_sublotes_arca_segun_regxreq backend/tests/test_lotes_comprobantes.py::test_procesar_lote_fallback_regxreq_degrada_a_unitario_con_aviso -q`
  OK.
- Pendiente de QA visual local: abrir `Emisión masiva`, revisar que el aviso de
  fallback se vea correctamente en un lote mockeado o de prueba local, sin
  emitir comprobantes reales.

### Gestión resolutiva de lotes parciales - verificación técnica 2026-06-03

- Se agregó panel de resolución en `Emisión masiva` para lotes con pendientes:
  reintentar fallidos, reconciliar comprobantes emitidos en ARCA Web, descartar
  comprobantes visibles, compactar lotes cerrados y eliminar lotes sin emisión.
- El reintento de fallidos exige el mismo tipo de confirmación fiscal exacta que
  la emisión inicial: fecha fiscal y punto de venta deben coincidir con el token
  calculado por backend.
- Si un reintento queda interrumpido después de tomar el grupo, el grupo queda
  como reconciliable y no vuelve automáticamente a fallido. Debe verificarse en
  ARCA y cerrarse con `Reconciliar ARCA Web`.
- La reconciliación externa no confía en datos cargados a mano: el backend
  consulta ARCA con `FECompConsultar` y solo cierra el grupo si coinciden tipo,
  punto de venta, número, fecha, total, emisor, receptor y CAE.
- Los cierres quedan separados para QA:
  - `Completado`: todo fue emitido por FactuFlow
  - `Cerrado reconciliado`: todo quedó autorizado, con al menos un comprobante
    emitido fuera de FactuFlow y verificado contra ARCA
  - `Cerrado con descartes`: quedan comprobantes descartados por decisión
    operativa
- La compactación elimina el detalle original por fila de lotes cerrados; luego
  el archivo observado ya no debe descargarse. El resumen del lote y los grupos
  deben seguir visibles.
- Compactar no pide motivo operativo: debe mostrar un popup con consecuencias y
  registrar internamente el motivo estándar de ahorro de almacenamiento.
- La eliminación física solo debe aparecer o prosperar si el lote no tiene
  comprobantes emitidos, reconciliados ni inciertos.
- Verificación automatizada segura, sin llamadas reales a ARCA:
  backend `python -m pytest backend/tests/test_lotes_comprobantes.py -q` OK
  (63 tests); frontend
  `npm run test:unit -- --run src/utils/lote-progress.spec.ts src/utils/lote-totals.spec.ts src/views/comprobantes/LotesComprobantesView.spec.ts`
  OK (14 tests), `npm run type-check` OK y `npm run lint:check` OK.
- Pendiente de QA visual local: usar una base de prueba con un lote parcial,
  verificar que las acciones se habilitan o bloquean según el estado, confirmar
  que el modal de reintento muestra fecha/punto de venta concretos, y no emitir
  comprobantes reales durante esa revisión salvo decisión explícita del usuario.

### Detalle paginado de lotes grandes - QA visual 2026-05-29

- En navegador integrado se abrio `http://127.0.0.1:8080/comprobantes/lotes`
  con usuario QA local y emisor activo privado.
- Se reviso un lote local grande de 1432 comprobantes sin emitir. La pantalla
  muestra el resumen completo del lote y la leyenda
  `El resumen fiscal considera el lote completo`.
- La grilla inicial carga 100 comprobantes y muestra
  `Mostrando 1 a 100 de 1432 comprobantes`. Al avanzar, muestra
  `Mostrando 101 a 200 de 1432 comprobantes`.
- La medicion visual quedo acotada: 100 filas renderizadas, `nodeCount`
  aproximado 2026 y `scrollHeight` aproximado 15371. La version anterior
  renderizaba todo el ultimo lote, con aproximadamente 24629 nodos y
  `scrollHeight` 165654.
- No se presiono `Emitir comprobantes validos` ni se solicitaron CAE durante
  esta QA.

### PDF profesional y QR ARCA - verificacion tecnica 2026-05-14

- Se actualizo el PDF de comprobante para presentacion administrativa
  profesional, alineando las ubicaciones principales con la factura oficial ARCA
  sin copiar identidad visual ni formato editable oficial.
- El PDF muestra `ORIGINAL`, caja de letra/codigo, emisor, receptor, periodo,
  detalle, totales, CAE, vencimiento CAE, leyenda ARCA y QR en una hoja A4.
- Para consumidor final sin documento, el PDF muestra `Doc.: -` y
  `Condicion frente al IVA: Consumidor Final`, evitando exponer el `0` tecnico
  usado por WSFE/QR. Si el receptor tiene una razon social real, se muestra; si
  solo dice `A CONSUMIDOR FINAL`/`Consumidor Final`, el nombre queda vacio.
- `Emisores` y el setup inicial permiten cargar `Ingresos Brutos`; el PDF lo
  muestra si esta informado y, para emisores anteriores, indica `No informado`.
- Los comprobantes nuevos guardan fechas de servicio y vencimiento de pago para
  mostrarlas en el PDF cuando corresponda.
- Se aplico migracion local para reconstruir fechas de servicio/vencimiento de
  comprobantes historicos emitidos por lote desde el `payload_json` del grupo.
- El QR se verifico por test decodificando el Base64 de la URL y comparando el
  payload con los campos requeridos por ARCA.
- Verificacion visual tecnica local: se renderizo un PDF de muestra a PNG desde
  la plantilla real y quedo en una pagina con QR, CAE y totales visibles.
- Verificacion tecnica sobre un comprobante autorizado local: el PDF queda en
  una pagina y el texto extraido incluye periodo `01/04/2026 - 30/04/2026`,
  vencimiento `30/04/2026`, CAE y razon social del receptor.
- Pendiente de QA visual final: abrir un PDF real desde la UI y revisar
  legibilidad en preview/descarga con un comprobante autorizado.

### Formato privado - Factura B IVA 21% - QA 2026-05-11

- Se creo un formato particular de Factura B IVA 21% para un emisor privado y
  se vinculo al perfil predeterminado de ese emisor.
- El formato toma `Imp. Neto Gravado` como neto del item y usa `Imp. Total`
  solo como control de consistencia.
- El Excel privado revisado trae 1432 filas utiles, todas `Factura B`, fecha de
  origen `28/02/2026`, receptor sin identificacion y columna `Punto de Venta`
  vacia. Para la QA se uso el punto fijo `5` del perfil del emisor.
- Validacion segura en copia de la base local, sin presionar ni ejecutar
  procesamiento de emision: 1432 grupos validos, 0 observados, 0 emitidos.
- La prueba negativa con `Imp. Total` usado como neto quedo bloqueada por la
  validacion de consistencia: 1432 grupos con error y 0 emitidos.
- El detalle del lote validado ahora muestra `Totales listos para emitir` antes
  del avance y antes de confirmar emision: neto, IVA 21%, IVA 10,5% y total.
  Verificacion automatizada frontend: el helper suma solo grupos validados y
  reproduce el redondeo por comprobante.

### Progreso de lotes con timer - verificacion controlada 2026-05-10

- Se implemento seguimiento real de emision para lotes chicos y grandes: la UI
  inicia el procesamiento con `background=true` y consulta el lote por polling.
- La barra de avance muestra comprobantes procesados sobre emitibles, emitidos,
  fallidos, pendientes, tiempo transcurrido y estimado restante.
- Mientras el lote esta `En cola` o sin primer comprobante procesado, la barra
  usa animacion indeterminada y muestra `Estimando...`.
- Verificacion sin emision real: los tests backend mockean
  `FacturacionService.emitir_comprobante`, por lo que no solicitan CAE ni
  consumen numeracion fiscal real.
- Se verifico por test que la API sigue bloqueando procesamiento sin
  `X-Confirmacion-Fecha-Fiscal` valido.
- Actualización técnica 2026-06-12: si un lote ya está `Procesando`, la API no
  lo vuelve a bajar a `En cola` al pedir procesamiento background. Si el worker
  encuentra un lote `Procesando` vencido por
  `BATCH_PROCESSING_STALE_MINUTES`, ya no lo reanuda para pedir CAE. Primero
  vincula comprobantes locales ya autorizados si puede hacerlo sin llamar a
  ARCA; si queda cualquier comprobante pendiente o incertidumbre, lo marca como
  `requiere_reconciliacion` y registra `bloqueo_operativo_no_reemitir`. Los
  grupos que seguían `validado` también pasan a `requiere_reconciliacion` para
  que la pantalla no los presente como listos para emitir.
- Verificacion tecnica 2026-05-16: si ARCA devuelve CAE pero FactuFlow no logra
  persistir el comprobante, la emision queda marcada como
  `requiere_reconciliacion` y no como `fallido`. En ese estado no debe
  reintentarse el lote; corresponde consultar ARCA y reconciliar antes de
  continuar.
- Verificacion tecnica 2026-05-16: Factura C no permite items con IVA distinto
  de 0. La emision individual fuerza el selector de IVA a 0 para Factura C y la
  validacion de lotes rechaza archivos tipo C con IVA informado.
- Verificacion tecnica 2026-05-16: el emisor activo queda aislado por pestaña
  para que otra pestaña no cambie silenciosamente `X-Empresa-Id`; si header y
  query legacy `empresa_id` no coinciden, la API rechaza el pedido.
- Verificacion tecnica 2026-05-16: la vista previa de nueva factura muestra el
  punto de venta elegido y el Excel observado de lotes escapa valores con forma
  de formula.
- Verificacion tecnica 2026-05-16: `Puntos de venta` solo habilita
  `Sincronizar con ARCA` si hay certificado activo para el ambiente backend
  actual, no por un certificado activo de otro ambiente.
- Verificacion tecnica 2026-05-17: lotes rechazan XLSX malformados y uploads
  mayores que `BATCH_MAX_UPLOAD_BYTES`; el procesamiento exige un header
  `X-Confirmacion-Fecha-Fiscal` con token exacto
  `fechas=AAAA-MM-DD,...;puntos_venta=N,...` calculado desde los grupos
  validados; los mensajes de rechazo muestran fecha y punto concretos.
- Verificacion tecnica 2026-05-17: perfiles con reglas relativas de fecha ya
  no completan una fecha fiscal por contexto temporal al autoaplicarse en
  `Emision masiva`; el usuario debe elegir fecha exacta o archivo antes de
  validar.
- Verificacion tecnica 2026-05-17: los totales previos de lotes interpretan
  importes argentinos como `1.234,56` y avisan si queda algun valor ambiguo.
- Pendiente de QA visual opcional: levantar entorno local y confirmar en
  navegador que el modal de fecha fiscal puede cancelarse con `Volver a revisar`
  y que la barra avanza durante un lote mockeado o de homologacion controlada.

### Perfiles de carga masiva - QA 2026-05-09

Validado visualmente en `http://127.0.0.1:8080` con usuario local privado:
- En `Emisores > Carga masiva`, se creo un perfil de carga masiva con formato
  global, concepto `Servicios`, descripcion fija `Ajuste QA` y reglas relativas
  `ultimo_dia_mes_anterior`, `mes_anterior_completo` y `emision_mas_dias`.
- La UI ya no ofrece `Fecha actual` como regla persistible de fecha de emision
  del perfil de carga masiva.
- Se creo un segundo perfil de carga masiva, se marco como predeterminado, se
  edito desde modal y se elimino con confirmacion visual.
- En `Emision masiva`, el perfil de carga masiva predeterminado se aplico
  automaticamente al cambiar de emisor y al entrar a la pantalla.
- Formato, concepto fiscal ARCA, descripcion facturada y fechas quedaron
  visibles y editables antes de validar.
- Al modificar manualmente una fecha calculada, la pantalla mostro que la carga
  se validaria sin snapshot de perfil de carga masiva.
- Se valido un Excel privado local para un emisor monotributo local con
  puntos de venta QA `6`, `8`, `10`, `12` y `13`: 20 comprobantes validos,
  fecha fiscal resuelta `30/04/2026`, periodo `01/04/2026 - 30/04/2026` y
  descripcion `Ajuste QA`.
- Antes de emitir aparecio el modal `Confirmar fecha fiscal` con fecha concreta
  y puntos de venta concretos:
  `Está seguro que quiere emitir comprobantes con fecha 30/04/2026 para los puntos de venta 0006, 0008, 0010, 0012, 0013? Recuerde que luego no podrá emitir comprobantes con fecha anterior para ese mismo punto de venta.`
  Se cancelo con `Volver a revisar`; no se solicito CAE.
- El cambio de emisor activo recargo perfiles, lotes y formatos sin mezclar
  CUITs.

Actualizacion 2026-05-10:
- Los perfiles de carga masiva permiten elegir `Utilizar punto de venta definido
  en el archivo` o un punto de venta usable del emisor activo.
- Si el emisor no tiene puntos usables cargados, el modal de perfil indica que
  primero deben completarse en `Puntos de venta`.
- En `Emision masiva`, el punto de venta aplicado por perfil queda visible y
  editable antes de validar; si se elige un punto fijo, la validacion usa ese
  punto para todos los comprobantes.
- Verificacion automatizada sin emision: backend cubre perfil con punto
  habilitado, rechazo de punto no usable, sobrescritura del punto del archivo al
  validar lote y bloqueo de punto fijo no cargado. Frontend cubre resolucion de
  punto fijo desde perfil.

### Selector de emisor activo - QA 2026-05-09

- Usuario usado: cuenta QA local privada.
- Se valido en `http://127.0.0.1:18082` que al cambiar el selector de emisor
  activo las secciones vuelven a pedir datos con el `X-Empresa-Id` correcto:
  Dashboard, Clientes, Comprobantes, Emision masiva, Certificados, Puntos de
  venta, Nueva factura, Reporte de ventas, Subdiario IVA y Ranking de clientes.
- En Reportes, si ya habia un resultado visible, el cambio de emisor regenera
  el reporte con el mismo filtro para el nuevo emisor.
- En Nueva factura, el cambio de emisor recarga puntos de venta/proximo numero
  y limpia el cliente seleccionado para evitar mezclar datos entre CUITs.
- Verificacion tecnica 2026-05-16: el backend tambien bloquea la emision si el
  request intenta usar un punto de venta o `cliente_id` de otro emisor. La
  validacion ocurre en el servicio de facturacion antes de solicitar CAE y cubre
  tanto emision individual como emision por lotes.

### 1. Dashboard

- Cargo correctamente.
- El selector de empresa activa se vio bien.
- Se corrigieron los KPIs hardcodeados.
- Estado validado hoy:
  - `Total Clientes = 7`
  - `Comprobantes del Mes = 3`
  - `Ultimo Comprobante = 0005-00000006`
  - `Estado Certificado = Valido`

### 2. Comprobantes

- El listado mostro correctamente 6 comprobantes autorizados.
- Se verificaron columnas tipo, numero, fecha, cliente, total, estado y acciones.

### 3. Detalle de comprobante

- El detalle carga correctamente.
- Se verificaron CAE, vencimiento, cliente, items y totales.

### 4. PDF

- `Ver PDF` abre correctamente.
- Se visualizo CAE y QR.
- `Descargar PDF` descarga correctamente el archivo.
- Desde 2026-05-14 el PDF tiene nuevo diseño y requiere revalidacion visual en
  navegador antes de tomarlo como evidencia manual vigente.

### 5. Nueva factura

- Se completo el flujo real desde UI.
- Se detecto y corrigio un fallo en `proximo-numero` causado por resolucion incorrecta del path de certificados legacy.
- Verificacion tecnica 2026-05-17: `Nueva factura` solo ofrece puntos de venta
  usables por FactuFlow para emitir. Si se consulta directo
  `proximo-numero` con un punto no Web Services, la API responde 400 de negocio
  y no un 500.
- Resultado real:
  - `Factura B`
  - `0005-00000004`
  - CAE registrado en evidencia local privada

### 6. Emision masiva

- `Descargar plantilla` funciona.
- La validacion del lote funciona.
- El flujo mantiene la separacion entre validar y emitir: no se consume
  numeracion fiscal hasta presionar `Emitir comprobantes validos`.
- La emision del lote funciona desde UI.
- `Descargar observado` funciona sobre el lote completado.
- Se valido desde UI un lote productivo preparatorio privado con consumidor
  final sin documento para el emisor real privado. Resultado:
  `Validado`, `Listos para emitir = 1`, receptor `A CONSUMIDOR FINAL`,
  documento `0`, punto de venta `6`, total estimado `$1.210,00`. No se presiono
  `Emitir comprobantes validos`.
- Resultado real:
  - `0005-00000005` -> CAE registrado en evidencia local privada
  - `0005-00000006` -> CAE registrado en evidencia local privada

Validado localmente el 2026-05-08:
- autodeteccion asistida de formato al subir Excel externo
- preseleccion automatica del formato sugerido cuando la coincidencia es alta;
  el usuario puede cambiarlo si no esta de acuerdo
- si al subir un archivo todavia no hay encabezados analizados, la pantalla
  bloquea `Validar lote` y ofrece `Analizar encabezados` como reintento manual
- formato global `Extracto bancario - creditos IVA exento`
- mapeo de columnas `Fecha`, `Créditos`, `Leyendas Adicionales1`,
  `Leyendas Adicionales2` y `Pto Vta`
- validacion de un extracto chico con puntos de venta `6`, `10` y `13`
- la validacion quedo sin emision: `Ya emitidos = 0`
- formato particular local `Factura B IVA 21%` para un emisor Responsable
  Inscripto privado
- la muestra privada local detecta ese formato con
  confianza alta, 7 filas y punto de venta `2`; mapea `Imp. Neto Gravado` como
  precio neto del item e IVA constante `21`
- la muestra no trae numero de documento real del receptor: la columna
  `Nro. Doc. Receptor` contiene nombres y `Denominación Receptor` viene vacia,
  por lo que la prueba debe tratar esos comprobantes como consumidor final sin
  documento mientras el importe este bajo el umbral legal
- la fecha de la muestra es `30/04/2026`; al probarla el usuario debe elegir
  una politica de fecha permitida por ARCA antes de validar o emitir
- se agrego validacion anti-mapeo incorrecto: si un formato externo trae
  `Imp. Total`, el total calculado desde item e IVA debe coincidir con ese total
  antes de habilitar emision. Un formato de prueba que usa `Imp. Total` como
  neto queda observado con error de diferencia de total.
- se genero un Excel privado local con 1113 Nota de Credito B para corregir el
  exceso de Factura B de un emisor Responsable Inscripto privado. Validacion
  contra copia de base local:
  1113 grupos validos, 0 errores, 0 emitidos, total `$7.288.804,44`.
- queda documentado para usuario final que, en la plantilla oficial, FactuFlow
  procesa la hoja `Comprobantes`; hojas como `Resumen` o `Control` son solo
  informativas.

Cambio critico posterior el 2026-05-08:
- la emision individual y masiva ya no debe asumir fecha del dia actual
- el lote exige definir fecha de emision antes de validar: desde archivo o fecha
  fija
- el lote no debe asumir productos ni servicios por defecto; antes de validar y
  emitir el usuario debe elegir `Productos`, `Servicios` o `Definido por archivo`
- si se elige `Definido por archivo`, el Excel debe tener una columna valida con
  `Producto` o `Servicio` en todas las filas; si falta o hay valores invalidos,
  se informa al usuario y no se habilita la emision
- el selector anterior define el tipo de concepto fiscal ARCA; no es la
  descripcion/concepto facturado del item. La descripcion del item debe
  definirse aparte, por columna del archivo o como texto fijo para todo el lote
  antes de validar, por ejemplo `Honorarios`, `Zapatillas` o `Servicio mensual`
- para servicios, el lote exige definir tambien fecha desde, fecha hasta y
  vencimiento de pago: desde archivo o fechas fijas
- la validacion observa fechas de emision fuera de ventana ARCA antes de emitir
- si la fecha del archivo queda fuera de ventana ARCA, el usuario debe elegir
  una fecha permitida por el web service antes de emitir
- se probo un Excel privado local: el archivo trae fecha `06/04/2026` como
  serial numerico de Excel; el sistema la interpreta correctamente, lo clasifica
  como servicios con el formato global vigente y bloquea los 20 comprobantes por
  estar fuera de ventana ARCA. No se emitio nada.
- se revalido ese Excel privado despues de separar descripcion facturada:
  si se elige descripcion desde archivo, el backend rechaza porque el Excel no
  trae columna de descripcion; con descripcion fija de prueba `Honorarios`, el
  lote `id=8` queda `con_errores`, 0 validos, 20 observados por fecha fuera de
  ventana ARCA y 0 emitidos.
- se reviso el archivo observado privado: el fallo de emision no era por
  puntos de venta inexistentes en el Excel, sino por una normalizacion incorrecta
  de `Bloqueado=N` devuelto por ARCA. Se corrigio la validacion para que puntos
  como `6`, `10` y `13` no se rechacen cuando ARCA los informa no bloqueados.
- se reviso el segundo fallo productivo observado: ARCA rechazo Factura C con
  codigo `10071` porque el request informaba el objeto `Iva` con alicuota 0.
  Se corrigio para no enviar `Iva` en tipos `11`, `12` y `13`, y para bloquear
  localmente Factura C con items de IVA distinto de 0.
- se corrigio el reintento de lotes: si el archivo ya fue cargado pero el lote
  termino `fallido` o `con_errores` sin ningun comprobante emitido, ahora puede
  volver a validarse el mismo archivo. El historial se conserva; solo se libera
  la clave de idempotencia del intento anterior.
- la primera prueba productiva real autorizo comprobantes con CAE. Se detecto
  procesamiento concurrente por procesos backend viejos y se corrigio la toma
  atómica del lote para impedir que una segunda ejecución procese el mismo lote.
- se preparo un Excel privado local para anular los 19 comprobantes duplicados
  mediante Nota de Credito C. El archivo se valido contra una copia de la base
  local, sin emitir y sin registrar el lote en la base operativa: 19 grupos
  validos, 0 observados, 0 emitidos. Cada grupo incluye el comprobante asociado
  que debe enviarse a ARCA como `CbtesAsoc`.
- el usuario proceso ese Excel privado en produccion. Verificacion posterior
  sin operaciones de emision: lote `12` completado, 19 grupos autorizados,
  0 fallidos, 0 con error. `FECompConsultar` contra ARCA confirmo las 19 Nota de
  Credito C con `Resultado=A`, CAE coincidente y `CbtesAsoc` contra las facturas
  duplicadas esperadas.
- incidente critico detectado despues: las 19 Nota de Credito C quedaron
  emitidas con fecha fiscal `08/05/2026`. Desde ahora la QA manual de cualquier
  emision debe verificar que aparece el modal `Confirmar fecha fiscal` con el
  texto `Está seguro que quiere emitir comprobantes con fecha XX/XX/XX? Recuerde
  que luego no podrá emitir comprobantes con fecha anterior para ese mismo punto
  de venta.` antes de solicitar CAE.
- verificacion tecnica asociada: la API tambien bloquea emision directa si falta
  la confirmacion fiscal explicita (`confirmacion_fecha_fiscal=true` en emision
  individual o `X-Confirmacion-Fecha-Fiscal` con fechas y puntos concretos en
  procesamiento de lotes).
- QA visual local: al subir el Excel privado, la pantalla muestra el
  selector `Tipo de concepto fiscal ARCA obligatorio`, el selector
  `Descripcion facturada obligatoria`, las opciones de descripcion desde archivo
  o fija, y la columna `Descripcion facturada` antes de emitir.

Reglas vigentes para cualquier nueva emision productiva:
- definir con el usuario/contador la fecha de emision permitida por ARCA
- antes de emitir facturas, notas de credito o notas de debito de emisores
  privados, confirmar explicitamente la fecha fiscal fija o la politica de
  fecha tomada del archivo
- definir con el usuario/contador la descripcion facturada real si no viene del
  archivo
- revisar totales, puntos de venta y formato confirmado
- emitir solo con confirmacion explicita e irreversible

### 7. Clientes

- El listado carga correctamente.
- Desde 2026-05-09, el listado respeta el emisor activo tambien para usuarios
  admin y recarga al cambiar el selector.
- En el flujo legacy de homologacion se verifico que los clientes creados automaticamente por emision masiva quedaron visibles:
  - `Consumidor Final Lote Uno`
  - `Consumidor Final Lote Dos`
- Desde 2026-05-05, los lotes masivos no crean clientes persistentes por defecto
  cuando el receptor viene solo como consumidor final del Excel; el comprobante
  guarda snapshot fiscal del receptor.

### 8. Reportes

- `Ventas por periodo` carga y muestra los 3 comprobantes de abril.
- `IVA ventas` carga y refleja bases e IVA de abril.
- `Ranking de clientes` carga y ordena correctamente los clientes facturados.
- Desde 2026-05-09, los tres reportes usan el emisor activo y se regeneran al
  cambiarlo si habia un resultado visible.
- Verificacion tecnica 2026-05-17: los reportes descartan respuestas viejas si
  el usuario cambia de emisor activo mientras hay pedidos en curso.
- Verificacion tecnica 2026-05-17: el detalle del subdiario IVA incluye
  columnas para gravado e IVA 27%.

### 9. Certificados

- La vista carga correctamente.
- Se visualizo certificado homologacion valido, ambiente y vencimiento.
- Se agrego accion `Probar conexion` en cada certificado para validar WSAA/ARCA
  antes de emitir, reutilizando el endpoint scopiado por emisor activo.
- Se agrego al wizard el paso previo de autorizar `wsfe` en ARCA antes de
  ejecutar `Probar conexion`.
- Verificacion tecnica 2026-05-16: la carga de certificados solo acepta claves
  privadas generadas por FactuFlow para el CUIT y ambiente del emisor activo, y
  ubicadas dentro de `CERTS_PATH`. Una renovacion deja activo solo el
  certificado nuevo del mismo emisor/ambiente. No se hicieron llamadas ARCA
  reales en esta verificacion.
- Verificacion tecnica 2026-05-17: el enlace al portal ARCA del wizard abre con
  `target="_blank"` y `rel="noopener noreferrer"`; la lista de certificados
  descarta respuestas viejas si cambia el emisor activo durante la carga.

### 10. Puntos de venta

- La vista carga correctamente.
- Se verifico el punto de venta `0005` activo.
- Durante la QA se detecto y corrigio un fallo real en `Sincronizar con ARCA`.
- Estado final: sincronizacion ejecutada con respuesta OK desde UI.
- Verificacion puntual 2026-05-10: para un emisor privado, ARCA produccion
  devolvio puntos con `Bloqueado=N` y sin fecha de baja. La UI los mostraba como
  `Otro sistema` porque habian sido sincronizados solo con numero. Se corrigio
  `Sincronizar con ARCA` para crear o actualizar puntos WSFE como Web Services
  usables.
- En preparacion productiva se sincronizaron para el emisor real los puntos
  habilitados `6`, `8`, `10`, `12`, `13` y `14`; ARCA devolvio `7` y `9`
  bloqueados.
- Se importo la constancia PDF de puntos de venta del CUIT real y se valido que
  quedan visibles sistema, domicilio, nombre fantasia, usabilidad FactuFlow y
  estado bloqueado/no bloqueado.
- Verificacion tecnica 2026-05-17: `Puntos de venta` y el store descartan
  respuestas viejas al cambiar el emisor activo; la habilitacion de
  `Sincronizar con ARCA` sigue dependiendo del certificado activo del ambiente
  backend actual.

### 11. Mi Empresa

- La pantalla dejo de estar en placeholder.
- Se implemento formulario real contra la API.
- Se probo guardado desde UI con `PUT 200`.

## Hallazgos corregidos durante la QA

- Detalle de comprobante: faltaba `result.unique()`.
- Preview de PDF: el frontend llamaba mal la ruta.
- Proximo numero para nueva factura: path legacy de certificado mal resuelto.
- Sincronizacion de puntos de venta ARCA: helper usaba el CUIT incorrecto.
- Dashboard: KPIs hardcodeados.
- Mi Empresa: placeholder sin funcionalidad.

## Resultado

- QA manual funcional cerrada para el alcance actual del MVP en homologacion.
- Produccion real ya fue operada y verificada con evidencia privada local; este
  documento conserva los hitos y reglas de QA sin copiar datos privados.
- El flujo de emision masiva ahora inicia desde la UI lotes chicos y grandes en
  segundo plano para poder mostrar avance real.
- La pantalla muestra estado `En cola` / `Procesando`, barra de progreso,
  emitidos, fallidos, pendientes, tiempo transcurrido y estimado restante.
- La pantalla de emision masiva permite revisar el formato detectado, confirmar
  el formato de importacion y validar antes de emitir.
- La pantalla `Emisores` permite agregar un nuevo emisor desde un modal y
  seleccionarlo como activo al crearlo.
- En el modal `Agregar emisor`, la accion `Subir constancia` procesa un PDF de
  constancia ARCA y precompleta los datos detectados sin guardar automaticamente.
- Se valido el parser con una constancia de opcion de Monotributo: detecta CUIT,
  razon social, condicion Monotributo, domicilio, localidad, provincia, codigo
  postal e inicio de actividades.
- Se validó el parser con una constancia de inscripción de persona física:
  corrige cortes de texto del PDF en nombre, domicilio y localidad, detecta
  codigo postal/provincia y no completa provincia con lineas tecnicas.
- En `Emisores`, provincia se selecciona desde un catalogo cerrado de provincias
  argentinas tanto en alta como en edicion.
- Puntos de venta respeta el emisor activo: al seleccionar un emisor nuevo sin
  puntos cargados, no muestra puntos de otros emisores.
- Verificacion Clawpatch 2026-05-17: backend, frontend y repo quedaron con
  `openFindings=0`; la ultima revision repo no encontro features pendientes ni
  hallazgos nuevos.
- Verificación Clawpatch 2026-07-05: backend, frontend y repo completo vuelven
  a quedar con `openFindings=0`. El ciclo fue técnico y sanitizado: no solicitó
  CAE, no emitió comprobantes, no llamó ARCA real y no usó datos privados. El
  cierre operativo quedó en
  `docs/project/audits/clawpatch/2026-07-05-cierre-auditoria.md`.
- Verificación automatizada vigente 2026-07-05: frontend `npm run test:unit`
  OK (83 tests), `npm run type-check` OK y `npm run lint:check` OK. CI remoto
  GitHub Actions para `ebc176d` quedó OK en `Frontend Build`, `Backend Tests`,
  `Security Audit` y `E2E Tests`; la matriz multinavegador/mobile local queda
  opt-in con `E2E_FULL_BROWSER_MATRIX=1`.
- QA local post-incidente 2026-06-12 sobre lote `requiere_reconciliacion`:
  navegador Playwright con base aislada en `.tmp`, sin llamadas reales a ARCA.
  La pantalla mostró `Requiere reconciliación`, `Listos para emitir 0`,
  pendientes visibles, grupo en reconciliación, sin mensaje de `Validado
  correctamente. Listo para emitir.`, y acciones sensibles deshabilitadas:
  `Emitir comprobantes válidos`, `Reintentar fallidos`, `Descartar visibles` y
  `Reconciliar comprobante`. No hubo errores de consola.
- Quedan pendientes tareas de robustez operativa post-piloto que no se resuelven
  solo desde QA local: completar observabilidad operativa estándar, automatización
  futura de backups, política de retención, trazabilidad visible y soporte de
  despliegue.

## Punto de reanudacion

El estado operativo canonico esta en `docs/agents/current-status.md`.

Desde la QA manual, no queda pendiente volver a configurar desde cero
certificado productivo, autorizacion `wsfe` ni puntos de venta productivos para
el emisor real: esos puntos fueron verificados en la preparacion productiva y
la produccion real ya fue utilizada.

Retomar en consolidacion post-piloto:

1. Usar `docs/agents/current-status.md` como estado operativo canonico.
2. Mantener documentacion viva alineada con evidencia local segura, sin copiar
   CUITs, CAEs, Excels, PDFs ni logs privados.
3. Para nuevos lotes productivos, repetir siempre la validacion fiscal completa:
   formato, concepto fiscal ARCA, descripcion facturada, fechas fiscales,
   totales, puntos de venta y confirmacion irreversible.
4. La instalación VPS privada ya quedó publicada por HTTPS, fue usada con login
   real y tiene auditoría post-emisión sanitizada sin desfases fiscales
   bloqueantes.
5. Guardar la clave real del backup cifrado en un gestor de contraseñas seguro;
   la copia local protegida por DPAPI sirve como resguardo de esta PC, pero no
   reemplaza un secreto portable.
6. Para VPS, verificar política de almacenamiento mínimo: PDFs, ZIPs,
   observados y temporales descargables no deben quedar como ocupación
   permanente si no son vitales para operar, auditar o recuperar el sistema.
7. Repetir en VPS con datos de prueba controlados la QA visual del gestor de
   almacenamiento. La prevalidación local con API mockeada ya cubrió uso total,
   desglose por emisor, desglose por tipo de dato, resguardo ZIP y confirmación
   de limpieza segura sin datos reales.
8. Completar la observabilidad operativa estándar definida en
   `docs/agents/operational-observability.md`: healthcheck dedicado de worker,
   backup visible, trazabilidad histórica y próximos pasos claros para usuarios
   no técnicos.
9. Diseñar, pero no implementar todavía, la automatización de backups cifrados
   con validación periódica, retención y destino externo.
10. Convertir los detalles detectados durante la emisión real en backlog
   priorizado antes de seguir ampliando uso. El diagnóstico UX de carga masiva
   ya quedó formalizado en `docs/agents/lotes-ux-redesign.md`; el primer corte
   recomendado es reorganizar preparación y validación sin tocar lógica fiscal.
