"""CLI de solo lectura para inventariar candidatos legacy de PF-19."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from pydantic import ValidationError as PydanticValidationError

from app.core.config import settings
from app.core.database import dispose_database_engines, engine
from app.services.inventario_legacy_pf19_service import (
    FiltrosInventarioLegacyPF19,
    InventarioLegacyPF19Error,
    inventariar_legacy_pf19,
)


def _entero_positivo(valor: str) -> int:
    """Parsea un entero estrictamente positivo para filtros allowlist."""
    try:
        numero = int(valor)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("debe ser un entero positivo") from exc
    if numero <= 0:
        raise argparse.ArgumentTypeError("debe ser un entero positivo")
    return numero


def construir_parser() -> argparse.ArgumentParser:
    """Construye el parser sin aceptar SQL, URLs ni rutas de salida."""
    parser = argparse.ArgumentParser(
        description=(
            "Inventaría candidatos legacy PF-19 en modo de solo lectura y "
            "devuelve JSON sanitizado y privado por stdout."
        )
    )
    parser.add_argument("--empresa-id", type=_entero_positivo, required=True)
    parser.add_argument("--punto-venta", type=_entero_positivo)
    parser.add_argument("--tipo-comprobante", type=_entero_positivo)
    parser.add_argument("--lote-id", type=_entero_positivo)
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Indenta el JSON para revisión humana.",
    )
    return parser


async def ejecutar(args: argparse.Namespace) -> dict:
    """Ejecuta el inventario contra DATABASE_URL sin realizar llamadas ARCA."""
    ambiente = settings.arca_env.strip().lower()
    try:
        filtros = FiltrosInventarioLegacyPF19(
            ambiente_runtime=ambiente,
            empresa_id=args.empresa_id,
            punto_venta=args.punto_venta,
            tipo_comprobante=args.tipo_comprobante,
            lote_id=args.lote_id,
        )
    except PydanticValidationError as exc:
        raise InventarioLegacyPF19Error(
            "ARCA_ENV o los filtros del inventario no son válidos"
        ) from exc
    return await inventariar_legacy_pf19(engine, filtros)


async def ejecutar_y_disponer(args: argparse.Namespace) -> dict:
    """Ejecuta y libera los pools dentro del mismo event loop."""
    try:
        return await ejecutar(args)
    finally:
        await dispose_database_engines()


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada con errores públicos sanitizados."""
    args = construir_parser().parse_args(argv)
    try:
        resultado = asyncio.run(ejecutar_y_disponer(args))
    except InventarioLegacyPF19Error as exc:
        print(f"Inventario PF-19 abortado: {exc}", file=sys.stderr)
        return 2
    except Exception:
        print(
            "Inventario PF-19 abortado por un error interno; no se generó salida.",
            file=sys.stderr,
        )
        return 2
    print(
        json.dumps(
            resultado,
            ensure_ascii=False,
            indent=2 if args.pretty else None,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
