"""Pruebas de seguridad para scripts operativos fuera del backend."""

from __future__ import annotations

import importlib.util
import json
import sys
import tarfile
import zipfile
import xml.etree.ElementTree as ET

import pytest
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_script(module_name: str, relative_path: str) -> ModuleType:
    """Carga un script del repositorio como módulo de prueba."""
    module_path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_arca_extract_clean_rejects_docs_dir_as_output(tmp_path: Path) -> None:
    """--clean no debe borrar la documentación fuente si el destino es igual."""
    script = _load_script("arca_ws_extract", "scripts/arca_ws_extract.py")
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    source = docs_dir / "fuente.pdf"
    source.write_text("contenido", encoding="utf-8")

    result = script.main(
        ["--docs-dir", str(docs_dir), "--out-dir", str(docs_dir), "--clean"]
    )

    assert result == 2
    assert source.exists()


def test_arca_extract_clean_rejects_parent_output_dir(tmp_path: Path) -> None:
    """--clean no debe borrar un directorio padre que contiene la fuente."""
    script = _load_script("arca_ws_extract", "scripts/arca_ws_extract.py")
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    source = docs_dir / "fuente.pdf"
    source.write_text("contenido", encoding="utf-8")

    result = script.main(
        ["--docs-dir", str(docs_dir), "--out-dir", str(tmp_path), "--clean"]
    )

    assert result == 2
    assert source.exists()


def test_arca_extract_clean_rejects_symlink_output_dir(tmp_path: Path) -> None:
    """--clean no debe seguir enlaces hacia directorios externos."""
    script = _load_script("arca_ws_extract", "scripts/arca_ws_extract.py")
    docs_dir = tmp_path / "docs"
    target_dir = tmp_path / "target"
    out_link = tmp_path / "out-link"
    docs_dir.mkdir()
    target_dir.mkdir()
    existing = target_dir / "usuario.txt"
    existing.write_text("no borrar", encoding="utf-8")
    try:
        out_link.symlink_to(target_dir, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"el entorno no permite crear symlinks: {exc}")

    result = script.main(
        ["--docs-dir", str(docs_dir), "--out-dir", str(out_link), "--clean"]
    )

    assert result == 2
    assert existing.exists()


def test_arca_extract_clean_rejects_unmarked_external_output_dir(
    tmp_path: Path,
) -> None:
    """--clean no debe borrar directorios externos no generados por el script."""
    script = _load_script("arca_ws_extract", "scripts/arca_ws_extract.py")
    docs_dir = tmp_path / "docs"
    out_dir = tmp_path / "externo"
    docs_dir.mkdir()
    out_dir.mkdir()
    existing = out_dir / "usuario.txt"
    existing.write_text("no borrar", encoding="utf-8")

    result = script.main(
        ["--docs-dir", str(docs_dir), "--out-dir", str(out_dir), "--clean"]
    )

    assert result == 2
    assert existing.exists()


def test_arca_extract_does_not_mark_mixed_external_output_dir(
    tmp_path: Path,
) -> None:
    """Un destino externo con archivos previos no queda habilitado para --clean."""
    script = _load_script("arca_ws_extract", "scripts/arca_ws_extract.py")
    docs_dir = tmp_path / "docs"
    out_dir = tmp_path / "externo"
    docs_dir.mkdir()
    out_dir.mkdir()
    existing = out_dir / "usuario.txt"
    existing.write_text("no borrar", encoding="utf-8")

    result = script.main(["--docs-dir", str(docs_dir), "--out-dir", str(out_dir)])
    clean_result = script.main(
        ["--docs-dir", str(docs_dir), "--out-dir", str(out_dir), "--clean"]
    )

    assert result == 0
    assert clean_result == 2
    assert existing.exists()
    assert not (out_dir / script.GENERATED_MARKER).exists()


def test_arca_extract_clean_rejects_unmarked_nested_extracted_dir(
    tmp_path: Path,
) -> None:
    """--clean no debe borrar _extracted anidados no marcados como generados."""
    script = _load_script("arca_ws_extract", "scripts/arca_ws_extract.py")
    docs_dir = tmp_path / "docs"
    nested = docs_dir / "manual" / "_extracted"
    nested.mkdir(parents=True)
    existing = nested / "usuario.txt"
    existing.write_text("no borrar", encoding="utf-8")

    result = script.main(
        ["--docs-dir", str(docs_dir), "--out-dir", str(nested), "--clean"]
    )

    assert result == 2
    assert existing.exists()


def test_arca_extract_manifest_marks_pdf_without_extractor(
    tmp_path: Path, monkeypatch
) -> None:
    """El manifest no debe anunciar TXT inexistente si no hay extractor PDF."""
    script = _load_script("arca_ws_extract", "scripts/arca_ws_extract.py")
    monkeypatch.setattr(script, "_detect_pdf_extractor", lambda: (None, None))
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "fuente.pdf").write_text("contenido", encoding="utf-8")

    result = script.main(["--docs-dir", str(docs_dir)])

    assert result == 0
    manifest = json.loads(
        (docs_dir / "_extracted" / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["pdfs"] == [
        {
            "path": "fuente.pdf",
            "status": "skipped",
            "reason": "pdf_extractor_unavailable",
        }
    ]
    assert not (docs_dir / "_extracted" / "fuente.txt").exists()


def test_arca_extract_processes_tar_gz_files(tmp_path: Path) -> None:
    """La extensión .tar.gz debe entrar en el listado TGZ generado."""
    script = _load_script("arca_ws_extract", "scripts/arca_ws_extract.py")
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    payload = docs_dir / "archivo.txt"
    payload.write_text("contenido", encoding="utf-8")
    archive = docs_dir / "paquete.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(payload, arcname="archivo.txt")

    result = script.main(["--docs-dir", str(docs_dir)])

    assert result == 0
    contents = docs_dir / "_extracted" / "paquete.tar.gz.contents.txt"
    assert contents.exists()
    assert "archivo.txt" in contents.read_text(encoding="utf-8")


def test_arca_extract_records_corrupt_archive_in_manifest(tmp_path: Path) -> None:
    """Los ZIP corruptos deben figurar como error en el manifest generado."""
    script = _load_script("arca_ws_extract", "scripts/arca_ws_extract.py")
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "corrupto.zip").write_text("no es zip", encoding="utf-8")

    result = script.main(["--docs-dir", str(docs_dir)])

    assert result == 0
    manifest = json.loads(
        (docs_dir / "_extracted" / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["archives"][0]["path"] == "corrupto.zip"
    assert manifest["archives"][0]["type"] == "zip"
    assert manifest["archives"][0]["status"] == "error"
    assert manifest["archives"][0]["out"] == "_extracted/corrupto.zip.contents.txt"


def test_arca_extract_allows_external_output_dir(tmp_path: Path) -> None:
    """Un --out-dir externo seguro debe generar manifest sin fallar por rutas."""
    script = _load_script("arca_ws_extract", "scripts/arca_ws_extract.py")
    docs_dir = tmp_path / "docs"
    out_dir = tmp_path / "salida"
    docs_dir.mkdir()
    payload = docs_dir / "archivo.txt"
    payload.write_text("contenido", encoding="utf-8")
    archive = docs_dir / "paquete.zip"
    with zipfile.ZipFile(archive, "w") as zip_file:
        zip_file.write(payload, arcname="archivo.txt")

    result = script.main(["--docs-dir", str(docs_dir), "--out-dir", str(out_dir)])

    assert result == 0
    manifest = out_dir / "manifest.json"
    assert manifest.exists()
    assert "paquete.zip.contents.txt" in manifest.read_text(encoding="utf-8")


def test_arca_extract_limits_archive_entries_while_listing(tmp_path: Path) -> None:
    """--limit debe acotar las entradas escritas y contar las omitidas."""
    script = _load_script("arca_ws_extract", "scripts/arca_ws_extract.py")
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    archive = docs_dir / "paquete.zip"
    with zipfile.ZipFile(archive, "w") as zip_file:
        for index in range(3):
            zip_file.writestr(f"archivo-{index}.txt", "contenido")

    result = script.main(["--docs-dir", str(docs_dir), "--limit", "1"])

    assert result == 0
    contents = (docs_dir / "_extracted" / "paquete.zip.contents.txt").read_text(
        encoding="utf-8"
    )
    assert "archivo-0.txt" in contents
    assert "archivo-1.txt" not in contents
    assert "... (listado truncado por --limit)" in contents


def test_wsaa_tra_unique_id_changes_with_same_clock_tick(monkeypatch) -> None:
    """Dos TRAs consecutivos no deben reutilizar uniqueId aunque el reloj empate."""
    script = _load_script("wsaa_manual", "scripts/wsaa_manual.py")
    monkeypatch.setattr(script.time, "time", lambda: 1_800_000_000)

    first = ET.fromstring(script.build_tra_xml("wsfe")).findtext("./header/uniqueId")
    second = ET.fromstring(script.build_tra_xml("wsfe")).findtext("./header/uniqueId")

    assert first is not None
    assert second is not None
    assert first.isdigit()
    assert second.isdigit()
    assert first != second
    assert int(first) <= 2**32 - 1
    assert int(second) <= 2**32 - 1


def test_wsaa_tra_escapes_service_xml_text() -> None:
    """El servicio WSAA debe escaparse como texto XML seguro."""
    script = _load_script("wsaa_manual", "scripts/wsaa_manual.py")

    xml = script.build_tra_xml("wsfe&test<manual>")
    root = ET.fromstring(xml)

    assert root.findtext("./service") == "wsfe&test<manual>"
    assert "wsfe&amp;test&lt;manual&gt;" in xml


def test_wsaa_login_does_not_print_credentials_by_default(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """La prueba WSAA no debe imprimir Token/Sign salvo pedido explícito."""
    script = _load_script("wsaa_manual", "scripts/wsaa_manual.py")
    cert = tmp_path / "cert.crt"
    key = tmp_path / "cert.key"
    cert.write_text("cert", encoding="utf-8")
    key.write_text("key", encoding="utf-8")

    class FakeService:
        """Servicio WSAA mínimo para simular loginCms."""

        def loginCms(self, cms_b64: str) -> str:  # noqa: N802
            assert cms_b64 == "cms"
            return "<credentials><token>TOKEN</token><sign>SIGN</sign></credentials>"

    class FakeClient:
        """Cliente Zeep mínimo para inyectar el servicio falso."""

        service = FakeService()

        def __init__(self, wsdl: str) -> None:
            assert wsdl

    monkeypatch.setattr(script, "sign_tra", lambda *_args: "cms")
    monkeypatch.setattr(script, "Client", FakeClient)

    result = script.main(["--cert", str(cert), "--key", str(key)])

    output = capsys.readouterr().out
    assert result == 0
    assert "TOKEN" not in output
    assert "SIGN" not in output
    assert "Respuesta recibida" in output


def test_wsaa_login_writes_sensitive_output_with_warning(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """--out debe guardar la respuesta y advertir que contiene Token/Sign."""
    script = _load_script("wsaa_manual", "scripts/wsaa_manual.py")
    cert = tmp_path / "cert.crt"
    key = tmp_path / "cert.key"
    out = tmp_path / "ta.xml"
    cert.write_text("cert", encoding="utf-8")
    key.write_text("key", encoding="utf-8")

    class FakeService:
        """Servicio WSAA mínimo para simular loginCms."""

        def loginCms(self, cms_b64: str) -> str:  # noqa: N802
            assert cms_b64 == "cms"
            return "<credentials><token>TOKEN</token><sign>SIGN</sign></credentials>"

    class FakeClient:
        """Cliente Zeep mínimo para inyectar el servicio falso."""

        service = FakeService()

        def __init__(self, wsdl: str) -> None:
            assert wsdl

    monkeypatch.setattr(script, "sign_tra", lambda *_args: "cms")
    monkeypatch.setattr(script, "Client", FakeClient)

    result = script.main(["--cert", str(cert), "--key", str(key), "--out", str(out)])

    captured = capsys.readouterr()
    assert result == 0
    assert "TOKEN" in out.read_text(encoding="utf-8")
    assert "Token y Sign" in captured.err
    assert "TOKEN" not in captured.out


def test_wsaa_login_refuses_to_overwrite_sensitive_output(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """--out no debe sobrescribir una respuesta existente por defecto."""
    script = _load_script("wsaa_manual", "scripts/wsaa_manual.py")
    cert = tmp_path / "cert.crt"
    key = tmp_path / "cert.key"
    out = tmp_path / "ta.xml"
    cert.write_text("cert", encoding="utf-8")
    key.write_text("key", encoding="utf-8")
    out.write_text("existente", encoding="utf-8")

    class FakeService:
        """Servicio WSAA mínimo para simular loginCms."""

        def loginCms(self, cms_b64: str) -> str:  # noqa: N802
            assert cms_b64 == "cms"
            return "<credentials><token>TOKEN</token><sign>SIGN</sign></credentials>"

    class FakeClient:
        """Cliente Zeep mínimo para inyectar el servicio falso."""

        service = FakeService()

        def __init__(self, wsdl: str) -> None:
            assert wsdl

    monkeypatch.setattr(script, "sign_tra", lambda *_args: "cms")
    monkeypatch.setattr(script, "Client", FakeClient)

    result = script.main(["--cert", str(cert), "--key", str(key), "--out", str(out)])

    captured = capsys.readouterr()
    assert result == 7
    assert out.read_text(encoding="utf-8") == "existente"
    assert "ya existe" in captured.err
