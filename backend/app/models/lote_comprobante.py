"""Modelos para emisión masiva de comprobantes."""

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class LoteComprobante(Base):
    """Representa un archivo cargado para emisión masiva."""

    __tablename__ = "lotes_comprobantes"
    __table_args__ = (
        UniqueConstraint(
            "empresa_id",
            "archivo_hash",
            name="uq_lotes_comprobantes_empresa_hash",
        ),
        Index("ix_lotes_comprobantes_empresa_estado", "empresa_id", "estado"),
        Index("ix_lotes_comprobantes_hash", "empresa_id", "archivo_hash"),
    )

    id = Column(Integer, primary_key=True, index=True)
    nombre_archivo = Column(String(255), nullable=False)
    archivo_hash = Column(String(64), nullable=False)
    estado = Column(String(30), nullable=False, default="cargado")
    modo_procesamiento = Column(String(20), nullable=False, default="sincronico")
    procesamiento_async = Column(Boolean, nullable=False, default=False)
    total_filas = Column(Integer, nullable=False, default=0)
    total_grupos = Column(Integer, nullable=False, default=0)
    grupos_validos = Column(Integer, nullable=False, default=0)
    grupos_con_error = Column(Integer, nullable=False, default=0)
    grupos_emitidos = Column(Integer, nullable=False, default=0)
    grupos_fallidos = Column(Integer, nullable=False, default=0)
    mensaje_resumen = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    mapeo_usado_json = Column(JSON, nullable=True)
    headers_detectados_json = Column(JSON, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    empresa_id = Column(
        Integer, ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    usuario_id = Column(
        Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    formato_importacion_id = Column(
        Integer,
        ForeignKey("formatos_importacion.id", ondelete="SET NULL"),
        nullable=True,
    )
    formato_importacion_version_id = Column(
        Integer,
        ForeignKey("formatos_importacion_versiones.id", ondelete="SET NULL"),
        nullable=True,
    )

    empresa = relationship("Empresa", back_populates="lotes_comprobantes")
    usuario = relationship("Usuario", back_populates="lotes_comprobantes")
    formato_importacion = relationship("FormatoImportacion")
    formato_importacion_version = relationship("FormatoImportacionVersion")
    grupos = relationship(
        "LoteComprobanteGrupo",
        back_populates="lote",
        cascade="all, delete-orphan",
        order_by="LoteComprobanteGrupo.orden",
    )
    filas = relationship(
        "LoteComprobanteFila",
        back_populates="lote",
        cascade="all, delete-orphan",
        order_by="LoteComprobanteFila.fila_excel",
    )


class LoteComprobanteGrupo(Base):
    """Representa un comprobante agrupado dentro de un lote."""

    __tablename__ = "lotes_comprobantes_grupos"
    __table_args__ = (
        UniqueConstraint(
            "lote_id",
            "comprobante_ref",
            name="uq_lotes_comprobantes_grupos_lote_ref",
        ),
        Index("ix_lotes_comprobantes_grupos_lote_ref", "lote_id", "comprobante_ref"),
    )

    id = Column(Integer, primary_key=True, index=True)
    comprobante_ref = Column(String(100), nullable=False)
    orden = Column(Integer, nullable=False, default=0)
    estado = Column(String(30), nullable=False, default="cargado")
    tipo_comprobante = Column(Integer, nullable=True)
    punto_venta_numero = Column(Integer, nullable=True)
    cliente_documento = Column(String(20), nullable=True)
    cliente_razon_social = Column(String(255), nullable=True)
    total_estimado = Column(Numeric(12, 2), nullable=False, default=0)
    payload_json = Column(JSON, nullable=True)
    mensajes_json = Column(JSON, nullable=True)
    cae = Column(String(14), nullable=True)
    numero_asignado = Column(Integer, nullable=True)
    comprobante_id = Column(
        Integer, ForeignKey("comprobantes.id", ondelete="SET NULL"), nullable=True
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    lote_id = Column(
        Integer, ForeignKey("lotes_comprobantes.id", ondelete="CASCADE"), nullable=False
    )

    lote = relationship("LoteComprobante", back_populates="grupos")
    filas = relationship(
        "LoteComprobanteFila",
        back_populates="grupo",
        cascade="all, delete-orphan",
        order_by="LoteComprobanteFila.fila_excel",
    )
    comprobante = relationship("Comprobante")


class LoteComprobanteFila(Base):
    """Representa una fila individual del Excel importado."""

    __tablename__ = "lotes_comprobantes_filas"
    __table_args__ = (
        Index("ix_lotes_comprobantes_filas_lote_fila", "lote_id", "fila_excel"),
    )

    id = Column(Integer, primary_key=True, index=True)
    fila_excel = Column(Integer, nullable=False)
    comprobante_ref = Column(String(100), nullable=False)
    estado = Column(String(30), nullable=False, default="cargado")
    datos_json = Column(JSON, nullable=True)
    mensajes_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    lote_id = Column(
        Integer, ForeignKey("lotes_comprobantes.id", ondelete="CASCADE"), nullable=False
    )
    grupo_id = Column(
        Integer,
        ForeignKey("lotes_comprobantes_grupos.id", ondelete="CASCADE"),
        nullable=False,
    )

    lote = relationship("LoteComprobante", back_populates="filas")
    grupo = relationship("LoteComprobanteGrupo", back_populates="filas")
