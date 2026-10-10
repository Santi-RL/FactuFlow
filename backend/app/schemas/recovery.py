"""Contrato privado y proyección administrativa de evidencia de recuperación."""

from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.schemas.utc_datetime import UTCResponseDateTime

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
ComponentName = Literal["database", "certificates", "configuration", "runtime"]
CheckResult = Literal["verified", "failed", "not_verified"]
ChangeResult = Literal["changed", "not_detected", "unknown"]
Purpose = Literal["pre_update", "pre_maintenance", "pre_resolution", "manual"]


class _EvidenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RecoveryComponent(_EvidenceModel):
    name: ComponentName
    state: Literal["present", "missing", "unknown"]
    sha256: Digest | None = None

    @model_validator(mode="after")
    def validate_digest(self):
        if (self.state == "present") != (self.sha256 is not None):
            raise ValueError("El componente requiere un hash sólo si está presente.")
        return self


class RecoveryCheck(_EvidenceModel):
    result: CheckResult = "not_verified"
    checked_at: AwareDatetime | None = None
    report_sha256: Digest | None = None
    manifest_sha256: Digest | None = None
    components: list[ComponentName] = Field(default_factory=list, max_length=4)
    time_precision: Literal["instant", "minute", "unknown"] = "instant"

    @model_validator(mode="after")
    def validate_proof(self):
        proof = (self.checked_at, self.report_sha256, self.manifest_sha256)
        if self.result == "not_verified":
            if any(value is not None for value in proof) or self.components:
                raise ValueError("Una comprobación desconocida no declara evidencia.")
        elif any(value is None for value in proof) or not self.components:
            raise ValueError("La comprobación requiere instante, informe y alcance.")
        if len(self.components) != len(set(self.components)):
            raise ValueError("Componentes repetidos.")
        return self


class RecoveryComparison(_EvidenceModel):
    observed_at: AwareDatetime
    report_sha256: Digest
    manifest_sha256: Digest
    database: ChangeResult
    database_scope: Literal["all_tables", "partial", "unknown"]
    managed_files: ChangeResult
    configuration: ChangeResult
    fiscal_writes: ChangeResult
    administrative_writes: ChangeResult

    @model_validator(mode="after")
    def validate_changes(self):
        if self.database == "not_detected" and self.database_scope != "all_tables":
            raise ValueError("La igualdad de base requiere cotejar todas las tablas.")
        if self.database == "not_detected" and "changed" in (
            self.fiscal_writes,
            self.administrative_writes,
        ):
            raise ValueError("El cotejo contiene resultados contradictorios.")
        return self


class RecoveryEvidence(_EvidenceModel):
    version: Literal[1]
    installation_id: UUID
    backup_id: UUID
    operation_id: UUID
    purpose: Purpose
    source_code_sha: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
    created_at: AwareDatetime | None
    captured_at: AwareDatetime | None
    manifest_sha256: Digest
    components: list[RecoveryComponent] = Field(max_length=4)
    integrity: RecoveryCheck
    restore: RecoveryCheck
    external_copy: RecoveryCheck = Field(default_factory=RecoveryCheck)
    comparison: RecoveryComparison | None = None

    @field_validator("version", mode="before")
    @classmethod
    def validate_version(cls, value):
        if isinstance(value, bool) or not isinstance(value, int) or value != 1:
            raise ValueError("Versión no soportada.")
        return value

    @model_validator(mode="after")
    def validate_links(self):
        names = [component.name for component in self.components]
        if len(names) != len(set(names)):
            raise ValueError("Componentes repetidos.")
        present = {
            component.name
            for component in self.components
            if component.state == "present"
        }
        for check in (self.integrity, self.restore, self.external_copy):
            if check.result != "not_verified":
                if check.manifest_sha256 != self.manifest_sha256:
                    raise ValueError("La comprobación pertenece a otro respaldo.")
                if check.result == "verified" and not set(check.components) <= present:
                    raise ValueError("La comprobación acredita componentes ausentes.")
        if self.comparison:
            if self.comparison.manifest_sha256 != self.manifest_sha256:
                raise ValueError("El cotejo pertenece a otro respaldo.")
            comparisons = {
                "database": (
                    self.comparison.database,
                    self.comparison.fiscal_writes,
                    self.comparison.administrative_writes,
                ),
                "certificates": (self.comparison.managed_files,),
                "configuration": (self.comparison.configuration,),
            }
            for component, results in comparisons.items():
                if component not in present and any(
                    result != "unknown" for result in results
                ):
                    raise ValueError("El cotejo acredita componentes ausentes.")
        instants = [
            self.integrity.checked_at,
            self.restore.checked_at,
            self.external_copy.checked_at,
        ]
        if self.comparison:
            instants.append(self.comparison.observed_at)
        now = datetime.now(timezone.utc)
        for instant in [self.created_at, self.captured_at, *instants]:
            if instant is not None and instant > now:
                raise ValueError("La evidencia contiene un instante futuro.")
        if self.captured_at and any(
            instant < self.captured_at for instant in instants if instant is not None
        ):
            raise ValueError("La comprobación es anterior al punto respaldado.")
        if self.created_at and any(
            instant < self.created_at for instant in instants if instant is not None
        ):
            raise ValueError("La comprobación es anterior a la creación del respaldo.")
        return self


class RecoveryComponentResponse(BaseModel):
    name: ComponentName
    state: Literal["present", "missing", "unknown"]


class RecoveryCheckResponse(BaseModel):
    result: CheckResult = "not_verified"
    checked_at: UTCResponseDateTime | None = None
    components: list[ComponentName] = Field(default_factory=list)
    time_precision: Literal["instant", "minute", "unknown"] = "instant"


class RecoveryComparisonResponse(BaseModel):
    observed_at: UTCResponseDateTime
    database: ChangeResult
    managed_files: ChangeResult
    configuration: ChangeResult
    fiscal_writes: ChangeResult
    administrative_writes: ChangeResult


class RecoveryHealthResponse(BaseModel):
    status: Literal["recorded", "not_verified"]
    reason: Literal["not_configured", "missing", "invalid", "recorded"]
    scope: Literal["installation"] = "installation"
    current_coverage: Literal["unknown"] = "unknown"
    backup_id: UUID | None = None
    purpose: Purpose | None = None
    source_code_sha: str | None = None
    created_at: UTCResponseDateTime | None = None
    captured_at: UTCResponseDateTime | None = None
    components: list[RecoveryComponentResponse] = Field(default_factory=list)
    integrity: RecoveryCheckResponse = Field(default_factory=RecoveryCheckResponse)
    restore: RecoveryCheckResponse = Field(default_factory=RecoveryCheckResponse)
    external_copy: RecoveryCheckResponse = Field(default_factory=RecoveryCheckResponse)
    comparison: RecoveryComparisonResponse | None = None
