"""Modelos para perfiles de carga masiva por emisor."""

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class PerfilCargaMasiva(Base):
    """Configuración reutilizable para precargar la emisión masiva."""

    __tablename__ = "perfiles_carga_masiva"
    __table_args__ = (
        UniqueConstraint(
            "empresa_id",
            "nombre",
            name="uq_perfiles_carga_masiva_empresa_nombre",
        ),
        Index(
            "ix_perfiles_carga_masiva_empresa_activo",
            "empresa_id",
            "activo",
        ),
        Index(
            "uq_perfiles_carga_masiva_predeterminado_activo",
            "empresa_id",
            unique=True,
            sqlite_where=text("es_predeterminado = 1 AND activo = 1"),
            postgresql_where=text("es_predeterminado IS TRUE AND activo IS TRUE"),
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(120), nullable=False)
    descripcion = Column(Text, nullable=True)
    configuracion_json = Column(JSON, nullable=False)
    es_predeterminado = Column(Boolean, nullable=False, default=False)
    activo = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    empresa_id = Column(
        Integer, ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )

    empresa = relationship("Empresa", back_populates="perfiles_carga_masiva")
