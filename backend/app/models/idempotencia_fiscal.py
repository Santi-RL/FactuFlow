"""Modelos de idempotencia e intentos fiscales."""

from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


ESTADOS_INTENTO_FISCAL = (
    "autorizado",
    "en_proceso",
    "fallido_verificado",
    "rechazado_arca",
    "requiere_reconciliacion",
)
ESTADOS_RESERVA_FISCAL_ACTIVA = (
    "autorizado",
    "en_proceso",
    "requiere_reconciliacion",
)
ESTADOS_INTENTO_FISCAL_BLOQUEANTES = (
    "en_proceso",
    "requiere_reconciliacion",
)
_ESTADOS_INTENTO_FISCAL_SQL = ", ".join(
    f"'{estado}'" for estado in ESTADOS_INTENTO_FISCAL
)
PREDICADO_RESERVA_FISCAL_ACTIVA = (
    "numero_planificado IS NOT NULL AND estado IN ("
    f"{', '.join(repr(estado) for estado in ESTADOS_RESERVA_FISCAL_ACTIVA)}"
    ")"
)


class OperacionIdempotente(Base):
    """Representa una operación fiscal protegida por idempotencia."""

    __tablename__ = "operaciones_idempotentes"
    __table_args__ = (
        UniqueConstraint(
            "empresa_id",
            "idempotency_key",
            name="uq_operaciones_idempotentes_empresa_key",
        ),
        Index(
            "ix_operaciones_idempotentes_empresa_estado",
            "empresa_id",
            "estado",
        ),
        Index(
            "ix_operaciones_idempotentes_key",
            "empresa_id",
            "idempotency_key",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    idempotency_key = Column(String(128), nullable=False)
    tipo_operacion = Column(String(50), nullable=False)
    payload_hash = Column(String(64), nullable=False)
    estado = Column(String(40), nullable=False, default="en_proceso")
    response_json = Column(JSON, nullable=True)
    error_json = Column(JSON, nullable=True)
    lote_id = Column(
        Integer,
        ForeignKey("lotes_comprobantes.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    empresa_id = Column(
        Integer, ForeignKey("empresas.id", ondelete="RESTRICT"), nullable=False
    )
    usuario_id = Column(
        Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )

    empresa = relationship("Empresa")
    usuario = relationship("Usuario")
    lote = relationship("LoteComprobante")
    intentos = relationship(
        "IntentoEmisionFiscal",
        back_populates="operacion",
        cascade="all, delete-orphan",
    )


class IntentoEmisionFiscal(Base):
    """Reserva y audita un comprobante fiscal planificado."""

    __tablename__ = "intentos_emision_fiscal"
    __table_args__ = (
        CheckConstraint(
            f"estado IN ({_ESTADOS_INTENTO_FISCAL_SQL})",
            name="ck_intentos_emision_fiscal_estado_valido",
        ),
        Index(
            "uq_intentos_emision_fiscal_reserva_activa",
            "empresa_id",
            "punto_venta_id",
            "tipo_comprobante",
            "numero_planificado",
            unique=True,
            sqlite_where=text(PREDICADO_RESERVA_FISCAL_ACTIVA),
            postgresql_where=text(PREDICADO_RESERVA_FISCAL_ACTIVA),
        ),
        Index(
            "ix_intentos_emision_fiscal_operacion",
            "operacion_id",
            "estado",
        ),
        Index(
            "ix_intentos_emision_fiscal_lote_grupo",
            "lote_id",
            "grupo_id",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    tipo_comprobante = Column(Integer, nullable=False)
    punto_venta_numero = Column(Integer, nullable=False)
    numero_planificado = Column(Integer, nullable=True)
    fecha_emision = Column(Date, nullable=False)
    total = Column(Numeric(12, 2), nullable=False)
    receptor_tipo_documento = Column(Integer, nullable=True)
    receptor_numero_documento = Column(String(20), nullable=True)
    receptor_razon_social = Column(String(255), nullable=True)
    payload_hash = Column(String(64), nullable=False)
    huella_logica = Column(String(64), nullable=False)
    cae = Column(String(14), nullable=True)
    cae_vencimiento = Column(Date, nullable=True)
    estado = Column(String(40), nullable=False, default="en_proceso")
    categoria_error = Column(String(80), nullable=True)
    mensaje = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    operacion_id = Column(
        Integer,
        ForeignKey("operaciones_idempotentes.id", ondelete="CASCADE"),
        nullable=True,
    )
    empresa_id = Column(
        Integer, ForeignKey("empresas.id", ondelete="RESTRICT"), nullable=False
    )
    usuario_id = Column(
        Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    punto_venta_id = Column(
        Integer, ForeignKey("puntos_venta.id", ondelete="RESTRICT"), nullable=False
    )
    comprobante_id = Column(
        Integer, ForeignKey("comprobantes.id", ondelete="SET NULL"), nullable=True
    )
    lote_id = Column(
        Integer,
        ForeignKey("lotes_comprobantes.id", ondelete="SET NULL"),
        nullable=True,
    )
    grupo_id = Column(
        Integer,
        ForeignKey("lotes_comprobantes_grupos.id", ondelete="SET NULL"),
        nullable=True,
    )

    operacion = relationship("OperacionIdempotente", back_populates="intentos")
    empresa = relationship("Empresa")
    usuario = relationship("Usuario")
    punto_venta = relationship("PuntoVenta")
    comprobante = relationship("Comprobante")
    lote = relationship("LoteComprobante")
    grupo = relationship("LoteComprobanteGrupo")
