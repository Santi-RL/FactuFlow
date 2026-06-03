"""Modelos de auditoría operativa del sistema."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class EventoSistema(Base):
    """Registra acciones administrativas de mantenimiento y diagnóstico."""

    __tablename__ = "eventos_sistema"

    id = Column(Integer, primary_key=True, index=True)
    accion = Column(String(80), nullable=False)
    categoria = Column(String(50), nullable=False)
    estado = Column(String(30), nullable=False, default="exitoso")
    descripcion = Column(Text, nullable=True)
    bytes_afectados = Column(BigInteger, nullable=False, default=0)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    usuario_id = Column(
        Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    empresa_id = Column(
        Integer, ForeignKey("empresas.id", ondelete="SET NULL"), nullable=True
    )

    usuario = relationship("Usuario")
    empresa = relationship("Empresa")


class ExportacionAlmacenamiento(Base):
    """Representa un paquete descargable creado antes de liberar almacenamiento."""

    __tablename__ = "exportaciones_almacenamiento"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(64), unique=True, index=True, nullable=False)
    estado = Column(String(30), nullable=False, default="pendiente_descarga")
    categoria = Column(String(50), nullable=False, default="mixta")
    archivo_nombre = Column(String(255), nullable=False)
    checksum_sha256 = Column(String(64), nullable=False)
    size_bytes = Column(BigInteger, nullable=False, default=0)
    seleccion_json = Column(JSON, nullable=True)
    manifest_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    downloaded_at = Column(DateTime, nullable=True)
    released_at = Column(DateTime, nullable=True)

    usuario_id = Column(
        Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )

    usuario = relationship("Usuario")
