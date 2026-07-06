# Estructura del repositorio

Este documento describe dónde vive cada tipo de archivo y qué se espera en cada carpeta. Si agregás nuevas áreas o submódulos, actualizá este archivo y el índice en `docs/agents/README.md`.

## Reglas de organización
1. Todo archivo nuevo debe ir en la carpeta correspondiente según su propósito.
2. Si se crea una nueva carpeta relevante, registrar la estructura aquí.
3. Mantener la nomenclatura ARCA (AFIP solo en URLs/variables legacy).

## Raíz del repositorio
- `backend/`: aplicación FastAPI y lógica de negocio.
- `frontend/`: aplicación Vue 3 (UI).
- `docs/`: documentación técnica, funcional y operativa.
- `scripts/`: scripts auxiliares de desarrollo o mantenimiento.
- `certs/`: certificados locales (gitignored).
- `data/`: datos locales, DBs o artefactos temporales (gitignored).
- `.env.example`: variables de entorno de referencia.
- `docker-compose.yml`: orquestación local con Docker.
- `FactuFlow Local.vbs`: acceso local Windows sin consola visible con launcher
  en tray para desarrollo/QA.
- `FactuFlow Local.cmd`: acceso de compatibilidad que delega en el launcher
  oculto.
- `run-local.ps1`: helper para correr el proyecto en Windows.
- `README.md`: overview público del proyecto.
- `AGENTS.md`: guía rápida para agentes.

## Backend
- `backend/app/main.py`: entrada de FastAPI y registro de routers.
- `backend/app/api/`: endpoints REST por dominio.
- `backend/app/api/lotes_comprobantes.py`: endpoints de emisión masiva por Excel.
- `backend/app/api/almacenamiento.py`: endpoints administrativos de uso,
  resguardo y limpieza segura de almacenamiento.
- `backend/app/api/formatos_importacion.py`: endpoints de formatos configurables para importar Excel externos.
- `backend/app/api/perfiles_carga_masiva.py`: endpoints de perfiles de carga
  masiva por emisor.
- `backend/app/arca/`: integración ARCA (WSAA, WSFEv1, SOAP, crypto, cache, utils).
- `backend/app/afip/`: legacy (mantener solo compatibilidad).
- `backend/app/core/`: configuración, seguridad y utilidades base.
- `backend/app/models/`: modelos ORM.
- `backend/app/schemas/`: esquemas Pydantic.
- `backend/app/services/`: servicios de negocio.
- `backend/app/models/formato_importacion.py`: modelos versionados de formatos, campos y reglas de importación.
- `backend/app/models/perfil_carga_masiva.py`: perfiles de carga masiva por emisor.
- `backend/app/models/evento_sistema.py`: auditoría administrativa y
  exportaciones de almacenamiento.
- `backend/app/models/idempotencia_fiscal.py`: operaciones idempotentes e
  intentos fiscales durables para emisión ARCA segura.
- `backend/app/schemas/formato_importacion.py`: contratos de formatos, deteccion y candidatos.
- `backend/app/schemas/perfil_carga_masiva.py`: contratos de perfiles de carga masiva.
- `backend/app/schemas/almacenamiento.py`: contratos del gestor de
  almacenamiento.
- `backend/app/services/formatos_importacion_service.py`: deteccion, resolución de mapeos y normalizacion de archivos externos.
- `backend/app/services/idempotencia_fiscal_service.py`: idempotencia fiscal,
  reserva de numeración activa, deduplicación lógica y reconciliación de
  intentos.
- `backend/app/services/perfiles_carga_masiva_service.py`: CRUD, scoping y validación de perfiles de carga masiva.
- `backend/app/services/almacenamiento_service.py`: cálculo acotado de uso,
  ZIPs de resguardo y limpieza confirmada.
- `backend/app/services/lote_worker.py`: worker reanudable de lotes grandes.
- `backend/app/scripts/create_admin_user.py`: alta/promocion de usuario administrador.
- `backend/app/templates/`: plantillas (PDF/HTML).
- `backend/tests/`: tests del backend.
- `backend/tests/test_arca/`: tests específicos de ARCA.

## Frontend
- `frontend/src/main.ts`: bootstrap de la app.
- `frontend/src/router/`: rutas.
- `frontend/src/views/`: vistas por dominio.
- `frontend/src/components/`: componentes por dominio y layout.
- `frontend/src/components/ui/`: componentes base `Base*`.
- `frontend/src/composables/`: hooks de Composition API.
- `frontend/src/services/`: acceso a API.
- `frontend/src/services/lotes-comprobantes.service.ts`: cliente HTTP de lotes.
- `frontend/src/services/almacenamiento.service.ts`: cliente HTTP del gestor
  administrativo de almacenamiento.
- `frontend/src/services/formatos-importacion.service.ts`: cliente HTTP para listar y detectar formatos de importación.
- `frontend/src/services/perfiles-carga-masiva.service.ts`: cliente HTTP de perfiles de carga masiva.
- `frontend/src/stores/`: estado global (Pinia).
- `frontend/src/types/`: tipos compartidos.
- `frontend/src/types/lote-comprobante.ts`: tipos del flujo de lotes.
- `frontend/src/types/almacenamiento.ts`: tipos del gestor de almacenamiento.
- `frontend/src/types/formato-importacion.ts`: tipos de formatos, versiones y candidatos detectados.
- `frontend/src/types/perfil-carga-masiva.ts`: tipos de perfiles de carga masiva.
- `frontend/src/assets/`: estáticos.

## Documentación
- `docs/agents/`: instrucciones operativas para agentes.
- `docs/agents/README.md`: índice de documentación y guía de búsqueda.
- `docs/agents/overview.md`: resumen y arquitectura.
- `docs/agents/arca.md`: integración ARCA y nomenclatura legacy.
- `docs/arca-ws/`: descargas locales de documentación oficial ARCA WS (gitignored).
- `docs/api/`: referencia de API REST.
- `docs/certificates/`: manejo de certificados.
- `docs/setup/`: instalación y puesta en marcha.
- `docs/user-guide/`: manual de usuario.
- `docs/arca-integration.md`: integración ARCA detallada.
- `docs/certificados-wizard.md`: wizard de certificados.
- `docs/FASE_6_PDF_REPORTES.md`: PDFs y reportes.
