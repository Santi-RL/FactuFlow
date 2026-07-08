"""Modelos para formatos configurables de importación."""

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
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class FormatoImportacion(Base):
    """Representa un formato reutilizable para interpretar archivos externos."""

    __tablename__ = "formatos_importacion"
    __table_args__ = (
        Index("ix_formatos_importacion_empresa", "empresa_id", "activo"),
        Index("ix_formatos_importacion_alcance", "alcance", "activo"),
    )

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(120), nullable=False)
    descripcion = Column(Text, nullable=True)
    alcance = Column(String(20), nullable=False, default="emisor")
    activo = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    empresa_id = Column(
        Integer, ForeignKey("empresas.id", ondelete="RESTRICT"), nullable=True
    )

    empresa = relationship("Empresa")
    versiones = relationship(
        "FormatoImportacionVersion",
        back_populates="formato",
        cascade="all, delete-orphan",
        order_by="FormatoImportacionVersion.version.desc()",
    )


class FormatoImportacionVersion(Base):
    """Versiona la configuración efectiva usada para importar un archivo."""

    __tablename__ = "formatos_importacion_versiones"
    __table_args__ = (
        UniqueConstraint(
            "formato_id",
            "version",
            name="uq_formatos_importacion_versiones_formato_version",
        ),
        Index(
            "ix_formatos_importacion_versiones_formato_estado",
            "formato_id",
            "estado",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    version = Column(Integer, nullable=False, default=1)
    estado = Column(String(20), nullable=False, default="vigente")
    configuracion_json = Column(JSON, nullable=False)
    headers_firma_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    formato_id = Column(
        Integer,
        ForeignKey("formatos_importacion.id", ondelete="CASCADE"),
        nullable=False,
    )

    formato = relationship("FormatoImportacion", back_populates="versiones")
    campos = relationship(
        "FormatoImportacionCampo",
        back_populates="version",
        cascade="all, delete-orphan",
        order_by="FormatoImportacionCampo.id",
    )
    reglas = relationship(
        "FormatoImportacionRegla",
        back_populates="version",
        cascade="all, delete-orphan",
        order_by="FormatoImportacionRegla.orden",
    )


class FormatoImportacionCampo(Base):
    """Mapeo declarativo entre una columna externa y un campo FactuFlow."""

    __tablename__ = "formatos_importacion_campos"
    __table_args__ = (
        UniqueConstraint(
            "version_id",
            "campo_destino",
            name="uq_formatos_importacion_campos_version_campo",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    campo_destino = Column(String(100), nullable=False)
    origen_tipo = Column(String(20), nullable=False)
    encabezado = Column(String(255), nullable=True)
    alias_json = Column(JSON, nullable=True)
    letra_columna = Column(String(10), nullable=True)
    indice_columna = Column(Integer, nullable=True)
    valor_constante_json = Column(JSON, nullable=True)
    requerido = Column(Boolean, nullable=False, default=False)
    transformacion = Column(String(50), nullable=True)
    valor_default_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    version_id = Column(
        Integer,
        ForeignKey("formatos_importacion_versiones.id", ondelete="CASCADE"),
        nullable=False,
    )

    version = relationship("FormatoImportacionVersion", back_populates="campos")


class FormatoImportacionRegla(Base):
    """Regla adicional aplicada al interpretar un formato de importación."""

    __tablename__ = "formatos_importacion_reglas"
    __table_args__ = (
        Index("ix_formatos_importacion_reglas_version", "version_id", "activo"),
    )

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(120), nullable=False)
    tipo = Column(String(50), nullable=False)
    configuracion_json = Column(JSON, nullable=True)
    orden = Column(Integer, nullable=False, default=0)
    activo = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    version_id = Column(
        Integer,
        ForeignKey("formatos_importacion_versiones.id", ondelete="CASCADE"),
        nullable=False,
    )

    version = relationship("FormatoImportacionVersion", back_populates="reglas")
