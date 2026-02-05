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
- `run-local.ps1`: helper para correr el proyecto en Windows.
- `README.md`: overview público del proyecto.
- `AGENTS.md`: guía rápida para agentes.

## Backend
- `backend/app/main.py`: entrada de FastAPI y registro de routers.
- `backend/app/api/`: endpoints REST por dominio.
- `backend/app/arca/`: integración ARCA (WSAA, WSFEv1, crypto, cache, utils).
- `backend/app/afip/`: legacy (mantener solo compatibilidad).
- `backend/app/core/`: configuración, seguridad y utilidades base.
- `backend/app/models/`: modelos ORM.
- `backend/app/schemas/`: esquemas Pydantic.
- `backend/app/services/`: servicios de negocio.
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
- `frontend/src/stores/`: estado global (Pinia).
- `frontend/src/types/`: tipos compartidos.
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
