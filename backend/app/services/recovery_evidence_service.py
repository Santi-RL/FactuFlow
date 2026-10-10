"""Lee un resumen externo sin ejecutar operaciones de recuperación."""

import asyncio
import json
import stat
from pathlib import Path
from uuid import UUID

from pydantic import ValidationError

from app.schemas.recovery import (
    RecoveryCheckResponse,
    RecoveryComparisonResponse,
    RecoveryComponentResponse,
    RecoveryEvidence,
    RecoveryHealthResponse,
)

MAX_EVIDENCE_BYTES = 64 * 1024


def _unique_object(pairs):
    """Rechaza claves duplicadas en lugar de elegir una evidencia ambigua."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Clave repetida.")
        result[key] = value
    return result


def read_recovery_evidence(
    path: str | None, installation_id: str | None
) -> RecoveryHealthResponse:
    """Carga evidencia acotada; ningún fallo revela rutas o contenido privado."""
    if not path or not installation_id:
        return RecoveryHealthResponse(status="not_verified", reason="not_configured")
    try:
        expected_installation = UUID(installation_id)
        evidence_path = Path(path)
        file_stat = evidence_path.stat()
        if (
            not stat.S_ISREG(file_stat.st_mode)
            or file_stat.st_size > MAX_EVIDENCE_BYTES
        ):
            raise ValueError("Archivo inválido.")
        with evidence_path.open("rb") as stream:
            content = stream.read(MAX_EVIDENCE_BYTES + 1)
        if len(content) > MAX_EVIDENCE_BYTES:
            raise ValueError("Archivo excesivo.")
        evidence = RecoveryEvidence.model_validate(
            json.loads(content, object_pairs_hook=_unique_object)
        )
        if evidence.installation_id != expected_installation:
            raise ValueError("Instalación distinta.")
    except FileNotFoundError:
        return RecoveryHealthResponse(status="not_verified", reason="missing")
    except (OSError, ValueError, ValidationError, RecursionError):
        return RecoveryHealthResponse(status="not_verified", reason="invalid")

    def project_check(check):
        return RecoveryCheckResponse(
            result=check.result,
            checked_at=check.checked_at,
            components=check.components,
            time_precision=check.time_precision,
        )

    comparison = evidence.comparison
    return RecoveryHealthResponse(
        status="recorded",
        reason="recorded",
        backup_id=evidence.backup_id,
        purpose=evidence.purpose,
        source_code_sha=evidence.source_code_sha,
        created_at=evidence.created_at,
        captured_at=evidence.captured_at,
        components=[
            RecoveryComponentResponse(name=component.name, state=component.state)
            for component in evidence.components
        ],
        integrity=project_check(evidence.integrity),
        restore=project_check(evidence.restore),
        external_copy=project_check(evidence.external_copy),
        comparison=(
            RecoveryComparisonResponse(
                observed_at=comparison.observed_at,
                database=comparison.database,
                managed_files=comparison.managed_files,
                configuration=comparison.configuration,
                fiscal_writes=comparison.fiscal_writes,
                administrative_writes=comparison.administrative_writes,
            )
            if comparison
            else None
        ),
    )


async def recovery_health(
    path: str | None, installation_id: str | None
) -> RecoveryHealthResponse:
    """El I/O de archivos no bloquea el loop de la API ni llama a ARCA."""
    return await asyncio.to_thread(read_recovery_evidence, path, installation_id)
