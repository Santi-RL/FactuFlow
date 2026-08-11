"""CLI privada de dos fases para resolver un único candidato legacy PF-19C."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import stat
import sys
from pathlib import Path

from sqlalchemy import select

from app.arca.config import ArcaAmbiente
from app.arca.utils import clean_cuit
from app.arca.wsaa import WSAAClient
from app.arca.wsfev1 import WSFEv1Client
from app.core.database import AsyncSessionLocal, dispose_database_engines, engine
from app.models.certificado import Certificado
from app.models.empresa import Empresa
from app.services.certificados_service import requerir_material_certificado
from app.services.resolucion_legacy_pf19_service import (
    AdaptadorWSFEDiferidoLegacyPF19,
    BackupLegacyPF19,
    PlanLegacyPF19,
    ResolucionLegacyPF19Error,
    SolicitudApplyLegacyPF19,
    SolicitudPlanLegacyPF19,
    aplicar_resolucion_legacy_pf19,
    planificar_resolucion_legacy_pf19,
)


MAX_PLAN_BYTES = 1024 * 1024


class _PlanJsonRetirado(argparse.Action):
    """Rechaza el plan inline sin reflejar su contenido en la salida de la CLI."""

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: object,
        option_string: str | None = None,
    ) -> None:
        """Aborta antes de persistir o registrar el valor entregado por argv."""
        del namespace, values, option_string
        parser.error(
            "--plan-json fue retirado; use --plan-file con un archivo privado o '-'"
        )


def _entero_positivo(valor: str) -> int:
    """Parsea enteros positivos sin aceptar expresiones ni SQL."""
    try:
        numero = int(valor)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("debe ser un entero positivo") from exc
    if numero <= 0:
        raise argparse.ArgumentTypeError("debe ser un entero positivo")
    return numero


def construir_parser() -> argparse.ArgumentParser:
    """Construye una CLI privada, acotada y sin rutas de backup."""
    parser = argparse.ArgumentParser(
        description="Planifica o aplica un cierre legacy PF-19C para un solo intento."
    )
    parser.add_argument("accion", choices=("plan", "apply"))
    parser.add_argument("--intento-id", type=_entero_positivo, required=True)
    parser.add_argument("--empresa-id", type=_entero_positivo, required=True)
    parser.add_argument("--punto-venta", type=_entero_positivo, required=True)
    parser.add_argument("--tipo-comprobante", type=_entero_positivo, required=True)
    parser.add_argument(
        "--plan-file",
        metavar="RUTA",
        help=(
            "Archivo privado UTF-8 con el JSON exacto de plan, o '-' para stdin. "
            "No pase el plan por argumentos."
        ),
    )
    parser.add_argument(
        "--plan-json",
        nargs=1,
        action=_PlanJsonRetirado,
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--actor-usuario-id", type=_entero_positivo)
    parser.add_argument("--confirmar", action="store_true")
    parser.add_argument("--ventana-mantenimiento-confirmada", action="store_true")
    parser.add_argument("--backup-identificador")
    parser.add_argument("--backup-timestamp")
    parser.add_argument("--backup-proposito")
    parser.add_argument("--backup-referencia-codigo")
    parser.add_argument("--backup-sha256")
    parser.add_argument("--pretty", action="store_true")
    return parser


def _solicitud_plan(args: argparse.Namespace) -> SolicitudPlanLegacyPF19:
    """Construye la identidad explícita del intento sin elegir ambiente."""
    return SolicitudPlanLegacyPF19(
        intento_id=args.intento_id,
        empresa_id=args.empresa_id,
        punto_venta=args.punto_venta,
        tipo_comprobante=args.tipo_comprobante,
    )


def _es_archivo_reparse(metadata: os.stat_result) -> bool:
    """Detecta puntos de reanálisis cuando la plataforma expone ese atributo."""
    bandera = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    atributos = getattr(metadata, "st_file_attributes", 0)
    return bool(bandera and atributos & bandera)


def _tiene_permisos_privados_razonables(metadata: os.stat_result) -> bool:
    """Exige modo privado en POSIX; Windows no expone una ACL portable equivalente."""
    if os.name == "nt":
        return True
    permisos_ajenos = stat.S_IRWXG | stat.S_IRWXO
    return not bool(metadata.st_mode & permisos_ajenos)


def _leer_bytes_limitados(entrada: object) -> bytes:
    """Lee un único payload binario sin aceptar planes de tamaño no acotado."""
    try:
        contenido = entrada.read(MAX_PLAN_BYTES + 1)  # type: ignore[attr-defined]
    except (OSError, ValueError) as exc:
        raise ResolucionLegacyPF19Error("No se pudo leer el plan privado") from exc
    if not isinstance(contenido, bytes):
        raise ResolucionLegacyPF19Error("No se pudo leer el plan privado")
    if len(contenido) > MAX_PLAN_BYTES:
        raise ResolucionLegacyPF19Error("El plan privado excede el tamaño permitido")
    return contenido


def _leer_plan_desde_archivo(ruta_texto: str) -> bytes:
    """Lee un archivo regular privado sin revelar su ruta ante un fallo.

    En plataformas que lo soportan, ``O_NOFOLLOW`` protege también la apertura.
    En Windows se verifica el atributo de punto de reanálisis antes y después de
    abrirlo; el operador debe mantener el archivo en una ruta privada ignorada.
    """
    ruta = Path(ruta_texto)
    try:
        metadata_inicial = ruta.lstat()
    except (OSError, ValueError) as exc:
        raise ResolucionLegacyPF19Error(
            "No se pudo abrir un archivo de plan privado"
        ) from exc
    if (
        ruta.is_symlink()
        or not stat.S_ISREG(metadata_inicial.st_mode)
        or _es_archivo_reparse(metadata_inicial)
        or not _tiene_permisos_privados_razonables(metadata_inicial)
    ):
        raise ResolucionLegacyPF19Error(
            "El plan debe provenir de un archivo regular privado"
        )

    banderas = os.O_RDONLY
    if hasattr(os, "O_BINARY"):
        banderas |= os.O_BINARY
    if hasattr(os, "O_NOFOLLOW"):
        banderas |= os.O_NOFOLLOW
    try:
        descriptor = os.open(ruta, banderas)
    except (OSError, ValueError) as exc:
        raise ResolucionLegacyPF19Error(
            "No se pudo abrir un archivo de plan privado"
        ) from exc
    try:
        with os.fdopen(descriptor, "rb", closefd=True) as entrada:
            metadata_abierto = os.fstat(entrada.fileno())
            if (
                not stat.S_ISREG(metadata_abierto.st_mode)
                or _es_archivo_reparse(metadata_abierto)
                or not _tiene_permisos_privados_razonables(metadata_abierto)
            ):
                raise ResolucionLegacyPF19Error(
                    "El plan debe provenir de un archivo regular privado"
                )
            return _leer_bytes_limitados(entrada)
    except ResolucionLegacyPF19Error:
        raise
    except (OSError, ValueError) as exc:
        raise ResolucionLegacyPF19Error("No se pudo leer el plan privado") from exc


def _plan_desde_archivo(args: argparse.Namespace) -> PlanLegacyPF19:
    """Exige el plan inmutable desde stdin o un archivo privado durante apply."""
    if not args.plan_file:
        raise ResolucionLegacyPF19Error("apply requiere --plan-file con el plan exacto")
    if args.plan_file == "-":
        contenido = _leer_bytes_limitados(sys.stdin.buffer)
    else:
        contenido = _leer_plan_desde_archivo(args.plan_file)
    try:
        plan_json = contenido.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ResolucionLegacyPF19Error(
            "El plan privado debe usar UTF-8 válido"
        ) from exc
    try:
        plan = PlanLegacyPF19.model_validate_json(plan_json)
    except Exception as exc:
        raise ResolucionLegacyPF19Error(
            "El plan privado no es un plan PF-19C válido"
        ) from exc
    solicitud = _solicitud_plan(args)
    if (
        plan.intento_id != solicitud.intento_id
        or plan.empresa_id != solicitud.empresa_id
        or plan.punto_venta != solicitud.punto_venta
        or plan.tipo_comprobante != solicitud.tipo_comprobante
    ):
        raise ResolucionLegacyPF19Error("La identidad CLI no coincide con el plan")
    return plan


def _crear_cliente_diferido(plan: PlanLegacyPF19):
    """Devuelve una factory que no inicia WSAA hasta después de revalidar apply."""

    async def crear_cliente(ambiente_texto: str) -> WSFEv1Client:
        """Crea el cliente para el ambiente que el plan ya derivó automáticamente."""
        if ambiente_texto not in plan.ambientes_consultados:
            raise ResolucionLegacyPF19Error("El ambiente no pertenece al plan PF-19C")
        ambiente = ArcaAmbiente(ambiente_texto)
        async with AsyncSessionLocal() as session:
            empresa = await session.get(Empresa, plan.empresa_id)
            if empresa is None:
                raise ResolucionLegacyPF19Error("La empresa del plan no existe")
            certificado = (
                (
                    await session.execute(
                        select(Certificado)
                        .where(
                            Certificado.empresa_id == empresa.id,
                            Certificado.activo.is_(True),
                            Certificado.ambiente == ambiente.value,
                        )
                        .order_by(
                            Certificado.fecha_vencimiento.desc(), Certificado.id.desc()
                        )
                    )
                )
                .scalars()
                .first()
            )
            if certificado is None:
                raise ResolucionLegacyPF19Error(
                    "No hay certificado activo para uno de los ambientes requeridos"
                )
            crt, key = requerir_material_certificado(
                certificado.archivo_crt,
                certificado.archivo_key,
            )
            ticket = await WSAAClient(ambiente).login(
                cert_path=str(crt),
                key_path=str(key),
                cuit=clean_cuit(empresa.cuit),
                servicio="wsfe",
            )
            return WSFEv1Client(ambiente=ambiente, ticket=ticket, cuit=empresa.cuit)

    return crear_cliente


async def ejecutar(args: argparse.Namespace) -> dict[str, object]:
    """Ejecuta plan read-only o apply confirmado para un único intento."""
    if args.accion == "plan":
        return (
            await planificar_resolucion_legacy_pf19(engine, _solicitud_plan(args))
        ).model_dump()

    plan = _plan_desde_archivo(args)
    requeridos = (
        args.actor_usuario_id,
        args.confirmar,
        args.ventana_mantenimiento_confirmada,
        args.backup_identificador,
        args.backup_timestamp,
        args.backup_proposito,
        args.backup_referencia_codigo,
        args.backup_sha256,
    )
    if any(valor in (None, False, "") for valor in requeridos):
        raise ResolucionLegacyPF19Error(
            "apply requiere actor, confirmación, ventana y metadatos completos de backup"
        )
    solicitud = SolicitudApplyLegacyPF19(
        plan=plan,
        actor_usuario_id=args.actor_usuario_id,
        confirmacion="APLICAR_CIERRE_LEGACY_PF19",
        ventana_mantenimiento_confirmada=True,
        backup=BackupLegacyPF19(
            identificador=args.backup_identificador,
            timestamp=args.backup_timestamp,
            proposito=args.backup_proposito,
            referencia_codigo=args.backup_referencia_codigo,
            sha256=args.backup_sha256,
        ),
    )
    async with AsyncSessionLocal() as session:
        return await aplicar_resolucion_legacy_pf19(
            session,
            solicitud,
            AdaptadorWSFEDiferidoLegacyPF19(_crear_cliente_diferido(plan)),
        )


async def ejecutar_y_disponer(args: argparse.Namespace) -> dict[str, object]:
    """Asegura liberar pools también cuando plan o apply abortan."""
    try:
        return await ejecutar(args)
    finally:
        await dispose_database_engines()


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada con salida sanitizada y sin datos de ARCA."""
    args = construir_parser().parse_args(argv)
    try:
        resultado = asyncio.run(ejecutar_y_disponer(args))
    except ResolucionLegacyPF19Error as exc:
        print(f"Resolución legacy PF-19C abortada: {exc}", file=sys.stderr)
        return 2
    except Exception:
        print(
            "Resolución legacy PF-19C abortada por un error interno; no se aplicó un cierre.",
            file=sys.stderr,
        )
        return 2
    print(
        json.dumps(
            resultado,
            ensure_ascii=False,
            sort_keys=True,
            indent=2 if args.pretty else None,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
