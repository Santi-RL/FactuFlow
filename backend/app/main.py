# FactuFlow Backend
# Sistema de Facturación Electrónica Argentina (AFIP)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine, Base
from app.api import health, auth, empresas, clientes, puntos_venta, certificados, arca, comprobantes, pdf, reportes

app = FastAPI(
    title="FactuFlow API",
    description="Sistema de Facturación Electrónica AFIP - Argentina",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
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
app.include_router(puntos_venta.router, prefix="/api/puntos-venta", tags=["Puntos de Venta"])
app.include_router(certificados.router, prefix="/api/certificados", tags=["Certificados"])
app.include_router(arca.router, prefix="/api/arca", tags=["ARCA"])
app.include_router(comprobantes.router, prefix="/api/comprobantes", tags=["Comprobantes"])
app.include_router(pdf.router, prefix="/api/pdf", tags=["PDF"])
app.include_router(reportes.router, prefix="/api/reportes", tags=["Reportes"])


@app.on_event("startup")
async def startup():
    """Crear tablas en la base de datos al iniciar (solo desarrollo)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.get("/")
async def root():
    """Endpoint raíz."""
    return {
        "message": "FactuFlow API",
        "version": "0.1.0",
        "docs": "/api/docs"
    }
