"""Contrato A-01: exactitud, encodabilidad, guardado y migración reales."""

from decimal import Decimal, localcontext
import sqlite3
import hashlib
import os
import subprocess
import sys

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, create_engine, select
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.fiscal_storage import (
    ExactAmount,
    ExactDecimal,
    ExactInteger,
    amount_sum,
    decimal_search_key,
    encode_decimal,
    scaled_integer,
    sum_amounts,
    _install_sqlite_functions,
)
from app.core.fiscal_storage_legacy import A01_HEAD, LEGACY_HEAD
from app.core.fiscal_storage_legacy import LEGACY_COLUMNS, legacy_read
from app.models.comprobante_item import ComprobanteItem
from app.schemas.comprobante import ComprobanteDetalleResponse, EmitirComprobanteRequest
from tests.test_alembic_migrations import (
    REVISION_INTEGRIDAD_FISCAL,
    _run_alembic,
    _run_alembic_failure,
    _backup_env_pf19,
    _crear_contexto_fiscal_sintetico,
    _insertar_comprobante_sintetico,
    _alembic_version,
)
from tests import test_facturacion_cliente_asociacion as association_tests

fixture_escenario_cliente = association_tests.escenario_cliente
_guardar_sintetico = association_tests._guardar_sintetico


def test_paquete_v5_preserva_decimales_y_no_reinterpreta_v4(tmp_path):
    from app.core.database import Base
    from app.scripts import vps_migration, vps_migration_v4
    from tests.test_vps_migration import _create_source_db, _build_v4_package

    source, certs = _create_source_db(tmp_path, fiscal_head=True)
    engine = create_engine(f"sqlite:///{source}")
    with engine.begin() as connection:
        connection.execute(
            Base.metadata.tables["comprobante_items"]
            .update()
            .values(
                codigo="S" * 101,
                cantidad=Decimal("1.00005"),
                precio_unitario=Decimal("0.1234567890123456789012345678"),
                descuento_porcentaje=Decimal("0.00123"),
            )
        )
        connection.execute(
            Base.metadata.tables["comprobantes"]
            .update()
            .values(cotizacion=Decimal("1E200000"))
        )
    engine.dispose()
    package = vps_migration.export_package(
        source,
        certs,
        tmp_path / "packages",
        "clave-sintética-destino",
        source_quiesced=True,
    )
    manifest = vps_migration.load_and_verify_manifest(package)
    assert manifest["package_version"] == 5
    assert manifest["alembic_version"] == A01_HEAD
    rows = vps_migration.read_package_rows(package, manifest, "comprobante_items")
    assert rows[0]["cantidad"] == Decimal("1.00005")
    assert rows[0]["precio_unitario"] == Decimal("0.1234567890123456789012345678")
    assert rows[0]["codigo"] == "S" * 101
    assert vps_migration.read_package_rows(package, manifest, "comprobantes")[0][
        "cotizacion"
    ] == Decimal("1E200000")
    # Volver a un paquete histórico en el mismo proceso no hereda el descriptor.
    legacy_package, _, original = _build_v4_package(tmp_path / "legacy")
    raw = (legacy_package / "manifest.json").read_bytes()
    checksum = hashlib.sha256(raw).hexdigest()
    loaded = vps_migration.load_and_verify_manifest(legacy_package)
    assert vps_migration.select_import_contract(loaded) is vps_migration_v4.V4_CONTRACT
    assert (
        hashlib.sha256((legacy_package / "manifest.json").read_bytes()).hexdigest()
        == checksum
    )
    assert loaded["idempotency_barrier"] == original["idempotency_barrier"]


def test_migracion_sqlite_grafo_v4_preserva_json_huellas_y_reservas(tmp_path):
    from app.core.database import Base
    from tests.integration.test_vps_migration_postgresql import _crear_fuente_v4_pf13

    source, _ = _crear_fuente_v4_pf13(tmp_path)
    url = f"sqlite:///{source.as_posix()}"
    dialect = create_engine("sqlite://").dialect

    def snapshot(upgraded):
        result = {}
        with sqlite3.connect(source) as connection:
            connection.row_factory = sqlite3.Row
            for name in Base.metadata.tables:
                rows = []
                for raw in connection.execute(f'SELECT * FROM "{name}"'):
                    row = dict(raw)
                    row.pop("cotizacion_busqueda", None)
                    for column, old_type in LEGACY_COLUMNS.get(name, {}).items():
                        value = row[column]
                        if value is not None and column not in {
                            "codigo",
                            "cotizacion_duplicados",
                        }:
                            row[column] = (
                                Decimal(value)
                                if upgraded
                                else legacy_read(value, old_type, dialect)
                            )
                    rows.append(row)
                result[name] = rows
        return result

    before = snapshot(False)
    _run_alembic("upgrade", A01_HEAD, url)
    assert snapshot(True) == before
    _run_alembic("downgrade", LEGACY_HEAD, url)
    assert snapshot(False) == before
    _run_alembic("upgrade", A01_HEAD, url)
    assert snapshot(True) == before


@pytest.mark.parametrize(
    "value",
    [
        "1.00005",
        "0.1234567890123456789012345678",
        "1E+200000",
        "1E-200000",
        "10000000000000000000000000.01",
        "-0.000",
        "12.3400",
    ],
)
def test_codec_sin_contexto_ni_expansion(value):
    with localcontext() as context:
        context.prec = 8
        encoded = encode_decimal(Decimal(value))
        assert Decimal(encoded) == Decimal(value)
        assert len(encoded) < 50
        assert encode_decimal(Decimal(encoded)) == encoded
    assert decimal_search_key(Decimal("1.0000")) == decimal_search_key(Decimal("1"))


def test_centavos_y_agregado_fuera_de_int64_sin_contexto():
    value = Decimal("10000000000000000000000000.01")
    with localcontext() as context:
        context.prec = 8
        assert scaled_integer(value, 2) == 1000000000000000000000000001
        assert sum_amounts([value] * 1000) == Decimal("10000000000000000000000000010")
        with pytest.raises(ValueError):
            scaled_integer(Decimal("0.001"), 2)
        with pytest.raises(ValueError):
            encode_decimal(float("nan"))
        with pytest.raises(ValueError):
            encode_decimal(Decimal("Infinity"))


def storage_table():
    return Table(
        "fiscal_storage_contract",
        MetaData(),
        Column("id", Integer, primary_key=True),
        Column("variable", ExactDecimal()),
        Column("amount", ExactAmount()),
        Column("cents", ExactInteger()),
    )


def test_sqlite_sincrono_comparacion_orden_y_sum_exacto():
    engine = create_engine("sqlite://")
    table = storage_table()
    values = [
        Decimal(v)
        for v in ["-12.1", "-12", "0", "0.12", "0.121", "2", "10", "1E200000"]
    ]
    with engine.begin() as connection:
        table.create(connection)
        connection.execute(
            table.insert(),
            [
                {
                    "id": i,
                    "variable": v,
                    "amount": Decimal("10000000000000000000000000.01"),
                    "cents": 1000000000000000000000000001,
                }
                for i, v in enumerate(reversed(values))
            ],
        )
        assert (
            connection.scalars(
                select(table.c.variable).order_by(table.c.variable.asc())
            ).all()
            == values
        )
        assert (
            connection.scalars(
                select(table.c.variable)
                .where(table.c.variable > Decimal("2.0"))
                .order_by(table.c.variable.asc())
            ).all()
            == values[-2:]
        )
        assert connection.scalar(select(amount_sum(table.c.amount))) == Decimal(
            "80000000000000000000000000.08"
        )
        assert (
            connection.scalar(select(amount_sum(table.c.amount)).where(table.c.id < 0))
            is None
        )
        assert (
            connection.scalar(select(table.c.cents).limit(1))
            == 1000000000000000000000000001
        )
    engine.dispose()


async def test_aiosqlite_registra_agregado_en_conexiones_nuevas(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'exact.db'}")
    table = storage_table()
    async with engine.begin() as connection:
        await connection.run_sync(table.create)
        await connection.execute(
            table.insert(),
            {
                "variable": Decimal("1.00005"),
                "amount": Decimal("9007199254740992.01"),
                "cents": 900719925474099201,
            },
        )
    await engine.dispose()
    async with engine.connect() as connection:
        assert await connection.scalar(select(amount_sum(table.c.amount))) == Decimal(
            "9007199254740992.01"
        )
        assert await connection.scalar(
            select(table.c.variable).where(table.c.variable == Decimal("1.0000500"))
        ) == Decimal("1.00005")
    await engine.dispose()


def test_sqlite_agregados_comparan_y_ordenan_numericamente():
    engine = create_engine("sqlite://")
    table = storage_table()
    amounts = [
        Decimal(value) for value in ["-1000", "-900", "9.01", "9.02", "900", "1000"]
    ]
    total = amount_sum(table.c.amount)
    with engine.begin() as connection:
        table.create(connection)
        connection.execute(
            table.insert(),
            [{"id": index, "amount": value} for index, value in enumerate(amounts)],
        )
        query = select(total).group_by(table.c.id)
        assert connection.scalars(query.order_by(total.asc())).all() == amounts
        assert connection.scalars(query.order_by(total.desc())).all() == amounts[::-1]
        assert connection.scalars(
            query.having(total > Decimal("900")).order_by(total.desc())
        ).all() == [Decimal("1000")]
        assert (
            connection.scalars(
                select(table.c.amount)
                .where(table.c.amount < Decimal("0"))
                .order_by(table.c.amount.asc())
            ).all()
            == amounts[:2]
        )
    engine.dispose()


@pytest.mark.parametrize("compensado", [False, True])
async def test_guardado_ampliado_y_consulta_preservan_pf03b(
    fixture_escenario_cliente, db_session, compensado
):
    service, original, point = fixture_escenario_cliente
    payload = original.model_dump(mode="json")
    payload["cotizacion"] = "1.1234567890123456789012345678"
    payload["items"][0].update(
        codigo="S" * 10000,
        cantidad="1.00005",
        precio_unitario="123456789012345.123456789",
        descuento_porcentaje="0.00123",
    )
    if compensado:
        payload["items"][0].update(
            cantidad=str(Decimal("1.2345E200000")),
            precio_unitario=str(Decimal("1.2345E-200000")),
        )
    request = EmitirComprobanteRequest.model_validate(payload)
    receipt = await _guardar_sintetico(service, request, point, commit=True)
    db_session.expire_all()
    item = (await db_session.execute(select(ComprobanteItem))).scalar_one()
    assert item.cantidad == request.items[0].cantidad
    assert item.precio_unitario == request.items[0].precio_unitario
    assert item.descuento_porcentaje == Decimal("0.00123")
    assert item.codigo == "S" * 10000
    await db_session.refresh(receipt)
    await db_session.refresh(receipt, ["items"])
    response = ComprobanteDetalleResponse.model_validate(receipt).model_dump(
        mode="json"
    )
    assert Decimal(response["cotizacion"]) == Decimal(payload["cotizacion"])
    assert (
        Decimal(response["total"]) == service._calcular_totales(request.items)["total"]
    )
    assert request.model_dump(mode="json") == payload


def test_orden_tecnico_rechazado_en_preparacion():
    from tests.test_pf03b_importes import request_canonico

    payload = request_canonico()
    payload["items"][0]["orden"] = 2147483648
    with pytest.raises(ValueError, match="orden del ítem"):
        EmitirComprobanteRequest.model_validate(payload)


@pytest.fixture
def legacy_database(tmp_path):
    path = tmp_path / "a01.db"
    url = f"sqlite:///{path.as_posix()}"
    _run_alembic("upgrade", REVISION_INTEGRIDAD_FISCAL, url)
    backup = _backup_env_pf19(path, tmp_path / "backup.db")
    _run_alembic("upgrade", LEGACY_HEAD, url, extra_env=backup)
    _crear_contexto_fiscal_sintetico(path)
    _insertar_comprobante_sintetico(
        path, estado="autorizado", cae="00000000000000", cae_vencimiento="2026-07-13"
    )
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO comprobante_items (id, comprobante_id, codigo, descripcion, cantidad, unidad, precio_unitario, descuento_porcentaje, iva_porcentaje, subtotal, orden) VALUES (1, 1, 'S', 'Sintético', 1.00005, 'unidades', 100.00005, 0, 21, 100, 0)"
        )
    return path, url


def test_cadena_sqlite_preserva_lectura_original_y_downgrade(legacy_database):
    path, url = legacy_database
    _run_alembic("upgrade", A01_HEAD, url)
    with sqlite3.connect(path) as connection:
        _install_sqlite_functions(connection, None)
        values = connection.execute(
            "SELECT cantidad, precio_unitario FROM comprobante_items"
        ).fetchone()
        assert [Decimal(v) for v in values] == [Decimal("1.0001"), Decimal("100.0001")]
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert (
            connection.execute("SELECT cae FROM comprobantes").fetchone()[0]
            == "00000000000000"
        )
        query = "SELECT id FROM lotes_comprobantes_grupos WHERE empresa_id=? AND ambiente=? AND tipo_comprobante=? AND punto_venta_numero=? AND fecha_emision_normalizada=? AND moneda_duplicados=? AND cotizacion_busqueda=? AND total_centavos=? AND identidad_documento_hash=?"
        plan = connection.execute(
            "EXPLAIN QUERY PLAN " + query,
            (
                1,
                "homologacion",
                11,
                1,
                "2026-07-13",
                "PES",
                "0" * 64,
                "10000",
                "0" * 64,
            ),
        ).fetchall()
        assert any("ix_lotes_grupos_dup_documento" in row[3] for row in plan)
    _run_alembic("downgrade", LEGACY_HEAD, url)
    _run_alembic("upgrade", A01_HEAD, url)
    assert _alembic_version(path) == A01_HEAD


def test_downgrade_incompatible_aborta_antes_del_ddl(legacy_database):
    path, url = legacy_database
    _run_alembic("upgrade", A01_HEAD, url)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE comprobante_items SET cantidad='100005E-5', codigo=?", ("S" * 51,)
        )
    output = _run_alembic_failure("downgrade", LEGACY_HEAD, url)
    assert "comprobante_items.cantidad=1" in output
    assert "comprobante_items.codigo=1" in output
    assert _alembic_version(path) == A01_HEAD
    with sqlite3.connect(path) as connection:
        assert (
            connection.execute("SELECT cantidad FROM comprobante_items").fetchone()[0]
            == "100005E-5"
        )
        assert (
            connection.execute(
                "SELECT name FROM sqlite_master WHERE name LIKE '_a01_%'"
            ).fetchall()
            == []
        )


def test_rebuild_sqlite_falla_atomica_y_restaura_foreign_keys(legacy_database):
    path, url = legacy_database
    with sqlite3.connect(path) as connection:
        before = list(connection.iterdump())
    script = """
from sqlalchemy import event
from sqlalchemy.engine import Engine
from alembic import command
from alembic.config import Config
state = {"drops": 0, "failed": False, "restored": False}
@event.listens_for(Engine, "before_cursor_execute")
def fail_mid_rebuild(connection, cursor, statement, parameters, context, many):
    if statement.lstrip().upper().startswith("DROP TABLE"):
        state["drops"] += 1
        if state["drops"] == 2:
            state["failed"] = True
            raise RuntimeError("fallo sintético durante rebuild")
@event.listens_for(Engine, "after_cursor_execute")
def check_foreign_keys(connection, cursor, statement, parameters, context, many):
    if state["failed"] and statement == "PRAGMA foreign_keys=ON":
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
        state["restored"] = True
try:
    command.upgrade(Config("alembic.ini"), "b2c3d4e5f6a7")
except RuntimeError as error:
    assert "fallo sintético" in str(error)
else:
    raise AssertionError("La inyección debía abortar la migración")
assert state["restored"]
print("rollback y foreign_keys verificados")
"""
    from tests.test_alembic_migrations import BACKEND_DIR

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=BACKEND_DIR,
        env={**os.environ, "DATABASE_URL": url, "APP_ENV": "testing"},
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "rollback y foreign_keys verificados" in result.stdout
    with sqlite3.connect(path) as connection:
        assert list(connection.iterdump()) == before
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_importe_no_calculable_rechazado_durante_preparacion():
    from tests.test_pf03b_importes import request_canonico

    payload = request_canonico()
    payload["items"][0]["precio_unitario"] = "1E200000"
    with pytest.raises(ValueError, match="importes.*total válido"):
        EmitirComprobanteRequest.model_validate(payload)
