"""Modelo Usuario - Usuarios del sistema."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base


class Usuario(Base):
    """Modelo de Usuario del sistema."""
    
    __tablename__ = "usuarios"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    nombre = Column(String(255), nullable=False)
    activo = Column(Boolean, default=True, nullable=False)
    es_admin = Column(Boolean, default=False, nullable=False)
    
    # Relación con empresa (nullable para superadmin)
    empresa_id = Column(Integer, ForeignKey("empresas.id", ondelete="CASCADE"), nullable=True)
    empresa = relationship("Empresa", back_populates="usuarios")
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    ultimo_login = Column(DateTime, nullable=True)
    
    def __repr__(self) -> str:
        return f"<Usuario {self.email}>"
