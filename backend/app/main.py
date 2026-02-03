# FactuFlow Backend
# Sistema de Facturación Electrónica Argentina (AFIP)

from fastapi import FastAPI

app = FastAPI(
    title="FactuFlow API",
    description="Sistema de Facturación Electrónica AFIP - Argentina",
    version="0.1.0"
)


@app.get("/")
async def root():
    """Endpoint raíz."""
    return {
        "message": "FactuFlow API",
        "version": "0.1.0",
        "status": "En desarrollo"
    }


@app.get("/health")
async def health():
    """Health check para Docker."""
    return {"status": "healthy"}
