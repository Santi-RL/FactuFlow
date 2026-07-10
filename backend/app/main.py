"""Entrada principal de FactuFlow."""

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

import app.models  # noqa: F401
from app.core.config import settings
from app.core.database import Base, dispose_database_engines, engine
from app.services.lote_worker import ensure_lote_worker_running, stop_lote_worker
from app.api import (
    almacenamiento,
    arca,
    auth,
    certificados,
    clientes,
    comprobantes,
    empresas,
    formatos_importacion,
    health,
    lotes_comprobantes,
    pdf,
    perfiles_carga_masiva,
    puntos_venta,
    reportes,
    usuarios,
)

logger = logging.getLogger(__name__)

CERTIFICATE_UPLOAD_PATH = "/api/certificados/subir-certificado"
CERTIFICATE_UPLOAD_MULTIPART_OVERHEAD_BYTES = 16 * 1024


class CertificateUploadSizeLimitMiddleware:
    """Rechaza uploads de certificados antes del parseo multipart."""

    def __init__(self, app: ASGIApp) -> None:
        """Inicializa el middleware ASGI."""
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Limita el cuerpo HTTP del endpoint de certificados."""
        if not self._debe_limitar(scope):
            await self.app(scope, receive, send)
            return

        max_body_bytes = (
            settings.certificate_max_upload_bytes
            + CERTIFICATE_UPLOAD_MULTIPART_OVERHEAD_BYTES
        )
        if self._content_length_supera_limite(scope, max_body_bytes):
            await self._rechazar(scope, receive, send)
            return

        mensajes: list[Message] = []
        total = 0
        while True:
            message = await receive()
            mensajes.append(message)
            if message["type"] != "http.request":
                break

            total += len(message.get("body", b""))
            if total > max_body_bytes:
                await self._rechazar(scope, receive, send)
                return
            if not message.get("more_body", False):
                break

        async def replay_receive() -> Message:
            if mensajes:
                return mensajes.pop(0)
            return {"type": "http.request", "body": b"", "more_body": False}

        await self.app(scope, replay_receive, send)

    def _debe_limitar(self, scope: Scope) -> bool:
        """Indica si el request corresponde al upload de certificados."""
        return (
            scope["type"] == "http"
            and scope.get("method") == "POST"
            and scope.get("path") == CERTIFICATE_UPLOAD_PATH
        )

    def _content_length_supera_limite(self, scope: Scope, max_body_bytes: int) -> bool:
        """Evalúa Content-Length antes de recibir el cuerpo del request."""
        headers = dict(scope.get("headers") or [])
        raw_content_length = headers.get(b"content-length")
        if raw_content_length is None:
            return False
        try:
            content_length = int(raw_content_length.decode("ascii"))
        except ValueError:
            return False
        return content_length > max_body_bytes

    async def _rechazar(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Devuelve una respuesta 413 uniforme para certificados grandes."""
        response = JSONResponse(
            status_code=413,
            content={
                "detail": "El certificado supera el tamaño máximo permitido",
            },
        )
        await response(scope, receive, send)


def configure_logging() -> None:
    """Configura logging básico para desarrollo y producción."""
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if settings.log_file:
        log_path = Path(settings.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        handlers=handlers,
        force=True,
    )


configure_logging()

app = FastAPI(
    title="FactuFlow API",
    description="Sistema de Facturación Electrónica ARCA - Argentina",
    version=settings.app_version,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)


async def database_temporarily_unavailable_handler(
    _request: Request,
    exc: Exception,
) -> JSONResponse:
    """Devuelve un 503 sanitizado ante saturación o desconexión de base."""
    logger.warning(
        "event=database_temporarily_unavailable type_error=%s",
        type(exc).__name__,
    )
    return JSONResponse(
        status_code=503,
        content={
            "detail": (
                "La base de datos está temporalmente no disponible. "
                "Intentá nuevamente en unos segundos."
            )
        },
        headers={"Retry-After": "2"},
    )


app.add_exception_handler(
    SQLAlchemyTimeoutError,
    database_temporarily_unavailable_handler,
)
app.add_exception_handler(
    OperationalError,
    database_temporarily_unavailable_handler,
)
app.add_middleware(CertificateUploadSizeLimitMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health.router, prefix="/api/health", tags=["Health"])
app.include_router(auth.router, prefix="/api/auth", tags=["Autenticación"])
app.include_router(usuarios.router, prefix="/api/usuarios", tags=["Usuarios"])
app.include_router(empresas.router, prefix="/api/empresas", tags=["Empresas"])
app.include_router(clientes.router, prefix="/api/clientes", tags=["Clientes"])
app.include_router(
    puntos_venta.router, prefix="/api/puntos-venta", tags=["Puntos de Venta"]
)
app.include_router(
    certificados.router, prefix="/api/certificados", tags=["Certificados"]
)
app.include_router(arca.router, prefix="/api/arca", tags=["ARCA"])
app.include_router(
    comprobantes.router, prefix="/api/comprobantes", tags=["Comprobantes"]
)
app.include_router(
    lotes_comprobantes.router,
    prefix="/api/lotes-comprobantes",
    tags=["Lotes de comprobantes"],
)
app.include_router(
    perfiles_carga_masiva.router,
    prefix="/api/perfiles-carga-masiva",
    tags=["Perfiles de carga masiva"],
)
app.include_router(
    formatos_importacion.router,
    prefix="/api/formatos-importacion",
    tags=["Formatos de importación"],
)
app.include_router(pdf.router, prefix="/api/pdf", tags=["PDF"])
app.include_router(reportes.router, prefix="/api/reportes", tags=["Reportes"])
app.include_router(
    almacenamiento.router,
    prefix="/api/almacenamiento",
    tags=["Almacenamiento"],
)


@app.on_event("startup")
async def startup():
    """Inicializa recursos de aplicacion."""
    if settings.app_env.lower() in {"test", "testing"}:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    app.state.lotes_background_tasks = set()
    ensure_lote_worker_running(app)


@app.on_event("shutdown")
async def shutdown():
    """Detiene tareas de background de forma ordenada."""
    await stop_lote_worker(app)
    await dispose_database_engines()


@app.get("/")
async def root():
    """Endpoint raíz."""
    return {
        "message": "FactuFlow API",
        "version": settings.app_version,
        "docs": "/api/docs",
    }
