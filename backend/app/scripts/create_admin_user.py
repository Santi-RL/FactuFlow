"""Crear o actualizar un usuario administrador desde consola."""

import argparse
import asyncio
from datetime import datetime
from getpass import getpass
import sys

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash
from app.models.usuario import Usuario


email_adapter = TypeAdapter(EmailStr)


def _build_parser() -> argparse.ArgumentParser:
    """Construir el parser CLI del script."""
    parser = argparse.ArgumentParser(
        description=(
            "Crea un usuario administrador o promueve uno existente. "
            "Usa la base configurada por DATABASE_URL."
        )
    )
    parser.add_argument("--email", help="Email del usuario administrador.")
    parser.add_argument("--nombre", help="Nombre visible del usuario.")
    parser.add_argument(
        "--empresa-id",
        type=int,
        default=None,
        help=(
            "Empresa asociada. Omitir para superadmin global sin empresa fija. "
            "Los administradores pueden seleccionar empresa activa desde la UI."
        ),
    )
    parser.add_argument(
        "--no-reset-password",
        action="store_true",
        help="Si el usuario ya existe, no modifica su contraseña.",
    )
    parser.add_argument(
        "--inactive",
        action="store_true",
        help="Crear o dejar el usuario inactivo.",
    )
    return parser


def _prompt_required(label: str, current_value: str | None = None) -> str:
    """Solicitar un valor obligatorio si no vino por argumento."""
    if current_value:
        return current_value.strip()

    value = input(f"{label}: ").strip()
    if not value:
        raise ValueError(f"{label} es obligatorio.")
    return value


def _validate_email(email: str) -> str:
    """Validar y normalizar el email del usuario."""
    try:
        return str(email_adapter.validate_python(email)).lower()
    except ValidationError as exc:
        raise ValueError("Email invalido.") from exc


def _get_password(args: argparse.Namespace, user_exists: bool) -> str | None:
    """Obtener contraseña inicial o nueva contraseña."""
    if user_exists and args.no_reset_password:
        return None

    action = "Nueva contrasena" if user_exists else "Contrasena"
    password = getpass(f"{action}: ")
    confirmation = getpass("Repetir contrasena: ")
    if password != confirmation:
        raise ValueError("Las contrasenas no coinciden.")

    if len(password) < 6 or len(password) > 100:
        raise ValueError("La contrasena debe tener entre 6 y 100 caracteres.")

    return password


async def _create_or_update_admin(args: argparse.Namespace) -> tuple[Usuario, bool]:
    """Crear o actualizar el usuario administrador."""
    email = _validate_email(_prompt_required("Email", args.email))
    nombre = _prompt_required("Nombre", args.nombre)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Usuario).where(Usuario.email == email))
        user = result.scalar_one_or_none()
        user_exists = user is not None
        password = _get_password(args, user_exists)

        if user is None:
            if password is None:
                raise ValueError("La contrasena es obligatoria para usuarios nuevos.")

            user = Usuario(
                email=email,
                nombre=nombre,
                hashed_password=get_password_hash(password),
                es_admin=True,
                activo=not args.inactive,
                empresa_id=args.empresa_id,
                password_changed_at=datetime.utcnow(),
            )
            db.add(user)
            created = True
        else:
            user.nombre = nombre
            user.es_admin = True
            user.activo = not args.inactive
            user.empresa_id = args.empresa_id
            if password is not None:
                user.hashed_password = get_password_hash(password)
                user.password_changed_at = datetime.utcnow()
            created = False

        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise ValueError(
                "No se pudo guardar el usuario. Verifica que empresa-id exista."
            ) from None

        await db.refresh(user)
        return user, created


def main() -> int:
    """Punto de entrada del comando."""
    parser = _build_parser()
    args = parser.parse_args()

    try:
        user, created = asyncio.run(_create_or_update_admin(args))
    except (KeyboardInterrupt, EOFError):
        print("\nOperacion cancelada.", file=sys.stderr)
        return 130
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    action = "creado" if created else "actualizado"
    scope = (
        f"empresa_id={user.empresa_id}"
        if user.empresa_id is not None
        else "superadmin global"
    )
    status = "activo" if user.activo else "inactivo"
    print(
        f"Usuario admin {action}: id={user.id} email={user.email} "
        f"estado={status} alcance={scope}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
