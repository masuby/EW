"""DOCX to PDF conversion using a pure-Python backend.

In production we avoid shelling out to LibreOffice and instead rely on
Python libraries. The current strategy is:

1. Use the ``docx2pdf`` package if available. On Windows this uses
   Microsoft Word via COM; on macOS it uses the Word app via AppleScript.
2. If ``docx2pdf`` is not installed or conversion fails, raise a clear
   RuntimeError so the caller can decide to fall back to DOCX-only output.
"""

from pathlib import Path


def _ensure_output_dir(docx_path: Path, output_dir: str | None) -> Path:
    """Return the directory where the PDF should be written."""
    if output_dir is None:
        return docx_path.parent
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    return out


def convert_docx_to_pdf(docx_path: str, output_dir: str | None = None) -> str:
    """Convert a .docx file to PDF using docx2pdf.

    Args:
        docx_path: Path to the .docx file.
        output_dir: Directory for the PDF output (defaults to same dir as docx).

    Returns:
        Path to the generated PDF file as a string.

    Raises:
        RuntimeError: If conversion fails or docx2pdf is not available.
        FileNotFoundError: If the input file does not exist.
    """
    try:
        from docx2pdf import convert as _docx2pdf_convert  # type: ignore
    except Exception as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "PDF conversion requires the 'docx2pdf' package and a compatible "
            "Microsoft Word installation. Install with 'pip install docx2pdf' "
            "or set output_format='docx' to disable PDF output."
        ) from exc

    docx_path_obj = Path(docx_path)
    if not docx_path_obj.exists():
        raise FileNotFoundError(f"Input file not found: {docx_path_obj}")

    out_dir = _ensure_output_dir(docx_path_obj, output_dir)

    # docx2pdf always writes <stem>.pdf into the target directory
    try:
        _docx2pdf_convert(str(docx_path_obj), str(out_dir))
    except Exception as exc:  # pragma: no cover - passes through library error
        raise RuntimeError(f"docx2pdf PDF conversion failed: {exc}") from exc

    pdf_path = out_dir / (docx_path_obj.stem + ".pdf")
    if not pdf_path.exists():
        raise RuntimeError(f"Expected PDF not found after conversion: {pdf_path}")

    return str(pdf_path)

