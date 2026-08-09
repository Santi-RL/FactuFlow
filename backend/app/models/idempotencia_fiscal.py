"""Modelos de idempotencia e intentos fiscales."""

from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
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
        UniqueConstraint(
            "id",
            "empresa_id",
            name="uq_operaciones_idempotentes_id_empresa",
        ),
        CheckConstraint(
            "rece_snapshot_hash IS NULL OR length(rece_snapshot_hash) = 64",
            name="ck_operaciones_idempotentes_rece_snapshot_hash",
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
    rece_snapshot_hash = Column(String(64), nullable=True)
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
        foreign_keys="IntentoEmisionFiscal.operacion_id",
    )


class IntentoEmisionFiscal(Base):
    """Reserva y audita un comprobante fiscal planificado."""

    __tablename__ = "intentos_emision_fiscal"
    __table_args__ = (
        CheckConstraint(
            f"estado IN ({_ESTADOS_INTENTO_FISCAL_SQL})",
            name="ck_intentos_emision_fiscal_estado_valido",
        ),
        CheckConstraint(
            "(((lote_id IS NULL AND grupo_id IS NULL) "
            "OR (lote_id IS NOT NULL AND grupo_id IS NOT NULL)) "
            "AND ((ambiente IS NULL "
            "AND punto_venta_elegibilidad_revision_id IS NULL "
            "AND punto_venta_revision_fiscal IS NULL "
            "AND guarda_rece_id IS NULL) "
            "OR (ambiente IS NOT NULL "
            "AND ambiente IN ('homologacion', 'produccion') "
            "AND operacion_id IS NOT NULL "
            "AND punto_venta_elegibilidad_revision_id IS NOT NULL "
            "AND punto_venta_revision_fiscal IS NOT NULL "
            "AND punto_venta_revision_fiscal > 0 "
            "AND guarda_rece_id IS NOT NULL)))",
            name="ck_intentos_emision_fiscal_snapshot_rece_completo",
        ),
        ForeignKeyConstraint(
            ["operacion_id", "empresa_id"],
            ["operaciones_idempotentes.id", "operaciones_idempotentes.empresa_id"],
            name="fk_intento_operacion_empresa",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["punto_venta_id", "empresa_id"],
            ["puntos_venta.id", "puntos_venta.empresa_id"],
            name="fk_intento_punto_empresa",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "punto_venta_elegibilidad_revision_id",
                "empresa_id",
                "punto_venta_id",
                "ambiente",
            ],
            [
                "puntos_venta_elegibilidad_rece_revisiones.id",
                "puntos_venta_elegibilidad_rece_revisiones.empresa_id",
                "puntos_venta_elegibilidad_rece_revisiones.punto_venta_id",
                "puntos_venta_elegibilidad_rece_revisiones.ambiente",
            ],
            name="fk_intento_revision_rece_compuesta",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["lote_id", "empresa_id"],
            ["lotes_comprobantes.id", "lotes_comprobantes.empresa_id"],
            name="fk_intento_lote_empresa",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["grupo_id", "empresa_id"],
            [
                "lotes_comprobantes_grupos.id",
                "lotes_comprobantes_grupos.empresa_id",
            ],
            name="fk_intento_grupo_empresa",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "grupo_id",
                "lote_id",
                "empresa_id",
                "punto_venta_id",
                "punto_venta_numero",
                "ambiente",
                "punto_venta_elegibilidad_revision_id",
                "punto_venta_revision_fiscal",
                "tipo_comprobante",
            ],
            [
                "lotes_comprobantes_grupos.id",
                "lotes_comprobantes_grupos.lote_id",
                "lotes_comprobantes_grupos.empresa_id",
                "lotes_comprobantes_grupos.punto_venta_id",
                "lotes_comprobantes_grupos.punto_venta_numero",
                "lotes_comprobantes_grupos.ambiente",
                "lotes_comprobantes_grupos.punto_venta_elegibilidad_revision_id",
                "lotes_comprobantes_grupos.punto_venta_revision_fiscal",
                "lotes_comprobantes_grupos.tipo_comprobante",
            ],
            name="fk_intento_grupo_snapshot_rece_exacto",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "guarda_rece_id",
                "operacion_id",
                "empresa_id",
                "punto_venta_id",
                "ambiente",
                "punto_venta_elegibilidad_revision_id",
                "punto_venta_revision_fiscal",
            ],
            [
                "puntos_venta_guardas_emision_rece.id",
                "puntos_venta_guardas_emision_rece.operacion_id",
                "puntos_venta_guardas_emision_rece.empresa_id",
                "puntos_venta_guardas_emision_rece.punto_venta_id",
                "puntos_venta_guardas_emision_rece.ambiente",
                "puntos_venta_guardas_emision_rece.elegibilidad_revision_id",
                "puntos_venta_guardas_emision_rece.punto_venta_revision_fiscal",
            ],
            name="fk_intento_guarda_rece_compuesta",
            ondelete="RESTRICT",
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
    ambiente = Column(String(20), nullable=True)
    punto_venta_elegibilidad_revision_id = Column(Integer, nullable=True)
    punto_venta_revision_fiscal = Column(Integer, nullable=True)
    guarda_rece_id = Column(
        Integer,
        ForeignKey("puntos_venta_guardas_emision_rece.id", ondelete="RESTRICT"),
        nullable=True,
    )
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
        Integer,
        ForeignKey("puntos_venta.id", ondelete="RESTRICT"),
        nullable=False,
    )
    comprobante_id = Column(
        Integer, ForeignKey("comprobantes.id", ondelete="SET NULL"), nullable=True
    )
    lote_id = Column(
        Integer,
        ForeignKey("lotes_comprobantes.id", ondelete="RESTRICT"),
        nullable=True,
    )
    grupo_id = Column(
        Integer,
        ForeignKey("lotes_comprobantes_grupos.id", ondelete="RESTRICT"),
        nullable=True,
    )

    operacion = relationship(
        "OperacionIdempotente",
        back_populates="intentos",
        foreign_keys=[operacion_id],
    )
    empresa = relationship("Empresa")
    usuario = relationship("Usuario")
    punto_venta = relationship(
        "PuntoVenta",
        foreign_keys=[punto_venta_id],
    )
    comprobante = relationship("Comprobante")
    lote = relationship(
        "LoteComprobante",
        foreign_keys=[lote_id, empresa_id],
        viewonly=True,
    )
    grupo = relationship(
        "LoteComprobanteGrupo",
        foreign_keys=[grupo_id, empresa_id],
        viewonly=True,
    )
    elegibilidad_revision = relationship(
        "PuntoVentaElegibilidadReceRevision",
        foreign_keys=[
            punto_venta_elegibilidad_revision_id,
            empresa_id,
            punto_venta_id,
            ambiente,
        ],
        viewonly=True,
    )
    guarda_rece = relationship(
        "PuntoVentaGuardaEmisionRece",
        foreign_keys=[
            guarda_rece_id,
            operacion_id,
            empresa_id,
            punto_venta_id,
            ambiente,
            punto_venta_elegibilidad_revision_id,
            punto_venta_revision_fiscal,
        ],
        viewonly=True,
    )
