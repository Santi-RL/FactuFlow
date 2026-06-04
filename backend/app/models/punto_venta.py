"""Modelo PuntoVenta - Puntos de venta de la empresa."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy import Index, UniqueConstraint
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
        Index("ix_puntos_venta_empresa_numero", "empresa_id", "numero"),
    )

    id = Column(Integer, primary_key=True, index=True)
    numero = Column(Integer, nullable=False)  # 1-99999
    nombre = Column(String(255), nullable=True)  # ej: "Sucursal Centro"
    sistema = Column(String(255), nullable=True)
    domicilio = Column(String(500), nullable=True)
    nombre_fantasia = Column(String(255), nullable=True)
    es_webservice = Column(Boolean, default=False, nullable=False)
    bloqueado = Column(Boolean, default=False, nullable=False)
    fecha_baja = Column(String(20), nullable=True)
    fuente = Column(String(50), nullable=True)
    activo = Column(Boolean, default=True, nullable=False)

    # Relación con empresa
    empresa_id = Column(
        Integer, ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
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
        )

    def __repr__(self) -> str:
        return f"<PuntoVenta {self.numero} - {self.nombre or 'Sin nombre'}>"
