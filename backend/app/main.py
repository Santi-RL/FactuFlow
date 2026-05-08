"""Entrada principal de FactuFlow."""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models  # noqa: F401
from app.core.config import settings
from app.core.database import engine, Base
from app.services.lote_worker import ensure_lote_worker_running, stop_lote_worker
from app.api import (
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
    puntos_venta,
    reportes,
)


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
    formatos_importacion.router,
    prefix="/api/formatos-importacion",
    tags=["Formatos de importación"],
)
app.include_router(pdf.router, prefix="/api/pdf", tags=["PDF"])
app.include_router(reportes.router, prefix="/api/reportes", tags=["Reportes"])


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


@app.get("/")
async def root():
    """Endpoint raíz."""
    return {
        "message": "FactuFlow API",
        "version": settings.app_version,
        "docs": "/api/docs",
    }
