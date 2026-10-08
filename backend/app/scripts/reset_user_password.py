"""Restablecimiento asistido por consola, sin promover ni reasignar usuarios."""

import argparse
import asyncio
from datetime import datetime
from getpass import getpass
import sys

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


class RecoveryError(ValueError):
    """Mensaje controlado, sin valores secretos de configuración o credenciales."""


async def reset_password(db: AsyncSession, email: str, password: str) -> None:
    """Cambia únicamente credencial y fecha de revocación; no hace commit."""
    from app.core.security import get_password_hash
    from app.models.usuario import Usuario
    from app.schemas.usuario import UsuarioPasswordReset

    data = UsuarioPasswordReset(password=password)
    users = (
        (
            await db.execute(
                select(Usuario)
                .where(func.lower(Usuario.email) == email.strip().lower())
                .with_for_update()
            )
        )
        .scalars()
        .all()
    )
    if len(users) != 1:
        raise RecoveryError(
            "No existe una cuenta inequívoca para ese correo. No se modificó ninguna cuenta."
        )
    user = users[0]
    user.hashed_password = get_password_hash(data.password)
    user.password_changed_at = datetime.utcnow()
    await db.flush()


async def _run(email: str, password: str) -> None:
    # Inicializar configuración dentro del manejo de errores de consola.
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        async with db.begin():
            await reset_password(db, email, password)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", help="Correo de la cuenta existente.")
    args = parser.parse_args()
    try:
        email = (args.email or input("Correo de la cuenta: ")).strip()
        if not email:
            raise RecoveryError("El correo es obligatorio.")
        password = getpass("Nueva contraseña: ")
        if password != getpass("Repetir contraseña: "):
            raise RecoveryError("Las contraseñas no coinciden.")
        # Validar fuera del contexto de ejecución: nunca imprimir valores secretos.
        if not 6 <= len(password) <= 100 or "\x00" in password:
            raise RecoveryError(
                "La contraseña debe tener entre 6 y 100 caracteres y no contener caracteres nulos."
            )
        asyncio.run(_run(email, password))
    except (KeyboardInterrupt, EOFError):
        print("Operación cancelada.", file=sys.stderr)
        return 130
    except RecoveryError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception:
        print(
            "No se pudo completar el restablecimiento. Revisa la configuración y conexión de la instalación.",
            file=sys.stderr,
        )
        return 1
    print(
        "Contraseña restablecida. Se conservaron cuenta, permisos y datos. Inicia sesión de nuevo; si hay una espera vigente, respétala."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
