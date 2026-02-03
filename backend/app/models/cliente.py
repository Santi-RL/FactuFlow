"""Modelo Cliente - Receptor de facturas."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base


class Cliente(Base):
    """Modelo de Cliente receptor de comprobantes."""
    
    __tablename__ = "clientes"
    
    id = Column(Integer, primary_key=True, index=True)
    razon_social = Column(String(255), nullable=False)
    tipo_documento = Column(String(20), nullable=False)  # CUIT, CUIL, DNI, etc.
    numero_documento = Column(String(20), nullable=False)
    condicion_iva = Column(String(50), nullable=False)  # RI, Monotributo, CF, Exento
    domicilio = Column(String(255), nullable=True)
    localidad = Column(String(100), nullable=True)
    provincia = Column(String(100), nullable=True)
    codigo_postal = Column(String(10), nullable=True)
    email = Column(String(255), nullable=True)
    telefono = Column(String(50), nullable=True)
    notas = Column(String(500), nullable=True)
    activo = Column(Boolean, default=True, nullable=False)
    
    # Relación con empresa
    empresa_id = Column(Integer, ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False)
    empresa = relationship("Empresa", back_populates="clientes")
    
    # Relación con comprobantes
    comprobantes = relationship("Comprobante", back_populates="cliente")
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __repr__(self) -> str:
        return f"<Cliente {self.razon_social} - {self.tipo_documento}: {self.numero_documento}>"
