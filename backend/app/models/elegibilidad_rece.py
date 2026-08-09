"""Modelos durables de elegibilidad RECE y guardas de emisión."""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


AMBIENTES_RECE = ("homologacion", "produccion")
ESTADOS_ELEGIBILIDAD_RECE = ("verificado_rece", "no_rece", "no_verificado")
FUENTES_ELEGIBILIDAD_RECE = (
    "migracion_legacy",
    "alta_manual",
    "sincronizacion_wsfe",
    "constancia_arca_atestada",
    "edicion",
)
TIPOS_EVIDENCIA_RECE = ("sin_evidencia", "rece_aplicativo_web_services_v1")
FASES_GUARDA_RECE = (
    "pre_arca",
    "arca_iniciada",
    "requiere_reconciliacion",
    "cerrada_pre_arca",
    "cerrada_terminal",
)
FASES_GUARDA_RECE_ACTIVAS = (
    "pre_arca",
    "arca_iniciada",
    "requiere_reconciliacion",
)


def _sql_allowlist(valores: tuple[str, ...]) -> str:
    """Convierte una allowlist fija en material seguro para checks SQL."""
    return ", ".join(repr(valor) for valor in valores)


class PuntoVentaElegibilidadReceRevision(Base):
    """Revisión inmutable de elegibilidad RECE para un punto y ambiente."""

    __tablename__ = "puntos_venta_elegibilidad_rece_revisiones"
    __table_args__ = (
        CheckConstraint(
            f"ambiente IN ({_sql_allowlist(AMBIENTES_RECE)})",
            name="ck_pv_rece_revision_ambiente",
        ),
        CheckConstraint(
            f"estado IN ({_sql_allowlist(ESTADOS_ELEGIBILIDAD_RECE)})",
            name="ck_pv_rece_revision_estado",
        ),
        CheckConstraint(
            f"fuente IN ({_sql_allowlist(FUENTES_ELEGIBILIDAD_RECE)})",
            name="ck_pv_rece_revision_fuente",
        ),
        CheckConstraint(
            f"evidencia_tipo IN ({_sql_allowlist(TIPOS_EVIDENCIA_RECE)})",
            name="ck_pv_rece_revision_evidencia_tipo",
        ),
        CheckConstraint("revision > 0", name="ck_pv_rece_revision_positiva"),
        CheckConstraint(
            "punto_revision_fiscal > 0",
            name="ck_pv_rece_revision_fiscal_positiva",
        ),
        CheckConstraint(
            "evidencia_sha256 IS NULL OR length(evidencia_sha256) = 64",
            name="ck_pv_rece_revision_sha256",
        ),
        CheckConstraint(
            "empresa_cuit_snapshot IS NULL OR length(empresa_cuit_snapshot) = 11",
            name="ck_pv_rece_revision_cuit_snapshot",
        ),
        CheckConstraint(
            "punto_venta_numero_snapshot IS NULL OR "
            "punto_venta_numero_snapshot BETWEEN 1 AND 99999",
            name="ck_pv_rece_revision_numero_snapshot",
        ),
        CheckConstraint(
            "actor_usuario_id_snapshot IS NULL OR actor_usuario_id_snapshot > 0",
            name="ck_pv_rece_revision_actor_snapshot",
        ),
        CheckConstraint(
            "vigente_hasta IS NULL OR documento_emitido_en IS NULL OR "
            "vigente_hasta >= documento_emitido_en",
            name="ck_pv_rece_revision_vigencia",
        ),
        CheckConstraint(
            "((estado = 'verificado_rece' "
            "AND ambiente = 'produccion' "
            "AND fuente = 'constancia_arca_atestada' "
            "AND evidencia_tipo = 'rece_aplicativo_web_services_v1' "
            "AND evidencia_sha256 IS NOT NULL "
            "AND clasificador_version IS NOT NULL "
            "AND empresa_cuit_snapshot IS NOT NULL "
            "AND punto_venta_numero_snapshot IS NOT NULL "
            "AND documento_emitido_en IS NOT NULL "
            "AND vigente_hasta IS NOT NULL "
            "AND verificado_en IS NOT NULL "
            "AND actor_usuario_id_snapshot IS NOT NULL) "
            "OR (estado <> 'verificado_rece' "
            "AND vigente_hasta IS NULL "
            "AND verificado_en IS NULL))",
            name="ck_pv_rece_revision_verificada_coherente",
        ),
        CheckConstraint(
            "fuente NOT IN ('migracion_legacy', 'alta_manual', "
            "'sincronizacion_wsfe', 'edicion') OR estado <> 'verificado_rece'",
            name="ck_pv_rece_revision_fuente_no_promueve",
        ),
        UniqueConstraint(
            "punto_venta_id",
            "ambiente",
            "revision",
            name="uq_pv_rece_revision_punto_ambiente_revision",
        ),
        UniqueConstraint(
            "id",
            "empresa_id",
            "punto_venta_id",
            "ambiente",
            name="uq_pv_rece_revision_identidad_compuesta",
        ),
        ForeignKeyConstraint(
            ["punto_venta_id", "empresa_id"],
            ["puntos_venta.id", "puntos_venta.empresa_id"],
            name="fk_pv_rece_revision_punto_empresa",
            ondelete="RESTRICT",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    empresa_id = Column(Integer, nullable=False)
    punto_venta_id = Column(Integer, nullable=False)
    ambiente = Column(String(20), nullable=False)
    revision = Column(Integer, nullable=False)
    estado = Column(String(30), nullable=False)
    fuente = Column(String(40), nullable=False)
    evidencia_tipo = Column(String(50), nullable=False)
    evidencia_sha256 = Column(String(64), nullable=True)
    clasificador_version = Column(String(40), nullable=True)
    empresa_cuit_snapshot = Column(String(11), nullable=True)
    punto_venta_numero_snapshot = Column(Integer, nullable=True)
    punto_revision_fiscal = Column(Integer, nullable=False)
    documento_emitido_en = Column(Date, nullable=True)
    vigente_hasta = Column(Date, nullable=True)
    observado_en = Column(DateTime, nullable=False, default=datetime.utcnow)
    verificado_en = Column(DateTime, nullable=True)
    creado_por_usuario_id = Column(
        Integer,
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_usuario_id_snapshot = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    punto_venta = relationship(
        "PuntoVenta",
        foreign_keys=[punto_venta_id, empresa_id],
        viewonly=True,
    )
    creado_por_usuario = relationship("Usuario", foreign_keys=[creado_por_usuario_id])


class PuntoVentaElegibilidadReceActual(Base):
    """Cabeza transaccional de elegibilidad RECE por punto y ambiente."""

    __tablename__ = "puntos_venta_elegibilidad_rece_actual"
    __table_args__ = (
        CheckConstraint(
            f"ambiente IN ({_sql_allowlist(AMBIENTES_RECE)})",
            name="ck_pv_rece_actual_ambiente",
        ),
        UniqueConstraint(
            "punto_venta_id",
            "ambiente",
            name="uq_pv_rece_actual_punto_ambiente",
        ),
        ForeignKeyConstraint(
            ["punto_venta_id", "empresa_id"],
            ["puntos_venta.id", "puntos_venta.empresa_id"],
            name="fk_pv_rece_actual_punto_empresa",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "revision_actual_id",
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
            name="fk_pv_rece_actual_revision_compuesta",
            ondelete="RESTRICT",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    empresa_id = Column(Integer, nullable=False)
    punto_venta_id = Column(Integer, nullable=False)
    ambiente = Column(String(20), nullable=False)
    revision_actual_id = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    punto_venta = relationship(
        "PuntoVenta",
        foreign_keys=[punto_venta_id, empresa_id],
        viewonly=True,
    )
    revision_actual = relationship(
        "PuntoVentaElegibilidadReceRevision",
        foreign_keys=[revision_actual_id, empresa_id, punto_venta_id, ambiente],
        viewonly=True,
    )


class OperacionIdempotenteElegibilidadRece(Base):
    """Snapshot RECE normalizado de una operación fiscal idempotente."""

    __tablename__ = "operaciones_idempotentes_elegibilidad_rece"
    __table_args__ = (
        CheckConstraint(
            f"ambiente IN ({_sql_allowlist(AMBIENTES_RECE)})",
            name="ck_operacion_rece_ambiente",
        ),
        CheckConstraint(
            "punto_venta_revision_fiscal > 0",
            name="ck_operacion_rece_revision_fiscal_positiva",
        ),
        UniqueConstraint(
            "operacion_id",
            "punto_venta_id",
            "ambiente",
            name="uq_operacion_rece_punto_ambiente",
        ),
        UniqueConstraint(
            "operacion_id",
            "empresa_id",
            "punto_venta_id",
            "ambiente",
            "elegibilidad_revision_id",
            "punto_venta_revision_fiscal",
            name="uq_operacion_rece_snapshot_compuesto",
        ),
        ForeignKeyConstraint(
            ["operacion_id", "empresa_id"],
            ["operaciones_idempotentes.id", "operaciones_idempotentes.empresa_id"],
            name="fk_operacion_rece_operacion_empresa",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["punto_venta_id", "empresa_id"],
            ["puntos_venta.id", "puntos_venta.empresa_id"],
            name="fk_operacion_rece_punto_empresa",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "elegibilidad_revision_id",
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
            name="fk_operacion_rece_revision_compuesta",
            ondelete="RESTRICT",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    operacion_id = Column(Integer, nullable=False)
    empresa_id = Column(Integer, nullable=False)
    punto_venta_id = Column(Integer, nullable=False)
    ambiente = Column(String(20), nullable=False)
    elegibilidad_revision_id = Column(Integer, nullable=False)
    punto_venta_revision_fiscal = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    operacion = relationship(
        "OperacionIdempotente",
        foreign_keys=[operacion_id, empresa_id],
        viewonly=True,
    )
    revision = relationship(
        "PuntoVentaElegibilidadReceRevision",
        foreign_keys=[
            elegibilidad_revision_id,
            empresa_id,
            punto_venta_id,
            ambiente,
        ],
        viewonly=True,
    )


class PuntoVentaGuardaEmisionRece(Base):
    """Guarda durable que inmoviliza contexto RECE durante FECAE."""

    __tablename__ = "puntos_venta_guardas_emision_rece"
    __table_args__ = (
        CheckConstraint(
            f"ambiente IN ({_sql_allowlist(AMBIENTES_RECE)})",
            name="ck_guarda_rece_ambiente",
        ),
        CheckConstraint(
            f"fase IN ({_sql_allowlist(FASES_GUARDA_RECE)})",
            name="ck_guarda_rece_fase",
        ),
        CheckConstraint(
            "punto_venta_revision_fiscal > 0",
            name="ck_guarda_rece_revision_fiscal_positiva",
        ),
        CheckConstraint(
            "((fase = 'pre_arca' AND arca_iniciada_en IS NULL "
            "AND cerrada_en IS NULL) "
            "OR (fase IN ('arca_iniciada', 'requiere_reconciliacion') "
            "AND arca_iniciada_en IS NOT NULL AND cerrada_en IS NULL) "
            "OR (fase = 'cerrada_pre_arca' AND arca_iniciada_en IS NULL "
            "AND cerrada_en IS NOT NULL) "
            "OR (fase = 'cerrada_terminal' AND arca_iniciada_en IS NOT NULL "
            "AND cerrada_en IS NOT NULL))",
            name="ck_guarda_rece_fase_timestamps",
        ),
        UniqueConstraint(
            "id",
            "operacion_id",
            "empresa_id",
            "punto_venta_id",
            "ambiente",
            "elegibilidad_revision_id",
            "punto_venta_revision_fiscal",
            name="uq_guarda_rece_identidad_compuesta",
        ),
        UniqueConstraint("token", name="uq_guarda_rece_token"),
        ForeignKeyConstraint(
            ["operacion_id", "empresa_id"],
            ["operaciones_idempotentes.id", "operaciones_idempotentes.empresa_id"],
            name="fk_guarda_rece_operacion_empresa",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["punto_venta_id", "empresa_id"],
            ["puntos_venta.id", "puntos_venta.empresa_id"],
            name="fk_guarda_rece_punto_empresa",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "elegibilidad_revision_id",
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
            name="fk_guarda_rece_revision_compuesta",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "operacion_id",
                "empresa_id",
                "punto_venta_id",
                "ambiente",
                "elegibilidad_revision_id",
                "punto_venta_revision_fiscal",
            ],
            [
                "operaciones_idempotentes_elegibilidad_rece.operacion_id",
                "operaciones_idempotentes_elegibilidad_rece.empresa_id",
                "operaciones_idempotentes_elegibilidad_rece.punto_venta_id",
                "operaciones_idempotentes_elegibilidad_rece.ambiente",
                "operaciones_idempotentes_elegibilidad_rece.elegibilidad_revision_id",
                "operaciones_idempotentes_elegibilidad_rece.punto_venta_revision_fiscal",
            ],
            name="fk_guarda_rece_snapshot_operacion",
            ondelete="RESTRICT",
        ),
        Index(
            "uq_guarda_rece_activa",
            "empresa_id",
            "punto_venta_id",
            "ambiente",
            unique=True,
            sqlite_where=text(
                "fase IN ('pre_arca', 'arca_iniciada', 'requiere_reconciliacion')"
            ),
            postgresql_where=text(
                "fase IN ('pre_arca', 'arca_iniciada', 'requiere_reconciliacion')"
            ),
        ),
        Index("ix_guarda_rece_operacion", "operacion_id", "fase"),
    )

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(64), nullable=False)
    fase = Column(String(40), nullable=False, default="pre_arca")
    operacion_id = Column(Integer, nullable=False)
    empresa_id = Column(Integer, nullable=False)
    punto_venta_id = Column(Integer, nullable=False)
    ambiente = Column(String(20), nullable=False)
    elegibilidad_revision_id = Column(Integer, nullable=False)
    punto_venta_revision_fiscal = Column(Integer, nullable=False)
    arca_iniciada_en = Column(DateTime, nullable=True)
    cerrada_en = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    operacion = relationship(
        "OperacionIdempotente",
        foreign_keys=[operacion_id, empresa_id],
        viewonly=True,
    )
    revision = relationship(
        "PuntoVentaElegibilidadReceRevision",
        foreign_keys=[
            elegibilidad_revision_id,
            empresa_id,
            punto_venta_id,
            ambiente,
        ],
        viewonly=True,
    )
