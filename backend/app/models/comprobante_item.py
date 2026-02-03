"""Modelo ComprobanteItem - Líneas de detalle de comprobantes."""

from decimal import Decimal
from sqlalchemy import Column, Integer, String, Numeric, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base


class ComprobanteItem(Base):
    """Modelo de Item/Línea de Comprobante."""
    
    __tablename__ = "comprobante_items"
    
    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(50), nullable=True)  # Código de producto (opcional)
    descripcion = Column(String(500), nullable=False)
    cantidad = Column(Numeric(10, 4), nullable=False)
    unidad = Column(String(50), default="unidades", nullable=False)
    precio_unitario = Column(Numeric(12, 4), nullable=False)
    descuento_porcentaje = Column(Numeric(5, 2), default=0, nullable=False)
    iva_porcentaje = Column(Numeric(5, 2), nullable=False)  # 21, 10.5, 27, 0
    subtotal = Column(Numeric(12, 2), nullable=False)
    orden = Column(Integer, nullable=False)  # Para mantener orden de líneas
    
    # Relación con comprobante
    comprobante_id = Column(Integer, ForeignKey("comprobantes.id", ondelete="CASCADE"), nullable=False)
    comprobante = relationship("Comprobante", back_populates="items")
    
    def __repr__(self) -> str:
        return f"<ComprobanteItem {self.descripcion} - Cantidad: {self.cantidad} - Subtotal: ${self.subtotal}>"
