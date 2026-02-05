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
import shutil
import sys
import tarfile
import textwrap
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


@dataclass(frozen=True)
class ExtractorInfo:
    name: str


def _repo_root() -> Path:
    # scripts/arca_ws_extract.py -> repo root is parent of scripts/
    return Path(__file__).resolve().parents[1]


def _iter_files(base: Path, exts: set[str]) -> Iterable[Path]:
    for p in base.rglob("*"):
        if p.is_file() and p.suffix.lower() in exts:
            yield p


def _safe_relpath(path: Path, base: Path) -> str:
    return path.relative_to(base).as_posix()


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


def _list_zip(zip_path: Path) -> list[dict]:
    out: list[dict] = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            out.append(
                {
                    "name": info.filename,
                    "size": info.file_size,
                    "compressed": info.compress_size,
                }
            )
    return out


def _list_tgz(tgz_path: Path) -> list[dict]:
    out: list[dict] = []
    with tarfile.open(tgz_path, "r:*") as tf:
        for m in tf.getmembers():
            out.append(
                {
                    "name": m.name,
                    "size": m.size,
                    "type": m.type,
                }
            )
    return out


def _format_contents(entries: list[dict], limit: int) -> str:
    shown = entries[:limit]
    lines = []
    for e in shown:
        name = e.get("name", "")
        size = e.get("size", "")
        lines.append(f"{size}\t{name}")
    if len(entries) > limit:
        lines.append(f"... ({len(entries) - limit} mas)")
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
    docs_dir = Path(args.docs_dir) if args.docs_dir else root / "docs" / "arca-ws"
    out_dir = Path(args.out_dir) if args.out_dir else docs_dir / "_extracted"

    if not docs_dir.exists():
        print(f"[ERROR] No existe el directorio: {docs_dir}", file=sys.stderr)
        return 2

    if args.clean and out_dir.exists():
        shutil.rmtree(out_dir)

    out_dir.mkdir(parents=True, exist_ok=True)

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
        out_txt = out_dir / (rel[:-4] + ".txt")
        manifest["pdfs"].append({"path": rel, "out": _safe_relpath(out_txt, docs_dir)})
        if extractor_fn is None:
            continue
        try:
            text = extractor_fn(pdf_path)
            header = f"[source] {rel}\n[extractor] {extractor_info.name if extractor_info else 'unknown'}\n\n"
            _write_text(out_txt, header + (text or ""))
            pdf_txt_paths.append(_safe_relpath(out_txt, docs_dir))
        except Exception as e:
            err_txt = out_dir / (rel[:-4] + ".error.txt")
            _write_text(err_txt, f"[source] {rel}\n[error] {type(e).__name__}: {e}\n")

    # ZIP/TGZ -> contents listing
    for z_path in sorted(_iter_files(docs_dir, {".zip"}), key=lambda p: p.as_posix()):
        rel = _safe_relpath(z_path, docs_dir)
        out_list = out_dir / (rel + ".contents.txt")
        try:
            entries = _list_zip(z_path)
            _write_text(out_list, _format_contents(entries, args.limit))
            zip_list_paths.append(_safe_relpath(out_list, docs_dir))
            manifest["archives"].append(
                {"path": rel, "type": "zip", "out": _safe_relpath(out_list, docs_dir), "count": len(entries)}
            )
        except Exception as e:
            _write_text(out_list, f"[source] {rel}\n[error] {type(e).__name__}: {e}\n")

    for t_path in sorted(_iter_files(docs_dir, {".tgz", ".tar.gz"}), key=lambda p: p.as_posix()):
        rel = _safe_relpath(t_path, docs_dir)
        out_list = out_dir / (rel + ".contents.txt")
        try:
            entries = _list_tgz(t_path)
            _write_text(out_list, _format_contents(entries, args.limit))
            tgz_list_paths.append(_safe_relpath(out_list, docs_dir))
            manifest["archives"].append(
                {"path": rel, "type": "tgz", "out": _safe_relpath(out_list, docs_dir), "count": len(entries)}
            )
        except Exception as e:
            _write_text(out_list, f"[source] {rel}\n[error] {type(e).__name__}: {e}\n")

    # index + manifest
    idx = _render_index(out_dir, pdf_txt_paths, zip_list_paths, tgz_list_paths, extractor_info)
    _write_text(out_dir / "index.md", idx)
    _write_text(out_dir / "manifest.json", json.dumps(manifest, indent=2, ensure_ascii=True) + "\n")

    print(f"[OK] Generado: {out_dir}")
    if extractor_fn is None:
        print("[OK] Indices y listados creados. (PDFs sin texto extraido).")
    else:
        print("[OK] Texto de PDFs + listados de archivos generados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

