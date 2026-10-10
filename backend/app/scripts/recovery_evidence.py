"""Valida el resumen externo de recuperación; no crea backups ni restaura datos."""

import argparse
import json

from app.services.recovery_evidence_service import read_recovery_evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Resumen privado a comprobar.")
    parser.add_argument(
        "--installation-id", required=True, help="UUID de la instalación."
    )
    args = parser.parse_args()
    result = read_recovery_evidence(args.input, args.installation_id)
    # Sólo estado del contrato: ni archivo, hashes, ruta, identidad o error crudo.
    print(json.dumps({"status": result.status, "reason": result.reason}))
    return 0 if result.status == "recorded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
