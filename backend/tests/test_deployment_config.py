"""Regresiones estáticas de la topología productiva soportada."""

from pathlib import Path


def test_readme_no_inicia_multiples_workers_embebidos() -> None:
    """El runbook no debe levantar varios workers de lotes por instalación."""

    backend_readme = Path(__file__).resolve().parents[1] / "README.md"
    contenido = backend_readme.read_text(encoding="utf-8")

    assert "--workers 1" in contenido
    assert "--workers 4" not in contenido
    assert "BATCH_WORKER_ENABLED=true" in contenido


POOL_DEFAULTS = {
    "DATABASE_API_POOL_SIZE": "4",
    "DATABASE_API_MAX_OVERFLOW": "0",
    "DATABASE_WORKER_POOL_SIZE": "1",
    "DATABASE_POOL_TIMEOUT_SECONDS": "5",
    "DATABASE_POOL_HOLD_WARNING_SECONDS": "10",
}


def test_compose_documenta_limites_pool_api_y_worker() -> None:
    """Desarrollo y producción deben propagar los mismos límites seguros."""
    root = Path(__file__).resolve().parents[2]

    for compose_name in ("docker-compose.yml", "docker-compose.prod.yml"):
        contenido = (root / compose_name).read_text(encoding="utf-8")
        for setting_name, default in POOL_DEFAULTS.items():
            assert f"{setting_name}: ${{{setting_name}:-{default}}}" in contenido


def test_env_example_documenta_limites_pool() -> None:
    """El ejemplo debe hacer visible el techo de conexiones de la aplicación."""
    root = Path(__file__).resolve().parents[2]
    contenido = (root / ".env.example").read_text(encoding="utf-8")

    for setting_name, default in POOL_DEFAULTS.items():
        assert f"{setting_name}={default}" in contenido
    assert "un único proceso Uvicorn" in contenido


def test_runtime_docker_mantiene_un_solo_uvicorn() -> None:
    """La topología embebida no debe multiplicar pools ni workers fiscales."""
    root = Path(__file__).resolve().parents[2]
    dockerfile = (root / "backend" / "Dockerfile").read_text(encoding="utf-8")
    compose_dev = (root / "docker-compose.yml").read_text(encoding="utf-8")
    compose_prod = (root / "docker-compose.prod.yml").read_text(encoding="utf-8")

    assert "uvicorn app.main:app" in dockerfile
    assert "uvicorn app.main:app" in compose_dev
    assert "--workers" not in dockerfile
    assert "--workers" not in compose_dev
    assert "--workers" not in compose_prod
