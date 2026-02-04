"""Modelo Comprobante - Facturas, Notas de Crédito y Débito."""

from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import Column, Integer, String, Date, DateTime, Numeric, ForeignKey, Index
from sqlalchemy.orm import relationship

from app.core.database import Base


class Comprobante(Base):
    """Modelo de Comprobante (Facturas, NC, ND)."""
    
    __tablename__ = "comprobantes"
    
    # Índices compuestos para consultas frecuentes
    __table_args__ = (
        # Índice para búsqueda por tipo y número (único por punto de venta)
        Index('ix_comprobantes_tipo_numero', 'tipo_comprobante', 'numero'),
        # Índice para filtros por fecha
        Index('ix_comprobantes_fecha_emision', 'fecha_emision'),
        # Índice para búsqueda por CAE
        Index('ix_comprobantes_cae', 'cae'),
        # Índice para filtro por estado
        Index('ix_comprobantes_estado', 'estado'),
        # Índice compuesto para listados paginados
        Index('ix_comprobantes_empresa_fecha', 'empresa_id', 'fecha_emision'),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Tipo y número
    tipo_comprobante = Column(Integer, nullable=False)  # 1=FA, 6=FB, 11=FC, 3=NCA, etc.
    numero = Column(Integer, nullable=False)
    
    # Fechas
    fecha_emision = Column(Date, nullable=False)
    fecha_vencimiento = Column(Date, nullable=True)
    
    # Importes
    subtotal = Column(Numeric(12, 2), nullable=False)
    descuento = Column(Numeric(12, 2), default=0, nullable=False)
    iva_21 = Column(Numeric(12, 2), default=0, nullable=False)
    iva_10_5 = Column(Numeric(12, 2), default=0, nullable=False)
    iva_27 = Column(Numeric(12, 2), default=0, nullable=False)
    otros_impuestos = Column(Numeric(12, 2), default=0, nullable=False)
    total = Column(Numeric(12, 2), nullable=False)
    
    # AFIP
    cae = Column(String(14), nullable=True)  # Nullable hasta autorizado
    cae_vencimiento = Column(Date, nullable=True)
    estado = Column(String(20), default="borrador", nullable=False)  # borrador, pendiente, autorizado, rechazado
    
    # Datos adicionales
    moneda = Column(String(3), default="PES", nullable=False)
    cotizacion = Column(Numeric(10, 6), default=1, nullable=False)
    observaciones = Column(String(500), nullable=True)
    
    # Relaciones
    empresa_id = Column(Integer, ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False)
    empresa = relationship("Empresa", back_populates="comprobantes")
    
    punto_venta_id = Column(Integer, ForeignKey("puntos_venta.id", ondelete="RESTRICT"), nullable=False)
    punto_venta = relationship("PuntoVenta", back_populates="comprobantes")
    
    cliente_id = Column(Integer, ForeignKey("clientes.id", ondelete="RESTRICT"), nullable=False)
    cliente = relationship("Cliente", back_populates="comprobantes")
    
    # Items del comprobante
    items = relationship("ComprobanteItem", back_populates="comprobante", cascade="all, delete-orphan")
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __repr__(self) -> str:
        return f"<Comprobante {self.tipo_comprobante}-{self.numero} - Total: ${self.total}>"
