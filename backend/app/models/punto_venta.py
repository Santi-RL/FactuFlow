"""Modelo PuntoVenta - Puntos de venta de la empresa."""

from datetime import datetime
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property

from app.core.database import Base


class PuntoVenta(Base):
    """Modelo de Punto de Venta."""

    __tablename__ = "puntos_venta"
    __table_args__ = (
        UniqueConstraint(
            "empresa_id",
            "numero",
            name="uq_puntos_venta_empresa_numero",
        ),
        UniqueConstraint(
            "id",
            "empresa_id",
            name="uq_puntos_venta_id_empresa",
        ),
        CheckConstraint(
            "revision_fiscal > 0",
            name="ck_puntos_venta_revision_fiscal_positiva",
        ),
        CheckConstraint(
            "domicilio_fuente IS NULL OR "
            "domicilio_fuente IN ('manual', 'constancia_arca')",
            name="ck_puntos_venta_domicilio_fuente",
        ),
        CheckConstraint(
            "nombre_fantasia_fuente IS NULL OR "
            "nombre_fantasia_fuente IN ('manual', 'constancia_arca')",
            name="ck_puntos_venta_nombre_fantasia_fuente",
        ),
        Index("ix_puntos_venta_empresa_numero", "empresa_id", "numero"),
    )

    id = Column(Integer, primary_key=True, index=True)
    numero = Column(Integer, nullable=False)  # 1-99999
    nombre = Column(String(255), nullable=True)  # ej: "Sucursal Centro"
    sistema = Column(String(255), nullable=True)
    domicilio = Column(String(500), nullable=True)
    domicilio_fuente = Column(String(30), nullable=True)
    nombre_fantasia = Column(String(255), nullable=True)
    nombre_fantasia_fuente = Column(String(30), nullable=True)
    es_webservice = Column(Boolean, default=False, nullable=False)
    bloqueado = Column(Boolean, default=False, nullable=False)
    fecha_baja = Column(String(20), nullable=True)
    fuente = Column(String(50), nullable=True)
    activo = Column(Boolean, default=True, nullable=False)
    # El default Python conserva construcciones legacy internas y fixtures que
    # representan filas migradas. Los productores runtime PF-19D declaran el
    # valor explícitamente; la migración y el default del schema son fail-closed.
    usar_en_factuflow = Column(Boolean, default=True, nullable=False)
    revision_fiscal = Column(Integer, default=1, nullable=False)
    ultima_comprobacion_arca_en = Column(DateTime, nullable=True)

    # Relación con empresa
    empresa_id = Column(
        Integer, ForeignKey("empresas.id", ondelete="RESTRICT"), nullable=False
    )
    empresa = relationship("Empresa", back_populates="puntos_venta")

    # Relación con comprobantes
    comprobantes = relationship("Comprobante", back_populates="punto_venta")

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    @hybrid_property
    def usable_factuflow(self) -> bool:
        """Indica si el punto puede usarse para emitir por FactuFlow."""
        return bool(
            self.activo
            and self.es_webservice
            and not self.bloqueado
            and not self.fecha_baja
            and self.usar_en_factuflow
        )

    def __repr__(self) -> str:
        return f"<PuntoVenta {self.numero} - {self.nombre or 'Sin nombre'}>"
