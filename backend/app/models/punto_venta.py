"""Modelo PuntoVenta - Puntos de venta de la empresa."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base


class PuntoVenta(Base):
    """Modelo de Punto de Venta."""

    __tablename__ = "puntos_venta"

    id = Column(Integer, primary_key=True, index=True)
    numero = Column(Integer, nullable=False)  # 1-99999
    nombre = Column(String(255), nullable=True)  # ej: "Sucursal Centro"
    activo = Column(Boolean, default=True, nullable=False)

    # Relación con empresa
    empresa_id = Column(
        Integer, ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    empresa = relationship("Empresa", back_populates="puntos_venta")

    # Relación con comprobantes
    comprobantes = relationship("Comprobante", back_populates="punto_venta")

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<PuntoVenta {self.numero} - {self.nombre or 'Sin nombre'}>"
