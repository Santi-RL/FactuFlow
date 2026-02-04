"""Modelo Certificado - Metadatos de certificados AFIP."""

from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Date, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base


class Certificado(Base):
    """Modelo de Certificado AFIP (solo metadatos, no el archivo)."""

    __tablename__ = "certificados"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(255), nullable=False)  # Identificador amigable
    cuit = Column(String(11), nullable=False)  # CUIT asociado al certificado
    fecha_emision = Column(Date, nullable=False)
    fecha_vencimiento = Column(Date, nullable=False)
    archivo_crt = Column(String(255), nullable=False)  # Path relativo en /certs
    archivo_key = Column(String(255), nullable=False)  # Path relativo en /certs
    activo = Column(Boolean, default=True, nullable=False)
    ambiente = Column(String(20), nullable=False)  # homologacion/produccion

    # Relación con empresa
    empresa_id = Column(
        Integer, ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    empresa = relationship("Empresa", back_populates="certificados")

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<Certificado {self.nombre} - CUIT: {self.cuit} - {self.ambiente}>"
