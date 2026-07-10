"""Regresiones estáticas de la topología productiva soportada."""

from pathlib import Path


def test_readme_no_inicia_multiples_workers_embebidos() -> None:
    """El runbook no debe levantar varios workers de lotes por instalación."""

    backend_readme = Path(__file__).resolve().parents[1] / "README.md"
    contenido = backend_readme.read_text(encoding="utf-8")

    assert "--workers 1" in contenido
    assert "--workers 4" not in contenido
    assert "BATCH_WORKER_ENABLED=true" in contenido
