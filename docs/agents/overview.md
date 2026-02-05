# Resumen del proyecto

## Descripción
- FactuFlow es un sistema de facturación electrónica para Argentina.
- El objetivo es ser liviano, self-hosted y fácil de usar.
- La integración principal es con ARCA (nomenclatura legacy AFIP en endpoints).

## Arquitectura
- Frontend: Vue 3 + Tailwind, servido por Vite.
- Backend: FastAPI con API REST.
- DB: SQLite por defecto, PostgreSQL opcional.
- Servicios externos: WSAA y WSFEv1 de ARCA.

## Stack principal
- Backend: FastAPI, SQLAlchemy, Pydantic, Uvicorn, Zeep o cliente SOAP equivalente.
- Frontend: Vue 3, Pinia, Vue Router, Axios, Tailwind, Vite.
- Infra: Docker y Docker Compose.

## Idioma y mensajes
- UI y documentación de usuario en español (Argentina).
- Código en inglés o español, docstrings preferiblemente en español.

## Principios de diseño
- Simplicidad primero.
- Usuario no técnico en mente.
- Seguridad por defecto.
- Self-hosted friendly.
- Documentación abundante.

## Recursos
- AFIP/ARCA Dev: `docs/agents/arca.md`
- Certificados: `docs/certificates/README.md`
- Estructura del repo: `docs/agents/structure.md`
