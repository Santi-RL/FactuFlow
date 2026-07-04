"""
Utilidad para generar una capa "consultable" sobre `docs/arca-ws/`.

- Extrae texto de PDFs a `docs/arca-ws/_extracted/**/*.txt` (si hay extractor disponible).
- Lista contenido de ZIP/TGZ a `docs/arca-ws/_extracted/**/*.contents.txt`.
- Genera un indice en `docs/arca-ws/_extracted/index.md`.

Este output es local (no se recomienda commitearlo).
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import shutil
import sys
import tarfile
import textwrap
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


GENERATED_MARKER = ".arca_ws_extract_generated"


@dataclass(frozen=True)
class ExtractorInfo:
    name: str


@dataclass(frozen=True)
class ArchiveListing:
    """Resultado acotado de listar un archivo comprimido."""

    entries: list[dict]
    truncated: bool


def _repo_root() -> Path:
    # scripts/arca_ws_extract.py -> repo root is parent of scripts/
    return Path(__file__).resolve().parents[1]


def _matches_extension(path: Path, exts: set[str]) -> bool:
    """Indica si el archivo termina con alguna extensión soportada."""
    name = path.name.lower()
    return any(name.endswith(ext.lower()) for ext in exts)


def _iter_files(base: Path, exts: set[str]) -> Iterable[Path]:
    for p in base.rglob("*"):
        if p.is_file() and _matches_extension(p, exts):
            yield p


def _safe_relpath(path: Path, base: Path) -> str:
    return path.relative_to(base).as_posix()


def _output_relpath(path: Path, docs_dir: Path, out_dir: Path) -> str:
    """Representa una salida relativa a docs-dir o al directorio generado."""
    if _is_relative_to(path, docs_dir):
        return _safe_relpath(path, docs_dir)
    if _is_relative_to(path, out_dir):
        return _safe_relpath(path, out_dir)
    return path.as_posix()


def _is_relative_to(path: Path, base: Path) -> bool:
    """Devuelve si path está dentro de base sin depender de Python menor."""
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def _absolute_path(path: Path) -> Path:
    """Normaliza una ruta absoluta sin seguir el último componente."""
    return Path(os.path.abspath(path))


def _is_symlink_or_reparse_point(path: Path) -> bool:
    """Detecta enlaces o reparse points antes de escribir o borrar."""
    if path.is_symlink():
        return True
    if os.name != "nt":
        return False
    try:
        attrs = os.stat(path, follow_symlinks=False).st_file_attributes
    except (AttributeError, OSError):
        return False
    return bool(attrs & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _output_dir_is_empty(path: Path) -> bool:
    """Indica si el destino existe como directorio sin contenido."""
    try:
        next(path.iterdir())
    except StopIteration:
        return True
    except OSError:
        return False
    return False


def _output_dir_is_owned(path: Path) -> bool:
    """Valida el marcador nuevo de propiedad del directorio generado."""
    marker = path / GENERATED_MARKER
    try:
        lines = marker.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    return "owned=true" in lines


def _should_write_marker(out_dir: Path, existed_before: bool) -> bool:
    """Evita marcar como propio un directorio externo con archivos previos."""
    if not existed_before:
        return True
    return _output_dir_is_empty(out_dir) or _output_dir_is_owned(out_dir)


def _validate_output_target(out_dir: Path) -> None:
    """Bloquea destinos ambiguos antes de escribir salidas generadas."""
    if _is_symlink_or_reparse_point(out_dir):
        raise ValueError("--out-dir no puede ser un enlace simbólico o junction")
    if out_dir.exists() and not out_dir.is_dir():
        raise ValueError("--out-dir debe ser un directorio")


def _validate_clean_target(docs_dir: Path, out_dir: Path) -> None:
    """Bloquea destinos de limpieza que puedan borrar documentación fuente."""
    _validate_output_target(out_dir)

    if out_dir == docs_dir:
        raise ValueError(
            "--out-dir no puede ser igual a --docs-dir cuando se usa --clean"
        )

    if _is_relative_to(docs_dir, out_dir):
        raise ValueError(
            "--out-dir no puede contener al directorio fuente cuando se usa --clean"
        )

    if _is_relative_to(out_dir, docs_dir) and out_dir.name != "_extracted":
        raise ValueError(
            "cuando --out-dir está dentro de --docs-dir debe llamarse _extracted para usar --clean"
        )

    if (
        out_dir.exists()
        and not _output_dir_is_empty(out_dir)
        and not _output_dir_is_owned(out_dir)
    ):
        raise ValueError(
            "--clean solo puede borrar un directorio existente si fue creado vacío por este script"
        )


def _ensure_parent(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)


def _write_text(path: Path, content: str) -> None:
    _ensure_parent(path)
    path.write_text(content, encoding="utf-8", errors="replace")


def _detect_pdf_extractor() -> tuple[Optional[ExtractorInfo], Optional[callable]]:
    """
    Devuelve (info, func) donde func(pdf_path)->str.

    Orden de preferencia:
    - PyMuPDF (fitz)
    - pdfminer.six
    - pypdf (fallback; calidad variable)
    """
    try:
        import fitz  # type: ignore

        def extract_with_pymupdf(pdf_path: Path) -> str:
            doc = fitz.open(pdf_path)  # type: ignore[attr-defined]
            try:
                parts: list[str] = []
                for page in doc:
                    parts.append(page.get_text("text"))
                return "\n".join(parts)
            finally:
                doc.close()

        return ExtractorInfo("pymupdf"), extract_with_pymupdf
    except Exception:
        pass

    try:
        from pdfminer.high_level import extract_text  # type: ignore

        def extract_with_pdfminer(pdf_path: Path) -> str:
            return extract_text(str(pdf_path))  # type: ignore[misc]

        return ExtractorInfo("pdfminer.six"), extract_with_pdfminer
    except Exception:
        pass

    try:
        from pypdf import PdfReader  # type: ignore

        def extract_with_pypdf(pdf_path: Path) -> str:
            reader = PdfReader(str(pdf_path))  # type: ignore[misc]
            parts: list[str] = []
            for page in reader.pages:
                parts.append(page.extract_text() or "")
            return "\n".join(parts)

        return ExtractorInfo("pypdf"), extract_with_pypdf
    except Exception:
        pass

    return None, None


def _list_zip(zip_path: Path, limit: int) -> ArchiveListing:
    entries: list[dict] = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.filelist:
            if len(entries) >= limit:
                return ArchiveListing(entries=entries, truncated=True)
            entries.append(
                {
                    "name": info.filename,
                    "size": info.file_size,
                    "compressed": info.compress_size,
                }
            )
    return ArchiveListing(entries=entries, truncated=False)


def _list_tgz(tgz_path: Path, limit: int) -> ArchiveListing:
    entries: list[dict] = []
    with tarfile.open(tgz_path, "r:*") as tf:
        for member in tf:
            if len(entries) >= limit:
                return ArchiveListing(entries=entries, truncated=True)
            entries.append(
                {
                    "name": member.name,
                    "size": member.size,
                    "type": member.type,
                }
            )
    return ArchiveListing(entries=entries, truncated=False)


def _format_contents(listing: ArchiveListing) -> str:
    lines = []
    for entry in listing.entries:
        name = entry.get("name", "")
        size = entry.get("size", "")
        lines.append(f"{size}\t{name}")
    if listing.truncated:
        lines.append("... (listado truncado por --limit)")
    return "\n".join(lines) + ("\n" if lines else "")


def _render_index(
    extracted_dir: Path,
    pdf_txts: list[str],
    zip_lists: list[str],
    tgz_lists: list[str],
    extractor: Optional[ExtractorInfo],
) -> str:
    extractor_line = extractor.name if extractor else "no-disponible"
    return textwrap.dedent(
        f"""\
        # ARCA WS - Indice generado

        Este directorio fue generado por `scripts/arca_ws_extract.py`.

        - Extractor PDF: `{extractor_line}`
        - Nota: este output es local y no se recomienda commitearlo.

        ## PDFs (texto extraido)
        {os.linesep.join([f"- `{p}`" for p in pdf_txts]) if pdf_txts else "- (no generado)"}

        ## ZIP (listado de contenidos)
        {os.linesep.join([f"- `{p}`" for p in zip_lists]) if zip_lists else "- (no generado)"}

        ## TGZ (listado de contenidos)
        {os.linesep.join([f"- `{p}`" for p in tgz_lists]) if tgz_lists else "- (no generado)"}
        """
    )


def main(argv: list[str]) -> int:
    """Ejecuta la extracción consultable de documentación ARCA."""
    parser = argparse.ArgumentParser(
        description="Genera una capa consultable sobre docs/arca-ws (texto de PDFs y listados de ZIP/TGZ)."
    )
    parser.add_argument(
        "--docs-dir",
        default=None,
        help="Directorio fuente. Default: <repo>/docs/arca-ws",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Directorio destino. Default: <repo>/docs/arca-ws/_extracted",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Borra el directorio de salida antes de regenerar.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Limite de entradas por ZIP/TGZ para el listado de contenidos.",
    )
    args = parser.parse_args(argv)

    root = _repo_root()
    docs_dir_arg = Path(args.docs_dir) if args.docs_dir else root / "docs" / "arca-ws"
    docs_dir = docs_dir_arg.resolve()
    out_dir_arg = Path(args.out_dir) if args.out_dir else docs_dir / "_extracted"
    out_dir = _absolute_path(out_dir_arg)

    if args.limit < 0:
        print("[ERROR] --limit no puede ser negativo", file=sys.stderr)
        return 2

    if not docs_dir.exists():
        print(f"[ERROR] No existe el directorio: {docs_dir}", file=sys.stderr)
        return 2

    if args.clean:
        try:
            _validate_clean_target(docs_dir, out_dir)
        except ValueError as exc:
            print(f"[ERROR] {exc}", file=sys.stderr)
            return 2

    try:
        _validate_output_target(out_dir)
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    out_dir_existed = out_dir.exists()

    if args.clean and out_dir.exists():
        shutil.rmtree(out_dir)
        out_dir_existed = False

    write_marker = _should_write_marker(out_dir, out_dir_existed)
    out_dir.mkdir(parents=True, exist_ok=True)
    if write_marker:
        _write_text(
            out_dir / GENERATED_MARKER,
            "generated by scripts/arca_ws_extract.py\nowned=true\n",
        )

    extractor_info, extractor_fn = _detect_pdf_extractor()
    if extractor_fn is None:
        print(
            textwrap.dedent(
                """\
                [WARN] No hay extractor de PDF disponible.
                Para habilitar extraccion de texto, instala UNO de estos:

                - PyMuPDF:    pip install pymupdf
                - pdfminer:   pip install pdfminer.six
                - pypdf:      pip install pypdf
                """
            ).rstrip()
        )

    manifest: dict = {
        "docs_dir": str(docs_dir),
        "out_dir": str(out_dir),
        "pdf_extractor": extractor_info.name if extractor_info else None,
        "pdfs": [],
        "archives": [],
    }

    pdf_txt_paths: list[str] = []
    zip_list_paths: list[str] = []
    tgz_list_paths: list[str] = []

    # PDFs -> TXT
    for pdf_path in sorted(_iter_files(docs_dir, {".pdf"}), key=lambda p: p.as_posix()):
        rel = _safe_relpath(pdf_path, docs_dir)
        pdf_record = {"path": rel}
        out_txt = out_dir / (rel[:-4] + ".txt")
        if extractor_fn is None:
            pdf_record.update(
                {"status": "skipped", "reason": "pdf_extractor_unavailable"}
            )
            manifest["pdfs"].append(pdf_record)
            continue
        try:
            text = extractor_fn(pdf_path)
            header = f"[source] {rel}\n[extractor] {extractor_info.name if extractor_info else 'unknown'}\n\n"
            _write_text(out_txt, header + (text or ""))
            out_rel = _output_relpath(out_txt, docs_dir, out_dir)
            pdf_txt_paths.append(out_rel)
            pdf_record.update({"status": "ok", "out": out_rel})
        except Exception as e:
            err_txt = out_dir / (rel[:-4] + ".error.txt")
            _write_text(err_txt, f"[source] {rel}\n[error] {type(e).__name__}: {e}\n")
            pdf_record.update(
                {
                    "status": "error",
                    "error": f"{type(e).__name__}: {e}",
                    "out": _output_relpath(err_txt, docs_dir, out_dir),
                }
            )
        manifest["pdfs"].append(pdf_record)
    # ZIP/TGZ -> contents listing
    for z_path in sorted(_iter_files(docs_dir, {".zip"}), key=lambda p: p.as_posix()):
        rel = _safe_relpath(z_path, docs_dir)
        out_list = out_dir / (rel + ".contents.txt")
        archive_record = {"path": rel, "type": "zip"}
        try:
            listing = _list_zip(z_path, args.limit)
            _write_text(out_list, _format_contents(listing))
            out_rel = _output_relpath(out_list, docs_dir, out_dir)
            zip_list_paths.append(out_rel)
            archive_record.update(
                {
                    "status": "ok",
                    "out": out_rel,
                    "count": len(listing.entries),
                    "truncated": listing.truncated,
                }
            )
        except Exception as e:
            _write_text(out_list, f"[source] {rel}\n[error] {type(e).__name__}: {e}\n")
            archive_record.update(
                {
                    "status": "error",
                    "error": f"{type(e).__name__}: {e}",
                    "out": _output_relpath(out_list, docs_dir, out_dir),
                }
            )
        manifest["archives"].append(archive_record)

    for t_path in sorted(
        _iter_files(docs_dir, {".tgz", ".tar.gz"}), key=lambda p: p.as_posix()
    ):
        rel = _safe_relpath(t_path, docs_dir)
        out_list = out_dir / (rel + ".contents.txt")
        archive_record = {"path": rel, "type": "tgz"}
        try:
            listing = _list_tgz(t_path, args.limit)
            _write_text(out_list, _format_contents(listing))
            out_rel = _output_relpath(out_list, docs_dir, out_dir)
            tgz_list_paths.append(out_rel)
            archive_record.update(
                {
                    "status": "ok",
                    "out": out_rel,
                    "count": len(listing.entries),
                    "truncated": listing.truncated,
                }
            )
        except Exception as e:
            _write_text(out_list, f"[source] {rel}\n[error] {type(e).__name__}: {e}\n")
            archive_record.update(
                {
                    "status": "error",
                    "error": f"{type(e).__name__}: {e}",
                    "out": _output_relpath(out_list, docs_dir, out_dir),
                }
            )
        manifest["archives"].append(archive_record)

    # index + manifest
    idx = _render_index(
        out_dir, pdf_txt_paths, zip_list_paths, tgz_list_paths, extractor_info
    )
    _write_text(out_dir / "index.md", idx)
    _write_text(
        out_dir / "manifest.json",
        json.dumps(manifest, indent=2, ensure_ascii=True) + "\n",
    )

    print(f"[OK] Generado: {out_dir}")
    if extractor_fn is None:
        print("[OK] Indices y listados creados. (PDFs sin texto extraido).")
    else:
        print("[OK] Texto de PDFs + listados de archivos generados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
