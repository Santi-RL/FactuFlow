"""Evidencia fechada y privada; nunca un permiso implícito de restauración."""

import copy
import json
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.models.evento_sistema import EventoSistema
from app.models.idempotencia_fiscal import OperacionIdempotente
from app.services.recovery_evidence_service import (
    MAX_EVIDENCE_BYTES,
    read_recovery_evidence,
)

INSTALLATION = "00000000-0000-4000-8000-000000000001"
MANIFEST = "a" * 64


def sample_evidence():
    check = {
        "result": "verified",
        "checked_at": "2026-01-02T00:30:00Z",
        "report_sha256": "b" * 64,
        "manifest_sha256": MANIFEST,
        "components": ["database", "certificates", "configuration"],
    }
    return {
        "version": 1,
        "installation_id": INSTALLATION,
        "backup_id": "00000000-0000-4000-8000-000000000002",
        "operation_id": "00000000-0000-4000-8000-000000000003",
        "purpose": "pre_update",
        "source_code_sha": "d" * 40,
        "created_at": "2026-01-01T23:30:00Z",
        "captured_at": "2026-01-01T23:31:00Z",
        "manifest_sha256": MANIFEST,
        "components": [
            {"name": name, "state": "present", "sha256": "c" * 64}
            for name in ["database", "certificates", "configuration"]
        ],
        "integrity": check,
        "restore": copy.deepcopy(check),
        "comparison": {
            "observed_at": "2026-01-02T00:40:00Z",
            "report_sha256": "e" * 64,
            "manifest_sha256": MANIFEST,
            "database": "changed",
            "database_scope": "all_tables",
            "managed_files": "changed",
            "configuration": "not_detected",
            "fiscal_writes": "changed",
            "administrative_writes": "changed",
        },
    }


def save_evidence(tmp_path, value):
    path = tmp_path / "recovery.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return str(path)


def test_projects_only_allowlist_and_keeps_historical_evidence(tmp_path):
    result = read_recovery_evidence(
        save_evidence(tmp_path, sample_evidence()), INSTALLATION
    )
    data = result.model_dump(mode="json")
    assert data["status"] == "recorded"
    assert data["current_coverage"] == "unknown"
    assert data["integrity"]["checked_at"] == "2026-01-02T00:30:00Z"
    assert data["comparison"]["fiscal_writes"] == "changed"
    assert data["external_copy"]["result"] == "not_verified"
    serialized = json.dumps(data)
    for private in ["installation_id", "operation_id", "sha256", "report_sha256"]:
        assert private not in serialized


def test_identical_historical_state_does_not_establish_current_coverage(tmp_path):
    value = sample_evidence()
    for key in ["database", "managed_files", "fiscal_writes", "administrative_writes"]:
        value["comparison"][key] = "not_detected"
    result = read_recovery_evidence(save_evidence(tmp_path, value), INSTALLATION)
    assert result.status == "recorded"
    assert result.current_coverage == "unknown"


def test_unknown_snapshot_missing_component_and_partial_restore_are_honest(tmp_path):
    value = sample_evidence()
    value["captured_at"] = None
    value["components"][1] = {"name": "certificates", "state": "missing"}
    value["integrity"]["components"] = ["database", "configuration"]
    value["restore"]["components"] = ["database"]
    value["comparison"] = None
    result = read_recovery_evidence(save_evidence(tmp_path, value), INSTALLATION)
    assert result.status == "recorded"
    assert result.captured_at is None
    assert result.restore.components == ["database"]
    assert result.components[1].state == "missing"
    assert result.comparison is None


@pytest.mark.parametrize(
    "component,fields",
    [
        ("database", ["database", "fiscal_writes", "administrative_writes"]),
        ("certificates", ["managed_files"]),
        ("configuration", ["configuration"]),
    ],
)
@pytest.mark.parametrize("state", ["missing", "unknown", "omitted"])
@pytest.mark.parametrize("result", ["changed", "not_detected"])
def test_comparison_cannot_claim_results_against_absent_material(
    tmp_path, component, fields, state, result
):
    value = sample_evidence()
    value["components"] = [
        item for item in value["components"] if item["name"] != component
    ]
    if state != "omitted":
        value["components"].append({"name": component, "state": state})
    value["integrity"]["components"].remove(component)
    value["restore"]["components"].remove(component)
    for field in fields:
        value["comparison"][field] = "unknown"
    if component == "database":
        value["comparison"]["fiscal_writes"] = "unknown"
        value["comparison"]["administrative_writes"] = "unknown"
    value["comparison"][fields[0]] = result
    path = save_evidence(tmp_path, value)
    assert read_recovery_evidence(path, INSTALLATION).reason == "invalid"
    value["comparison"][fields[0]] = "unknown"
    assert (
        read_recovery_evidence(save_evidence(tmp_path, value), INSTALLATION).status
        == "recorded"
    )


@pytest.mark.parametrize("field", ["fiscal_writes", "administrative_writes"])
def test_activity_comparison_requires_backed_up_database(tmp_path, field):
    value = sample_evidence()
    value["components"].pop(0)
    value["integrity"]["components"].remove("database")
    value["restore"]["components"].remove("database")
    for key in ["database", "fiscal_writes", "administrative_writes"]:
        value["comparison"][key] = "unknown"
    value["comparison"][field] = "not_detected"
    assert (
        read_recovery_evidence(save_evidence(tmp_path, value), INSTALLATION).reason
        == "invalid"
    )


@pytest.mark.parametrize("field", ["integrity", "restore", "external_copy"])
def test_failed_proof_is_not_promoted_to_success(tmp_path, field):
    value = sample_evidence()
    value[field] = {**value["integrity"], "result": "failed"}
    result = read_recovery_evidence(save_evidence(tmp_path, value), INSTALLATION)
    assert getattr(result, field).result == "failed"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda v: v.update(installation_id=str(UUID(int=9))),
        lambda v: v.update(captured_at="2026-01-01T23:31:00"),
        lambda v: v.update(captured_at="2999-01-01T00:00:00Z"),
        lambda v: v.update(created_at="2026-01-03T00:00:00Z"),
        lambda v: v.update(version=True),
        lambda v: v["restore"].update(checked_at="2025-01-01T00:00:00Z"),
        lambda v: v["restore"].update(manifest_sha256="f" * 64),
        lambda v: v["comparison"].update(manifest_sha256="f" * 64),
        lambda v: v["comparison"].update(database="not_detected"),
        lambda v: v["comparison"].update(
            database="not_detected",
            database_scope="partial",
            fiscal_writes="unknown",
            administrative_writes="unknown",
        ),
        lambda v: v["components"].append(copy.deepcopy(v["components"][0])),
        lambda v: v["restore"].update(report_sha256=None),
        lambda v: v["restore"].update(result="not_verified"),
        lambda v: v["restore"].update(components=["runtime"]),
        lambda v: v.update(private_path="/private/MARKER_SECRET"),
        lambda v: v.update(empresa_id=900),
    ],
)
def test_invalid_ambiguous_or_foreign_evidence_is_sanitized(tmp_path, mutation):
    value = sample_evidence()
    mutation(value)
    result = read_recovery_evidence(save_evidence(tmp_path, value), INSTALLATION)
    assert result.reason == "invalid"
    assert result.backup_id is None
    assert "MARKER_SECRET" not in result.model_dump_json()


@pytest.mark.parametrize(
    "content",
    [b"{", b"\xff", b'{"version":1,"version":1}', b"x" * (MAX_EVIDENCE_BYTES + 1)],
    ids=["malformed", "invalid_utf8", "duplicate_keys", "oversized"],
)
def test_unreadable_or_excessive_document(tmp_path, content):
    path = tmp_path / "private.json"
    path.write_bytes(content)
    assert read_recovery_evidence(str(path), INSTALLATION).reason == "invalid"


def test_missing_removed_or_unconfigured_file_does_not_reuse_success(tmp_path):
    path = save_evidence(tmp_path, sample_evidence())
    assert read_recovery_evidence(path, INSTALLATION).status == "recorded"
    Path(path).unlink()
    assert read_recovery_evidence(path, INSTALLATION).reason == "missing"
    assert read_recovery_evidence(None, INSTALLATION).reason == "not_configured"
    assert read_recovery_evidence(path, None).reason == "not_configured"
    assert read_recovery_evidence(str(tmp_path), INSTALLATION).reason == "invalid"


def test_permission_error_is_sanitized(tmp_path, monkeypatch):
    path = save_evidence(tmp_path, sample_evidence())

    def forbidden_open(*args, **kwargs):
        raise PermissionError("/private/MARKER_SECRET")

    monkeypatch.setattr(Path, "open", forbidden_open)
    result = read_recovery_evidence(path, INSTALLATION)
    assert result.reason == "invalid"
    assert "MARKER_SECRET" not in result.model_dump_json()


async def test_endpoint_requires_admin_before_reading_evidence(
    client, auth_headers, monkeypatch
):
    from app.api import health

    async def forbidden_read(*args):
        raise AssertionError("No debe leer evidencia sin permisos.")

    monkeypatch.setattr(health, "recovery_health", forbidden_read)
    assert (await client.get("/api/health/recovery")).status_code == 403
    assert (
        await client.get("/api/health/recovery", headers=auth_headers)
    ).status_code == 403


async def test_admin_reads_installation_evidence_without_mutating_uncertain_operations(
    client,
    admin_auth_headers,
    db_session,
    test_empresa,
    tmp_path,
    monkeypatch,
):
    value = sample_evidence()
    monkeypatch.setattr(
        settings, "recovery_evidence_path", save_evidence(tmp_path, value)
    )
    monkeypatch.setattr(settings, "recovery_installation_id", INSTALLATION)
    operation = OperacionIdempotente(
        empresa_id=test_empresa.id,
        idempotency_key="synthetic-recovery",
        tipo_operacion="emitir_comprobante",
        payload_hash="0" * 64,
        estado="requiere_reconciliacion",
        error_json={"evidence": "preserved"},
    )
    db_session.add(operation)
    await db_session.commit()
    events_before = await db_session.scalar(select(func.count(EventoSistema.id)))
    for _ in range(2):
        response = await client.get("/api/health/recovery", headers=admin_auth_headers)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "private, no-store"
        assert response.json()["current_coverage"] == "unknown"
        assert "empresa_id" not in response.text
        assert "usuario_id" not in response.text
    await db_session.refresh(operation)
    assert operation.estado == "requiere_reconciliacion"
    assert operation.error_json == {"evidence": "preserved"}
    assert (
        await db_session.scalar(select(func.count(EventoSistema.id))) == events_before
    )


@pytest.mark.parametrize("valid", [True, False])
def test_validation_cli_outputs_only_contract_state(
    tmp_path, monkeypatch, capsys, valid
):
    from app.scripts.recovery_evidence import main

    path = save_evidence(
        tmp_path, sample_evidence() if valid else {"secret": "MARKER_SECRET"}
    )
    monkeypatch.setattr(
        "sys.argv",
        ["recovery_evidence", "--input", path, "--installation-id", INSTALLATION],
    )
    assert main() == (0 if valid else 1)
    output = capsys.readouterr().out
    assert json.loads(output)["status"] == ("recorded" if valid else "not_verified")
    assert "MARKER_SECRET" not in output
    assert path not in output
