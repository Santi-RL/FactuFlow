"""Asignaciones explícitas de usuarios a emisores."""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class UsuarioEmisorAcceso(Base):
    """Autoridad persistida para que un operador pueda usar un emisor."""

    __tablename__ = "usuario_emisor_acceso"
    __table_args__ = (
        CheckConstraint(
            "origen IN ('migracion_legacy', 'asignacion_admin', 'creacion_propia')",
            name="ck_usuario_emisor_acceso_origen",
        ),
        Index("ix_usuario_emisor_acceso_empresa", "empresa_id", "usuario_id"),
    )

    usuario_id = Column(
        Integer,
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        primary_key=True,
    )
    empresa_id = Column(
        Integer,
        ForeignKey("empresas.id", ondelete="CASCADE"),
        primary_key=True,
    )
    otorgado_por_usuario_id = Column(
        Integer,
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True,
    )
    origen = Column(String(30), nullable=False)
    otorgado_en = Column(DateTime, default=datetime.utcnow, nullable=False)

    usuario = relationship(
        "Usuario",
        back_populates="accesos_emisores",
        foreign_keys=[usuario_id],
    )
    empresa = relationship("Empresa", back_populates="accesos_usuarios")
    otorgado_por = relationship("Usuario", foreign_keys=[otorgado_por_usuario_id])
