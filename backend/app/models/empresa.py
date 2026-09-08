"""Modelo Empresa - Datos del emisor de facturas."""

from datetime import datetime
from sqlalchemy import (
    CheckConstraint,
    Column,
    Integer,
    String,
    Date,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class Empresa(Base):
    """Modelo de Empresa emisora de comprobantes."""

    __tablename__ = "empresas"

    id = Column(Integer, primary_key=True, index=True)
    razon_social = Column(String(255), nullable=False)
    cuit = Column(String(11), unique=True, index=True, nullable=False)
    condicion_iva = Column(String(50), nullable=False)  # RI, Monotributo, Exento
    ingresos_brutos = Column(String(50), nullable=True)
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
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relaciones
    usuarios = relationship("Usuario", back_populates="empresa", passive_deletes=True)
    accesos_usuarios = relationship(
        "UsuarioEmisorAcceso",
        back_populates="empresa",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    clientes = relationship("Cliente", back_populates="empresa", passive_deletes=True)
    puntos_venta = relationship(
        "PuntoVenta", back_populates="empresa", passive_deletes=True
    )
    certificados = relationship(
        "Certificado", back_populates="empresa", passive_deletes=True
    )
    comprobantes = relationship(
        "Comprobante", back_populates="empresa", passive_deletes=True
    )
    lotes_comprobantes = relationship(
        "LoteComprobante", back_populates="empresa", passive_deletes=True
    )
    perfiles_carga_masiva = relationship(
        "PerfilCargaMasiva", back_populates="empresa", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<Empresa {self.razon_social} - CUIT: {self.cuit}>"


class LoteDuplicadosCoordinacion(Base):
    """Serializa decisiones de duplicados por emisor y ambiente."""

    __tablename__ = "lotes_duplicados_coordinacion"
    __table_args__ = (
        CheckConstraint(
            "ambiente IN ('homologacion', 'produccion')",
            name="ck_lotes_duplicados_coordinacion_ambiente",
        ),
    )

    empresa_id = Column(
        Integer,
        ForeignKey("empresas.id", ondelete="CASCADE"),
        primary_key=True,
    )
    ambiente = Column(String(20), primary_key=True)
    revision = Column(Integer, nullable=False, default=0)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
