"""Modelo Empresa - Datos del emisor de facturas."""

from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Date, DateTime
from sqlalchemy.orm import relationship

from app.core.database import Base


class Empresa(Base):
    """Modelo de Empresa emisora de comprobantes."""
    
    __tablename__ = "empresas"
    
    id = Column(Integer, primary_key=True, index=True)
    razon_social = Column(String(255), nullable=False)
    cuit = Column(String(11), unique=True, index=True, nullable=False)
    condicion_iva = Column(String(50), nullable=False)  # RI, Monotributo, Exento
    domicilio = Column(String(255), nullable=False)
    localidad = Column(String(100), nullable=False)
    provincia = Column(String(100), nullable=False)
    codigo_postal = Column(String(10), nullable=False)
    email = Column(String(255), nullable=True)
    telefono = Column(String(50), nullable=True)
    inicio_actividades = Column(Date, nullable=False)
    logo = Column(String(255), nullable=True)  # Path al archivo de logo
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relaciones
    usuarios = relationship("Usuario", back_populates="empresa", cascade="all, delete-orphan")
    clientes = relationship("Cliente", back_populates="empresa", cascade="all, delete-orphan")
    puntos_venta = relationship("PuntoVenta", back_populates="empresa", cascade="all, delete-orphan")
    certificados = relationship("Certificado", back_populates="empresa", cascade="all, delete-orphan")
    comprobantes = relationship("Comprobante", back_populates="empresa", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Empresa {self.razon_social} - CUIT: {self.cuit}>"
