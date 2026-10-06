"""A-01 sobre PostgreSQL desechable: tipos, cadena y downgrade sin pérdida."""

from decimal import Decimal
from datetime import date

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.fiscal_storage import amount_sum
from app.core.fiscal_storage_legacy import A01_HEAD, LEGACY_HEAD
from tests.test_fiscal_storage import storage_table
from tests.integration.test_integridad_fiscal_postgresql import (
    _reset_schema,
    _run_alembic,
    _crear_contexto_sintetico,
    _insertar_comprobante,
)
from tests.test_alembic_migrations import _run_alembic_failure
from app.models.comprobante_item import ComprobanteItem
from tests.postgresql_harness import require_disposable_postgres_url


async def test_postgresql_exactitud_comparacion_y_migracion():
    url = require_disposable_postgres_url(purpose="contrato A-01")
    await _reset_schema(url)
    engine = create_async_engine(url)
    try:
        _run_alembic("upgrade", LEGACY_HEAD, url)
        await _crear_contexto_sintetico(engine)
        await _insertar_comprobante(
            engine,
            1,
            "autorizado",
            cae="00000000000000",
            cae_vencimiento=date(2026, 7, 13),
        )
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO comprobante_items (id, comprobante_id, codigo, descripcion, cantidad, unidad, precio_unitario, descuento_porcentaje, iva_porcentaje, subtotal, orden) VALUES (1, 1, 'S', 'Sintético', 1.00005, 'unidades', 100.00005, 0, 21, 100, 0)"
                )
            )
        _run_alembic("upgrade", A01_HEAD, url)
        await engine.dispose()  # Reemplazar prepared statements tras cambiar tipos.
        table = storage_table()
        values = [
            Decimal(value)
            for value in ["-12.1", "-12", "0", "0.12", "0.121", "2", "10", "1E200000"]
        ]
        async with engine.begin() as connection:
            assert await connection.scalar(select(ComprobanteItem.cantidad)) == Decimal(
                "1.0001"
            )
            await connection.run_sync(table.create)
            await connection.execute(
                table.insert(),
                [
                    {
                        "id": index,
                        "variable": value,
                        "amount": Decimal("10000000000000000000000000.01"),
                        "cents": 1000000000000000000000000001,
                    }
                    for index, value in enumerate(reversed(values))
                ],
            )
            assert (
                await connection.scalars(
                    select(table.c.variable).order_by(table.c.variable.asc())
                )
            ).all() == values
            assert (
                await connection.scalars(
                    select(table.c.variable)
                    .where(table.c.variable > Decimal("2.0"))
                    .order_by(table.c.variable.asc())
                )
            ).all() == values[-2:]
            assert await connection.scalar(
                select(amount_sum(table.c.amount))
            ) == Decimal("80000000000000000000000000.08")
            assert (
                await connection.scalar(select(table.c.cents).limit(1))
                == 1000000000000000000000000001
            )
            amounts = [
                Decimal(value)
                for value in [
                    "-1000",
                    "-900",
                    "9.01",
                    "9.02",
                    "900",
                    "1000",
                    "2000",
                    "3000",
                ]
            ]
            for index, value in enumerate(amounts):
                await connection.execute(
                    table.update().where(table.c.id == index).values(amount=value)
                )
            total = amount_sum(table.c.amount)
            query = select(total).group_by(table.c.id)
            assert (
                await connection.scalars(query.order_by(total.asc()))
            ).all() == amounts
            assert (
                await connection.scalars(query.order_by(total.desc()))
            ).all() == amounts[::-1]
            assert (
                await connection.scalars(
                    query.having(total > Decimal("900")).order_by(total.desc())
                )
            ).all() == [Decimal("3000"), Decimal("2000"), Decimal("1000")]
            indexes = (
                (
                    await connection.execute(
                        text(
                            "SELECT indexdef FROM pg_indexes WHERE indexname IN ('ix_lotes_grupos_dup_documento','ix_lotes_grupos_dup_nombre')"
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert len(indexes) == 2
            assert all(
                "cotizacion_busqueda" in definition
                and "cotizacion_duplicados" not in definition
                for definition in indexes
            )
            await connection.execute(text("SET LOCAL enable_seqscan=off"))
            plan = (
                (
                    await connection.execute(
                        text(
                            "EXPLAIN SELECT id FROM lotes_comprobantes_grupos "
                            "WHERE empresa_id=1 AND ambiente='homologacion' AND tipo_comprobante=11 "
                            "AND punto_venta_numero=1 AND fecha_emision_normalizada='2026-07-13' "
                            "AND moneda_duplicados='PES' AND cotizacion_busqueda=repeat('0',64) "
                            "AND total_centavos=10000 AND identidad_documento_hash=repeat('0',64)"
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert any("ix_lotes_grupos_dup_documento" in line for line in plan)
        await engine.dispose()
        _run_alembic("downgrade", LEGACY_HEAD, url)
        _run_alembic("upgrade", A01_HEAD, url)
        await engine.dispose()
        async with engine.begin() as connection:
            await connection.execute(
                ComprobanteItem.__table__.update().values(
                    cantidad=Decimal("1.00005"), codigo="S" * 101
                )
            )
        await engine.dispose()
        failure = _run_alembic_failure("downgrade", LEGACY_HEAD, url)
        assert "comprobante_items.cantidad=1" in failure
        assert "comprobante_items.codigo=1" in failure
        async with engine.connect() as connection:
            assert (
                await connection.scalar(text("SELECT version_num FROM alembic_version"))
                == A01_HEAD
            )
            assert await connection.scalar(select(ComprobanteItem.cantidad)) == Decimal(
                "1.00005"
            )
    finally:
        await engine.dispose()
        await _reset_schema(url)
